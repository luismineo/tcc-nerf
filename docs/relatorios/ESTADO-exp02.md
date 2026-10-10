# Estado do exp02 — o que foi medido, o que quebrou, o que falta

Consolida a migração do Synthetic-NeRF para cenas reais do Mip-NeRF 360, de
2026-08-21 a 2026-09-13. Documento de referência: serve para retomar o trabalho
sem reler o histórico e para sustentar as escolhas no texto do TCC.

---

## 1. Resumo em uma tela

**Fechado.** `garden` e `bonsai`, fator de redução 2, `aabb_scale` 4 e 8
respectivamente, divisão retida 1-em-8, 5000 iterações. Grid completo executado:
56/56 com sucesso, 4h04m, **zero OOM**. Fronteira de Pareto calculada.

**O resultado que não veio.** Nenhuma das 54 combinações falhou por memória, então
o mapa de viabilidade — que o `SPEC-exp02` §5.2 chama de "metade da contribuição"
— não existe. A causa é estrutural: o piso de memória é dominado pelas imagens de
treino, que `T`, `F` e `L` não tocam.

**O risco aberto.** O baseline executado duas vezes na mesma configuração e seed
diferiu **0,25 dB** — magnitude comparável às diferenças que a fronteira precisa
distinguir. Ver §6.1.

---

## 2. Decisões fechadas

| decisão | `garden` | `bonsai` | como foi decidida |
|---|---|---|---|
| resolução | fator 2 — 2594×1681 | fator 2 — 1559×1039 | maior fator viável; nenhum caiu na janela de 5–6 GB do spec |
| `aabb_scale` | **4** | **8** | varredura quantitativa com PSNR/SSIM em vistas retidas |
| divisão treino/teste | 161 / 24 | 255 / 37 | `holdout_every=8` (convenção LLFF) |
| iterações | 5000 | 5000 (extrapolado) | curva de convergência de 30 000 passos em `garden` |
| `nerf_compatibility` | desligado | desligado | cenas reais não-limitadas |

`per_level_scale` é derivado por cena como `N_max = 2048 × aabb_scale`, o que faz
`L=8` reproduzir o valor que o Instant-NGP calcularia do `base.json` intocado —
garantindo que o baseline coincida com um ponto do grid. Ver §4.6.

---

## 3. Defeitos encontrados

Oito, dos quais **sete eram silenciosos**: rodariam até o fim e produziriam CSV,
gráfico e fronteira, todos errados.

| # | defeito | como se manifestava | correção |
|---|---|---|---|
| 1 | `file_path` relativo à raiz do projeto | falha alta — nenhuma cena carregava | `rebase_transforms_paths.py` |
| 2 | arredondamento bancário nas dimensões | `garden` f2 com `h=1680` contra imagem de 1681 | half-up em `scale_transforms.py` |
| 3 | `--nerf-compatibility` ligado por padrão | zerava `cone_angle_constant`, inadequado a cena 360 | padrão invertido nos dois scripts |
| 4 | `aabb_scale=16` nunca validado | floaters; PSNR caindo com o treino | varredura quantitativa; 4 e 8 |
| 5 | sem divisão treino/teste | PSNR medido em vistas de treino (20,35 dB contra ~15,9 reais) | `split_holdout.py` |
| 6 | comentário sobre `per_level_scale` falso para `aabb≠1` | baseline e grid com resolução mais fina 4× diferente | `N_max = 2048 × aabb_scale` |
| 7 | calibração feita com a config pesada do grid | superestimava o consumo em ~1,5 GB | refeita com `base.json` |
| 8 | `status=ok` em execução que paginou para RAM do host | `bonsai` f1 "coube" a 1,0 passo/s | detector em `resolucao_final.py` |

O defeito 4 é o caso exemplar: uma verificação visual de ~10 minutos que não foi
feita custou uma execução de 30 000 iterações inteiramente inaproveitável, além de
invalidar a calibração de resolução que dependia dela.

### 3.1 Verificações que voltaram limpas

Registrar isso importa — mostra que o método distingue defeito de ruído.

| verificação | resultado |
|---|---|
| referencial (`scale`/`offset`/`up`) depende do split? | não — constantes fixas |
| pose de uma imagem muda entre conjuntos? | não — diferença 0,000000 |
| `render_aabb` / `aabb` mudam entre splits? | não — idênticos |
| a referência renderizada é a foto certa? | sim — 59,2 dB contra ~13 dB das vizinhas |
| 1000 passos bastam para o pico de VRAM? | sim — cresce só 41,9 MB até 5000 |
| avaliação pesada (`spp=8`) custa VRAM? | não — 13,7 MB, dentro do ruído |

