#!/usr/bin/env python3
"""Etapa 4 do fechamento: consolidacao analitica do exp02.

Produz, em runs/exp02_final/:

  1. Fronteira de Pareto com ESPESSURA. A fronteira classica trata qualquer
     diferenca de PSNR como real. Com ruido medido de 0,244 dB entre execucoes
     identicas, pontos a menos que isso um do outro nao estao ordenados. A figura
     mostra a fronteira e uma banda de 0,244 dB abaixo dela: o que cai dentro da
     banda e equivalente a fronteira dentro do que os dados resolvem.

  2. Guia por orcamento de VRAM, construido como uma ESCADA: o primeiro degrau e
     a configuracao mais barata; cada degrau seguinte e a configuracao mais barata
     que seja MENSURAVELMENTE melhor (> 0,244 dB) que o degrau anterior. Entre
     dois degraus, pagar mais VRAM nao compra qualidade mensuravel. E o "guia
     pratico de configuracao" que o resumo do artigo promete.

  3. Tabelas finais: grid completo por cena com marcacao de fronteira,
     baselines, e um tabelas.md pronto para transcrever no artigo.

Entrada: runs/exp02_triagem/grid_corrigido.csv (grid com procedencia por linha;
nenhum ponto foi substituido na Etapa 1).

    python3 scripts/consolidacao_final.py
"""

import argparse
import csv
from pathlib import Path

RUIDO = 0.244
# VRAM tambem tem ruido: maior amplitude de vram_peak_mb entre execucoes
# identicas na validacao de variancia (garden/padrao_artigo, 121,6 MB).
RUIDO_VRAM = 122.0


PADRAO = ("19", "4", "8")   # base.json; com N_max = 2048*aabb, e o mesmo modelo
                            # que o ponto T19 F4 L8 do grid (b derivado identico)


def _medidas(raiz):
    """Todas as medicoes a 5000 iteracoes, de todas as fontes, por configuracao.

    Fontes: grid e baseline do exp02, baselines avulsos, validacao de variancia
    (sem o outlier marcado pelo criterio declarado em analise_variancia.py) e
    reexecucoes da triagem. Execucoes a 20 000 iteracoes (Etapa 2) ficam de
    fora: outro regime de treino.
    """
    import statistics
    import analise_variancia as av

    m = {}

    def add(cena, T, F, L, r, fonte):
        if r.get("status") != "ok":
            return
        chave = (cena, str(T), str(F), str(L))
        m.setdefault(chave, []).append({
            "psnr": float(r["psnr"]), "ssim": float(r["ssim"]),
            "lpips": float(r["lpips"]) if r.get("lpips") not in (None, "") else None,
            "vram": float(r["vram_peak_mb"]), "t_train": float(r["t_train_s"]),
            "fonte": fonte})

    for r in csv.DictReader((raiz / "runs/exp02/results.csv").open()):
        if r.get("kind") == "grid":
            add(r["dataset"], r["T"], r["F"], r["L"], r, "grid")
        elif r.get("kind") == "baseline":
            add(r["dataset"], *PADRAO, r, "grid-baseline")
    for r in csv.DictReader((raiz / "runs/exp02_baseline/results.csv").open()):
        add(r["dataset"], *PADRAO, r, "baseline-avulso")

    var_rows = av.carregar(raiz / "runs/exp02_variance")
    _, _, outliers = av.marcar_outliers(av.grupos(var_rows))
    excluir = {(o["scene"], o["config"], o["rep"]) for o in outliers}
    for r in csv.DictReader((raiz / "runs/exp02_variance/variancia_bruto.csv").open()):
        if (r["scene"], r["config"], r["rep"]) in excluir:
            continue
        T, F, L = (r["T"], r["F"], r["L"]) if r["T"] else PADRAO
        add(r["scene"], T, F, L, r, "variancia")
    for r in csv.DictReader((raiz / "runs/exp02_triagem/reexecucoes_bruto.csv").open()):
        add(r["scene"], r["T"], r["F"], r["L"], r, "triagem")

    pontos = {}
    for (cena, T, F, L), ls in m.items():
        def med(k):
            v = [x[k] for x in ls if x[k] is not None]
            return statistics.fmean(v) if v else None
        psnrs = [x["psnr"] for x in ls]
        pontos.setdefault(cena, []).append({
            "run_tag": f"{cena}_T{T}_F{F}_L{L}", "scene": cena,
            "T": T, "F": F, "L": L, "n": len(ls),
            "psnr": med("psnr"), "ssim": med("ssim"), "lpips": med("lpips"),
            "vram": med("vram"), "t_train": med("t_train"),
            "psnr_amplitude": max(psnrs) - min(psnrs),
            "procedencia": "+".join(sorted({x["fonte"] for x in ls})),
        })
    return pontos


