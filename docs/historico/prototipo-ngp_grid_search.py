#!/usr/bin/env python3
"""
Grid search de hiperparametros para o instant-ngp.

Uso tipico (a partir da raiz do repo instant-ngp):

    python ngp_grid_search.py \
        --scene data/nerf/fox \
        --test-transforms data/nerf/fox/transforms.json \
        --base-config configs/nerf/base.json \
        --n-steps 5000 \
        --out-dir runs/grid01

Cada combinacao vira um JSON de rede em <out-dir>/configs/, um log em
<out-dir>/logs/ e uma linha no CSV <out-dir>/results.csv (gravado de forma
incremental, entao dá pra interromper e retomar com --resume).

Para descobrir os caminhos validos de hiperparametro, rode com --show-base.
"""

import argparse
import copy
import csv
import itertools
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# O GRID. Chaves usam notacao pontuada seguindo a estrutura de configs/nerf/base.json.
# Comente/descomente linhas conforme o que voce quer varrer. Lembre que o custo
# e o produto cartesiano: 3 x 2 x 2 = 12 treinos.
# ---------------------------------------------------------------------------
GRID = {
    "encoding.log2_hashmap_size": [15, 17, 19],
    "encoding.n_levels": [4, 8, 16],
    "encoding.n_features_per_level": [2, 4, 8],
    # "encoding.base_resolution": [16, 32],
    # "encoding.per_level_scale": [1.38, 1.5],
    # "network.n_neurons": [32, 64],          # FullyFusedMLP aceita so 16/32/64/128
    # "network.n_hidden_layers": [1, 2, 3],
    # "rgb_network.n_neurons": [64],
    # "optimizer.nested.nested.learning_rate": [1e-2, 5e-3],
    # "loss.otype": ["Huber", "L2"],
}

PSNR_RE = re.compile(r"PSNR[=:\s]+([0-9]*\.?[0-9]+)", re.IGNORECASE)
SSIM_RE = re.compile(r"SSIM[=:\s]+([0-9]*\.?[0-9]+)", re.IGNORECASE)


def get_by_path(cfg, dotted):
    node = cfg
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    return node


def set_by_path(cfg, dotted, value):
    keys = dotted.split(".")
    node = cfg
    for key in keys[:-1]:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    if keys[-1] not in node:
        raise KeyError(dotted)
    node[keys[-1]] = value


def flatten_keys(cfg, prefix=""):
    """Lista todos os caminhos pontuados de um dict aninhado (para --show-base)."""
    out = []
    for key, value in cfg.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.extend(flatten_keys(value, path + "."))
        else:
            out.append((path, value))
    return out


def validate_grid(base_cfg, grid):
    bad = []
    for path in grid:
        try:
            get_by_path(base_cfg, path)
        except KeyError:
            bad.append(path)
    if bad:
        raise SystemExit(
            "Caminhos inexistentes no base-config: "
            + ", ".join(bad)
            + "\nRode com --show-base para ver os caminhos validos."
        )


def combinations(grid):
    keys = list(grid.keys())
    for values in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values))


def short_tag(combo):
    """Nome curto e legivel para a combinacao."""
    parts = []
    for path, value in combo.items():
        name = path.split(".")[-1]
        initials = "".join(w[0] for w in name.split("_"))
        parts.append(f"{initials}{value}")
    return "_".join(parts).replace(".", "p")


