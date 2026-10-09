#!/usr/bin/env python3
"""Etapa 1 do fechamento: triagem de pontos suspeitos no grid do exp02.

O grid tem n=1 por combinacao, e a validacao de variancia observou falha de
convergencia em 1 de 24 execucoes (uma execucao terminou 1,8 dB abaixo das
gemeas, com status=ok e nenhum aviso). Extrapolando, ~2 dos 54 pontos podem
estar contaminados, e o results.csv nao os distingue.

Criterio, fixado antes de olhar os dados (docs/PLANO-fechamento.md):
aumentar T, F ou L mantendo os outros dois fixos nao deveria REDUZIR o PSNR em
mais de 0,47 dB -- 3x a mediana das amplitudes medidas entre execucoes
identicas. Cada violacao gera um suspeito: o ponto de MENOR PSNR do par, porque
falha de convergencia produz valor baixo, nao alto.

Monotonicidade e heuristica, nao lei: mais capacidade a iteracoes fixas pode
genuinamente render menos. Por isso suspeito nao e descartado -- e reexecutado,
e a reexecucao decide.

    python3 scripts/triagem_monotonicidade.py --csv runs/exp02/results.csv
"""

import argparse
import csv
from pathlib import Path

LIMIAR_DB = 0.47
EIXOS = {"T": [15, 17, 19], "F": [2, 4, 8], "L": [4, 8, 16]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="runs/exp02/results.csv")
    ap.add_argument("--limiar", type=float, default=LIMIAR_DB)
    ap.add_argument("--out-dir", default="runs/exp02_triagem")
    args = ap.parse_args()

    linhas = [l for l in csv.DictReader(Path(args.csv).open())
              if l.get("status") == "ok" and l.get("kind") == "grid"]
    ponto = {}
    for l in linhas:
        ponto[(l["dataset"], int(l["T"]), int(l["F"]), int(l["L"]))] = l

    violacoes = []
    for (cena, T, F, L), l in ponto.items():
        atual = {"T": T, "F": F, "L": L}
        for eixo, valores in EIXOS.items():
            i = valores.index(atual[eixo])
            if i + 1 >= len(valores):
                continue
            maior = dict(atual)
            maior[eixo] = valores[i + 1]
            chave = (cena, maior["T"], maior["F"], maior["L"])
            if chave not in ponto:
                continue
            p_menor = float(l["psnr"])
            p_maior = float(ponto[chave]["psnr"])
            queda = p_menor - p_maior
            if queda > args.limiar:
                violacoes.append({
                    "scene": cena, "eixo": eixo,
                    "de": f"T{T} F{F} L{L}",
                    "para": f"T{maior['T']} F{maior['F']} L{maior['L']}",
                    "psnr_de": round(p_menor, 4), "psnr_para": round(p_maior, 4),
                    "queda_db": round(queda, 4),
                    "suspeito": f"{cena}_T{maior['T']}_F{maior['F']}_L{maior['L']}",
                })

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "violacoes.csv").open("w", newline="") as fh:
        campos = ["scene", "eixo", "de", "para", "psnr_de", "psnr_para",
                  "queda_db", "suspeito"]
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for v in sorted(violacoes, key=lambda v: (v["scene"], -v["queda_db"])):
            w.writerow(v)

    # Um ponto pode violar em mais de um eixo; conta uma vez.
    suspeitos = {}
    for v in violacoes:
        s = suspeitos.setdefault(v["suspeito"], {"n_violacoes": 0, "max_queda": 0.0,
                                                  "eixos": set()})
        s["n_violacoes"] += 1
        s["max_queda"] = max(s["max_queda"], v["queda_db"])
        s["eixos"].add(v["eixo"])

    with (out / "suspeitos.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["run_tag", "scene", "T", "F", "L", "psnr",
                                           "n_violacoes", "max_queda_db", "eixos"])
        w.writeheader()
        for tag, s in sorted(suspeitos.items(), key=lambda kv: -kv[1]["max_queda"]):
            cena, t, f, l = tag.split("_")
            p = ponto[(cena, int(t[1:]), int(f[1:]), int(l[1:]))]
            w.writerow({"run_tag": tag, "scene": cena, "T": t[1:], "F": f[1:],
                        "L": l[1:], "psnr": p["psnr"],
                        "n_violacoes": s["n_violacoes"],
                        "max_queda_db": round(s["max_queda"], 4),
                        "eixos": "".join(sorted(s["eixos"]))})

    print(f"{len(linhas)} pontos do grid | limiar {args.limiar} dB")
    print(f"{len(violacoes)} violacoes de monotonicidade, {len(suspeitos)} pontos suspeitos\n")
    print(f"{'cena':>7} {'eixo':>4} {'de':>13} -> {'para':<13} {'PSNR de':>8} "
          f"{'PSNR para':>9} {'queda':>7}")
    print("-" * 72)
    for v in sorted(violacoes, key=lambda v: (v["scene"], -v["queda_db"])):
        print(f"{v['scene']:>7} {v['eixo']:>4} {v['de']:>13} -> {v['para']:<13} "
              f"{v['psnr_de']:>8.3f} {v['psnr_para']:>9.3f} {v['queda_db']:>7.3f}")
    print("\nSUSPEITOS (ponto de menor PSNR de cada violacao):")
    for tag, s in sorted(suspeitos.items(), key=lambda kv: -kv[1]["max_queda"]):
        print(f"  {tag:<24} {s['n_violacoes']} violacao(oes), queda max "
              f"{s['max_queda']:.3f} dB, eixo(s) {''.join(sorted(s['eixos']))}")
    print(f"\ncsv -> {out}/violacoes.csv, {out}/suspeitos.csv")


if __name__ == "__main__":
    main()
