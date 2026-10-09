#!/usr/bin/env python3
"""Etapa 2 do fechamento: o truncamento em 5000 iteracoes distorceu a fronteira?

A curva de convergencia do bonsai mostrou ~1,6 dB ainda disponiveis entre 5000 e
30 000 iteracoes. Que 20 000 iteracoes rendem mais PSNR ja se sabe. A pergunta
aqui e outra: a ORDEM entre configuracoes se mantem? Configuracoes de maior
capacidade convergem mais devagar e podem ter sido penalizadas pelo truncamento.

Criterio, fixado antes de rodar (docs/PLANO-fechamento.md, Etapa 2):

  ordem PRESERVADA se
    (1) nenhum par separado por mais que o ruido (0,244 dB) a 5000 iteracoes
        inverter de sinal a 20 000; e
    (2) a distancia de PSNR entre a leve e a pesada nao crescer mais que 0,5 dB.

  caso contrario, ordem ALTERADA -> refazer o grid do bonsai a 20 000.

Referencia a 5000: media das 3 repeticoes onde existe (exp02_variance), valor do
grid nas demais.

    python3 scripts/teste_ordenacao.py
"""

import argparse
import csv
import itertools
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import variancia as var  # noqa: E402
from calib_resolucao import acquire_lock  # noqa: E402

RUIDO_REF = 0.244
CRESC_MAX = 0.5

CONFIGS = [
    ("leve", 17, 2, 8),
    ("candidata", 19, 2, 8),
    ("base_json", None, None, None),
    ("pesada", 19, 8, 16),
]


