#!/usr/bin/env python3
"""Reescreve os file_path de um transforms.json para caminhos relativos a cena.

O colmap2nerf.py foi rodado a partir da raiz do projeto, entao gravou caminhos
como './data/mip_nerf/garden/images/DSC08140.JPG'. O instant-ngp resolve
file_path relativo ao diretorio do proprio JSON (nerf_loader.cu:335, base_path =
jsonpaths[i].parent_path()), e nao ao CWD, entao esses caminhos apontam para
'<cena>/data/mip_nerf/garden/images/...' e o load falha com
'Could not find image file'.

Este script corta tudo que vem antes do segmento images/ ou images_<N>/,
deixando './images/DSC08140.JPG'. Grava um .bak antes de sobrescrever.

    python3 scripts/rebase_transforms_paths.py data/mip_nerf/garden/transforms.json
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

IMAGES_SEG = re.compile(r"^images(_\d+)?$")


def rebase(file_path):
    """'./data/mip_nerf/garden/images/X.JPG' -> './images/X.JPG'."""
    parts = [p for p in file_path.replace("\\", "/").split("/") if p not in ("", ".")]
    for i, part in enumerate(parts):
        if IMAGES_SEG.match(part):
            return "./" + "/".join(parts[i:])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_paths", nargs="+", help="transforms.json a corrigir")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    for raw in args.json_paths:
        path = Path(raw)
        data = json.loads(path.read_text())
        frames = data.get("frames", [])
        if not frames:
            sys.exit(f"{path}: sem frames")

        changed = 0
        missing = []
        for frame in frames:
            new = rebase(frame["file_path"])
            if new is None:
                sys.exit(f"{path}: file_path sem segmento images/: {frame['file_path']}")
            if new != frame["file_path"]:
                frame["file_path"] = new
                changed += 1
            # valida contra o disco usando a mesma regra do instant-ngp
            if not (path.parent / new).exists():
                missing.append(new)

        if missing:
            print(f"{path}: ABORTADO, {len(missing)} imagens nao encontradas apos o rebase")
            for m in missing[:5]:
                print(f"    {path.parent / m}")
            sys.exit(1)

        if not args.no_backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(path, bak)
                print(f"  backup -> {bak}")
            else:
                print(f"  backup ja existia, preservado -> {bak}")

        path.write_text(json.dumps(data, indent=2))
        print(f"{path}")
        print(f"  frames reescritos... {changed}/{len(frames)}")
        print(f"  file_path[0]........ {frames[0]['file_path']}")
        print(f"  todas as {len(frames)} imagens resolvem a partir de {path.parent}")


if __name__ == "__main__":
    main()