def carregar(caminho):
    """Pontos agregados; o padrao e o ponto T19 F4 L8 de cada cena."""
    raiz = Path(__file__).resolve().parent.parent
    import sys
    sys.path.insert(0, str(raiz / "scripts"))
    grid = _medidas(raiz)
    base = {cena: next(p for p in pts if (p["T"], p["F"], p["L"]) == PADRAO)
            for cena, pts in grid.items()}
    return grid, base


def rotulo(p):
    return f"T{p['T']} F{p['F']} L{p['L']}"


def fronteira_2d(pontos):
    """Nao dominados em (max PSNR, min VRAM)."""
    fr = []
    for p in pontos:
        dominado = any(q is not p and q["vram"] <= p["vram"] and q["psnr"] >= p["psnr"]
                       and (q["vram"] < p["vram"] or q["psnr"] > p["psnr"])
                       for q in pontos)
        if not dominado:
            fr.append(p)
    return sorted(fr, key=lambda p: p["vram"])


def nao_dominado_mensuravel(p, pontos):
    """Nenhuma outra configuracao e tao barata e MENSURAVELMENTE melhor."""
    return not any(q is not p and q["vram"] <= p["vram"] and q["psnr"] > p["psnr"] + RUIDO
                   for q in pontos)


def escada(pontos):
    restantes = sorted(pontos, key=lambda p: (p["vram"], -p["psnr"]))
    degraus = [restantes[0]]
    while True:
        atual = degraus[-1]
        melhores = [p for p in pontos if p["psnr"] > atual["psnr"] + RUIDO]
        if not melhores:
            break
        prox = min(melhores, key=lambda p: (p["vram"], -p["psnr"]))
        degraus.append(prox)
    return degraus


def podar(degraus):
    """Remove degraus dominados na pratica: se o degrau seguinte custa o mesmo
    (dentro do ruido de VRAM) e e mensuravelmente melhor, o atual nao e uma
    escolha racional -- "economizar" ali nao economiza nada mensuravel."""
    d = list(degraus)
    mudou = True
    while mudou:
        mudou = False
        for i in range(len(d) - 1):
            if d[i + 1]["vram"] - d[i]["vram"] <= RUIDO_VRAM:
                d.pop(i)
                mudou = True
                break
    return d


