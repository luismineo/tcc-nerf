#!/usr/bin/env python3
"""Etapa 1.5 do exp02: revalidacao do numero de iteracoes em cena nao-limitada.

As 5000 iteracoes do exp01 foram ancoradas na curva de convergencia do Lego --
cena limitada, fundo branco, convergencia rapida. Cena real nao-limitada com
aabb_scale alto converge mais devagar, e reaproveitar aquele numero sem medir
seria extrapolacao. Este script produz a curva equivalente para a cena real.

DESENHO EM DUAS FASES, e o motivo importa:

  Fase 1  treina N passos no split de treino, registrando loss a cada
          --loss-every passos e salvando um snapshot a cada --psnr-every.
  Fase 2  carrega o split de TESTE e avalia cada snapshot.

O PSNR intermediario NAO e medido durante o treino. `load_training_data()`
substitui o dataset e reinicializa o grid de densidade, entao alternar entre
treino e teste a cada 2000 passos contaminaria justamente a curva de
convergencia que este script existe para medir. Snapshots isolam as duas coisas.

    python3 scripts/convergencia.py \
        --train-json data/mip_nerf/garden/transforms_f2_train.json \
        --test-json  data/mip_nerf/garden/transforms_f2_test.json \
        --out-dir runs/etapa15_convergencia/garden_f2 \
        --n-steps 30000
"""

import argparse
import json
import shutil
import statistics
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ngp_worker import VramSampler, _write_png, linear_to_srgb, mse2psnr  # noqa: E402

BACKGROUND_COLOR = [0.0, 0.0, 0.0, 1.0]
RENDER_MIN_TRANSMITTANCE = 1e-4


def carregar_pyngp(ngp_root):
    for so in sorted(Path(ngp_root).glob("build*/**/pyngp*.so")):
        sys.path.insert(0, str(so.parent))
        break
    else:
        raise RuntimeError(f"pyngp*.so nao encontrado em {ngp_root}/build*")
    import pyngp as ngp
    return ngp


# ---------------------------------------------------------------------------
# Fase 1 -- treino com registro de loss e snapshots
# ---------------------------------------------------------------------------
def treinar(ngp, args, snap_dir, sampler):
    testbed = ngp.Testbed()
    testbed.root_dir = str(Path(args.ngp_root).resolve())
    if hasattr(testbed, "seed"):
        testbed.seed = int(args.seed)

    testbed.load_training_data(args.train_json)
    n_train = int(testbed.nerf.training.dataset.n_images)
    testbed.reload_network_from_file(args.network)

    # Cena real: o bloco nerf_compatibility zera o cone_angle_constant e nao se
    # aplica aqui. Ver SPEC-exp02 secao 2.4.
    testbed.training_batch_size = int(args.batch_size)
    testbed.shall_train = True

    loss_hist = []      # [passo, loss, segundos]
    marcos_snap = []    # [passo, caminho do snapshot, segundos]

    t0 = time.perf_counter()
    for passo in range(1, int(args.n_steps) + 1):
        testbed.train(int(args.batch_size))

        # O ngp so recalcula o loss quando training_step % 16 == 0; amostrar em
        # multiplo de 100 pega valores repetidos se 100 nao for multiplo de 16,
        # entao o valor registrado e o mais recente disponivel -- que e o que a
        # curva precisa, e o mesmo criterio do ngp_worker.
        if passo % int(args.loss_every) == 0 or passo == 1:
            loss_hist.append([passo, float(testbed.loss),
                              round(time.perf_counter() - t0, 2)])

        if passo % int(args.psnr_every) == 0:
            caminho = snap_dir / f"step_{passo:06d}.ingp"
            testbed.save_snapshot(str(caminho), False)
            marcos_snap.append([passo, str(caminho),
                                round(time.perf_counter() - t0, 2)])
            print(f"  [treino] passo {passo:6d}  loss={testbed.loss:.6f}  "
                  f"t={time.perf_counter() - t0:7.1f}s", flush=True)

    t_train = time.perf_counter() - t0
    del testbed  # libera a VRAM do dataset de treino antes da fase 2
    return loss_hist, marcos_snap, n_train, t_train


