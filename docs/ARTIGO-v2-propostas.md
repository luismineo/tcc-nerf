# Artigo v2 — propostas sobre a versão 1.1

Base: PDF da **versão 1.1** do artigo (21 páginas), recebido em 2026-10-09. Este
arquivo substitui a versão anterior, que partia da v1. As páginas citadas são as
do PDF v1.1.

Como usar:

1. a **seção 1** mostra o que da proposta anterior já entrou na v1.1;
2. a **seção 2** lista o que ainda falta, por prioridade;
3. a **seção 3** traz o texto pronto, só para os trechos que precisam mudar;
4. as **seções 4 e 5** cobrem referências, figuras e tabelas.

Trechos marcados **[verificar]** dependem de informação que só o autor tem.
Todos os números vêm de `runs/` e dos relatórios em `docs/`
(`RELATORIO-fechamento.md`, `RELATORIO-exp02-validacoes.md`,
`runs/exp02_final/tabelas.md`). Os conceitos usados aqui (joelho, sweet spot,
ruído, patamares, piso) estão explicados em `GUIA-conceitos-e-achados.md`.

---

## 1. O que a v1.1 já resolveu

| item da proposta anterior | situação na v1.1 |
|---|---|
| título em português e inglês | **resolvido** — título novo, mais preciso |
| Resumo e Abstract com o piso de memória e a não-proporcionalidade | **resolvido**, com um ajuste sugerido (2.1, item 14) |
| "constantes erros por falta de memória" na Introdução | **resolvido** — removido |
| objetivo do trabalho | **resolvido** — "caracterizar o potencial e os limites" |
| número do exp01 (2981 MB, 54 execuções, zero OOM) | **resolvido** |
| CPU e RAM (Ryzen 7 5700X3D, DDR4) | **resolvido** — combinação válida |
| placeholders do baseline (fator 2, `aabb_scale` 4 e 8) | **resolvido** |
| divisão treino/teste com os números (161/24 e 255/37) | **resolvido** — ficou na 3.2, o que funciona |
| 5000 iterações como orçamento padronizado | **resolvido em parte** — falta Garden e o teste de ordenação (item 7) |
| Bergstra e Bengio citados para o Grid Search | **resolvido no texto** — falta na lista de referências |
| Tabela 1, `base.json`, `per_level_scale`, `nerf_compatibility`, ruído, −2 dB, Seções 4 e 5 | **pendentes** — seção 2 |

---

## 2. O que ainda falta, por prioridade

### 2.1 Contradições com os dados — corrigir antes de enviar

| # | onde | problema | onde está o texto |
|---|---|---|---|
| 1 | **Tabela 1**, p. 8 | Continua a tabela antiga, medida com a configuração mais pesada do grid, `aabb_scale` = 16 e sem divisão treino/teste. Diz que Garden no fator 2 deu OOM — e a Seção 3.2 adota justamente Garden no fator 2. A banca vai ver a contradição. | 3.3 |
| 2 | p. 8, antes da Tabela 1 | "por um número reduzido de iterações, suficiente apenas para que o pico de alocação fosse atingido" — a calibração final usou 5000 iterações e mediu também o PSNR. | 3.3 |
| 3 | Seção 3, p. 11, e fim da 3.2, p. 13–14 | "limite superior de qualidade" — o baseline não é limite superior: 2 configurações em Garden e 4 em Bonsai o superam por mais que o ruído (até +0,46 dB e +0,90 dB). | 3.4 |
| 4 | 3.3, p. 14 | "reduções em qualquer um dos três implicam redução **proporcional** no consumo de VRAM" — contradiz o próprio Resumo da v1.1 ("não é proporcional") e os dados: os parâmetros da codificação variam ~255×, a VRAM 1,3× em Garden e 1,7× em Bonsai. | 3.4 |
| 5 | 3.3, p. 14 | "Müller et al. fixam L = 16, T = 19 e F = 2 … vértice superior do espaço de busca … baseline" — três erros: o `base.json` usado é **T = 19, F = 4, L = 8**; esse ponto é interior, não vértice; e `T19 F2 L16` também não é o vértice (o vértice é `T19 F8 L16`). | 3.4 |
| 6 | 3.3, p. 15 | "esperava-se que uma parcela das combinações pudesse exceder os 6 GB … mapeamento das combinações inviáveis" — nenhuma excedeu (54 de 54 mais os baselines). | 3.4 |
| 7 | 3.2, p. 12–13, e Figura 4 | A Figura 4 é de **Bonsai**, mas o texto não diz. A frase "continua apresentando ganhos após 5000 … estabilização a partir de 10 000" vale só para Bonsai; Garden estabiliza em 4000. Falta o argumento mais forte: o teste de ordenação a 20 000 iterações. | 3.4 |
| 8 | 3.2, p. 12 | "o marco de 20 000 passos … ponto de parada metodologicamente defensável" — logo antes de adotar 5000. O fato (decaimento da taxa de aprendizado em 20 000) é útil; o enquadramento contradiz a escolha. | 3.4 |
| 9 | 2.1, p. 10 | "curiosamente, contradiz a recomendação inicial dos autores" — a recomendação é **começar alto e reduzir**. O resultado a **confirma**. | 3.3 |
| 10 | 2.1 | Só Garden é justificado. Bonsai aparece com `aabb_scale` = 8 na 3.2 sem evidência no texto. | 3.3 (figura nova) |
| 11 | 3.5, p. 17 | "limiar de −2 dB considerado aceitável na literatura (Mildenhall et al., 2021; Müller et al., 2022)" — nenhum dos dois trabalhos define esse limiar. | 3.4 |
| 12 | 3.5, p. 17 | Promete, na Seção 4, a "comparação entre os regimes de cena limitada e não-limitada quanto à magnitude dos efeitos de cada hiperparâmetro". Esse número não existia — **agora existe** (`efeito_hiperparametros.csv`). | 3.5 (Seção 4.6) |
| 13 | Seção 2, p. 6 | "folhagem de alta frequência … acarreta maior consumo de VRAM" — os dados mostram outra coisa: Garden consome mais porque suas imagens têm mais pixels. Descontadas as imagens, Garden consome **menos** que Bonsai (1641 contra 1800 MB). | 3.3 |
| 14 | Resumo e Abstract | "alocações dinâmicas do processo de amostragem" — sustentado só em parte. O que foi medido é o custo das imagens; o restante do piso não foi decomposto. Há evidência indireta (o `aabb_scale` sozinho move ~500 MB em Garden), mas não medição direta. | 3.1 |
| 15 | Seção 2, p. 6 | "demonstraram que o Instant-NGP já se demonstra otimizado, para datasets pequenos" — o exp01 mostrou ausência de pressão de memória, não que o modelo seja "otimizado". | 3.3 |
| 16 | 3.4 | O sweet spot é citado como objetivo, mas nunca definido de forma operacional. Sem definição, a escolha parece arbitrária. | 3.4 |

