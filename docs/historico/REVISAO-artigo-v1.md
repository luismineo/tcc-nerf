# Revisão do artigo v1 — alinhamento com os dados medidos

Confronta `docs/artigo/TCC-Artigo-v1.pdf` (19 p.) com o que foi medido até
2026-09-13. Cobre inconsistências de valor, onde entram as figuras novas e que
ajustes de texto a nova direção exige. **Não trata da Seção 4 (resultados)**, que
fica para a entrega seguinte.

---

## 1. A inconsistência que puxa todas as outras

**A Tabela 1 (p. 7–8) foi medida sob três premissas que o próprio artigo depois
abandona.** Ela veio da primeira varredura de calibração, feita com:

| premissa da Tabela 1 | o que o artigo declara | o que foi usado de fato |
|---|---|---|
| configuração **mais pesada** do grid (T=19 F=8 L=16) | "Instant-NGP em sua configuração padrão, sem variação dos hiperparâmetros" (p. 7) | `base.json` intocado (T=19 F=4 L=8) |
| `aabb_scale = 16` | a Seção 2.1 conclui **4** para Garden | 4 (Garden) e 8 (Bonsai) |
| **sem** divisão treino/teste (185 e 292 imagens) | "uma a cada oito imagens reservada para teste" (p. 10) | 161/24 e 255/37 |

As três empurram o consumo para cima, e o efeito visível é grave: **a tabela diz
que Garden no fator 2 deu OOM** — e o fator 2 é exatamente a resolução escolhida
para o experimento. Com a configuração padrão, `aabb_scale=4` e o split aplicado,
ele consome 4882,8 MB e roda normalmente.

### Tabela 1 — valores corrigidos

Configuração padrão (`base.json`), 5000 iterações, `aabb_scale` validado, divisão
retida 1-em-8, todas as vistas de teste avaliadas com `spp=8`.

| Cena | Fator | Resolução | Treino | Teste | Status | Pico − base (MB) | Base (MB) | Dispositivo (MB) | PSNR |
|---|---|---|---|---|---|---|---|---|---|
| garden | 8 | 648×420 | 161 | 24 | OK | 1322,4 | 582,6 | 1905,0 | 22,53 |
| garden | 4 | 1297×840 | 161 | 24 | OK | 2053,3 | 558,3 | 2611,6 | 21,35 |
| **garden** | **2** | **2594×1681** | 161 | 24 | **OK** | **4311,8** | 571,0 | 4882,8 | 20,99 |
| garden | 1 | 5187×3361 | — | — | **Falha (RAM do host)** | — | — | — | — |
| bonsai | 8 | 390×260 | 255 | 37 | OK | 1329,8 | 1427,5 | 2757,3 | 29,87 |
| bonsai | 4 | 780×520 | 255 | 37 | OK | 1682,3 | 1428,7 | 3111,0 | 28,82 |
| **bonsai** | **2** | **1559×1039** | 255 | 37 | **OK** | **3388,3** | 1427,8 | 4816,1 | 28,64 |
| bonsai | 1 | 3118×2078 | 255 | 37 | **Degradado (paginação)** | 4746,2 | 1380,0 | 6126,2 | 28,47 |

Três observações que a tabela antiga não comportava:

**A coluna que compara é `Pico − base`, não `Dispositivo`.** A linha de base do
Windows variou entre 254 e 1457 MB ao longo dos experimentos; o valor absoluto do
dispositivo não é comparável entre execuções. Recomendo manter as três colunas e
dizer isso na legenda.

**Garden fator 1 não é OOM de VRAM.** O processo foi morto pelo OOM killer do
kernel Linux com 7,57 GB de RSS, em 82% do carregamento das imagens — esgotou a
RAM do sistema antes de chegar à placa. É um limite diferente e vale nomear.

**Bonsai fator 1 não é OOM nem sucesso.** Terminou com status `ok`, mas as
imagens de treino a 4 B/px somam 6303 MB contra um pico medido de 4746 MB —
aritmeticamente impossível — e a vazão caiu de ~34 para **1,0 passo/s**. O driver
paginou para a RAM do host em vez de falhar. Sugiro a categoria "degradado" e uma
nota de rodapé explicando o critério.

---

## 2. Ordem metodológica invertida (Seção 2)

