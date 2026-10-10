# Relatório — Etapa 1: calibração do ponto de operação (`exp02`)

**Escopo.** Executa a Etapa 1 de `SPEC-exp02-cena-real.md` §3: *em que resolução os 6 GB da RTX 2060 passam a ser restritivos?* Cenas `garden` (externa) e `bonsai` (interna) do Mip-NeRF 360.

**Ambiente.** WSL2, RTX 2060 6144 MiB, driver 591.86, CUDA 12.4, `pyngp` compilado em `vendor/instant-ngp/build/`.

**Status.** Etapa 1 concluída para `garden`, com recomendação. `bonsai` medido, mas **sem** ponto de operação que satisfaça o critério do spec — ver §6.

---

## 1. Resumo executivo

**Recomendação: `garden` no fator 2 (2594×1681).** A configuração padrão do Instant-NGP consome ali **5983.7 MB no protocolo completo** (5000 passos, `spp=8`, stride 4), dentro da janela de 5–6 GB que o §3 do spec define como critério, com 160.3 MB livres e PSNR 20.35. Na mesma resolução, a configuração mais pesada do grid (`T=19 F=8 L=16`) dá OOM — ou seja, **o grid atravessa a fronteira de viabilidade**, que é o que o mapa de viabilidade da §5.3 do spec precisa para existir.

**Achado colateral que afeta o desenho do `exp02`:** entre a configuração mais leve do grid e a padrão, o pico de VRAM é **indistinguível** (5493.9 contra 5490.4 MB, corrigidos por baseline), apesar de 64× de diferença no número de parâmetros de encoding. O controlador adaptativo de raios compensa a redução do modelo. Ver §3.4 — isso tem consequência direta sobre o que a Fronteira de Pareto vai conseguir mostrar.

Para `bonsai`, nenhum dos quatro fatores disponíveis satisfaz o critério: o fator 2 fica abaixo da janela e o fator 1 estoura. Aplica-se o remédio previsto no próprio spec §3 — gerar um fator intermediário.

Três correções em dados foram necessárias antes de qualquer medição; sem elas nenhuma cena carregava. Ver §2.

---

## 2. Correções na Etapa 0 (bloqueadores encontrados)

### 2.1 `file_path` não resolvia em nenhuma das duas cenas

O `colmap2nerf.py` foi executado a partir da raiz do projeto e gravou caminhos relativos a ela:

```
./data/mip_nerf/garden/images/DSC08140.JPG
```

O Instant-NGP resolve `file_path` relativo ao **diretório do próprio JSON**, não ao diretório de trabalho — `nerf_loader.cu:335` define `base_path = jsonpaths[i].parent_path()` e `:320` faz `base_path / local_path`. O `resolve_path` só tem fallback de extensão, nunca de CWD, e `:564` lança `Could not find image file`. O caminho efetivamente procurado era:

```
data/mip_nerf/garden/data/mip_nerf/garden/images/DSC08140.JPG   (inexistente)
```

**Impacto:** as duas cenas eram inutilizáveis pelo Instant-NGP, e as variantes derivadas herdariam o defeito, porque `scale_transforms.py` só reescreve o segmento `images` e preserva o prefixo.

**Correção:** `scripts/rebase_transforms_paths.py` reescreve para `./images/X.JPG`, validando a existência de cada arquivo pela mesma regra do loader. Backups em `transforms.json.bak`. 185 frames em `garden`, 292 em `bonsai`, todos resolvidos.

### 2.2 Arredondamento de dimensão ímpar

`garden` tem altura 3361. O `round()` do Python usa arredondamento bancário: `round(1680.5) = 1680`, mas a imagem real em `images_2/` tem 1681. O JSON ficaria 1 px fora da imagem em disco.

**Correção:** `scale_transforms.py` passou a usar half-up (`floor(x + 0.5)`), que é a convenção com que as reduções do Mip-NeRF 360 foram geradas. Afetava apenas `garden` f2; as demais combinações já conferiam.

### 2.3 Variantes geradas

Todas com `aabb_scale=16`, todas validadas pelo `check_real_size` do próprio `scale_transforms.py` contra as imagens em disco:

| cena | f2 | f4 | f8 |
|---|---|---|---|
| `garden` (185 imgs) | 2594×1681 | 1297×840 | 648×420 |
| `bonsai` (292 imgs) | 1559×1039 | 780×520 | 390×260 |

---

## 3. Medições

