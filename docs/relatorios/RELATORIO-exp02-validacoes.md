# Relatório — validações complementares do exp02

Três validações executadas em 2026-09-13 para fechar lacunas metodológicas do
grid do `exp02`. Não substituem nem alteram os resultados anteriores: todas as
saídas foram gravadas em diretórios novos.

| # | validação | status | diretório |
|---|---|---|---|
| 1 | caracterização da variância | **executada** — 24 execuções | `runs/exp02_variance/` |
| 2 | curva de convergência do `bonsai` | **executada** — 30 000 iterações | `runs/exp02_convergence_bonsai/` |
| 3 | fronteira de viabilidade | **não executada** — ambiente fora de critério | — |

---

## 1. Metodologia comum

**Parâmetros fixos.** `garden` fator 2 (2594×1681, `aabb_scale=4`), `bonsai`
fator 2 (1559×1039, `aabb_scale=8`), divisão retida `holdout_every=8` (161/24 e
255/37), 5000 iterações, `B=262144`, `nerf_compatibility` desabilitado, seed 0,
`spp=8`, todas as vistas de teste avaliadas, LPIPS em CPU.

**Execução estritamente sequencial.** Nunca dois treinamentos simultâneos. Os
scripts compartilham uma trava `flock` em `runs/.calib.lock`; duas execuções
concorrentes invalidam a medida de VRAM, porque cada processo leria como linha de
base o que a outra já alocou.

**Linha de base.** Cinco amostras antes de cada execução, com média e desvio
gravados por linha. Acima de 900 MB o script aguarda 60 s e reavalia, até três
tentativas; persistindo, prossegue mas marca `baseline_alta=True`. Nenhum
resultado foi ajustado para compensar a linha de base.

**Medida comparativa.** `vram_peak_mb` (pico menos linha de base). A ocupação
absoluta `vram_peak_device_mb` é registrada apenas como contexto — ela inclui o
consumo do Windows, que variou de 254 a 1457 MB ao longo do projeto e não é
comparável entre execuções.

**Alteração de código.** Um script novo (`variancia.py`) e um de análise
(`analise_variancia.py`). Nenhuma definição de métrica ou protocolo foi alterada.

### 1.1 Inconsistência encontrada e tratada

A especificação do experimento indicava `T=19, F=2, L=16` como "baseline padrão
do Instant-NGP". Esse é o padrão declarado **no artigo** de Müller et al. (2022),
mas o `configs/nerf/base.json` distribuído no repositório — que é o que todas as
execuções do `exp02` usaram — traz **T=19, F=4, L=8**.

São pontos diferentes do grid. Em `garden`, `T19 F2 L16` rende 20,661 dB e **não
está na fronteira de Pareto**; o `base.json` rende 21,054 dB e está. Como a
discrepância de 0,245 dB que motivou esta validação foi observada no `base.json`,
os dois foram executados, rotulados `base_json` e `padrao_artigo`. A escolha não
foi resolvida em silêncio.

### 1.2 Regressão corrigida antes de executar

A correção do `per_level_scale` (feita anteriormente, para derivar
`N_max = 2048 × aabb_scale`) passou a exigir `run["aabb_scale"]` em
`grid_runner.write_network_json`, quebrando quatro chamadores:
`calib_resolucao.py`, `envelope_viabilidade.py`, `teste_viabilidade.py` e o
`variancia.py` novo. Detectada por teste de fumaça antes da série. Os dados já
produzidos estão íntegros — foram gerados antes da mudança — mas reexecutar
aqueles scripts falharia. Corrigido nos quatro, com revalidação do
`grid_runner --dry-run`.

---

## 2. Validação 1 — variância entre execuções idênticas

### 2.1 Desenho

Quatro configurações por cena, três repetições cada, **24 execuções**. Todos os
parâmetros controláveis mantidos constantes, **inclusive a seed** — o objetivo é
medir o não-determinismo residual sob controle máximo, que vem da ordem de
redução de operações atômicas em CUDA, não da inicialização.