As duas últimas autorizam calibrar VRAM com execuções curtas e avaliação leve, o
que barateou todo o resto.

---

## 4. Resultados medidos

### 4.1 `aabb_scale` (5000 iterações, split retido, fator 2)

| aabb | `garden` PSNR / SSIM | `bonsai` PSNR / SSIM |
|---|---|---|
| 2 | 14,39 / 0,309 | 14,06 / 0,446 |
| **4** | **20,95 / 0,493** | 20,80 / 0,699 |
| 8 | 18,79 / 0,406 | **28,60 / 0,865** |
| 16 | 15,33 / 0,321 | 14,11 / 0,449 |
| 32 | 17,30 / 0,363 | — |

O ótimo **difere por cena**. O valor herdado (16) custava 5,6 dB em `garden` e
14,5 dB em `bonsai`. A triagem visual eliminou corretamente 2 e 16, mas **errou o
desempate entre 4 e 8 em `garden`** — julgamento feito sobre uma vista a 800×520
contra 24 vistas a resolução plena.

### 4.2 Resolução (config padrão, `aabb` validado, split retido)

| cena | fator | resolução | veredito | pico−base | PSNR |
|---|---|---|---|---|---|
| garden | 8 | 648×420 | viável | 1322,4 | 22,53 |
| garden | 4 | 1297×840 | viável | 2053,3 | 21,35 |
| **garden** | **2** | **2594×1681** | **viável** | **4311,8** | 20,99 |
| garden | 1 | 5187×3361 | falha (RAM do host) | — | — |
| bonsai | 8 | 390×260 | viável | 1329,8 | 29,87 |
| bonsai | 4 | 780×520 | viável | 1682,3 | 28,82 |
| **bonsai** | **2** | **1559×1039** | **viável** | **3388,3** | 28,64 |
| bonsai | 1 | 3118×2078 | degradado (paginação) | 4746,2 | 28,47 |

PSNR **cai** com o aumento da resolução, a iterações fixas — mais pixels, mesma
supervisão. Resolução e número de iterações estão acoplados.

### 4.3 Convergência (`garden` f2, 30 000 iterações)

| passo | 2000 | 5000 | 10000 | 20000 | 30000 |
|---|---|---|---|---|---|
| PSNR | 20,77 | ~20,99 | 21,10 | 21,15 | 21,19 |
| SSIM | 0,458 | ~0,490 | 0,512 | 0,525 | 0,536 |

A 5000 iterações o PSNR é **99 %** do valor de 30 000. Ir a 30 000 compra
**+0,24 dB por 5,1× o custo** (grid de 1,5 h para 7,6 h). O ganho marginal cai
abaixo de 0,1 dB/1000 iterações em **4000**.

### 4.4 Grid (56 execuções, 4h04m, zero OOM)

| cena | VRAM | PSNR | baseline |
|---|---|---|---|
| garden | 3916,7 – 5253,8 MB | 14,80 – 21,47 dB | 21,13 dB @ 4320,0 MB |
| bonsai | 2904,6 – 5038,6 MB | 22,52 – 29,52 dB | 28,59 dB @ 3428,0 MB |

**10 configurações são não-dominadas nas duas cenas** — a recomendação não depende
da cena. 35 das 54 ficam dentro da tolerância de −2 dB. Três casos em que LPIPS e
PSNR discordam de sinal.

Maiores economias dentro da tolerância: `garden T15 F8 L4` (−0,80 dB, −7,7 % de
VRAM, **−47 % de tempo**) e `bonsai T19 F2 L8` (−0,89 dB, −9,3 %, −12,1 %).

No extremo caro, `bonsai` de `T19 F4 L16` para `T19 F8 L16`: **+1070 MB compram
+0,18 dB**.

### 4.5 A alavanca contra o piso

Decomposição do pico de VRAM no fator 2:

| cena | imagens de treino | leve | padrão | pesada | **janela útil** | alavanca total |
|---|---|---|---|---|---|---|
| garden | 2676,8 MB | 1239,9 | 1643,2 | 2577,0 | **403 MB** | 1337 MB |
| bonsai | 1575,7 MB | 1328,9 | 1852,3 | 3462,9 | **523 MB** | 2134 MB |

As colunas leve/padrão/pesada são a parcela **não-imagem** — a única que `T`, `F`
e `L` movem. A "janela útil" (padrão − leve) é o que separa "não cabe" de "cabe",
e é ~3× menor que a alavanca total (leve − pesada).

