# Guia — por que verificar antes do grid

Documento de orientação. Resume o que cada verificação pré-grid responde, o que
custaria pular, e o que de fato foi encontrado. Serve para você defender as
decisões sem recorrer a "é boa prática".

---

## 1. O que está em jogo

O grid é **27 combinações** (T×F×L), **5 a 12 h de GPU**, e o spec §5 registra:
*"cabe até novembro, mas não cabe duas vezes"*.

Isso muda a natureza do trabalho preparatório. Não se está buscando perfeição —
está-se comprando **falha ruidosa em vez de falha silenciosa**. Um erro que
derruba a execução custa minutos. O mesmo erro passando despercebido custa o
orçamento inteiro de GPU e, pior, produz números publicáveis que estão errados.

Toda verificação abaixo existe para converter um modo de falha silencioso
específico em um erro visível **antes** de gastar o orçamento.

---

## 2. O argumento mais forte que você tem

**As verificações não foram cerimônia: sete defeitos reais foram encontrados.**

| # | Defeito | Era silencioso? |
|---|---|---|
| 1 | `file_path` apontava para caminho inexistente nas duas cenas | Não — falha alto |
| 2 | `garden` f2 com altura 1680 no JSON contra 1681 na imagem | **Sim** |
| 3 | `--nerf-compatibility` com padrão ligado, herdado do `exp01` | **Sim** |
| 4 | `aabb_scale=16` nunca validado visualmente | **Sim** |
| 5 | Divisão treino/teste inexistente — PSNR medido em vistas de treino | **Sim** |
| 6 | Comentário do `per_level_scale` falso para `aabb_scale≠1` | **Sim** |
| 7 | Calibração feita com a config errada (pior caso do grid, não a padrão) | **Sim** |

Seis dos sete não davam erro. Rodariam até o fim e produziriam CSV, gráfico e
Fronteira de Pareto — todos errados.

Igualmente importante: **cinco verificações voltaram limpas** (§5). Isso mostra
que o método discrimina, em vez de só acusar problema em tudo.

---

## 3. As verificações, por etapa

### Etapa 0 — preparação do dataset

**`file_path` resolve?**
O Instant-NGP resolve `file_path` relativo ao diretório do próprio JSON, não ao
diretório de trabalho (`nerf_loader.cu:335`). O `colmap2nerf.py` foi rodado da
raiz do projeto e gravou `./data/mip_nerf/garden/images/X.JPG`, que a partir da
pasta da cena vira um caminho aninhado inexistente.
*Se pular:* nada carrega. Falha alta — é o defeito barato.

**Arredondamento das dimensões reduzidas**
`garden` tem altura ímpar (3361). O `round()` do Python usa arredondamento
bancário: `round(1680.5) = 1680`, mas a imagem em `images_2/` tem 1681.
*Se pular:* intrínsecos 1 px fora da imagem em todas as execuções de `garden` f2.
Não quebra nada — só enviesa tudo, discretamente.

**Divisão treino/teste**
O Mip-NeRF 360 não traz divisão oficial. Sem ela, avaliar significa renderizar
vistas que o modelo já viu.
*Se pular:* o PSNR não mede generalização, mede memorização. **É o erro mais
grave da lista**, porque produz números altos e plausíveis. Concretamente: a
Etapa 1 mediu 20.35 dB avaliando em vistas de treino; com holdout 1-em-8 real, o
mesmo regime dá ~15.9 dB.

**`aabb_scale` validado visualmente**
O `aabb_scale` define o volume que o modelo tenta representar. Grande demais
gasta resolução no vazio e gera *floaters*; pequeno demais corta o fundo.
*Se pular:* foi o que aconteceu — ver §4.

**`--nerf-compatibility`**
Reproduz o protocolo do NeRF original: zera o `cone_angle_constant`, que é o
mecanismo que torna viável marchar por cena não-limitada. Correto no `exp01`
(Synthetic-NeRF), errado aqui. O padrão continuava ligado.
*Se pular:* amostras por raio explodem; VRAM e tempo medidos deixam de
representar o regime real.

### Etapa 1 — calibração de resolução

**Em que resolução os 6 GB passam a restringir?**
Este é o ponto que o `exp01` ensinou: lá o Synthetic-NeRF nunca passou de
2981 MB em 54 execuções — zero OOM. A restrição não mordia, e sem restrição
ativa não há troca a otimizar; a Fronteira de Pareto degenera num ranking de
qualidade sem eixo de custo.
*Se pular:* escolher `images_8` e concluir "não aperta" seria **selecionar o
resultado**. Escolher `images_2` porque estoura, idem.

**Com qual configuração calibrar?**
Com a **padrão** do Instant-NGP (§3 do spec), não com o pior caso do grid. São
perguntas diferentes: o pior caso responde "o grid inteiro cabe?"; a padrão
responde "a restrição morde?". A diferença medida entre as duas é ~1.5 GB —
suficiente para escolher a resolução errada.

