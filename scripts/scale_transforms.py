"""
Deriva um transforms.json para uma versao reduzida do dataset a partir do
transforms.json gerado em resolucao cheia pelo colmap2nerf.py.

Escala os intrinsecos (fl_x, fl_y, cx, cy, w, h) pelo fator de reducao e
reaponta os file_path para o diretorio de imagens correspondente.

Os coeficientes de distorcao (k1, k2, p1, p2) NAO sao escalados: eles operam
em coordenadas normalizadas e independem da resolucao.

Uso tipico, a partir da pasta da cena:

    python scale_transforms.py --in-json transforms.json \
        --factor 4 --out-json transforms_f4.json --aabb-scale 16
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

SCALED_KEYS = ("fl_x", "fl_y", "cx", "cy", "w", "h")
INT_KEYS = ("w", "h")


def scale_block(block, factor):
    """Escala os intrinsecos presentes em um dict (raiz ou frame)."""
    for key in SCALED_KEYS:
        if key in block and isinstance(block[key], (int, float)):
            block[key] = block[key] / factor
    for key in INT_KEYS:
        if key in block:
            # Arredondamento half-up, nao o round() bancario do Python. As
            # imagens reduzidas do mip-NeRF 360 sao geradas com half-up, entao
            # uma dimensao impar como a altura 3361 do garden precisa dar
            # 3361/2 -> 1681. Com round() daria 1680 (empate vai para o par) e
            # o JSON ficaria 1 px fora da imagem em disco.
            block[key] = int(math.floor(block[key] + 0.5))


def check_real_size(scene_dir, frames, expected_w, expected_h):
    """Confere a dimensao real da primeira imagem, se o Pillow estiver disponivel."""
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow ausente: pulando verificacao de dimensao real)")
        return
    if not frames:
        return
    img_path = (scene_dir / frames[0]["file_path"]).resolve()
    if not img_path.exists():
        print(f"  AVISO: imagem nao encontrada para verificacao: {img_path}")
        return
    with Image.open(img_path) as im:
        real_w, real_h = im.size
    if (real_w, real_h) == (expected_w, expected_h):
        print(f"  OK: imagem real {real_w}x{real_h} confere com o JSON")
    else:
        print(f"  ERRO: JSON diz {expected_w}x{expected_h}, "
              f"mas a imagem tem {real_w}x{real_h}")
        print("  Verifique o fator de reducao ou o diretorio de imagens.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", required=True,
                    help="transforms.json em resolucao cheia")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--factor", type=int, required=True, choices=[1, 2, 4, 8],
                    help="fator de reducao do dataset")
    ap.add_argument("--images-dir", default=None,
                    help="diretorio das imagens; padrao images_<factor>")
    ap.add_argument("--aabb-scale", type=int, default=None,
                    help="sobrescreve o aabb_scale do JSON de entrada")
    args = ap.parse_args()

    in_path = Path(args.in_json)
    out_path = Path(args.out_json)
    data = json.loads(in_path.read_text())

    factor = args.factor
    images_dir = args.images_dir or (f"images_{factor}" if factor > 1 else "images")

    scale_block(data, factor)
    if args.aabb_scale is not None:
        data["aabb_scale"] = args.aabb_scale

    frames = data.get("frames", [])
    if not frames:
        sys.exit("transforms.json sem frames")

    pattern = re.compile(r"(^|/)images(_\d+)?(/|$)")
    for frame in frames:
        scale_block(frame, factor)
        frame["file_path"] = pattern.sub(
            lambda m: f"{m.group(1)}{images_dir}{m.group(3)}",
            frame["file_path"],
        )

    out_path.write_text(json.dumps(data, indent=2))

    print(f"{out_path}")
    print(f"  frames........ {len(frames)}")
    print(f"  imagens....... {images_dir}")
    print(f"  resolucao..... {data.get('w')}x{data.get('h')}")
    print(f"  fl_x / fl_y... {data.get('fl_x'):.2f} / {data.get('fl_y'):.2f}")
    print(f"  aabb_scale.... {data.get('aabb_scale')}")
    check_real_size(out_path.parent, frames, data.get("w"), data.get("h"))


if __name__ == "__main__":
    main()