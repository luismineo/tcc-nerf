#!/usr/bin/env python3
"""
Comparacao visual de aabb_scale, sem GUI.

Treina a mesma cena por um numero curto de passos com cada valor de aabb_scale
informado e salva uma imagem renderizada da MESMA pose para cada valor, mais uma
folha de contato com todos lado a lado.

Serve para descartar um aabb_scale mal escolhido antes de fixa-lo:
  - caixa PEQUENA demais -> neblina/manchas ("floaters") nas bordas, fundo
    cortado ou "achatado" contra uma parede invisivel;
  - caixa GRANDE demais  -> resolucao efetiva desperdicada no vazio, objeto de
    interesse mais mole, e floaters difusos no volume inteiro.

Nao substitui medicao de PSNR/SSIM ao fim do treino. Se as imagens parecerem
equivalentes, isso NAO prova que o valor e otimo, so que nao esta obviamente
quebrado.

Uso tipico (a partir da raiz do projeto):

    python3 scripts/aabb_visual_check.py \
        --scene data/mip_nerf/garden/transforms_f2_train.json \
        --eval-json data/mip_nerf/garden/transforms_f2_test.json \
        --values 4 8 16 32 \
        --steps 2000 \
        --out-dir runs/aabb_check/garden
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ngp_worker import linear_to_srgb  # noqa: E402


def carregar_pyngp(ngp_root):
    """Localiza o pyngp em build/ ou build*/**, como o resto do pipeline faz."""
    for so in sorted(Path(ngp_root).glob("build*/**/pyngp*.so")):
        sys.path.insert(0, str(so.parent))
        break
    else:
        raise SystemExit(
            f"pyngp*.so nao encontrado em {ngp_root}/build*.\n"
            "Compile o instant-ngp ou aponte --ngp-root para a raiz correta."
        )
    import pyngp as ngp
    return ngp


def make_variant(base_json_path, aabb_scale, out_path):
    data = json.loads(Path(base_json_path).read_text())
    data["aabb_scale"] = aabb_scale
    Path(out_path).write_text(json.dumps(data, indent=2))
    return out_path


def render_view(testbed, idx, largura, altura):
    """Render em sRGB, pelo mesmo caminho que o ngp_worker usa nas metricas."""
    testbed.set_camera_to_training_view(idx)
    testbed.render_ground_truth = False
    img = testbed.render(largura, altura, 8, True)  # linear=True; sRGB abaixo
    return (np.clip(linear_to_srgb(img[..., :3]), 0, 1) * 255 + 0.5).astype(np.uint8)


def render_ref(testbed, idx, largura, altura):
    testbed.render_ground_truth = True
    img = testbed.render(largura, altura, 1, True)
    testbed.render_ground_truth = False
    return (np.clip(linear_to_srgb(img[..., :3]), 0, 1) * 255 + 0.5).astype(np.uint8)


def folha_de_contato(itens, destino, titulo):
    """Junta os renders numa imagem so, rotulada, para comparacao lado a lado."""
    from PIL import Image, ImageDraw

    if not itens:
        return
    faixa = 28
    larguras = [im.width for _, im in itens]
    altura = max(im.height for _, im in itens)
    total_w = sum(larguras)
    folha = Image.new("RGB", (total_w, altura + faixa * 2), "white")
    d = ImageDraw.Draw(folha)
    d.text((6, 6), titulo, fill="black")
    x = 0
    for rotulo, im in itens:
        folha.paste(im, (x, faixa))
        d.text((x + 6, altura + faixa + 6), rotulo, fill="black")
        x += im.width
    folha.save(destino)


