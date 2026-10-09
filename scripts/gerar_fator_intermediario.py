#!/usr/bin/env python3
"""Gera um fator de reducao intermediario para uma cena do Mip-NeRF 360.

O dataset so distribui reducoes por 2, 4 e 8. A secao 3 do SPEC-exp02 preve
gerar um fator intermediario quando os disponiveis forem grosseiros demais --
que e o caso aqui: entre o fator 2 (que cabe folgado) e o fator 1 (cujas
imagens sozinhas excedem a placa) nao ha nada.

Produz:
  data/mip_nerf/<cena>/images_<fator>/          imagens reduzidas
  data/mip_nerf/<cena>/transforms_f<fator>.json intrinsecos escalados

O aabb_scale e herdado do transforms.json de resolucao cheia, que ja carrega o
valor validado. A reducao usa LANCZOS, o mesmo filtro de alta qualidade que o
Mip-NeRF 360 empregou nas suas proprias reducoes.

    python3 scripts/gerar_fator_intermediario.py --scene garden --factor 1.62
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def half_up(x):
    """Mesmo arredondamento do scale_transforms.py: half-up, nao bancario."""
    return int(math.floor(x + 0.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--factor", type=float, required=True)
    ap.add_argument("--in-json", default="transforms.json",
                    help="transforms de resolucao cheia da cena")
    ap.add_argument("--src-dir", default="images", help="imagens em resolucao cheia")
    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--force", action="store_true",
                    help="regera imagens que ja existirem")
    args = ap.parse_args()

    from PIL import Image

    sd = PROJECT_ROOT / "data" / "mip_nerf" / args.scene
    in_json = sd / args.in_json
    if not in_json.exists():
        sys.exit(f"nao encontrado: {in_json}")

    f = args.factor
    tag = f"{f:g}"                      # 1.62 -> "1.62"; 3.0 -> "3"
    dst_dir = sd / f"images_{tag}"
    dst_dir.mkdir(exist_ok=True)

    data = json.loads(in_json.read_text())
    W, H = int(data["w"]), int(data["h"])
    w, h = half_up(W / f), half_up(H / f)
    print(f"{args.scene}: {W}x{H} / {f} -> {w}x{h}  (aabb_scale={data.get('aabb_scale')})")

    # --- imagens ---------------------------------------------------------
    src_dir = sd / args.src_dir
    fontes = sorted(p for p in src_dir.iterdir() if p.suffix.lower() in
                    (".jpg", ".jpeg", ".png"))
    if not fontes:
        sys.exit(f"nenhuma imagem em {src_dir}")
    feitas, puladas = 0, 0
    for i, p in enumerate(fontes, 1):
        alvo = dst_dir / p.name
        if alvo.exists() and not args.force:
            puladas += 1
            continue
        with Image.open(p) as im:
            im = im.convert("RGB").resize((w, h), Image.LANCZOS)
            im.save(alvo, quality=args.quality)
        feitas += 1
        if i % 25 == 0 or i == len(fontes):
            print(f"  {i}/{len(fontes)} imagens", flush=True)
    print(f"  geradas {feitas}, reaproveitadas {puladas}")

    # --- transforms ------------------------------------------------------
    # Intrinsecos escalam com a resolucao; k1/k2/p1/p2 operam em coordenadas
    # normalizadas e NAO escalam.
    for k in ("fl_x", "fl_y", "cx", "cy"):
        if k in data:
            data[k] = data[k] / f
    data["w"], data["h"] = w, h

    padrao = re.compile(r"(^|/)images(_[\d.]+)?(/|$)")
    frames = data.get("frames", [])
    if not frames:
        sys.exit("transforms sem frames")
    faltando = []
    for fr in frames:
        fr["file_path"] = padrao.sub(lambda m: f"{m.group(1)}images_{tag}{m.group(3)}",
                                     fr["file_path"])
        if not (sd / fr["file_path"]).exists():
            faltando.append(fr["file_path"])
    if faltando:
        sys.exit(f"ERRO: {len(faltando)} imagens nao resolvem, ex.: {faltando[0]}")

    out_json = sd / f"transforms_f{tag}.json"
    out_json.write_text(json.dumps(data, indent=2))

    # Conferencia contra o disco, como o scale_transforms.py faz.
    with Image.open(sd / frames[0]["file_path"]) as im:
        rw, rh = im.size
    ok = (rw, rh) == (w, h)
    print(f"{out_json}")
    print(f"  frames........ {len(frames)}")
    print(f"  resolucao..... {w}x{h}  ({'OK' if ok else f'ERRO: imagem e {rw}x{rh}'})")
    print(f"  fl_x / fl_y... {data['fl_x']:.2f} / {data['fl_y']:.2f}")
    print(f"  aabb_scale.... {data.get('aabb_scale')}")
    mb = len(frames) * w * h * 4 / 1048576
    print(f"  imagens na VRAM a 4 B/px (conjunto completo): {mb:.0f} MB")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
