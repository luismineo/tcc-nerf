#!/usr/bin/env python3
"""Etapa 1 refeita: escolha de resolucao sob as condicoes corrigidas.

A primeira calibracao de resolucao rodou com aabb_scale=16 e SEM divisao de
treino/teste. As duas coisas foram corrigidas depois, e ambas derrubam o consumo
de VRAM -- entao o ponto de operacao precisa ser remedido, nao ajustado.

Para cada fator de reducao:
  1. deriva transforms de treino e teste com o aabb_scale escolhido;
  2. treina do zero pelo ngp_worker.py na configuracao PADRAO do Instant-NGP;
  3. avalia no split retido, guarda os renders e registra VRAM, PSNR e SSIM.

Criterio do SPEC-exp02 secao 3: escolher o fator em que a configuracao padrao
consome entre 5 e 6 GB, ou falha por pouco. Abaixo disso a restricao nao morde e
a Fronteira de Pareto degenera num ranking de qualidade sem eixo de custo.

Saidas em --out-dir: resolucao_final.csv, resolucao_final.png e
comparacao_resolucao.png (folha de contato de uma vista retida por fator).

    python3 scripts/resolucao_final.py --factors 8 4 2 1 --aabb-scale 4
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from calib_resolucao import acquire_lock  # noqa: E402

VRAM_TOTAL_MB = 6144
JANELA = (5000.0, 6000.0)   # criterio do spec, em MB

CSV_FIELDS = [
    "factor", "resolucao", "aabb_scale", "status", "veredito", "motivo",
    "imagens_mb", "steps_rel",
    "psnr", "psnr_median", "psnr_std", "ssim", "ssim_ngp", "loss_final",
    "vram_peak_mb", "vram_peak_device_mb", "vram_livre_mb", "vram_baseline_mb",
    "vram_at_failure_mb", "dentro_da_janela",
    "n_train_images", "n_test_images", "test_views", "megapixels_treino",
    "n_params", "n_encoding_params",
    "samples_per_ray_mean", "n_rays_effective_mean",
    "steps_per_s", "t_train_s", "t_eval_s", "t_total_s", "error",
]


class _PularExecucao(Exception):
    """Sinaliza modo --somente-analise; nao e erro."""


def variante(base_json, aabb_scale, destino):
    d = json.loads(Path(base_json).read_text())
    d["aabb_scale"] = int(aabb_scale)
    Path(destino).write_text(json.dumps(d, indent=2))
    return d


def jsons_do_fator(scene_dir, fator):
    """Convencao do split_holdout.py: transforms_f<N>_{train,test}.json."""
    tr = scene_dir / f"transforms_f{fator}_train.json"
    te = scene_dir / f"transforms_f{fator}_test.json"
    return tr, te


def rodar_um(fator, args, exp_dir):
    scene_dir = PROJECT_ROOT / "data" / "mip_nerf" / args.dataset
    base_tr, base_te = jsons_do_fator(scene_dir, fator)
    linha = {"factor": fator, "aabb_scale": args.aabb_scale}

    if not base_tr.exists() or not base_te.exists():
        linha.update({"status": "sem_split",
                      "error": f"faltam {base_tr.name} / {base_te.name}; "
                               f"rode split_holdout.py para o fator {fator}"})
        return linha

    marca = os.getpid()
    tmp_tr = scene_dir / f"_resf_{marca}_train_{fator}.json"
    tmp_te = scene_dir / f"_resf_{marca}_test_{fator}.json"
    out_dir = exp_dir / f"f{fator}"
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    try:
        d = variante(base_tr, args.aabb_scale, tmp_tr)
        variante(base_te, args.aabb_scale, tmp_te)
        w, h = int(d["w"]), int(d["h"])
        n_tr = len(d["frames"])
        linha["resolucao"] = f"{w}x{h}"
        # Orcamento de pixels de treino: e ele, e nao o rotulo do fator, que
        # governa o piso de VRAM (as imagens ficam na placa a 4 B/px).
        linha["megapixels_treino"] = round(n_tr * w * h / 1e6, 1)

        cmd = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "ngp_worker.py"),
            "--scene", str(tmp_tr),
            "--test-transforms", str(tmp_te),
            "--network", args.network,
            "--out-dir", str(out_dir),
            "--n-steps", str(args.n_steps),
            "--batch-size", str(args.batch_size),
            "--seed", str(args.seed),
            "--test-stride", str(args.test_stride),
            "--spp", str(args.spp),
            "--lpips-device", args.lpips_device,
            "--no-nerf-compatibility",
            "--dataset", args.dataset,
            "--downsample-factor", str(fator),
        ]
        if args.keep_renders:
            cmd.append("--keep-renders")

        print(f"\n--- fator {fator} ({w}x{h}, {linha['megapixels_treino']} Mpx) ---",
              flush=True)
        if args.somente_analise:
            # Reclassifica a partir do metrics.json ja gravado, sem tocar a GPU.
            print("  (somente analise: reaproveitando metrics.json existente)",
                  flush=True)
            raise _PularExecucao
        with (out_dir / "worker.log").open("w") as log:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                    stdout=log, stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    except _PularExecucao:
        pass
    finally:
        tmp_tr.unlink(missing_ok=True)
        tmp_te.unlink(missing_ok=True)

    linha["t_total_s"] = round(time.perf_counter() - t0, 1)
    mp = out_dir / "metrics.json"
    if not mp.exists():
        linha.update({"status": "sem_metrics", "error": "worker nao gravou metrics.json"})
        return linha

    m = json.loads(mp.read_text())
    for k in CSV_FIELDS:
        if k in m:
            linha[k] = m[k]
    # Custo so das imagens de treino na VRAM: o instant-ngp as guarda como RGBA
    # de 8 bits (nerf_loader.cu, load_stbi com 4 componentes). Serve de piso
    # fisico para conferir o pico medido.
    try:
        w2, h2 = [int(x) for x in str(m.get("image_resolution")).split("x")]
        linha["imagens_mb"] = round(
            (m.get("n_train_images") or 0) * w2 * h2 * 4 / 1048576, 1)
    except Exception:
        linha["imagens_mb"] = None
    pdev = m.get("vram_peak_device_mb")
    linha["vram_livre_mb"] = None if pdev is None else round(VRAM_TOTAL_MB - pdev, 1)
    linha["status"] = m.get("status")
    linha["error"] = "" if m.get("status") == "ok" else str(m.get("error", ""))[:200]
    linha["dentro_da_janela"] = (
        bool(pdev is not None and JANELA[0] <= pdev <= JANELA[1])
        if m.get("status") == "ok" else False)

    print(f"[res] f{fator}: status={linha['status']} pico={pdev} MB "
          f"livre={linha['vram_livre_mb']} PSNR={linha.get('psnr')} "
          f"janela={linha['dentro_da_janela']}", flush=True)
    return linha


def classificar(linhas, frac_lenta=0.4):
    """Separa "coube" de "o driver fingiu que coube".

    O driver NVIDIA em WSL2 permite oversubscricao de VRAM: quando a alocacao
    excede a placa, ele migra paginas para a RAM do sistema em vez de falhar. O
    processo termina com status=ok e o nvidia-smi reporta o pico travado perto
    do teto -- mas o treino fica uma ordem de grandeza mais lento e a medida de
    VRAM deixa de significar qualquer coisa.

    Dois detectores independentes:

      (1) aritmetico -- se as imagens de treino sozinhas (4 B/px, que e como o
          instant-ngp as guarda) ja excedem o pico medido do processo, parte
          dos dados nao esta residente na placa. Nao depende de comparacao.

      (2) de vazao -- o custo por passo e governado por B, nao pela resolucao
          das imagens. Queda grande de steps/s entre fatores denuncia paginacao.

    Nao sobrescreve `status`, que e o veredito do worker: acrescenta `veredito`,
    que e interpretacao. Fato medido e leitura ficam em colunas separadas.
    """
    ok = [l for l in linhas if l.get("status") == "ok" and l.get("steps_per_s")]
    velocidades = sorted(l["steps_per_s"] for l in ok)
    mediana = velocidades[len(velocidades) // 2] if velocidades else None

    for l in linhas:
        if l.get("status") != "ok":
            l["veredito"] = l.get("status") or "desconhecido"
            l["motivo"] = l.get("error", "")[:120]
            continue

        motivos = []
        imgs = l.get("imagens_mb")
        pico = l.get("vram_peak_mb")   # pico do processo, ja sem a linha de base
        if imgs and pico and imgs > pico:
            motivos.append(
                f"imagens a 4 B/px ({imgs:.0f} MB) excedem o pico medido "
                f"({pico:.0f} MB): parte dos dados nao esta na VRAM")

        sps = l.get("steps_per_s")
        if mediana and sps:
            l["steps_rel"] = round(sps / mediana, 3)
            if sps < frac_lenta * mediana:
                motivos.append(
                    f"vazao {sps:.1f} passos/s contra mediana {mediana:.1f} "
                    f"({sps / mediana:.0%}): indica paginacao para a RAM do host")

        l["veredito"] = "degradado" if motivos else "viavel"
        l["motivo"] = " | ".join(motivos)
        if motivos:
            # Um ponto degradado nao pode contar como candidato de resolucao.
            l["dentro_da_janela"] = False
    return linhas


def folha_de_contato(linhas, exp_dir, destino, altura=340):
    """Uma vista retida por fator, normalizada em altura, lado a lado."""
    from PIL import Image, ImageDraw

    itens = []
    ref_posta = False
    for l in linhas:
        d = exp_dir / f"f{l['factor']}" / "renders"
        if not d.exists():
            continue
        if not ref_posta:
            refs = sorted(d.glob("ref_*.png"))
            if refs:
                im = Image.open(refs[0]).convert("RGB")
                im.thumbnail((10000, altura))
                itens.append(("REFERENCIA (foto)", im))
                ref_posta = True
        vistas = sorted(d.glob("view_*.png"))
        if vistas:
            im = Image.open(vistas[0]).convert("RGB")
            im.thumbnail((10000, altura))
            itens.append((f"fator {l['factor']} ({l.get('resolucao', '?')})", im))

    if not itens:
        print("sem renders para a folha de contato")
        return None
    faixa = 26
    total_w = sum(im.width for _, im in itens)
    alt = max(im.height for _, im in itens)
    folha = Image.new("RGB", (total_w, alt + faixa * 2), "white")
    dr = ImageDraw.Draw(folha)
    dr.text((6, 6), "resolucao | vista retida | configuracao padrao", fill="black")
    x = 0
    for rot, im in itens:
        folha.paste(im, (x, faixa))
        dr.text((x + 6, alt + faixa + 6), rot, fill="black")
        x += im.width
    folha.save(destino)
    return destino


def plotar(linhas, destino, args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordenadas = sorted(linhas, key=lambda l: l.get("megapixels_treino") or 0)
    x = [l.get("megapixels_treino") or 0 for l in ordenadas]
    rot = [f"f{l['factor']}" for l in ordenadas]
    pico = [l.get("vram_peak_device_mb") for l in ordenadas]
    falha = [l.get("vram_at_failure_mb") for l in ordenadas]
    psnr = [l.get("psnr") for l in ordenadas]

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(9.5, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.14})

    ax.axhspan(JANELA[0], JANELA[1], color="#2e7d32", alpha=0.13,
               label="janela do criterio (5-6 GB)")
    ax.axhline(VRAM_TOTAL_MB, color="black", ls="--", lw=1.3)
    ax.annotate(f"{VRAM_TOTAL_MB} MB (RTX 2060)", xy=(x[0], VRAM_TOTAL_MB),
                xytext=(4, 5), textcoords="offset points", fontsize=8)

    xs_ok = [xi for xi, p in zip(x, pico) if p is not None]
    ys_ok = [p for p in pico if p is not None]
    if xs_ok:
        ax.plot(xs_ok, ys_ok, marker="o", ms=7, lw=1.8, color="#1f4e79",
                label="pico de VRAM (ok)")
    for xi, fi, li in zip(x, falha, ordenadas):
        if li.get("status") == "oom":
            ax.plot([xi], [fi if fi else VRAM_TOTAL_MB], marker="X", ms=13,
                    color="#c00000", ls="none",
                    label="OOM" if "OOM" not in ax.get_legend_handles_labels()[1] else None)
    for xi, ri, li in zip(x, rot, ordenadas):
        p = li.get("vram_peak_device_mb") or li.get("vram_at_failure_mb") or VRAM_TOTAL_MB
        ax.annotate(ri, xy=(xi, p), xytext=(6, 8), textcoords="offset points",
                    fontsize=9, weight="bold")
    ax.set_ylabel("VRAM (MB)")
    ax.set_xscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(
        f"Etapa 1 refeita — {args.dataset}, aabb_scale={args.aabb_scale}, split retido\n"
        f"{args.n_steps} iteracoes, configuracao padrao, spp={args.spp}", fontsize=11)

    xs_p = [xi for xi, p in zip(x, psnr) if p is not None]
    ys_p = [p for p in psnr if p is not None]
    if xs_p:
        ax2.plot(xs_p, ys_p, marker="s", ms=6, lw=1.6, color="#2e7d32")
    ax2.set_ylabel("PSNR (dB)")
    ax2.set_xlabel("megapixels de treino (n_imagens x largura x altura)")
    ax2.set_xscale("log")
    ax2.grid(alpha=0.3, which="both")

    fig.subplots_adjust(left=0.10, right=0.97, top=0.88, bottom=0.09)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="garden")
    ap.add_argument("--factors", nargs="+", type=int, default=[8, 4, 2, 1],
                    help="do mais leve para o mais pesado")
    ap.add_argument("--aabb-scale", type=int, required=True,
                    help="valor escolhido na varredura quantitativa de aabb_scale")
    ap.add_argument("--n-steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--test-stride", type=int, default=1)
    ap.add_argument("--lpips-device", default="none", choices=["cpu", "cuda", "none"])
    ap.add_argument("--network", default=None)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--exp-id", default="etapa1_final")
    ap.add_argument("--no-keep-renders", dest="keep_renders", action="store_false")
    ap.add_argument("--somente-analise", action="store_true",
                    help="nao treina: reclassifica a partir dos metrics.json ja gravados")
    ap.add_argument("--frac-lenta", type=float, default=0.4,
                    help="fracao da mediana de steps/s abaixo da qual a run e "
                         "considerada degradada por paginacao")
    args = ap.parse_args()

    args.network = args.network or str(
        PROJECT_ROOT / "vendor" / "instant-ngp" / "configs" / "nerf" / "base.json")

    exp_dir = PROJECT_ROOT / "runs" / args.exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    if not args.somente_analise:
        _lock = acquire_lock(PROJECT_ROOT / "runs" / ".calib.lock")  # noqa: F841

    print(f"cena {args.dataset} | aabb_scale={args.aabb_scale} | "
          f"fatores {args.factors} | {args.n_steps} passos | rede padrao")

    linhas = [rodar_um(f, args, exp_dir) for f in args.factors]
    linhas = classificar(linhas, args.frac_lenta)

    csv_path = exp_dir / "resolucao_final.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for l in linhas:
            w.writerow(l)

    png_path = exp_dir / "resolucao_final.png"
    plotar(linhas, png_path, args)
    folha = folha_de_contato(linhas, exp_dir, exp_dir / "comparacao_resolucao.png")

    def f(v, nd=2):
        return "-" if v is None or v == "" else (
            f"{v:.{nd}f}" if isinstance(v, float) else str(v))

    print("\n" + "=" * 96)
    print(f"ETAPA 1 REFEITA — {args.dataset}, aabb_scale={args.aabb_scale}, split retido")
    print("=" * 96)
    print(f"{'fator':>6} {'resolucao':>12} {'Mpx':>8} {'veredito':>10} {'pico MB':>9} "
          f"{'imgs MB':>9} {'steps/s':>8} {'janela':>7} {'PSNR':>8} {'SSIM':>8}")
    print("-" * 96)
    for l in sorted(linhas, key=lambda z: -(z.get("factor") or 0)):
        print(f"{('f' + str(l['factor'])):>6} {f(l.get('resolucao')):>12} "
              f"{f(l.get('megapixels_treino'), 1):>8} {str(l.get('veredito')):>10} "
              f"{f(l.get('vram_peak_device_mb'), 1):>9} {f(l.get('imagens_mb'), 0):>9} "
              f"{f(l.get('steps_per_s'), 1):>8} "
              f"{('SIM' if l.get('dentro_da_janela') else '-'):>7} "
              f"{f(l.get('psnr')):>8} {f(l.get('ssim'), 4):>8}")
    print("-" * 96)
    for l in linhas:
        if l.get("veredito") == "degradado":
            print(f"  DEGRADADO f{l['factor']}: {l.get('motivo')}")
    dentro = [l for l in linhas if l.get("dentro_da_janela")]
    if dentro:
        print("DENTRO DA JANELA DE 5-6 GB: " +
              ", ".join(f"f{l['factor']}" for l in dentro))
    else:
        print("NENHUM FATOR NA JANELA DE 5-6 GB "
              "-- ver secao 3 do spec: gerar fator intermediario.")
    print(f"\ncsv     -> {csv_path}")
    print(f"grafico -> {png_path}")
    if folha:
        print(f"imagens -> {folha}  (renders completos em {exp_dir}/f*/renders/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
