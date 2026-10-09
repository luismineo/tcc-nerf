#!/usr/bin/env python3
"""Testa se existe um ponto de operacao onde o padrao NAO cabe e o grid cabe.

E a afirmacao mais forte que o SPEC-exp02 secao 1 descreve: "nesta cena e nesta
resolucao, o Instant-NGP em configuracao padrao nao treina numa RTX 2060; com a
configuracao X, treina a Y dB".

No fator 2 isso nao acontece -- as 27 combinacoes cabem. A janela util (distancia
entre a configuracao padrao e a mais leve do grid) mede ~400 MB em garden, e cai
num fator de reducao intermediario, gerado pelo gerar_fator_intermediario.py.

A margem e estreita, entao a linha de base da GPU precisa ser verificada: ela
variou entre 254 e 1457 MB nesta maquina, ou seja, mais que a propria janela. O
script aborta se a base estiver acima de --base-maxima.

    python3 scripts/teste_viabilidade.py \
        --train-json data/mip_nerf/garden/transforms_f1.62_train.json \
        --test-json  data/mip_nerf/garden/transforms_f1.62_test.json
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import grid_runner as gr  # noqa: E402
from ngp_worker import VramSampler  # noqa: E402

VRAM_TOTAL_MB = 6144

# Configuracoes: a padrao (base.json intocado) e os dois extremos uteis do grid.
# A mais leve e a de MENOR VRAM medida no exp02 para garden (T15 F2 L8), nao a
# de menos parametros -- sao diferentes, e o que importa aqui e a memoria.
CONFIGS = [
    ("padrao", None, None, None),
    ("mediana", 17, 4, 8),
    ("leve", 15, 2, 8),
]

CSV_FIELDS = [
    "config", "T", "F", "L", "per_level_scale", "status", "veredito",
    "psnr", "ssim", "lpips", "vram_peak_mb", "vram_peak_device_mb",
    "vram_baseline_mb", "vram_livre_mb", "vram_at_failure_mb",
    "n_params", "n_encoding_params", "n_train_images", "n_test_images",
    "image_resolution", "steps_per_s", "t_train_s", "t_eval_s", "error",
]


def rede(nome, T, F, L, aabb, exp_dir):
    base_cfg = json.loads(
        (PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json").read_text())
    path = exp_dir / f"network_{nome}.json"
    if T is None:
        path.write_text(json.dumps(base_cfg, indent=2))
        return path, None
    gr.validate_grid(base_cfg)
    b = round(gr.per_level_scale(L, aabb), 6)
    gr.write_network_json(
        {"T": T, "F": F, "L": L, "is_baseline": False, "aabb_scale": aabb},
        base_cfg, path)
    return path, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--test-json", required=True)
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--test-stride", type=int, default=1)
    ap.add_argument("--lpips-device", default="none", choices=["cpu", "cuda", "none"])
    ap.add_argument("--exp-id", default="teste_viabilidade")
    ap.add_argument("--dataset", default="garden")
    ap.add_argument("--base-maxima", type=float, default=700.0,
                    help="aborta se a linha de base da GPU estiver acima disso")
    ap.add_argument("--timeout", type=int, default=7200)
    args = ap.parse_args()

    # A margem deste teste e menor que a variacao historica da linha de base.
    # Medir antes e condicao de validade, nao formalidade.
    amostra = VramSampler()
    base = amostra.measure_baseline()
    print(f"linha de base da GPU: {base} MB (limite aceito: {args.base_maxima} MB)")
    if base is not None and base > args.base_maxima:
        sys.exit(
            f"ABORTADO: linha de base em {base:.0f} MB.\n"
            f"A janela util deste teste e de ~400 MB; com a base acima de "
            f"{args.base_maxima:.0f} MB o resultado mede contaminacao, nao capacidade.\n"
            "Feche consumidores de GPU no Windows e repita."
        )

    tr = Path(args.train_json)
    aabb = int(json.loads(tr.read_text())["aabb_scale"])
    w = int(json.loads(tr.read_text())["w"])
    h = int(json.loads(tr.read_text())["h"])
    n = len(json.loads(tr.read_text())["frames"])
    imgs_mb = n * w * h * 4 / 1048576
    print(f"cena {args.dataset} | {w}x{h} | {n} imagens de treino | aabb_scale={aabb}")
    print(f"imagens na VRAM a 4 B/px: {imgs_mb:.0f} MB | disponivel: "
          f"{VRAM_TOTAL_MB - (base or 0):.0f} MB")

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    linhas = []
    for nome, T, F, L in CONFIGS:
        net, b = rede(nome, T, F, L, aabb, exp_dir)
        out_dir = exp_dir / nome
        out_dir.mkdir(exist_ok=True)
        cmd = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "ngp_worker.py"),
            "--scene", str(tr), "--test-transforms", args.test_json,
            "--network", str(net), "--out-dir", str(out_dir),
            "--n-steps", str(args.n_steps), "--batch-size", str(args.batch_size),
            "--seed", "0", "--test-stride", str(args.test_stride),
            "--spp", str(args.spp), "--lpips-device", args.lpips_device,
            "--no-nerf-compatibility", "--dataset", args.dataset,
        ]
        print(f"\n--- {nome} (T={T} F={F} L={L} b={b}) ---", flush=True)
        t0 = time.perf_counter()
        with (out_dir / "worker.log").open("w") as log:
            p = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=log,
                                 stderr=subprocess.STDOUT)
            try:
                p.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(timeout=120)

        linha = {"config": nome, "T": T, "F": F, "L": L, "per_level_scale": b}
        mp = out_dir / "metrics.json"
        if mp.exists():
            m = json.loads(mp.read_text())
            for k in CSV_FIELDS:
                if k in m:
                    linha[k] = m[k]
            pdev = m.get("vram_peak_device_mb")
            linha["vram_livre_mb"] = None if pdev is None else round(VRAM_TOTAL_MB - pdev, 1)
            linha["status"] = m.get("status")
            linha["error"] = "" if m.get("status") == "ok" else str(m.get("error", ""))[:160]
            sps = m.get("steps_per_s")
            pico = m.get("vram_peak_mb")
            if m.get("status") != "ok":
                linha["veredito"] = "NAO CABE"
            elif pico and imgs_mb > pico:
                linha["veredito"] = "degradado"
            else:
                linha["veredito"] = "cabe"
        else:
            linha.update({"status": "sem_metrics", "veredito": "NAO CABE",
                          "error": "worker morreu sem gravar metrics.json"})
        linha.setdefault("t_train_s", round(time.perf_counter() - t0, 1))
        linhas.append(linha)
        print(f"[teste] {nome}: {linha['veredito']} | status={linha.get('status')} "
              f"pico={linha.get('vram_peak_device_mb')} MB "
              f"PSNR={linha.get('psnr')}", flush=True)

    csv_path = exp_dir / "teste_viabilidade.csv"
    with csv_path.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        wr.writeheader()
        for l in linhas:
            wr.writerow(l)

    # --- figura ---------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5.5))
    nomes = [l["config"] for l in linhas]
    picos = [l.get("vram_peak_device_mb") or l.get("vram_at_failure_mb") or VRAM_TOTAL_MB
             for l in linhas]
    cores = ["#c00000" if l["veredito"] == "NAO CABE" else "#2e7d32" for l in linhas]
    barras = ax.bar(nomes, picos, color=cores, alpha=0.85)
    ax.axhline(VRAM_TOTAL_MB, color="black", ls="--", lw=1.6)
    ax.annotate(f"{VRAM_TOTAL_MB} MB (RTX 2060)", xy=(0, VRAM_TOTAL_MB),
                xytext=(4, 5), textcoords="offset points", fontsize=9)
    if base:
        ax.axhline(VRAM_TOTAL_MB - base, color="#e07b00", ls=":", lw=1.6)
        ax.annotate(f"teto util: {VRAM_TOTAL_MB - base:.0f} MB "
                    f"(descontada a base de {base:.0f} MB)",
                    xy=(0, VRAM_TOTAL_MB - base), xytext=(4, -14),
                    textcoords="offset points", fontsize=9, color="#e07b00")
    ax.axhline(imgs_mb, color="#1f4e79", ls="-.", lw=1.4)
    ax.annotate(f"piso: imagens de treino, {imgs_mb:.0f} MB",
                xy=(len(nomes) - 1, imgs_mb), xytext=(-6, 6),
                textcoords="offset points", fontsize=9, color="#1f4e79", ha="right")
    for b_, l in zip(barras, linhas):
        txt = l["veredito"] + (f"\n{l['psnr']:.2f} dB" if l.get("psnr") else "")
        ax.annotate(txt, xy=(b_.get_x() + b_.get_width() / 2, b_.get_height()),
                    xytext=(0, 5), textcoords="offset points", ha="center",
                    fontsize=9, weight="bold")
    ax.set_ylabel("pico de VRAM no dispositivo (MB)")
    ax.set_title(f"Fronteira de viabilidade — {args.dataset} {w}x{h}, "
                 f"aabb_scale={aabb}\n{args.n_steps} iteracoes, split retido "
                 f"({n} treino / {linhas[0].get('n_test_images', '?')} teste)", fontsize=11)
    ax.set_ylim(0, max(VRAM_TOTAL_MB * 1.12, max(picos) * 1.12))
    ax.grid(alpha=0.3, axis="y")
    fig.subplots_adjust(left=0.10, right=0.97, top=0.86, bottom=0.10)
    png = exp_dir / "teste_viabilidade.png"
    fig.savefig(png, dpi=150)
    plt.close(fig)

    print("\n" + "=" * 78)
    print(f"{'config':>9} {'veredito':>10} {'pico dev':>10} {'livre':>8} "
          f"{'base':>8} {'PSNR':>8} {'SSIM':>8}")
    print("-" * 78)
    for l in linhas:
        def g(k, nd=1):
            v = l.get(k)
            return "-" if v in (None, "") else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
        print(f"{l['config']:>9} {l['veredito']:>10} {g('vram_peak_device_mb'):>10} "
              f"{g('vram_livre_mb'):>8} {g('vram_baseline_mb'):>8} "
              f"{g('psnr', 2):>8} {g('ssim', 4):>8}")
    print("-" * 78)
    cabem = [l for l in linhas if l["veredito"] == "cabe"]
    nao = [l for l in linhas if l["veredito"] == "NAO CABE"]
    if any(l["config"] == "padrao" for l in nao) and cabem:
        print("DEMONSTRACAO OBTIDA: a configuracao padrao nao cabe; "
              f"{', '.join(l['config'] for l in cabem)} cabe(m).")
    elif not nao:
        print("Todas couberam: este fator ainda nao pressiona o suficiente.")
    else:
        print("Nenhuma configuracao coube: este fator pressiona demais.")
    print(f"\ncsv     -> {csv_path}")
    print(f"grafico -> {png}")


if __name__ == "__main__":
    main()
