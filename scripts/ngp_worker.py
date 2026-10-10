#!/usr/bin/env python3
"""Executor de uma unica combinacao do grid search (1 processo = 1 run).

Treina o instant-ngp via pyngp, avalia no conjunto de teste seguindo o mesmo
protocolo de vendor/instant-ngp/scripts/run.py, e grava metrics.json.

REGRA INVIOLAVEL: este processo nunca termina sem escrever metrics.json. Toda
saida passa pelo bloco `finally` de main(). Falha silenciosa na coleta e
exatamente o modo de erro que este experimento existe para eliminar.

Uso (normalmente disparado pelo grid_runner.py, nao a mao):

    python3 scripts/ngp_worker.py \
        --scene data/nerf_synthetic/lego/transforms_train.json \
        --test-transforms data/nerf_synthetic/lego/transforms_test.json \
        --network runs/exp01/lego_T19_F4_L8_s0/network.json \
        --out-dir runs/exp01/lego_T19_F4_L8_s0 \
        --n-steps 5000 --batch-size 262144 --seed 0
"""

import argparse
import json
import os
import re
import signal
import statistics
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Constantes do protocolo de avaliacao. Copiadas de
# vendor/instant-ngp/scripts/run.py (bloco --test_transforms, linhas 257-317)
# para que os numeros sejam comparaveis aos da literatura.
# NAO alterar sem registrar no manifest.
# ---------------------------------------------------------------------------
BACKGROUND_COLOR = [0.0, 0.0, 0.0, 1.0]  # preto, como no run.py deste repositorio
RENDER_MIN_TRANSMITTANCE = 1e-4

# O loss so e recalculado quando training_step % 16 == 0 (src/testbed.cu:4625),
# e o teste usa o valor ANTES do incremento. Lendo testbed.loss logo apos
# testbed.train() com este passo, as amostras caem em training_step 1, 17, 33...
# — sempre valores crus e distintos, nunca repetidos.
LOSS_SAMPLE_STRIDE = 16

# Passo de amostragem dos contadores do controlador adaptativo (spec 4.2).
COUNTER_SAMPLE_STRIDE = 100

# Acima disto a linha de base da GPU contamina a medicao de pico (spec 5.1).
VRAM_BASELINE_WARN_MB = 500

# Substrings que identificam falta de memoria nas excecoes vindas do C++.
OOM_MARKERS = (
    "out of memory",
    "outofmemory",
    "cudaerrormemoryallocation",
    "cuda_error_out_of_memory",
    "bad_alloc",
)


class WorkerTimeout(Exception):
    """Levantada quando o orquestrador manda SIGTERM por estouro de timeout."""