### Etapa 1.5 — número de iterações

As 5000 iterações do `exp01` foram ancoradas na curva do **Lego**: cena limitada,
fundo branco, convergência rápida. Cena não-limitada não tem por que convergir no
mesmo ritmo.
*Se pular:* 27 execuções com orçamento de treino injustificado — e a banca
pergunta de onde saiu o 5000.

---

## 4. O caso que mostra por que isso não é excesso de zelo

A validação visual do `aabb_scale` (§2.2 do spec) **não tinha sido feita**; o
valor 16 foi herdado para as duas cenas. Consequência em cadeia:

1. A Etapa 1.5 rodou 30 000 iterações e mediu PSNR **caindo** monotonicamente nas
   vistas retidas (15.90 → 15.15 dB), com SSIM concordando.
2. A investigação descartou, uma a uma, as hipóteses de erro de instrumentação
   (§5) — o que levou tempo, mas foi o que deu confiança no resultado.
3. A comparação visual mostrou a causa: com `aabb_scale=16` a vista retida sai
   tomada de névoa; com **4 ou 8** sai nítida, com mesa, vaso e fundo.
4. O loss confirma independentemente: 0.00603 (aabb 4) e 0.00665 (aabb 8) contra
   0.00805 (aabb 16), a 1500 passos.

**Uma verificação de ~10 min que não foi feita custou uma execução de 30 000
iterações inteiramente inaproveitável.** É o argumento mais concreto que você
tem para justificar o trabalho preparatório.

E o efeito não para aí: mudar o `aabb_scale` **invalida a Etapa 1 e a 1.5**,
porque altera o consumo de VRAM (menos cascatas do grid de densidade) e o
`per_level_scale` derivado. As duas precisam ser refeitas.

---

## 5. As verificações que voltaram limpas

Registrar isso importa: mostra que o método distingue defeito de ruído.

| Verificação | Resultado |
|---|---|
| Referencial (`scale`/`offset`/`up`) depende do split? | Não — constantes fixas |
| A pose de uma imagem muda entre conjuntos? | Não — diferença 0.000000 |
| `render_aabb` / `aabb` mudam entre splits? | Não — idênticos |
| A referência renderizada é a foto certa? | Sim — 59.2 dB contra ~13 dB das vizinhas |
| 1000 passos bastam para o pico de VRAM? | Sim — cresce só 41.9 MB até 5000 |
| Avaliação pesada (`spp=8`) custa VRAM? | Não — 13.7 MB, dentro do ruído |

A quinta e a sexta linha valem dinheiro: autorizam calibrar VRAM com execuções
curtas e avaliação leve, o que barateia todo o resto.

---

## 6. Duas armadilhas de medição que valem citar

**`vram_peak_device_mb` não é comparável entre execuções.** Ele inclui a linha de
base do Windows, que variou de 254 MB a 1265 MB no mesmo dia. Só
`vram_peak_mb` (pico − linha de base) compara. Cheguei a reportar uma inversão
inexistente por confundir os dois.

**Duas calibrações simultâneas destroem a medida.** Cada processo lê como linha
de base a VRAM que o outro já alocou. O resultado não é ruidoso, é sem sentido —
dá para ver `f8` medindo mais que `f4`. Por isso `calib_resolucao.py` e
`envelope_viabilidade.py` têm trava `flock`.

---

## 7. Estado atual

| Item | Situação |
|---|---|
| `file_path`, arredondamento, variantes f2/f4/f8 | Corrigidos |
| Divisão treino/teste (161/24, `holdout_every=8`) | Feita |
| `--nerf-compatibility` padrão desligado | Feito |
| Colunas de procedência no CSV | Feitas |
| `aabb_scale` | **Em validação** — 4 e 8 são os candidatos |
| Etapa 1 (resolução) | **A refazer** após fixar `aabb_scale` |
| Etapa 1.5 (iterações) | **A refazer** — a curva atual mede o artefato |
| `grid_runner.py` aponta para `nerf_synthetic`/lego/chair | Pendente |
| `per_level_scale`: baseline vs grid comparáveis? | Pendente — decisão de desenho |
| Grid (27 combinações) | **Não iniciado** |

---

## 8. Como explicar em três frases

> O `exp01` mostrou que o benchmark padrão não pressiona uma GPU de 6 GB — piso
> de 1745 MB, zero OOM em 54 execuções. Migrar para cena real recria a restrição,
> mas troca um dataset curado por um que precisa ser construído, e cada decisão
> dessa construção (resolução, `aabb_scale`, divisão de teste, protocolo) entra
> silenciosamente em todos os resultados. Como o grid custa 5 a 12 h e não cabe
> duas vezes, cada uma dessas decisões foi medida antes, e não presumida — o que
> encontrou sete defeitos, seis deles silenciosos.

Se pressionado sobre o custo do preparo, a resposta é o §4: uma verificação de
10 min que foi pulada custou uma execução de 30 000 iterações.
