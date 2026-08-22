#!/usr/bin/env python3
"""Envelope de viabilidade: onde o grid atravessa a fronteira de VRAM.

A calibracao de resolucao (calib_resolucao.py) responde "esta resolucao cabe na
configuracao mais pesada do grid?". Essa pergunta serve para planejar o grid,
mas nao e a pergunta do trabalho. O trabalho e sobre otimizar hiperparametros
para viabilizar treino pesado em GPU limitada, entao a resolucao interessante
nao e a folgada: e aquela onde parte das configuracoes cabe e parte nao cabe.

O consumo de VRAM se divide em duas parcelas:

  - piso independente de configuracao: as imagens de treino na VRAM. T, F e L
    nao mexem nisso.
  - parcela dependente de configuracao: tabela de hash, gradientes e estado do
    Adam. E so essa que os hiperparametros controlam.

Dai as tres leituras possiveis por resolucao:

  leve estoura            -> PAREDE. O piso ja nao cabe; nenhum hiperparametro
                             resgata. Descartar a resolucao.
  leve cabe, pesada nao   -> FRONTEIRA. O ponto de operacao que o trabalho
                             procura: o grid atravessa a viabilidade.
  leve e pesada cabem     -> SEM TENSAO. A VRAM nao restringe, e a Fronteira de
                             Pareto degenera num ranking de qualidade.

Protocolo de avaliacao igual ao do grid (spp=8, test-stride 4). Medido antes de
fixar isso: em garden f8 o pico foi 3902.5 MB com spp=8 contra 3916.2 MB com
spp=1, ou seja, o protocolo pesado nao custa VRAM. Mas o PSNR foi 21.66 com 47
vistas contra 19.84 com 3, entao a avaliacao leve nao serve para qualidade.

    python3 scripts/envelope_viabilidade.py
    python3 scripts/envelope_viabilidade.py --targets garden:2 --n-steps 5000
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import grid_runner as gr  # noqa: E402
from calib_resolucao import acquire_lock, resolucao, scene_json  # noqa: E402

# Extremos e centro do GRID de grid_runner.py. T, F e L crescem juntos, entao a
# ordem abaixo e monotonica em numero de parametros: se uma estoura, as
# seguintes tambem estouram, e da para parar cedo.
CONFIGS = [
    ("leve", 15, 2, 4),
    ("mediana", 17, 4, 8),
    ("pesada", 19, 8, 16),
]

CSV_FIELDS = [
    "scene", "factor", "resolucao", "config", "T", "F", "L",
    "n_train_images", "status", "vram_peak_device_mb", "vram_livre_mb",
    "vram_peak_mb", "vram_baseline_mb", "vram_at_failure_mb",
    "n_params", "n_encoding_params", "psnr", "psnr_median", "ssim",
    "test_views", "steps_per_s", "t_setup_s", "t_train_s", "t_eval_s",
    "t_total_s", "error",
]

VRAM_TOTAL_MB = 6144


def parse_target(text):
    scene, _, factor = text.partition(":")
    if not factor:
        sys.exit(f"alvo invalido: {text!r} (esperado cena:fator, ex. garden:2)")
    return scene, int(factor)


def build_network(exp_dir, name, T, F, L):
    base_cfg = json.loads(
        (PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json").read_text()
    )
    gr.validate_grid(base_cfg)
    path = exp_dir / f"network_{name}_T{T}_F{F}_L{L}.json"
    gr.write_network_json({"T": T, "F": F, "L": L, "is_baseline": False}, base_cfg, path)
    return path


def run_one(scene, factor, cfg_name, T, F, L, network, args):
    sj = scene_json(scene, factor)
    if not sj.exists():
        return {"scene": scene, "factor": factor, "config": cfg_name,
                "status": "sem_json", "error": f"{sj} nao existe"}

    out_dir = PROJECT_ROOT / "runs" / args.exp_id / f"{scene}_f{factor}_{cfg_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    res = resolucao(sj)

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "ngp_worker.py"),
        "--scene", str(sj),
        "--test-transforms", str(sj),
        "--network", str(network),
        "--out-dir", str(out_dir),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(gr.FIXED_BATCH_SIZE),
        "--seed", "0",
        "--test-stride", str(args.test_stride),
        "--spp", str(args.spp),
        "--lpips-device", args.lpips_device,
        "--no-nerf-compatibility",
    ]

    print(f"\n--- {scene} f{factor} ({res}) | {cfg_name} T={T} F={F} L={L} ---", flush=True)
    t0 = time.perf_counter()
    log_path = out_dir / "worker.log"
    try:
        with log_path.open("w") as log:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                    stdout=log, stderr=subprocess.STDOUT)
            proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"[env] timeout de {args.timeout}s, enviando SIGTERM", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    t_total = time.perf_counter() - t0

    mp = out_dir / "metrics.json"
    if not mp.exists():
        return {"scene": scene, "factor": factor, "resolucao": res, "config": cfg_name,
                "T": T, "F": F, "L": L, "status": "sem_metrics",
                "t_total_s": round(t_total, 1),
                "error": "worker morreu sem gravar metrics.json"}

    m = json.loads(mp.read_text())
    row = {k: m.get(k) for k in CSV_FIELDS if k in m}
    pdev = m.get("vram_peak_device_mb")
    row.update({
        "scene": scene, "factor": factor, "resolucao": res, "config": cfg_name,
        "T": T, "F": F, "L": L, "t_total_s": round(t_total, 1),
        "vram_livre_mb": None if pdev is None else round(VRAM_TOTAL_MB - pdev, 1),
    })
    if m.get("status") == "ok":
        row["error"] = ""
    return row


def classificar(rows_alvo):
    """Traduz os status de um alvo em parede / fronteira / sem tensao."""
    por_cfg = {r["config"]: r.get("status") for r in rows_alvo}
    leve = por_cfg.get("leve")
    pesada = por_cfg.get("pesada")
    if leve in ("oom", "sem_metrics"):
        return "PAREDE", "nem a config mais leve cabe; nenhum hiperparametro resgata"
    if pesada == "ok":
        return "SEM TENSAO", "as 27 combinacoes cabem; a VRAM nao restringe"
    if leve == "ok" and pesada in ("oom", "sem_metrics", None):
        cabem = [c for c, s in por_cfg.items() if s == "ok"]
        return "FRONTEIRA", f"cabem: {', '.join(cabem)}; a pesada estoura"
    return "INDEFINIDO", f"status: {por_cfg}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="+", default=["garden:2", "bonsai:2", "bonsai:1"],
                    help="cena:fator, ex. garden:2 bonsai:1")
    ap.add_argument("--n-steps", type=int, default=5000,
                    help="igual ao grid: uma config que cabe em 1000 passos pode "
                         "estourar em 5000 conforme o grid de densidade popula")
    ap.add_argument("--test-stride", type=int, default=4)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--lpips-device", default="none", choices=["cpu", "cuda", "none"])
    ap.add_argument("--timeout", type=int, default=10800)
    ap.add_argument("--exp-id", default="etapa1_envelope")
    args = ap.parse_args()

    targets = [parse_target(t) for t in args.targets]
    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    networks = {name: build_network(exp_dir, name, T, F, L)
                for name, T, F, L in CONFIGS}
    print("configuracoes do envelope:")
    for name, T, F, L in CONFIGS:
        cfg = json.loads(networks[name].read_text())
        print(f"  {name:8} T={T:<3} F={F:<2} L={L:<3} "
              f"per_level_scale={cfg['encoding']['per_level_scale']}")
    print(f"protocolo: {args.n_steps} passos, spp={args.spp}, "
          f"test-stride={args.test_stride}, B={gr.FIXED_BATCH_SIZE}")

    rows = []
    veredito = {}
    for scene, factor in targets:
        do_alvo = []
        for name, T, F, L in CONFIGS:
            row = run_one(scene, factor, name, T, F, L, networks[name], args)
            rows.append(row)
            do_alvo.append(row)
            st = row.get("status")
            print(f"[env] {scene} f{factor} {name}: status={st} "
                  f"peak_dev={row.get('vram_peak_device_mb')} "
                  f"livre={row.get('vram_livre_mb')} psnr={row.get('psnr')}", flush=True)
            if st in ("oom", "sem_metrics"):
                # T, F e L crescem juntos: se esta estourou, as seguintes tambem.
                restantes = [c[0] for c in CONFIGS[CONFIGS.index((name, T, F, L)) + 1:]]
                for c in restantes:
                    rows.append({"scene": scene, "factor": factor, "config": c,
                                 "status": "pulado",
                                 "error": f"config {name} ja estourou"})
                if restantes:
                    print(f"[env] {scene} f{factor}: pulando {restantes}", flush=True)
                break
        veredito[(scene, factor)] = classificar(do_alvo)

    csv_path = exp_dir / "envelope.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    def f(v, nd=1):
        if v is None or v == "":
            return "-"
        return f"{v:.{nd}f}" if isinstance(v, float) else str(v)

    print("\n" + "=" * 100)
    print(f"ENVELOPE DE VIABILIDADE   ({args.n_steps} passos, spp={args.spp}, "
          f"stride={args.test_stride}, {VRAM_TOTAL_MB} MiB)")
    print("=" * 100)
    print(f"{'cena':8} {'fator':6} {'resolucao':12} {'config':9} {'status':8} "
          f"{'peak_dev':10} {'livre':9} {'enc_par':11} {'psnr':7} {'ssim':7}")
    print("-" * 100)
    for r in rows:
        print(f"{f(r.get('scene')):8} {('f' + str(r.get('factor'))):6} "
              f"{f(r.get('resolucao')):12} {f(r.get('config')):9} {f(r.get('status')):8} "
              f"{f(r.get('vram_peak_device_mb')):10} {f(r.get('vram_livre_mb')):9} "
              f"{f(r.get('n_encoding_params')):11} {f(r.get('psnr'), 2):7} "
              f"{f(r.get('ssim'), 4):7}")
    print("-" * 100)
    print("\nVEREDITO POR RESOLUCAO")
    for (scene, factor), (verd, motivo) in veredito.items():
        print(f"  {scene} f{factor}: {verd} - {motivo}")
    print(f"\ncsv -> {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
