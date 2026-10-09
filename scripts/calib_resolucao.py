#!/usr/bin/env python3
"""Etapa 1 do experimento: calibracao de resolucao.

Para cada cena e cada fator de reducao, roda um treino curto pelo ngp_worker.py
e registra o pico de VRAM. O objetivo nao e qualidade, e achar em qual resolucao
cada cena passa a pressionar os 6 GB da RTX 2060.

A configuracao de rede e o PIOR CASO do grid (T=19, F=8, L=16, B=262144): se uma
resolucao couber aqui, as outras 26 combinacoes do grid tambem cabem.

Os fatores sao varridos do mais leve para o mais pesado. Quando uma cena estoura
a VRAM, os fatores mais pesados dela sao pulados (ja se sabe que estouram).

    python3 scripts/calib_resolucao.py
    python3 scripts/calib_resolucao.py --scenes garden --factors 4 2
"""

import argparse
import csv
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import grid_runner as gr  # noqa: E402

# Pior caso do grid definido em grid_runner.GRID.
CALIB_T, CALIB_F, CALIB_L = 19, 8, 16

CSV_FIELDS = [
    "scene", "factor", "resolucao", "n_train_images", "status",
    "vram_peak_mb", "vram_baseline_mb", "vram_peak_device_mb", "vram_at_failure_mb",
    "vram_method", "n_params", "n_encoding_params", "steps_per_s",
    "t_setup_s", "t_total_s", "error",
]


