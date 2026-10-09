# Artigo v2 — texto proposto

Texto para transcrever no artigo (`docs/TCC Artigo - InstantNGP.pdf`, v1).
Organizado em: (A) correções pontuais, (B) referências, (C) texto revisado por
seção, (D) figuras e tabelas. Trechos marcados **[verificar]** dependem de
informação que só o autor tem.

Números: todos rastreáveis a `runs/` e aos relatórios em `docs/`
(`RELATORIO-fechamento.md`, `RELATORIO-exp02-validacoes.md`,
`runs/exp02_final/tabelas.md`).

---

## A. Correções pontuais

### A.1 Valores e afirmações

| local (v1) | problema | correção |
|---|---|---|
| Tabela 1, p. 7–8 | medida com a configuração mais pesada do grid, `aabb_scale=16` e sem divisão treino/teste; diz que `garden` f2 deu OOM | substituir pela Tabela 1 da seção C.2 |
| p. 12 | "Müller et al. (2022) fixam L=16, T=19 e F=2 como configuração padrão… vértice superior… baseline" | o `base.json` usado é **T=19, F=4, L=8**, ponto interior do grid; ver C.3 |
| p. 12 | "redução proporcional no consumo de VRAM" | parâmetros variam 238×, VRAM varia ~1,3× em `garden`; ver C.3 |
| p. 12 | "esperava-se que uma parcela das combinações pudesse exceder os 6 GB" | nenhuma excedeu (56/56); ver C.3 |
| p. 9 | "contradiz a recomendação inicial dos autores do Instant-NGP" | **confirma** a recomendação (começar alto e reduzir) |
| p. 7 | critério de escolha da resolução | nenhum fator caiu entre 5 e 6 GB; o critério efetivo foi a maior resolução viável |
| p. 11 | defende 20 000 iterações e deixa `[N]` | 5000, com justificativa medida por cena; ver C.3 |
| p. 14 | "limiar de −2 dB considerado aceitável na literatura (Mildenhall et al., 2021; Müller et al., 2022)" | nenhum dos dois trabalhos define esse limiar. Apresentar como critério adotado pelo trabalho, sem atribuir à literatura |
| p. 4 | "causando constantes erros por falta de memória" | nenhuma execução do grid falhou por memória; ver C.1 |
| p. 1–2 | "a metodologia divide-se em três etapas" | a Seção 3 descreve quatro, além da calibração prévia |
| p. 10 | "Ryzen 7 7700 X3D … 16 GB de RAM DDR4" **[verificar]** | o modelo 7700 X3D não existe (há 7700X e 7800X3D), e a série Ryzen 7000 usa DDR5. Acrescentar a RAM disponível ao WSL (~7,7 GB medidos) |

### A.2 Terminologia

"Fator" designa duas grandezas no texto. Reservar **fator de redução** para a
resolução (2, 4, 8) e escrever sempre **`aabb_scale`** por extenso, inclusive na
legenda da Figura 2 ("valores de `aabb_scale` de 2 a 32", não "fatores").

### A.3 Título e revisão de texto

- Título em português com dois-pontos duplos: "…UM OLHAR PARA OTIMIZAÇÃO DE
  HIPERPARÂMETROS: EM HARDWARES…". Sugestão: **"Treinamento de modelos NeRF
  baseados em grade: otimização de hiperparâmetros em hardware de baixa
  especificação"**.
- Título em inglês termina em "ON LOW-SPECIFICATION" — falta "HARDWARE".
- Grafia: "amplamentes", "parametreis", "extresmos", "experiemento",
  "experimentacao", "tambem", "fato de aabb_scale" (legenda da Figura 3),
  "em relativamente" (p. 12).
- "características dissidentes" (p. 5) → "características distintas".

---

## B. Referências

**Citadas no texto e ausentes da lista:**

- ABADI, Martín et al. TensorFlow: a system for large-scale machine learning. 2016.
- BARRON, Jonathan T. et al. Mip-NeRF 360: unbounded anti-aliased neural
  radiance fields. In: IEEE/CVF CONFERENCE ON COMPUTER VISION AND PATTERN
  RECOGNITION, 2022.
- BERGSTRA, James; BENGIO, Yoshua. Random search for hyper-parameter
  optimization. Journal of Machine Learning Research, v. 13, 2012.
