#!/usr/bin/env python3
"""Figura didatica: como o joelho da fronteira de Pareto e encontrado.

Os dois eixos sao reescalados para [0, 1] entre o pior e o melhor ponto da
fronteira, para que MB e dB pesem igual. A reta que liga os dois extremos
representa "ganho proporcional ao custo"; a distancia de cada ponto acima dela
mede quanto ele rende mais que isso. O joelho e o ponto de maior distancia. A
caixa em volta dele e o ruido medido (+-0,244 dB, +-122 MB) na mesma escala:
os pontos dentro dela empatam com o joelho (candidatos a sweet spot).

Mesmo criterio de scripts/pareto_bolhas.py, de onde vem a funcao sweet_spot.

    python3 scripts/joelho_explicado.py
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pareto_bolhas import (AZUL, CINZA, LARANJA, MUDO, RUIDO_PSNR, RUIDO_VRAM,
                           SUPERFICIE, TINTA, TINTA_2, GRADE, br, carregar, cfg,
                           estilo, sweet_spot)

# posicao do rotulo do joelho (coordenadas normalizadas), escolhida olhando a
# figura: a area livre acima da fronteira difere entre as cenas
POS_JOELHO = {"garden": (0.17, 1.10), "bonsai": (0.0, 0.95)}


def painel(ax, cena):
    from matplotlib.patches import Rectangle

    fr, joelho, cand, doce = sweet_spot(carregar(cena))
    x0, x1 = fr[0]["vram"], fr[-1]["vram"]
    y0, y1 = fr[0]["psnr"], fr[-1]["psnr"]
    for p in fr:
        p["xn"] = (p["vram"] - x0) / (x1 - x0)
        p["yn"] = (p["psnr"] - y0) / (y1 - y0)

    ax.grid(True, color=GRADE, lw=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    # reta entre os extremos
    ax.plot([0, 1], [0, 1], color=MUDO, lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(0.68, 0.635, "reta entre os extremos\n(ganho proporcional ao custo)",
            rotation=45, rotation_mode="anchor", ha="center", va="top",
            fontsize=8, color=TINTA_2, transform_rotates_text=True)

    # distancias perpendiculares (pe na reta y = x)
    for p in fr:
        pe = (p["xn"] + p["yn"]) / 2
        destaque = p is joelho
        ax.plot([p["xn"], pe], [p["yn"], pe],
                color=LARANJA if destaque else CINZA,
                lw=2 if destaque else 1, zorder=2)

    # caixa de empate: o ruido medido, na escala normalizada
    rx = RUIDO_VRAM / (x1 - x0)
    ry = RUIDO_PSNR / (y1 - y0)
    ax.add_patch(Rectangle((joelho["xn"] - rx, joelho["yn"] - ry), 2 * rx, 2 * ry,
                           fc=LARANJA, alpha=0.12, ec=LARANJA, lw=1, ls="--",
                           zorder=1))

    # fronteira
    ax.plot([p["xn"] for p in fr], [p["yn"] for p in fr], color=AZUL, lw=1.4,
            alpha=0.6, zorder=3)
    normais = [p for p in fr if p not in cand]
    ax.scatter([p["xn"] for p in normais], [p["yn"] for p in normais], s=42,
               color=AZUL, edgecolor=SUPERFICIE, lw=1.2, zorder=4)
    outros = [p for p in cand if p is not joelho]
    ax.scatter([p["xn"] for p in outros], [p["yn"] for p in outros], s=42,
               color=AZUL, edgecolor=LARANJA, lw=1.6, zorder=5)
    ax.scatter([joelho["xn"]], [joelho["yn"]], s=70, color=LARANJA,
               edgecolor=SUPERFICIE, lw=1.2, zorder=6)

    # rotulos: o joelho (na area vazia acima da fronteira) e os dois extremos
    ax.annotate(f"joelho: {cfg(joelho)}\ndistância à reta: {br(joelho['dist_joelho'])}",
                xy=(joelho["xn"], joelho["yn"]), xytext=POS_JOELHO[cena],
                textcoords="data", fontsize=8.5, color=TINTA, va="top",
                arrowprops=dict(arrowstyle="-", color=LARANJA, lw=0.8, shrinkB=5))
    ax.annotate(f"{cfg(fr[0])}\n{br(fr[0]['psnr'])} dB · {br(fr[0]['vram'], 0)} MB",
                xy=(0, 0), xytext=(10, -2), textcoords="offset points",
                fontsize=8, color=TINTA_2, va="top")
    ax.annotate(f"{cfg(fr[-1])}\n{br(fr[-1]['psnr'])} dB · {br(fr[-1]['vram'], 0)} MB",
                xy=(1, 1), xytext=(-8, -12), textcoords="offset points",
                fontsize=8, color=TINTA_2, ha="right", va="top")
    nomes = ", ".join(cfg(p) for p in sorted(cand, key=lambda p: p["vram"]))
    ax.text(0.98, 0.04,
            f"caixa = ruído medido (±0,244 dB, ±122 MB)\n"
            f"empatam com o joelho: {nomes}\n"
            f"o mais rápido deles é o sweet spot: {cfg(doce)}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            color=TINTA_2, linespacing=1.45)

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.08, 1.13)
    ax.set_aspect("equal")
    ax.set_title(cena, loc="left", fontsize=11, color=TINTA, weight="bold")
    ax.set_xlabel("VRAM normalizada (0 = menor, 1 = maior da fronteira)")
    ax.set_ylabel("PSNR normalizado (0 = menor, 1 = maior da fronteira)")
    ax.xaxis.set_major_formatter(lambda v, _: br(v, 1))
    ax.yaxis.set_major_formatter(lambda v, _: br(v, 1))


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    estilo()
    fig, axs = plt.subplots(1, 2, figsize=(12, 6.6))
    for ax, cena in zip(axs, ["garden", "bonsai"]):
        painel(ax, cena)
    h = fig.get_figheight()
    fig.suptitle("Como o joelho da fronteira é encontrado", x=0.06,
                 y=1 - 0.12 / h, ha="left", va="top", fontsize=11.5, color=TINTA)
    fig.text(0.06, 1 - 0.42 / h,
             "Só os pontos da fronteira, com os dois eixos reescalados para 0–1. "
             "A distância de cada ponto acima da reta mede quanto ele rende além do "
             "proporcional;\no joelho é o mais distante — a partir dele, cada MB "
             "a mais compra cada vez menos qualidade.",
             ha="left", va="top", fontsize=8.5, color=TINTA_2, linespacing=1.5)
    fig.subplots_adjust(left=0.06, right=0.985, top=1 - 1.15 / h, bottom=0.1,
                        wspace=0.18)
    out = Path("runs/exp02_final")
    fig.savefig(out / "joelho_explicado.png", dpi=170)
    fig.savefig(out / "joelho_explicado.pdf")
    print(f"figura -> {out}/joelho_explicado.png/.pdf")


if __name__ == "__main__":
    main()