As configurações vizinhas foram determinadas a partir de
`runs/exp02/analise/pareto.csv`, escolhendo o ponto da fronteira mais próximo da
candidata em PSNR e VRAM:

| cena | candidata | vizinha | Δ PSNR no grid | Δ VRAM |
|---|---|---|---|---|
| `garden` | T15 F8 L4 | T19 F4 L4 | +0,340 dB | +64 MB |
| `bonsai` | T19 F2 L8 | T17 F4 L8 | **+0,016 dB** | +72 MB |

### 2.2 Resultado: dois fenômenos distintos

| cena | config | PSNR médio | desvio | amplitude | ampl. VRAM |
|---|---|---|---|---|---|
| garden | candidata (T15 F8 L4) | 20,3854 | 0,042 | 0,0761 | 18,1 MB |
| garden | vizinha (T19 F4 L4) | 20,7410 | 0,102 | 0,1867 | 38,0 MB |
| garden | padrao_artigo (T19 F2 L16) | 20,8538 | 0,130 | 0,2439 | 121,6 MB |
| garden | base_json (T19 F4 L8) | 20,3819 | 1,067 | **1,8803** | 23,8 MB |
| bonsai | base_json | 28,6114 | 0,109 | 0,1975 | 95,2 MB |
| bonsai | candidata (T19 F2 L8) | 27,6817 | 0,066 | 0,1263 | 64,5 MB |
| bonsai | padrao_artigo | 28,7136 | 0,012 | 0,0228 | 97,9 MB |
| bonsai | vizinha (T17 F4 L8) | 27,6955 | 0,060 | 0,1134 | 107,4 MB |

**Ruído típico: amplitude de 0,023 a 0,244 dB**, mediana de 0,157 dB. A
discrepância original de 0,245 dB que motivou esta validação está no topo dessa
faixa — **é ruído, confirmado**.

**Anomalia: `garden/base_json/rep2`.** Uma execução em 24 terminou **1,81 dB
abaixo da mediana** de suas gêmeas:

| rep | PSNR | SSIM | LPIPS | desvio entre vistas |
|---|---|---|---|---|
| 1 | 20,9647 | 0,4934 | 0,5596 | 1,46 |
| **2** | **19,1503** | **0,4373** | **0,6622** | **2,20** |
| 3 | 21,0306 | 0,4961 | 0,5577 | 1,40 |

As três métricas concordam e o desvio entre as 24 vistas subiu 50 % — **o modelo
convergiu para uma solução pior, não é erro de leitura**. Linha de base (834 MB
contra 824 e 824) e vazão (32,9 contra 33,5 e 34,2) estavam normais. Não há
`status` anômalo nem aviso: a execução terminou como `ok`.

Isto é **instabilidade de convergência**, fenômeno distinto do ruído de medição:

- o ruído típico (~0,15 dB) afeta a ordenação de pontos próximos na fronteira;
- a falha ocasional produz um ponto que **aparenta ser dominado sem o ser**.

Taxa observada: 1 em 24 execuções (4 %). Num grid de 54, isso implica
aproximadamente **2 pontos afetados**, e nada no `results.csv` do `exp02` os
distingue.

### 2.3 Tratamento do outlier

Descartar a execução sem critério seria seleção de dados; mantê-la sem sinalizar
inflaria o ruído de `garden` de 0,24 para 1,88 dB e tornaria quase tudo
indistinguível — conservador ao ponto de esvaziar a análise.

Critério adotado, declarado em `analise_variancia.py`: outlier é a execução cujo
desvio da mediana do próprio grupo excede **3× a mediana das amplitudes de todos
os grupos** (0,157 dB → limiar de 0,470 dB). O limiar vem do conjunto, não do
grupo, para não ser circular — um grupo com outlier tem amplitude grande
justamente por causa dele. Apenas `garden/base_json/rep2` foi marcado. **O CSV
bruto preserva as 24 execuções**; a marcação vive na análise.