def main():
    ap = argparse.ArgumentParser(
        description="Compara valores de aabb_scale renderizando a mesma pose para cada um")
    ap.add_argument("--scene", required=True,
                    help="transforms.json de TREINO (o aabb_scale sera sobrescrito)")
    ap.add_argument("--eval-json", default=None,
                    help="transforms.json de TESTE; se informado, o render sai de uma "
                         "vista RETIDA, que e onde floaters aparecem primeiro")
    ap.add_argument("--values", type=int, nargs="+", required=True)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--view", type=int, default=0,
                    help="indice da vista renderizada (mesma para todos os valores)")
    ap.add_argument("--render-width", type=int, default=800)
    ap.add_argument("--render-height", type=int, default=520)
    ap.add_argument("--batch-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--network", default=None,
                    help="padrao: <ngp-root>/configs/nerf/base.json (configuracao padrao)")
    ap.add_argument("--ngp-root", default=str(PROJECT_ROOT / "vendor" / "instant-ngp"))
    args = ap.parse_args()

    ngp_root = Path(args.ngp_root).resolve()
    network = args.network or str(ngp_root / "configs" / "nerf" / "base.json")
    ngp = carregar_pyngp(ngp_root)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # O JSON derivado precisa ficar na MESMA pasta do transforms.json base: os
    # file_path dentro dele sao relativos a essa pasta (o instant-ngp resolve
    # contra o diretorio do proprio JSON). Escrever em out_dir quebra isso e o
    # testbed carrega zero imagens.
    scene_dir = Path(args.scene).resolve().parent
    eval_dir = Path(args.eval_json).resolve().parent if args.eval_json else None

    # PID no nome do temporario: duas execucoes simultaneas do script (comum
    # quando se esquece que ja ha uma rodando) processariam o mesmo aabb_scale e
    # o `finally` de uma apagaria o JSON que a outra esta carregando. Aqui a
    # concorrencia so custa velocidade, entao nomear por processo resolve sem
    # precisar de trava.
    marca = os.getpid()

    itens, refs = [], None
    for scale in args.values:
        tmp_treino = scene_dir / f"_aabb_tmp_{marca}_train_{scale}.json"
        tmp_eval = (eval_dir / f"_aabb_tmp_{marca}_eval_{scale}.json") if args.eval_json else None
        testbed = None
        try:
            make_variant(args.scene, scale, tmp_treino)
            print(f"--- aabb_scale={scale} ---", flush=True)

            testbed = ngp.Testbed()
            testbed.root_dir = str(ngp_root)          # faltava: resolve recursos do ngp
            if hasattr(testbed, "seed"):
                testbed.seed = int(args.seed)
            testbed.load_training_data(str(tmp_treino))
            testbed.reload_network_from_file(network)  # faltava: sem isso nao ha rede
            testbed.training_batch_size = int(args.batch_size)
            testbed.shall_train = True                 # faltava: sem isso nao treina nada

            for i in range(args.steps):
                # train() e nao frame(): frame() para de treinar em silencio
                # quando o ngp seta m_train=false. Mesma razao documentada no
                # ngp_worker.py.
                testbed.train(int(args.batch_size))
                if i % 500 == 0:
                    print(f"  passo {i:5d}  loss={testbed.loss:.5f}", flush=True)

            testbed.background_color = [0.0, 0.0, 0.0, 1.0]
            testbed.snap_to_pixel_centers = True
            testbed.nerf.render_min_transmittance = 1e-4
            testbed.shall_train = False
            testbed.render_with_lens_distortion = True

            # Vista retida, quando disponivel: e nela que o excesso de caixa
            # aparece como neblina, porque nao houve supervisao direta ali.
            if args.eval_json:
                make_variant(args.eval_json, scale, tmp_eval)
                testbed.load_training_data(str(tmp_eval))
                origem = "retida"
            else:
                origem = "treino"

            n = int(testbed.nerf.training.dataset.n_images)
            idx = min(args.view, n - 1)
            img = render_view(testbed, idx, args.render_width, args.render_height)

            from PIL import Image
            destino = out_dir / f"render_aabb{scale}.png"
            Image.fromarray(img).save(destino)
            itens.append((f"aabb_scale={scale}", Image.fromarray(img)))
            print(f"  vista {origem} {idx} -> {destino}", flush=True)

            if refs is None:
                ref = render_ref(testbed, idx, args.render_width, args.render_height)
                refs = out_dir / "referencia.png"
                Image.fromarray(ref).save(refs)
                print(f"  referencia (foto real) -> {refs}", flush=True)
        finally:
            if testbed is not None:
                del testbed           # libera a VRAM antes do proximo valor
            tmp_treino.unlink(missing_ok=True)
            if tmp_eval is not None:
                tmp_eval.unlink(missing_ok=True)

    if refs is not None:
        from PIL import Image
        itens = [("REFERENCIA (foto)", Image.open(refs))] + itens
    folha = out_dir / "comparacao.png"
    # Somente ASCII no rotulo: a fonte bitmap padrao do PIL nao tem travessao
    # nem acento, e desenha um retangulo vazio no lugar.
    folha_de_contato(itens, folha,
                     f"aabb_scale | {args.steps} passos | vista "
                     f"{'retida' if args.eval_json else 'de treino'} {args.view}")

    print(f"\nFolha de contato: {folha}")
    print("Abra e compare da esquerda (referencia) para a direita.")
    print("  caixa PEQUENA demais: fundo cortado, neblina densa nas bordas")
    print("  caixa GRANDE demais : cena inteira mais mole, neblina difusa no volume")
    print("Imagens equivalentes NAO provam que o valor e otimo, so que nao esta quebrado.")


if __name__ == "__main__":
    main()