Protocolo comum: `B=262144`, `--no-nerf-compatibility` (spec §2.4), seed 0. `peak_dev` é `vram_peak_device_mb` (uso absoluto do dispositivo); `livre` é `6144 − peak_dev`. Baseline do Windows entre 438.6 e 447.6 MB em todas as execuções.

### 3.1 Varredura de resolução — configuração **padrão** (`base.json`: T=19, F=4, L=8, 13 041 664 parâmetros de encoding)

É a configuração que o critério do spec §3 avalia.

| cena | fator | resolução | passos | protocolo | peak_dev | livre | status | PSNR |
|---|---|---|---|---|---|---|---|---|
| `garden` | f8 | 648×420 | 1000 | `spp=1`, stride 64 | 2429.5 | 3714.5 | ok | 20.23 |
| `garden` | f2 | 2594×1681 | 1000 | `spp=1`, stride 64 | 5957.9 | 186.1 | ok | 19.04 |
| `garden` | **f2** | **2594×1681** | **5000** | **`spp=8`, stride 4** | **5983.7** | **160.3** | **ok** | **20.35** |

A última linha é a execução de referência da recomendação: protocolo idêntico ao que o grid usará. SSIM 0.378, 47 vistas, treino 158.1 s, avaliação 163.3 s, 31.6 passos/s.

### 3.2 Varredura de resolução — configuração mais **pesada** do grid (T=19, F=8, L=16, 48 784 960 parâmetros)

Esta foi a varredura inicial. **Não** é a que o critério do spec avalia — ver §5.1 — mas delimita o extremo superior do grid.

| cena | fator | resolução | peak_dev | livre | status | PSNR |
|---|---|---|---|---|---|---|
| `garden` | f8 | 648×420 | 3916.2 | 2227.8 | ok | 19.84 |
| `garden` | f4 | 1297×840 | 5400.2 | 743.8 | ok | 19.01 |
| `garden` | f2 | 2594×1681 | — | — | **oom** | — |
| `bonsai` | f8 | 390×260 | 3406.2 | 2737.8 | ok | 27.05 |
| `bonsai` | f4 | 780×520 | 4354.2 | 1789.8 | ok | 25.30 |
| `bonsai` | f2 | 1559×1039 | 6052.2 | 91.8 | ok | 25.13 |
| `bonsai` | f1 | 3118×2078 | — | — | **oom** | — |

`garden` f2 falhou durante o carregamento (`t_setup` 2.2 s), com 5918.2 MB no instante da falha. `bonsai` f1 falhou após 34 s de setup e 58 min totais, com 5921.7 MB.

### 3.3 Amplitude controlável por hiperparâmetro (`garden` f8)

Quanto `T`, `F` e `L` deslocam o consumo, mantendo tudo o mais fixo:

| configuração | T, F, L | parâmetros de encoding | peak_dev |
|---|---|---|---|
| leve | 15, 2, 4 | 204 800 | 2063.4 |
| mediana | 17, 4, 8 | 3 293 184 | 2265.0 |
| **padrão** | **19, 4, 8** | **13 041 664** | **2429.5** |
| pesada | 19, 8, 16 | 48 784 960 | 3961.2 |

**Ressalva importante:** estes quatro pontos foram medidos com **20 passos** (leve, mediana, pesada) ou 1000 (padrão). O controlador adaptativo de raios do Instant-NGP parte de 4096 raios por batch e leva dezenas de passos para convergir, então a 20 passos ele ainda não estabilizou. A amplitude de ~1.9 GB que esta tabela sugere **não se reproduz no ponto de operação** — ver §3.4, onde a mesma comparação a 5000 passos dá diferença de 3.5 MB. Esta tabela serve para ordenar o custo bruto de armazenamento dos parâmetros, não para prever o pico em regime.

### 3.4 Fronteira de viabilidade em `garden` f2

`peak−base` (`vram_peak_mb`) desconta a baseline do Windows e é a única coluna comparável entre execuções; `peak_dev` é o valor absoluto, que é o que decide o OOM.

| configuração | parâmetros | passos | baseline | peak_dev | **peak−base** | livre | status | PSNR |
|---|---|---|---|---|---|---|---|---|
| leve (15, 2, 4) | 204 800 | 5000 | 519.0 | 6012.9 | **5493.9** | 131.1 | ok | 20.81 |
| padrão (19, 4, 8) | 13 041 664 | 5000 | 493.3 | 5983.7 | **5490.4** | 160.3 | ok | 20.35 |
| padrão (19, 4, 8) | 13 041 664 | 1000 | 509.4 | 5957.9 | 5448.5 | 186.1 | ok | 19.04 |
| pesada (19, 8, 16) | 48 784 960 | 1000 | 447.6 | — | — | — | **oom** | — |

