#!/usr/bin/env python3
"""Efeito de cada hiperparametro, cena limitada (exp01) contra nao-limitada (exp02).

Responde a comparacao prometida na Secao 3.5 do artigo: a magnitude do efeito
de T, F e L sobre PSNR e VRAM muda entre os dois regimes de cena?

Efeito de um hiperparametro H = media, sobre as 9 combinacoes dos outros dois,
de [metrica(H no maximo) - metrica(H no minimo)]: T 15->19, F 2->8, L 4->16.
A amplitude (min e max entre as 9 combinacoes) mostra o quanto o efeito depende
dos outros dois -- interacao.

Fontes:
  exp01: runs/exp01/results.csv (lego, chair; n=1 por configuracao)
  exp02: runs/exp02_final/grid_{cena}.csv (garden, bonsai; media de todas as
         medicoes a 5000 iteracoes, como nas tabelas finais)

PSNR absoluto nao e comparavel entre os experimentos (protocolo, divisao de
dados e cenas diferem); diferencas dentro de cada cena sao. VRAM tambem e dada
em % do baseline da propria cena, porque os pisos diferem.

Saidas: runs/exp02_final/efeito_hiperparametros.csv e .png/.pdf

    python3 scripts/efeito_hiperparametros.py
"""

import csv
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pareto_bolhas import (EIXO, GRADE, MUDO, RUIDO_PSNR, SUPERFICIE, TINTA,
                           TINTA_2, br, estilo)

# ordem fixa das series (paleta categorica de referencia, slots 1-4, validada)
CENAS = [("lego", "exp01"), ("chair", "exp01"), ("garden", "exp02"), ("bonsai", "exp02")]
CORES = {"lego": "#2a78d6", "chair": "#eb6834", "garden": "#1baf7a", "bonsai": "#eda100"}
EXTREMOS = {"T": ("15", "19"), "F": ("2", "8"), "L": ("4", "16")}
OUTROS = {"T": ("F", "L"), "F": ("T", "L"), "L": ("T", "F")}


def carregar():
    """{cena: {(T, F, L): {psnr, vram, t}}} e {cena: vram do baseline}."""
    dados, base = {}, {}
    for r in csv.DictReader(open("runs/exp01/results.csv")):
        if r["kind"] == "grid":
            dados.setdefault(r["scene"], {})[(r["T"], r["F"], r["L"])] = {
                "psnr": float(r["psnr"]), "vram": float(r["vram_peak_mb"]),
                "t": float(r["t_train_s"])}
        elif r["kind"] == "baseline":
            base[r["scene"]] = float(r["vram_peak_mb"])
    for cena in ("garden", "bonsai"):
        for r in csv.DictReader(open(f"runs/exp02_final/grid_{cena}.csv")):
            dados.setdefault(cena, {})[(r["T"], r["F"], r["L"])] = {
                "psnr": float(r["psnr"]), "vram": float(r["vram"]),
                "t": float(r["t_train"])}
        base[cena] = dados[cena][("19", "4", "8")]["vram"]
    return dados, base


def efeitos(dados, base):
    linhas = []
    eixos = {"T": 0, "F": 1, "L": 2}
    for cena, exp in CENAS:
        g = dados[cena]
        for h, (lo, hi) in EXTREMOS.items():
            difs = {"psnr": [], "vram": [], "t": []}
            for cfg_lo, v_lo in g.items():
                if cfg_lo[eixos[h]] != lo:
                    continue
                cfg_hi = list(cfg_lo)
                cfg_hi[eixos[h]] = hi
                v_hi = g[tuple(cfg_hi)]
                for m in difs:
                    difs[m].append(v_hi[m] - v_lo[m])
            assert len(difs["psnr"]) == 9, (cena, h)
            linhas.append({
                "experimento": exp, "cena": cena, "hiperparametro": h,
                "de": lo, "para": hi, "n_pares": 9,
                "d_psnr_db": round(mean(difs["psnr"]), 3),
                "d_psnr_min": round(min(difs["psnr"]), 3),
                "d_psnr_max": round(max(difs["psnr"]), 3),
                "d_vram_mb": round(mean(difs["vram"]), 1),
                "d_vram_min": round(min(difs["vram"]), 1),
                "d_vram_max": round(max(difs["vram"]), 1),
                "d_vram_pct_baseline": round(100 * mean(difs["vram"]) / base[cena], 1),
                "vram_baseline_mb": round(base[cena], 1),
                "d_t_train_s": round(mean(difs["t"]), 1),
            })
    return linhas