O artigo calibra **resolução primeiro** (Tabela 1) e `aabb_scale` depois (2.1).
A dependência é a oposta: `aabb_scale` altera o número de cascatas da grade de
ocupação e o `per_level_scale` derivado, logo altera o consumo de VRAM. Calibrar
resolução com `aabb_scale=16` produziu exatamente a tabela que o texto depois
invalida.

**Sugestão:** inverter as subseções — 2.1 `aabb_scale`, 2.2 resolução — e abrir a
2.2 dizendo que a resolução foi calibrada *com o `aabb_scale` já fixado*. Isso
também torna a narrativa mais forte: mostra que a ordem das decisões foi
deliberada, não acidental.

---

## 3. Inconsistências pontuais de valor

| # | Local | Problema | Correção |
|---|---|---|---|
| 1 | p. 12 | "Müller et al. fixam L=16, T=19 e F=2 como configuração padrão… correspondem ao vértice superior do espaço de busca e ao baseline" | O `configs/nerf/base.json` do repositório tem **L=8, F=4, T=19**. Ver §4 abaixo — é a correção mais delicada |
| 2 | p. 12 | "reduções em qualquer um dos três implicam redução **proporcional** no consumo de VRAM" | Não é proporcional. Parâmetros de encoding variam **238×** (204 800 → 48 784 960); a VRAM varia **1,34×** em Garden (3917 → 5254 MB) |
| 3 | p. 12 | "esperava-se que uma parcela das combinações pudesse exceder os 6 GB" | **56/56 executaram com sucesso, zero OOM.** Parágrafo escrito em modo de expectativa precisa virar constatação |
| 4 | p. 9 | "contradiz a recomendação inicial dos autores do Instant-NGP" | Não contradiz — **confirma**. A documentação manda começar alto e reduzir; foi o que se fez, e reduzir melhorou. O achado é que o passo de redução **não é opcional**: 16 custa 5,6 dB em Garden e 14,5 dB em Bonsai |
| 5 | p. 7 | Critério: "a menor resolução cujo consumo se aproximasse do limite de 6 GB" | Nenhum fator caiu na faixa de 5–6 GB. Garden f2 ficou em 4882,8 MB e Bonsai f2 em 4816,1 MB. O critério real foi **a maior resolução viável** |
| 6 | p. 10 | "Ryzen 7 7700 X3D… 16 GB de RAM DDR4" | Não existe 7700X3D (há 7700X e 7800X3D); e a série Ryzen 7000 é **DDR5**. Verificar. Vale ainda declarar a RAM **disponível na WSL** (~7,7 GB medidos), porque foi ela que inviabilizou Garden f1 |
| 7 | p. 10–11 | Placeholders `X`, `XXXXxYYYY`, `[a confirmar ainda]`, `[N]` | Garden: fator **2**, 2594×1681, `aabb_scale=4`. Bonsai: fator **2**, 1559×1039, `aabb_scale=8`. Iterações: **5000** |
| 8 | p. 11 | Argumenta que 20 000 passos é "ponto de parada defensável" | Está correto que 20 000 é o início do decaimento da taxa de aprendizado (`decay_start: 20000` no `base.json`), mas o trabalho adota **5000**. Ver §5 |
| 9 | p. 7–9 | "fator" designa duas coisas | Ver §6 |

---

## 4. A correção mais delicada: qual é a "configuração padrão"

O artigo afirma que a configuração padrão é L=16, T=19, F=2. **O artigo do
Instant-NGP realmente lista esses valores como padrão da codificação**, mas o
arquivo `configs/nerf/base.json` distribuído no repositório — que é o que o
experimento usa como baseline — traz:

```json
"n_levels": 8,  "n_features_per_level": 4,  "log2_hashmap_size": 19
```

Isso muda três afirmações do texto:

- O baseline **não** está no vértice superior do grid. O vértice é T=19 F=8 L=16.
- O baseline coincide com o ponto **interior** T=19 F=4 L=8.
- Portanto o baseline não é o "limite superior de qualidade" que a Seção 3
  descreve: o grid contém configurações mais pesadas *e* de maior PSNR.

**Sugestão de redação:** distinguir explicitamente "configuração padrão do artigo"
de "configuração padrão da implementação (`base.json`)", declarar que o trabalho
adota a segunda por ser a que um usuário real executa, e ajustar a Seção 3 para
falar em "ponto de referência" em vez de "limite superior de qualidade".

Há um efeito colateral que também precisa entrar no texto. O `base.json` não
define `per_level_scale`; quem o preenche é o Instant-NGP, derivando-o do
`aabb_scale` (`src/testbed.cu:4248`):

