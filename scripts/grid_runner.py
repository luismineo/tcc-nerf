#!/usr/bin/env python3
"""Orquestrador do grid search de hiperparametros do Instant-NGP.

Monta o grid, dispara um subprocesso ngp_worker.py por combinacao, le o
metrics.json de cada um e consolida results.csv.

Um processo por combinacao, de proposito: isola a medicao de pico de VRAM (sem
fragmentacao acumulada entre runs) e faz com que uma combinacao que estoure os
6 GB nao derrube as outras 53.

Este arquivo nao importa torch nem pyngp. Mantem-se leve.

Executar a partir da raiz do projeto (o diretorio que contem scripts/ e vendor/):

    python3 scripts/grid_runner.py --exp-id exp01 --dry-run
    python3 scripts/grid_runner.py --exp-id exp01
    python3 scripts/grid_runner.py --exp-id exp01 --resume
"""

import argparse
import copy
import csv
import itertools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Layout do projeto. Tudo e derivado da localizacao deste arquivo, entao os
# comandos funcionam de qualquer diretorio de trabalho.
#
#   tcc-nerf/
#     scripts/      <- este arquivo
#     data/nerf_synthetic/{lego,chair}
#     runs/
#     vendor/instant-ngp/   <- o fork, com os patches de patches/
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NGP_ROOT = PROJECT_ROOT / "vendor" / "instant-ngp"
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data" / "mip_nerf"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs"
WORKER = Path(__file__).resolve().parent / "ngp_worker.py"

# ---------------------------------------------------------------------------
# Espaco de busca.
#
# T = encoding.log2_hashmap_size   (tamanho da tabela de hash)
# F = encoding.n_features_per_level
# B = training_batch_size          (amostras-alvo por batch)
#
# NOTA METODOLOGICA: o terceiro eixo e training_batch_size, nao
# n_rays_per_batch. Este build do pyngp nao expoe n_rays_per_batch (o campo
# vive em Testbed::NerfCounters, sem binding pybind11) e, mesmo se expusesse,
# ele quase nao move a VRAM: no workspace de treino (testbed_nerf.cu:3009-3040)
# os termos proporcionais a rays_per_batch somam ~44 bytes por raio, enquanto os
# proporcionais a training_batch_size incluem coords = B*16*7*4 bytes (~117 MB
# no default). O eixo que a Fronteira de Pareto precisa varrer e B.
# ---------------------------------------------------------------------------
GRID = {
    "T": [15, 17, 19],
    "F": [2, 4, 8],
    "L": [4, 8, 16],
}

# Caminho pontuado no JSON de rede -> chave do grid. Validado contra o base.json
# antes de qualquer treino: caminho inexistente aborta com erro explicito.
NETWORK_PATHS = {
    "T": "encoding.log2_hashmap_size",
    "F": "encoding.n_features_per_level",
    "L": "encoding.n_levels",
}

# --- per_level_scale derivado -------------------------------------------------
# ARMADILHA: o base.json nao define per_level_scale, entao o tiny-cuda-nn assume
# b = 2. Com b fixo, a resolucao mais fina e N_min * b^(L-1) e varia com L:
#   L=4  -> 128        L=8 -> 2048        L=16 -> 524288
# Variar L com b fixo mudaria o numero de niveis E a resolucao maxima em quatro
# ordens de grandeza ao mesmo tempo, e todo o efeito seria atribuido a L.
#
# Aqui b e derivado para segurar N_max constante, que e a pratica padrao:
#   b = (N_max / N_min)^(1/(L-1))
# Com N_min=16 e N_max=2048, L=8 devolve b=2.0000 — exatamente o base.json, de
# modo que o baseline continua intocado e coincide com um ponto do grid.
GRID_N_MIN = 16       # encoding.base_resolution do base.json
GRID_N_MAX_UNIT = 2048  # resolucao mais fina alvo SOBRE O CUBO UNITARIO

# CORRECAO exp02. O comentario acima descrevia o comportamento do exp01 e
# tornou-se falso ao migrar para cena real. O tiny-cuda-nn NAO assume b=2
# quando per_level_scale esta ausente: quem decide e o Instant-NGP, em
# testbed.cu:4248, e ele DERIVA o valor a partir do aabb_scale:
#
#     b = exp( log(2048 * aabb_scale / base_resolution) / (L - 1) )
#
# No Synthetic-NeRF o aabb_scale esta ausente do transforms, o ngp assume 1, e
# a formula devolve exatamente 2.0 -- por isso a afirmacao valia no exp01. Com
# o aabb_scale=4 de garden ela devolve 2.438.
#
# Consequencia se nao corrigido: o baseline (base.json intocado) receberia
# b=2.438 enquanto o ponto de grid L=8 receberia b=2.0, ou seja, resolucao mais
# fina 4x diferente. Baseline e grid deixariam de ser comparaveis, e a intencao
# declarada -- "L=8 coincide com o base.json" -- se perderia em silencio.
#
# A correcao preserva a intencao original: o alvo passa a ser o mesmo que o ngp
# usaria, 2048 * aabb_scale sobre o cubo unitario.
def grid_n_max(aabb_scale):
    return GRID_N_MAX_UNIT * aabb_scale