### 2.2 Coerência de método — recomendado

- **Ordem `aabb_scale` → resolução.** O `aabb_scale` altera o consumo de VRAM
  (em Garden, de 4216 para 4710 MB entre os valores 2 e 32), então a resolução
  foi calibrada com ele já fixado. O texto apresenta a resolução primeiro e o
  `aabb_scale` "paralelamente". Há uma correção mínima e uma completa (3.3).
- **Como a VRAM foi medida.** A v1.1 nunca diz. Com a ocupação do desktop
  variando entre 254 e 1457 MB, isso é indispensável (3.3 e 3.4).
- **`base.json` versus o padrão do artigo original** (3.4, item 3.2).
- **`per_level_scale`** — por que `L` = 8 reproduz o baseline (3.4, item 3.3).
- **`nerf_compatibility`** — uma frase sobre o que ele muda (3.4).
- **Ruído entre execuções** — 0,244 dB e 122 MB, base de toda a discussão (3.4,
  item 3.5).
- **Achado novo desta revisão: o limiar de ruído é limítrofe em Garden.** Com
  todas as medições reunidas, a amplitude chegou a 0,34 dB numa configuração. O
  limiar fixado antes (0,244 dB) foi mantido, mas a análise de sensibilidade
  (`sensibilidade_ruido.csv`) mostra que os degraus do guia de Garden dependem
  dele; sweet spots e guia de Bonsai, não. Está incorporado nas Seções 4.1, 4.4
  e 4.7 propostas.
- **Triagem de monotonicidade** — a resposta pronta para "o grid tem n = 1"
  (3.4, item 3.3).
- **3.4 declara três objetivos** (PSNR, VRAM, tempo) e depois apresenta a
  fronteira bidimensional. Basta dizer onde o tempo entra: área dos pontos e
  desempate do sweet spot (3.4).

### 2.3 Redação

| página | trecho | correção |
|---|---|---|
| 4 | "em portugês" (duas vezes: PSNR e VRAM) | "em português" |
| 3–4 | "um decodificador mais compacto, essa estratégia, por sua vez, acelerou" | "…mais compacto. Essa estratégia acelerou…" |
| 5 | "qualidade foto realista" | "qualidade fotorrealista" |
| 5 | "podemos tentar determinar experimentalmente, em que grau" | "busca-se determinar experimentalmente em que grau" |
| 6 | "características dissidentes" | "características distintas" |
| 6 | "os valores parametrais relevantes a ambos os extremos" | "os valores de parâmetros relevantes nos dois extremos" |
| 6 | "Dado essa premissa, foi realizado o experimento exp01, o qual, os resultados, …" | ver 3.3 |
| 6 | "(Barron, et al. 2021)" e "(Barron et al., 2022)" no mesmo parágrafo | "(Barron et al., 2022)" nas duas |
| 6 | "distâncias mais arbitrárias" | "distâncias arbitrárias" |
| 8 | "RTX 2060, 6GB" | "6 GB" |
| 9 | "podemos notar que o fator 4 e 8" | "os valores 4 e 8 de `aabb_scale`" — "fator" fica reservado à resolução |
| 10 | "Essa rodada de testes, também capturou … revelou que, o fator 4" | sem as vírgulas entre sujeito e verbo e depois de "que" |
| 10 | legenda da Figura 3: "para o fato de aabb_scale" | ver seção 5 (figura nova) |
| 11 | "O experiemento deste trabalho" | "O experimento" |
| 11 | "partimos para a experimentação em si" | "passou-se à experimentação" |
| 12 | "calculadas sobre as vistas retidas.." | um ponto só |
| 12 | "foi realizado uma nova execução de uma validação específica" | "foi realizada uma validação específica" |
| 14 | "em relativamente, entre a de cena limitada … e o de cena não-limitada" | "em termos relativos, entre o regime de cena limitada … e o de cena não-limitada" |
| 15 | "Assumimos que uma configuração domina outra" | "Considera-se que…" — e o segundo parágrafo da 3.4 repete a definição de dominância; manter uma só |
| 17 | "Fonte : Elaborado pelos autores, 2026" | padronizar: "Fonte: Elaborado pelos autores (2026)." |
| todo | "podemos", "partimos", "Assumimos" ao lado de "optou-se", "adotou-se" | escolher a voz impessoal e usar em todo o texto |

---

## 3. Texto proposto

### 3.1 Resumo e Abstract

**Substituir** "Verificou-se que uma parcela significativa da memória é
determinada pelo armazenamento das imagens de treinamento e por alocações
dinâmicas do processo de amostragem, estabelecendo um piso de consumo
independente dos hiperparâmetros analisados." **por:**

> Verificou-se que uma parcela significativa da memória é determinada pelo
> armazenamento das imagens de treinamento — entre 1,6 e 2,7 GB nas cenas
> avaliadas — e por um custo fixo de execução, parcialmente associado à extensão
> espacial da cena, estabelecendo um piso de consumo que os hiperparâmetros
> analisados não alcançam.

*Abstract:*

> A significant portion of memory consumption was found to be determined by the
> storage of training images — between 1.6 and 2.7 GB in the evaluated scenes —
> and by a fixed runtime cost, partly associated with the spatial extent of the
> scene, establishing a memory floor that the analyzed hyperparameters cannot
> reach.

**Opcional** — se houver espaço, os números que tornam o Resumo verificável,
depois de "não é proporcional ao tamanho da estrutura hash":

> : enquanto o número de parâmetros da codificação varia cerca de 255 vezes no
> espaço de busca, o pico de VRAM varia entre 1,3 e 2,1 GB. Diferenças de
> qualidade inferiores a 0,24 dB mostraram-se indistinguíveis da variação entre
> execuções idênticas.

*Abstract:*

