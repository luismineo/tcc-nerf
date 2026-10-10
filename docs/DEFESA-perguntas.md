# Defesa — perguntas prováveis e respostas

Cada resposta traz o número que a sustenta e onde está a evidência. A ideia é
nunca responder "porque é boa prática": responder com o dado.

Fontes: `RELATORIO-fechamento.md` (RF), `RELATORIO-exp02-validacoes.md` (RV),
`ESTADO-exp02.md` (EE), `runs/exp02_final/tabelas.md` (TF).

---

## 1. O argumento em três frases

> Numa GPU de 6 GB, o benchmark padrão da área não exerce pressão de memória, então
> o estudo migrou para cenas reais, calibradas para que o eixo de custo percorra
> a maior parte da placa. Medindo 56 execuções e o ruído do próprio
> treinamento, mostramos que os hiperparâmetros da codificação deslocam o
> consumo em 1,3 a 2,1 GB, em poucos patamares de qualidade distinguível, e que o
> piso de memória vem dos dados de treino, fora do alcance desses
> hiperparâmetros. O resultado é um guia de configuração por orçamento, com a
> incerteza declarada.

---

## 2. Escolhas de desenho

**Por que o Instant-NGP, e não 3D Gaussian Splatting, Zip-NeRF ou Mip-NeRF 360?**
É o método de qualidade competitiva com menor exigência de memória. O 3DGS tem
requisitos de VRAM e armazenamento consideravelmente maiores (Gao et al., 2026,
já citado no artigo); métodos baseados em MLP pura, como o Mip-NeRF 360, levam de
horas a dias por cena. Estudar viabilidade em 6 GB com um método que não cabe no
hardware-alvo não teria o que otimizar. E a pergunta é sobre os hiperparâmetros
da codificação de hash, que só existem nessa família.

**Por que abandonar o Synthetic-NeRF?** No exp01, o pico de VRAM não passou de
2981 MB em 54 execuções, sem nenhuma falha por memória. Não havia restrição a
otimizar. (EE §1)

**Por que Garden e Bonsai?** Repetem o contraste do exp01 (Lego denso / Chair
regular) entre tipos de captura: externa não-limitada, com vegetação e fundo
distante, e interna, mais contida. O contraste se confirmou em qualidade: Bonsai
reconstrói 7,6 dB melhor. Em memória, cuidado: Garden consome ~940 MB a mais
porque suas imagens somam 1,7× mais pixels (2678 contra 1576 MB na VRAM), não
por ser mais complexa — descontadas as imagens, Garden consome *menos* (1641
contra 1800 MB). (TF)

**Por que o fator 2 de resolução?** É a maior resolução viável nas duas cenas.
Na resolução original, só as imagens de treino — que o Instant-NGP mantém na
VRAM a 4 bytes por pixel — somam 10,7 GB em Garden e 6,3 GB em Bonsai, acima dos
6,1 GB da placa. (RF Etapa 4; artigo v2 §2.3)

**A documentação recomenda `aabb_scale` alto para cenas naturais. Por que 4 e 8?**
A documentação recomenda *começar* alto e reduzir até a qualidade ser adequada —
foi o que se fez. O valor inicial, 16, custava 5,6 dB em Garden e 14,5 dB em
Bonsai. O ótimo difere por cena, o que mostra que a calibração precisa ser feita
cena a cena. (EE §4.1)

**Por que 5000 iterações?** Por cena, com dado:
- Garden: o ganho total entre 4000 e 30 000 iterações é 0,24 dB, menor que o
  ruído entre execuções idênticas. Treinar mais não produz diferença mensurável.
- Bonsai: converge mais devagar e fica ~1 dB abaixo do valor a 20 000. Mas
  quatro configurações retreinadas a 20 000 ganharam todas entre 1,00 e
  1,12 dB, sem nenhuma inversão de ordem. A fronteira — que é o que o trabalho
  afirma — não muda. (RF Etapa 2)

Bônus: manter 5000 preserva a comparabilidade com o exp01.