O ruído de referência para distinguibilidade é a **maior amplitude observada sem
outliers: 0,2439 dB** (`garden/padrao_artigo`). Adota-se o pior caso, não a
média.

### 2.4 Pares distinguíveis e não distinguíveis

| cena | par | Δ PSNR | Δ VRAM | veredito |
|---|---|---|---|---|
| bonsai | **candidata vs vizinha** | **+0,0138** | −52,1 MB | **NÃO distinguível** |
| bonsai | base_json vs padrao_artigo | −0,1022 | −53,8 MB | **NÃO distinguível** |
| bonsai | candidata vs padrao_artigo | −1,0318 | −288,7 MB | distinguível |
| bonsai | base_json vs candidata | +0,9297 | +235,0 MB | distinguível |
| garden | base_json vs padrao_artigo | +0,1438 | +10,1 MB | **NÃO distinguível** |
| garden | padrao_artigo vs vizinha | +0,1128 | +275,1 MB | **NÃO distinguível** |
| garden | candidata vs vizinha | −0,3556 | +14,6 MB | distinguível |
| garden | base_json vs candidata | +0,6122 | +270,6 MB | distinguível |

O par `bonsai` candidata vs vizinha era o caso decisivo: **0,014 dB de diferença
contra 0,244 dB de ruído**. `T19 F2 L8` e `T17 F4 L8` são estatisticamente
indistinguíveis em qualidade, e a segunda custa 52 MB a mais — a escolha entre
elas deve ser feita pela VRAM, não pelo PSNR.

O par `garden` padrao_artigo vs vizinha é mais notável: **indistinguíveis em
qualidade, mas separados por 275 MB de VRAM**. É exatamente o tipo de par que a
Fronteira de Pareto existe para revelar.

---

## 3. Validação 2 — curva de convergência do `bonsai`

### 3.1 Desenho

Mesmo protocolo do `garden`: configuração padrão (`base.json`), 30 000 iterações,
loss a cada 100 passos, PSNR e SSIM a cada 2000 sobre as 37 vistas retidas com
`spp=8`. Avaliação feita a partir de snapshots, em fase separada — alternar entre
treino e teste durante o treinamento reinicializaria o grid de densidade e
contaminaria a curva.

### 3.2 Resultado: 5000 iterações **não** se sustentam em `bonsai`

| passo | 2000 | 4000 | 10000 | 20000 | 30000 |
|---|---|---|---|---|---|
| PSNR | 27,270 | 28,349 | 29,214 | 29,610 | **29,990** |
| SSIM | 0,8266 | 0,8576 | 0,8792 | 0,8881 | 0,8947 |
| % do final | 90,9 % | 94,5 % | 97,4 % | 98,7 % | 100 % |

| | `garden` | `bonsai` |
|---|---|---|
| joelho (< 0,1 dB/1000 it) | **4000** | **10 000** |
| % do PSNR final em ~4000 | 98,9 % | **94,5 %** |
| ganho de ~4000 até 30 000 | +0,24 dB | **+1,64 dB** |
| custo desse ganho | 5,1× | 4,9× |

O ganho marginal do `bonsai` só cruza o limiar de 0,1 dB/1000 iterações em
**10 000 passos**, contra 4000 no `garden`. A 5000 iterações restam **1,6 dB** na
mesa. **Os dados não sustentam 5000 para `bonsai` pelo mesmo critério que os
sustenta para `garden`.**

### 3.3 A curva não é monotonicamente decrescente

O ganho marginal **aumenta** ao cruzar 20 000 passos, nas duas cenas:

| cena | ganho médio 10k–20k | ganho médio 20k–24k | razão | queda de loss no limiar |
|---|---|---|---|---|
| garden | 0,0047 dB/1000it | 0,0103 | 2,2× | 5,1 % |
| bonsai | 0,0396 dB/1000it | 0,0717 | 1,8× | 11,7 % |

A causa é o cronograma do otimizador no `base.json`: `decay_start: 20000`,
`decay_interval: 10000`, `decay_base: 0.33` — o primeiro decaimento da taxa de
aprendizado. O loss confirma independentemente do PSNR.