def grafico(linhas, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    estilo()
    fig, axs = plt.subplots(1, 2, figsize=(11, 5.8))
    hs = list(EXTREMOS)
    larg = 0.19
    paineis = [
        ("d_psnr_db", "d_psnr_min", "d_psnr_max", "variação de PSNR (dB)",
         "Qualidade", lambda v, _: br(v, 1)),
        ("d_vram_mb", "d_vram_min", "d_vram_max", "variação do pico de VRAM (MB)",
         "Memória", lambda v, _: f"{v:,.0f}".replace(",", ".").replace("-", "−")),
    ]
    for ax, (col, cmin, cmax, rot, tit, fmt) in zip(axs, paineis):
        ax.grid(True, axis="y", color=GRADE, lw=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.axhline(0, color=EIXO, lw=1)
        if col == "d_psnr_db":
            ax.axhspan(-RUIDO_PSNR, RUIDO_PSNR, color=GRADE, alpha=0.7, lw=0, zorder=0)
            ax.text(2.47, -RUIDO_PSNR - 0.06, "faixa cinza: ruído medido (±0,244 dB, exp02)",
                    ha="right", va="top", fontsize=7.5, color=MUDO)
        for i, (cena, _) in enumerate(CENAS):
            sel = {r["hiperparametro"]: r for r in linhas if r["cena"] == cena}
            xs = [k + (i - 1.5) * larg for k in range(len(hs))]
            ys = [sel[h][col] for h in hs]
            ax.bar(xs, ys, width=larg - 0.03, color=CORES[cena], label=cena,
                   edgecolor=SUPERFICIE, lw=0, zorder=2)
            # amplitude entre as 9 combinacoes dos outros dois hiperparametros
            ax.vlines(xs, [sel[h][cmin] for h in hs], [sel[h][cmax] for h in hs],
                      color=TINTA_2, lw=0.9, zorder=3)
        ax.set_xticks(range(len(hs)))
        ax.set_xticklabels([f"{h}: {EXTREMOS[h][0]} → {EXTREMOS[h][1]}" for h in hs],
                           color=TINTA_2)
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        ax.set_ylabel(rot)
        ax.set_title(tit, loc="left", fontsize=11, color=TINTA, weight="bold")

    h = fig.get_figheight()
    fig.suptitle("Efeito de levar cada hiperparâmetro do menor ao maior valor, "
                 "cena limitada (exp01) × não-limitada (exp02)",
                 x=0.06, y=1 - 0.12 / h, ha="left", va="top", fontsize=11.5,
                 color=TINTA)
    fig.text(0.06, 1 - 0.42 / h,
             "Barra: média sobre as 9 combinações dos outros dois hiperparâmetros. "
             "Traço: menor e maior efeito entre essas 9 combinações.\n"
             "lego e chair: exp01, n = 1 por configuração. garden e bonsai: exp02, "
             "média de todas as medições a 5000 iterações.",
             ha="left", va="top", fontsize=8.5, color=TINTA_2, linespacing=1.5)
    alcas, nomes = axs[0].get_legend_handles_labels()
    fig.legend(alcas, nomes, loc="upper left", bbox_to_anchor=(0.055, 1 - 0.88 / h),
               frameon=False, fontsize=8.5, ncol=4, labelcolor=TINTA_2,
               handlelength=1.2, columnspacing=1.4)
    fig.subplots_adjust(left=0.07, right=0.985, top=1 - 1.6 / h, bottom=0.1,
                        wspace=0.22)
    fig.savefig(out.with_suffix(".png"), dpi=170)
    fig.savefig(out.with_suffix(".pdf"))


def main():
    dados, base = carregar()
    linhas = efeitos(dados, base)
    out = Path("runs/exp02_final/efeito_hiperparametros")
    with out.with_suffix(".csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    grafico(linhas, out)
    for r in linhas:
        print(f"{r['cena']:7s} {r['hiperparametro']} {r['de']:>2}->{r['para']:<2} "
              f"dPSNR {r['d_psnr_db']:+6.2f} [{r['d_psnr_min']:+.2f}, {r['d_psnr_max']:+.2f}]  "
              f"dVRAM {r['d_vram_mb']:+7.1f} MB ({r['d_vram_pct_baseline']:+5.1f} %) "
              f"[{r['d_vram_min']:+.0f}, {r['d_vram_max']:+.0f}]  dt {r['d_t_train_s']:+6.1f} s")
    print(f"-> {out}.csv/.png/.pdf")


if __name__ == "__main__":
    main()