**Qual é a "configuração padrão"?** O `base.json` distribuído com a
implementação: `T` = 19, `F` = 4, `L` = 8. O artigo original recomenda `F` = 2 e
`L` = 16, escolhidos por uma análise de Pareto entre tempo e erro (Müller et al.,
Fig. 5), e deixa `T` para ajustar a cada tarefa (2^14 a 2^24). Até 23/02/2023, o
`base.json` era `T19 F2 L16`; os próprios autores o mudaram para `F4 L8` "para
desempenho e qualidade ligeiramente melhores" (commits `3612ea5` e `298ce96`).
Os dois pontos foram medidos. Adotou-se o atual por ser o que um usuário
executa. (RV §1.1; ARTIGO-v2-propostas §4)

**E o resultado contradiz o artigo original?** Não exatamente — o critério é
outro. Eles otimizaram tempo × erro numa cena sintética e numa GPU de 24 GB, com
número de parâmetros constante. Aqui o custo é memória, em cena real. Sob esse
critério, `T19 F2 L16` fica fora da fronteira em Garden e empata com o padrão
atual em Bonsai, treinando 39 % mais devagar. E os próprios autores trocaram o
padrão depois.

**Por que derivar o `per_level_scale`?** O `base.json` não o define, e a
implementação o calcula a partir do `aabb_scale`, para que o nível mais fino
chegue a 2048 × o tamanho da cena, como os autores especificam para NeRF
(Müller et al., Seção 4). Variar `L` com razão fixa
mudaria ao mesmo tempo o número de níveis e a resolução mais fina, e todo o
efeito seria atribuído a `L`. Fixando o mesmo alvo de resolução da
implementação, `L` = 8 reproduz exatamente o baseline. (EE §4.6)

**Por que desligar o `nerf_compatibility`?** Ele anula o alargamento do passo
de amostragem ao longo do raio, que é o que torna viável percorrer cena
não-limitada. Altera o treino, não só a avaliação — e por isso o PSNR do exp02
não é comparável ao do exp01.

**Por que medir VRAM descontando a ocupação prévia?** A interface do Windows
ocupou entre 254 e 1457 MB da placa, conforme a sessão. O valor absoluto do
dispositivo mede o desktop junto. (PROTOCOLO-medicao.md)

---

## 3. Rigor estatístico — as perguntas mais prováveis

**Cada configuração do grid foi executada uma vez. Como confiar?**
1. O ruído entre execuções idênticas foi **medido**: no máximo 0,244 dB. A
   amplitude de qualidade do grid é 6,7 dB em Garden e 7,0 dB em Bonsai —
   ~27× o ruído. (RV §2)
2. Nenhuma diferença menor que 0,244 dB é usada para ordenar configurações.
3. Pontos suspeitos foram buscados por critério declarado (monotonicidade) e
   reexecutados: os dois encontrados reproduziram o valor original. (RF Etapa 1)
4. Onde havia mais de uma medida, a tabela final usa a média; o padrão tem 5 e
   6 medidas. (RF Etapa 4)
5. Se perguntarem se 0,244 dB é mesmo o teto do ruído: não é garantido. Com
   todas as medições reunidas, uma configuração chegou a 0,34 dB. O limiar foi
   fixado antes e mantido; a sensibilidade foi verificada
   (`runs/exp02_final/sensibilidade_ruido.csv`): sweet spots e guia de Bonsai
   não mudam até 0,35 dB; em Garden, a partir de 0,29 dB o padrão deixa de ser
   um degrau distinto de `T19 F4 L4`.

**Por que repetir com a mesma semente?** Para medir o não-determinismo residual
das operações paralelas em GPU sob controle máximo. Variar a semente somaria a
variação de inicialização — é trabalho futuro, e tornaria o ruído *maior*, não
menor.

**Uma das 24 execuções da validação de ruído (2 cenas × 4 configurações × 3
repetições) convergiu 1,8 dB abaixo. Isso não invalida tudo?** Foi detectada,
analisada e tratada por critério declarado (desvio maior que 3× a mediana das
amplitudes). Nenhuma ocorrência semelhante foi encontrada nas 54 combinações do
grid. O dado bruto está preservado. (RV §2.2–2.3)

**De onde vem a tolerância de −2 dB?** É um critério próprio, fixado no
pré-projeto. Nenhum dos artigos de referência define limiar de degradação
aceitável (conferido em Mildenhall et al., Müller et al. e Gao et al.). É uma
tolerância ampla: na ablação do NeRF, −2,24 dB é o custo de remover a
codificação posicional. E nenhuma conclusão depende dela — ordenação, fronteira,
patamares e sweet spot usam o ruído medido (0,244 dB). Ela só delimita a região
de interesse (20 de 27 configurações em Garden, 15 de 27 em Bonsai).