- CHEN, Anpei et al. TensoRF: tensorial radiance fields. In: EUROPEAN
  CONFERENCE ON COMPUTER VISION, 2022.
- MILDENHALL, Ben et al. Local light field fusion: practical view synthesis with
  prescriptive sampling guidelines. ACM Transactions on Graphics, 2019.
- NVLABS. instant-ngp (repositório). 2025. **[verificar URL e data de acesso]**

**Na lista e não citadas:** DESCARTES (2001) e FOLEY et al. (1996) —
provavelmente herança do modelo; remover ou citar.

**Inconsistências:** Mip-NeRF 360 aparece como "Barron, et al. 2021" (p. 6) e
"Barron et al., 2022" (p. 6). Usar 2022 (CVPR). A referência ZHANG et al. termina
com resto do modelo ("Edição. Cidade: Editora, Ano de Publicação.").

**[verificar]** os dados completos de cada entrada adicionada — os acima são de
memória e servem para localizar a obra, não para copiar sem conferência.

---

## C. Texto revisado

### C.1 Resumo, Abstract e Introdução

**Resumo — substituir a partir de "A metodologia divide-se…":**

> A metodologia compreende uma calibração prévia do cenário experimental, com a
> escolha de resolução e de extensão espacial da cena para duas cenas reais
> não-limitadas do conjunto Mip-NeRF 360, seguida de quatro etapas: definição de
> um baseline com o Instant-NGP em configuração padrão, exploração sistemática
> de 27 combinações de hiperparâmetros da codificação de hash por cena, análise
> multiobjetivo por Fronteira de Pareto e avaliação comparativa pelas métricas
> PSNR, SSIM e LPIPS, pico de VRAM e tempo de treinamento. A variabilidade entre
> execuções idênticas foi medida e usada para delimitar quais diferenças são
> distinguíveis. Os resultados indicam que a escolha de hiperparâmetros desloca o
> consumo de memória em até cerca de 1,3 a 2,1 GB, que diferenças de qualidade
> abaixo de 0,24 dB não são distinguíveis do ruído do próprio treinamento, e que
> o piso de memória é dominado pelas imagens de treino, que esses
> hiperparâmetros não alcançam. O produto é um guia de configuração por
> orçamento de memória para treinar modelos NeRF em hardware acessível.

*(O Abstract deve ser atualizado em paralelo.)*

**Introdução, p. 4 — substituir "Na prática, isso cria um novo impeditivo para
hardwares limitados, causando constantes erros por falta de memória e
restringindo novamente a técnica (Liao et al., 2025)" por:**

> Na prática, isso cria um novo impeditivo para hardwares limitados: o consumo
> de memória passa a condicionar quais configurações e resoluções podem ser
> treinadas, restringindo novamente a técnica (Liao et al., 2025).

**Introdução, p. 4 — no parágrafo "É exatamente neste gargalo…", substituir
"O objetivo final é fornecer um guia prático…" por:**

> O objetivo final é fornecer um guia prático que indique, para cada orçamento
> de memória disponível, a configuração de menor custo que entrega qualidade
> mensuravelmente superior à anterior, e que delimite até onde a otimização de
> hiperparâmetros pode levar — distinguindo o que ela controla do que depende
> apenas do volume de dados de treino.

### C.2 Seção 2 — reordenar: `aabb_scale` antes da resolução

A dependência entre as duas calibrações é a oposta da ordem atual: o
`aabb_scale` altera o consumo de VRAM, então a resolução precisa ser calibrada
com ele já fixado. Proposta de estrutura:

- **2** Estudo preliminar e definição do cenário (texto atual até a Figura 1 e o
  parágrafo da cena Bonsai, mantidos)
- **2.1** Divisão entre treino e teste *(mover da Seção 3.2)*
- **2.2** Calibração do `aabb_scale`
- **2.3** Calibração da resolução

**Seção 2, após a Figura 1 — acrescentar o número que torna o argumento
concreto:**

> No exp01, o pico de VRAM não ultrapassou 2981 MB em nenhuma das 54 execuções,
> e nenhuma falhou por falta de memória: o conjunto Synthetic-NeRF não exerce
> pressão sobre uma GPU de 6 GB.

