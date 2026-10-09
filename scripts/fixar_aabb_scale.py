#!/usr/bin/env python3
"""Fixa o aabb_scale escolhido nos transforms de uma cena.

Depois da validacao quantitativa, o valor escolhido precisa viver NO DADO, nao
numa flag de linha de comando. Parametro que depende de alguem lembrar de
passar --aabb-scale a cada execucao e a mesma classe de erro silencioso que ja
custou uma execucao de 30 000 iteracoes neste projeto.

Grava um backup por arquivo antes de sobrescrever.

    python3 scripts/fixar_aabb_scale.py --scene garden --aabb-scale 4
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="subdiretorio em data/mip_nerf/")
    ap.add_argument("--aabb-scale", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sd = PROJECT_ROOT / "data" / "mip_nerf" / args.scene
    if not sd.is_dir():
        sys.exit(f"cena nao encontrada: {sd}")

    alvos = sorted(p for p in sd.glob("transforms*.json"))
    if not alvos:
        sys.exit(f"nenhum transforms*.json em {sd}")

    sufixo = ".bak-aabb"
    mudados, iguais = 0, 0
    for p in alvos:
        d = json.loads(p.read_text())
        atual = d.get("aabb_scale")
        if atual == args.aabb_scale:
            print(f"  ja em {args.aabb_scale}  {p.name}")
            iguais += 1
            continue
        if args.dry_run:
            print(f"  [dry-run] {p.name}: {atual} -> {args.aabb_scale}")
            mudados += 1
            continue
        bak = p.with_suffix(p.suffix + f"{sufixo}{atual}")
        if not bak.exists():
            shutil.copy2(p, bak)
        d["aabb_scale"] = args.aabb_scale
        p.write_text(json.dumps(d, indent=2))
        print(f"  {atual} -> {args.aabb_scale}  {p.name}   (backup: {bak.name})")
        mudados += 1

    print(f"\n{mudados} alterado(s), {iguais} ja corretos, de {len(alvos)} arquivos")
    if not args.dry_run and mudados:
        # Conferencia: nenhum arquivo pode ficar com valor divergente, ou uma
        # execucao futura mistura configuracoes sem avisar.
        valores = {json.loads(p.read_text()).get("aabb_scale") for p in alvos}
        if valores != {args.aabb_scale}:
            sys.exit(f"ERRO: valores divergentes apos a escrita: {valores}")
        print(f"conferido: todos os {len(alvos)} arquivos com aabb_scale={args.aabb_scale}")


if __name__ == "__main__":
    main()