> : while the number of encoding parameters varies by a factor of about 255
> across the search space, peak VRAM varies by 1.3 to 2.1 GB. Quality
> differences below 0.24 dB were found to be indistinguishable from the
> variation between identical runs.

### 3.2 Introdução

Só a redação da p. 5 (tabela 2.3). O conteúdo está alinhado com os resultados.

### 3.3 Seção 2 — Preliminares e definição do cenário

**p. 6 — substituir** "Dado essa premissa, foi realizado o experimento exp01 , o
qual, os resultados, que podem ser vistos na Figura 1 abaixo, demonstraram que o
Instant-NGP já se demonstra otimizado, para datasets pequenos." **por:**

> Dada essa premissa, foi realizado o experimento exp01, cujos resultados,
> apresentados na Figura 1, mostraram que, em cenas sintéticas pequenas, o
> consumo de memória do Instant-NGP fica bem abaixo da capacidade da placa: não
> havia restrição de memória a otimizar.

**p. 6 — substituir** "os autores decidiram por usar o dataset Garden, este,
também, amplamente utilizado e considerado padrão ouro na literatura (Gao et al.,
2026), inicialmente apresentado através do artigo do Mip-NeRF 360 (Barron, et al.
2021)." **por:**

> optou-se pela cena Garden, do conjunto Mip-NeRF 360 (Barron et al., 2022),
> amplamente utilizado como referência na literatura (Gao et al., 2026).

**[verificar]** se Gao et al. usam de fato a expressão "padrão ouro"; se sim, ela
pode voltar.

**p. 6 — substituir** "A cena Garden, especificamente, apresenta geometria
complexa e folhagem de alta frequência, o que dificulta a inferência do modelo e
acarreta maior consumo de VRAM." **por:**

> A cena Garden, especificamente, apresenta geometria complexa e folhagem de alta
> frequência, o que dificulta a reconstrução. É também capturada em resolução
> mais alta que a cena interna adotada, o que eleva o custo de memória das
> imagens de treinamento.

**Ordem `aabb_scale` → resolução.** Duas opções:

