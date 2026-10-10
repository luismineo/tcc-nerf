# Scripts

Todos rodam a partir da raiz do projeto: `python3 scripts/<nome>.py`. Cada um
explica no próprio cabeçalho o que faz, os critérios e as opções (`--help`).
Os arquivos ficam numa pasta só porque vários se importam entre si.

Os que precisam de GPU executam treinos pelo `ngp_worker.py`, um de cada vez.
Duas execuções simultâneas invalidam a medida de VRAM: cada uma lê como
ocupação prévia o que a outra já alocou. Os scripts de calibração e validação
compartilham uma trava (`runs/.calib.lock`) que impede isso; `grid_runner.py` e
`convergencia.py` não a usam — não rode nada em paralelo com eles.

## Pipeline (GPU)

| script | o que faz | saída |
|---|---|---|
| `grid_runner.py` | monta o grid T × F × L, dispara um worker por combinação, consolida `results.csv` e `manifest.json` | `runs/exp01/`, `runs/exp02/` |
| `ngp_worker.py` | um treino: treina, avalia nas vistas de teste, mede VRAM e grava `metrics.json` | pasta de cada execução |

## Preparação dos dados

| script | o que faz |
|---|---|
| `rebase_transforms_paths.py` | torna os caminhos das imagens relativos à cena |
| `scale_transforms.py` | gera o `transforms.json` de cada fator de redução |
| `split_holdout.py` | separa 1 imagem a cada 8 para teste |
| `fixar_aabb_scale.py` | grava o `aabb_scale` escolhido nos arquivos da cena |
| `gerar_fator_intermediario.py` | gera um fator de redução fracionário (usado só no teste de viabilidade) |

## Calibração (GPU)

| script | o que faz | saída | situação |
|---|---|---|---|
| `aabb_visual_check.py` | renderiza a mesma vista para cada `aabb_scale` | `runs/aabb_check/` | Figura 2 |
| `aabb_quantitativo.py` | escolhe o `aabb_scale` por PSNR e SSIM médios | `runs/aabb_quantitativo*/` | adotado |
| `resolucao_final.py` | calibração de resolução, com detector de paginação | `runs/etapa1_final*/` | Tabela 1 |
| `convergencia.py` | curva de 30 000 iterações, avaliada a partir de snapshots | `runs/etapa15_final/`, `runs/exp02_convergence_bonsai/` | Figuras 4 e 5 |
| `justificativa_iteracoes.py` | figura de quatro painéis a partir da curva (sem GPU) | mesma pasta da curva | Figuras 4 e 5 |
| `calib_resolucao.py` | primeira calibração de resolução | `runs/etapa1_calib/` | superado por `resolucao_final.py` |
| `envelope_viabilidade.py` | configurações leve, mediana e pesada por resolução | `runs/etapa1_envelope*/` | planejamento |

## Validações (GPU)

| script | o que faz | saída |
|---|---|---|
| `variancia.py` | repete configurações idênticas para medir o ruído | `runs/exp02_variance/` |
| `analise_variancia.py` | separa ruído de falha de convergência (sem GPU) | `runs/exp02_variance/` |
| `triagem_monotonicidade.py` | procura pontos suspeitos no grid (sem GPU) | `runs/exp02_triagem/` |
| `reverificar.py` | reexecuta os suspeitos e decide | `runs/exp02_triagem/` |
| `teste_ordenacao.py` | quatro configurações de Bonsai a 20 000 iterações | `runs/exp02_ordenacao/` |
| `teste_viabilidade.py` | "o padrão não cabe e o grid cabe?" | não executado (ambiente fora do critério) |

## Análise final (sem GPU)

Reproduzem tudo de `runs/exp02_final/` a partir dos CSVs. Rode
`consolidacao_final.py` primeiro: os outros leem os `grid_{cena}.csv` que ele
gera.

| script | o que faz |
|---|---|
| `consolidacao_final.py` | médias por configuração, guia por orçamento, tabelas, fronteira com faixa de ruído |
| `pareto_bolhas.py` | fronteira com tempo na área da bolha, joelho e sweet spot |
| `sensibilidade_ruido.py` | refaz guia e sweet spot com limiares de 0,15 a 0,50 dB |
| `efeito_hiperparametros.py` | efeito de T, F e L, exp01 × exp02 |
| `figura_aabb.py` | figura da calibração do `aabb_scale` para o artigo |
| `joelho_explicado.py` | figura didática do joelho |
| `pareto_analysis.py` | análise do exp01 e análise preliminar do exp02 (`runs/exp*/analise/`) |
