#!/usr/bin/env python3
"""Figura de decisao do numero de iteracoes (Etapa 1.5).

A curva de convergencia bruta mostra que o PSNR estabiliza, mas nao torna
legivel a pergunta que decide: quanto custa cada decibel a mais, no grid
inteiro. Esta figura separa as duas coisas.

Quatro paineis:
  (a) loss por iteracao, com os marcos;
  (b) PSNR e SSIM em vistas retidas, com a assintota e a linha de 99%;
  (c) ganho marginal em dB por 1000 iteracoes, contra o limiar adotado;
  (d) custo do grid completo em horas contra o ganho acumulado em dB.

O painel (d) e o argumento: ele poe as duas grandezas que competem no mesmo
grafico, em unidades que a banca entende (horas de GPU e decibeis).

    python3 scripts/justificativa_iteracoes.py \
        --run-dir runs/etapa15_final/garden_f2 \
        --metrics-ref runs/etapa1_envelope_f2/garden_f2_mediana/metrics.json
"""

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ler_curvas(run_dir):
    conv = json.loads((run_dir / "convergencia.json").read_text())
    loss = [(int(s), float(v), float(t)) for s, v, t in conv["loss_hist"]]
    psnr = []
    for linha in conv["psnr_hist"]:
        passo, media, mediana, t = linha[0], linha[1], linha[2], linha[3]
        ssim = linha[4] if len(linha) > 4 else None
        psnr.append((int(passo), float(media), float(mediana), float(t), ssim))
    return conv, loss, psnr