O piso de imagens é `n_imagens × w × h × 4 B` e **não responde a hiperparâmetro
nenhum**. Em resolução cheia ele sozinho excede a placa: 10 707 MB em `garden`,
6303 MB em `bonsai`, contra 6144 MB disponíveis.

### 4.6 `per_level_scale` derivado de `aabb_scale`

O `base.json` não define `per_level_scale`; quem preenche é o Instant-NGP
(`src/testbed.cu:4248`):

```
b = exp( log(2048 · aabb_scale / base_resolution) / (L − 1) )
```

Com `aabb_scale` ausente (Synthetic-NeRF) o ngp assume 1 e a fórmula devolve
exatamente 2,0 — por isso o comentário do `grid_runner.py` valia no `exp01` e
passou a mentir no `exp02`. Valores atuais: `garden` (aabb 4) → L=4 b=8,000;
L=8 b=2,438; L=16 b=1,516. `bonsai` (aabb 8) → 10,079 / 2,692 / 1,587.

---

## 5. Achados metodológicos

**O orçamento de amostras domina o consumo, não o tamanho do modelo.** Sob
`aabb_scale=16`, a config leve (204 800 parâmetros) e a padrão (13 041 664)
tiveram pico indistinguível — 3,5 MB de diferença. O controlador adaptativo
compensa: modelo mais grosseiro gasta menos amostras por raio e o ngp aumenta os
raios por batch para perseguir `B`. Com `aabb_scale=4` o efeito some e a alavanca
reaparece, mas o mecanismo continua valendo.

**`aabb_scale` controla a taxa de supervisão, não só a geometria.** Em `garden`
com aabb 4 o treino usa 21 692 raios/batch a 12,2 amostras/raio; com aabb 8, 7910
raios a 34,0 amostras. A orçamento fixo de `B`, caixa compacta entrega ~3× mais
raios por iteração.

**O driver mente sobre caber.** Em WSL2 o driver NVIDIA pagina para a RAM do
sistema em vez de falhar. `bonsai` f1 terminou com `status=ok` e pico "dentro" da
placa, mas as imagens a 4 B/px (6303 MB) excediam o pico medido (4746 MB) e a
vazão caiu de 34 para 1,0 passo/s. Dois detectores independentes pegam isso: o
aritmético e o de vazão.

**`vram_peak_device_mb` não é comparável entre execuções.** Inclui a ocupação do
Windows, que variou de **254 a 1457 MB**. Só `vram_peak_mb` (pico − base) compara.
Chegou-se a reportar uma inversão inexistente por confundir os dois.

**A linha de base não é constante, é um processo.** Amostrada 10 vezes em 20 s sem
nenhum app CUDA: 702, 667, 677, 643, 661, 658, 643, 643, 643, 638 MiB — oscila
~64 MB sozinha, e derivou 192 MB em um minuto. Numa placa de 6 GB compartilhada
com o desktop, **mais de 10 % da memória está comprometida antes do experimento
começar**. Isso é, por si só, um resultado sobre viabilizar NeRF em hardware de
consumo.

**Duas execuções simultâneas destroem a medida.** Cada processo lê como linha de
base a VRAM que o outro já alocou; o resultado não é ruidoso, é sem sentido (dá
para ver f8 medindo mais que f4). Ocorreu duas vezes; daí a trava `flock`.

---

## 6. Pendências e riscos

### 6.1 Variância entre execuções não foi caracterizada — risco alto

O baseline foi executado duas vezes, com a **mesma configuração e a mesma seed**:

| | `runs/exp02_baseline` | `runs/exp02` | diferença |
|---|---|---|---|
| garden PSNR | 20,8894 | 21,1346 | **+0,245 dB** |
| garden VRAM | 4314,5 | 4320,0 | +5,5 MB |
| bonsai PSNR | 28,6817 | 28,5920 | −0,090 dB |
| bonsai VRAM | 3304,1 | 3428,0 | +123,9 MB |

**0,245 dB de variação entre execuções idênticas é da mesma ordem das diferenças
que a fronteira precisa resolver** — a maior economia dentro da tolerância em
`garden` é −0,80 dB, e o ponto `T19 F2 L8` está a −0,27 dB do baseline, ou seja,
dentro do ruído. O grid rodou com `SEEDS = [0]`, uma execução por combinação, sem
estimativa de variância.

O Instant-NGP tem não-determinismo de CUDA independente da seed, então isso é
esperado — mas precisa ser **medido e declarado**, não ignorado. Bastariam 3
repetições de 2 ou 3 configurações (~30 min) para estimar o desvio e decidir quais
diferenças da fronteira são reportáveis.