# B (training_batch_size) deixa de ser eixo e passa a variavel controlada.
# Motivo metodologico: B nao e hiperparametro do modelo. Reduzir B com o numero
# de iteracoes fixo nao produz um modelo menor, produz o MESMO modelo treinado
# com menos amostras — a queda de PSNR seria efeito de orcamento de treino, nao
# de capacidade. Ver docs/metodo/PIPELINE.md, secao "Por que o terceiro eixo e
# n_levels".
FIXED_BATCH_SIZE = 262144   # default do instant-ngp (1<<18)

# Varredura separada de B, numa configuracao mediana de Lego, reportada a parte
# como "efeito do orcamento de amostras, sob controle".
BATCH_SWEEP = [65536, 131072, 262144]
BATCH_SWEEP_CONFIG = {"scene": "garden", "T": 17, "F": 4, "L": 8}


def per_level_scale(n_levels, aabb_scale):
    """b tal que N_min * b^(L-1) == N_max, com N_max = 2048 * aabb_scale.

    Com esse alvo, L=8 devolve exatamente o b que o Instant-NGP derivaria do
    base.json intocado -- entao o baseline coincide com um ponto do grid, que
    era a intencao declarada do desenho.
    """
    if n_levels <= 1:
        return 1.0
    return (grid_n_max(aabb_scale) / GRID_N_MIN) ** (1.0 / (n_levels - 1))


def aabb_da_cena(data_root, scene):
    """Le o aabb_scale do transforms da cena -- ele vive no dado, nao no grid."""
    fator = DOWNSAMPLE[scene]
    p = Path(data_root) / SCENES[scene] / f"transforms_f{fator}_train.json"
    return int(json.loads(p.read_text())["aabb_scale"])

# Nome da cena -> subdiretorio em data/nerf_synthetic/. Cada um precisa conter
# transforms_train.json e transforms_test.json.
# exp02: cenas reais nao-limitadas do Mip-NeRF 360. O exp01 rodava
# {"lego","chair"} em data/nerf_synthetic e continua valido como estudo
# preliminar -- para reproduzi-lo, passe --data-root e --scenes.
SCENES = {"garden": "garden", "bonsai": "bonsai"}

# Fator de reducao calibrado por cena (Etapa 1). Define QUAL transforms e usado:
# transforms_f<N>_train.json / _test.json, gerados pelo split_holdout.py.
#
# Ambas calibradas na Etapa 1 (ver docs/relatorios/RELATORIO-etapa1-calibracao.md):
#   garden  f2 2594x1681, aabb_scale=4, split 161/24
#   bonsai  f2 1559x1039, aabb_scale=8, split 255/37
# O aabb_scale otimo DIFERE entre as cenas, entao o per_level_scale derivado
# tambem difere (N_max = 2048 * aabb_scale). Os efeitos de T/F/L permanecem
# comparaveis dentro de cada cena; os valores absolutos de b, nao entre elas.
DOWNSAMPLE = {"garden": 2, "bonsai": 2}
SCENES_CALIBRADAS = {"garden", "bonsai"}

SEEDS = [0]

CSV_FIELDS = [
    "run_tag", "scene", "kind", "is_baseline", "seed", "T", "F", "L", "per_level_scale",
    "batch_size", "n_steps",
    # Procedencia do dataset (exp02). Coletada pelo worker a partir dos JSONs da
    # cena, antes do treino, entao aparece tambem nas linhas com status oom.
    "dataset", "aabb_scale", "n_train_images", "n_test_images", "image_resolution",
    "downsample_factor", "test_split_rule",
    "psnr", "psnr_std", "psnr_median", "ssim", "ssim_ngp", "lpips", "loss_final",
    "vram_peak_mb", "vram_peak_device_mb", "vram_baseline_mb", "vram_device_min_mb", "vram_method",
    "t_train_s", "t_eval_s", "t_setup_s", "steps_per_s",
    "n_rays_effective_mean", "n_rays_effective_std", "samples_per_batch_mean",
    "samples_per_ray_mean", "batch_size_drift", "test_views", "spp",
    "n_params", "n_encoding_params", "mlp_impl", "nerf_compatibility",
    "status", "error", "timestamp",
]

# Colunas que ficam VAZIAS (nunca zero) quando status != ok, para nao poluir medias.
NUMERIC_FIELDS = [
    "psnr", "psnr_std", "psnr_median", "ssim", "ssim_ngp", "lpips", "loss_final",
    "t_eval_s", "steps_per_s", "n_params",
]