# ---------------------------------------------------------------------------
# Fase 2 -- PSNR de cada snapshot no split de teste
# ---------------------------------------------------------------------------
def avaliar(ngp, args, marcos_snap):
    testbed = ngp.Testbed()
    testbed.root_dir = str(Path(args.ngp_root).resolve())
    testbed.load_training_data(args.test_json)
    n_test = int(testbed.nerf.training.dataset.n_images)

    indices = list(range(0, n_test, max(1, int(args.test_stride))))
    resolucoes = [testbed.nerf.training.dataset.metadata[i].resolution for i in indices]

    def preparar():
        """Reaplicado a cada snapshot: load_snapshot pode reescrever estes campos."""
        testbed.background_color = BACKGROUND_COLOR
        testbed.snap_to_pixel_centers = True
        testbed.nerf.render_min_transmittance = RENDER_MIN_TRANSMITTANCE
        testbed.shall_train = False
        testbed.render_with_lens_distortion = True

    # Ground truth nao depende do snapshot: renderizado uma vez e reaproveitado.
    preparar()
    refs = []
    for k, i in enumerate(indices):
        testbed.set_camera_to_training_view(i)
        testbed.render_ground_truth = True
        ref = testbed.render(resolucoes[k][0], resolucoes[k][1], 1, True)
        refs.append(np.clip(linear_to_srgb(ref[..., :3]), 0.0, 1.0).astype(np.float32))
    testbed.render_ground_truth = False
    print(f"  [aval] {len(indices)} vistas de referencia renderizadas", flush=True)

    from skimage.metrics import structural_similarity

    # Dump de imagens: sem inspecao visual nao da para distinguir "o modelo
    # generalizou mal" de "o render esta degenerado". Salvo no primeiro e no
    # ultimo checkpoint para poder comparar os dois regimes.
    dump_dir = Path(args.out_dir) / "renders"
    if args.dump_renders:
        dump_dir.mkdir(parents=True, exist_ok=True)
        for k in range(min(args.dump_renders, len(indices))):
            _write_png(dump_dir / f"ref_view{indices[k]:03d}.png",
                       (refs[k] * 255.0 + 0.5).astype(np.uint8))

    psnr_hist = []
    for n_snap, (passo, caminho, t_treino) in enumerate(marcos_snap):
        testbed.load_snapshot(caminho)
        preparar()
        testbed.render_ground_truth = False
        por_vista, ssim_vista = [], []
        for k, i in enumerate(indices):
            testbed.set_camera_to_training_view(i)
            img = testbed.render(resolucoes[k][0], resolucoes[k][1], int(args.spp), True)
            A = np.clip(linear_to_srgb(img[..., :3]), 0.0, 1.0).astype(np.float32)
            mse = max(float(np.mean((A - refs[k]) ** 2)), 1e-12)
            por_vista.append(float(mse2psnr(mse)))
            A8 = (A * 255.0 + 0.5).astype(np.uint8)
            R8 = (refs[k] * 255.0 + 0.5).astype(np.uint8)
            # SSIM entra como contraprova: o PSNR premia render borrado, entao
            # uma queda de PSNR com SSIM subindo significaria nitidez mal
            # posicionada, nao piora de fato.
            ssim_vista.append(float(structural_similarity(R8, A8, channel_axis=-1,
                                                          data_range=255)))
            if args.dump_renders and k < args.dump_renders and \
                    n_snap in (0, len(marcos_snap) - 1):
                _write_png(dump_dir / f"step{passo:06d}_view{i:03d}.png", A8)

        psnr = statistics.fmean(por_vista)
        ssim = statistics.fmean(ssim_vista)
        psnr_hist.append([passo, round(psnr, 4), round(statistics.median(por_vista), 4),
                          t_treino, round(ssim, 5)])
        print(f"  [aval] passo {passo:6d}  PSNR={psnr:7.4f} dB  SSIM={ssim:.5f}  "
              f"({len(por_vista)} vistas)", flush=True)

    del testbed
    return psnr_hist, n_test, len(indices)