def tempo_eval(caminho, padrao):
    """Tempo de avaliacao por execucao, medido, para converter em custo de grid."""
    if not caminho:
        return padrao, "padrao"
    try:
        m = json.loads(Path(caminho).read_text())
        v = m.get("t_eval_s")
        if v:
            return float(v), str(caminho)
    except Exception:
        pass
    return padrao, "padrao (leitura falhou)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--metrics-ref", default=None,
                    help="metrics.json de onde tirar o t_eval_s medido")
    ap.add_argument("--t-eval-s", type=float, default=85.0,
                    help="usado se --metrics-ref nao trouxer o valor")
    ap.add_argument("--t-setup-s", type=float, default=12.0)
    ap.add_argument("--n-runs", type=int, default=27,
                    help="combinacoes do grid (T x F x L)")
    ap.add_argument("--limiar-db-1k", type=float, default=0.1)
    ap.add_argument("--escolhido", type=int, default=5000)
    ap.add_argument("--rotulo", default="garden f2 (2594x1681), aabb_scale=4")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    conv, loss, psnr = ler_curvas(run_dir)
    t_eval, origem_eval = tempo_eval(args.metrics_ref, args.t_eval_s)

    psnr_final = psnr[-1][1]
    ssim_final = psnr[-1][4]

    # --- tabela derivada -------------------------------------------------
    linhas = []
    for i, (passo, media, mediana, t_treino, ssim) in enumerate(psnr):
        if i == 0:
            ganho = None
        else:
            p0, v0 = psnr[i - 1][0], psnr[i - 1][1]
            ganho = (media - v0) / (passo - p0) * 1000.0
        # custo do grid inteiro se o orcamento fosse este numero de iteracoes
        seg_por_run = t_treino + t_eval + args.t_setup_s
        linhas.append({
            "step": passo,
            "psnr": round(media, 4),
            "psnr_median": round(mediana, 4),
            "ssim": None if ssim is None else round(ssim, 5),
            "t_train_s": round(t_treino, 2),
            "ganho_db_por_1k": None if ganho is None else round(ganho, 4),
            "pct_do_psnr_final": round(100.0 * media / psnr_final, 2),
            "delta_db_ate_o_fim": round(psnr_final - media, 4),
            "s_por_run": round(seg_por_run, 1),
            "horas_grid": round(seg_por_run * args.n_runs / 3600.0, 2),
        })

    csv_path = run_dir / "justificativa_iteracoes.csv"
    campos = list(linhas[0].keys())
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for l in linhas:
            w.writerow(l)

    # --- figura ----------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(2, 2, figsize=(13, 8.5))
    (a, b), (c, d) = axs

    esc = args.escolhido

    # (a) loss
    a.plot([x[0] for x in loss], [x[1] for x in loss], lw=1.0, color="#1f4e79")
    a.set_yscale("log")
    a.set_ylabel("loss de treino (log)")
    a.set_xlabel("iteracao")
    a.set_title("(a) loss por iteracao", fontsize=10, loc="left")
    a.grid(alpha=0.3, which="both")
    a.axvline(esc, color="#c00000", ls="--", lw=1.4)

    # (b) PSNR + SSIM
    xs = [l["step"] for l in linhas]
    ys = [l["psnr"] for l in linhas]
    b.plot(xs, ys, marker="o", ms=4, lw=1.6, color="#2e7d32", label="PSNR (retido)")
    b.axhline(psnr_final, color="grey", ls="-", lw=1.0, alpha=0.7)
    b.axhline(psnr_final * 0.99, color="grey", ls=":", lw=1.2)
    b.annotate(f"99% de {psnr_final:.2f} dB", xy=(xs[len(xs) // 2], psnr_final * 0.99),
               xytext=(0, -13), textcoords="offset points", fontsize=8, color="grey")
    b.set_ylabel("PSNR (dB)", color="#2e7d32")
    b.set_xlabel("iteracao")
    b.set_title("(b) qualidade em vistas retidas", fontsize=10, loc="left")
    b.grid(alpha=0.3)
    b.axvline(esc, color="#c00000", ls="--", lw=1.4)
    if any(l["ssim"] is not None for l in linhas):
        bs = b.twinx()
        bs.plot(xs, [l["ssim"] for l in linhas], marker="s", ms=3.5, lw=1.2,
                ls=":", color="#8e24aa", label="SSIM")
        bs.set_ylabel("SSIM", color="#8e24aa")
        ls_ = b.get_lines()[:1] + bs.get_lines()
        b.legend(ls_, [x.get_label() for x in ls_], loc="lower right", fontsize=8)

    # (c) ganho marginal
    gx = [l["step"] for l in linhas if l["ganho_db_por_1k"] is not None]
    gy = [l["ganho_db_por_1k"] for l in linhas if l["ganho_db_por_1k"] is not None]
    c.plot(gx, gy, marker="o", ms=4, lw=1.6, color="#e07b00")
    c.axhline(args.limiar_db_1k, color="black", ls="--", lw=1.3)
    c.annotate(f"limiar adotado: {args.limiar_db_1k} dB / 1000 it",
               xy=(gx[len(gx) // 2], args.limiar_db_1k), xytext=(0, 6),
               textcoords="offset points", fontsize=8)
    c.set_ylabel("ganho marginal (dB por 1000 it)")
    c.set_xlabel("iteracao")
    c.set_title("(c) ganho marginal contra o limiar", fontsize=10, loc="left")
    c.grid(alpha=0.3)
    c.axvline(esc, color="#c00000", ls="--", lw=1.4)

    # (d) custo do grid x ganho -- o painel que decide
    horas = [l["horas_grid"] for l in linhas]
    d.plot(horas, ys, marker="o", ms=5, lw=1.8, color="#1f4e79")
    for l, h, y in zip(linhas, horas, ys):
        if l["step"] in (2000, esc, 10000, 20000, 30000):
            d.annotate(f"{l['step']}", xy=(h, y), xytext=(5, -10),
                       textcoords="offset points", fontsize=9, weight="bold")
    # O valor escolhido nao precisa coincidir com um checkpoint: o PSNR foi
    # amostrado a cada --psnr-every passos. Ancorar no ponto MEDIDO mais
    # proximo e dizer qual foi, em vez de interpolar em silencio.
    sel = min(linhas, key=lambda l: abs(l["step"] - esc))
    exato = sel["step"] == esc
    if sel:
        d.plot([sel["horas_grid"]], [sel["psnr"]], marker="o", ms=13,
               mfc="none", mec="#c00000", mew=2.2)
        ult = linhas[-1]
        nota = "" if exato else f"\n(ponto medido mais proximo de {esc})"
        d.annotate(
            f"de {sel['step']} a {ult['step']} it:\n"
            f"+{ult['psnr'] - sel['psnr']:.2f} dB por "
            f"+{ult['horas_grid'] - sel['horas_grid']:.1f} h de GPU{nota}",
            xy=(sel["horas_grid"], sel["psnr"]), xytext=(26, -58),
            textcoords="offset points", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4", fc="#fff6cc", ec="#c00000"),
            arrowprops=dict(arrowstyle="->", color="#c00000"))
    d.set_xlabel(f"custo do grid completo ({args.n_runs} execucoes), em horas")
    d.set_ylabel("PSNR (dB)")
    d.set_title("(d) o que cada hora de GPU compra", fontsize=10, loc="left")
    d.grid(alpha=0.3)

    fig.suptitle(
        f"Escolha do numero de iteracoes — {args.rotulo}\n"
        f"vermelho tracejado: {esc} iteracoes (escolhido) | "
        f"custo por execucao = treino + {t_eval:.0f}s aval + {args.t_setup_s:.0f}s setup",
        fontsize=11)
    fig.subplots_adjust(left=0.07, right=0.93, top=0.87, bottom=0.08,
                        hspace=0.32, wspace=0.30)
    png_path = run_dir / "justificativa_iteracoes.png"
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    # --- resumo ----------------------------------------------------------
    print(f"t_eval_s usado: {t_eval:.1f}s  (fonte: {origem_eval})")
    print(f"\n{'passo':>7} {'PSNR':>8} {'SSIM':>8} {'dB/1000it':>11} "
          f"{'% do final':>11} {'falta dB':>9} {'grid (h)':>9}")
    print("-" * 70)
    for l in linhas:
        g = "-" if l["ganho_db_por_1k"] is None else f"{l['ganho_db_por_1k']:.4f}"
        s = "-" if l["ssim"] is None else f"{l['ssim']:.4f}"
        print(f"{l['step']:>7} {l['psnr']:>8.3f} {s:>8} {g:>11} "
              f"{l['pct_do_psnr_final']:>10.2f}% {l['delta_db_ate_o_fim']:>9.3f} "
              f"{l['horas_grid']:>9.2f}")
    print("-" * 70)
    if sel:
        ult = linhas[-1]
        if not exato:
            print(f"\nATENCAO: {esc} nao e um checkpoint medido "
                  f"(amostragem a cada {linhas[1]['step'] - linhas[0]['step']} passos). "
                  f"Ancorado em {sel['step']}.")
        print(f"ancora {sel['step']}: {sel['psnr']:.3f} dB, "
              f"{sel['pct_do_psnr_final']:.2f}% do final, grid em {sel['horas_grid']:.2f} h")
        print(f"ir ate {ult['step']}: +{ult['psnr'] - sel['psnr']:.3f} dB por "
              f"+{ult['horas_grid'] - sel['horas_grid']:.2f} h "
              f"({ult['horas_grid'] / max(sel['horas_grid'], 1e-9):.1f}x o custo)")
    print(f"\ncsv     -> {csv_path}")
    print(f"grafico -> {png_path}")


if __name__ == "__main__":
    main()
