# Spec — `exp02`: busca em grade em cenas reais não-limitadas

**Substitui `SPEC-ablacoes-escala.md`.** A rota de ablações mudava a pergunta de pesquisa; esta rota a preserva, trocando o dataset por um regime em que a restrição de 6 GB efetivamente se manifesta.

**Continuação de `exp01`** (grid T×F×L sobre Synthetic-NeRF, 59 execuções, concluído). Reutiliza `grid_runner.py`, `ngp_worker.py` e `pareto_analysis.py` com as extensões da §6.

---

## 1. Posicionamento

A pergunta de pesquisa **não muda**: identificar configurações de hiperparâmetros que equilibrem qualidade visual e custo computacional numa GPU de consumo com 6 GB de VRAM.

O que muda é o objeto de teste, e o `exp01` é a justificativa dessa mudança:

> O benchmark padrão da área foi medido primeiro. Constatou-se que o Synthetic-NeRF não pressiona uma GPU de 6 GB — piso de 1 745 MB, pico máximo de 2 981 MB em todo o espaço de busca, zero ocorrências de falta de memória em 54 execuções. A investigação migrou, portanto, para cenas reais não-limitadas, regime em que a restrição de hardware efetivamente se manifesta.

**Nomenclatura obrigatória:** o `exp01` é **estudo preliminar** ou **condição de referência**, nunca *baseline* do `exp02`. Os datasets, o protocolo (`nerf_compatibility`) e a divisão de teste são diferentes; os valores de PSNR **não são comparáveis entre os dois experimentos**. O baseline do `exp02` é o Instant-NGP em configuração padrão rodando na própria cena real.

### Ponto de operação alvo

O resultado mais forte possível é aquele em que **a configuração padrão não cabe nos 6 GB e configurações do grid cabem**. Isso permite escrever: *"nesta cena e nesta resolução, o Instant-NGP em configuração padrão não treina numa RTX 2060; com a configuração X, treina a Y dB"* — que é exatamente a tese original do trabalho, agora com evidência.

Toda a Etapa 1 existe para localizar esse ponto de operação.

---

## 2. Etapa 0 — Preparação do dataset

**Faça isto primeiro, em uma cena só, antes de planejar qualquer grid.** É o passo que mais consome tempo de calendário e o que menos consome GPU.

### 2.1 Escolha das cenas
Manter o paralelo de perfis do `exp01` (Lego denso / Chair regular), agora entre tipos de captura:

| Papel | Cena | Perfil | `aabb_scale` esperado |
|---|---|---|---|
| Externa | `garden` (Mip-NeRF 360) | não-limitada, céu e vegetação, grande extensão | 16 ou 32 |
| Interna | `room` ou `bonsai` (Mip-NeRF 360) | extensão menor, geometria de interior | 4 ou 8 |

O contraste externa/interna substitui o contraste Lego/Chair e continua sustentando a análise de validade externa da Seção 4.5 do projeto.

Começar por `garden`. A cena interna entra apenas se a Etapa 1 confirmar viabilidade no cronograma.

### 2.2 Conversão
O Mip-NeRF 360 traz reconstrução COLMAP, mas o Instant-NGP exige `transforms.json`:

1. Rodar `scripts/colmap2nerf.py` sobre a reconstrução existente (não refazer o COLMAP do zero).
2. Definir `aabb_scale` explicitamente. Para cenas externas 360 o valor usual é 16 ou 32; testar visualmente na GUI antes de fixar.
3. Registrar `aabb_scale`, `n_images`, resolução e fator de redução no `manifest.json`.

### 2.3 Divisão de teste
O dataset não traz split oficial de treino/teste. Adotar a convenção da literatura: **1 a cada 8 imagens vai para teste**, as demais para treino. Declarar a regra no texto (`test_split_rule` no CSV) e mantê-la idêntica em todas as execuções.

### 2.4 Protocolo
`--nerf-compatibility` **desligado**. Ele reproduz o protocolo do NeRF original, adequado ao Synthetic-NeRF e inadequado a capturas reais. Gravar a flag por linha no CSV.

### Custo
2–4 h de trabalho manual, quase nenhuma GPU.

---

## 3. Etapa 1 — Calibração do ponto de operação

**Pergunta:** em que resolução os 6 GB passam a ser restritivos?

Esta é a etapa que impede repetir o erro do `exp01`. Escolher `images_8` e concluir "não aperta" seria selecionar o resultado; escolher `images_2` porque estoura também. A resolução precisa ser *encontrada*, não presumida.

### Desenho
Configuração de rede **fixa no padrão** do Instant-NGP. Varia apenas o fator de redução do dataset, que o Mip-NeRF 360 já fornece pronto (`images_8`, `images_4`, `images_2`, mais o original).

| Fator | Resolução aproximada | Execuções |
|---|---|---|
| 8 | ~640×420 | 1 |
| 4 | ~1280×840 | 1 |
| 2 | ~2500×1680 | 1 |
| 1 (original) | — | 1, apenas se o fator 2 couber |

Cada execução: 1 000 iterações (basta para atingir o pico de alocação; não é medição de qualidade), registrando `vram_peak_mb` ou `status="oom"`.

### Critério de escolha
Selecionar o fator em que o padrão consome **entre 5 e 6 GB, ou falha por pouco**. Se os fatores fornecidos forem grosseiros demais — por exemplo, fator 4 usando 3,2 GB e fator 2 estourando —, **gerar um fator intermediário** com ImageMagick (redução por 3, por exemplo) e repetir. Duas ou três execuções extras resolvem, e a granularidade vale o custo.

Se nem a resolução original pressionar os 6 GB, os eixos seguintes são o `aabb_scale` e o número de imagens, nesta ordem.

### Custo
6 a 9 execuções curtas, ≈ 30 min de GPU.

