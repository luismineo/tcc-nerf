#!/usr/bin/env python3
"""Sensibilidade das conclusoes ao limiar de ruido de PSNR.

O limiar de 0,244 dB foi fixado antes da consolidacao: maior amplitude entre
tres execucoes identicas na validacao de variancia. Ao reunir todas as medicoes
de cada configuracao (grid, baselines, variancia, triagem), a amplitude chegou a
0,341 dB em garden T19 F2 L16 (n = 4). O criterio NAO e trocado depois de ver o
dado; este script so mostra o que mudaria se fosse, para que as conclusoes
limitrofes sejam declaradas como tais.

Para cada limiar entre 0,15 e 0,50 dB recalcula, por cena: os patamares do guia
(mesma escada e poda de consolidacao_final.py, ruido de VRAM fixo em 122 MB), o
sweet spot (mesmo criterio de pareto_bolhas.py) e o substituto do padrao.

Saidas: runs/exp02_final/sensibilidade_ruido.csv e .png/.pdf

    python3 scripts/sensibilidade_ruido.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import consolidacao_final as cf
import pareto_bolhas as pb

REFERENCIA = 0.244
MAIOR_AMPLITUDE = 0.341   # garden T19 F2 L16, n = 4 (grid_garden.csv)


def analisar(cena, limiar):
    cf.RUIDO = limiar
    pb.RUIDO_PSNR = limiar
    pts = pb.carregar(cena)
    padrao = next(p for p in pts if (p["T"], p["F"], p["L"]) == pb.PADRAO)
    degraus = cf.podar(cf.escada(pts))
    _, joelho, cand, doce = pb.sweet_spot(pts)
    eq = cf.equivalente_ao_padrao(pts, padrao)
    return {
        "cena": cena, "limiar_db": round(limiar, 3),
        "n_patamares": len(degraus),
        "patamares": " | ".join(pb.cfg(p) for p in degraus),
        "padrao_e_patamar": padrao in degraus,
        "joelho": pb.cfg(joelho),
        "candidatos": " | ".join(pb.cfg(p) for p in sorted(cand, key=lambda p: p["vram"])),
        "sweet_spot": pb.cfg(doce),
        "substituto_do_padrao": pb.cfg(eq) if eq else "",
    }


def main():
    limiares = [round(0.15 + 0.01 * i, 3) for i in range(36)]
    for v in (REFERENCIA, MAIOR_AMPLITUDE):
        if v not in limiares:
            limiares.append(v)
    limiares.sort()
    linhas = [analisar(c, l) for c in ("garden", "bonsai") for l in limiares]

    out = Path("runs/exp02_final/sensibilidade_ruido")
    with out.with_suffix(".csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)

    for r in linhas:
        if r["limiar_db"] in (REFERENCIA, MAIOR_AMPLITUDE):
            print(f"{r['cena']:6s} {r['limiar_db']:.3f}  {r['n_patamares']} patamares: "
                  f"{r['patamares']}  | sweet spot {r['sweet_spot']} "
                  f"| substituto {r['substituto_do_padrao'] or '-'}")
    grafico(linhas, out)
    print(f"-> {out}.csv/.png/.pdf")


def grafico(linhas, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pb.estilo()
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    for ax, cena in zip(axs, ("garden", "bonsai")):
        sel = [r for r in linhas if r["cena"] == cena]
        xs = [r["limiar_db"] for r in sel]
        ys = [r["n_patamares"] for r in sel]
        ax.grid(True, color=pb.GRADE, lw=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.axvspan(REFERENCIA, MAIOR_AMPLITUDE, color=pb.GRADE, alpha=0.8, lw=0)
        ax.step(xs, ys, where="post", color=pb.AZUL, lw=2)
        ax.axvline(REFERENCIA, color=pb.LARANJA, lw=1.4)
        ax.text(REFERENCIA - 0.004, 0.3, "limiar adotado\n0,244 dB", ha="right",
                va="bottom", fontsize=8, color=pb.TINTA)
        ax.text(MAIOR_AMPLITUDE + 0.004, 0.3, "maior amplitude\nobservada, 0,341 dB",
                ha="left", va="bottom", fontsize=8, color=pb.TINTA_2)
        ax.set_title(cena, loc="left", fontsize=11, color=pb.TINTA, weight="bold")
        ax.set_xlabel("limiar de ruído de PSNR (dB)")
        ax.xaxis.set_major_formatter(lambda v, _: pb.br(v, 2))
        ax.set_ylim(0, 6.5)
    axs[0].set_ylabel("patamares no guia")
    h = fig.get_figheight()
    fig.suptitle("Quantos patamares o guia teria com outro limiar de ruído",
                 x=0.07, y=1 - 0.12 / h, ha="left", va="top", fontsize=11.5,
                 color=pb.TINTA)
    fig.text(0.07, 1 - 0.42 / h,
             "Faixa cinza: entre o limiar fixado antes da análise e a maior amplitude "
             "vista depois, ao reunir todas as medições. Ruído de VRAM fixo em 122 MB.",
             ha="left", va="top", fontsize=8.5, color=pb.TINTA_2)
    fig.subplots_adjust(left=0.07, right=0.985, top=1 - 0.95 / h, bottom=0.13,
                        wspace=0.12)
    fig.savefig(out.with_suffix(".png"), dpi=170)
    fig.savefig(out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