MLP_RE = re.compile(r"Density model:.*?--\[(\w*MLP)\(")


# ---------------------------------------------------------------------------
def get_by_path(cfg, dotted):
    node = cfg
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    return node


def set_by_path(cfg, dotted, value):
    keys = dotted.split(".")
    node = cfg
    for key in keys[:-1]:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    if keys[-1] not in node:
        raise KeyError(dotted)
    node[keys[-1]] = value


def validate_grid(base_cfg):
    """Aborta cedo se um caminho do grid nao existir no base.json."""
    bad = [p for p in NETWORK_PATHS.values() if not _path_exists(base_cfg, p)]
    if bad:
        raise SystemExit(
            "Caminhos inexistentes no base-config: " + ", ".join(bad)
        )


def _path_exists(cfg, dotted):
    try:
        get_by_path(cfg, dotted)
        return True
    except KeyError:
        return False


def build_runs(args):
    """Ordem fixa e deterministica: baselines, grid (cena, T, F, L), varredura de B."""
    runs = []
    for scene in args.scenes:
        for seed in SEEDS:
            runs.append({
                "run_tag": f"{scene}_baseline_s{seed}", "kind": "baseline",
                "scene": scene, "is_baseline": True, "seed": seed,
                "T": None, "F": None, "L": None, "B": FIXED_BATCH_SIZE,
            })
    for scene in args.scenes:
        for T, F, L in itertools.product(GRID["T"], GRID["F"], GRID["L"]):
            for seed in SEEDS:
                runs.append({
                    "run_tag": f"{scene}_T{T}_F{F}_L{L}_s{seed}", "kind": "grid",
                    "scene": scene, "is_baseline": False, "seed": seed,
                    "T": T, "F": F, "L": L, "B": FIXED_BATCH_SIZE,
                })
    if args.batch_sweep:
        c = BATCH_SWEEP_CONFIG
        if c["scene"] in args.scenes:
            for B in BATCH_SWEEP:
                for seed in SEEDS:
                    runs.append({
                        "run_tag": f"{c['scene']}_T{c['T']}_F{c['F']}_L{c['L']}_B{B}_s{seed}",
                        "kind": "batch_sweep", "scene": c["scene"], "is_baseline": False,
                        "seed": seed, "T": c["T"], "F": c["F"], "L": c["L"], "B": B,
                    })
    # O aabb_scale vem do transforms da cena, nao do grid: e ele que define o
    # alvo de resolucao mais fina e, portanto, o per_level_scale de cada run.
    cache = {}
    for r in runs:
        if r["scene"] not in cache:
            cache[r["scene"]] = aabb_da_cena(args.data_root, r["scene"])
        r["aabb_scale"] = cache[r["scene"]]
    return runs


def write_network_json(run, base_cfg, path):
    """Deep copy do base.json com sobrescrita de T, F, L e per_level_scale."""
    cfg = copy.deepcopy(base_cfg)
    if not run["is_baseline"]:
        set_by_path(cfg, NETWORK_PATHS["T"], run["T"])
        set_by_path(cfg, NETWORK_PATHS["F"], run["F"])
        set_by_path(cfg, NETWORK_PATHS["L"], run["L"])
        # per_level_scale nao existe no base.json, entao e inserido (nao
        # sobrescrito): set_by_path exigiria a chave preexistente.
        cfg["encoding"]["per_level_scale"] = round(
            per_level_scale(run["L"], run["aabb_scale"]), 6)
    path.write_text(json.dumps(cfg, indent=2))
    return cfg