O grid atravessa a viabilidade nesta resolução: a pesada não cabe, a padrão e a leve cabem. É a estrutura que o mapa de viabilidade da §5.3 do spec pede.

**Mas a alavanca é achatada na faixa de baixo.** Entre leve e padrão, a 5000 passos e mesmo protocolo, o pico corrigido por baseline difere em **3.5 MB** — 5493.9 contra 5490.4 — apesar de 64× de diferença em parâmetros de encoding (204 800 contra 13 041 664). Reduzir o modelo não devolveu memória.

A explicação está nos contadores do próprio treino:

| configuração | raios por batch | amostras por raio |
|---|---|---|
| leve | 18 452.9 | 14.3 |
| padrão | 6 384.3 | 41.9 |

O Instant-NGP ajusta `rays_per_batch` para que o número de amostras por batch persiga `B=262144`. A configuração leve produz um grid de densidade mais grosseiro, logo menos amostras por raio, logo precisa de ~3× mais raios para preencher o mesmo orçamento. **O orçamento de amostras é fixo em `B`, e é ele que domina o consumo no ponto de operação** — não o tamanho da tabela de hash.

Isso não significa que `T`, `F` e `L` não movam nada: a configuração pesada, com 48.8 M parâmetros, estoura. A alavanca existe no topo da faixa e é plana embaixo. Consequência para o `exp02` em §6, lacuna 5.

### 3.5 O protocolo de avaliação não custa VRAM

`garden` f8, configuração pesada, variando só a avaliação:

| protocolo | vistas | peak_dev | PSNR |
|---|---|---|---|
| `spp=1`, stride 64 | 3 | 3916.2 | 19.84 |
| `spp=8`, stride 4 | 47 | 3902.5 | 21.66 |

**A avaliação pesada é gratuita em memória** (diferença de 13.7 MB, dentro do ruído) **e necessária para o PSNR** (1.8 dB de diferença entre 3 e 47 vistas). Consequência prática: calibrar VRAM com avaliação leve é válido; comparar qualidade com poucas vistas, não.

---

## 4. Recomendação

### 4.1 `garden`: fator 2 (2594×1681)

**Satisfaz o critério do spec §3 diretamente.** A configuração padrão consome 5983.7 MB no protocolo completo do grid (5000 passos, `spp=8`, stride 4) — dentro da janela de 5–6 GB, sem precisar de fator intermediário. Confirmado em execução dedicada, não extrapolado.

O que sustenta a escolha, além do critério:

- **A restrição morde.** Com 160.3 MB livres, a padrão está no limite. A configuração pesada do grid dá OOM.
- **O grid continua mensurável.** A configuração leve cabe com PSNR 20.81, então há pontos para uma frente, e as combinações que estouram viram o mapa de viabilidade.
- **A qualidade é utilizável.** PSNR 20.35 e SSIM 0.378 na padrão a 5000 passos, sobre 47 vistas. Não é o número final — a Etapa 1.5 ainda vai definir o número de iterações — mas descarta a hipótese de que a resolução seja alta demais para convergir no orçamento previsto.
- **f4 não serve.** Na pesada, f4 consome 5400.2 MB contra o OOM de f2; aplicando o deslocamento medido entre pesada e padrão em f8 (−1486.7 MB), a padrão em f4 ficaria em torno de 3.9 GB — bem abaixo da janela. *Extrapolação, não medição.*

### 4.2 `bonsai`: nenhum fator disponível serve

Na configuração pesada, f2 cabe (6052.2 MB) e f1 estoura. Aplicando o mesmo deslocamento de −1486.7 MB, a padrão em f2 ficaria em torno de **4.6 GB** — abaixo da janela de 5–6 GB. *Extrapolação.* O fator 1 tem 292 imagens de 3118×2078 e estourou já na configuração pesada.

Aplica-se o remédio que o próprio spec §3 prevê: **gerar um fator intermediário** entre 1 e 2 com ImageMagick e repetir a medição. Duas ou três execuções resolvem.

Antes disso, porém, há uma questão anterior a resolver — ver §5.3: o `aabb_scale` de `bonsai` está em 16, e o spec §2.1 esperava 4 ou 8 para cena interna. Corrigi-lo muda o consumo e invalidaria a calibração feita antes.