**Por que o limiar de suspeita é 0,47 dB?** Três vezes a mediana das
amplitudes medidas (0,157 dB). Calculado sobre o conjunto, não por grupo, para
não ser circular.

**Os critérios foram escolhidos depois de ver os dados?** Não. Os critérios das
etapas finais foram registrados em `PLANO-fechamento.md` antes de cada execução
e estão versionados com data. Um caso concreto: na Etapa 3, a linha de base
estava estável e o teste provavelmente funcionaria, mas estava acima do limite
fixado — e não foi executado. (RF Etapa 3)

---

## 4. Resultados

**Qual é o resultado prático?** Um guia por orçamento de memória (TF):
- Garden: três patamares — `T19 F4 L4` (20,72 dB, 4040 MB), padrão (21,01 dB,
  4319 MB), `T19 F4 L16` (21,28 dB, 4845 MB). O padrão pode ser substituído por
  `T19 F2 L8`: −0,15 dB (dentro do ruído), **−268 MB, −16 % de tempo**. Os
  degraus de Garden (+0,29 e +0,26 dB) estão perto do ruído — ver item 5 da
  seção 3.
- Sweet spot (joelho + empate no ruído + mais rápido): Garden `T19 F4 L4`
  (−0,29 dB, −278 MB, −37 % de tempo contra o padrão); Bonsai, o próprio padrão.
- Bonsai: cinco patamares, de 2905 a 5039 MB. O padrão já está na fronteira
  eficiente.

**O que de mais útil um usuário leva do trabalho?**
- Em Garden, abaixo de ~4040 MB não há economia: quatro configurações cabem em
  128 MB de diferença com qualidade de 14,7 a 20,4 dB. Escolher a mais fraca só
  perde qualidade.
- O topo do grid não compensa: em Garden, `T19 F8 L16` supera o patamar anterior
  em 0,19 dB (abaixo do ruído) por +409 MB; em Bonsai, o último patamar custa
  mais memória que todos os anteriores somados.
- Nas duas cenas, **`T` = 15 nunca formou patamar**: reduzir o tamanho da tabela
  de hash foi a pior forma de economizar memória. *(Observação sobre duas cenas,
  não regra geral.)*

**Por que nenhuma configuração estourou a memória? A metodologia não prometia
mapear as inviáveis?** As imagens de treino ocupam 2,7 GB (Garden) e 1,6 GB
(Bonsai) independentemente dos hiperparâmetros; a parte que os hiperparâmetros
controlam varia 1,3 a 2,1 GB. Em qualquer resolução em que o padrão caiba com
folga, todo o grid cabe; na resolução seguinte, nem as imagens cabem. A janela
em que o padrão estoura e uma configuração leve cabe existe, mas tem ~400 MB de
largura — menos que a variação da ocupação do desktop. Ficou como trabalho
futuro, com o motivo documentado. (EE §4.5; RF Etapa 3)

**PSNR, SSIM e LPIPS concordam?** Quase sempre. Em 3 de 54 configurações, PSNR e
LPIPS discordam de sinal em relação ao baseline, todas por diferenças pequenas.
A projeção PSNR × VRAM é o resultado principal pela mesma razão do exp01: a
fronteira tridimensional é pouco legível.

---

## 5. Limitações — assumir antes que perguntem

- Duas cenas, uma máquina, uma semente.
- Cada ponto do grid com n=1 (mitigado: ruído medido, suspeitos reverificados,
  médias onde havia repetição).
- GPU compartilhada com o desktop; ocupação variável entre sessões.
- Bonsai com PSNR absoluto ~1 dB abaixo do valor a 20 000 iterações (ordem
  preservada).
- LPIPS calculado em CPU — afeta só o tempo de avaliação.
- Fronteira de viabilidade não medida.

## 6. Trabalhos futuros

- Fronteira de viabilidade com controle rigoroso da ocupação prévia da GPU e uma
  configuração leve de qualidade aceitável.
- Mais cenas e múltiplas sementes.
- Estratégias que reduzam o custo de memória dos dados de treino, que os
  hiperparâmetros da codificação não alcançam.
