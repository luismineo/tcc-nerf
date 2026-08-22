#!/usr/bin/env python3
"""Analise de Fronteira de Pareto sobre o results.csv do grid search.

Consome o CSV canonico produzido pelo grid_runner.py e nao decide nada sobre a
execucao: e um segundo script, deliberadamente separado.

Objetivos: maximizar PSNR, minimizar vram_peak_mb, minimizar t_train_s.

Nao importa pyngp nem toca na GPU: roda em qualquer maquina com o CSV em maos.

    python3 scripts/pareto_analysis.py --csv runs/exp01/results.csv
    python3 scripts/pareto_analysis.py --csv runs/exp01/results.csv --out-dir runs/exp01/analise
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

# Objetivos: (coluna, sentido). -1 = maximizar, +1 = minimizar.
OBJECTIVES = [("psnr", -1), ("vram_peak_mb", 1), ("t_train_s", 1)]

# Limiar de degradacao aceitavel prometido na Secao 5 do TCC.
PSNR_TOLERANCE_DB = -2.0


def read_rows(csv_path):
    """Le o CSV e mantem, para cada run_tag, a ultima linha gravada.

    Uma run reexecutada apos --resume (por exemplo, um oom que virou ok) gera
    uma segunda linha com o mesmo run_tag; a mais recente e a que vale.
    """
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    latest = {}
    for row in rows:
        latest[row["run_tag"]] = row
    return list(latest.values()), len(rows)


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def prepare(rows):
    ok, dropped = [], []
    for row in rows:
        if row.get("status") != "ok":
            dropped.append(row)
            continue
        record = dict(row)
        for key in ["psnr", "psnr_std", "psnr_median", "ssim", "ssim_ngp", "lpips",
                    "loss_final", "vram_peak_mb", "vram_peak_device_mb", "vram_baseline_mb",
                    "t_train_s", "t_eval_s", "steps_per_s", "n_params"]:
            record[key] = to_float(row.get(key))
        for key in ["T", "F", "L", "batch_size", "seed", "n_steps"]:
            value = to_float(row.get(key))
            record[key] = int(value) if value is not None else None
        for key in ["per_level_scale", "n_rays_effective_mean", "samples_per_ray_mean"]:
            record[key] = to_float(row.get(key))
        record["is_baseline"] = str(row.get("is_baseline", "")).lower() in ("true", "1")
        record["kind"] = row.get("kind", "grid")
        if any(record[c] is None for c, _ in OBJECTIVES):
            dropped.append(row)
            continue
        ok.append(record)
    return ok, dropped


def pareto_front(records):
    """Conjunto nao dominado. a domina b se e melhor-ou-igual em tudo e
    estritamente melhor em pelo menos um objetivo."""
    if not records:
        return []
    costs = np.array([[r[c] * s for c, s in OBJECTIVES] for r in records], dtype=float)
    n = len(records)
    is_efficient = np.ones(n, dtype=bool)
    for i in range(n):
        if not is_efficient[i]:
            continue
        dominated = np.all(costs <= costs[i], axis=1) & np.any(costs < costs[i], axis=1)
        if dominated.any():
            is_efficient[i] = False
    return [r for r, keep in zip(records, is_efficient) if keep]


def pareto_front_2d(records, x_col="vram_peak_mb", y_col="psnr"):
    """Fronteira 2D: minimizar x, maximizar y. E a figura que vai para o texto."""
    pts = sorted(records, key=lambda r: (r[x_col], -r[y_col]))
    front, best_y = [], -float("inf")
    for r in pts:
        if r[y_col] > best_y:
            front.append(r)
            best_y = r[y_col]
    return front


def config_key(record):
    return (record["T"], record["F"], record["L"])


def degradation_table(records):
    """Δ em relacao ao baseline da mesma cena."""
    baselines = {r["scene"]: r for r in records if r["is_baseline"]}
    table = []
    for r in records:
        if r["is_baseline"]:
            continue
        base = baselines.get(r["scene"])
        if base is None:
            continue
        entry = {
            "run_tag": r["run_tag"], "scene": r["scene"],
            "T": r["T"], "F": r["F"], "L": r["L"],
            "psnr": r["psnr"], "vram_peak_mb": r["vram_peak_mb"], "t_train_s": r["t_train_s"],
            "delta_psnr_db": round(r["psnr"] - base["psnr"], 3),
            "delta_vram_pct": round(100.0 * (r["vram_peak_mb"] - base["vram_peak_mb"]) / base["vram_peak_mb"], 2)
            if base["vram_peak_mb"] else None,
            "delta_time_pct": round(100.0 * (r["t_train_s"] - base["t_train_s"]) / base["t_train_s"], 2)
            if base["t_train_s"] else None,
        }
        if r.get("lpips") is not None and base.get("lpips") is not None:
            entry["delta_lpips"] = round(r["lpips"] - base["lpips"], 5)
        entry["within_tolerance"] = entry["delta_psnr_db"] > PSNR_TOLERANCE_DB
        table.append(entry)
    return table


def coherence_check(table):
    """Configuracoes em que LPIPS e PSNR discordam de sinal.

    PSNR maior e melhor; LPIPS menor e melhor. Se uma configuracao melhora o
    PSNR e piora o LPIPS (ou vice-versa) em relacao ao baseline, ela merece
    aparecer na discussao sobre ruido de hash.
    """
    flagged = []
    for e in table:
        if "delta_lpips" not in e:
            continue
        psnr_better = e["delta_psnr_db"] > 0
        lpips_better = e["delta_lpips"] < 0
        if psnr_better != lpips_better:
            flagged.append(e)
    return flagged


def make_figures(records, fronts_2d, table, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib ausente: figuras nao geradas (o CSV da analise foi produzido normalmente).")
        print("  Para gerar: pip3 install matplotlib")
        return []

    written = []
    scenes = sorted({r["scene"] for r in records})

    # --- Figura principal: PSNR x VRAM, uma cor por cena ---------------------
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for idx, scene in enumerate(scenes):
        pts = [r for r in records if r["scene"] == scene and not r["is_baseline"]]
        ax.scatter([r["vram_peak_mb"] for r in pts], [r["psnr"] for r in pts],
                   s=26, alpha=0.55, color=colors[idx % len(colors)], label=f"{scene}")
        front = fronts_2d.get(scene, [])
        if front:
            ax.plot([r["vram_peak_mb"] for r in front], [r["psnr"] for r in front],
                    "-o", color=colors[idx % len(colors)], lw=2, ms=6,
                    label=f"{scene} — fronteira")
        base = [r for r in records if r["scene"] == scene and r["is_baseline"]]
        if base:
            ax.scatter([base[0]["vram_peak_mb"]], [base[0]["psnr"]], marker="*", s=260,
                       color=colors[idx % len(colors)], edgecolor="black", linewidth=0.6,
                       zorder=5, label=f"{scene} — baseline")
    ax.set_xlabel("Pico de VRAM (MB)")
    ax.set_ylabel("PSNR (dB)")
    ax.set_title("Fronteira de Pareto: qualidade visual x consumo de VRAM")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        path = out_dir / f"pareto_psnr_vram.{ext}"
        fig.savefig(path, dpi=300)
        written.append(path)
    plt.close(fig)

    # --- PSNR x tempo de treino ---------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 5))
    for idx, scene in enumerate(scenes):
        pts = [r for r in records if r["scene"] == scene and not r["is_baseline"]]
        ax.scatter([r["t_train_s"] for r in pts], [r["psnr"] for r in pts],
                   s=26, alpha=0.6, color=colors[idx % len(colors)], label=scene)
    ax.set_xlabel("Tempo de treino (s)")
    ax.set_ylabel("PSNR (dB)")
    ax.set_title("Qualidade x custo computacional")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        path = out_dir / f"pareto_psnr_tempo.{ext}"
        fig.savefig(path, dpi=300)
        written.append(path)
    plt.close(fig)

    # --- Degradacao em relacao ao baseline ----------------------------------
    if table:
        fig, ax = plt.subplots(figsize=(7, 5))
        for idx, scene in enumerate(scenes):
            pts = [e for e in table if e["scene"] == scene and e["delta_vram_pct"] is not None]
            ax.scatter([e["delta_vram_pct"] for e in pts], [e["delta_psnr_db"] for e in pts],
                       s=28, alpha=0.65, color=colors[idx % len(colors)], label=scene)
        ax.axhline(PSNR_TOLERANCE_DB, color="crimson", ls="--", lw=1.2,
                   label=f"tolerancia {PSNR_TOLERANCE_DB} dB")
        ax.axhline(0, color="gray", lw=0.8)
        ax.axvline(0, color="gray", lw=0.8)
        ax.set_xlabel("Variacao de VRAM em relacao ao baseline (%)")
        ax.set_ylabel("Variacao de PSNR (dB)")
        ax.set_title("Degradacao de qualidade x economia de memoria")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            path = out_dir / f"degradacao_baseline.{ext}"
            fig.savefig(path, dpi=300)
            written.append(path)
        plt.close(fig)

    return written


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="Fronteira de Pareto do grid search do Instant-NGP")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", default=None, help="padrao: ao lado do results.csv")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV nao encontrado: {csv_path}")
    out_dir = Path(args.out_dir) if args.out_dir else csv_path.parent / "analise"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_rows, n_lines = read_rows(csv_path)
    records, dropped = prepare(raw_rows)

    print(f"{n_lines} linhas no CSV, {len(raw_rows)} run_tags unicos, "
          f"{len(records)} utilizaveis, {len(dropped)} descartadas")
    if dropped:
        by_status = {}
        for row in dropped:
            by_status[row.get("status", "?")] = by_status.get(row.get("status", "?"), 0) + 1
        print("  descartadas por status:", by_status)
    if not records:
        raise SystemExit("Nenhuma run com status=ok e metricas completas.")

    # A varredura de B e variavel controlada, nao parte do grid: entra na sua
    # propria tabela e fica fora das fronteiras, para nao misturar um efeito de
    # orcamento de treino com os de capacidade do modelo.
    sweep_records = [r for r in records if r["kind"] == "batch_sweep"]
    grid_records = [r for r in records if not r["is_baseline"] and r["kind"] != "batch_sweep"]
    scenes = sorted({r["scene"] for r in records if r["kind"] != "batch_sweep"})

    # --- Fronteiras 3D por cena --------------------------------------------
    fronts, fronts_2d = {}, {}
    pareto_rows = []
    for scene in scenes:
        subset = [r for r in grid_records if r["scene"] == scene]
        front = pareto_front(subset)
        fronts[scene] = front
        fronts_2d[scene] = pareto_front_2d(subset)
        print(f"\nCena {scene}: {len(subset)} runs, {len(front)} nao dominadas (3D), "
              f"{len(fronts_2d[scene])} na fronteira 2D PSNR x VRAM")
        for r in sorted(front, key=lambda r: -r["psnr"]):
            pareto_rows.append({
                "scene": scene, "run_tag": r["run_tag"],
                "T": r["T"], "F": r["F"], "L": r["L"], "per_level_scale": r["per_level_scale"],
                "psnr": r["psnr"], "psnr_std": r["psnr_std"], "ssim": r["ssim"], "lpips": r["lpips"],
                "vram_peak_mb": r["vram_peak_mb"], "t_train_s": r["t_train_s"],
                "front": "3d",
                "on_2d_front": r in fronts_2d[scene],
            })
            print(f"   T={r['T']:2d} F={r['F']} L={r['L']:2d}  "
                  f"PSNR={r['psnr']:6.2f}  VRAM={r['vram_peak_mb']:7.1f} MB  "
                  f"t_train={r['t_train_s']:7.1f}s")

    # --- Intersecao entre cenas ---------------------------------------------
    if len(scenes) > 1:
        keys = [set(config_key(r) for r in fronts[s]) for s in scenes]
        common = set.intersection(*keys)
        print(f"\nConfiguracoes nao dominadas em TODAS as cenas ({len(common)}):")
        if common:
            for T, F, L in sorted(common):
                psnrs = {s: next(r["psnr"] for r in fronts[s] if config_key(r) == (T, F, L)) for s in scenes}
                detalhe = "  ".join(f"{s}={psnrs[s]:.2f}dB" for s in scenes)
                print(f"   T={T:2d} F={F} L={L:2d}   {detalhe}")
                pareto_rows.append({
                    "scene": "INTERSECAO", "run_tag": f"T{T}_F{F}_L{L}",
                    "T": T, "F": F, "L": L, "front": "intersecao",
                })
        else:
            print("   nenhuma — os dois perfis de cena pedem configuracoes diferentes,")
            print("   o que ja e um resultado para a Secao 4.5.")

    write_csv(out_dir / "pareto.csv", pareto_rows,
              ["scene", "run_tag", "T", "F", "L", "per_level_scale", "psnr", "psnr_std",
               "ssim", "lpips", "vram_peak_mb", "t_train_s", "front", "on_2d_front"])

    # --- Varredura de B, reportada em separado -------------------------------
    if sweep_records:
        print(f"\nVarredura de training_batch_size ({len(sweep_records)} runs, variavel controlada):")
        for r in sorted(sweep_records, key=lambda r: r["batch_size"]):
            print(f"   B={r['batch_size']:7d}  PSNR={r['psnr']:6.2f}  "
                  f"VRAM={r['vram_peak_mb']:7.1f} MB  t_train={r['t_train_s']:7.1f}s  "
                  f"raios={r['n_rays_effective_mean']}")
        print("   Lembrete: com n_steps fixo, B menor = mesmo modelo treinado com")
        print("   menos amostras. A diferenca de PSNR e de orcamento, nao de capacidade.")
        write_csv(out_dir / "varredura_batch.csv", sweep_records,
                  ["run_tag", "scene", "T", "F", "L", "batch_size", "psnr", "ssim", "lpips",
                   "vram_peak_mb", "t_train_s", "steps_per_s", "n_rays_effective_mean",
                   "samples_per_ray_mean"])

    # --- Degradacao vs baseline ---------------------------------------------
    table = degradation_table([r for r in records if r["kind"] != "batch_sweep"])
    if table:
        write_csv(out_dir / "degradacao_baseline.csv", table,
                  ["run_tag", "scene", "T", "F", "L", "psnr", "vram_peak_mb",
                   "t_train_s", "delta_psnr_db", "delta_vram_pct", "delta_time_pct",
                   "delta_lpips", "within_tolerance"])
        dentro = [e for e in table if e["within_tolerance"]]
        print(f"\nDegradacao vs baseline: {len(dentro)}/{len(table)} runs com "
              f"delta_PSNR > {PSNR_TOLERANCE_DB} dB")
        economicas = sorted(
            (e for e in dentro if e["delta_vram_pct"] is not None),
            key=lambda e: e["delta_vram_pct"],
        )[:5]
        if economicas:
            print("  Maior economia de VRAM dentro da tolerancia:")
            for e in economicas:
                print(f"   {e['run_tag']:34s} dPSNR={e['delta_psnr_db']:+6.2f} dB  "
                      f"dVRAM={e['delta_vram_pct']:+7.2f}%  dTempo={e['delta_time_pct']:+7.2f}%")
    else:
        print("\nSem baseline no CSV: tabela de degradacao nao gerada.")

    # --- Coerencia LPIPS x PSNR ---------------------------------------------
    flagged = coherence_check(table)
    if flagged:
        print(f"\nConfiguracoes em que LPIPS e PSNR discordam de sinal ({len(flagged)}):")
        for e in flagged[:10]:
            print(f"   {e['run_tag']:34s} dPSNR={e['delta_psnr_db']:+6.2f} dB  "
                  f"dLPIPS={e['delta_lpips']:+.5f}")
        write_csv(out_dir / "incoerencias_lpips_psnr.csv", flagged,
                  ["run_tag", "scene", "T", "F", "L", "delta_psnr_db", "delta_lpips"])
    elif any("delta_lpips" in e for e in table):
        print("\nLPIPS e PSNR concordam de sinal em todas as configuracoes.")

    figures = make_figures(records, fronts_2d, table, out_dir)

    summary = {
        "csv": str(csv_path),
        "n_rows": n_lines,
        "n_unique_runs": len(raw_rows),
        "n_usable": len(records),
        "scenes": scenes,
        "front_sizes": {s: len(fronts[s]) for s in scenes},
        "psnr_tolerance_db": PSNR_TOLERANCE_DB,
        "n_within_tolerance": sum(1 for e in table if e["within_tolerance"]),
        "n_lpips_psnr_disagreements": len(flagged),
        "figures": [str(p.name) for p in figures],
    }
    (out_dir / "resumo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\nSaidas em {out_dir}")
    for name in ["pareto.csv", "degradacao_baseline.csv", "incoerencias_lpips_psnr.csv", "resumo.json"]:
        if (out_dir / name).exists():
            print(f"  {name}")
    for path in figures:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