Isso tem consequência metodológica: **"o ganho tornou-se marginal" medido antes de
20 000 passos é enganoso**, porque há uma melhoria programada esperando ali. Em
`garden` o efeito é desprezível em termos absolutos (0,025 dB no intervalo); em
`bonsai` vale 0,23 dB só naquele trecho.

### 3.4 Implicação sobre o grid já executado

As 27 execuções de `bonsai` do `exp02` rodaram com ~1,6 dB de qualidade ainda
disponível. A ordenação relativa provavelmente se preserva — todas sofreram o
mesmo truncamento — mas duas ressalvas se aplicam:

1. os valores absolutos de PSNR do `bonsai` estão subestimados;
2. configurações de maior capacidade convergem mais devagar e podem estar sendo
   penalizadas desproporcionalmente pelo truncamento precoce.

Não há como quantificar (2) sem reexecutar o grid do `bonsai` com mais iterações.

---

## 4. Validação 3 — fronteira de viabilidade: não executada

### 4.1 Critério de abortagem

O teste exige que a configuração padrão exceda a memória disponível enquanto uma
configuração leve permaneça utilizável. A janela entre as duas, medida no
`exp02`, é de **403 MB em `garden`**. A preparação já existia: fator 1,62
(3202×2075, 185 imagens, split 161/24, 4081 MB de imagens de treino na VRAM).

Amostragem da linha de base imediatamente antes, GPU ociosa e sem nenhum
aplicativo CUDA:

```
683  683  682  678  696  722  721  704  753  730  740  720   MiB
```

Média **709 MB**, faixa de **75 MB**, com tendência de alta ao longo da janela de
24 s (678 → 753). Disponível: 5435 MB. Previsões: configuração padrão 5724 MB
(não caberia), configuração leve 5321 MB (caberia com **114 MB** de folga).

**114 MB de margem contra 75 MB de oscilação medida no próprio ambiente.** O
resultado seria determinado pelo estado do Windows durante a execução, não pela
configuração. Abortado de forma limpa, sem executar.

### 4.2 O que não foi feito, deliberadamente

Não foram encerrados processos do usuário, não foi alterada configuração do
sistema operacional, e a resolução não foi ajustada repetidamente até produzir o
caso desejado. Qualquer uma dessas ações fabricaria o resultado em vez de
medi-lo.

### 4.3 Condição para executar

Linha de base estável abaixo de ~400 MB (já foram medidos 254 MB nesta máquina em
outra ocasião). Com base em 300 MB o disponível sobe para 5844 MB, a configuração
padrão excederia por 120 MB e a leve teria 523 MB de folga — margem confortável
frente à oscilação observada. São 3 execuções, cerca de 15 minutos.

### 4.4 Um resultado que o aborto produz

A linha de base não é uma constante que se mede uma vez: **é um processo**.
Oscilou 75 MB em 24 segundos, sem aplicação CUDA alguma, e variou de 254 a
1457 MB ao longo do projeto. Numa placa de 6 GB compartilhada com o desktop,
**mais de 10 % da memória está comprometida antes do experimento começar**, e a
fração não é previsível. Isso é, por si só, um dado sobre viabilizar NeRF em
hardware de consumo, e merece registro no texto independentemente de o teste vir
a ser executado.

---

## 5. Anomalias e limitações

1. **Uma execução em 24 (4 %) falhou em convergir** sem sinalizar erro.
   Extrapolando, ~2 pontos do grid de 54 podem estar afetados.
2. **`n=3` por configuração** é suficiente para ordem de grandeza do ruído, não
   para inferência estatística. Não foram calculados intervalos de confiança.
3. **O ruído foi medido em 4 das 27 configurações por cena.** Configurações de
   capacidade muito diferente podem ter ruído diferente; a extrapolação de
   0,244 dB para todo o grid é suposição, não medição.
4. **A curva de convergência do `bonsai` tem `n=1`.** Dado o ruído medido, o
   joelho em 10 000 tem incerteza não caracterizada.