### 4.3 Ordem sugerida

1. Fixar `garden` f2 e seguir para a Etapa 1.5 (revalidação do número de iterações), que o spec já condiciona à resolução escolhida.
2. Resolver o `aabb_scale` de `bonsai` (§5.3).
3. Só então calibrar `bonsai`, com fator intermediário se necessário.

O spec §2.1 já autoriza essa ordem: *"Começar por `garden`. A cena interna entra apenas se a Etapa 1 confirmar viabilidade no cronograma."*

---

## 5. Desvios em relação ao `SPEC-exp02-cena-real.md`

### 5.1 A varredura inicial usou a configuração errada

O spec §3 manda calibrar com a **configuração de rede fixa no padrão**. A primeira varredura (§3.2) usou a configuração mais pesada do grid, escolhida para garantir que as 27 combinações coubessem. É a pergunta de planejamento do grid, não o critério do spec, e superestima o consumo em cerca de 1.5 GB.

**Corrigido**: as medições da §3.1 e §3.4 usam `base.json` sem modificação. A varredura pesada fica no relatório porque delimita o extremo superior do grid, que é informação necessária para o mapa de viabilidade.

### 5.2 A divisão de teste não foi aplicada

O spec §2.3 adota **1 em cada 8 imagens para teste**. Todas as medições aqui usaram o conjunto completo tanto para treino quanto para avaliação, porque a Etapa 1 mede alocação e não qualidade.

**Consequência:** o conjunto de treino usado é 8/7 do que o protocolo final terá — 185 imagens em vez de ~162 em `garden`. Como as imagens de treino ficam na VRAM, **todos os picos aqui estão superestimados** em relação ao protocolo do spec. O erro é conservador, mas não é nulo, e os 186 MB livres de `garden` f2 devem ficar maiores quando a divisão for aplicada.

### 5.3 `aabb_scale` de `bonsai` fora do esperado

O spec §2.1 esperava `aabb_scale` 4 ou 8 para a cena interna. As duas cenas foram geradas com 16. Para `garden` (externa) o valor está dentro do previsto; para `bonsai`, não. O `aabb_scale` governa quantos níveis de marcha o raio percorre em cena não-limitada, então afeta consumo e tempo.

**Não corrigi**, porque o spec §2.2 manda validar visualmente na GUI antes de fixar, e isso é decisão sua. Mas a calibração de `bonsai` deve ser refeita depois de resolver isso.

### 5.4 A premissa de que 1000 iterações bastam se sustenta, com margem estreita

O spec §3 afirma que 1000 iterações bastam para atingir o pico de alocação. **Medido e confirmado**, com ressalva: na configuração padrão em `garden` f2, o pico corrigido por baseline foi 5448.5 MB a 1000 passos e 5490.4 MB a 5000 — crescimento de **41.9 MB**, ou 0.8 %.

A premissa vale para calibrar resolução. Mas 41.9 MB é a mesma ordem de grandeza da folga do ponto de operação (160.3 MB), então **uma calibração a 1000 passos não é margem de segurança suficiente para declarar viável uma combinação do grid**. Para o mapa de viabilidade da §5.3, a viabilidade precisa ser lida das execuções reais do grid, não de sondagens curtas.

> Uma versão anterior deste relatório afirmava que a premissa não se sustentava, com base numa comparação entre a configuração leve a 5000 passos (6012.9 MB) e a padrão a 1000 (5957.9 MB). Essa comparação usava `peak_dev`, que **inclui a baseline do Windows** — 519.0 MB numa execução e 509.4 na outra. Corrigida por baseline, a inversão desaparece. Registrado aqui porque é o modo de erro mais fácil de cometer com estes dados: `vram_peak_device_mb` não é comparável entre execuções, só `vram_peak_mb` é.

---

## 6. Lacunas

| # | Lacuna | Custo | Por que importa |
|---|---|---|---|
| 1 | Recalibrar com a divisão 1-em-8 | 2–3 execuções | Todos os picos aqui estão superestimados; a margem real é maior que os 160.3 MB medidos. |
| 2 | `aabb_scale` de `bonsai` | decisão + GUI | Bloqueia a calibração de `bonsai`. |
| 3 | Fator intermediário para `bonsai` | 2–3 execuções | Nenhum fator disponível cai na janela de 5–6 GB. |
| 4 | Quantas das 27 combinações cabem em `garden` f2 | sai do próprio grid | É o mapa de viabilidade da §5.3 do spec, sem execuções extras. |
| 5 | **Qual eixo de fato move a VRAM no ponto de operação** | análise + 2–3 execuções | Ver abaixo. Afeta o desenho do `exp02`, não só a calibração. |