# ---------------------------------------------------------------------------
# Amostragem de VRAM
# ---------------------------------------------------------------------------
class VramSampler:
    """Thread daemon que amostra NVML a cada `interval` segundos.

    Em WSL2 o campo usedGpuMemory de nvmlDeviceGetComputeRunningProcesses volta
    None mesmo com o PID corretamente listado (verificado nesta maquina). Por
    isso o metodo primario e o consumo do device menos a linha de base, e a
    leitura por processo fica como registro secundario quando disponivel.
    """

    def __init__(self, interval=0.05):
        self.interval = interval
        self.available = False
        self.error = None
        self.baseline_mb = None
        self.peak_process_mb = None
        self.peak_device_mb = None
        self.min_device_mb = None
        self.method = "unavailable"
        self._pid = os.getpid()
        self._stop = threading.Event()
        self._thread = None
        self._nvml = None
        self._handle = None
        self._process_readings = 0

        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.available = True
        except Exception as exc:  # pynvml ausente ou driver sem NVML
            self.error = f"{type(exc).__name__}: {exc}"

    def _read(self):
        """Retorna (mb_do_processo_ou_None, mb_do_device)."""
        mine = None
        try:
            for proc in self._nvml.nvmlDeviceGetComputeRunningProcesses(self._handle):
                if proc.pid == self._pid and proc.usedGpuMemory is not None:
                    mine = proc.usedGpuMemory / 1024**2
        except Exception:
            pass  # a leitura do device abaixo continua valendo
        device = self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used / 1024**2
        return mine, device

    def measure_baseline(self):
        """Le a linha de base. Precisa rodar ANTES de importar o pyngp."""
        if not self.available:
            return None
        # Media de algumas leituras: o lado Windows oscila em WSL2.
        readings = []
        for _ in range(5):
            readings.append(self._read()[1])
            time.sleep(0.02)
        self.baseline_mb = round(statistics.median(readings), 1)
        self.min_device_mb = self.baseline_mb
        self.peak_device_mb = self.baseline_mb
        return self.baseline_mb

    def start(self):
        if not self.available:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                mine, device = self._read()
            except Exception:
                self._stop.wait(self.interval)
                continue
            if mine is not None:
                self._process_readings += 1
                self.peak_process_mb = mine if self.peak_process_mb is None else max(self.peak_process_mb, mine)
            self.peak_device_mb = device if self.peak_device_mb is None else max(self.peak_device_mb, device)
            self.min_device_mb = device if self.min_device_mb is None else min(self.min_device_mb, device)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.available:
            # Declara explicitamente qual metodo valeu: a metodologia precisa
            # dizer como o pico foi medido, e nao escolher em silencio.
            self.method = "process" if self._process_readings > 0 else "device_minus_baseline"
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass

    def current_device_mb(self):
        """Leitura pontual, usada para registrar a VRAM no instante de um OOM."""
        if not self.available:
            return None
        try:
            return round(self._read()[1], 1)
        except Exception:
            return None

    def peak_mb(self):
        """Pico atribuivel a este processo, pelo metodo que estiver disponivel."""
        if self.method == "process" and self.peak_process_mb is not None:
            return round(self.peak_process_mb, 1)
        if self.peak_device_mb is not None and self.baseline_mb is not None:
            return round(max(0.0, self.peak_device_mb - self.baseline_mb), 1)
        return None


# ---------------------------------------------------------------------------
# Metricas de qualidade
# ---------------------------------------------------------------------------
def linear_to_srgb(img):
    """Identica a scripts/common.py:129, replicada para nao depender do sys.path."""
    limit = 0.0031308
    return np.where(img > limit, 1.055 * (img ** (1.0 / 2.4)) - 0.055, 12.92 * img)


def mse2psnr(x):
    return -10.0 * np.log(x) / np.log(10.0)


class LpipsScorer:
    """LPIPS AlexNet, a rede padrao da literatura NeRF.

    Carregado apos o fim do treino e usado vista a vista, sem acumular as
    imagens: guardar os 200 pares de 800x800 float32 custaria ~3 GB de RAM.
    Com --lpips-device cpu nao toca na GPU de forma alguma.
    """

    def __init__(self, device):
        import torch
        import lpips as lpips_pkg

        self._torch = torch
        self.device = device
        self.version = getattr(lpips_pkg, "__version__", None)
        self.net = lpips_pkg.LPIPS(net="alex", verbose=False).to(device)

    def score(self, render, ref):
        torch = self._torch
        with torch.no_grad():
            # lpips espera NCHW normalizado em [-1, 1]
            a = torch.from_numpy(render).permute(2, 0, 1).unsqueeze(0).to(self.device) * 2.0 - 1.0
            b = torch.from_numpy(ref).permute(2, 0, 1).unsqueeze(0).to(self.device) * 2.0 - 1.0
            return float(self.net(a, b).item())


