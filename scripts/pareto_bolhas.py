#!/usr/bin/env python3
"""Fronteira de Pareto PSNR x VRAM com o tempo de treino no tamanho da bolha.

Tres objetivos num grafico so: qualidade (eixo y), memoria (eixo x) e tempo de
treino (area da bolha). Um painel por cena -- as escalas diferem, e dois eixos y
num mesmo painel inventariam uma correlacao.

Criterio de sweet spot, objetivo e declarado:

  1. joelho da fronteira: o ponto de maior distancia acima da reta que liga os
     extremos da fronteira, com os dois eixos normalizados para [0, 1];
  2. candidatos: o joelho e os pontos da fronteira indistinguiveis dele dentro
     do ruido medido (|dPSNR| <= 0,244 dB e |dVRAM| <= 122 MB);
  3. sweet spot: o candidato de menor tempo de treino.

O passo 3 existe porque o joelho geometrico so olha PSNR e VRAM: nas duas cenas
ele cai num ponto que empata, dentro do ruido, com um vizinho bem mais rapido.

Area da bolha proporcional ao tempo (e nao o diametro): com o diametro, uma
configuracao com 4x o tempo pareceria 16x maior.

Entrada: runs/exp02_final/grid_{cena}.csv (media de todas as medicoes a 5000
iteracoes por configuracao, com n registrado).

    python3 scripts/pareto_bolhas.py
"""

import csv
import math
from pathlib import Path

RUIDO_PSNR = 0.244
RUIDO_VRAM = 122.0
PADRAO = ("19", "4", "8")

# Paleta: referencia da skill de visualizacao, validada (2 slots, todos os pares,
# PASS em CVD e contraste). Cor so como enfase: cinza para o grid, azul para a
# fronteira, laranja exclusivamente para candidatos e sweet spot.
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
MUDO = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
CINZA = "#c9c8c2"
AZUL = "#2a78d6"
LARANJA = "#eb6834"

ESCALA_AREA = 1.25    # pontos^2 por segundo de treino


def br(x, casas=2):
    """Numero com virgula decimal, como no texto do artigo."""
    return f"{x:.{casas}f}".replace(".", ",").replace("-", "−")


def carregar(cena):
    pts = []
    for r in csv.DictReader(open(f"runs/exp02_final/grid_{cena}.csv")):
        pts.append({
            "T": r["T"], "F": r["F"], "L": r["L"], "n": int(r["n"]),
            "psnr": float(r["psnr"]), "vram": float(r["vram"]),
            "t": float(r["t_train"]), "ssim": float(r["ssim"]),
            "fronteira": r["na_fronteira"] == "True",
        })
    return pts


def cfg(p):
    return f"T{p['T']} F{p['F']} L{p['L']}"