def referencia_5000(cena, rotulo, T, F, L):
    """Melhor estimativa disponivel a 5000 iteracoes, com a procedencia."""
    resumo = PROJECT_ROOT / "runs/exp02_variance/variancia_resumo_robusto.csv"
    if resumo.exists():
        for r in csv.DictReader(resumo.open()):
            if r["scene"] == cena and r["config"] == rotulo:
                return float(r["psnr_media_sem"]), f"media n={r['n_sem_outlier']}"
    grid = PROJECT_ROOT / "runs/exp02/results.csv"
    for r in csv.DictReader(grid.open()):
        if r.get("dataset") != cena or r.get("status") != "ok":
            continue
        if T is None and r["kind"] == "baseline":
            return float(r["psnr"]), "grid n=1"
        if T is not None and r["T"] == str(T) and r["F"] == str(F) and r["L"] == str(L):
            return float(r["psnr"]), "grid n=1"
    return None, "ausente"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bonsai")
    ap.add_argument("--n-steps", type=int, default=20000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--test-stride", type=int, default=1)
    ap.add_argument("--lpips-device", default="cpu", choices=["cpu", "cuda", "none"])
    ap.add_argument("--base-limite", type=float, default=900.0)
    ap.add_argument("--base-tentativas", type=int, default=3)
    ap.add_argument("--base-espera", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=10800)
    ap.add_argument("--exp-id", default="exp02_ordenacao")
    args = ap.parse_args()

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    linhas = []
    for rotulo, T, F, L in CONFIGS:
        linhas.append(var.uma_execucao(args.scene, rotulo, T, F, L, 1, args, exp_dir))
        with (exp_dir / "ordenacao_bruto.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=var.CSV_FIELDS, extrasaction="ignore")
            w.writeheader()
            for l in linhas:
                w.writerow(l)

    tabela = []
    for (rotulo, T, F, L), l in zip(CONFIGS, linhas):
        ref, proc = referencia_5000(args.scene, rotulo, T, F, L)
        p20 = float(l["psnr"]) if l.get("status") == "ok" else None
        tabela.append({
            "config": rotulo, "T": T or 19, "F": F or 4, "L": L or 8,
            "psnr_5000": ref, "procedencia_5000": proc, "psnr_20000": p20,
            "ganho": None if (ref is None or p20 is None) else round(p20 - ref, 4),
            "vram_20000": l.get("vram_peak_mb"),
            "t_train_20000": l.get("t_train_s"),
        })

    # --- criterio (1): inversoes entre pares separados por mais que o ruido ---
    inversoes = []
    for a, b in itertools.combinations(tabela, 2):
        if None in (a["psnr_5000"], b["psnr_5000"], a["psnr_20000"], b["psnr_20000"]):
            continue
        d5 = a["psnr_5000"] - b["psnr_5000"]
        d20 = a["psnr_20000"] - b["psnr_20000"]
        if abs(d5) > RUIDO_REF and (d5 > 0) != (d20 > 0):
            inversoes.append((a["config"], b["config"], d5, d20))

    # --- criterio (2): crescimento da distancia leve -> pesada ---------------
    leve = next(t for t in tabela if t["config"] == "leve")
    pesada = next(t for t in tabela if t["config"] == "pesada")
    dist5 = pesada["psnr_5000"] - leve["psnr_5000"]
    dist20 = pesada["psnr_20000"] - leve["psnr_20000"]
    cresc = dist20 - dist5

    preservada = (not inversoes) and (cresc <= CRESC_MAX)

    with (exp_dir / "ordenacao.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tabela[0]))
        w.writeheader()
        for t in tabela:
            w.writerow(t)
    with (exp_dir / "veredito.txt").open("w") as fh:
        fh.write(f"inversoes={len(inversoes)}\n")
        for i in inversoes:
            fh.write(f"  {i[0]} vs {i[1]}: 5000 {i[2]:+.4f} / 20000 {i[3]:+.4f}\n")
        fh.write(f"distancia_leve_pesada_5000={dist5:.4f}\n")
        fh.write(f"distancia_leve_pesada_20000={dist20:.4f}\n")
        fh.write(f"crescimento={cresc:.4f} (limite {CRESC_MAX})\n")
        fh.write(f"veredito={'PRESERVADA' if preservada else 'ALTERADA'}\n")

    # --- figura: grafico de inclinacao 5000 -> 20000 -------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 6))
    cores = {"leve": "#2e7d32", "candidata": "#1f4e79",
             "base_json": "#8e24aa", "pesada": "#c00000"}
    for t in tabela:
        ax.plot([0, 1], [t["psnr_5000"], t["psnr_20000"]], marker="o", ms=8,
                lw=2, color=cores[t["config"]])
        ax.annotate(f"{t['config']}  T{t['T']} F{t['F']} L{t['L']}  "
                    f"({t['psnr_5000']:.2f})", xy=(0, t["psnr_5000"]),
                    xytext=(-8, 0), textcoords="offset points", ha="right",
                    va="center", fontsize=8, color=cores[t["config"]])
        ax.annotate(f"{t['psnr_20000']:.2f}  (+{t['ganho']:.2f})",
                    xy=(1, t["psnr_20000"]), xytext=(8, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=8, color=cores[t["config"]])
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["5000 iteracoes", "20 000 iteracoes"])
    ax.set_xlim(-0.9, 1.6)
    ax.set_ylabel("PSNR no conjunto de teste (dB)")
    ax.set_title(f"{args.scene}: a ordem entre configuracoes se mantem?\n"
                 f"veredito: {'PRESERVADA' if preservada else 'ALTERADA'} — "
                 f"{len(inversoes)} inversao(oes), distancia leve-pesada "
                 f"{dist5:.2f} -> {dist20:.2f} dB", fontsize=10)
    ax.grid(alpha=0.3, axis="y")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.08)
    fig.savefig(exp_dir / "ordenacao.png", dpi=150)
    plt.close(fig)

    print("\n" + "=" * 84)
    print(f"{'config':>10} {'T F L':>10} {'PSNR 5000':>10} {'origem':>11} "
          f"{'PSNR 20000':>11} {'ganho':>7} {'VRAM 20k':>9}")
    print("-" * 84)
    for t in tabela:
        print(f"{t['config']:>10} {str(t['T'])+' '+str(t['F'])+' '+str(t['L']):>10} "
              f"{t['psnr_5000']:>10.4f} {t['procedencia_5000']:>11} "
              f"{t['psnr_20000']:>11.4f} {t['ganho']:>+7.3f} "
              f"{float(t['vram_20000']):>9.1f}")
    print("-" * 84)
    print(f"inversoes entre pares distinguiveis: {len(inversoes)}")
    for i in inversoes:
        print(f"  {i[0]} vs {i[1]}: {i[2]:+.4f} -> {i[3]:+.4f}")
    print(f"distancia leve->pesada: {dist5:.4f} -> {dist20:.4f} "
          f"(crescimento {cresc:+.4f}, limite {CRESC_MAX})")
    print(f"VEREDITO: ORDEM {'PRESERVADA' if preservada else 'ALTERADA'}")
    print(f"\ncsv -> {exp_dir}/ordenacao.csv | figura -> {exp_dir}/ordenacao.png")


if __name__ == "__main__":
    main()