# ---------------------------------------------------------------------------
# Fluxo principal de uma run
# ---------------------------------------------------------------------------
def execute(args, metrics, sampler):
    # -- 1. Setup -----------------------------------------------------------
    t_setup_start = time.perf_counter()

    # O .so pode estar em build/ ou build*/, dependendo de como o fork foi
    # compilado. Import tardio e proposital: so depois da linha de base de VRAM.
    ngp_root = Path(args.ngp_root).resolve()
    for so in sorted(ngp_root.glob("build*/**/pyngp*.so")):
        sys.path.insert(0, str(so.parent))
        break
    else:
        raise RuntimeError(f"pyngp*.so nao encontrado em {ngp_root}/build*")

    import pyngp as ngp  # noqa: E402

    testbed = ngp.Testbed()
    testbed.root_dir = str(ngp_root)

    # A semente precisa ser atribuida ANTES de reload_network_from_file(): e la
    # que m_rng e o Trainer a consomem (src/testbed.cu:4163 e 4383).
    seed_supported = hasattr(testbed, "seed")
    metrics["seed_supported"] = seed_supported
    if seed_supported:
        testbed.seed = int(args.seed)

    # Sempre o transforms_train.json, nunca o diretorio: passar a pasta faz o
    # loader varrer train+val+test e treinar em 400 imagens, teste incluso.
    testbed.load_training_data(args.scene)
    metrics["n_train_images"] = int(testbed.nerf.training.dataset.n_images)

    testbed.reload_network_from_file(args.network)
    metrics["n_params"] = int(testbed.n_params())
    metrics["n_encoding_params"] = int(testbed.n_encoding_params())

    # Registrado sempre: dois dos tres ajustes mexem no TREINO, entao PSNRs de
    # execucoes com e sem a opcao nao sao comparaveis entre si.
    metrics["nerf_compatibility"] = bool(args.nerf_compatibility)
    if args.nerf_compatibility:
        # Mesmo bloco de scripts/run.py:164-188.
        testbed.color_space = ngp.ColorSpace.SRGB
        testbed.nerf.cone_angle_constant = 0
        testbed.nerf.training.random_bg_color = False

    # O eixo do grid: numero-alvo de amostras por batch. Diferente de
    # n_rays_per_batch, este valor nao e reajustado dinamicamente pelo ngp.
    testbed.training_batch_size = int(args.batch_size)
    metrics["batch_size_effective_before"] = int(testbed.training_batch_size)

    testbed.shall_train = True
    metrics["t_setup_s"] = round(time.perf_counter() - t_setup_start, 3)

    # -- 2. Treino ----------------------------------------------------------
    loss_history = []
    rays_samples, batch_samples = [], []
    n_steps = int(args.n_steps)

    # Contadores do controlador adaptativo. Com B fixo, quem flutua e o numero de
    # raios: o ngp ajusta rays_per_batch para que measured_batch_size persiga B.
    # Quantos raios uma cena precisa para preencher o mesmo orcamento de amostras
    # e um proxy de ocupacao — Lego e Chair diferem aqui (spec 4.2).
    counters = getattr(testbed.nerf.training, "n_rays_per_batch", None) is not None
    metrics["counters_available"] = counters

    t_train_start = time.perf_counter()
    for step in range(n_steps):
        # train() executa um passo completo (prep do grid de densidade + passo
        # do otimizador) e ja sincroniza o stream CUDA no fim (testbed.cu:4641).
        # Preferido a frame(): frame() para de treinar em silencio quando o ngp
        # seta m_train=false, e o laco `while frame()` vira loop infinito.
        testbed.train(int(args.batch_size))

        if step % LOSS_SAMPLE_STRIDE == 0:
            loss_history.append([int(testbed.training_step), float(testbed.loss)])

        # Primeiros passos descartados: rays_per_batch parte de 4096 e leva ~60
        # passos para convergir, enquanto a grade de densidade ainda esta poda.
        if counters and step % COUNTER_SAMPLE_STRIDE == 0 and step >= COUNTER_SAMPLE_STRIDE:
            rays_samples.append(int(testbed.nerf.training.n_rays_per_batch))
            batch_samples.append(int(testbed.nerf.training.measured_batch_size))

        # Deteccao precoce de treino natimorto: com a build compilada para a
        # arquitetura errada o ngp emite "Nerf training generated 0 samples" e
        # o loss fica cravado em zero. Melhor abortar do que gastar 5000 passos.
        if step == 200 and all(v == 0.0 for _, v in loss_history):
            raise RuntimeError(
                "loss identicamente zero apos 200 passos: o treino nao gerou amostras. "
                "Verifique se a build corresponde a compute capability desta GPU."
            )
    t_train = time.perf_counter() - t_train_start

    metrics["t_train_s"] = round(t_train, 3)
    metrics["steps_per_s"] = round(n_steps / t_train, 2) if t_train > 0 else None
    metrics["training_step_final"] = int(testbed.training_step)
    metrics["loss_history"] = loss_history
    metrics["batch_size_effective_after"] = int(testbed.training_batch_size)

    # loss_final = media das amostras da janela final, nao um valor instantaneo.
    # Com --loss-window 100 sao ~6 amostras (o loss so e recalculado a cada 16
    # passos); 800 da ~50, pelo mesmo custo.
    tail = [v for s, v in loss_history if s > n_steps - int(args.loss_window)]
    metrics["loss_final"] = round(statistics.fmean(tail), 8) if tail else None
    metrics["loss_final_n_samples"] = len(tail)
    metrics["loss_window"] = int(args.loss_window)

    if counters:
        metrics["n_rays_per_batch_final"] = int(testbed.nerf.training.n_rays_per_batch)
        metrics["measured_batch_size_final"] = int(testbed.nerf.training.measured_batch_size)
        if rays_samples:
            metrics["n_rays_effective_mean"] = round(statistics.fmean(rays_samples), 1)
            metrics["n_rays_effective_std"] = round(statistics.pstdev(rays_samples), 1) if len(rays_samples) > 1 else 0.0
            metrics["samples_per_batch_mean"] = round(statistics.fmean(batch_samples), 1)
            # Amostras por raio: quanto cada raio precisa marchar. Cena mais
            # ocupada => mais amostras por raio => menos raios para o mesmo B.
            metrics["samples_per_ray_mean"] = round(
                statistics.fmean(batch_samples) / max(1.0, statistics.fmean(rays_samples)), 2
            )
            # B e o alvo; measured deve orbitar em torno dele. Divergencia grande
            # indica que o controlador nao convergiu (cena vazia, treino abortado).
            drift = abs(statistics.fmean(batch_samples) - args.batch_size) / max(1, args.batch_size)
            metrics["batch_size_drift"] = round(drift, 4)
            if drift > 0.10:
                metrics["batch_not_converged"] = True

    if args.save_snapshot:
        testbed.save_snapshot(args.save_snapshot, False)

    # -- 3. Avaliacao -------------------------------------------------------
    # Protocolo identico ao de scripts/run.py:269-291.
    t_eval_start = time.perf_counter()

    testbed.background_color = BACKGROUND_COLOR
    testbed.snap_to_pixel_centers = True
    testbed.nerf.render_min_transmittance = RENDER_MIN_TRANSMITTANCE
    testbed.shall_train = False
    testbed.load_training_data(args.test_transforms)
    testbed.render_with_lens_distortion = True

    n_test = int(testbed.nerf.training.dataset.n_images)
    view_indices = list(range(0, n_test, max(1, int(args.test_stride))))
    metrics["test_views"] = len(view_indices)
    metrics["test_views_available"] = n_test
    metrics["spp"] = int(args.spp)

    renders_dir = Path(args.out_dir) / "renders"
    if args.keep_renders:
        renders_dir.mkdir(parents=True, exist_ok=True)

    psnr_per_view, ssim_per_view, ssim_ngp_per_view, mse_per_view = [], [], [], []
    lpips_per_view = []

    from skimage.metrics import structural_similarity

    # LPIPS instanciado aqui: o treino ja terminou, entao nao ha disputa por
    # VRAM, e assim nao e preciso reter as imagens ate o fim do laco.
    #
    # Falha no LPIPS nao pode derrubar a run: PSNR e SSIM sao as metricas
    # centrais e ja custaram o treino inteiro. Registra o erro e segue.
    scorer = None
    if args.lpips_device != "none":
        t_lpips_start = time.perf_counter()
        try:
            scorer = LpipsScorer(args.lpips_device)
            metrics["t_lpips_load_s"] = round(time.perf_counter() - t_lpips_start, 3)
        except Exception as exc:
            metrics["lpips_error"] = f"{type(exc).__name__}: {exc}"
            print(f"[worker] LPIPS indisponivel ({exc}); seguindo com PSNR e SSIM", flush=True)

    for i in view_indices:
        resolution = testbed.nerf.training.dataset.metadata[i].resolution
        testbed.set_camera_to_training_view(i)

        testbed.render_ground_truth = True
        ref_image = testbed.render(resolution[0], resolution[1], 1, True)
        testbed.render_ground_truth = False
        image = testbed.render(resolution[0], resolution[1], int(args.spp), True)

        # Render e referencia passam pelo mesmo caminho e pelo mesmo
        # background_color: a composicao de alpha e simetrica por construcao.
        A = np.clip(linear_to_srgb(image[..., :3]), 0.0, 1.0).astype(np.float32)
        R = np.clip(linear_to_srgb(ref_image[..., :3]), 0.0, 1.0).astype(np.float32)

        # Piso em mse para que uma vista perfeita nao produza inf, que quebraria
        # o JSON e contaminaria a media.
        mse = max(float(np.mean((A - R) ** 2)), 1e-12)
        mse_per_view.append(mse)
        psnr_per_view.append(float(mse2psnr(mse)))

        # SSIM do skimage sobre sRGB 8 bits, como pede a spec 4.4.
        A8 = (A * 255.0 + 0.5).astype(np.uint8)
        R8 = (R * 255.0 + 0.5).astype(np.uint8)
        ssim_per_view.append(float(structural_similarity(R8, A8, channel_axis=-1, data_range=255)))

        # SSIM proprio do instant-ngp (luminancia + blur 5-tap, common.py:175).
        # Nao e comparavel ao do skimage; gravado so para conferir com o run.py.
        ssim_ngp_per_view.append(float(_ngp_ssim(A, R)))

        if scorer is not None:
            try:
                lpips_per_view.append(scorer.score(A, R))
            except Exception as exc:
                metrics.setdefault("lpips_error", f"{type(exc).__name__}: {exc}")
                scorer = None

        if args.keep_renders:
            _write_png(renders_dir / f"view_{i:04d}.png", A8)
            if i == view_indices[0]:
                _write_png(renders_dir / f"ref_{i:04d}.png", R8)

    metrics["t_eval_s"] = round(time.perf_counter() - t_eval_start, 3)

    metrics["psnr_per_view"] = [round(v, 4) for v in psnr_per_view]
    metrics["psnr"] = round(statistics.fmean(psnr_per_view), 4)
    metrics["psnr_median"] = round(statistics.median(psnr_per_view), 4)
    metrics["psnr_std"] = round(statistics.pstdev(psnr_per_view), 4) if len(psnr_per_view) > 1 else 0.0
    # PSNR do MSE medio, como o psnr_avgmse do run.py:314.
    metrics["psnr_avgmse"] = round(float(mse2psnr(statistics.fmean(mse_per_view))), 4)
    metrics["ssim"] = round(statistics.fmean(ssim_per_view), 5)
    metrics["ssim_ngp"] = round(statistics.fmean(ssim_ngp_per_view), 5)

    if scorer is not None and lpips_per_view:
        metrics["lpips"] = round(statistics.fmean(lpips_per_view), 5)
        metrics["lpips_per_view"] = [round(v, 5) for v in lpips_per_view]
        metrics["lpips_version"] = scorer.version
        metrics["lpips_device"] = args.lpips_device

    metrics["status"] = "ok"