# ---------------------------------------------------------------------------
# Fase 3 -- analise da curva
# ---------------------------------------------------------------------------
def analisar(loss_hist, psnr_hist, args):
    """Localiza a estabilizacao por ganho marginal, em loss e em PSNR."""
    analise = {}

    # --- criterio em PSNR: dB ganhos por 1000 iteracoes ---
    # Limiar de 0.1 dB/1000 it: abaixo disso a diferenca e imperceptivel e nao
    # justifica o custo de GPU. E o criterio principal por ser interpretavel na
    # mesma unidade do resultado do trabalho.
    ganhos = []
    for a, b in zip(psnr_hist, psnr_hist[1:]):
        p0, v0 = a[0], a[1]
        p1, v1 = b[0], b[1]
        ganhos.append([p1, round((v1 - v0) / (p1 - p0) * 1000.0, 4)])
    analise["ganho_psnr_por_1k"] = ganhos

    joelho_psnr = None
    for passo, g in ganhos:
        if g < args.limiar_psnr:
            joelho_psnr = passo
            break
    analise["joelho_psnr"] = joelho_psnr
    analise["limiar_psnr_db_por_1k"] = args.limiar_psnr

    # --- criterio em loss: fracao da reducao total ja alcancada ---
    if loss_hist:
        l0 = max(v for _, v, _ in loss_hist)
        lf = min(v for _, v, _ in loss_hist)
        span = max(l0 - lf, 1e-12)
        atingido = []
        for passo, v, _ in loss_hist:
            atingido.append([passo, round((l0 - v) / span, 4)])
        analise["fracao_reducao_loss"] = atingido
        alvo = args.limiar_loss
        joelho_loss = next((p for p, f in atingido if f >= alvo), None)
        analise["joelho_loss"] = joelho_loss
        analise["limiar_fracao_loss"] = alvo
        analise["loss_max"] = round(l0, 6)
        analise["loss_min"] = round(lf, 6)

    # --- valores nos marcos pedidos ---
    marcos = {}
    for m in args.marcos:
        l = min((x for x in loss_hist if x[0] <= m), key=lambda x: abs(x[0] - m), default=None)
        p = next((x for x in psnr_hist if x[0] == m), None)
        marcos[str(m)] = {
            "loss": None if l is None else round(l[1], 6),
            "t_s": None if l is None else l[2],
            "psnr": None if p is None else p[1],
        }
    analise["marcos"] = marcos
    return analise