5. **A linha de base esteve entre 808 e 897 MB durante a série de variância**,
   acima do ideal, mas estável e registrada por execução. Afeta
   `vram_peak_device_mb`, não `vram_peak_mb` nem o PSNR.
6. **LPIPS em CPU** — não afeta VRAM, mas domina o tempo por execução.

---

## 6. Implicações para o TCC

### 6.1 O que os novos resultados sustentam

**A escolha de 5000 iterações para `garden`.** Reforçada: a 4000 passos o PSNR já
é 98,9 % do valor de 30 000, e o ganho marginal está abaixo do limiar desde ali.

**A existência de pares de igual qualidade e custo diferente.** Em `garden`,
`T19 F2 L16` e `T19 F4 L4` são indistinguíveis em PSNR (Δ 0,113 dB contra ruído
de 0,244) mas separados por **275 MB**. É o argumento central do trabalho, agora
com o ruído caracterizado.

**A diferença entre as cenas.** `bonsai` reconstrói melhor e converge mais
devagar; `garden` é o caso difícil e satura antes. O contraste
externa/interna previsto na Seção 2 do artigo se confirma.

### 6.2 O que precisa ser enfraquecido

**"5000 iterações" não pode ser apresentado como validado para as duas cenas.**
Está validado para `garden` e **contrariado** para `bonsai`, que precisaria de
~10 000. O texto deve declarar que o `bonsai` rodou truncado e que seus valores
absolutos de PSNR estão subestimados em ~1,6 dB.

**Nenhuma diferença de PSNR menor que ~0,25 dB pode ser usada para ordenar
configurações.** Isso invalida, especificamente:

| afirmação anterior | situação |
|---|---|
| `bonsai`: `T19 F2 L8` é preferível a `T17 F4 L8` (Δ 0,016 dB) | **não sustentável** — indistinguíveis; a escolha deve ser pela VRAM (−52 MB) |
| `garden`: `T19 F2 L8` economiza VRAM com −0,27 dB de perda | **não sustentável como perda** — está dentro do ruído; a economia de 6,2 % permanece válida |
| ordenação fina entre pontos vizinhos da fronteira | **não sustentável** em geral |

**A Fronteira de Pareto tem espessura.** Pontos separados por menos de 0,25 dB
não estão ordenados; formam uma faixa. A figura principal deveria indicar isso,
por exemplo com uma banda de ±0,25 dB, sob pena de sugerir precisão que os dados
não têm.

**Toda execução do grid tem `n=1`.** Com 4 % de falhas de convergência
observadas, pontos isolados abaixo da tendência devem ser tratados como
suspeitos, não como medida.

### 6.3 Diferenças da fronteira que permanecem maiores que o ruído

Com ruído de referência de 0,244 dB, continuam reportáveis:

- `garden`: `base_json` vs `candidata` (+0,612 dB, +271 MB) e `candidata` vs
  `vizinha` (−0,356 dB);
- `bonsai`: todos os pares envolvendo `candidata` ou `vizinha` contra
  `base_json` ou `padrao_artigo` (0,92 a 1,03 dB);
- no grid completo, o intervalo de qualidade de cada cena (6,7 dB em `garden`,
  7,0 dB em `bonsai`) e o custo do extremo caro (+1070 MB por +0,18 dB em
  `bonsai`) — esta última diferença, sendo menor que o ruído em qualidade, deve
  ser apresentada como **"não compra qualidade mensurável"**, o que fortalece o
  argumento em vez de enfraquecê-lo.

### 6.4 Recomendação de ordem

1. Declarar o ruído de ±0,25 dB na metodologia e aplicá-lo a toda a discussão.
2. Corrigir a afirmação sobre iterações do `bonsai`.
3. Reexecutar o grid do `bonsai` com 10 000 iterações, se houver orçamento
   (~2 h), ou declarar o truncamento como limitação.
4. Executar a validação 3 apenas se a linha de base permitir.
