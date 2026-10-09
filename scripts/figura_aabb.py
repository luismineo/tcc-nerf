#!/usr/bin/env python3
"""Figura da calibracao de aabb_scale, garden e bonsai lado a lado.

Substitui a figura de aabb_quantitativo.py para o artigo: um eixo por painel
(PSNR, SSIM e VRAM em linhas separadas, em vez de PSNR e SSIM num eixo duplo)
e VRAM como pico descontada a ocupacao previa, a mesma medida do resto do
trabalho. Os dados sao os mesmos CSVs, sem nova execucao.

Entradas: runs/aabb_quantitativo/aabb_quantitativo.csv (garden)
          runs/aabb_quantitativo_bonsai/aabb_quantitativo.csv (bonsai)
Saida:    runs/exp02_final/aabb_calibracao.png/.pdf

    python3 scripts/figura_aabb.py
"""

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pareto_bolhas import (AZUL, GRADE, LARANJA, MUDO, SUPERFICIE, TINTA,
                           TINTA_2, br, estilo)

FONTES = {"garden": "runs/aabb_quantitativo/aabb_quantitativo.csv",
          "bonsai": "runs/aabb_quantitativo_bonsai/aabb_quantitativo.csv"}
ESCOLHIDO = {"garden": 4, "bonsai": 8}
INICIAL = 16
VALORES = [2, 4, 8, 16, 32]


def carregar(cena):
    return [{"aabb": int(r["aabb_scale"]), "psnr": float(r["psnr"]),
             "ssim": float(r["ssim"]), "vram": float(r["vram_peak_mb"])}
            for r in csv.DictReader(open(FONTES[cena])) if r["status"] == "ok"]


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    estilo()
    linhas = [("psnr", "PSNR (dB)", lambda v, _: br(v, 0)),
              ("ssim", "SSIM", lambda v, _: br(v, 2)),
              ("vram", "VRAM, pico − base (MB)",
               lambda v, _: f"{v:,.0f}".replace(",", "."))]
    fig, axs = plt.subplots(3, 2, figsize=(10, 8.4), sharex=True,
                            gridspec_kw={"height_ratios": [1.5, 1, 1]})
    for j, cena in enumerate(["garden", "bonsai"]):
        pts = sorted(carregar(cena), key=lambda p: p["aabb"])
        esc = next(p for p in pts if p["aabb"] == ESCOLHIDO[cena])
        ini = next(p for p in pts if p["aabb"] == INICIAL)
        for i, (m, rot, fmt) in enumerate(linhas):
            ax = axs[i, j]
            ax.grid(True, color=GRADE, lw=0.6)
            ax.set_axisbelow(True)
            for lado in ("top", "right"):
                ax.spines[lado].set_visible(False)
            xs = [math.log2(p["aabb"]) for p in pts]
            ax.plot(xs, [p[m] for p in pts], color=AZUL, lw=2, zorder=2)
            ax.scatter(xs, [p[m] for p in pts], s=40, color=AZUL,
                       edgecolor=SUPERFICIE, lw=1.4, zorder=3)
            ax.scatter([math.log2(esc["aabb"])], [esc[m]], s=70, color=LARANJA,
                       edgecolor=SUPERFICIE, lw=1.4, zorder=4)
            ax.yaxis.set_major_formatter(FuncFormatter(fmt))
            ax.margins(y=0.18)
            if j == 0:
                ax.set_ylabel(rot)
            if i == 0:
                ax.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
                ax.set_title(cena, loc="left", fontsize=11, color=TINTA, weight="bold")
                ax.annotate(f"escolhido: {esc['aabb']} · {br(esc['psnr'])} dB",
                            xy=(math.log2(esc["aabb"]), esc["psnr"]),
                            xytext=(0, 9), textcoords="offset points",
                            fontsize=8.5, color=TINTA, ha="center", va="bottom")
                ax.annotate(f"valor inicial ({INICIAL}):\n"
                            f"{br(ini['psnr'] - esc['psnr'], 1)} dB",
                            xy=(math.log2(INICIAL), ini["psnr"]),
                            xytext=(-10, -2), textcoords="offset points",
                            fontsize=8, color=TINTA_2, ha="right", va="top")
        if cena == "bonsai":
            axs[0, j].annotate("32 não\ntestado", xy=(5, 0.5),
                               xycoords=("data", "axes fraction"), fontsize=7.5,
                               color=MUDO, ha="center", va="center")
    for ax in axs[-1]:
        ax.set_xticks([math.log2(v) for v in VALORES])
        ax.set_xticklabels([str(v) for v in VALORES])
        ax.set_xlabel("aabb_scale (escala logarítmica)")
        ax.set_xlim(0.7, 5.3)

    h = fig.get_figheight()
    fig.suptitle("Calibração do aabb_scale: o melhor valor difere entre as cenas",
                 x=0.07, y=1 - 0.12 / h, ha="left", va="top", fontsize=11.5,
                 color=TINTA)
    fig.text(0.07, 1 - 0.42 / h,
             "Configuração padrão, fator de redução 2, 5000 iterações, média sobre "
             "todas as vistas retidas (24 em garden, 37 em bonsai).",
             ha="left", va="top", fontsize=8.5, color=TINTA_2)
    fig.subplots_adjust(left=0.09, right=0.985, top=1 - 0.95 / h, bottom=0.07,
                        hspace=0.12, wspace=0.2)
    out = Path("runs/exp02_final/aabb_calibracao")
    fig.savefig(out.with_suffix(".png"), dpi=170)
    fig.savefig(out.with_suffix(".pdf"))
    print(f"-> {out}.png/.pdf")


if __name__ == "__main__":
    main()