---

## 4. Etapa 1.5 — Revalidação do número de iterações

A justificativa das 5 000 iterações (Figura 1 do projeto) foi medida na cena **Lego**, limitada e de convergência rápida. Cenas não-limitadas convergem mais devagar, e reaproveitar aquele argumento aqui seria uma extrapolação indefensável na banca.

**Uma execução** na cena `garden`, na resolução escolhida na Etapa 1, com 30 000 iterações e registro do histórico de loss e de PSNR intermediário. Refazer a Figura 1 para o novo regime e reancorar a escolha — que pode continuar sendo 5 000, ou subir para 10 000 se a curva exigir.

Esta etapa também resolve a pendência nº 4 do documento de reposicionamento.

### Custo
1 execução longa, ≈ 30–60 min de GPU.

---

## 5. Etapas 2 e 3 — Baseline e busca em grade

### 5.1 Baseline
Instant-NGP em configuração padrão, na resolução calibrada, uma execução por cena. **Se der OOM, isso é o resultado principal do trabalho** — registrar `status="oom"` e o consumo no instante da falha, e seguir para o grid.

### 5.2 Grid
Idêntico ao `exp01`, para que os *efeitos* sejam confrontáveis mesmo que os valores absolutos não sejam:

```
T ∈ {15, 17, 19}   log2_hashmap_size
F ∈ {2, 4, 8}      n_features_per_level
L ∈ {4, 8, 16}     n_levels
```

27 combinações × 1 ou 2 cenas. Número de iterações definido pela Etapa 1.5.

**Execuções com OOM são resultado, não falha.** A fronteira de viabilidade — quais configurações cabem e quais não — é metade da contribuição. O `pareto_analysis.py` já trata `status != ok` corretamente; garantir que o relatório final inclua a contagem e o mapa das combinações inviáveis.

### 5.3 Análise
Sem alteração: Fronteira de Pareto sobre PSNR × VRAM × tempo, com a projeção 2D PSNR × VRAM como resultado principal. Acrescentar uma figura nova: **mapa de viabilidade** T×F×L indicando quais combinações couberam nos 6 GB.

### Custo
2 baselines + 27 execuções (1 cena) ou 54 (2 cenas). Estimativa por execução: 2 a 4 vezes o tempo do `exp01` (84–310 s), pelo maior número de imagens e `aabb_scale` alto. **Total: 5 a 12 h de GPU.** Cabe até novembro, mas **não cabe duas vezes** — planejar para rodar uma única vez.

---

## 6. Extensões necessárias na pipeline

Nenhuma reescrita. Quatro pontos:

1. **`--nerf-compatibility` como flag explícita** no worker, gravada por linha no CSV. Padrão passa a ser desligado.
2. **`--holdout-every N`** (padrão 8): separa as vistas de avaliação e as remove do treino. Registrar `test_split_rule` no manifest.
3. **`--downsample-factor`** como eixo do runner, para a Etapa 1, apontando para o subdiretório `images_N` correspondente.
4. **Colunas novas no CSV:** `dataset`, `aabb_scale`, `n_train_images`, `n_test_images`, `image_resolution`, `downsample_factor`, `nerf_compatibility`, `test_split_rule`.

O `aabb_scale` vive no `transforms.json`, não no `network.json`. Se vier a ser variado, o worker precisa gerar uma cópia do `transforms.json` por execução — mas na rota atual ele é fixo por cena, definido na Etapa 0.

---

## 7. Cronograma

| Etapa | Trabalho manual | GPU |
|---|---|---|
| 0 — preparação do dataset | 2–4 h | — |
| 1 — calibração | 1 h | ~30 min |
| 1.5 — revalidação de iterações | 1 h | ~1 h |
| 2+3 — baseline e grid | 1 h | 5–12 h |
| Análise e figuras | 3–4 h | — |

Executar as Etapas 0 e 1 **antes** de reescrever qualquer coisa no texto do TCC: o resultado da calibração determina se a tese original volta inteira ou se é preciso recorrer ao enquadramento alternativo.

---

## 8. Riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Conversão COLMAP → `transforms.json` consumir uma semana | **Alta** | Fazer primeiro, em uma cena, antes de planejar o grid |
| Nenhuma resolução disponível pressionar os 6 GB | Média | Recorrer a `aabb_scale` e número de imagens; em último caso, retomar o enquadramento de `reposicionamento-pesquisa-ablacoes.md` |
| Todo o grid dar OOM | Média | É o que a Etapa 1 previne; se ocorrer, reduzir um fator de resolução e reexecutar |
| Orçamento de GPU estourar o cronograma | Média | Rodar só `garden` no grid completo; a cena interna entra apenas se sobrar tempo |
| Comparar PSNR do `exp02` com o do `exp01` no texto | **Alta** | Nomenclatura da §1; repetir o aviso na discussão |
| 5 000 iterações serem insuficientes em cena não-limitada | Média | Etapa 1.5 resolve antes do grid |

---

## 9. Critérios de aceitação

1. A Etapa 1 produz uma resolução em que o consumo do padrão fica entre 5 e 6 GB, ou falha — e a escolha está registrada com os dados que a sustentam.
2. A Etapa 1.5 produz uma curva de convergência para a cena real e uma justificativa numérica do número de iterações adotado.
3. Toda linha do CSV registra `nerf_compatibility`, `test_split_rule`, `aabb_scale` e `downsample_factor`.
4. O relatório final inclui o mapa de viabilidade T×F×L, com a contagem de combinações que couberam nos 6 GB.
5. Nenhuma comparação numérica direta entre PSNR do `exp01` e do `exp02` aparece no texto.
6. Existe ao menos uma configuração viável com qualidade reportável — sem isso não há fronteira de Pareto, apenas uma lista de falhas.
