#!/usr/bin/env python3
"""Caracteriza o ruido entre execucoes identicas do Instant-NGP.

O baseline do exp02 foi executado duas vezes, com a mesma configuracao e a mesma
seed, e diferiu 0,245 dB em garden. Isso e da mesma ordem de grandeza de
diferencas usadas para ordenar a Fronteira de Pareto -- entao, antes de
interpretar qualquer diferenca pequena de PSNR, e preciso saber quanto do valor
e sinal e quanto e ruido.

O nao-determinismo aqui NAO vem da seed: vem de operacoes atomicas em CUDA, cuja
ordem de reducao varia entre execucoes. Por isso todas as repeticoes usam a
MESMA seed -- o objetivo e medir o residual sob controle maximo, nao amostrar
seeds.

Execucoes estritamente sequenciais. Duas simultaneas invalidam a medida de VRAM,
porque cada processo leria como linha de base o que a outra ja alocou.

    python3 scripts/variancia.py --scenes garden bonsai --repeticoes 3
"""

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import grid_runner as gr  # noqa: E402
from calib_resolucao import acquire_lock  # noqa: E402
from ngp_worker import VramSampler  # noqa: E402

VRAM_TOTAL_MB = 6144

# (rotulo, T, F, L). T=None -> base.json intocado.
#
# Duas configuracoes "padrao" de proposito: o base.json e o que o exp02 usou
# como baseline e onde a discrepancia de 0,245 dB apareceu; T19/F2/L16 e o
# padrao declarado no artigo do Instant-NGP. Sao pontos diferentes do grid e a
# distincao precisa ficar visivel, nao resolvida por escolha silenciosa.
CONFIGS = {
    "garden": [
        ("base_json", None, None, None),
        ("padrao_artigo", 19, 2, 16),
        ("candidata", 15, 8, 4),
        ("vizinha", 19, 4, 4),
    ],
    "bonsai": [
        ("base_json", None, None, None),
        ("padrao_artigo", 19, 2, 16),
        ("candidata", 19, 2, 8),
        ("vizinha", 17, 4, 8),
    ],
}

CSV_FIELDS = [
    "scene", "config", "rep", "T", "F", "L", "per_level_scale", "seed",
    "status", "psnr", "psnr_median", "psnr_std", "ssim", "ssim_ngp", "lpips",
    "vram_peak_mb", "vram_baseline_mb", "vram_peak_device_mb", "vram_livre_mb",
    "baseline_amostras_media", "baseline_amostras_desvio", "baseline_alta",
    "n_params", "n_encoding_params", "n_train_images", "n_test_images",
    "image_resolution", "aabb_scale", "downsample_factor", "test_split_rule",
    "n_steps", "batch_size", "nerf_compatibility",
    "steps_per_s", "t_train_s", "t_eval_s", "t_total_s",
    "timestamp", "error",
]


def amostrar_baseline(n=5, intervalo=1.5):
    """Varias leituras: a ocupacao do Windows oscila dezenas de MB sozinha."""
    vals = []
    for i in range(n):
        s = VramSampler()
        v = s.measure_baseline()
        if v is not None:
            vals.append(float(v))
        if i < n - 1:
            time.sleep(intervalo)
    if not vals:
        return None, None
    media = statistics.fmean(vals)
    desvio = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    return round(media, 1), round(desvio, 1)


def esperar_baseline(limite, tentativas, espera):
    """Aguarda e reavalia em vez de iniciar em silencio sob base contaminada."""
    for t in range(1, tentativas + 1):
        media, desvio = amostrar_baseline()
        if media is None:
            return None, None, False
        if media <= limite:
            return media, desvio, False
        print(f"  [base] {media:.0f} MB (desvio {desvio:.0f}) acima do limite "
              f"{limite:.0f} MB — tentativa {t}/{tentativas}, aguardando {espera}s",
              flush=True)
        if t < tentativas:
            time.sleep(espera)
    # Nao aborta a serie inteira: registra e marca. Descartar 24 execucoes por
    # causa do ambiente seria pior que reportar o ambiente junto com o dado.
    print(f"  [base] prosseguindo com base ALTA ({media:.0f} MB) — marcado no CSV",
          flush=True)
    return media, desvio, True