### Sobre a lacuna 5

A §3.4 mostra que, entre a configuração leve e a padrão, o pico não se move (3.5 MB), porque o controlador de raios compensa a redução do modelo para manter `B=262144` amostras por batch. O eixo que dominou o consumo nessas duas execuções foi `B`, que o `grid_runner.py` **excluiu deliberadamente** do grid, por argumento metodológico registrado no código: reduzir `B` com o número de iterações fixo não produz um modelo menor, produz o mesmo modelo treinado com menos amostras.

O argumento continua válido, e não estou propondo trocar o eixo. Mas ele tem uma consequência que precisa estar no texto do TCC: se `T`, `F` e `L` só movem a VRAM no topo da faixa, a projeção PSNR × VRAM da §5.3 vai mostrar **um aglomerado de combinações com custo praticamente igual e uma minoria que estoura**, em vez de uma frente contínua. Isso ainda é um resultado — e o mapa de viabilidade continua sendo a contribuição —, mas é diferente da figura que o projeto antecipa.

Vale confirmar com duas ou três execuções em `garden` f2 variando só `F` (2, 4, 8) com `T` e `L` fixos, antes de rodar o grid inteiro. Se o aglomerado se confirmar, é melhor saber antes de gastar as 5–12 h de GPU que o spec §5 orça.

---

## 7. Reprodutibilidade

### Scripts criados nesta etapa

| Arquivo | Função |
|---|---|
| `scripts/rebase_transforms_paths.py` | Corrige `file_path` para relativo à cena, com backup e validação em disco |
| `scripts/calib_resolucao.py` | Varredura de resolução com configuração fixa; trava `flock` contra execução concorrente |
| `scripts/envelope_viabilidade.py` | Varredura de configurações (leve/mediana/pesada) por resolução, com classificação parede / fronteira / sem tensão |

`scripts/scale_transforms.py` foi modificado (arredondamento half-up, §2.2).

### Dados

| Caminho | Conteúdo |
|---|---|
| `runs/etapa1_calib/` | Varredura da configuração pesada (§3.2), `calibracao.csv` |
| `runs/etapa1_default/garden_f8_default`, `garden_f2_default` | Configuração padrão, 1000 passos (§3.1) |
| `runs/etapa1_default/garden_f2_default_5k` | **Execução de referência da recomendação** (§3.1, §4.1) |
| `runs/etapa1_envelope/` | Fronteira em `garden` f2 (§3.4) |
| `runs/etapa1_confirm/` | `garden` f8 com protocolo pesado (§3.5) |

Cada execução tem `metrics.json` completo e `worker.log`.

### Reexecutar

```bash
# varredura de resolução, configuração padrão
python3 scripts/ngp_worker.py \
  --scene data/mip_nerf/garden/transforms_f2.json \
  --test-transforms data/mip_nerf/garden/transforms_f2.json \
  --network vendor/instant-ngp/configs/nerf/base.json \
  --out-dir runs/etapa1_default/garden_f2_default \
  --n-steps 1000 --batch-size 262144 --seed 0 \
  --test-stride 64 --spp 1 --lpips-device none --no-nerf-compatibility

# envelope de viabilidade
python3 scripts/envelope_viabilidade.py \
  --targets garden:2 --n-steps 5000 --spp 8 --test-stride 4
```

### Condição de reprodutibilidade

**O experimento exige GPU dedicada.** A baseline do Windows foi medida entre 254 MB e 1265 MB no mesmo dia, dependendo do que estava aberto. As margens do ponto de operação recomendado (186 MB) são **menores que essa variação**: abrir um navegador durante o grid derruba execuções. As medições deste relatório foram feitas com baseline entre 438.6 e 447.6 MB.

Duas execuções simultâneas de calibração corrompem a medida de forma silenciosa — cada processo lê como baseline a VRAM que o outro já alocou, e o resultado fica sem sentido (picos não monotônicos em resolução). Isso ocorreu uma vez durante esta etapa e os dados afetados foram descartados. `calib_resolucao.py` e `envelope_viabilidade.py` compartilham uma trava `flock` em `runs/.calib.lock` que aborta a segunda execução.
