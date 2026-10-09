#!/usr/bin/env python3
"""Analise robusta da variancia, separando ruido tipico de falha de convergencia.

A serie de 24 execucoes revelou dois fenomenos distintos que nao podem ser
tratados pela mesma estatistica:

  1. ruido tipico -- amplitude de 0,02 a 0,24 dB entre execucoes identicas,
     presente em todas as configuracoes;
  2. falha ocasional de convergencia -- uma execucao terminou 1,8 dB abaixo das
     gemeas, com SSIM e LPIPS concordando e o desvio entre vistas elevado.

Misturar os dois infla o ruido e torna quase tudo "indistinguivel", o que e
conservador demais. Separa-los e escolher a dedo o que descartar, o que e pior.
A saida adotada: identificar outliers por criterio declarado (desvio > k vezes a
mediana das amplitudes), reportar as duas leituras lado a lado e nunca remover
dado do CSV bruto.

    python3 scripts/analise_variancia.py --run-dir runs/exp02_variance
"""

import argparse
import csv
import statistics
from pathlib import Path


def carregar(run_dir):
    rows = [r for r in csv.DictReader((run_dir / "variancia_bruto.csv").open())
            if r.get("status") == "ok"]
    for r in rows:
        for k in ("psnr", "ssim", "lpips", "vram_peak_mb", "t_train_s",
                  "steps_per_s", "psnr_std"):
            if r.get(k) not in (None, ""):
                r[k] = float(r[k])
    return rows


def grupos(rows):
    g = {}
    for r in rows:
        g.setdefault((r["scene"], r["config"]), []).append(r)
    return g


def marcar_outliers(g, k=3.0):
    """Outlier = desvio da mediana do grupo maior que k vezes a mediana das
    amplitudes de TODOS os grupos. O limiar vem do conjunto, nao do grupo, para
    nao virar circular (um grupo com outlier tem amplitude grande por causa
    dele)."""
    amplitudes = []
    for ls in g.values():
        v = [r["psnr"] for r in ls]
        amplitudes.append(max(v) - min(v))
    ruido_tipico = statistics.median(amplitudes)
    limiar = k * ruido_tipico

    marcados = []
    for (scene, cfg), ls in g.items():
        med = statistics.median(r["psnr"] for r in ls)
        for r in ls:
            r["desvio_da_mediana"] = round(r["psnr"] - med, 4)
            r["outlier"] = abs(r["psnr"] - med) > limiar
            if r["outlier"]:
                marcados.append(r)
    return ruido_tipico, limiar, marcados