def equivalente_ao_padrao(pontos, base):
    """Mais barata que seja equivalente ou melhor em PSNR E mensuravelmente mais
    barata em VRAM. Sem isso, "substituto" seria so ruido de VRAM."""
    cand = [p for p in pontos if p["psnr"] >= base["psnr"] - RUIDO
            and p["vram"] < base["vram"] - RUIDO_VRAM]
    return min(cand, key=lambda p: (p["vram"], -p["psnr"])) if cand else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="runs/exp02_triagem/grid_corrigido.csv")
    ap.add_argument("--out-dir", default="runs/exp02_final")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    grid, base = carregar(args.grid)

    md = ["# Tabelas finais — exp02", "",
          f"Ruído de referência: **{RUIDO} dB** (maior amplitude entre execuções "
          "idênticas, `RELATORIO-exp02-validacoes.md` §2). VRAM = pico do processo "
          "descontada a linha de base (`vram_peak_mb`). `bonsai` a 5000 iterações: "
          "valores absolutos ~1 dB abaixo de 20 000, ordenação preservada "
          "(`RELATORIO-fechamento.md`, Etapa 2).", "",
          "Cada configuração é a **média de todas as medições a 5000 iterações** "
          "disponíveis (grid, baselines, validação de variância e reexecuções da "
          "triagem); `n` varia de 1 a 6. A execução anômala `garden/base_json/rep2` "
          "está excluída pelo critério declarado em `analise_variancia.py`. O padrão "
          "(`base.json`) é tratado como o ponto `T19 F4 L8`, que é o mesmo modelo.", ""]

    resumo_fig = {}
    for cena in sorted(grid):
        pts = grid[cena]
        fr = fronteira_2d(pts)
        ids_fr = {p["run_tag"] for p in fr}
        for p in pts:
            p["na_fronteira"] = p["run_tag"] in ids_fr
            p["nao_dominado_mensuravel"] = nao_dominado_mensuravel(p, pts)

        # --- tabela do grid ---------------------------------------------
        with (out / f"grid_{cena}.csv").open("w", newline="") as fh:
            campos = ["run_tag", "T", "F", "L", "n", "psnr", "psnr_amplitude",
                      "ssim", "lpips", "vram", "t_train", "na_fronteira",
                      "nao_dominado_mensuravel", "procedencia"]
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for p in sorted(pts, key=lambda p: p["vram"]):
                w.writerow(p)

        # --- escada ------------------------------------------------------
        completo = escada(pts)
        deg = podar(completo)
        podados = [p for p in completo if p not in deg]
        b = base[cena]
        eq = equivalente_ao_padrao(pts, b)
        with (out / f"guia_{cena}.csv").open("w", newline="") as fh:
            campos = ["degrau", "config", "n", "vram_mb", "psnr", "ssim", "lpips",
                      "t_train_s", "ganho_vs_anterior_db", "custo_vs_anterior_mb",
                      "mantido_no_guia"]
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            for i, p in enumerate(completo):
                ant = completo[i - 1] if i else None
                w.writerow({
                    "degrau": i + 1, "config": rotulo(p), "n": p["n"],
                    "vram_mb": round(p["vram"], 1),
                    "psnr": round(p["psnr"], 3), "ssim": round(p["ssim"], 4),
                    "lpips": None if p["lpips"] is None else round(p["lpips"], 4),
                    "t_train_s": round(p["t_train"], 1),
                    "ganho_vs_anterior_db": None if not ant else round(p["psnr"] - ant["psnr"], 3),
                    "custo_vs_anterior_mb": None if not ant else round(p["vram"] - ant["vram"], 1),
                    "mantido_no_guia": p in deg,
                })

        # --- markdown ----------------------------------------------------
        md += [f"## {cena}", "",
               f"Fronteira 2D (PSNR × VRAM): **{len(fr)}** de {len(pts)} configurações. "
               f"Não dominadas de forma mensurável (nenhuma outra tão barata e "
               f"> {RUIDO} dB melhor): **{sum(p['nao_dominado_mensuravel'] for p in pts)}**.",
               "", "### Guia por orçamento de VRAM", "",
               "Cada degrau é a configuração mais barata **mensuravelmente melhor** "
               f"(> {RUIDO} dB) que o anterior, e **mensuravelmente mais cara** "
               f"(> {RUIDO_VRAM:.0f} MB, o ruído de VRAM). Entre degraus, VRAM adicional "
               "não compra qualidade mensurável.",
               "", "| degrau | config | n | VRAM (MB) | PSNR | SSIM | LPIPS | treino (s) | ganho | custo |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for i, p in enumerate(deg):
            ant = deg[i - 1] if i else None
            g = "—" if not ant else f"+{p['psnr'] - ant['psnr']:.2f} dB"
            c = "—" if not ant else f"+{p['vram'] - ant['vram']:.0f} MB"
            lp = "—" if p["lpips"] is None else f"{p['lpips']:.3f}"
            md.append(f"| {i + 1} | `{rotulo(p)}` | {p['n']} | {p['vram']:.0f} | "
                      f"{p['psnr']:.2f} | {p['ssim']:.3f} | {lp} | {p['t_train']:.0f} | "
                      f"{g} | {c} |")
        if podados:
            faixa_lo = min(p["vram"] for p in podados)
            md += ["",
                   f"Removidos por custarem o mesmo que um degrau melhor (diferença de "
                   f"VRAM ≤ {RUIDO_VRAM:.0f} MB): "
                   + ", ".join(f"`{rotulo(p)}` ({p['psnr']:.2f} dB, {p['vram']:.0f} MB)"
                               for p in podados)
                   + f". Abaixo de ~{deg[0]['vram']:.0f} MB não há economia mensurável: "
                   f"a partir de {faixa_lo:.0f} MB o consumo é dominado pelas imagens de "
                   "treino e escolher a configuração mais fraca só perde qualidade."]

        md += ["", "### Configuração padrão e seu substituto", "",
               f"Padrão (`base.json`, T19 F4 L8, média de n={b['n']}): "
               f"**{b['psnr']:.2f} dB, {b['vram']:.0f} MB, {b['t_train']:.0f} s** de treino."]
        if not eq:
            md += ["", "Nenhuma configuração é ao mesmo tempo equivalente em PSNR "
                   f"(≥ padrão − {RUIDO} dB) e mensuravelmente mais barata "
                   f"(> {RUIDO_VRAM:.0f} MB a menos). **O padrão já está na borda "
                   "eficiente desta cena.**"]
        if eq:
            dv = eq["vram"] - b["vram"]
            dt = 100 * (eq["t_train"] - b["t_train"]) / b["t_train"]
            dp = eq["psnr"] - b["psnr"]
            md += ["",
                   f"Mais barata estatisticamente equivalente ou melhor (PSNR ≥ padrão − "
                   f"{RUIDO} dB): **`{rotulo(eq)}`** — {eq['psnr']:.2f} dB "
                   f"({dp:+.2f} dB, dentro do ruído), {eq['vram']:.0f} MB "
                   f"(**{dv:+.0f} MB**, {100 * dv / b['vram']:+.1f} %), treino "
                   f"{eq['t_train']:.0f} s ({dt:+.0f} %)."]
        topo = max(pts, key=lambda p: p["psnr"])
        md += ["",
               f"Maior PSNR do grid: `{rotulo(topo)}` — {topo['psnr']:.2f} dB, "
               f"{topo['vram']:.0f} MB, {topo['t_train']:.0f} s.", ""]

        resumo_fig[cena] = {"pts": pts, "fr": fr, "deg": deg, "base": b, "eq": eq}

    # --- baselines --------------------------------------------------------
    md += ["## Baselines (configuração padrão, `base.json`)", "",
           "| cena | n | PSNR | amplitude | SSIM | LPIPS | VRAM (MB) | treino (s) |",
           "|---|---|---|---|---|---|---|---|"]
    with (out / "baselines.csv").open("w", newline="") as fh:
        campos_b = ["scene", "n", "psnr", "psnr_amplitude", "ssim", "lpips", "vram",
                    "t_train", "procedencia"]
        w = csv.DictWriter(fh, fieldnames=campos_b)
        w.writeheader()
        for cena, b in sorted(base.items()):
            w.writerow({k: b[k] for k in campos_b if k != "scene"} | {"scene": cena})
            md.append(f"| {cena} | {b['n']} | {b['psnr']:.2f} | {b['psnr_amplitude']:.2f} | "
                      f"{b['ssim']:.3f} | {b['lpips']:.3f} | {b['vram']:.0f} | "
                      f"{b['t_train']:.0f} |")
    (out / "tabelas.md").write_text("\n".join(md) + "\n")

    # --- figura: fronteira com espessura ---------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cenas = sorted(resumo_fig)
    fig, axs = plt.subplots(1, len(cenas), figsize=(7.2 * len(cenas), 5.8))
    for ax, cena in zip(axs, cenas):
        d = resumo_fig[cena]
        pts, fr, deg, b, eq = d["pts"], d["fr"], d["deg"], d["base"], d["eq"]
        ax.scatter([p["vram"] for p in pts], [p["psnr"] for p in pts], s=26,
                   color="#9e9e9e", alpha=0.75, label="configurações do grid", zorder=2)
        fx = [p["vram"] for p in fr]
        fy = [p["psnr"] for p in fr]
        ax.step(fx, fy, where="post", color="#1f4e79", lw=1.8,
                label="fronteira de Pareto", zorder=3)
        ax.fill_between(fx, [y - RUIDO for y in fy], fy, step="post",
                        color="#1f4e79", alpha=0.15,
                        label=f"faixa de ruído (−{RUIDO} dB)", zorder=1)
        ax.plot([p["vram"] for p in deg], [p["psnr"] for p in deg], "o", ms=9,
                mfc="none", mec="#2e7d32", mew=2, label="degraus do guia", zorder=4)
        for i, p in enumerate(deg):
            ax.annotate(f"{i + 1}", xy=(p["vram"], p["psnr"]), xytext=(-12, 6),
                        textcoords="offset points", fontsize=8, color="#2e7d32",
                        weight="bold")
        ax.plot([b["vram"]], [b["psnr"]], "*", ms=16, color="#c00000",
                mec="black", label="padrão (base.json)", zorder=5)
        if eq:
            ax.annotate(f"equivalente ao padrão\n{rotulo(eq)}: "
                        f"{eq['vram'] - b['vram']:+.0f} MB",
                        xy=(eq["vram"], eq["psnr"]), xytext=(15, -38),
                        textcoords="offset points", fontsize=8,
                        arrowprops=dict(arrowstyle="->", color="#c00000"),
                        color="#c00000")
        ax.set_xlabel("pico de VRAM descontada a linha de base (MB)")
        ax.set_ylabel("PSNR no conjunto de teste (dB)")
        ax.set_title(f"{cena} — {len(fr)} na fronteira, "
                     f"{sum(p['nao_dominado_mensuravel'] for p in pts)} não dominadas "
                     f"de forma mensurável", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Fronteira de Pareto com espessura: diferenças menores que o ruído "
                 "não ordenam configurações", fontsize=11)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.10, wspace=0.18)
    fig.savefig(out / "pareto_espessura.png", dpi=150)
    fig.savefig(out / "pareto_espessura.pdf")
    plt.close(fig)

    print((out / "tabelas.md").read_text())
    print(f"saidas em {out}/")


if __name__ == "__main__":
    main()