def _ngp_ssim(a, b):
    """SSIM do instant-ngp (scripts/common.py:175-192), para conferencia."""
    from scipy.ndimage import convolve1d

    def blur(x):
        k = np.array([0.120078, 0.233881, 0.292082, 0.233881, 0.120078])
        return convolve1d(convolve1d(x, k, axis=0), k, axis=1)

    def luminance(x):
        return 0.2126 * x[:, :, 0] + 0.7152 * x[:, :, 1] + 0.0722 * x[:, :, 2]

    a, b = luminance(a), luminance(b)
    mA, mB = blur(a), blur(b)
    sA, sB = blur(a * a) - mA**2, blur(b * b) - mB**2
    sAB = blur(a * b) - mA * mB
    c1, c2 = 0.01**2, 0.03**2
    p1 = (2.0 * mA * mB + c1) / (mA * mA + mB * mB + c1)
    p2 = (2.0 * sAB + c2) / (sA + sB + c2)
    return np.mean(p1 * p2)


def _write_png(path, img_uint8):
    import imageio

    imageio.imwrite(str(path), img_uint8)


# ---------------------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Executa uma combinacao do grid search do instant-ngp")
    ap.add_argument("--scene", required=True, help="transforms_train.json (NUNCA o diretorio da cena)")
    ap.add_argument("--network", required=True, help="JSON de rede desta combinacao")
    ap.add_argument("--test-transforms", required=True, help="transforms_test.json")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=262144,
                    help="training_batch_size: amostras-alvo por batch (variavel controlada)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--test-stride", type=int, default=4, help="avalia 1 a cada N vistas de teste")
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--lpips-device", default="cpu", choices=["cpu", "cuda", "none"])
    ap.add_argument("--ngp-root", default=str(Path(__file__).resolve().parent.parent / "vendor" / "instant-ngp"),
                    help="raiz do fork do instant-ngp (contem build/ com o pyngp)")
    ap.add_argument("--keep-renders", action="store_true")
    ap.add_argument("--save-snapshot", default="")
    ap.add_argument("--loss-window", type=int, default=800,
                    help="janela final, em passos, para a media do loss_final")
    # PADRAO DESLIGADO desde a migracao para cena real (exp02). O bloco de
    # compatibilidade zera o cone_angle_constant, que e justamente o mecanismo
    # que torna viavel marchar por uma cena nao-limitada com aabb_scale alto.
    # Era o padrao correto no exp01 (Synthetic-NeRF) e e o errado aqui.
    # Ver SPEC-exp02-cena-real.md secao 2.4.
    ap.add_argument("--nerf-compatibility", action="store_true", default=False,
                    help="protocolo do NeRF original (run.py:164); DESLIGADO por padrao, "
                         "adequado ao Synthetic-NeRF e inadequado a captura real")
    ap.add_argument("--no-nerf-compatibility", dest="nerf_compatibility", action="store_false")
    # Metadados do exp02. Todos tem derivacao automatica; os argumentos existem
    # para o caso de o nome do arquivo nao seguir a convencao transforms_fN.
    ap.add_argument("--dataset", default=None,
                    help="nome da cena; padrao: diretorio que contem o transforms")
    ap.add_argument("--downsample-factor", type=int, default=None,
                    help="padrao: lido do sufixo _fN do transforms (1 se ausente)")
    ap.add_argument("--test-split-rule", default=None,
                    help="padrao: campo test_split_rule do transforms de teste")
    return ap.parse_args()