def estat(ls, campo="psnr"):
    v = [r[campo] for r in ls if isinstance(r.get(campo), float)]
    if not v:
        return {}
    return {
        "n": len(v), "media": statistics.fmean(v),
        "desvio": statistics.stdev(v) if len(v) > 1 else 0.0,
        "min": min(v), "max": max(v), "amplitude": max(v) - min(v),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/exp02_variance")
    ap.add_argument("--k-outlier", type=float, default=3.0)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    rows = carregar(run_dir)
    g = grupos(rows)
    ruido_tipico, limiar, marcados = marcar_outliers(g, args.k_outlier)

    print(f"mediana das amplitudes de PSNR entre grupos: {ruido_tipico:.4f} dB")
    print(f"limiar de outlier ({args.k_outlier}x): {limiar:.4f} dB\n")

    if marcados:
        print("EXECUCOES MARCADAS COMO OUTLIER:")
        for r in marcados:
            print(f"  {r['scene']}/{r['config']}/rep{r['rep']}: "
                  f"PSNR={r['psnr']:.4f} ({r['desvio_da_mediana']:+.4f} da mediana) "
                  f"SSIM={r['ssim']:.4f} LPIPS={r['lpips']:.4f} "
                  f"desvio entre vistas={r.get('psnr_std')}")
        print()

    print(f"{'cena':>7} {'config':>14} | {'COM outlier':>26} | {'SEM outlier':>26}")
    print(f"{'':>7} {'':>14} | {'media':>8}{'ampl':>9}{'n':>4} | "
          f"{'media':>8}{'ampl':>9}{'n':>4}")
    print("-" * 84)
    resumo = []
    for (scene, cfg), ls in sorted(g.items()):
        com = estat(ls)
        limpo = [r for r in ls if not r["outlier"]]
        sem = estat(limpo)
        resumo.append({"scene": scene, "config": cfg,
                       "com": com, "sem": sem, "limpo": limpo})
        print(f"{scene:>7} {cfg:>14} | {com['media']:>8.4f}{com['amplitude']:>9.4f}"
              f"{com['n']:>4} | {sem['media']:>8.4f}{sem['amplitude']:>9.4f}{sem['n']:>4}")

    # --- ruido de referencia, sem os outliers -------------------------------
    amps = [r["sem"]["amplitude"] for r in resumo if r["sem"].get("n", 0) > 1]
    ruido_ref = max(amps)
    print(f"\nruido de referencia (maior amplitude sem outliers): {ruido_ref:.4f} dB")
    print("Usado como limiar de distinguibilidade: conservador, pois adota o pior")
    print("caso observado em vez da media.\n")

    # --- comparacoes --------------------------------------------------------
    print("COMPARACOES ENTRE CONFIGURACOES (sem outliers)")
    print(f"{'cena':>7} {'par':>32} {'dPSNR':>9} {'dVRAM':>9} {'veredito':>18}")
    print("-" * 82)
    saida = []
    for scene in sorted({r["scene"] for r in resumo}):
        rs = [r for r in resumo if r["scene"] == scene]
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if not (a["sem"] and b["sem"]):
                    continue
                d = a["sem"]["media"] - b["sem"]["media"]
                va = estat(a["limpo"], "vram_peak_mb")
                vb = estat(b["limpo"], "vram_peak_mb")
                dv = va["media"] - vb["media"]
                dist = abs(d) > ruido_ref
                veredito = "distinguivel" if dist else "NAO distinguivel"
                par = f"{a['config']} vs {b['config']}"
                print(f"{scene:>7} {par:>32} {d:>+9.4f} {dv:>+9.1f} {veredito:>18}")
                saida.append({
                    "scene": scene, "config_a": a["config"], "config_b": b["config"],
                    "psnr_a": round(a["sem"]["media"], 4),
                    "psnr_b": round(b["sem"]["media"], 4),
                    "delta_psnr": round(d, 4),
                    "delta_vram_mb": round(dv, 1),
                    "ruido_referencia": round(ruido_ref, 4),
                    "distinguivel": dist,
                })

    with (run_dir / "variancia_comparacoes_robusto.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(saida[0]))
        w.writeheader()
        for r in saida:
            w.writerow(r)

    with (run_dir / "variancia_resumo_robusto.csv").open("w", newline="") as fh:
        campos = ["scene", "config", "n_total", "n_sem_outlier",
                  "psnr_media_com", "psnr_amplitude_com",
                  "psnr_media_sem", "psnr_amplitude_sem", "psnr_desvio_sem",
                  "vram_media_sem", "vram_amplitude_sem"]
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for r in resumo:
            v = estat(r["limpo"], "vram_peak_mb")
            w.writerow({
                "scene": r["scene"], "config": r["config"],
                "n_total": r["com"]["n"], "n_sem_outlier": r["sem"]["n"],
                "psnr_media_com": round(r["com"]["media"], 4),
                "psnr_amplitude_com": round(r["com"]["amplitude"], 4),
                "psnr_media_sem": round(r["sem"]["media"], 4),
                "psnr_amplitude_sem": round(r["sem"]["amplitude"], 4),
                "psnr_desvio_sem": round(r["sem"]["desvio"], 4),
                "vram_media_sem": round(v.get("media", 0), 1),
                "vram_amplitude_sem": round(v.get("amplitude", 0), 1),
            })

    print(f"\ncsv -> {run_dir}/variancia_resumo_robusto.csv")
    print(f"csv -> {run_dir}/variancia_comparacoes_robusto.csv")


if __name__ == "__main__":
    main()