### 6.2 O mapa de viabilidade não existe

A §3.3 do artigo promete o mapeamento de combinações inviáveis. Zero OOM em 54
execuções. Duas saídas: reformular a promessa para "amplitude de VRAM liberada
pelos hiperparâmetros", ou produzir o mapa num fator intermediário. O teste do
fator 1,62 foi preparado e **abortou pelo próprio guarda** — a linha de base subiu
de 590 para 782 MB entre a verificação e a execução. Ver §6.4.

### 6.3 A curva de convergência só existe para `garden`

Adotar 5000 iterações em `bonsai` é extrapolação. Defensável (a cena converge mais
facilmente: 28,68 dB já no baseline), mas é extrapolação e precisa ser declarada.

### 6.4 O teste de fronteira de viabilidade está bloqueado por ambiente

Fator 1,62 gerado (3202×2075, 185 imagens, split 161/24). Previsões com base de
590 MB: padrão 5724 MB (estoura), leve 5321 MB (cabe, 233 MB de folga). A janela é
~400 MB, menor que a variação observada da linha de base. Exige derrubar a base
para ~300 MB — já foi medido 254 MB nesta máquina.

### 6.5 Menores

- `exp01` e `exp02` não têm PSNR comparável (protocolo, split e cenas diferem).
- Os `aabb_scale` ótimos diferem entre cenas, logo o `per_level_scale` também —
  efeitos de `T`/`F`/`L` comparáveis **dentro** de cada cena, valores absolutos de
  `b` não entre elas.
- O estimador de tempo do `grid_runner.py` usa steps/s do `exp01` (Lego) e está
  descalibrado: anuncia 4h17m para o que medimos como ~3,2 h.
- O eixo PSNR × tempo é mais frágil que PSNR × VRAM: `steps_per_s` variou por
  contenção com o Windows ao longo das 4 h.

---

## 7. Inventário

### Scripts criados

| arquivo | função |
|---|---|
| `rebase_transforms_paths.py` | corrige `file_path` para relativo à cena |
| `split_holdout.py` | divisão treino/teste por holdout periódico |
| `fixar_aabb_scale.py` | grava o `aabb_scale` escolhido nos JSONs da cena |
| `gerar_fator_intermediario.py` | gera fator de redução fracionário com Pillow |
| `calib_resolucao.py` | varredura de resolução com config fixa |
| `envelope_viabilidade.py` | varredura leve/mediana/pesada por resolução |
| `aabb_quantitativo.py` | escolha de `aabb_scale` por PSNR/SSIM |
| `resolucao_final.py` | Etapa 1 com detector de degradação |
| `convergencia.py` | curva de loss e PSNR em duas fases, via snapshots |
| `justificativa_iteracoes.py` | figura de decisão do número de iterações |
| `teste_viabilidade.py` | testa "padrão não cabe / grid cabe" |

Modificados: `grid_runner.py` (cenas, caminhos, `per_level_scale`, colunas,
trava de cena não calibrada), `ngp_worker.py` (padrão de `nerf_compatibility`,
metadados de procedência), `scale_transforms.py` (arredondamento).

### Dados

| caminho | conteúdo |
|---|---|
| `runs/exp02/` | grid completo, `results.csv`, `analise/` com a fronteira |
| `runs/exp02_baseline/` | baselines das duas cenas |
| `runs/etapa1_final*/` | Etapa 1 refeita, CSV, gráfico, folha de contato |
| `runs/aabb_quantitativo*/` | escolha de `aabb_scale`, CSV e gráfico |
| `runs/etapa15_final/` | convergência, curvas e figura de justificativa |
| `runs/aabb_check/garden_5000/` | comparação visual de `aabb_scale` |
| `runs/teste_viabilidade/` | teste do fator 1,62 (abortado, ver §6.4) |

Backups: `transforms.json.bak` (rebase) e `*.bak-aabb16` (mudança de `aabb_scale`).

---

## 8. Próximos passos sugeridos

1. **Caracterizar a variância** (§6.1) — 3 repetições de 2–3 configurações. É o
   item de maior risco: sem ele não se sabe quais diferenças da fronteira são
   reportáveis.
2. **Decidir sobre o mapa de viabilidade** (§6.2) — reformular a promessa do texto
   ou retomar o teste do fator 1,62 com a base da GPU controlada.
3. **Curva de convergência para `bonsai`** (§6.3), se houver orçamento.
4. **Aplicar a revisão do artigo** — ver `REVISAO-artigo-v1.md`.