# ---------------------------------------------------------------------------
# Metadados da cena (exp02)
#
# Tudo aqui sai de arquivo, sem tocar a GPU, e e coletado ANTES do treino: assim
# o metrics.json de uma run que termina em OOM ainda carrega a procedencia
# completa. Metadado que so existe na run bem-sucedida obriga a retroagir dados
# depois, que e exatamente o que estas colunas existem para evitar.
# ---------------------------------------------------------------------------
DOWNSAMPLE_RE = re.compile(r"transforms_f(\d+)")


def scene_metadata(args):
    meta = {
        "dataset": None, "aabb_scale": None, "image_resolution": None,
        "downsample_factor": None, "n_test_images": None, "test_split_rule": None,
    }
    scene_path = Path(args.scene)
    meta["dataset"] = args.dataset or scene_path.parent.name

    try:
        data = json.loads(scene_path.read_text())
        meta["aabb_scale"] = data.get("aabb_scale")
        w, h = data.get("w"), data.get("h")
        if w and h:
            meta["image_resolution"] = f"{int(w)}x{int(h)}"
        meta["n_train_images_json"] = len(data.get("frames", []))
    except Exception as exc:
        meta["metadata_error"] = f"scene: {type(exc).__name__}: {exc}"

    if args.downsample_factor is not None:
        meta["downsample_factor"] = int(args.downsample_factor)
    else:
        m = DOWNSAMPLE_RE.search(scene_path.name)
        # transforms.json sem sufixo _fN e a resolucao cheia: fator 1.
        meta["downsample_factor"] = int(m.group(1)) if m else 1

    try:
        test_data = json.loads(Path(args.test_transforms).read_text())
        meta["n_test_images"] = len(test_data.get("frames", []))
        # split_holdout.py grava test_split_rule dentro do proprio JSON, entao a
        # regra viaja junto com os dados em vez de depender da linha de comando.
        meta["test_split_rule"] = args.test_split_rule or test_data.get("test_split_rule")
    except Exception as exc:
        meta["test_split_rule"] = args.test_split_rule
        meta["metadata_error"] = f"test: {type(exc).__name__}: {exc}"

    return meta


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "metrics.json"

    # Status inicial pessimista: se o processo morrer de forma que nem o finally
    # rode (SIGKILL), o arquivo simplesmente nao existe e o orquestrador trata
    # como crash. Qualquer outra saida passa pelo finally e grava algo valido.
    metrics = {
        "status": "crash",
        "error": "worker terminou sem concluir",
        "run_tag": out_dir.name,
        "scene": args.scene,
        "network": args.network,
        "n_steps": args.n_steps,
        "batch_size": args.batch_size,
        "seed": args.seed,
        "test_stride": args.test_stride,
        "spp": args.spp,
        "pid": os.getpid(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # Procedencia coletada antes do treino, para sobreviver a um OOM.
    metrics.update(scene_metadata(args))
    metrics["nerf_compatibility"] = bool(args.nerf_compatibility)

    def on_sigterm(signum, frame):
        raise WorkerTimeout("SIGTERM recebido (timeout do orquestrador)")

    signal.signal(signal.SIGTERM, on_sigterm)

    sampler = VramSampler()
    metrics["vram_baseline_mb"] = sampler.measure_baseline()
    metrics["nvml_error"] = sampler.error

    # Em WSL2 o pico so pode ser medido como (device - linha de base), entao tudo
    # que o lado Windows estiver usando vira ruido em vram_peak_mb. Medido nesta
    # maquina: ~900-1200 MB com a area de trabalho ociosa, ~3800 MB com um jogo
    # aberto. Acima do limiar o aviso e serio, nao cosmetico.
    baseline = metrics["vram_baseline_mb"]
    if baseline is not None and baseline > VRAM_BASELINE_WARN_MB:
        metrics["vram_baseline_high"] = True
        print(f"[worker] AVISO: linha de base da GPU em {baseline:.0f} MB "
              f"(limiar {VRAM_BASELINE_WARN_MB} MB). Feche consumidores de GPU no "
              f"Windows: vram_peak_mb fica contaminado e o treino fica mais lento.",
              flush=True)

    sampler.start()

    try:
        execute(args, metrics, sampler)
    except WorkerTimeout as exc:
        metrics["status"] = "timeout"
        metrics["error"] = str(exc)
    except KeyboardInterrupt:
        metrics["status"] = "interrupted"
        metrics["error"] = "KeyboardInterrupt"
    except BaseException as exc:  # inclusive SystemExit e erros do C++
        text = f"{type(exc).__name__}: {exc}"
        metrics["status"] = "oom" if any(m in text.lower() for m in OOM_MARKERS) else "crash"
        metrics["error"] = text
        metrics["traceback"] = traceback.format_exc()
        metrics["vram_at_failure_mb"] = sampler.current_device_mb()
    finally:
        sampler.stop()
        metrics["vram_peak_mb"] = sampler.peak_mb()
        metrics["vram_peak_process_mb"] = (
            round(sampler.peak_process_mb, 1) if sampler.peak_process_mb is not None else None
        )
        metrics["vram_peak_device_mb"] = (
            round(sampler.peak_device_mb, 1) if sampler.peak_device_mb is not None else None
        )
        metrics["vram_device_min_mb"] = (
            round(sampler.min_device_mb, 1) if sampler.min_device_mb is not None else None
        )
        metrics["vram_method"] = sampler.method

        # n_rays_per_batch nao tem binding em pyngp nesta build: o campo fica
        # explicitamente nulo em vez de zero, para nao poluir medias nem sugerir
        # que foi medido. Ver docs/metodo/PIPELINE.md, secao "Limitacoes e
        # ressalvas".
        metrics.setdefault("n_rays_effective_mean", None)
        metrics.setdefault("samples_per_batch_mean", None)

        tmp = metrics_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
        os.replace(tmp, metrics_path)  # troca atomica: nunca um JSON pela metade
        print(f"[worker] status={metrics['status']} -> {metrics_path}", flush=True)

    # OOM e um resultado do trabalho, nao um erro do script: delimita a fronteira
    # de viabilidade da GPU. Retorna 0 para o grid seguir adiante.
    return 0 if metrics["status"] in ("ok", "oom") else 1


if __name__ == "__main__":
    sys.exit(main())