```
b = exp( log(2048 · aabb_scale / base_resolution) / (L − 1) )
```

No Synthetic-NeRF o `aabb_scale` está ausente e a fórmula devolve exatamente 2,0.
Com `aabb_scale=4` devolve 2,438; com 8, 2,692. Para que baseline e grid fiquem na
mesma régua, o alvo de resolução mais fina do grid foi fixado em
`N_max = 2048 · aabb_scale`, o que faz L=8 reproduzir o `b` do `base.json`. Sem
isso, baseline e grid teriam resolução mais fina 4× diferente. **Isso merece um
parágrafo na Seção 3.3** — é uma decisão de desenho não óbvia e um revisor atento
perguntaria.

---

## 5. Número de iterações (Seção 3.2)

O parágrafo atual defende 20 000 passos e deixa `[N]` em aberto. O valor medido é
**5000**, e a justificativa mudou de natureza — agora é empírica, sobre vistas
retidas:

- A 5000 iterações o PSNR já é **99 %** do valor de 30 000 (≈20,99 contra 21,19 dB).
- Ir a 10 000 compra **+0,11 dB** por 2× o custo; ir a 30 000 compra **+0,20 dB**
  por 6× (165 s → 953 s por execução).
- O ganho marginal cai abaixo de 0,1 dB/1000 iterações já em **4000**.
- Mantém a comparabilidade com o `exp01`, que usou 5000.

Sobre os 20 000: continua verdade que é ali que começa o decaimento da taxa de
aprendizado, mas a curva mostra que a qualidade estabiliza muito antes. Sugiro
manter a menção como contexto e explicitar que a curva medida, não o cronograma
do otimizador, é o que ancora a escolha.

**Ressalva a declarar:** a curva de convergência foi medida **apenas em Garden**.
Adotar 5000 em Bonsai é extrapolação — defensável, porque Bonsai converge mais
facilmente (28,68 dB já no baseline), mas é extrapolação.

---

## 6. Colisão de terminologia: "fator"

O texto usa "fator" para duas grandezas independentes:

- **fator de redução de resolução** — 2, 4, 8 (Tabela 1, Seção 2)
- **`aabb_scale`** — 2, 4, 8, 16, 32 (Figura 2, Seção 2.1)

A Figura 2 tem legenda "Comparação visual da cena Garden para **fatores de 2 a
32**" logo depois de uma tabela cuja coluna se chama "Fator de Escala" e vai de 1
a 8. Um leitor que não acompanhou os experimentos lê as duas como a mesma coisa.

**Sugestão:** reservar "fator de redução" só para resolução e sempre escrever
`aabb_scale` por extenso, inclusive nas legendas. Na Figura 2:
*"Comparação visual da cena Garden para valores de `aabb_scale` de 2 a 32"*.

---

## 7. Onde entram as figuras novas

### Substituir

| Figura | Arquivo novo | Por quê |
|---|---|---|
| **Figura 2** (comparação visual `aabb_scale`, Garden) | `runs/aabb_check/garden_5000/comparacao.png` | A versão atual é de 2000 iterações; esta tem 5000 e separa melhor os candidatos. Inclui a foto de referência à esquerda |
| **Figura 3** (gráfico `aabb_scale`) | `runs/aabb_quantitativo/aabb_quantitativo.png` | Agora tem PSNR **e** SSIM no painel superior e pico de VRAM no inferior, com a linha dos 6144 MB |

### Inserir

| Onde | Arquivo | Papel |
|---|---|---|
| Seção 2.1, após a Figura 3 | `runs/aabb_quantitativo_bonsai/aabb_quantitativo.png` | O mesmo gráfico para Bonsai. **Essencial**: mostra que o ótimo é 8, e não 4 — a calibração é por cena, não global |
| Seção 2.2 (resolução), junto à Tabela 1 | `runs/etapa1_final/resolucao_final.png` | VRAM e PSNR por megapixels de treino, com a janela de 5–6 GB sombreada e o teto de 6144 MB. Torna o critério de escolha legível |
| Seção 2.2, opcional | `runs/etapa1_final_bonsai/resolucao_final.png` | Idem para Bonsai |
| Seção 2.2, opcional | `runs/etapa1_final/comparacao_resolucao.png` | Folha de contato com uma vista retida por resolução, mais a foto real. Útil para mostrar que f2 não compromete a qualidade |
| Seção 3.2, no lugar do `Figura X <TODO>` | `runs/etapa15_final/garden_f2/convergencia.png` | Curva de convergência: loss em cima, PSNR e SSIM em vistas retidas embaixo, com marcos em 5000/10000/20000/30000 |
| Seção 3.2, logo após | `runs/etapa15_final/garden_f2/justificativa_iteracoes.png` | Quatro painéis, sendo o (d) o que sustenta a escolha: PSNR contra custo do grid em horas. **É a figura que responde "por que 5000"** |