- **completa (recomendada):** mover o parágrafo do `aabb_scale` (p. 8–9, de
  "Paralelamente, foi necessário determinar…" até "…na etapa seguinte do
  experimento") e a Seção 2.1 para **antes** do parágrafo "Diferentemente do
  Synthetic-NeRF, contudo, o dataset Mip-NeRF 360 disponibiliza…". O texto
  passa a seguir a ordem em que as calibrações dependem uma da outra;
- **mínima:** manter a ordem e trocar "Paralelamente, foi necessário determinar
  o valor do parâmetro aabb_scale para cada cena." por: "As medições da Tabela 1
  foram feitas com o valor de `aabb_scale` de cada cena já definido, já que ele
  também altera o consumo de memória. Esse parâmetro define…".

**p. 8 — substituir** de "Essa calibração consistiu em treinar o Instant-NGP…"
até o fim da Tabela 1 **por:**

> Essa calibração consistiu em treinar o Instant-NGP em sua configuração padrão,
> sem variação dos hiperparâmetros de codificação de hash, em cada uma das
> resoluções disponíveis de cada cena, com o `aabb_scale` já definido e a divisão
> entre treino e teste aplicada (Seção 3.2), por 5000 iterações. Registraram-se o
> pico de VRAM e o PSNR nas vistas de teste (Tabela 1). O pico de VRAM é
> reportado descontada a memória já ocupada na placa antes de cada execução,
> porque a interface gráfica do sistema operacional, que compartilha a GPU,
> ocupou entre 254 e 1457 MB ao longo dos experimentos; o valor absoluto do
> dispositivo não é comparável entre execuções e aparece apenas como
> referência.

**Tabela 1 — Calibração da resolução** (configuração padrão, `aabb_scale`
definido, divisão treino/teste aplicada, 5000 iterações)

| Cena | Fator de redução | Resolução | Imagens (treino / teste) | Situação | Pico − base (MB) | Ocupação prévia (MB) | Pico no dispositivo (MB) | PSNR (dB) |
|---|---|---|---|---|---|---|---|---|
| Garden | 8 | 648×420 | 161 / 24 | viável | 1322,4 | 582,6 | 1905,0 | 22,53 |
| Garden | 4 | 1297×840 | 161 / 24 | viável | 2053,3 | 558,3 | 2611,6 | 21,35 |
| Garden | 2 | 2594×1681 | 161 / 24 | viável | 4311,8 | 571,0 | 4882,8 | 20,99 |
| Garden | 1 | 5187×3361 | 161 / 24 | inviável — memória do sistema esgotada ao carregar as imagens | — | — | — | — |
| Bonsai | 8 | 390×260 | 255 / 37 | viável | 1329,8 | 1427,5 | 2757,3 | 29,87 |
| Bonsai | 4 | 780×520 | 255 / 37 | viável | 1682,3 | 1428,7 | 3111,0 | 28,82 |
| Bonsai | 2 | 1559×1039 | 255 / 37 | viável | 3388,3 | 1427,8 | 4816,1 | 28,64 |
| Bonsai | 1 | 3118×2078 | 255 / 37 | inviável — paginação para a memória do sistema | (4746,2) | 1380,0 | (6126,2) | (28,47) |

Fonte: `runs/etapa1_final/resolucao_final.csv` e
`runs/etapa1_final_bonsai/resolucao_final.csv`. Os valores entre parênteses são
de uma execução inviável e não devem ser usados como medida.

**Logo após a Tabela 1 — acrescentar:**

> Na resolução original, nenhuma das cenas pôde ser treinada. Em Garden, o
> carregamento das imagens esgotou a memória do sistema antes de o treinamento
> começar. Em Bonsai, o processo terminou sem erro, mas com a vazão reduzida de
> cerca de 34 para 1 iteração por segundo: as imagens de treino, que o
> Instant-NGP mantém na VRAM a 4 bytes por pixel, somam 6303 MB, acima da
> capacidade da placa, e o controlador passou a usar a memória do sistema.
> Execuções nessa condição foram classificadas como inviáveis, ainda que
> concluídas. Nenhuma resolução viável aproximou a configuração padrão do limite
> de 6 GB, de modo que se aplicou a segunda parte do critério: adotou-se, nas
> duas cenas, o fator 2, a resolução imediatamente anterior à primeira
> inviável.

**2.1 — legenda da Figura 2:** "Comparação visual da cena Garden para valores de
`aabb_scale` de 2 a 32".

**p. 10 — substituir** de "Como podemos notar, o fator 2 e 16…" até a legenda da
Figura 3 **por:**

> Os valores 2 e 16 apresentam artefatos que comprometem a cena nesse ângulo. O
> resultado é coerente com a orientação da documentação: o valor elevado é o
> ponto de partida da redução progressiva, e não o valor a ser mantido.
>
> A inspeção de uma única vista, porém, não basta para a escolha final. Cada
> valor candidato foi também treinado por 5000 iterações e avaliado pelo PSNR e
> pelo SSIM médios sobre todas as vistas de teste (Figura 3). O melhor valor
> diferiu entre as cenas: 4 em Garden (20,95 dB; SSIM 0,493) e 8 em Bonsai
> (28,60 dB; SSIM 0,865). O valor inicial, 16, custava 5,6 dB em Garden e
> 14,5 dB em Bonsai. Em Garden, a média sobre as 24 vistas de teste favoreceu o
> valor 4 em 2,2 dB sobre o valor 8, que a inspeção visual deixara empatados. O
> `aabb_scale` também afeta a memória: em Garden, o pico de VRAM passou de 4216
> para 4710 MB entre os valores 2 e 32, razão pela qual ele foi fixado antes da
> calibração da resolução.
>
> **Figura 3 – PSNR, SSIM e pico de VRAM por valor de `aabb_scale`, cenas Garden
> e Bonsai**

### 3.4 Seção 3 — Metodologia

**Introdução da Seção 3, p. 11 — substituir** "A lógica que organiza essas etapas
é a de estabelecer primeiro um limite superior de qualidade (o comportamento do
modelo em sua configuração padrão) e, a partir dele, medir o quanto de memória é
possível economizar e qual o custo disso em fidelidade visual." **por:**

> A lógica que organiza essas etapas é a de estabelecer primeiro um ponto de
> referência — o comportamento do modelo em sua configuração padrão — e, a
> partir dele, medir quanto de memória é possível economizar, qual o custo disso
> em fidelidade visual e quanto se ganha ao investir mais memória.

**3.1 Ambiente experimental — acrescentar ao final:**

> O WSL dispunha de cerca de 7,7 GB da memória do sistema. A GPU era
> compartilhada com a interface gráfica do Windows, que ocupou entre 254 e
> 1457 MB de VRAM antes do início das execuções, a depender da sessão. Todas as
> execuções foram sequenciais, e a ocupação prévia foi medida imediatamente
> antes de cada uma.

**3.2 — depois de** "…sem qualquer alteração nos hiperparâmetros de codificação de
hash (Müller et al., 2022)", **acrescentar:**

> Cabe registrar que esse arquivo define T = 19, F = 4 e L = 8, e não os valores
> apresentados como padrão no artigo original (T = 19, F = 2, L = 16). Adotou-se o
> arquivo distribuído por ser a configuração que um usuário efetivamente executa;
> as duas configurações pertencem ao espaço de busca e foram medidas.

**3.2 — `nerf_compatibility`, acrescentar ao final do parágrafo:**

> Essa opção altera o próprio treinamento, e não apenas a avaliação: ela anula o
> alargamento progressivo do passo de amostragem ao longo do raio, mecanismo que
> torna viável percorrer cenas não-limitadas. Por esse motivo, os valores
> absolutos de PSNR do exp01 e deste experimento não são comparáveis.

**3.2 — iterações. Substituir** de "Para determinar um novo número de iterações…"
até "…e não como o ponto de convergência completa do modelo." **por:**

> Para definir o número de iterações, a configuração padrão de cada cena foi
> treinada por 30 000 iterações, com avaliação das vistas de teste a cada 2000
> (Figuras 4 e 5), em procedimento análogo ao realizado para a cena Lego no
> exp01. A verificação fez-se necessária porque cenas reais tendem a convergir
> mais lentamente que cenas sintéticas.
>
> O comportamento diferiu entre as cenas. Em Garden, o ganho marginal de PSNR
> caiu abaixo de 0,1 dB a cada 1000 iterações já em 4000, e o ganho total entre
> 4000 e 30 000 iterações (0,24 dB) foi inferior à variação entre execuções
> idênticas (Seção 3.5): treinar mais não produz diferença mensurável. Em Bonsai,
> o mesmo limiar só foi atingido em 10 000 iterações, e restaram cerca de 1,6 dB
> entre 4000 e 30 000. Nas duas curvas, o ganho marginal volta a crescer ao
> cruzar 20 000 iterações, ponto em que a implementação inicia o decaimento da
> taxa de aprendizado (*learning rate decay*); a estabilização observada antes
> desse ponto não equivale, portanto, à convergência completa.
>
> Como o objetivo não é obter a máxima qualidade de uma configuração, mas
> comparar as 27 combinações do Grid Search sob um mesmo orçamento
> computacional, adotaram-se 5000 iterações, valor que também mantém a
> comparabilidade com o exp01. A escolha foi testada no caso desfavorável,
> Bonsai: quatro configurações que cobrem a faixa de capacidade do espaço de
> busca foram treinadas também por 20 000 iterações (Figura 6). Todas ganharam
> entre 1,00 e 1,12 dB, nenhuma trocou de posição, e a diferença entre a de menor
> e a de maior capacidade variou apenas 0,008 dB. O truncamento desloca os
> valores de Bonsai de forma uniforme, sem alterar a ordenação entre
> configurações — que é o que a análise multiobjetivo utiliza. As 5000 iterações
> devem, assim, ser interpretadas como um orçamento experimental padronizado, e
> não como o ponto de convergência do modelo; em Bonsai, os valores absolutos de
> PSNR estão cerca de 1 dB abaixo dos obtidos com 20 000 iterações.

A frase "Vale lembrar que, na implementação original, o marco de 20.000 passos…
defensável…" sai: o fato que ela traz está incorporado acima.

**Legendas:** "Figura 4 – Curva de convergência da cena Garden" (nova) e
"Figura 5 – Curva de convergência da cena Bonsai" (a atual Figura 4).
"Figura 6 – PSNR a 5000 e a 20 000 iterações, quatro configurações de Bonsai".

**Fim da 3.2, p. 13–14 — substituir** "O objetivo desta etapa foi estabelecer esse
limite superior de qualidade visual e um ponto de referência de custo
computacional para cada cena…" **por:**

> O objetivo desta etapa foi estabelecer, para cada cena, um ponto de referência
> de qualidade visual e de custo computacional, contra o qual as configurações
> exploradas na etapa seguinte são comparadas. O baseline não é um limite
> superior: configurações de maior capacidade do espaço de busca o superam
> (Seção 4).

**3.3 — substituir** "…proporcional a L · 2^T · F (Müller et al., 2022); reduções
em qualquer um dos três implicam, portanto, redução proporcional no consumo de
VRAM." **por:**

> …proporcional a L · 2^T · F (Müller et al., 2022). No espaço de busca adotado,
> esse número varia cerca de 255 vezes, de 204 800 a 52,3 milhões de
> parâmetros. A redução de qualquer um dos três diminui o número de parâmetros,
> mas não proporcionalmente o consumo de VRAM, já que parte relevante desse
> consumo independe da codificação (Seção 4.5).

**3.3 — substituir** "Müller et al. (2022) fixam L = 16, T = 19 e F = 2 como
configuração padrão, valores que correspondem exatamente ao vértice superior do
espaço de busca aqui adotado e, consequentemente, ao baseline descrito na Seção
3.2." **por:**

> O baseline (T = 19, F = 4, L = 8) é um ponto interior desse espaço, que contém
> configurações de maior e de menor capacidade; a configuração apresentada como
> padrão no artigo original (T = 19, F = 2, L = 16) também pertence a ele.
>
> O arquivo de configuração não define a razão de crescimento da resolução entre
> níveis (`per_level_scale`); a implementação a deriva do `aabb_scale`, de modo
> que o nível mais fino alcance 2048 · `aabb_scale` em relação ao cubo unitário.
> Para que variar L não alterasse ao mesmo tempo a resolução do nível mais fino —
> o que atribuiria a L um efeito que também é de resolução —, a razão foi
> calculada para cada configuração com esse mesmo alvo. Com isso, a configuração
> com L = 8 reproduz exatamente o baseline.

**3.3 — substituir** o parágrafo "Diferentemente do exp01, no qual nenhuma das 54
execuções resultou em falha…" **por:**

> Execuções que excedessem a memória disponível seriam registradas como
> resultado, e não descartadas. Nenhuma das 54 combinações, contudo, excedeu os
> 6 GB, o que é discutido na Seção 4.5. Como cada combinação foi executada uma
> vez, buscou-se identificar execuções cuja convergência tivesse falhado sem
> produzir erro por meio de um critério de monotonicidade, fixado antes da
> verificação: aumentar T, F ou L, mantidos os outros dois, não deveria reduzir o
> PSNR em mais de 0,47 dB (três vezes a mediana das amplitudes entre execuções
> idênticas). Três violações foram encontradas, envolvendo duas configurações de
> Garden; cada uma foi reexecutada duas vezes e reproduziu o resultado original
> dentro do ruído, o que caracteriza comportamento do modelo, e não falha de
> execução.

**3.4 — acrescentar ao final:**

> O tempo de treinamento, terceiro objetivo, é representado pela área de cada
> ponto na figura da fronteira e usado como critério de desempate na escolha do
> sweet spot.
>
> Como a fronteira reúne todas as configurações não dominadas, ela não aponta
> sozinha um ponto preferível. Para identificar o sweet spot de forma
> reprodutível, adotou-se um critério em três passos. Primeiro, localiza-se o
> joelho da fronteira: com PSNR e VRAM reescalados para o intervalo de 0 a 1
> entre os extremos da fronteira, o joelho é o ponto mais distante acima da reta
> que liga esses extremos (Satopää et al., 2011) — a partir dele, cada megabyte
> adicional compra cada vez menos qualidade. Segundo, como diferenças menores que
> a variação entre execuções idênticas não são distinguíveis (Seção 3.5),
> reúnem-se como candidatos o joelho e os pontos da fronteira que diferem dele em
> menos de 0,244 dB e 122 MB. Terceiro, escolhe-se entre os candidatos o de menor
> tempo de treinamento.
>
> A fronteira foi também convertida em um guia por orçamento de memória,
> organizado em patamares: cada patamar é a configuração de menor custo que
> supera o anterior em mais de 0,244 dB e custa mais de 122 MB além dele.
> Configurações cujo custo difere de um patamar melhor em menos de 122 MB são
> descartadas, por não representarem economia mensurável. Entre patamares,
> memória adicional não compra qualidade mensurável.

**3.5 — antes de** "A degradação de cada configuração em relação ao respectivo
baseline…", **acrescentar:**

> Para delimitar quais diferenças são distinguíveis, quatro configurações por
> cena foram executadas três vezes cada, com todos os parâmetros controláveis —
> inclusive a semente aleatória — mantidos constantes. A maior amplitude de PSNR
> entre execuções idênticas, 0,244 dB, foi adotada como limiar: diferenças
> menores não são usadas para ordenar configurações. Pelo mesmo procedimento,
> diferenças de VRAM inferiores a 122 MB não são tratadas como economia. Quando
> uma configuração foi medida mais de uma vez — baselines, validação do ruído,
> reexecuções da triagem —, usa-se a média de todas as medições.

**3.5 — substituir** "…dentro do limiar de −2 dB considerado aceitável na
literatura (Mildenhall et al., 2021; Müller et al., 2022)" **por:**

> …dentro de uma tolerância de −2 dB, adotada neste trabalho como limite de
> degradação aceitável.

### 3.5 Seção 4 — Análise dos resultados (nova)

> **4.1 Variabilidade entre execuções**
>
> Repetidas sob condições idênticas, as execuções variaram entre 0,023 e
> 0,244 dB de PSNR, com mediana de 0,157 dB. A variação decorre do
> não-determinismo das operações paralelas em GPU, e não da semente aleatória,
> mantida fixa. Uma execução em 24, contudo, convergiu para uma solução 1,81 dB
> inferior às demais da mesma configuração, com PSNR, SSIM e LPIPS concordando e
> sem qualquer sinal de erro. Esse comportamento, distinto do ruído, motivou a
> triagem de monotonicidade aplicada à grade (Seção 3.3), que não encontrou
> ocorrência semelhante nas 54 combinações.
>
> A consequência para a análise é direta: diferenças de PSNR abaixo de 0,244 dB
> não ordenam configurações. Em Bonsai, `T19 F2 L8` e `T17 F4 L8` diferem
> 0,014 dB e são indistinguíveis; em Garden, `T19 F2 L16` e `T19 F4 L4` diferem
> 0,08 dB em qualidade, mas 272 MB em memória.
>
> O limiar de 0,244 dB foi fixado antes da consolidação dos resultados. Ao reunir
> todas as medições disponíveis de cada configuração, a amplitude chegou a
> 0,34 dB em uma delas (`T19 F2 L16` em Garden, quatro medições), o que indica
> que o ruído pode ser algo maior que o limiar adotado. O limiar foi mantido, e a
> sensibilidade das conclusões a ele foi verificada (Seção 4.4).
>
> **4.2 Baseline**
>
> [Tabela 2] Em configuração padrão, Garden atingiu 21,01 dB (SSIM 0,495; LPIPS
> 0,558) com 4319 MB e 146 s de treinamento, e Bonsai 28,62 dB (SSIM 0,865; LPIPS
> 0,218) com 3376 MB e 150 s, como médias de cinco e seis execuções. A cena
> externa é mais difícil de reconstruir, como antecipado na Seção 2. Seu maior
> consumo de memória, porém, não decorre da complexidade da cena: as imagens de
> treino de Garden, embora em menor número (161 contra 255), somam 1,7 vez mais
> pixels e ocupam 2678 MB, contra 1576 MB em Bonsai. Descontadas as imagens,
> Garden consome menos que Bonsai (1641 contra 1800 MB).
>
> **4.3 Fronteira de Pareto e sweet spot**
>
> A Figura 7 apresenta a projeção entre PSNR e VRAM das 27 configurações de cada
> cena, com o tempo de treinamento representado pela área de cada ponto. A
> fronteira reúne 12 configurações em Garden e 10 em Bonsai.
>
> Em Garden, a fronteira tem um joelho pronunciado. Abaixo de cerca de 4040 MB,
> a qualidade cai de 20,7 para 14,7 dB sem economia relevante de memória; acima,
> cada ganho custa centenas de megabytes. O joelho é `T19 F2 L8` (20,86 dB,
> 4051 MB, 123 s), empatado dentro do ruído com `T19 F4 L4` e `T17 F4 L8`. Entre
> os três, `T19 F4 L4` é o mais rápido e constitui o sweet spot: 20,72 dB,
> 4040 MB e 92 s. Em relação à configuração padrão, ele perde 0,29 dB — pouco
> acima do ruído —, economiza 278 MB e reduz o tempo de treinamento em 37 %.
>
> Em Bonsai, a fronteira cresce de forma mais gradual, e o joelho é `T19 F2 L16`
> (28,71 dB, 3393 MB, 246 s). Ele empata com a própria configuração padrão
> (28,62 dB, 3376 MB), que treina em 150 s, 39 % menos tempo, e é, portanto, o
> sweet spot da cena.
>
> O sweet spot responde a uma pergunta diferente da do substituto para a
> configuração padrão. Se o objetivo é manter a qualidade do padrão com menos
> memória, Garden admite `T19 F2 L8`: −0,15 dB (dentro do ruído), −268 MB e
> −16 % de tempo. Em Bonsai, nenhuma configuração equivalente ao padrão é
> mensuravelmente mais barata: a configuração padrão já está na fronteira
> eficiente.
>
> **4.4 Guia por orçamento de memória**
>
> [Tabelas 3 e 4] Em Garden, três patamares cobrem a faixa útil: `T19 F4 L4`
> (20,72 dB, 4040 MB), a configuração padrão (21,01 dB, 4319 MB) e `T19 F4 L16`
> (21,28 dB, 4845 MB). A configuração de maior PSNR da grade, `T19 F8 L16`
> (21,47 dB, 5254 MB), não constitui patamar: supera `T19 F4 L16` em 0,19 dB,
> abaixo do ruído, ao custo de 409 MB.
>
> Em Bonsai, cinco patamares vão de `T17 F2 L8` (26,50 dB, 2905 MB) a
> `T19 F8 L16` (29,52 dB, 5039 MB). A configuração padrão é um deles. O último
> patamar custa 1084 MB para ganhar 0,39 dB — mais memória do que todos os
> anteriores somados. Nas duas cenas, nenhuma configuração com T = 15 formou
> patamar: reduzir o tamanho da tabela de hash foi a forma menos eficiente de
> economizar memória neste espaço de busca.
>
> Em relação à tolerância de −2 dB, 20 das 27 configurações de Garden e 15 das
> 27 de Bonsai permanecem dentro dela.
>
> Repetida com limiares de ruído entre 0,24 e 0,35 dB, a análise mantém os sweet
> spots das duas cenas e todo o guia de Bonsai. O guia de Garden é limítrofe: os
> dois degraus acima de `T19 F4 L4` (+0,29 e +0,26 dB) estão próximos do ruído,
> e, com limiar a partir de 0,29 dB, a configuração padrão deixa de se distinguir
> de `T19 F4 L4`, que passa a ser também o seu substituto.
>
> **4.5 O piso de memória**
>
> Nenhuma combinação excedeu os 6 GB. A razão está na composição do consumo: o
> Instant-NGP mantém as imagens de treino na VRAM a 4 bytes por pixel, o que
> resulta em 2678 MB em Garden e 1576 MB em Bonsai, independentemente dos
> hiperparâmetros da codificação. O restante do consumo variou de 1229 a
> 2576 MB em Garden e de 1329 a 3463 MB em Bonsai — uma alavanca de 1,3 e
> 2,1 GB, respectivamente. Mesmo na configuração mais leve,
> cerca de 1,2 a 1,3 GB não pertencem nem às imagens nem à codificação; essa
> parcela não foi decomposta, mas responde à extensão espacial da cena: em
> Garden, o `aabb_scale` sozinho moveu o pico em cerca de 500 MB (Seção 2.1).
>
> Essa composição delimita o alcance da otimização de hiperparâmetros. Ela
> permite escolher, dentro de um orçamento, a configuração de melhor qualidade,
> mas não reduz o custo dos dados, que determina a resolução máxima treinável.
> Na resolução original, só as imagens de treino já excedem a capacidade da placa
> nas duas cenas (10 707 MB em Garden e 6303 MB em Bonsai). Em Garden, abaixo de
> cerca de 4040 MB não houve economia mensurável: quatro configurações ocuparam
> entre 3907 e 4035 MB, com qualidade de 14,71 a 20,37 dB.
>
> **4.6 Efeito de cada hiperparâmetro: cena limitada e não-limitada**
>
> A Figura 8 e a Tabela 5 comparam, entre os dois regimes, o efeito de levar
> cada hiperparâmetro do menor ao maior valor, em média sobre as nove
> combinações dos outros dois. Em qualidade, os efeitos têm a mesma ordem de
> grandeza nos dois regimes, entre 1,5 e 3,2 dB, e L é o hiperparâmetro de maior
> efeito nas quatro cenas (2,1 a 3,2 dB). Em memória, T custa o mesmo nos dois
> regimes (290 a 370 MB), mas F e L custam cerca do dobro nas cenas
> não-limitadas: 520 a 670 MB, contra 265 a 285 MB no exp01. Em proporção do
> consumo total, o efeito em Garden (7 a 12 % do baseline) fica abaixo do
> observado no exp01 (13 a 16 %), porque o piso das imagens, maior nessa cena,
> dilui a parcela que os hiperparâmetros controlam; em Bonsai, fica entre 11 e
> 20 %.
>
> O efeito de cada hiperparâmetro depende fortemente dos outros dois. O custo de
> memória de F em Bonsai, por exemplo, varia de 96 a 1645 MB conforme T e L; em
> Garden, aumentar T chega a reduzir o PSNR em uma das combinações (−1,0 dB).
> Por isso, recomendações sobre um hiperparâmetro isolado têm alcance limitado, e
> o guia por orçamento é apresentado em termos de configurações completas.
>
> **4.7 Limitações**
>
> Os resultados se apoiam em duas cenas, uma única máquina e uma semente fixa. A
> maior parte das combinações da grade foi executada uma vez; o ruído foi medido
> em quatro configurações por cena e estendido às demais, e as medições reunidas
> depois sugerem que ele pode chegar a 0,34 dB, o que torna limítrofes os
> degraus do guia de Garden. A GPU era compartilhada
> com a interface gráfica do sistema operacional, cuja ocupação variou entre
> sessões, o que também torna as medidas de tempo mais frágeis que as de memória.
> Em Bonsai, os valores absolutos de PSNR estão cerca de 1 dB abaixo dos obtidos
> com 20 000 iterações, embora a ordenação entre configurações se preserve. O
> joelho depende dos extremos da fronteira, e mudaria com outro espaço de busca.
> Os valores absolutos de PSNR do exp01 e do exp02 não são comparáveis entre si.
> O LPIPS foi calculado em CPU, o que não afeta as medidas de memória. Por fim, a
> fronteira de viabilidade — a resolução em que a configuração padrão deixa de
> caber e uma mais leve ainda cabe — não foi medida: a janela entre as duas, de
> cerca de 400 MB, é menor que a variação da ocupação prévia da GPU observada
> nesta máquina.

**Tabela 5 — Efeito médio de levar cada hiperparâmetro do menor ao maior valor**

| Regime | Cena | ΔPSNR T (dB) | ΔPSNR F (dB) | ΔPSNR L (dB) | ΔVRAM T (MB) | ΔVRAM F (MB) | ΔVRAM L (MB) |
|---|---|---|---|---|---|---|---|
| limitada (exp01) | Lego | +2,46 | +1,65 | +2,79 | +328 | +278 | +266 |
| limitada (exp01) | Chair | +1,48 | +1,78 | +2,13 | +324 | +273 | +284 |
| não-limitada (exp02) | Garden | +1,52 | +2,60 | +2,90 | +291 | +516 | +532 |
| não-limitada (exp02) | Bonsai | +2,31 | +1,72 | +3,17 | +368 | +674 | +631 |

T: 15 → 19; F: 2 → 8; L: 4 → 16. Média sobre as 9 combinações dos outros dois.
Fonte: `runs/exp02_final/efeito_hiperparametros.csv` (inclui mínimo, máximo, %
do baseline e tempo).

### 3.6 Seção 5 — Conclusão (nova)

> Este trabalho investigou a configuração de hiperparâmetros da codificação hash
> do Instant-NGP para treinar modelos NeRF em uma GPU de consumo com 6 GB de
> VRAM. O estudo preliminar mostrou que o conjunto Synthetic-NeRF não exerce
> pressão de memória nesse hardware, o que motivou a migração para cenas reais
> não-limitadas do Mip-NeRF 360, precedida de uma calibração da extensão
> espacial e da resolução de cada cena.
>
> Os resultados mostram que a escolha de hiperparâmetros desloca o consumo de
> memória em 1,3 a 2,1 GB e organiza as configurações em poucos patamares de
> qualidade distinguível: três em Garden, dois deles próximos do limiar de
> ruído, e cinco em Bonsai. Em Garden, o sweet
> spot (`T19 F4 L4`) entrega 20,72 dB com 278 MB e 37 % de tempo a menos que a
> configuração padrão; em Bonsai, o sweet spot é a própria configuração padrão.
> As configurações de maior capacidade custaram centenas de megabytes por ganhos
> próximos ou inferiores à variabilidade do próprio treinamento. Entre os três
> hiperparâmetros, o número de níveis teve o maior efeito sobre a qualidade nas
> quatro cenas estudadas, e reduzir o tamanho da tabela de hash foi a forma
> menos eficiente de economizar memória.
>
> Dois resultados metodológicos acompanham o guia. Primeiro, diferenças de
> qualidade abaixo de cerca de 0,24 dB não são distinguíveis entre execuções
> idênticas do Instant-NGP, o que limita o grau de detalhe com que configurações
> podem ser ordenadas. Segundo, o piso de memória é dominado pelas imagens de
> treino e por um custo fixo de execução, ambos fora do alcance da otimização de
> hiperparâmetros: ela permite escolher bem dentro de um orçamento, mas não
> ampliar a resolução treinável.
>
> Como trabalhos futuros, propõem-se: a delimitação empírica da fronteira de
> viabilidade, sob controle rigoroso da ocupação prévia da GPU; a extensão a mais
> cenas e a múltiplas sementes; a decomposição do custo fixo de execução; e
> estratégias que reduzam o custo de memória dos dados de treino, como manter as
> imagens em precisão reduzida ou carregá-las sob demanda.

---

## 4. Referências

**Citadas no texto e ausentes da lista:**

- ABADI, Martín et al. TensorFlow: a system for large-scale machine learning. In:
  USENIX SYMPOSIUM ON OPERATING SYSTEMS DESIGN AND IMPLEMENTATION, 12., 2016.
- BARRON, Jonathan T. et al. Mip-NeRF 360: unbounded anti-aliased neural
  radiance fields. In: IEEE/CVF CONFERENCE ON COMPUTER VISION AND PATTERN
  RECOGNITION, 2022.
- BERGSTRA, James; BENGIO, Yoshua. Random search for hyper-parameter
  optimization. Journal of Machine Learning Research, v. 13, p. 281–305, 2012.
- CHEN, Anpei et al. TensoRF: tensorial radiance fields. In: EUROPEAN
  CONFERENCE ON COMPUTER VISION, 2022.
- MILDENHALL, Ben et al. Local light field fusion: practical view synthesis with
  prescriptive sampling guidelines. ACM Transactions on Graphics, v. 38, n. 4,
  2019.
- NVLABS. instant-ngp. GitHub, 2025. **[verificar URL e data de acesso]**

**Nova, se o critério do joelho for citado (3.4):**

- SATOPÄÄ, Ville et al. Finding a "Kneedle" in a haystack: detecting knee points
  in system behavior. In: INTERNATIONAL CONFERENCE ON DISTRIBUTED COMPUTING
  SYSTEMS WORKSHOPS, 31., 2011. O algoritmo descrito ali normaliza os dois eixos
  e procura o ponto de maior afastamento da reta entre os extremos — o mesmo
  critério usado aqui.

**Na lista e não citadas:** DESCARTES (2001) e FOLEY et al. (1996). Remover, ou
citar onde couber.

**A conferir:**

- SHIN; PARK (2023), *Binary radiance fields*, aparece como "ACM Computing
  Surveys". O trabalho, até onde se sabe, foi publicado na NeurIPS 2023.
  **[verificar]**
- ZHANG et al. (2018) termina com resto do modelo: "Edição. Cidade: Editora, Ano
  de Publicação." — apagar.
- Mip-NeRF 360: usar "Barron et al., 2022" em todo o texto.

**[verificar]** os dados completos de cada entrada acrescentada — servem para
localizar a obra, não para copiar sem conferência.

---

## 5. Figuras e tabelas

Numeração proposta, na ordem em que aparecem no texto.

| nº | conteúdo | arquivo | seção | situação |
|---|---|---|---|---|
| Fig. 1 | exp01, PSNR × VRAM | (mantida) | 2 | ok |
| Fig. 2 | comparação visual de `aabb_scale`, Garden | `runs/aabb_check/garden_5000/comparacao.png` | 2.1 | ok — trocar a legenda |
| Fig. 3 | PSNR, SSIM e VRAM por `aabb_scale`, Garden e Bonsai | `runs/exp02_final/aabb_calibracao.pdf` | 2.1 | **substitui a atual** |
| Fig. 4 | convergência, Garden | `runs/etapa15_final/garden_f2/justificativa_iteracoes.png` | 3.2 | **nova** |
| Fig. 5 | convergência, Bonsai | `runs/exp02_convergence_bonsai/bonsai_f2/justificativa_iteracoes.png` | 3.2 | é a atual Fig. 4 |
| Fig. 6 | PSNR a 5000 e a 20 000 iterações, Bonsai | `runs/exp02_ordenacao/ordenacao.png` | 3.2 | **nova** |
| Fig. 7 | fronteira de Pareto com tempo na área da bolha e sweet spot | `runs/exp02_final/pareto_bolhas.pdf` | 4.3 | **nova** — principal |
| Fig. 8 | efeito de cada hiperparâmetro, exp01 × exp02 | `runs/exp02_final/efeito_hiperparametros.pdf` | 4.6 | **nova** |
| Tab. 1 | calibração da resolução | seção 3.3 acima | 2 | **substitui a atual** |
| Tab. 2 | baselines | `runs/exp02_final/tabelas.md` | 4.2 | nova |
| Tab. 3–4 | patamares por cena | `runs/exp02_final/tabelas.md` | 4.4 | nova |
| Tab. 5 | efeito por hiperparâmetro | seção 3.5 acima | 4.6 | nova |

**Sobre a Fig. 3 nova.** A figura atual usa dois eixos verticais no mesmo painel
(PSNR e SSIM) e mostra a VRAM do dispositivo, que inclui a ocupação do Windows.
A nova põe cada medida no seu painel, usa o pico descontada a ocupação prévia —
a mesma medida da Tabela 1 e da Seção 4 — e cobre as duas cenas, o que resolve
também a falta de justificativa do `aabb_scale` = 8 em Bonsai.

**Sobre a Fig. 7.** `pareto_bolhas.pdf` traz as duas cenas empilhadas, com
legenda única — numa página em retrato, cada cena ocupa a largura inteira. Se a
diagramação pedir as cenas separadas (por exemplo, 7a e 7b em páginas
diferentes), há `pareto_bolhas_garden.pdf` e `pareto_bolhas_bonsai.pdf`, cada
uma com a legenda completa. Dados em `runs/exp02_final/sweet_spot.csv`.

### Opcionais

| conteúdo | arquivo | uso |
|---|---|---|
| fronteira com a faixa de ruído | `runs/exp02_final/pareto_espessura.pdf` | se quiser mostrar a espessura da fronteira separadamente |
| patamares do guia em função do limiar de ruído | `runs/exp02_final/sensibilidade_ruido.pdf` | 4.4, se a banca pedir a sensibilidade |
| como o joelho é encontrado | `runs/exp02_final/joelho_explicado.pdf` | apêndice, ou só para a defesa |
| variabilidade entre execuções | `runs/exp02_variance/variancia.png` | 4.1 |
| VRAM e PSNR por resolução | `runs/etapa1_final/resolucao_final.png` | 2, ao lado da Tabela 1 |
| folha de contato por resolução | `runs/etapa1_final/comparacao_resolucao.png` | apêndice |

Para as figuras de convergência, `justificativa_iteracoes.png` (quatro painéis)
é preferível a `convergencia.png` por conter o painel de custo; se o espaço
apertar, usar só os painéis de PSNR e de ganho marginal.
