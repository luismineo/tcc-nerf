#!/usr/bin/env python3
"""Divide um transforms.json em treino e teste por holdout periodico.

O Mip-NeRF 360 nao traz divisao oficial de treino/teste, diferente do
Synthetic-NeRF. A convencao da literatura para essas cenas e reservar 1 a cada N
imagens para teste. Este script materializa essa regra em dois JSONs.

A separacao e feita pelo INDICE do frame na ordem em que ele aparece no JSON.
Nao ha reordenacao por nome de arquivo nem por qualquer outro criterio: a ordem
que o colmap2nerf.py grava ja e estavel, e reordenar aqui produziria uma divisao
diferente da que o resto do pipeline assume, silenciosamente.

    python3 scripts/split_holdout.py \
        --in-json data/mip_nerf/garden/transforms_f2.json \
        --holdout-every 8 \
        --out-prefix data/mip_nerf/garden/transforms_f2
"""

import argparse
import json
import sys
from pathlib import Path


def split_frames(frames, every):
    """Indices 0, every, 2*every, ... vao para teste; o resto para treino."""
    test, train = [], []
    for i, frame in enumerate(frames):
        (test if i % every == 0 else train).append(frame)
    return train, test


def main():
    ap = argparse.ArgumentParser(
        description="Divide um transforms.json em treino e teste por holdout periodico")
    ap.add_argument("--in-json", required=True, help="transforms.json de entrada")
    ap.add_argument("--holdout-every", type=int, default=8,
                    help="1 a cada N frames vai para teste (padrao 8)")
    ap.add_argument("--out-prefix", required=True,
                    help="prefixo de saida; gera <prefixo>_train.json e <prefixo>_test.json")
    ap.add_argument("--indent", type=int, default=2)
    args = ap.parse_args()

    every = args.holdout_every
    if every < 1:
        sys.exit(f"--holdout-every precisa ser >= 1, recebido {every}")

    in_path = Path(args.in_json)
    if not in_path.exists():
        sys.exit(f"nao encontrado: {in_path}")

    data = json.loads(in_path.read_text())
    frames = data.get("frames")
    if not frames:
        sys.exit(f"{in_path}: sem frames")

    train, test = split_frames(frames, every)

    # Pedido explicitamente: teste vazio e erro, nunca um JSON valido e inutil.
    # Com every >= 1 o indice 0 sempre entra, entao isso so dispara em caso
    # degenerado -- mas falhar alto aqui e melhor que um grid inteiro avaliado
    # contra nada.
    if not test:
        sys.exit(f"holdout_every={every} nao selecionou nenhum frame de teste "
                 f"entre {len(frames)} frames")
    if not train:
        sys.exit(f"holdout_every={every} nao deixou nenhum frame de treino "
                 f"entre {len(frames)} frames")

    rule = f"holdout_every={every}"
    outputs = []
    for nome, subset in (("train", train), ("test", test)):
        # Preserva todos os campos do original; so 'frames' e substituido.
        saida = {k: v for k, v in data.items() if k != "frames"}
        saida["frames"] = subset
        saida["test_split_rule"] = rule
        saida["split"] = nome
        path = Path(f"{args.out_prefix}_{nome}.json")
        path.write_text(json.dumps(saida, indent=args.indent))
        outputs.append((nome, path, len(subset)))

    print(f"{in_path}")
    print(f"  frames de entrada... {len(frames)}")
    print(f"  regra............... {rule} (indices 0, {every}, {2 * every}, ... para teste)")
    for nome, path, n in outputs:
        pct = 100.0 * n / len(frames)
        print(f"  {nome:5} ............. {n:4} imagens ({pct:.1f}%)  -> {path}")
    # Conferencia: a divisao precisa ser exaustiva e sem sobreposicao.
    total = sum(n for _, _, n in outputs)
    if total != len(frames):
        sys.exit(f"ERRO: {total} frames distribuidos contra {len(frames)} de entrada")
    print(f"  soma confere........ {total} == {len(frames)}")


if __name__ == "__main__":
    main()