### Para a Seção 4 (entrega seguinte)

`runs/exp02/analise/pareto_psnr_vram.png`, `pareto_psnr_tempo.png` e
`degradacao_baseline.png`, mais as tabelas de `runs/exp02/analise/*.csv`.

---

## 8. Ajustes de texto para acomodar a nova direção

### Resumo e Abstract (p. 1–2)

Dizem "A metodologia divide-se em **três** etapas". A Seção 3 já descreve
**quatro** (baseline, exploração, análise multiobjetivo, avaliação das métricas),
e na prática houve ainda a calibração prévia. Alinhar, e mencionar que o estudo
usa **cenas reais não-limitadas**, o que hoje não aparece no resumo.

### Introdução (p. 4–5)

O trecho "causando constantes erros por falta de memória" cria uma expectativa que
os dados não sustentam: **nenhuma das 56 execuções falhou por memória**. Sugiro
trocar por uma formulação sobre *pressão* de memória e margem, não sobre falha —
caso contrário a Seção 4 precisará explicar uma promessa não cumprida.

Também vale antecipar na introdução o que o trabalho de fato mede: a amplitude de
VRAM que a escolha de hiperparâmetros libera (1,3 GB em Garden, 2,1 GB em Bonsai),
em vez de prometer viabilizar o que não caberia.

### Seção 2 (p. 5–6)

Boa como está. Só acrescentaria, ao justificar a migração, que o `exp01` atingiu
teto de 2981 MB em 54 execuções sem nenhum OOM — o número torna o argumento
concreto.

### Seção 3.2 (baseline)

Além dos placeholders, acrescentar que `nerf_compatibility` foi desligado **e que
essa flag altera o treino**, não só a avaliação (ela zera o `cone_angle_constant`,
que é o mecanismo que viabiliza marchar por cena não-limitada). Hoje o texto diz
apenas que é "adequado ao Synthetic-NeRF mas não aos datasets reais", sem dizer o
que muda.

### Seção 3.3 (grid)

Três acréscimos:

1. O parágrafo sobre `per_level_scale` descrito em §4 acima.
2. Trocar a expectativa de OOM pela constatação de que todas couberam, e explicar
   por quê: o piso de memória é dominado pelas **imagens de treino** (2678 MB em
   Garden f2, 1576 MB em Bonsai f2), que `T`, `F` e `L` não tocam.
3. Corrigir a afirmação de proporcionalidade (item 2 da §3).

### Seção 3.5 (métricas)

Acrescentar que o pico de VRAM é reportado **descontada a linha de base do
sistema**, medida por execução, e o porquê: a ocupação da GPU pelo Windows variou
entre 254 e 1457 MB, o que inviabiliza comparar valores absolutos.

---

## 9. Pendência conceitual que o texto ainda não resolve

O §5.2 do spec trata o mapa de combinações inviáveis como "metade da
contribuição", e a Seção 3.3 do artigo promete isso ("o mapeamento das combinações
inviáveis representam uma informação relevante"). **Esse mapa não existe: todas as
54 combinações couberam.**

Não é falha do experimento — é consequência de o piso de memória ser dominado
pelos dados, não pelo modelo. Mas o artigo precisa decidir como tratar isso antes
da Seção 4, porque hoje ele promete na metodologia algo que os resultados não
entregam. As duas saídas honestas:

- **Reformular a promessa**: o trabalho mede a *amplitude* de VRAM que os
  hiperparâmetros liberam e onde está o joelho da fronteira, não a fronteira de
  viabilidade.
- **Produzir o mapa** num fator de resolução intermediário (≈1,6 para Garden),
  onde a configuração padrão não caberia e as leves caberiam. Estimado em 2
  execuções, mas com margem de ~400 MB — menor que a variação da linha de base do
  sistema, o que compromete a reprodutibilidade.

Recomendo a primeira.