def rede(scene, rotulo, T, F, L, aabb, exp_dir):
    base_cfg = json.loads(
        (PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json").read_text())
    path = exp_dir / f"network_{scene}_{rotulo}.json"
    if T is None:
        path.write_text(json.dumps(base_cfg, indent=2))
        # O ngp deriva per_level_scale do aabb_scale quando ausente; o valor
        # registrado aqui e o que ele calculara, para o CSV nao ficar vazio.
        return path, round(gr.per_level_scale(base_cfg["encoding"]["n_levels"], aabb), 6)
    gr.validate_grid(base_cfg)
    gr.write_network_json(
        {"T": T, "F": F, "L": L, "is_baseline": False, "aabb_scale": aabb},
        base_cfg, path)
    return path, round(gr.per_level_scale(L, aabb), 6)


def uma_execucao(scene, rotulo, T, F, L, rep, args, exp_dir):
    sd = PROJECT_ROOT / "data" / "mip_nerf" / scene
    fator = gr.DOWNSAMPLE[scene]
    tr = sd / f"transforms_f{fator}_train.json"
    te = sd / f"transforms_f{fator}_test.json"
    aabb = int(json.loads(tr.read_text())["aabb_scale"])

    net, b = rede(scene, rotulo, T, F, L, aabb, exp_dir)
    out_dir = exp_dir / f"{scene}_{rotulo}_rep{rep}"
    out_dir.mkdir(parents=True, exist_ok=True)

    media, desvio, alta = esperar_baseline(args.base_limite, args.base_tentativas,
                                           args.base_espera)

    linha = {
        "scene": scene, "config": rotulo, "rep": rep, "T": T, "F": F, "L": L,
        "per_level_scale": b, "seed": args.seed, "aabb_scale": aabb,
        "downsample_factor": fator,
        "baseline_amostras_media": media, "baseline_amostras_desvio": desvio,
        "baseline_alta": alta,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "ngp_worker.py"),
        "--scene", str(tr), "--test-transforms", str(te),
        "--network", str(net), "--out-dir", str(out_dir),
        "--n-steps", str(args.n_steps), "--batch-size", str(args.batch_size),
        "--seed", str(args.seed), "--test-stride", str(args.test_stride),
        "--spp", str(args.spp), "--lpips-device", args.lpips_device,
        "--no-nerf-compatibility", "--dataset", scene,
        "--downsample-factor", str(fator),
    ]

    print(f"\n--- {scene} / {rotulo} / rep {rep}  (T={T} F={F} L={L} b={b}) ---",
          flush=True)
    t0 = time.perf_counter()
    with (out_dir / "worker.log").open("w") as log:
        p = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=log,
                             stderr=subprocess.STDOUT)
        try:
            p.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            p.terminate()
            p.wait(timeout=120)
    linha["t_total_s"] = round(time.perf_counter() - t0, 1)

    mp = out_dir / "metrics.json"
    if mp.exists():
        m = json.loads(mp.read_text())
        for k in CSV_FIELDS:
            if k in m and k not in linha:
                linha[k] = m[k]
        pdev = m.get("vram_peak_device_mb")
        linha["vram_livre_mb"] = None if pdev is None else round(VRAM_TOTAL_MB - pdev, 1)
        linha["status"] = m.get("status")
        linha["error"] = "" if m.get("status") == "ok" else str(m.get("error", ""))[:160]
    else:
        linha["status"] = "sem_metrics"
        linha["error"] = "worker nao gravou metrics.json"

    print(f"[var] {scene}/{rotulo}/rep{rep}: status={linha.get('status')} "
          f"PSNR={linha.get('psnr')} VRAM={linha.get('vram_peak_mb')} "
          f"base={linha.get('vram_baseline_mb')}", flush=True)
    return linha