def acquire_lock(lock_path):
    """Trava exclusiva: duas calibracoes ao mesmo tempo destroem a medida.

    Duas execucoes concorrentes disputam a mesma GPU, entao cada uma le como
    'baseline' a VRAM que a outra ja alocou e grava no mesmo out-dir. O
    resultado nao e ruidoso, e sem sentido: da para ver f8 medindo mais que f4.
    Falhar aqui e barato; descobrir depois custa a varredura inteira.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # "a+", nunca "w": o modo "w" trunca no open, ou seja, ANTES de descobrir se
    # a trava foi obtida. O perdedor da corrida apagaria o pid do vencedor e a
    # mensagem de erro sairia sem dizer quem esta segurando a trava.
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        previous = ""
        try:
            fh.seek(0)
            previous = fh.read().strip()
        except OSError:
            pass
        sys.exit(
            f"ABORTADO: ja existe uma calibracao rodando ({previous or 'pid desconhecido'}).\n"
            f"Trava: {lock_path}\n"
            "Espere ela terminar ou mate o processo antes de comecar outra: "
            "medir VRAM com duas runs na mesma GPU nao produz numero aproveitavel."
        )
    fh.seek(0)
    fh.truncate()
    fh.write(f"pid={os.getpid()} inicio={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    fh.flush()
    return fh  # mantido aberto: a trava cai quando o processo morre


def scene_json(scene, factor):
    sd = PROJECT_ROOT / "data" / "mip_nerf" / scene
    return sd / ("transforms.json" if factor == 1 else f"transforms_f{factor}.json")


def resolucao(path):
    d = json.loads(Path(path).read_text())
    return f"{int(d['w'])}x{int(d['h'])}"


def build_network(out_path, aabb_scale=1):
    base_cfg = json.loads(
        (PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json").read_text()
    )
    gr.validate_grid(base_cfg)
    # aabb_scale exigido pelo write_network_json desde que o per_level_scale
    # passou a ser derivado por cena (N_max = 2048 * aabb_scale).
    run = {"T": CALIB_T, "F": CALIB_F, "L": CALIB_L, "is_baseline": False,
           "aabb_scale": aabb_scale}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gr.write_network_json(run, base_cfg, out_path)
    cfg = json.loads(out_path.read_text())
    print(f"rede de calibracao (pior caso do grid) -> {out_path}")
    print(f"  T={CALIB_T}  F={CALIB_F}  L={CALIB_L}  "
          f"per_level_scale={cfg['encoding']['per_level_scale']}  B={gr.FIXED_BATCH_SIZE}")
    return out_path


def run_one(scene, factor, network, args):
    sj = scene_json(scene, factor)
    if not sj.exists():
        return {"scene": scene, "factor": factor, "status": "sem_json",
                "error": f"{sj} nao existe"}

    out_dir = PROJECT_ROOT / "runs" / args.exp_id / f"{scene}_f{factor}"
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
        # Cenas reais 360 e sem fundo branco: o bloco nerf_compatibility zera o
        # cone_angle_constant, que e justamente o que torna viavel marchar por
        # uma cena ilimitada com aabb_scale=16. Ligado, o numero de amostras por
        # raio explode e a medida de VRAM deixa de representar o uso real.
        "--no-nerf-compatibility",
    ]

    print(f"\n--- {scene} f{factor} ({res}) ---", flush=True)
    t0 = time.perf_counter()
    # O instant-ngp escreve barras de progresso com \r sem parar; em log isso
    # vira megabytes de lixo. Vai tudo para worker.log e so o rabo aparece se
    # a run falhar.
    log_path = out_dir / "worker.log"
    try:
        with log_path.open("w") as log:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                    stdout=log, stderr=subprocess.STDOUT)
            proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"[calib] timeout de {args.timeout}s, enviando SIGTERM", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    t_total = time.perf_counter() - t0

    mp = out_dir / "metrics.json"
    if not mp.exists():
        return {"scene": scene, "factor": factor, "resolucao": res,
                "status": "sem_metrics", "t_total_s": round(t_total, 1),
                "error": "worker morreu sem gravar metrics.json (provavel SIGKILL/OOM do host)"}

    m = json.loads(mp.read_text())
    row = {k: m.get(k) for k in CSV_FIELDS if k in m}
    row.update({"scene": scene, "factor": factor, "resolucao": res,
                "t_total_s": round(t_total, 1)})
    # O worker inicializa metrics["error"] pessimista e so o sobrescreve quando
    # de fato falha; numa run ok o texto antigo continua la. Nao propaga.
    if m.get("status") == "ok":
        row["error"] = ""
    return row


def fmt(v, width, nd=0):
    if v is None or v == "":
        return "-".ljust(width)
    if isinstance(v, float):
        return f"{v:.{nd}f}".ljust(width)
    return str(v).ljust(width)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", nargs="+", default=["garden", "bonsai"])
    ap.add_argument("--factors", nargs="+", type=int, default=[8, 4, 2, 1],
                    help="varridos nesta ordem, do mais leve para o mais pesado")
    ap.add_argument("--n-steps", type=int, default=1000)
    ap.add_argument("--test-stride", type=int, default=64,
                    help="stride alto de proposito: a Etapa 1 mede VRAM, nao qualidade")
    ap.add_argument("--spp", type=int, default=1,
                    help="1 na sondagem inicial; 8 para reproduzir o protocolo do grid")
    ap.add_argument("--lpips-device", default="none", choices=["cpu", "cuda", "none"],
                    help="'none' por padrao: o torch instalado e build +cpu, entao o "
                         "LPIPS nunca toca a VRAM e so somaria tempo de parede")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--exp-id", default="etapa1_calib")
    ap.add_argument("--no-stop-on-oom", dest="stop_on_oom", action="store_false",
                    help="continua para fatores mais pesados mesmo depois de um OOM")
    args = ap.parse_args()

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841
    # O aabb_scale vive no transforms da cena; le do primeiro alvo da varredura.
    aabb_ref = json.loads(scene_json(args.scenes[0], args.factors[0]).read_text()
                          ).get("aabb_scale", 1)
    network = build_network(
        exp_dir / f"network_T{CALIB_T}_F{CALIB_F}_L{CALIB_L}.json", aabb_ref)

    rows = []
    for scene in args.scenes:
        for factor in args.factors:
            row = run_one(scene, factor, network, args)
            rows.append(row)
            st = row.get("status")
            print(f"[calib] {scene} f{factor}: status={st} "
                  f"vram_peak_mb={row.get('vram_peak_mb')}", flush=True)
            if args.stop_on_oom and st in ("oom", "sem_metrics"):
                pulados = [f for f in args.factors
                           if args.factors.index(f) > args.factors.index(factor)]
                for p in pulados:
                    rows.append({"scene": scene, "factor": p, "status": "pulado",
                                 "error": f"f{factor} ja estourou a VRAM"})
                print(f"[calib] {scene}: f{factor} estourou, pulando {pulados}", flush=True)
                break

    csv_path = exp_dir / "calibracao.csv"
    # Varreduras por cena costumam ser invocacoes separadas no mesmo exp-id. Sem
    # merge, a segunda apagaria as linhas da primeira e o CSV consolidado
    # mentiria sobre o que foi medido. Linhas da mesma (cena, fator) sao
    # substituidas; o resto e preservado.
    anteriores = []
    if csv_path.exists():
        with csv_path.open(newline="") as fh:
            anteriores = list(csv.DictReader(fh))
    chaves_novas = {(str(r.get("scene")), str(r.get("factor"))) for r in rows}
    merged = [r for r in anteriores
              if (str(r.get("scene")), str(r.get("factor"))) not in chaves_novas] + rows
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in merged:
            w.writerow(r)

    print("\n" + "=" * 78)
    print(f"ETAPA 1 - CALIBRACAO DE RESOLUCAO   (T={CALIB_T} F={CALIB_F} L={CALIB_L}, "
          f"B={gr.FIXED_BATCH_SIZE}, 6144 MiB, spp={args.spp}, stride={args.test_stride})")
    print("=" * 78)
    print(f"{'cena':8} {'fator':6} {'resolucao':12} {'imgs':6} {'status':10} "
          f"{'pico MB':10} {'base MB':9}")
    print("-" * 78)
    for r in rows:
        print(f"{fmt(r.get('scene'), 8)} {fmt('f' + str(r.get('factor')), 6)} "
              f"{fmt(r.get('resolucao'), 12)} {fmt(r.get('n_train_images'), 6)} "
              f"{fmt(r.get('status'), 10)} {fmt(r.get('vram_peak_mb'), 10, 1)} "
              f"{fmt(r.get('vram_baseline_mb'), 9, 1)}")
    print("-" * 78)
    print(f"csv -> {csv_path}")

    for r in rows:
        if r.get("error"):
            print(f"  {r.get('scene')} f{r.get('factor')}: {r.get('error')[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
