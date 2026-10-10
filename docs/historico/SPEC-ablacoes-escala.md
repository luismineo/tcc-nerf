# Spec — Ablações de escala: onde a GPU de 6 GB realmente falha

**Continuação do experimento `exp01`** (grid T×F×L, 59 execuções, concluído). Esta spec descreve três experimentos adicionais que reutilizam integralmente `grid_runner.py`, `ngp_worker.py` e `pareto_analysis.py`, com as extensões descritas na §5.

**Premissa a testar:** o pico de VRAM no treinamento do Instant-NGP é dominado por custos que escalam com a *escala da cena* (número de imagens, resolução, extensão espacial), não com a capacidade da tabela de hash. Corolário: os hiperparâmetros T, F e L só se tornam restrição efetiva em regime de `aabb_scale` alto.

**O que já está estabelecido pelo `exp01`** (a ser citado, não repetido):

| Medida | Valor |
|---|---|
| Piso irredutível de VRAM (menor modelo, 204 800 parâmetros) | 1 745 MB |
| Baseline (T19/F4/L8) | 2 000 MB (Lego) / 1 983 MB (Chair) |
| Máximo do grid (T19/F8/L16) | 2 981 MB |
| Custo marginal do encoding | ≈ 27 MB por milhão de parâmetros |
| Reprodutibilidade (configuração duplicada) | 0,017–0,063 dB / 19–28 MB |
| OOM em 54 execuções | zero |

---

## Experimento A — Parede de capacidade do modelo

**Pergunta:** em que ponto a tabela de hash, sozinha, esgota 6 GB? E o modelo afim de VRAM prevê esse ponto?

### Desenho
- Cena: Lego (mantém comparabilidade com o `exp01`).
- L fixo em 16, `per_level_scale` derivado pela mesma regra do `exp01`.
- `T ∈ {19, 20, 21, 22, 23, 24}` × `F ∈ {2, 8}` = 12 execuções.
- 5000 iterações, `--test-stride 4`, mesmas métricas.

### Predição registrada *antes* de rodar
Pelo modelo afim (1,7 GB + 27 MB por milhão de parâmetros), o teto de 6 GB corresponde a ≈ 165 M parâmetros de encoding. **Registrar a predição no `manifest.json` antes da execução** e comparar com o OOM observado. Acertar a parede com um modelo ajustado fora da faixa de calibração é resultado publicável; errar também é, desde que declarado como predição prévia.

### Saídas específicas
- Coluna `n_encoding_params` obrigatória em todas as linhas (já existe no worker).
- Figura: `vram_peak_mb` × `n_encoding_params`, com a reta ajustada sobre os dados do `exp01` (0,2 M–48,8 M) **extrapolada** até o OOM, e os pontos novos sobrepostos. Esta é a figura que demonstra o poder preditivo.
- Runs com `status="oom"` são resultado, não falha: registrar `vram_peak_device_mb` no instante da falha.

### Custo estimado
12 execuções, das quais várias falham cedo por OOM. ≈ 45 min de GPU.

---

## Experimento B — Os três eixos de escala da cena

**Pergunta:** o piso de 1,7 GB é composto de quê, e qual eixo o move mais?

Configuração de rede **fixa** em todas as execuções: o baseline T19/F4/L8. A variável é a cena, não o modelo. Cena: Lego.

### B1 — Número de imagens de treino
`n_train_images ∈ {25, 50, 100}` (subconjunto do `transforms_train.json`, amostrado uniformemente). 3 execuções.

Hipótese: relação aproximadamente linear, já que as imagens ficam residentes em VRAM. Este é o eixo apontado nas issues do repositório como causa de OOM em placas de 8 GB.

### B2 — Resolução das imagens
`resolution ∈ {200, 400, 800}` (downsample por fator 4, 2 e 1). 3 execuções.

Hipótese: relação quadrática no lado linear (pixels ∝ lado²). Se B1 e B2 juntos explicarem a maior parte do piso, a decomposição está fechada.

**Cuidado:** PSNR não é comparável entre resoluções diferentes. Reportar as métricas de qualidade apenas dentro de cada resolução; o eixo de interesse aqui é VRAM.

### B3 — Extensão espacial (`aabb_scale`)
`aabb_scale ∈ {1, 2, 4, 8, 16}` sobre a **mesma cena Lego**, com todo o resto idêntico. 5 execuções.

Este é o probe controlado do mecanismo: os dados de entrada não mudam em nada, apenas o volume que o modelo se compromete a representar. Isola o custo do `aabb_scale` de qualquer confundidor de dataset. Espera-se:
- custo direto modesto em VRAM (cascata da grade de ocupação, um nível por duplicação);
- **queda de PSNR**, porque a mesma tabela de hash passa a cobrir até 4096× mais volume, elevando as colisões.

A queda de qualidade aqui é o resultado, não um artefato: ela mede quanto de capacidade da tabela é consumido puramente por extensão espacial.

### Saídas específicas
- Colunas novas: `n_train_images`, `image_resolution`, `aabb_scale`, `n_density_grid_cascades`.
- Tabela de decomposição do piso: contribuição estimada de cada eixo em MB.

### Custo estimado
11 execuções, ≈ 40 min de GPU.

---

## Experimento C — Interação (o experimento decisivo)

**Pergunta:** o efeito de T e F sobre qualidade e memória **aumenta** quando a cena é espacialmente extensa?

Este é o experimento que sustenta a tese. Os dois anteriores são descritivos; este é comparativo.