def consolidar(linhas):
    """Media, desvio, min, max e amplitude por (cena, configuracao)."""
    grupos = {}
    for l in linhas:
        if l.get("status") != "ok":
            continue
        grupos.setdefault((l["scene"], l["config"]), []).append(l)

    resumo = []
    for (scene, cfg), ls in sorted(grupos.items()):
        item = {"scene": scene, "config": cfg, "n": len(ls),
                "T": ls[0]["T"], "F": ls[0]["F"], "L": ls[0]["L"]}
        for metrica in ("psnr", "ssim", "lpips", "vram_peak_mb", "t_train_s",
                        "steps_per_s"):
            vals = [float(x[metrica]) for x in ls
                    if x.get(metrica) not in (None, "")]
            if not vals:
                continue
            item[f"{metrica}_media"] = round(statistics.fmean(vals), 5)
            item[f"{metrica}_desvio"] = round(
                statistics.stdev(vals) if len(vals) > 1 else 0.0, 5)
            item[f"{metrica}_min"] = round(min(vals), 5)
            item[f"{metrica}_max"] = round(max(vals), 5)
            item[f"{metrica}_amplitude"] = round(max(vals) - min(vals), 5)
        resumo.append(item)
    return resumo


def comparar(resumo, fator_ruido=1.0):
    """Confronta cada par de configuracoes da mesma cena com o ruido medido.

    Criterio: a diferenca de PSNR entre duas configuracoes so e considerada
    distinguivel se exceder a soma das amplitudes observadas dentro de cada uma.
    Amplitude, e nao desvio-padrao, porque com n=3 o desvio e uma estimativa
    fraca e a amplitude e o que de fato se observou.
    """
    pares = []
    for scene in sorted({r["scene"] for r in resumo}):
        rs = [r for r in resumo if r["scene"] == scene]
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                d = a.get("psnr_media", 0) - b.get("psnr_media", 0)
                ruido = fator_ruido * (a.get("psnr_amplitude", 0) +
                                       b.get("psnr_amplitude", 0))
                pares.append({
                    "scene": scene, "config_a": a["config"], "config_b": b["config"],
                    "psnr_a": a.get("psnr_media"), "psnr_b": b.get("psnr_media"),
                    "delta_psnr": round(d, 4),
                    "ruido_combinado": round(ruido, 4),
                    "distinguivel": abs(d) > ruido,
                    "delta_vram_mb": round(a.get("vram_peak_mb_media", 0) -
                                           b.get("vram_peak_mb_media", 0), 1),
                })
    return pares