def collect_manifest(args, base_cfg, runs):
    def cmd(c, cwd=None):
        try:
            return subprocess.run(c, capture_output=True, text=True, timeout=20, cwd=cwd).stdout.strip()
        except Exception as exc:
            return f"indisponivel ({type(exc).__name__})"

    def pyver(mod):
        try:
            m = __import__(mod)
            return getattr(m, "__version__", "?")
        except Exception:
            return "ausente"

    return {
        "exp_id": args.exp_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "n_runs": len(runs),
        "grid": GRID,
        "network_paths": NETWORK_PATHS,
        "third_axis_note": (
            "O terceiro eixo e n_levels (L), nao training_batch_size. B nao e "
            "hiperparametro do modelo: com o numero de iteracoes fixo, reduzir B "
            "treina o MESMO modelo com menos amostras, confundindo orcamento de "
            "treino com capacidade. Ver docs/metodo/PIPELINE.md."
        ),
        "per_level_scale_rule": {
            "formula": "b = (2048 * aabb_scale / N_min) ** (1 / (L - 1))",
            "n_min": GRID_N_MIN,
            "n_max_por_cena": {s: grid_n_max(aabb_da_cena(args.data_root, s))
                               for s in args.scenes},
            "values": {
                s: {L: round(per_level_scale(L, aabb_da_cena(args.data_root, s)), 6)
                    for L in GRID["L"]}
                for s in args.scenes},
            "why": (
                "O base.json nao define per_level_scale, e quem preenche NAO e o "
                "tcnn com b=2: e o Instant-NGP, que deriva o valor do aabb_scale "
                "em testbed.cu:4248. Com b fixo, variar L mudaria tambem a "
                "resolucao mais fina e todo o efeito seria atribuido a L. "
                "Derivando b com N_max = 2048 * aabb_scale, N_max fica constante "
                "entre os L e L=8 reproduz exatamente o b do base.json, de modo "
                "que o baseline coincide com um ponto do grid. No exp01 o "
                "aabb_scale estava ausente (o ngp assume 1) e a formula devolvia "
                "b=2; em garden, com aabb_scale=4, devolve 2.438."
            ),
        },
        "batch_size_fixed": FIXED_BATCH_SIZE,
        "batch_sweep": BATCH_SWEEP if args.batch_sweep else [],
        "batch_sweep_config": BATCH_SWEEP_CONFIG if args.batch_sweep else None,
        "project_root": str(PROJECT_ROOT),
        "ngp_root": args.ngp_root,
        "data_root": args.data_root,
        "scenes": {s: str(Path(args.data_root) / SCENES[s]) for s in args.scenes},
        "seeds": SEEDS,
        "n_steps": args.n_steps,
        "test_stride": args.test_stride,
        "spp": args.spp,
        "lpips_device": args.lpips_device,
        "nerf_compatibility": args.nerf_compatibility,
        "timeout_s": args.timeout,
        "background_color": [0.0, 0.0, 0.0, 1.0],
        "background_note": "preto, identico ao bloco --test_transforms de scripts/run.py",
        "base_config_path": args.base_config,
        "base_config": base_cfg,
        "fixed_params": {
            "n_levels": get_by_path(base_cfg, "encoding.n_levels"),
            "base_resolution": get_by_path(base_cfg, "encoding.base_resolution"),
            "loss_otype": get_by_path(base_cfg, "loss.otype"),
            "network": get_by_path(base_cfg, "network"),
            "rgb_network": get_by_path(base_cfg, "rgb_network"),
            "optimizer": get_by_path(base_cfg, "optimizer"),
        },
        # Procedencia do fork do instant-ngp, nao do projeto: e o commit dele que
        # determina o binario. As alteracoes locais estao em patches/.
        "ngp_git_commit": cmd(["git", "rev-parse", "HEAD"], cwd=args.ngp_root),
        "ngp_git_dirty": bool(cmd(["git", "status", "--porcelain"], cwd=args.ngp_root)),
        "ngp_local_patches": sorted(p.name for p in (PROJECT_ROOT / "patches").glob("*.patch")),
        "gpu": cmd(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        "nvcc": cmd(["nvcc", "--version"]).splitlines()[-1:] or ["indisponivel"],
        "platform": platform.platform(),
        "python": sys.version,
        "versions": {m: pyver(m) for m in ["numpy", "skimage", "torch", "lpips", "pynvml", "scipy", "imageio"]},
        "execution_order": [r["run_tag"] for r in runs],
    }


# steps/s medidos nesta maquina (RTX 2060 6 GB, WSL2) em runs completas de 5000
# passos com o proprio ngp_worker.py, B=262144 e a **GPU ociosa**. Com B fixo, o
# que governa a velocidade e o tamanho do modelo; L e o melhor proxy simples.
#
#   T=15 F=2 L=4  -> 56,1 steps/s     T=19 F=4 L=8 -> 33,8     T=19 F=8 L=16 -> 16,4
#
# ATENCAO: com a GPU compartilhada com o Windows os mesmos numeros cairam para
# 3,0 steps/s (11x pior). Se a estimativa nao bater, o problema quase certamente
# nao e o modelo — e outra coisa usando a GPU.
# Recalibre com:
#   python3 scripts/grid_runner.py --exp-id calib --scenes lego --n-steps 5000 \
#     --no-warmup --no-batch-sweep --only lego_baseline lego_T15_F2_L4 lego_T19_F8_L16
STEPS_PER_S_BY_L = {4: 56.0, 8: 33.8, 16: 16.4}
DEFAULT_STEPS_PER_S = 33.8


def steps_per_s(run):
    """steps/s estimado. Escala inversa com B fora do valor calibrado."""
    sps = STEPS_PER_S_BY_L.get(run.get("L"), DEFAULT_STEPS_PER_S)
    B = run.get("B") or FIXED_BATCH_SIZE
    return sps * (FIXED_BATCH_SIZE / B)


def estimate(args, runs):
    """Estimativa de tempo e disco, com steps/s dependente de B."""
    n_views_grid = len(range(0, 200, max(1, args.test_stride)))
    n_views_base = len(range(0, 200, max(1, args.baseline_test_stride)))
    total = 0.0
    disk_views = 0
    for run in runs:
        n_views = n_views_base if run["is_baseline"] else n_views_grid
        total += args.setup_s + args.n_steps / steps_per_s(run) + n_views * args.eval_s_per_view
        disk_views += n_views
    return {
        "n_runs": len(runs),
        "n_views": n_views_grid,
        "n_views_base": n_views_base,
        "total_s": total,
        "per_run_s": total / max(1, len(runs)),
        "disk_mb": disk_views * 0.40 if args.keep_renders else 0.0,
    }


def fmt_hms(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def row_from_metrics(run, metrics, mlp_impl):
    row = {k: "" for k in CSV_FIELDS}
    row.update({
        "run_tag": run["run_tag"],
        "scene": run["scene"],
        "kind": run.get("kind", "grid"),
        "is_baseline": run["is_baseline"],
        "seed": run["seed"],
        "T": "" if run["T"] is None else run["T"],
        "F": "" if run["F"] is None else run["F"],
        "L": "" if run["L"] is None else run["L"],
        "per_level_scale": "" if run["L"] is None else round(
            per_level_scale(run["L"], run["aabb_scale"]), 6),
        "batch_size": metrics.get("batch_size", "" if run["B"] is None else run["B"]),
        "n_steps": metrics.get("n_steps", ""),
        "status": metrics.get("status", "crash"),
        "error": (metrics.get("error") or "").replace("\n", " ")[:300],
        "timestamp": metrics.get("timestamp", ""),
        "mlp_impl": mlp_impl or "",
    })
    # VRAM, tempos e contadores existem mesmo em falha: sao justamente o dado
    # interessante de um OOM. So as metricas de qualidade ficam vazias.
    for key in ["vram_peak_mb", "vram_peak_device_mb", "vram_baseline_mb",
                "vram_device_min_mb", "vram_method", "t_train_s", "t_setup_s",
                "test_views", "spp", "n_rays_effective_mean", "n_rays_effective_std",
                "samples_per_batch_mean", "samples_per_ray_mean", "batch_size_drift",
                "n_encoding_params", "nerf_compatibility",
                # Procedencia: precisa estar em TODA linha, nao so nas ok, para
                # nao ser preciso retroagir metadado depois.
                "dataset", "aabb_scale", "n_train_images", "n_test_images",
                "image_resolution", "downsample_factor", "test_split_rule"]:
        value = metrics.get(key)
        row[key] = "" if value is None else value

    if metrics.get("status") == "ok":
        for key in NUMERIC_FIELDS:
            value = metrics.get(key)
            row[key] = "" if value is None else value
    return row


def run_one(args, run, index, total, base_cfg, exp_dir):
    run_dir = exp_dir / run["run_tag"]
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.json"
    log_path = run_dir / "stdout.log"

    # --resume idempotente: so pula quem terminou com ok. Qualquer outro status
    # (oom, timeout, crash) e reexecutado.
    if args.resume and metrics_path.exists():
        try:
            existing = json.loads(metrics_path.read_text())
            if existing.get("status") == "ok":
                print(f"[{index}/{total}] {run['run_tag']}: ok anterior, pulando (--resume)", flush=True)
                return row_from_metrics(run, existing, _mlp_from_log(log_path)), True
        except json.JSONDecodeError:
            pass  # JSON corrompido: refaz

    network_path = run_dir / "network.json"
    write_network_json(run, base_cfg, network_path)

    scene_dir = Path(args.data_root) / SCENES[run["scene"]]
    fator = DOWNSAMPLE[run["scene"]]
    batch_size = run["B"]

    cmd = [
        sys.executable, str(WORKER),
        # JSON de treino explicito, nunca o diretorio: passar a pasta faria o
        # loader varrer tudo e treinar sobre o conjunto de teste. O sufixo
        # _f<N> carrega a resolucao calibrada na Etapa 1.
        "--scene", str(scene_dir / f"transforms_f{fator}_train.json"),
        "--test-transforms", str(scene_dir / f"transforms_f{fator}_test.json"),
        "--dataset", run["scene"],
        "--downsample-factor", str(fator),
        "--network", str(network_path),
        "--out-dir", str(run_dir),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(batch_size),
        "--seed", str(run["seed"]),
        "--test-stride", str(args.baseline_test_stride if run["is_baseline"] else args.test_stride),
        "--spp", str(args.spp),
        "--lpips-device", args.lpips_device,
        "--loss-window", str(args.loss_window),
        "--ngp-root", str(args.ngp_root),
    ]
    if args.keep_renders:
        cmd.append("--keep-renders")
    cmd.append("--nerf-compatibility" if args.nerf_compatibility else "--no-nerf-compatibility")

    label = f"[{index}/{total}] {run['run_tag']}"
    print(f"{label}: treinando ({args.n_steps} passos, B={batch_size})...", flush=True)
    started = time.time()

    # Popen em vez de subprocess.run(timeout=...): run() mata com SIGKILL, que o
    # worker nao consegue interceptar, e o metrics.json do timeout nunca e
    # escrito. Aqui manda-se SIGTERM primeiro (o worker o traduz em
    # status="timeout" e grava VRAM e tempos) e so depois, se ele nao sair,
    # SIGKILL.
    timed_out = False
    with log_path.open("w") as log:
        # cwd na raiz do instant-ngp: o proprio ngp resolve alguns recursos
        # (PTX do OptiX, shaders) em relacao a ela. Todos os caminhos do worker
        # sao absolutos, entao o cwd nao afeta mais nada.
        proc = subprocess.Popen(cmd, cwd=args.ngp_root, stdout=log, stderr=subprocess.STDOUT)
        try:
            returncode = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.terminate()
            try:
                returncode = proc.wait(timeout=args.term_grace)
            except subprocess.TimeoutExpired:
                proc.kill()
                returncode = proc.wait()

    elapsed = time.time() - started

    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text())
        except json.JSONDecodeError as exc:
            metrics = {"status": "crash", "error": f"metrics.json ilegivel: {exc}"}
    else:
        # O worker nao chegou a gravar: SIGKILL, OOM do sistema operacional ou
        # morte do interpretador. Registra e segue.
        metrics = {
            "status": "timeout" if timed_out else "crash",
            "error": f"metrics.json ausente (returncode={returncode}); ver {log_path.name}",
        }
    if timed_out and metrics.get("status") not in ("ok",):
        metrics["status"] = "timeout"

    mlp_impl = _mlp_from_log(log_path)
    row = row_from_metrics(run, metrics, mlp_impl)

    status = row["status"]
    if status == "ok":
        print(f"    ok  PSNR={row['psnr']}  SSIM={row['ssim']}  LPIPS={row['lpips']}  "
              f"VRAM={row['vram_peak_mb']}MB  ({elapsed:.0f}s)", flush=True)
    else:
        print(f"    {status.upper()}  {row['error'][:120]}  ({elapsed:.0f}s)", flush=True)
    return row, False


def _mlp_from_log(log_path):
    """Registra qual implementacao de MLP o tiny-cuda-nn escolheu (spec 4.1).

    Se F=8 fizer o FullyFusedMLP cair para CutlassMLP, o tempo de treino muda de
    patamar e a comparacao entre valores de F fica contaminada.
    """
    if not log_path.exists():
        return None
    try:
        text = log_path.read_text(errors="ignore")
    except OSError:
        return None
    match = MLP_RE.search(text)
    return match.group(1) if match else None


def print_summary(rows):
    print("\n" + "=" * 72)
    by_status = {}
    for r in rows:
        by_status.setdefault(r["status"], []).append(r)
    print("Contagem por status:")
    for status, items in sorted(by_status.items()):
        print(f"  {status:16s} {len(items)}")

    ok = [r for r in rows if r["status"] == "ok" and r["psnr"] != ""]
    if not ok:
        print("\nNenhuma run ok.")
        return

    print("\nTop 5 por PSNR:")
    for r in sorted(ok, key=lambda r: float(r["psnr"]), reverse=True)[:5]:
        print(f"  {float(r['psnr']):6.2f} dB  {r['run_tag']:34s} VRAM={r['vram_peak_mb']} MB")

    with_vram = [r for r in ok if r["vram_peak_mb"] not in ("", None)]
    if with_vram:
        low = min(with_vram, key=lambda r: float(r["vram_peak_mb"]))
        print(f"\nMenor VRAM: {low['run_tag']}  {low['vram_peak_mb']} MB  "
              f"PSNR={low['psnr']} dB")

    impls = {r["mlp_impl"] for r in ok if r["mlp_impl"]}
    if len(impls) > 1:
        print(f"\nATENCAO: implementacoes de MLP diferentes entre runs: {impls}")
        print("  Os tempos de treino nao sao comparaveis entre elas (spec 4.1).")


def main():
    ap = argparse.ArgumentParser(description="Grid search do Instant-NGP para a Fronteira de Pareto")
    ap.add_argument("--exp-id", default="exp01")
    ap.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    ap.add_argument("--ngp-root", default=str(DEFAULT_NGP_ROOT),
                    help="raiz do fork do instant-ngp (contem build/ e configs/)")
    ap.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT),
                    help="diretorio com uma pasta por cena (padrao: data/mip_nerf)")
    ap.add_argument("--permitir-nao-calibrada", action="store_true",
                    help="roda cenas que ainda nao passaram pela Etapa 1 e pela "
                         "validacao de aabb_scale; use so deliberadamente")
    ap.add_argument("--base-config", default=None,
                    help="padrao: <ngp-root>/configs/nerf/base.json")
    ap.add_argument("--scenes", nargs="+", default=list(SCENES), choices=list(SCENES))
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--test-stride", type=int, default=4, help="1 a cada N vistas de teste no grid")
    ap.add_argument("--baseline-test-stride", type=int, default=1, help="baseline avalia todas as vistas")
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--lpips-device", default="cpu", choices=["cpu", "cuda", "none"])
    ap.add_argument("--loss-window", type=int, default=800,
                    help="janela final, em passos, para a media do loss_final")
    ap.add_argument("--batch-sweep", action="store_true", default=True,
                    help="inclui as 3 runs extras variando training_batch_size")
    ap.add_argument("--no-batch-sweep", dest="batch_sweep", action="store_false")
    # 20 min nao bastam para B=262144, que levou ~29 min nesta maquina.
    ap.add_argument("--timeout", type=int, default=3600, help="timeout por run, em segundos")
    ap.add_argument("--term-grace", type=int, default=90,
                    help="segundos entre SIGTERM e SIGKILL, para o worker gravar o metrics.json")
    ap.add_argument("--keep-renders", action="store_true", default=True)
    ap.add_argument("--no-keep-renders", dest="keep_renders", action="store_false")
    # PADRAO DESLIGADO desde a migracao para cena real (exp02). Ver a nota em
    # ngp_worker.py e SPEC-exp02-cena-real.md secao 2.4. As 56 runs do exp01
    # rodaram com a flag LIGADA; por isso os PSNR dos dois experimentos nao sao
    # comparaveis, e por isso a flag e gravada por linha no CSV.
    ap.add_argument("--nerf-compatibility", action="store_true", default=False,
                    help="protocolo do NeRF original; DESLIGADO por padrao no exp02")
    ap.add_argument("--no-nerf-compatibility", dest="nerf_compatibility", action="store_false")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-warmup", action="store_true", help="pula a run de aquecimento")
    ap.add_argument("--limit", type=int, default=0, help="executa apenas as N primeiras runs (teste de fumaca)")
    ap.add_argument("--only", nargs="+", default=None, metavar="SUBSTRING",
                    help="executa apenas runs cujo run_tag contenha uma destas substrings")
    # Constantes de calibracao usadas apenas pela estimativa do --dry-run.
    # steps/s vem da tabela STEPS_PER_S_BY_B; estes dois sao medidos direto.
    ap.add_argument("--eval-s-per-view", type=float, default=1.3)
    ap.add_argument("--setup-s", type=float, default=15.0)
    args = ap.parse_args()

    args.ngp_root = str(Path(args.ngp_root).resolve())
    args.data_root = str(Path(args.data_root).resolve())
    args.out_root = str(Path(args.out_root).resolve())

    if not (Path(args.ngp_root) / "configs" / "nerf" / "base.json").exists():
        raise SystemExit(
            f"nao parece a raiz do instant-ngp: {args.ngp_root}\n"
            f"Esperado <ngp-root>/configs/nerf/base.json. Use --ngp-root."
        )
    if not list(Path(args.ngp_root).glob("build*/**/pyngp*.so")):
        raise SystemExit(
            f"pyngp nao encontrado em {args.ngp_root}/build.\n"
            f"Compile antes de rodar o grid (ver README, 'Pre-requisitos')."
        )

    args.base_config = args.base_config or str(Path(args.ngp_root) / "configs" / "nerf" / "base.json")
    base_path = Path(args.base_config)
    if not base_path.exists():
        raise SystemExit(f"base-config nao encontrado: {base_path}")
    base_cfg = json.loads(base_path.read_text())
    validate_grid(base_cfg)

    nao_calibradas = [s for s in args.scenes if s not in SCENES_CALIBRADAS]
    if nao_calibradas and not args.permitir_nao_calibrada:
        raise SystemExit(
            f"cena(s) sem calibracao confirmada: {', '.join(nao_calibradas)}.\n"
            "A Etapa 1 (resolucao) e a validacao de aabb_scale precisam estar "
            "feitas antes do grid -- rodar sem isso repete o erro que invalidou "
            "30 000 iteracoes em garden.\n"
            "Se for deliberado, use --permitir-nao-calibrada e registre o motivo."
        )

    for scene in args.scenes:
        scene_dir = Path(args.data_root) / SCENES[scene]
        fator = DOWNSAMPLE[scene]
        for name in (f"transforms_f{fator}_train.json", f"transforms_f{fator}_test.json"):
            if not (scene_dir / name).exists():
                raise SystemExit(
                    f"dataset ausente: {scene_dir / name}\n"
                    f"Gere com: python3 scripts/split_holdout.py "
                    f"--in-json {scene_dir}/transforms_f{fator}.json "
                    f"--holdout-every 8 --out-prefix {scene_dir}/transforms_f{fator}"
                )

    runs = build_runs(args)
    if args.only:
        runs = [r for r in runs if any(s in r["run_tag"] for s in args.only)]
        if not runs:
            raise SystemExit(f"Nenhum run_tag casa com {args.only}")
    if args.limit:
        runs = runs[:args.limit]

    est = estimate(args, runs)
    print(f"{est['n_runs']} runs x {args.n_steps} passos, {est['n_views']} vistas no grid "
          f"e {est['n_views_base']} no baseline")
    print(f"Estimativa: media de {fmt_hms(est['per_run_s'])} por run  ->  TOTAL {fmt_hms(est['total_s'])}")
    print("  memoria de calculo (por run): setup "
          f"{args.setup_s:.0f}s + {args.n_steps} passos / (steps/s do modelo) "
          f"+ vistas x {args.eval_s_per_view:.2f}s")
    for L, sps in sorted(STEPS_PER_S_BY_L.items()):
        t = args.setup_s + args.n_steps / sps + est["n_views"] * args.eval_s_per_view
        print(f"    L={L:2d}: {sps:5.1f} steps/s -> treino {args.n_steps/sps:5.0f}s, "
              f"run completa {fmt_hms(t)}")
    print("  (medido com a GPU OCIOSA; com o Windows usando a GPU cai ~11x)")
    if args.keep_renders:
        print(f"Disco previsto para renders: {est['disk_mb']:.0f} MB")

    if args.dry_run:
        for s in args.scenes:
            aabb = aabb_da_cena(args.data_root, s)
            print(f"\nper_level_scale derivado — {s} "
                  f"(aabb_scale={aabb}, N_min={GRID_N_MIN}, N_max={grid_n_max(aabb)}):")
            for L in GRID["L"]:
                b = per_level_scale(L, aabb)
                print(f"  L={L:2d}  b={b:.4f}  "
                      f"resolucao mais fina = {GRID_N_MIN * b**(L-1):.0f}")

        print("\nOrdem de execucao:")
        for i, r in enumerate(runs, 1):
            if r["is_baseline"]:
                extra = "baseline (base.json intocado)"
            elif r["kind"] == "batch_sweep":
                extra = f"varredura de B: T={r['T']} F={r['F']} L={r['L']} B={r['B']}"
            else:
                extra = f"T={r['T']} F={r['F']} L={r['L']}"
            print(f"  {i:03d} {r['run_tag']:36s} {extra}")
        print(f"\nCaminhos:")
        print(f"  instant-ngp : {args.ngp_root}")
        print(f"  datasets    : {args.data_root}")
        print(f"  resultados  : {Path(args.out_root) / args.exp_id}")
        free = shutil.disk_usage(PROJECT_ROOT).free / 1024**3
        print(f"  livre em disco: {free:.1f} GB")
        return 0

    exp_dir = Path(args.out_root) / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "manifest.json").write_text(
        json.dumps(collect_manifest(args, base_cfg, runs), indent=2, ensure_ascii=False)
    )

    # Run de aquecimento descartada: tira do primeiro treino medido o custo de
    # inicializacao de contexto CUDA, compilacao JIT e clock baixo da GPU.
    if not args.no_warmup:
        print("\nAquecimento (descartado)...", flush=True)
        warm = dict(runs[0])
        warm["run_tag"] = "_warmup"
        warm_args = argparse.Namespace(**vars(args))
        warm_args.n_steps = min(200, args.n_steps)
        warm_args.test_stride = 100
        run_one(warm_args, warm, 0, 0, base_cfg, exp_dir)
        shutil.rmtree(exp_dir / "_warmup", ignore_errors=True)

    csv_path = exp_dir / "results.csv"
    write_header = not csv_path.exists()
    rows = []
    started = time.time()

    try:
        with csv_path.open("a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
                fh.flush()
            for i, run in enumerate(runs, 1):
                row, skipped = run_one(args, run, i, len(runs), base_cfg, exp_dir)
                rows.append(row)
                if not skipped:
                    writer.writerow(row)
                    fh.flush()          # resultado parcial sobrevive a um Ctrl+C
                    os.fsync(fh.fileno())
    except KeyboardInterrupt:
        print("\nInterrompido. O CSV esta integro; retome com --resume.", flush=True)

    print(f"\nTempo total: {fmt_hms(time.time() - started)}")
    print_summary(rows)
    print(f"\nResultados em {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