def sweet_spot(pts):
    fr = sorted([p for p in pts if p["fronteira"]], key=lambda p: p["vram"])
    x0, x1 = fr[0]["vram"], fr[-1]["vram"]
    y0, y1 = fr[0]["psnr"], fr[-1]["psnr"]
    for p in fr:
        xn = (p["vram"] - x0) / (x1 - x0)
        yn = (p["psnr"] - y0) / (y1 - y0)
        p["dist_joelho"] = (yn - xn) / math.sqrt(2)
    joelho = max(fr, key=lambda p: p["dist_joelho"])
    cand = [p for p in fr if abs(p["psnr"] - joelho["psnr"]) <= RUIDO_PSNR
            and abs(p["vram"] - joelho["vram"]) <= RUIDO_VRAM]
    doce = min(cand, key=lambda p: (p["t"], p["vram"]))
    return fr, joelho, cand, doce


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 9,
        "axes.edgecolor": EIXO, "axes.labelcolor": TINTA_2,
        "xtick.color": MUDO, "ytick.color": MUDO,
        "axes.facecolor": SUPERFICIE, "figure.facecolor": SUPERFICIE,
    })

    out = Path("runs/exp02_final")
    cenas = ["garden", "bonsai"]
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.2))
    linhas_csv = []

    for ax, cena in zip(axs, cenas):
        pts = carregar(cena)
        fr, joelho, cand, doce = sweet_spot(pts)
        padrao = next(p for p in pts if (p["T"], p["F"], p["L"]) == PADRAO)

        for p in pts:
            linhas_csv.append({
                "scene": cena, "config": cfg(p), "n": p["n"],
                "psnr": round(p["psnr"], 4), "vram": round(p["vram"], 1),
                "t_train": round(p["t"], 1), "na_fronteira": p["fronteira"],
                "dist_joelho": round(p.get("dist_joelho", float("nan")), 4)
                if p["fronteira"] else "",
                "joelho": p is joelho, "candidato": p in cand,
                "sweet_spot": p is doce, "padrao": p is padrao,
            })

        # grade e eixos recessivos
        ax.grid(True, color=GRADE, lw=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)

        # fronteira: linha em degrau, por baixo das bolhas
        ax.step([p["vram"] for p in fr], [p["psnr"] for p in fr], where="post",
                color=AZUL, lw=2, alpha=0.9, zorder=2)

        # bolhas: anel da cor da superficie separa as que se sobrepoem
        fora = [p for p in pts if not p["fronteira"]]
        ax.scatter([p["vram"] for p in fora], [p["psnr"] for p in fora],
                   s=[p["t"] * ESCALA_AREA for p in fora], color=CINZA,
                   edgecolor=SUPERFICIE, lw=1.4, zorder=3)
        normais = [p for p in fr if p not in cand]
        ax.scatter([p["vram"] for p in normais], [p["psnr"] for p in normais],
                   s=[p["t"] * ESCALA_AREA for p in normais], color=AZUL,
                   edgecolor=SUPERFICIE, lw=1.4, alpha=0.85, zorder=4)
        outros_cand = [p for p in cand if p is not doce]
        ax.scatter([p["vram"] for p in outros_cand], [p["psnr"] for p in outros_cand],
                   s=[p["t"] * ESCALA_AREA for p in outros_cand], color=AZUL,
                   edgecolor=LARANJA, lw=2.2, zorder=5)
        ax.scatter([doce["vram"]], [doce["psnr"]], s=[doce["t"] * ESCALA_AREA],
                   color=LARANJA, edgecolor=SUPERFICIE, lw=1.6, zorder=6)
        ax.scatter([padrao["vram"]], [padrao["psnr"]], marker="*", s=70,
                   color=TINTA, edgecolor=SUPERFICIE, lw=0.6, zorder=7)

        # rotulos seletivos: so os candidatos que nao sao o sweet spot, na area
        # vazia acima da fronteira (abaixo dela ficam as bolhas cinza)
        for i, p in enumerate(sorted(outros_cand, key=lambda p: p["vram"])):
            ax.annotate(f"{cfg(p)} · {br(p['t'], 0)} s", xy=(p["vram"], p["psnr"]),
                        xytext=(14, 24 + 15 * i), textcoords="offset points",
                        fontsize=8, color=TINTA_2,
                        arrowprops=dict(arrowstyle="-", color=MUDO, lw=0.6,
                                        shrinkB=6))

        # balao do sweet spot
        if doce is padrao:
            comp = "= configuração padrão (base.json)"
        else:
            comp = (f"vs. padrão: {br(doce['psnr'] - padrao['psnr'])} dB · "
                    f"{br(doce['vram'] - padrao['vram'], 0)} MB · "
                    f"{br(100 * (doce['t'] - padrao['t']) / padrao['t'], 0)} % tempo")
        texto = (f"Sweet spot — {cena}\n"
                 f"T = {doce['T']} · F = {doce['F']} · L = {doce['L']}\n"
                 f"PSNR {br(doce['psnr'])} dB · SSIM {br(doce['ssim'], 3)}\n"
                 f"VRAM {br(doce['vram'], 0)} MB · treino {br(doce['t'], 0)} s\n"
                 f"média de n = {doce['n']} execuções\n{comp}")
        ax.annotate(texto, xy=(doce["vram"], doce["psnr"]),
                    xytext=(0.47, 0.30), textcoords="axes fraction",
                    fontsize=8.5, color=TINTA, linespacing=1.45,
                    bbox=dict(boxstyle="round,pad=0.6", fc="white", ec=LARANJA, lw=1.4),
                    arrowprops=dict(arrowstyle="-|>", color=LARANJA, lw=1.3,
                                    connectionstyle="arc3,rad=-0.15",
                                    shrinkA=4, shrinkB=9),
                    zorder=8)

        ax.set_title(f"{cena}", loc="left", fontsize=11, color=TINTA, weight="bold")
        ax.set_xlabel("pico de VRAM descontada a ocupação prévia (MB)")
        ax.set_ylabel("PSNR nas vistas de teste (dB)")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br(v, 0)))
        ax.margins(x=0.06, y=0.14)

    # legenda unica, compartilhada pelos dois paineis
    itens = [
        Line2D([], [], color=AZUL, lw=2, label="fronteira de Pareto"),
        Line2D([], [], ls="", marker="o", ms=9, mfc=CINZA, mec=SUPERFICIE,
               label="fora da fronteira"),
        Line2D([], [], ls="", marker="o", ms=9, mfc=AZUL, mec=SUPERFICIE,
               label="na fronteira"),
        Line2D([], [], ls="", marker="o", ms=9, mfc=AZUL, mec=LARANJA, mew=2,
               label="candidato (empata com o joelho)"),
        Line2D([], [], ls="", marker="o", ms=10, mfc=LARANJA, mec=SUPERFICIE,
               label="sweet spot"),
        Line2D([], [], ls="", marker="*", ms=10, mfc=TINTA, mec=SUPERFICIE,
               label="configuração padrão"),
    ]
    fig.legend(handles=itens, loc="lower left", bbox_to_anchor=(0.055, 0.01),
               ncol=3, frameon=False, fontsize=8.5, labelcolor=TINTA_2,
               columnspacing=2.0)
    tamanhos = [Line2D([], [], ls="", marker="o", mfc="none", mec=MUDO,
                       ms=math.sqrt(t * ESCALA_AREA), label=f"{t} s")
                for t in (100, 200, 300)]
    fig.legend(handles=tamanhos, loc="lower right", bbox_to_anchor=(0.985, 0.01),
               ncol=3, frameon=False, fontsize=8.5, labelcolor=TINTA_2,
               title="tempo de treino (área da bolha)", title_fontsize=8.5,
               handletextpad=0.4, columnspacing=1.6, borderpad=0.2)

    fig.suptitle("Fronteira de Pareto: qualidade × memória, com o tempo de treino "
                 "no tamanho da bolha", x=0.055, ha="left", fontsize=12, color=TINTA)
    fig.text(0.055, 0.905,
             "Cada bolha é uma configuração (T, F, L), média de todas as medições "
             "a 5000 iterações.\nSweet spot: entre o joelho da fronteira e os pontos "
             "indistinguíveis dele (±0,244 dB, ±122 MB), o de menor tempo de treino.",
             ha="left", fontsize=8.5, color=TINTA_2, linespacing=1.5)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.84, bottom=0.19, wspace=0.16)
    fig.savefig(out / "pareto_bolhas.png", dpi=170)
    fig.savefig(out / "pareto_bolhas.pdf")
    plt.close(fig)

    with (out / "sweet_spot.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas_csv[0]))
        w.writeheader()
        for r in linhas_csv:
            w.writerow(r)

    for cena in cenas:
        sel = [r for r in linhas_csv if r["scene"] == cena]
        j = next(r for r in sel if r["joelho"])
        d = next(r for r in sel if r["sweet_spot"])
        c = [r["config"] for r in sel if r["candidato"]]
        print(f"{cena}: joelho {j['config']} | candidatos {', '.join(c)} | "
              f"sweet spot {d['config']} ({d['psnr']} dB, {d['vram']} MB, {d['t_train']} s)")
    print(f"figura -> {out}/pareto_bolhas.png/.pdf | dados -> {out}/sweet_spot.csv")


if __name__ == "__main__":
    main()