def plotar(linhas, resumo, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cenas = sorted({r["scene"] for r in resumo})
    fig, axs = plt.subplots(1, len(cenas), figsize=(7 * len(cenas), 5.6))
    if len(cenas) == 1:
        axs = [axs]

    for ax, scene in zip(axs, cenas):
        rs = [r for r in resumo if r["scene"] == scene]
        rs.sort(key=lambda r: r.get("psnr_media", 0))
        nomes = [r["config"] for r in rs]
        x = range(len(rs))
        medias = [r.get("psnr_media") for r in rs]
        # Barra de erro = amplitude observada (min..max), nao desvio: com n=3
        # e o que se mediu de fato.
        baixo = [r["psnr_media"] - r["psnr_min"] for r in rs]
        alto = [r["psnr_max"] - r["psnr_media"] for r in rs]
        ax.errorbar(x, medias, yerr=[baixo, alto], fmt="o", ms=9, lw=2,
                    capsize=8, color="#1f4e79", ecolor="#c00000")
        for xi, r in zip(x, rs):
            pontos = [float(l["psnr"]) for l in linhas
                      if l["scene"] == scene and l["config"] == r["config"]
                      and l.get("status") == "ok"]
            ax.plot([xi] * len(pontos), pontos, ".", ms=7, alpha=0.55,
                    color="#e07b00")
            ax.annotate(f"amplitude\n{r['psnr_amplitude']:.3f} dB",
                        xy=(xi, r["psnr_max"]), xytext=(0, 10),
                        textcoords="offset points", ha="center", fontsize=8)
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"{n}\nT{r['T']} F{r['F']} L{r['L']}"
                            for n, r in zip(nomes, rs)], fontsize=8)
        ax.set_ylabel("PSNR (dB)")
        ax.set_title(f"{scene} — {rs[0]['n']} repeticoes por configuracao\n"
                     f"mesma seed, mesmos dados, mesmo protocolo", fontsize=11)
        ax.grid(alpha=0.3, axis="y")

    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.16, wspace=0.22)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", nargs="+", default=["garden", "bonsai"])
    ap.add_argument("--repeticoes", type=int, default=3)
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--test-stride", type=int, default=1)
    ap.add_argument("--lpips-device", default="cpu", choices=["cpu", "cuda", "none"])
    ap.add_argument("--base-limite", type=float, default=900.0)
    ap.add_argument("--base-tentativas", type=int, default=3)
    ap.add_argument("--base-espera", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--exp-id", default="exp02_variance")
    args = ap.parse_args()

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    total = sum(len(CONFIGS[s]) for s in args.scenes) * args.repeticoes
    print(f"{total} execucoes: {args.scenes} x "
          f"{len(CONFIGS[args.scenes[0]])} configs x {args.repeticoes} repeticoes")
    print(f"{args.n_steps} passos, seed {args.seed} fixa, spp={args.spp}, "
          f"stride={args.test_stride}, lpips={args.lpips_device}\n")

    linhas = []
    # Ordem: todas as repeticoes de uma configuracao em sequencia. Alternar
    # configuracoes distribuiria melhor uma eventual deriva do ambiente, mas
    # dificulta retomar a serie se ela for interrompida.
    for scene in args.scenes:
        for rotulo, T, F, L in CONFIGS[scene]:
            for rep in range(1, args.repeticoes + 1):
                linhas.append(uma_execucao(scene, rotulo, T, F, L, rep, args, exp_dir))
                # Grava a cada execucao: uma serie de 2h nao pode perder tudo
                # se algo interromper no meio.
                with (exp_dir / "variancia_bruto.csv").open("w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
                    w.writeheader()
                    for l in linhas:
                        w.writerow(l)

    resumo = consolidar(linhas)
    pares = comparar(resumo)

    if resumo:
        campos = sorted({k for r in resumo for k in r})
        ordem = ["scene", "config", "n", "T", "F", "L"]
        campos = ordem + [c for c in campos if c not in ordem]
        with (exp_dir / "variancia_resumo.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for r in resumo:
                w.writerow(r)
    if pares:
        with (exp_dir / "variancia_comparacoes.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(pares[0]))
            w.writeheader()
            for r in pares:
                w.writerow(r)

    png = exp_dir / "variancia.png"
    if resumo:
        plotar(linhas, resumo, png)

    print("\n" + "=" * 96)
    print("VARIANCIA ENTRE EXECUCOES IDENTICAS")
    print("=" * 96)
    print(f"{'cena':>8} {'config':>15} {'n':>3} {'PSNR medio':>11} {'desvio':>8} "
          f"{'amplitude':>10} {'VRAM media':>11} {'ampl. VRAM':>11}")
    print("-" * 96)
    for r in resumo:
        print(f"{r['scene']:>8} {r['config']:>15} {r['n']:>3} "
              f"{r.get('psnr_media', 0):>11.4f} {r.get('psnr_desvio', 0):>8.4f} "
              f"{r.get('psnr_amplitude', 0):>10.4f} "
              f"{r.get('vram_peak_mb_media', 0):>11.1f} "
              f"{r.get('vram_peak_mb_amplitude', 0):>11.1f}")
    print("-" * 96)
    print("\nPARES NAO DISTINGUIVEIS (|delta PSNR| <= ruido combinado):")
    algum = False
    for p in pares:
        if not p["distinguivel"]:
            algum = True
            print(f"  {p['scene']:>8}: {p['config_a']} vs {p['config_b']}  "
                  f"delta={p['delta_psnr']:+.4f} dB  ruido={p['ruido_combinado']:.4f} dB  "
                  f"(delta VRAM {p['delta_vram_mb']:+.1f} MB)")
    if not algum:
        print("  (nenhum — todas as diferencas excedem o ruido medido)")
    print(f"\nbruto      -> {exp_dir}/variancia_bruto.csv")
    print(f"resumo     -> {exp_dir}/variancia_resumo.csv")
    print(f"comparacoes-> {exp_dir}/variancia_comparacoes.csv")
    print(f"grafico    -> {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