### Desenho
Subgrid reduzido `T ∈ {15, 17, 19}` × `F ∈ {2, 8}`, L fixo em 16 — 6 combinações — replicado em **dois regimes**:

| Regime | Cena | `aabb_scale` |
|---|---|---|
| Controle | Lego (Synthetic-NeRF) | 1 |
| Tratamento | cena real não-limitada | 16 (ou o valor que o dataset exigir) |

O regime de controle **já existe no `exp01`** — as 6 combinações estão medidas. Só é preciso rodar o regime de tratamento: 6 execuções.

### Escolha da cena real
Duas opções, em ordem de preferência:

1. **`data/nerf/fox`**, que acompanha o repositório. Vantagens: já está em disco, ~50 imagens, `aabb_scale` já definido no `transforms.json` (conferir o valor), sem necessidade de COLMAP. Desvantagem: não tem divisão de teste — é preciso separar 1 a cada 8 imagens como conjunto de avaliação, prática padrão na literatura de cenas reais.
2. **Mip-NeRF 360** (`garden` ou `bicycle`), com o protocolo canônico de 1 a cada 8 vistas para teste. Vantagem: comparabilidade direta com a literatura. Desvantagem: download grande e imagens em resolução alta que provavelmente exigem downsample para caber nos 6 GB — o que, aliás, é ele próprio um dado a reportar.

Começar por fox. Se sobrar tempo no cronograma, acrescentar 360.

### Métrica de interesse
Não é o PSNR absoluto (que não é comparável entre datasets), e sim a **amplitude do efeito dentro de cada regime**:

```
efeito_T = PSNR(T=19) − PSNR(T=15), com F e L fixos
```

A hipótese é que `efeito_T` e `efeito_F` sejam substancialmente maiores no regime de tratamento. Reportar os dois lado a lado é o resultado central do trabalho.

### Custo estimado
6 execuções mais preparação do dataset, ≈ 1 h de GPU e 1–2 h de trabalho manual.

---

## 5. Extensões necessárias na pipeline

Nenhuma reescrita: quatro pontos de extensão.

1. **`grid_runner.py`** — aceitar `--aabb-scale`, `--n-train-images`, `--downsample-factor` como eixos do grid, além de T/F/L. O produto cartesiano já é genérico; basta ampliar o dicionário `GRID` e a geração do `run_tag`.
2. **`ngp_worker.py`** — `aabb_scale` não vive no `network.json`, e sim no `transforms.json` da cena. O worker precisa gerar uma cópia do `transforms.json` por run, com o campo alterado, e apontar o `--scene` para ela. Mesma lógica de subamostragem para `n_train_images`.
3. **Divisão de teste para cenas sem split** — flag `--holdout-every N` (padrão 8), que separa as vistas de avaliação e as remove do treino. Registrar `test_split_rule` no manifest.
4. **`--nerf-compatibility` DESLIGADO para cenas reais.** No `exp01` ele esteve ligado nas 59 execuções, reproduzindo o protocolo do NeRF original. Para fox e Mip-NeRF 360 isso é inadequado. **Consequência: PSNR de cenas reais não é comparável ao de Lego/Chair.** Este é o principal risco de erro de interpretação desta fase — o Experimento C compara *amplitudes de efeito dentro* de cada regime justamente para contornar isso. Gravar a flag por linha no CSV e repetir o aviso na discussão do TCC.

---

## 6. Custo total e encaixe no cronograma

| Experimento | Execuções | GPU |
|---|---|---|
| A — parede de capacidade | 12 | ~45 min |
| B — eixos de escala | 11 | ~40 min |
| C — interação | 6 | ~1 h |
| **Total** | **29** | **~2h30** |

Mais 2–3 h de trabalho de pipeline e preparação de dataset. Cabe com folga na janela de setembro do cronograma, e não depende de reexecutar nada do `exp01`.

---

## 7. Critérios de aceitação

1. O Experimento A produz ao menos uma execução com `status="oom"`, e a predição registrada previamente é comparada ao valor observado no texto.
2. A figura `vram_peak_mb` × `n_encoding_params` cobre três ordens de grandeza de contagem de parâmetros.
3. O Experimento B permite escrever uma frase da forma: "do piso de 1,7 GB, aproximadamente X MB são atribuíveis às imagens residentes, Y MB à resolução e Z MB ao contexto CUDA".
4. O Experimento C entrega `efeito_T` e `efeito_F` nos dois regimes, com a diferença entre regimes maior que a reprodutibilidade medida no `exp01` (0,063 dB) — caso contrário, a conclusão é que não há interação, o que também é um resultado, desde que a potência do teste seja discutida.
5. Toda execução de cena real registra `nerf_compatibility=false` e `test_split_rule` no CSV.

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Fox não tem divisão de teste padronizada; PSNR não comparável à literatura | Usar 1 a cada 8 vistas, declarar a regra, comparar apenas amplitudes internas |
| `aabb_scale` alto em cena limitada (B3) pode degradar a reconstrução a ponto de o PSNR virar ruído | É o efeito esperado; se colapsar completamente, reduzir a faixa para {1, 2, 4, 8} |
| Mip-NeRF 360 em resolução alta pode não caber em 6 GB | Isso é resultado, não obstáculo: registrar o fator de downsample mínimo viável |
| Interação nula no Experimento C | Resultado válido; exige discussão de potência e faixa de `aabb_scale` testada |
| Cronograma (defesa em novembro) | Executar A e B primeiro (1h25 de GPU, sem preparação de dataset); C é o único que depende de trabalho manual |
