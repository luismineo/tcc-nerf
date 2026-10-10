# Resultados

Cada pasta é a saída de um script de `scripts/`. As pastas não foram
reorganizadas porque os scripts e os `metrics.json` registram estes caminhos.
Arquivos pesados e reproduzíveis (renders, snapshots, logs) ficam fora do git;
ver `.gitignore`.

## Resultado final

| pasta | conteúdo |
|---|---|
| [`exp02_final/`](exp02_final/) | **tudo o que vai para o artigo**: tabelas (`tabelas.md`), médias por configuração (`grid_{cena}.csv`), guia por orçamento, sweet spot, figuras |

Arquivos de `exp02_final/`:

| arquivo | conteúdo | script |
|---|---|---|
| `tabelas.md` | baselines, guia por cena, substituto do padrão | `consolidacao_final.py` |
| `grid_{cena}.csv`, `guia_{cena}.csv`, `baselines.csv` | médias de todas as medições por configuração, com `n` e procedência | `consolidacao_final.py` |
| `pareto_bolhas.*`, `pareto_bolhas_{cena}.*`, `sweet_spot.csv` | fronteira com tempo na área da bolha e sweet spot | `pareto_bolhas.py` |
| `pareto_espessura.*` | fronteira com a faixa de ruído | `consolidacao_final.py` |
| `aabb_calibracao.*` | calibração do `aabb_scale`, duas cenas | `figura_aabb.py` |
| `efeito_hiperparametros.*` | efeito de T, F e L, exp01 × exp02 | `efeito_hiperparametros.py` |
| `sensibilidade_ruido.*` | conclusões com outros limiares de ruído | `sensibilidade_ruido.py` |
| `joelho_explicado.*` | figura didática do joelho | `joelho_explicado.py` |

## Dados de entrada da análise final

| pasta | conteúdo | relatório |
|---|---|---|
| `exp02/` | grid bruto: 54 combinações + 2 baselines, uma execução cada; `analise/` traz a fronteira preliminar, anterior às médias | ESTADO §4.4 |
| `exp02_baseline/` | baselines das duas cenas | ESTADO §6.1 |
| `exp02_variance/` | ruído: 2 cenas × 4 configurações × 3 repetições | VALIDAÇÕES §2 |
| `exp02_triagem/` | triagem de monotonicidade e reexecuções dos suspeitos | FECHAMENTO, Etapa 1 |
| `exp02_ordenacao/` | quatro configurações de Bonsai a 20 000 iterações | FECHAMENTO, Etapa 2 |

## Calibração do exp02 (valores adotados)

| pasta | conteúdo | uso no artigo |
|---|---|---|
| `aabb_check/garden_5000/` | comparação visual de `aabb_scale` | Figura 2 |
| `aabb_quantitativo/`, `aabb_quantitativo_bonsai/` | `aabb_scale` por PSNR e SSIM | Figura 3 (via `exp02_final/aabb_calibracao`) |
| `etapa1_final/`, `etapa1_final_bonsai/` | calibração de resolução válida | Tabela 1 |
| `etapa15_final/` | convergência de Garden, 30 000 iterações | Figura 4 |
| `exp02_convergence_bonsai/` | convergência de Bonsai, 30 000 iterações | Figura 5 |

## exp01 (Synthetic-NeRF)

| pasta | conteúdo |
|---|---|
| `exp01/` | grid de Lego e Chair, 59 execuções, `analise/` com a fronteira |
| `calib2/` | calibração do tempo de treino do exp01 (3 execuções de Lego) |

## Histórico e planejamento — fora do resultado final, guardados como registro

| pasta | o que foi | por que não entra no resultado |
|---|---|---|
| `grid/` | saída do protótipo do grid (`docs/historico/prototipo-ngp_grid_search.py`) | substituído por `grid_runner.py` |
| `etapa1_calib/` | primeira calibração de resolução, com a configuração mais pesada do grid | superestimava o consumo em ~1,5 GB (ESTADO §3, defeito 7) |
| `etapa1_default/` | configuração padrão, 1000 e 5000 iterações | anterior às correções: sem divisão treino/teste (185 imagens de treino) |
| `etapa1_confirm/` | confirmação com protocolo pesado | idem |
| `etapa1_envelope/` | configurações leve e mediana no fator 2 de Garden | sem divisão treino/teste |
| `etapa1_envelope_f2/` | leve, mediana e pesada no fator 2 de Garden, já com `aabb_scale` = 4 e divisão treino/teste | válido, mas serviu só para planejar o grid e o teste de viabilidade; o grid mede as mesmas configurações |
| `aabb_check/garden/` | primeira comparação visual de `aabb_scale`, treino curto | substituída por `aabb_check/garden_5000/` |
| `etapa15_convergencia/` | primeira curva de 30 000 iterações de Garden | feita com `aabb_scale` = 16, inaproveitável (ESTADO §3, defeito 4) |
| `etapa15_diag/` | curva de diagnóstico de 10 000 iterações | substituída por `etapa15_final/` |
| `probe_ordem/` | sondagem de diagnóstico (fora do git) | pode ser apagada sem perda |

## Logs

`logs/` guarda a saída de console das execuções longas (fora do git).

Relatórios citados: ESTADO = `docs/relatorios/ESTADO-exp02.md`; VALIDAÇÕES =
`docs/relatorios/RELATORIO-exp02-validacoes.md`; FECHAMENTO =
`docs/relatorios/RELATORIO-fechamento.md`.