def plotar(loss_hist, psnr_hist, analise, args, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    passos = [x[0] for x in loss_hist]
    losses = [x[1] for x in loss_hist]

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(11, 8.5), sharex=True,
        gridspec_kw={"height_ratios": [2, 1], "hspace": 0.12})

    ax.plot(passos, losses, lw=1.0, color="#1f4e79", label="loss (treino)")
    ax.set_yscale("log")
    ax.set_ylabel("loss (escala log)")
    ax.set_title(f"Convergência — {args.rotulo}\n"
                 f"{args.n_steps} iterações, configuração padrão, "
                 f"B={args.batch_size}, nerf_compatibility desligado", fontsize=11)
    ax.grid(alpha=0.3, which="both")

    cores = ["#c00000", "#e07b00", "#2e7d32", "#6a1b9a"]
    for cor, m in zip(cores, args.marcos):
        dados = analise["marcos"].get(str(m), {})
        if dados.get("loss") is None:
            continue
        ax.axvline(m, color=cor, ls="--", lw=1.1, alpha=0.85)
        ax.annotate(f"{m}\nloss {dados['loss']:.4f}\n{dados['t_s']:.0f}s",
                    xy=(m, dados["loss"]), xytext=(6, 12),
                    textcoords="offset points", fontsize=8, color=cor,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=cor, alpha=0.9))

    joelho = analise.get("joelho_psnr")
    if joelho:
        ax.axvline(joelho, color="black", lw=2.0, alpha=0.75)
        ax.annotate(f"estabilização: {joelho}\n"
                    f"(ganho < {args.limiar_psnr} dB / 1000 it)",
                    xy=(joelho, max(losses)), xytext=(10, -28),
                    textcoords="offset points", fontsize=9, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.35", fc="#fff6cc", ec="black"))
    ax.legend(loc="upper right", fontsize=9)

    if psnr_hist:
        ax2.plot([x[0] for x in psnr_hist], [x[1] for x in psnr_hist],
                 marker="o", ms=3.5, lw=1.3, color="#2e7d32",
                 label="PSNR no conjunto de teste")
        ax2.set_ylabel("PSNR (dB)", color="#2e7d32")
        ax2.grid(alpha=0.3)
        if len(psnr_hist[0]) > 4:
            # SSIM em eixo proprio: se PSNR cai e SSIM sobe, a perda e vies do
            # PSNR contra nitidez, nao piora estrutural.
            axs = ax2.twinx()
            axs.plot([x[0] for x in psnr_hist], [x[4] for x in psnr_hist],
                     marker="s", ms=3.0, lw=1.1, color="#8e24aa", ls=":",
                     label="SSIM no conjunto de teste")
            axs.set_ylabel("SSIM", color="#8e24aa")
            linhas = ax2.get_lines() + axs.get_lines()
            ax2.legend(linhas, [l.get_label() for l in linhas],
                       loc="lower right", fontsize=8)
        else:
            ax2.legend(loc="lower right", fontsize=9)
        for cor, m in zip(cores, args.marcos):
            ax2.axvline(m, color=cor, ls="--", lw=1.1, alpha=0.85)
        if joelho:
            ax2.axvline(joelho, color="black", lw=2.0, alpha=0.75)
    ax2.set_xlabel("iteração")

    # Sem tight_layout: o gridspec com hspace explicito ja define o arranjo, e
    # tight_layout reclama (e reposiciona) quando ha axes com sharex.
    fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=0.08)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--test-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--network",
                    default=str(PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json"),
                    help="padrao: base.json intocado (configuracao padrao do Instant-NGP)")
    ap.add_argument("--ngp-root", default=str(PROJECT_ROOT / "vendor" / "instant-ngp"))
    ap.add_argument("--n-steps", type=int, default=30000)
    ap.add_argument("--loss-every", type=int, default=100)
    ap.add_argument("--psnr-every", type=int, default=2000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spp", type=int, default=1,
                    help="1 no PSNR intermediario: e indicador de convergencia, nao medida final")
    ap.add_argument("--test-stride", type=int, default=1)
    ap.add_argument("--marcos", nargs="+", type=int, default=[5000, 10000, 20000, 30000])
    ap.add_argument("--limiar-psnr", type=float, default=0.1,
                    help="dB por 1000 iteracoes abaixo do qual se considera estabilizado")
    ap.add_argument("--limiar-loss", type=float, default=0.95,
                    help="fracao da reducao total de loss que define o joelho")
    ap.add_argument("--rotulo", default="garden f2 (2594x1681)")
    ap.add_argument("--keep-snapshots", action="store_true")
    ap.add_argument("--dump-renders", type=int, default=0,
                    help="salva PNG das N primeiras vistas de teste no primeiro e no "
                         "ultimo checkpoint, para inspecao visual")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_dir = out_dir / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    sampler = VramSampler()
    baseline = sampler.measure_baseline()
    sampler.start()

    resultado = {
        "train_json": args.train_json, "test_json": args.test_json,
        "network": args.network, "n_steps": args.n_steps,
        "batch_size": args.batch_size, "seed": args.seed,
        "loss_every": args.loss_every, "psnr_every": args.psnr_every,
        "spp_intermediario": args.spp, "nerf_compatibility": False,
        "vram_baseline_mb": baseline,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    try:
        ngp = carregar_pyngp(args.ngp_root)
        print(f"== Fase 1: treino, {args.n_steps} passos ==", flush=True)
        loss_hist, marcos_snap, n_train, t_train = treinar(ngp, args, snap_dir, sampler)
        resultado.update({"n_train_images": n_train, "t_train_s": round(t_train, 2),
                          "steps_per_s": round(args.n_steps / t_train, 2)})

        print(f"\n== Fase 2: PSNR de {len(marcos_snap)} snapshots ==", flush=True)
        psnr_hist, n_test, n_views = avaliar(ngp, args, marcos_snap)
        resultado.update({"n_test_images": n_test, "test_views": n_views})

        resultado["loss_hist"] = loss_hist
        resultado["psnr_hist"] = psnr_hist
        resultado["analise"] = analisar(loss_hist, psnr_hist, args)
        resultado["status"] = "ok"
    except BaseException as exc:
        resultado["status"] = "erro"
        resultado["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        sampler.stop()
        resultado["vram_peak_mb"] = sampler.peak_mb()
        resultado["vram_peak_device_mb"] = (
            round(sampler.peak_device_mb, 1) if sampler.peak_device_mb is not None else None)
        (out_dir / "convergencia.json").write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False))

    # CSVs de dados brutos, para replotar sem reexecutar
    with (out_dir / "loss_curve.csv").open("w") as fh:
        fh.write("step,loss,elapsed_s\n")
        for p, v, t in resultado["loss_hist"]:
            fh.write(f"{p},{v:.8f},{t}\n")
    with (out_dir / "psnr_curve.csv").open("w") as fh:
        fh.write("step,psnr_mean,psnr_median,train_elapsed_s,ssim_mean\n")
        for linha in resultado["psnr_hist"]:
            fh.write(",".join(str(x) for x in linha) + "\n")

    grafico = out_dir / "convergencia.png"
    plotar(resultado["loss_hist"], resultado["psnr_hist"],
           resultado["analise"], args, grafico)

    if not args.keep_snapshots:
        shutil.rmtree(snap_dir, ignore_errors=True)

    a = resultado["analise"]
    print("\n" + "=" * 72)
    print(f"CONVERGENCIA — {args.rotulo}")
    print("=" * 72)
    print(f"  treino............. {resultado['t_train_s']}s "
          f"({resultado['steps_per_s']} passos/s)")
    print(f"  VRAM pico.......... {resultado['vram_peak_device_mb']} MB "
          f"(baseline {baseline})")
    print(f"  imagens............ {resultado['n_train_images']} treino / "
          f"{resultado['n_test_images']} teste")
    print(f"\n  {'marco':>8} {'loss':>12} {'PSNR':>9} {'tempo':>9}")
    for m in args.marcos:
        d = a["marcos"].get(str(m), {})
        print(f"  {m:>8} {str(d.get('loss')):>12} {str(d.get('psnr')):>9} "
              f"{str(d.get('t_s')):>9}")
    print(f"\n  joelho por PSNR.... {a.get('joelho_psnr')} "
          f"(< {a.get('limiar_psnr_db_por_1k')} dB / 1000 it)")
    print(f"  joelho por loss.... {a.get('joelho_loss')} "
          f"({a.get('limiar_fracao_loss')} da reducao total)")
    print(f"\n  grafico -> {grafico}")
    print(f"  dados   -> {out_dir}/loss_curve.csv, psnr_curve.csv, convergencia.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
