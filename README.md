# Instant-NGP numa GPU de 6 GB

Código, dados e documentação do TCC *Treinamento de modelos NeRF baseados em
grid: um olhar para o consumo de VRAM e otimização de hiperparâmetros em
hardwares de baixa especificação* (Luis Afonso Mineo, UniFil, 2026).

O trabalho mede como os três hiperparâmetros da codificação hash do Instant-NGP
— tamanho da tabela (T), features por nível (F) e número de níveis (L) — afetam
qualidade, memória e tempo de treino numa RTX 2060 de 6 GB, nas cenas Garden e
Bonsai do Mip-NeRF 360.

**Resultado principal.** Os hiperparâmetros movem o pico de VRAM em 1,3 a 2,1 GB,
mas as imagens de treino sozinhas ocupam 1,6 a 2,7 GB da placa e não respondem a
eles. Otimizar T, F e L permite escolher bem dentro de um orçamento de memória,
não treinar em resolução maior. Diferenças de qualidade abaixo de ~0,24 dB são
ruído do próprio treino.

## Por onde começar

| para… | leia |
|---|---|
| entender o trabalho e os conceitos | [docs/defesa/GUIA-conceitos-e-achados.md](docs/defesa/GUIA-conceitos-e-achados.md) |
| ver o que mudar no artigo | [docs/artigo/ARTIGO-v2-propostas.md](docs/artigo/ARTIGO-v2-propostas.md) |
| ver as tabelas finais | [runs/exp02_final/tabelas.md](runs/exp02_final/tabelas.md) |
| achar qualquer documento | [docs/README.md](docs/README.md) |

## Estrutura

```
tcc-nerf/
├── docs/                    documentação — índice em docs/README.md
│   ├── artigo/              o texto do TCC e as propostas de revisão
│   ├── defesa/              guia de conceitos e perguntas da banca
│   ├── relatorios/          o que foi medido, em ordem cronológica
│   ├── metodo/              protocolo, plano com critérios, pipeline técnico
│   ├── historico/           especificações e revisões superadas
│   └── refs/                artigos de referência (PDFs fora do git)
├── scripts/                 todo o código — índice em scripts/README.md
├── runs/                    resultados — índice em runs/README.md
│   └── exp02_final/         o que vai para o artigo
├── patches/                 alterações locais no instant-ngp
├── data/                    datasets (fora do git)
└── vendor/instant-ngp/      instant-ngp, repositório git próprio (fora do git)
```

## Reproduzir a análise final (sem GPU)

A partir dos CSVs versionados em `runs/`:

```bash
python3 scripts/consolidacao_final.py     # médias, guia por orçamento, tabelas
python3 scripts/pareto_bolhas.py          # fronteira e sweet spot
python3 scripts/sensibilidade_ruido.py
python3 scripts/efeito_hiperparametros.py
python3 scripts/figura_aabb.py
python3 scripts/joelho_explicado.py
```

Saídas em `runs/exp02_final/`. Dependências em `requirements.txt`.

## Reproduzir os experimentos (GPU)

Build do instant-ngp, patches, dependências e comandos estão em
[docs/metodo/PIPELINE.md](docs/metodo/PIPELINE.md); as regras de medição, em
[docs/metodo/PROTOCOLO-medicao.md](docs/metodo/PROTOCOLO-medicao.md). Os
parâmetros de cada experimento ficam gravados em `runs/<experimento>/manifest.json`.

Ambiente usado: WSL2 com Ubuntu 22.04, RTX 2060 6 GB, Ryzen 7 5700X3D, 16 GB de
RAM DDR4. Execuções sempre sequenciais; a GPU era compartilhada com a interface
do Windows, cuja ocupação é medida antes de cada execução e descontada.