**2.1 Divisão entre treino e teste** — texto atual da p. 10–11 ("Diferentemente
do exp01, no qual o dataset Synthetic-NeRF…" até "…ambas as cenas"), acrescido
de:

> Com essa regra, Garden passou a contar com 161 imagens de treino e 24 de
> teste, e Bonsai com 255 e 37. Todas as métricas de qualidade deste trabalho
> foram calculadas sobre as vistas retidas.

**2.2 Calibração do `aabb_scale`** — manter o parágrafo atual da p. 8 sobre o
parâmetro e a recomendação da documentação; substituir o texto da atual Seção
2.1 por:

> A calibração foi realizada em duas fases. Na primeira, de triagem, cada valor
> candidato de `aabb_scale` (2, 4, 8, 16 e 32) foi usado em um treinamento breve,
> e a reconstrução de uma vista retida foi inspecionada em busca de artefatos
> (Figura 2). Valores pequenos demais colapsaram a cena; o valor inicialmente
> adotado, 16, produziu névoa sobre metade da imagem. A inspeção visual,
> contudo, não separou com segurança os melhores candidatos, e foi seguida de
> uma segunda fase quantitativa: treinamentos completos de 5000 iterações para
> cada valor, avaliados pelo PSNR e pelo SSIM médios sobre todas as vistas
> retidas (Figuras 3 e 4).
>
> O valor ótimo diferiu entre as cenas: 4 para Garden (20,95 dB; SSIM 0,493) e 8
> para Bonsai (28,60 dB; SSIM 0,865). O valor inicial de 16 custava 5,6 dB em
> Garden e 14,5 dB em Bonsai. O resultado confirma a orientação da documentação
> oficial, de partir de um valor elevado e reduzi-lo progressivamente, e mostra
> que o passo de redução não é opcional. Mostra também que a inspeção visual
> isolada é insuficiente para a escolha final: em Garden, a comparação de uma
> única vista sugeria o valor 8, enquanto a média sobre as 24 vistas retidas
> indicou 4 com 2,2 dB de vantagem.

**2.3 Calibração da resolução** — manter o primeiro parágrafo atual da p. 7
("Diferentemente do Synthetic-NeRF, contudo…" até "…calibração prévia à
execução do experimento principal") e substituir o restante por:

> A calibração consistiu em treinar o Instant-NGP em sua configuração padrão,
> com o `aabb_scale` já fixado e a divisão entre treino e teste aplicada, em cada
> uma das resoluções disponíveis, registrando o pico de alocação de VRAM
> descontada a ocupação prévia da placa pelo sistema operacional (Tabela 1). A
> ocupação prévia foi descontada porque variou entre 254 e 1457 MB ao longo dos
> experimentos, e o valor absoluto do dispositivo não é comparável entre
> execuções.
>
> [Tabela 1]
>
> Na resolução original, nenhuma das cenas pôde ser treinada. Em Garden, o
> carregamento das imagens esgotou a memória do sistema hospedeiro antes de
> alcançar a GPU. Em Bonsai, o processo terminou sem erro, mas com a vazão
> reduzida de cerca de 34 para 1 iteração por segundo: as imagens de treino,
> que o Instant-NGP mantém na VRAM a 4 bytes por pixel, somam 6303 MB, acima da
> capacidade da placa, e o controlador paginou dados para a memória do sistema.
> Execuções nessa condição foram classificadas como inviáveis, ainda que
> concluídas.
>
> Nenhuma resolução viável aproximou o consumo da configuração padrão do limite
> de 6 GB: o fator 2 consumiu 4312 MB em Garden e 3388 MB em Bonsai. Adotou-se,
> para as duas cenas, o fator 2 (2594×1681 e 1559×1039 pixels), a maior
> resolução viável. Nela, o extremo de maior capacidade do espaço de busca
> aproxima-se do limite da placa, o que garante que o eixo de custo da análise
> multiobjetivo percorra a maior parte da memória disponível.

**Tabela 1 — Calibração da resolução** (configuração padrão, `aabb_scale`
validado, divisão retida):

| Cena | Fator | Resolução | Treino / teste | Situação | Pico − base (MB) | PSNR (dB) |
|---|---|---|---|---|---|---|
| Garden | 8 | 648×420 | 161 / 24 | viável | 1322,4 | 22,53 |
| Garden | 4 | 1297×840 | 161 / 24 | viável | 2053,3 | 21,35 |
| Garden | 2 | 2594×1681 | 161 / 24 | viável | 4311,8 | 20,99 |
| Garden | 1 | 5187×3361 | 161 / 24 | inviável (RAM do sistema) | — | — |
| Bonsai | 8 | 390×260 | 255 / 37 | viável | 1329,8 | 29,87 |
| Bonsai | 4 | 780×520 | 255 / 37 | viável | 1682,3 | 28,82 |
| Bonsai | 2 | 1559×1039 | 255 / 37 | viável | 3388,3 | 28,64 |
| Bonsai | 1 | 3118×2078 | 255 / 37 | inviável (paginação) | — | — |

Fonte: `runs/etapa1_final/` e `runs/etapa1_final_bonsai/`.

### C.3 Seção 3 — Metodologia

**3.1 Ambiente experimental — substituir por:**

> O ambiente utilizado foi uma GPU NVIDIA RTX 2060 com 6 GB de memória de vídeo,
> uma CPU **[verificar modelo]** e **[verificar]** GB de RAM, com os
> experimentos executados no WSL (*Windows Subsystem for Linux*) com Ubuntu
> 22.04, ao qual estavam disponíveis cerca de 7,7 GB de memória do sistema. A
> GPU era compartilhada com a interface gráfica do Windows, que ocupou entre 254
> e 1457 MB de VRAM antes do início dos experimentos, a depender da sessão.
> Todas as execuções foram sequenciais, e a ocupação prévia foi medida antes de
> cada uma.

**3.2 Definição do baseline — substituir o parágrafo dos placeholders por:**

> O baseline consiste no treinamento do Instant-NGP com o arquivo de
> configuração de rede distribuído com a implementação (`base.json`), sem
> qualquer alteração, aplicado a cada uma das duas cenas na resolução e no
> `aabb_scale` definidos na calibração: fator 2 (2594×1681 pixels) e
> `aabb_scale` = 4 para Garden; fator 2 (1559×1039 pixels) e `aabb_scale` = 8
> para Bonsai. Cabe registrar que esse arquivo define `T` = 19, `F` = 4 e
> `L` = 8, e não os valores apresentados como padrão no artigo original
> (`T` = 19, `F` = 2, `L` = 16) (Müller et al., 2022). Adotou-se o arquivo
> distribuído por ser a configuração que um usuário efetivamente executa.

**3.2 — manter o parágrafo de `nerf_compatibility`, acrescentando ao final:**

> Essa opção altera o próprio treinamento, e não apenas a avaliação: ela anula
> o alargamento progressivo do passo de amostragem ao longo do raio, mecanismo
> que torna viável percorrer cenas não-limitadas com caixa delimitadora
> ampliada.

**3.2 — substituir o parágrafo das iterações por:**

> O número de iterações foi definido em 5000, mesmo valor do exp01, após
> validação específica por cena. Para cada cena, a configuração padrão foi
> treinada por 30 000 iterações, com avaliação das vistas retidas a cada 2000
> (Figuras 6 e 7). Em Garden, o ganho marginal caiu abaixo de 0,1 dB a cada
> 1000 iterações já a partir de 4000, e o ganho total entre 4000 e 30 000
> iterações (0,24 dB) mostrou-se inferior à variabilidade entre execuções
> idênticas (Seção 4.1) — isto é, indistinguível. Em Bonsai, a convergência foi
> mais lenta: o mesmo limiar só foi atingido em 10 000 iterações, e restaram
> cerca de 1,6 dB entre 4000 e 30 000. Nas duas cenas, observou-se um aumento do
> ganho marginal ao cruzar 20 000 iterações, ponto em que se inicia o decaimento
> programado da taxa de aprendizado.
>
> Como a análise multiobjetivo depende da ordenação entre configurações, e não
> de seus valores absolutos, verificou-se se o treinamento abreviado em Bonsai
> distorcia essa ordenação. Quatro configurações que cobrem a faixa de
> capacidade do espaço de busca foram treinadas por 20 000 iterações (Figura 8):
> todas ganharam entre 1,00 e 1,12 dB, nenhuma inverteu de posição, e a
> diferença entre a de menor e a de maior capacidade variou apenas 0,008 dB. O
> truncamento desloca uniformemente os valores de Bonsai, sem alterar a
> ordenação, e 5000 iterações foram mantidas para as duas cenas.

**3.3 Exploração dos hiperparâmetros — substituir o trecho "Müller et al.
(2022) fixam L = 16, T = 19 e F = 2…" até "…ao baseline descrito na Seção 3.2"
por:**

> O baseline (`T` = 19, `F` = 4, `L` = 8) é um ponto interior desse espaço de
> busca, que contém configurações de maior e de menor capacidade.
>
> O arquivo de configuração não define a razão de crescimento da resolução entre
> níveis (`per_level_scale`). Nesse caso, a implementação a deriva do
> `aabb_scale`, de modo que o nível mais fino alcance 2048 · `aabb_scale` sobre o
> cubo unitário. Para que variar `L` não alterasse simultaneamente a resolução do
> nível mais fino, a razão foi fixada para cada configuração com o mesmo alvo,
> o que faz a configuração com `L` = 8 reproduzir exatamente o baseline e mantém
> baseline e grade na mesma escala.

**3.3 — substituir "reduções em qualquer um dos três implicam, portanto,
redução proporcional no consumo de VRAM" por:**

> reduções em qualquer um dos três reduzem o número de parâmetros, mas não
> proporcionalmente o consumo de VRAM: parte relevante desse consumo independe da
> codificação, como se mostra na Seção 4.4.

**3.3 — substituir o parágrafo "Diferentemente do exp01, no qual nenhuma das 54
execuções…" por:**

> As execuções que excedessem a memória disponível seriam registradas como
> resultado, e não descartadas. Nenhuma das 54 combinações, contudo, excedeu os
> 6 GB, o que é discutido na Seção 4.4. Para detectar execuções cuja convergência
> tivesse falhado sem produzir erro, aplicou-se ao conjunto um critério de
> monotonicidade: o aumento isolado de `T`, `F` ou `L` não deveria reduzir o
> PSNR em mais de 0,47 dB. Três violações foram encontradas, envolvendo duas
> configurações; cada uma foi reexecutada duas vezes e reproduziu o resultado
> original, configurando comportamento real do modelo e não falha de execução.

**3.5 Avaliação das métricas — acrescentar ao final:**

> O pico de VRAM é reportado descontada a ocupação da placa medida
> imediatamente antes de cada execução. Para delimitar quais diferenças de
> qualidade são distinguíveis, quatro configurações por cena foram executadas
> três vezes cada, com todos os parâmetros controláveis — inclusive a semente
> aleatória — mantidos constantes. A maior amplitude de PSNR observada entre
> execuções idênticas, 0,244 dB, foi adotada como limiar: diferenças menores não
> são usadas para ordenar configurações. Pelo mesmo procedimento, diferenças de
> VRAM inferiores a 122 MB não são tratadas como economia.

**3.5 — substituir "…dentro do limiar de −2 dB considerado aceitável na
literatura (Mildenhall et al., 2021; Müller et al., 2022)" por:**

> …dentro de uma tolerância de −2 dB adotada neste trabalho como limite de
> degradação aceitável.

### C.4 Seção 4 — Análise dos resultados (nova)

> **4.1 Variabilidade entre execuções**
>
> Repetidas sob condições idênticas, as execuções variaram entre 0,023 e
> 0,244 dB de PSNR, com mediana de 0,157 dB (Figura 9). A variação decorre do
> não-determinismo das operações paralelas em GPU, e não da semente aleatória,
> mantida fixa. Uma execução em 24, contudo, convergiu para uma solução 1,81 dB
> inferior às demais da mesma configuração, com PSNR, SSIM e LPIPS concordando,
> sem qualquer sinal de erro. Esse comportamento, distinto do ruído, motivou o
> critério de monotonicidade aplicado à grade (Seção 3.3), que não detectou
> ocorrências semelhantes nas 54 combinações.
>
> A consequência para a análise é direta: diferenças de PSNR abaixo de 0,244 dB
> não ordenam configurações. Em Bonsai, por exemplo, `T19 F2 L8` e `T17 F4 L8`
> diferem 0,014 dB, e são indistinguíveis; em Garden, `T19 F2 L16` e `T19 F4 L4`
> diferem 0,113 dB em qualidade, mas 275 MB em VRAM.
>
> **4.2 Baseline**
>
> [Tabela 2] Em configuração padrão, Garden atingiu 21,01 dB (SSIM 0,495; LPIPS
> 0,558) com 4319 MB, e Bonsai 28,62 dB (SSIM 0,865; LPIPS 0,218) com 3376 MB,
> como média de cinco e seis execuções, respectivamente. A diferença entre as
> cenas acompanha o perfil antecipado na Seção 2: a cena externa, com fundo
> extenso e vegetação, é mais difícil de reconstruir e mais custosa em memória
> que a interna, mesmo com menos imagens.
>
> **4.3 Fronteira de Pareto e guia de configuração**
>
> As 54 combinações e os dois baselines foram executados em 4 h 04 min. A
> Figura 10 apresenta a projeção entre PSNR e VRAM com uma faixa de 0,244 dB sob
> a fronteira: configurações dentro dessa faixa são equivalentes à fronteira no
> limite do que os dados resolvem. Em vez de recomendar um único ponto, a
> fronteira foi convertida em uma sequência de patamares (Tabelas 3 e 4): cada
> patamar é a configuração mais barata que supera o anterior em mais de
> 0,244 dB e custa mais de 122 MB além dele. Entre patamares, memória adicional
> não compra qualidade mensurável.
>
> Em Garden, três patamares cobrem a faixa útil: `T19 F4 L4` (20,72 dB,
> 4040 MB), o baseline (21,01 dB, 4319 MB) e `T19 F4 L16` (21,28 dB, 4845 MB). A
> configuração de maior PSNR da grade, `T19 F8 L16` (21,47 dB, 5254 MB), não
> constitui patamar: supera `T19 F4 L16` em 0,19 dB, abaixo do limiar, ao custo
> de 409 MB. O baseline admite um substituto: `T19 F2 L8` entrega qualidade
> equivalente (−0,15 dB) com 268 MB a menos (−6,2 %) e 16 % menos tempo de
> treinamento.
>
> Em Bonsai, cinco patamares vão de `T17 F2 L8` (26,50 dB, 2905 MB) a
> `T19 F8 L16` (29,52 dB, 5039 MB). O baseline é um dos patamares e nenhuma
> configuração equivalente o supera em economia de memória: na cena interna, a
> configuração padrão já está sobre a fronteira eficiente. O último patamar
> custa 1084 MB para ganhar 0,39 dB — mais memória do que todos os patamares
> anteriores somados.
>
> **4.4 O piso de memória**
>
> Nenhuma combinação excedeu os 6 GB. A razão está na composição do consumo: o
> Instant-NGP mantém as imagens de treino na VRAM a 4 bytes por pixel, o que
> resulta em 2677 MB em Garden e 1576 MB em Bonsai, independentemente dos
> hiperparâmetros da codificação. A parcela que os hiperparâmetros controlam
> variou de 1240 a 2577 MB em Garden e de 1329 a 3463 MB em Bonsai. Em Garden,
> abaixo de cerca de 4040 MB não houve economia mensurável: quatro
> configurações ocuparam entre 3907 e 4035 MB, com qualidade de 14,71 a
> 20,37 dB. Escolher a mais fraca nessa faixa apenas perde qualidade.
>
> Essa composição delimita o alcance da otimização de hiperparâmetros. Ela
> desloca o consumo dentro de uma faixa de 1,3 a 2,1 GB e permite escolher, para
> cada orçamento, a configuração de melhor qualidade; não reduz, porém, o custo
> dos dados, que determina a resolução máxima treinável. Na resolução original,
> só as imagens de treino excedem a capacidade da placa nas duas cenas.

### C.5 Seção 5 — Conclusão (nova)

> Este trabalho investigou a configuração de hiperparâmetros do Instant-NGP para
> treinar modelos NeRF em uma GPU de consumo com 6 GB de VRAM. O estudo
> preliminar mostrou que o conjunto Synthetic-NeRF não exerce pressão de memória
> nesse hardware, o que motivou a migração para cenas reais não-limitadas do
> Mip-NeRF 360, precedida de uma calibração da extensão espacial e da resolução
> de cada cena.
>
> Os resultados mostram que a escolha de hiperparâmetros desloca o consumo de
> memória em 1,3 a 2,1 GB e organiza as configurações em poucos patamares de
> qualidade distinguível: três em Garden e cinco em Bonsai. A configuração
> padrão da implementação mostrou-se eficiente nas duas cenas — na fronteira em
> Bonsai e substituível, em Garden, por uma configuração equivalente que
> economiza 268 MB e 16 % do tempo. As configurações de maior capacidade
> custaram centenas de megabytes por ganhos próximos ou inferiores à
> variabilidade do próprio treinamento.
>
> Dois resultados metodológicos acompanham o guia. Primeiro, diferenças de
> qualidade abaixo de cerca de 0,24 dB não são distinguíveis entre execuções
> idênticas do Instant-NGP, o que limita o grau de detalhe com que configurações
> podem ser ordenadas — e que a literatura raramente reporta. Segundo, o piso
> de memória é dominado pelas imagens de treino e está fora do alcance da
> otimização de hiperparâmetros: ela permite escolher bem dentro de um
> orçamento, mas não ampliar a resolução treinável.
>
> Como trabalhos futuros, propõem-se: a delimitação empírica da fronteira de
> viabilidade, com a resolução ajustada para que a configuração padrão exceda a
> memória disponível enquanto configurações mais leves permaneçam treináveis, sob
> controle rigoroso da ocupação prévia da GPU; a extensão a mais cenas e a
> múltiplas sementes; e a investigação de estratégias que reduzam o custo de
> memória dos dados de treino, que os hiperparâmetros da codificação não
> alcançam.

### C.6 Limitações (nova subseção, em 4 ou 5)

> Os resultados se apoiam em duas cenas, uma única máquina e uma semente fixa.
> Cada combinação da grade foi executada uma vez; a variabilidade foi medida em
> quatro configurações por cena e extrapolada às demais. A GPU era compartilhada
> com a interface gráfica do sistema operacional, cuja ocupação variou entre
> sessões. Em Bonsai, os valores absolutos de PSNR estão cerca de 1 dB abaixo
> dos obtidos com 20 000 iterações, embora a ordenação entre configurações se
> preserve. O LPIPS foi calculado em CPU, o que não afeta as medidas de memória
> mas aumenta o tempo de avaliação.

---

## D. Figuras e tabelas

### Essenciais

| nº | conteúdo | arquivo | seção |
|---|---|---|---|
| Fig. 1 | exp01, PSNR × VRAM | (mantida) | 2 |
| Fig. 2 | comparação visual de `aabb_scale`, Garden | `runs/aabb_check/garden_5000/comparacao.png` | 2.2 |
| Fig. 3 | `aabb_scale` quantitativo, Garden | `runs/aabb_quantitativo/aabb_quantitativo.png` | 2.2 |
| Fig. 4 | `aabb_scale` quantitativo, Bonsai | `runs/aabb_quantitativo_bonsai/aabb_quantitativo.png` | 2.2 |
| Fig. 6 | convergência, Garden | `runs/etapa15_final/garden_f2/justificativa_iteracoes.png` | 3.2 |
| Fig. 7 | convergência, Bonsai | `runs/exp02_convergence_bonsai/bonsai_f2/justificativa_iteracoes.png` | 3.2 |
| Fig. 8 | ordenação a 5000 e 20 000 iterações, Bonsai | `runs/exp02_ordenacao/ordenacao.png` | 3.2 |
| Fig. 10 | fronteira de Pareto com faixa de ruído | `runs/exp02_final/pareto_espessura.pdf` | 4.3 |
| Fig. 11 | fronteira de Pareto com tempo de treino na área da bolha e sweet spot de cada cena | `runs/exp02_final/pareto_bolhas.pdf` (dados: `sweet_spot.csv`) | 4.3 |
| Tab. 1 | calibração de resolução | seção C.2 acima | 2.3 |
| Tab. 2 | baselines | `runs/exp02_final/tabelas.md` | 4.2 |
| Tab. 3–4 | patamares por cena | `runs/exp02_final/tabelas.md` | 4.3 |

### Opcionais

| nº | conteúdo | arquivo |
|---|---|---|
| Fig. 5 | VRAM e PSNR por resolução | `runs/etapa1_final/resolucao_final.png` |
| Fig. 9 | variabilidade entre execuções | `runs/exp02_variance/variancia.png` |
| — | folha de contato por resolução | `runs/etapa1_final/comparacao_resolucao.png` |

Para as figuras de convergência, `justificativa_iteracoes.png` (quatro painéis)
é preferível a `convergencia.png` por conter o painel de custo; se o espaço
apertar, usar só os painéis (b) e (d).