def run_one(args, combo, index, total, base_cfg, out_dir):
    tag = f"{index:03d}_{short_tag(combo)}"
    cfg_path = out_dir / "configs" / f"{tag}.json"
    log_path = out_dir / "logs" / f"{tag}.log"
    snap_path = out_dir / "snapshots" / f"{tag}.ingp"

    if args.resume and log_path.exists():
        text = log_path.read_text(errors="ignore")
        if PSNR_RE.search(text):
            print(f"[{index}/{total}] {tag}: ja existe, pulando (--resume)")
            return None

    cfg = copy.deepcopy(base_cfg)
    for path, value in combo.items():
        set_by_path(cfg, path, value)
    cfg_path.write_text(json.dumps(cfg, indent=2))

    cmd = [
        sys.executable, str(Path(args.ngp_root) / "scripts" / "run.py"),
        "--scene", args.scene,
        "--network", str(cfg_path),
        "--n_steps", str(args.n_steps),
    ]
    if args.test_transforms:
        cmd += ["--test_transforms", args.test_transforms]
    if args.save_snapshots:
        cmd += ["--save_snapshot", str(snap_path)]
    if args.extra_args:
        cmd += args.extra_args

    print(f"[{index}/{total}] {tag}: treinando...", flush=True)
    started = time.time()
    proc = subprocess.run(
        cmd, cwd=args.ngp_root, capture_output=True, text=True
    )
    elapsed = time.time() - started

    output = proc.stdout + "\n" + proc.stderr
    log_path.write_text(output)

    psnr_hits = PSNR_RE.findall(output)
    ssim_hits = SSIM_RE.findall(output)
    psnr = float(psnr_hits[-1]) if psnr_hits else None
    ssim = float(ssim_hits[-1]) if ssim_hits else None

    if proc.returncode != 0:
        print(f"    FALHOU (returncode={proc.returncode}) — veja {log_path}")
    elif psnr is None:
        print(f"    terminou sem PSNR (faltou --test-transforms?) — {log_path}")
    else:
        print(f"    PSNR={psnr:.3f}  ({elapsed:.0f}s)")

    row = {"tag": tag, "psnr": psnr, "ssim": ssim,
           "seconds": round(elapsed, 1), "returncode": proc.returncode}
    row.update({p: v for p, v in combo.items()})
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="pasta do dataset NeRF")
    ap.add_argument("--test-transforms", default=None,
                    help="transforms.json de teste; sem ele nao ha PSNR")
    ap.add_argument("--base-config", default="configs/nerf/base.json")
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--out-dir", default="runs/grid")
    ap.add_argument("--ngp-root", default=".", help="raiz do repo instant-ngp")
    ap.add_argument("--save-snapshots", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="pula combinacoes que ja tem log com PSNR")
    ap.add_argument("--dry-run", action="store_true",
                    help="so lista as combinacoes")
    ap.add_argument("--show-base", action="store_true",
                    help="imprime os caminhos do base-config e sai")
    ap.add_argument("--extra-args", nargs=argparse.REMAINDER, default=[],
                    help="argumentos extras repassados ao run.py")
    args = ap.parse_args()

    base_path = Path(args.ngp_root) / args.base_config
    if not base_path.exists():
        base_path = Path(args.base_config)
    base_cfg = json.loads(base_path.read_text())

    if args.show_base:
        for path, value in flatten_keys(base_cfg):
            print(f"{path} = {value!r}")
        return

    validate_grid(base_cfg, GRID)

    combos = list(combinations(GRID))
    total = len(combos)
    print(f"{total} combinacoes x {args.n_steps} steps\n")

    if args.dry_run:
        for i, combo in enumerate(combos, 1):
            print(f"{i:03d} {short_tag(combo)}: {combo}")
        return

    out_dir = Path(args.out_dir)
    for sub in ("configs", "logs", "snapshots"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "results.csv"
    fieldnames = (["tag", "psnr", "ssim", "seconds", "returncode"]
                  + list(GRID.keys()))
    write_header = not csv_path.exists()

    rows = []
    with csv_path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for i, combo in enumerate(combos, 1):
            row = run_one(args, combo, i, total, base_cfg, out_dir)
            if row is None:
                continue
            writer.writerow(row)
            fh.flush()          # resultado parcial sobrevive a um Ctrl+C
            rows.append(row)

    ok = [r for r in rows if r["psnr"] is not None]
    if ok:
        ok.sort(key=lambda r: r["psnr"], reverse=True)
        print("\nTop 5 por PSNR:")
        for r in ok[:5]:
            print(f"  {r['psnr']:.3f}  {r['tag']}")
    print(f"\nResultados em {csv_path}")


if __name__ == "__main__":
    main()