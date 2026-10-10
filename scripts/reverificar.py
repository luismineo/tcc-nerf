#!/usr/bin/env python3
"""Reexecuta pontos suspeitos do grid e decide se o valor original se sustenta.

Reaproveita variancia.uma_execucao (mesmo worker, mesmo protocolo, mesma
amostragem de linha de base), para que a reexecucao seja comparavel ao grid.

Regra de decisao, fixada antes de rodar (docs/metodo/PLANO-fechamento.md, Etapa 1):

  - reexecucoes concordam entre si (amplitude <= ruido de referencia, 0,244 dB)
    E a media difere do valor do grid em mais de 0,47 dB
      -> SUBSTITUIR o ponto do grid pela media das reexecucoes;
  - media das reexecucoes a ate 0,47 dB do grid
      -> MANTER o ponto do grid;
  - reexecucoes discordam entre si
      -> usar a MEDIANA dos tres valores (grid + 2 reexecucoes).

O valor original nunca e apagado: a correcao vive num CSV separado
(grid_corrigido.csv), com coluna de procedencia.

    python3 scripts/reverificar.py --suspeitos runs/exp02_triagem/suspeitos.csv
"""

import argparse
import csv
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import variancia as var  # noqa: E402
from calib_resolucao import acquire_lock  # noqa: E402

RUIDO_REF = 0.244
LIMIAR_SUSPEITA = 0.47


def decidir(grid_psnr, reexec):
    amp = max(reexec) - min(reexec)
    media = statistics.fmean(reexec)
    if amp > RUIDO_REF:
        valor = statistics.median([grid_psnr] + reexec)
        return "mediana_de_tres", valor, amp, media
    if abs(media - grid_psnr) > LIMIAR_SUSPEITA:
        return "substituir", media, amp, media
    return "manter", grid_psnr, amp, media


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suspeitos", default="runs/exp02_triagem/suspeitos.csv")
    ap.add_argument("--grid-csv", default="runs/exp02/results.csv")
    ap.add_argument("--repeticoes", type=int, default=2)
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
    ap.add_argument("--exp-id", default="exp02_triagem")
    args = ap.parse_args()

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    suspeitos = list(csv.DictReader(Path(args.suspeitos).open()))
    grid = list(csv.DictReader(Path(args.grid_csv).open()))
    print(f"{len(suspeitos)} suspeito(s) x {args.repeticoes} reexecucoes\n")

    linhas = []
    for s in suspeitos:
        T, F, L = int(s["T"]), int(s["F"]), int(s["L"])
        for rep in range(1, args.repeticoes + 1):
            linhas.append(var.uma_execucao(s["scene"], f"reexec_T{T}_F{F}_L{L}",
                                           T, F, L, rep, args, exp_dir))
            with (exp_dir / "reexecucoes_bruto.csv").open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=var.CSV_FIELDS, extrasaction="ignore")
                w.writeheader()
                for l in linhas:
                    w.writerow(l)

    decisoes = []
    for s in suspeitos:
        T, F, L = s["T"], s["F"], s["L"]
        reexec = [float(l["psnr"]) for l in linhas
                  if l["scene"] == s["scene"] and str(l["T"]) == T
                  and str(l["F"]) == F and str(l["L"]) == L
                  and l.get("status") == "ok"]
        g = float(s["psnr"])
        if len(reexec) < 2:
            decisoes.append({"run_tag": s["run_tag"], "decisao": "inconclusivo",
                             "psnr_grid": g, "reexecucoes": reexec})
            continue
        dec, valor, amp, media = decidir(g, reexec)
        decisoes.append({
            "run_tag": s["run_tag"], "scene": s["scene"], "T": T, "F": F, "L": L,
            "psnr_grid": g,
            "reexecucoes": " | ".join(f"{x:.4f}" for x in reexec),
            "media_reexec": round(media, 4),
            "amplitude_reexec": round(amp, 4),
            "delta_media_vs_grid": round(media - g, 4),
            "decisao": dec, "psnr_adotado": round(valor, 4),
        })

    with (exp_dir / "decisoes.csv").open("w", newline="") as fh:
        campos = ["run_tag", "scene", "T", "F", "L", "psnr_grid", "reexecucoes",
                  "media_reexec", "amplitude_reexec", "delta_media_vs_grid",
                  "decisao", "psnr_adotado"]
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for d in decisoes:
            w.writerow(d)

    # Grid corrigido: copia integral do original, com procedencia por linha.
    adotado = {d["run_tag"]: d for d in decisoes}
    campos_grid = list(grid[0].keys()) + ["psnr_original", "procedencia_psnr"]
    with (exp_dir / "grid_corrigido.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos_grid)
        w.writeheader()
        for r in grid:
            r = dict(r)
            chave = r["run_tag"].rsplit("_s", 1)[0]
            r["psnr_original"] = r.get("psnr")
            d = adotado.get(chave)
            if d and d["decisao"] in ("substituir", "mediana_de_tres"):
                r["psnr"] = d["psnr_adotado"]
                r["procedencia_psnr"] = f"{d['decisao']} (reverificado na Etapa 1)"
            elif d:
                r["procedencia_psnr"] = f"{d['decisao']} (reverificado na Etapa 1)"
            else:
                r["procedencia_psnr"] = "grid original"
            w.writerow(r)

    print("\n" + "=" * 88)
    print("DECISOES")
    print("=" * 88)
    for d in decisoes:
        print(f"  {d['run_tag']:<22} grid={d['psnr_grid']:.4f}  "
              f"reexec=[{d.get('reexecucoes')}]  -> {d['decisao'].upper()}  "
              f"(adotado {d.get('psnr_adotado')})")
    print(f"\ncsv -> {exp_dir}/decisoes.csv, {exp_dir}/grid_corrigido.csv")


if __name__ == "__main__":
    main()
