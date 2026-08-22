#!/usr/bin/env python3
"""Fecha a escolha de aabb_scale com PSNR/SSIM em vistas retidas.

O aabb_visual_check.py e triagem: separa "colapsou" de "funciona", mas nao
decide entre dois valores proximos -- a diferenca entre eles e menor que o ruido
visual de um treino curto. Este script troca o olho por numero.

Para cada aabb_scale candidato:
  1. deriva um transforms de TREINO e um de TESTE com aquele aabb_scale;
  2. treina do zero pelo ngp_worker.py, com a configuracao PADRAO do
     Instant-NGP (base.json intocado), sem variar T/F/L;
  3. avalia no split retido e registra PSNR, SSIM, VRAM e tempo.

Reaproveitar o ngp_worker garante que o protocolo de avaliacao seja identico ao
do grid -- mesma composicao de fundo, mesmo snap_to_pixel_centers, mesmo
linear_to_srgb, mesmo tratamento de OOM. Metrica medida por caminho diferente do
grid nao seria comparavel com ele.

Saida: aabb_quantitativo.csv e aabb_quantitativo.png em --out-dir.

    python3 scripts/aabb_quantitativo.py \
        --train-json data/mip_nerf/garden/transforms_f2_train.json \
        --test-json  data/mip_nerf/garden/transforms_f2_test.json \
        --values 2 4 8 16 32 --n-steps 5000
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from calib_resolucao import acquire_lock  # noqa: E402

VRAM_TOTAL_MB = 6144

CSV_FIELDS = [
    "aabb_scale", "status", "psnr", "psnr_median", "psnr_std",
    "ssim", "ssim_ngp", "lpips", "loss_final",
    "vram_peak_mb", "vram_peak_device_mb", "vram_livre_mb", "vram_baseline_mb",
    "n_train_images", "n_test_images", "test_views", "image_resolution",
    "n_params", "n_encoding_params", "per_level_scale_derivado",
    "samples_per_ray_mean", "n_rays_effective_mean",
    "steps_per_s", "t_train_s", "t_eval_s", "t_total_s", "error",
]


def variante(base_json, aabb_scale, destino):
    """Copia o transforms trocando so o aabb_scale."""
    d = json.loads(Path(base_json).read_text())
    d["aabb_scale"] = int(aabb_scale)
    Path(destino).write_text(json.dumps(d, indent=2))
    return destino


def b_derivado(aabb_scale, n_levels, base_res=16, desejada=2048.0):
    """b que o Instant-NGP deriva quando o config nao traz per_level_scale.

    testbed.cu:4248 -- b = exp(log(desejada * aabb_scale / base_res)/(L-1)).
    Registrado por linha porque muda com o aabb_scale e afeta a resolucao mais
    fina do hashgrid: nao e constante entre as linhas desta tabela.
    """
    import math
    if n_levels <= 1:
        return 1.0
    return math.exp(math.log(desejada * aabb_scale / base_res) / (n_levels - 1))


def rodar_um(aabb_scale, args, exp_dir):
    train_dir = Path(args.train_json).resolve().parent
    test_dir = Path(args.test_json).resolve().parent
    marca = os.getpid()
    tmp_tr = train_dir / f"_aabbq_{marca}_train_{aabb_scale}.json"
    tmp_te = test_dir / f"_aabbq_{marca}_test_{aabb_scale}.json"
    out_dir = exp_dir / f"aabb{aabb_scale}"
    out_dir.mkdir(parents=True, exist_ok=True)

    linha = {"aabb_scale": aabb_scale}
    t0 = time.perf_counter()
    try:
        variante(args.train_json, aabb_scale, tmp_tr)
        variante(args.test_json, aabb_scale, tmp_te)

        cmd = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "ngp_worker.py"),
            "--scene", str(tmp_tr),
            "--test-transforms", str(tmp_te),
            "--network", args.network,
            "--out-dir", str(out_dir),
            "--n-steps", str(args.n_steps),
            "--batch-size", str(args.batch_size),
            "--seed", str(args.seed),
            "--test-stride", str(args.test_stride),
            "--spp", str(args.spp),
            "--lpips-device", args.lpips_device,
            "--no-nerf-compatibility",
            "--dataset", args.dataset,
            "--downsample-factor", str(args.downsample_factor),
        ]

        print(f"\n--- aabb_scale={aabb_scale} ---", flush=True)
        log_path = out_dir / "worker.log"
        with log_path.open("w") as log:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                    stdout=log, stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    finally:
        tmp_tr.unlink(missing_ok=True)
        tmp_te.unlink(missing_ok=True)

    linha["t_total_s"] = round(time.perf_counter() - t0, 1)
    mp = out_dir / "metrics.json"
    if not mp.exists():
        linha.update({"status": "sem_metrics",
                      "error": "worker nao gravou metrics.json"})
        return linha

    m = json.loads(mp.read_text())
    for k in CSV_FIELDS:
        if k in m:
            linha[k] = m[k]
    pdev = m.get("vram_peak_device_mb")
    linha["vram_livre_mb"] = None if pdev is None else round(VRAM_TOTAL_MB - pdev, 1)
    linha["status"] = m.get("status")
    linha["error"] = "" if m.get("status") == "ok" else str(m.get("error", ""))[:200]

    # n_levels sai do proprio base.json usado na run.
    try:
        cfg = json.loads(Path(args.network).read_text())
        L = int(cfg["encoding"]["n_levels"])
        linha["per_level_scale_derivado"] = round(b_derivado(aabb_scale, L), 6)
    except Exception:
        linha["per_level_scale_derivado"] = None

    print(f"[aabb] {aabb_scale:3}: status={linha['status']} "
          f"PSNR={linha.get('psnr')} SSIM={linha.get('ssim')} "
          f"pico={pdev} MB", flush=True)
    return linha


def plotar(linhas, destino, args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = [l for l in linhas if l.get("status") == "ok" and l.get("psnr") is not None]
    if not ok:
        print("nenhuma linha valida para plotar")
        return
    x = [l["aabb_scale"] for l in ok]
    psnr = [l["psnr"] for l in ok]
    ssim = [l["ssim"] for l in ok]
    vram = [l["vram_peak_device_mb"] for l in ok]

    melhor_psnr = max(ok, key=lambda l: l["psnr"])["aabb_scale"]
    melhor_ssim = max(ok, key=lambda l: l["ssim"])["aabb_scale"]

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(9.5, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [2, 1], "hspace": 0.14})

    ax.plot(x, psnr, marker="o", ms=6, lw=1.8, color="#1f4e79", label="PSNR (teste)")
    ax.set_ylabel("PSNR (dB)", color="#1f4e79")
    ax.grid(alpha=0.3)
    axs = ax.twinx()
    axs.plot(x, ssim, marker="s", ms=5, lw=1.5, ls=":", color="#8e24aa",
             label="SSIM (teste)")
    axs.set_ylabel("SSIM", color="#8e24aa")

    ax.axvline(melhor_psnr, color="#2e7d32", lw=2, alpha=0.7)
    ax.annotate(f"melhor PSNR: aabb={melhor_psnr}", xy=(melhor_psnr, max(psnr)),
                xytext=(8, -14), textcoords="offset points", fontsize=9,
                weight="bold", color="#2e7d32")

    linhas_leg = ax.get_lines()[:1] + axs.get_lines()
    ax.legend(linhas_leg, [l.get_label() for l in linhas_leg],
              loc="lower center", fontsize=9)
    ax.set_title(
        f"aabb_scale — {args.rotulo}\n{args.n_steps} iteracoes, configuracao padrao, "
        f"split retido, spp={args.spp}", fontsize=11)

    ax2.plot(x, vram, marker="D", ms=5, lw=1.5, color="#c00000",
             label="pico de VRAM (dispositivo)")
    ax2.axhline(VRAM_TOTAL_MB, color="black", ls="--", lw=1.2)
    ax2.annotate(f"{VRAM_TOTAL_MB} MB (RTX 2060)", xy=(x[0], VRAM_TOTAL_MB),
                 xytext=(4, -14), textcoords="offset points", fontsize=8)
    ax2.set_ylabel("VRAM (MB)")
    ax2.set_xlabel("aabb_scale")
    ax2.set_xscale("log", base=2)
    ax2.set_xticks(x)
    ax2.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax2.grid(alpha=0.3)
    ax2.legend(loc="upper left", fontsize=9)

    fig.subplots_adjust(left=0.10, right=0.90, top=0.88, bottom=0.09)
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return melhor_psnr, melhor_ssim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--test-json", required=True)
    ap.add_argument("--values", nargs="+", type=int, default=[2, 4, 8, 16, 32])
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--test-stride", type=int, default=1,
                    help="1 por padrao: o split retido ja e pequeno (24 vistas)")
    ap.add_argument("--lpips-device", default="none", choices=["cpu", "cuda", "none"])
    ap.add_argument("--network", default=None,
                    help="padrao: base.json intocado (configuracao padrao do ngp)")
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--exp-id", default="aabb_quantitativo")
    ap.add_argument("--dataset", default="garden")
    ap.add_argument("--downsample-factor", type=int, default=2)
    ap.add_argument("--rotulo", default="garden f2 (2594x1681)")
    args = ap.parse_args()

    args.network = args.network or str(
        PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json")

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    print(f"rede: {args.network} (configuracao padrao, T/F/L intocados)")
    print(f"valores: {args.values} | {args.n_steps} passos | spp={args.spp} "
          f"| stride={args.test_stride}")

    linhas = [rodar_um(v, args, exp_dir) for v in args.values]

    csv_path = exp_dir / "aabb_quantitativo.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for l in linhas:
            w.writerow(l)

    png_path = exp_dir / "aabb_quantitativo.png"
    melhores = plotar(linhas, png_path, args)

    def f(v, nd=4):
        return "-" if v is None or v == "" else (
            f"{v:.{nd}f}" if isinstance(v, float) else str(v))

    print("\n" + "=" * 88)
    print(f"AABB_SCALE — {args.rotulo} — {args.n_steps} iteracoes, split retido")
    print("=" * 88)
    print(f"{'aabb':>5} {'status':>8} {'PSNR':>9} {'SSIM':>9} {'pico MB':>9} "
          f"{'livre':>8} {'b derivado':>11} {'amostras/raio':>14}")
    print("-" * 88)
    for l in linhas:
        print(f"{l['aabb_scale']:>5} {str(l.get('status')):>8} "
              f"{f(l.get('psnr')):>9} {f(l.get('ssim'), 5):>9} "
              f"{f(l.get('vram_peak_device_mb'), 1):>9} "
              f"{f(l.get('vram_livre_mb'), 1):>8} "
              f"{f(l.get('per_level_scale_derivado')):>11} "
              f"{f(l.get('samples_per_ray_mean'), 2):>14}")
    print("-" * 88)
    if melhores:
        print(f"melhor PSNR: aabb_scale={melhores[0]} | "
              f"melhor SSIM: aabb_scale={melhores[1]}")
    print(f"\ncsv     -> {csv_path}")
    print(f"grafico -> {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
