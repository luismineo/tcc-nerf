# Documentação

## Por onde começar

| para… | leia |
|---|---|
| entender o trabalho, os conceitos e os achados | [defesa/GUIA-conceitos-e-achados.md](defesa/GUIA-conceitos-e-achados.md) |
| saber o que mudar no artigo | [artigo/ARTIGO-v2-propostas.md](artigo/ARTIGO-v2-propostas.md) |
| se preparar para a banca | [defesa/DEFESA-perguntas.md](defesa/DEFESA-perguntas.md) |
| ver as tabelas finais | [../runs/exp02_final/tabelas.md](../runs/exp02_final/tabelas.md) |

## Pastas

### `artigo/` — o texto do TCC

| arquivo | conteúdo |
|---|---|
| [ARTIGO-v2-propostas.md](artigo/ARTIGO-v2-propostas.md) | correções e texto proposto sobre a v1.1, referências conferidas, numeração das figuras |
| `TCC-Artigo-v1.1.pdf` | versão 1.1 do artigo, base das propostas |
| `TCC-Artigo-v1.pdf` | versão 1, base da revisão de setembro |

### `defesa/` — estudo e preparação

| arquivo | conteúdo |
|---|---|
| [GUIA-conceitos-e-achados.md](defesa/GUIA-conceitos-e-achados.md) | a história do trabalho, conceitos em linguagem direta (joelho, sweet spot, ruído, piso…), achados com números, decisões e frases a evitar |
| [DEFESA-perguntas.md](defesa/DEFESA-perguntas.md) | perguntas prováveis da banca, com a resposta e a evidência |

### `relatorios/` — o que foi medido, em ordem

| data | arquivo | conteúdo | situação |
|---|---|---|---|
| 22/08 | [RELATORIO-etapa1-calibracao.md](relatorios/RELATORIO-etapa1-calibracao.md) | primeira calibração de resolução | **superado em parte**: foi feita com `aabb_scale` = 16 e sem divisão treino/teste; a calibração válida está no ESTADO §4.2 |
| 13/09 | [ESTADO-exp02.md](relatorios/ESTADO-exp02.md) | migração para o Mip-NeRF 360, os oito defeitos encontrados, grid, piso de memória | atual |
| 13/09 | [RELATORIO-exp02-validacoes.md](relatorios/RELATORIO-exp02-validacoes.md) | ruído entre execuções, convergência do Bonsai, viabilidade abortada | atual |
| 09/10 | [RELATORIO-fechamento.md](relatorios/RELATORIO-fechamento.md) | triagem, teste de ordenação, guia por orçamento | atual |

### `metodo/` — como foi feito

| arquivo | conteúdo |
|---|---|
| [PROTOCOLO-medicao.md](metodo/PROTOCOLO-medicao.md) | regras que toda execução do exp02 segue |
| [PLANO-fechamento.md](metodo/PLANO-fechamento.md) | etapas finais com os critérios fixados **antes** de rodar |
| [GUIA-verificacoes-pre-grid.md](metodo/GUIA-verificacoes-pre-grid.md) | por que cada verificação foi feita antes do grid |
| [PIPELINE.md](metodo/PIPELINE.md) | documentação técnica: build, patches, comandos, espaço de busca, instrumentação de VRAM (escrita para o exp01; o que mudou está no topo) |

### `historico/` — superados, guardados como registro

| arquivo | o que foi | substituído por |
|---|---|---|
| [SPEC-grid-search-ngp.md](historico/SPEC-grid-search-ngp.md) | especificação do pipeline do exp01 | `metodo/PIPELINE.md` |
| `prototipo-ngp_grid_search.py` | primeiro protótipo do grid | `scripts/grid_runner.py` |
| [SPEC-ablacoes-escala.md](historico/SPEC-ablacoes-escala.md) | rota abandonada de ablações de escala | `SPEC-exp02-cena-real.md` |
| [SPEC-exp02-cena-real.md](historico/SPEC-exp02-cena-real.md) | especificação do exp02 | os relatórios e o protocolo |
| [REVISAO-artigo-v1.md](historico/REVISAO-artigo-v1.md) | revisão da v1 do artigo | `artigo/ARTIGO-v2-propostas.md` |

### `refs/` — artigos de referência

PDFs dos três trabalhos usados para conferir as citações. Não são versionados
(são de terceiros); a lista, com as versões, está em [refs/README.md](refs/README.md).

## Linha do tempo

| quando | o que aconteceu | documentos |
|---|---|---|
| 16–17/08 | exp01 no Synthetic-NeRF: 2981 MB no máximo, zero falhas por memória | `historico/SPEC-grid-search-ngp.md`, `historico/SPEC-ablacoes-escala.md` |
| 21–22/08 | migração para Garden e Bonsai; primeira calibração | `historico/SPEC-exp02-cena-real.md`, `relatorios/RELATORIO-etapa1-calibracao.md`, `metodo/GUIA-verificacoes-pre-grid.md` |
| 22/08–13/09 | correção dos defeitos, calibrações finais, grid de 56 execuções | `relatorios/ESTADO-exp02.md` |
| 13/09 | validação do ruído e convergência do Bonsai; revisão da v1 | `relatorios/RELATORIO-exp02-validacoes.md`, `historico/REVISAO-artigo-v1.md` |
| 08–09/10 | fechamento com critérios fixados antes: triagem, ordenação, guia, sweet spot | `metodo/PLANO-fechamento.md`, `metodo/PROTOCOLO-medicao.md`, `relatorios/RELATORIO-fechamento.md` |
| 09–10/10 | propostas sobre a v1.1, guia de conceitos, referências conferidas | `artigo/`, `defesa/` |
