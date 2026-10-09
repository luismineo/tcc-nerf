# Plano de fechamento do trabalho

**Status:** executado em 2026-10-08/09. Resultados e decisões de cada etapa em
`RELATORIO-fechamento.md`.

| etapa | decisão |
|---|---|
| 0 | estado congelado, tag `exp02-pre-fechamento` |
| 1 | 2 suspeitos, ambos confirmados — nenhum ponto substituído |
| 2 | ordem preservada — Etapa 2b dispensada |
| 3 | não executada — linha de base (~545 MB) acima do critério |
| 4 | guia por orçamento e fronteira com espessura em `runs/exp02_final/` |
| 5 | texto proposto em `ARTIGO-v2-propostas.md` |
| 6 | `DEFESA-perguntas.md` |

O texto abaixo é o plano como foi aprovado, sem alterações posteriores.

Princípio que organiza o plano: cada etapa tem um **critério de decisão fixado
antes de rodar**, para que o resultado não possa ser interpretado depois na
direção que convém. É a mesma lógica que expôs os oito defeitos encontrados até
aqui (ver `ESTADO-exp02.md`), e é o argumento metodológico central a usar na
defesa.

Documentos de apoio: `ESTADO-exp02.md`, `RELATORIO-exp02-validacoes.md`,
`REVISAO-artigo-v1.md`.

---

## Etapa 0 — Congelar o estado atual

**Sem GPU · ~10 min**

Commit de tudo que existe (scripts, CSVs, relatórios), com tag
`exp02-pre-fechamento`. Registrar no repositório o protocolo de linha de base:
cinco amostras antes de cada execução, média e desvio gravados, `vram_peak_mb`
como medida comparativa.

**Argumento que sustenta:** reprodutibilidade — qualquer número do texto aponta
para um commit e um CSV.

---

## Etapa 1 — Triagem de pontos suspeitos no grid

**Sem GPU para a triagem · até ~30 min de GPU para confirmar**

Com 4 % de falha de convergência observada (1 em 24 execuções na validação de
variância), cerca de 2 dos 54 pontos do grid podem estar contaminados.

**Critério de suspeita — monotonicidade.** Aumentar `T`, `F` ou `L`, mantendo os
outros dois fixos, não deveria *reduzir* o PSNR em mais de **0,47 dB** (3× a
mediana das amplitudes medidas). Toda violação vira suspeita.

**Decisão:** cada suspeito é reexecutado 2 vezes.

- Reexecuções concordam entre si e discordam do grid → o ponto do grid é
  substituído pela média das reexecuções. O valor original permanece no CSV e a
  substituição é declarada.
- Reexecuções concordam com o grid → o ponto fica.

**Argumento que sustenta:** *"o grid tem n=1, mas pontos anômalos foram
identificados por critério declarado e reverificados"* — resposta direta à
objeção mais provável da banca.

Vem antes da Etapa 2 porque um suspeito pode estar entre as configurações do
teste de ordenação.

---

## Etapa 2 — Teste de ordenação do `bonsai` a 20 000 iterações

**GPU · ~1h15 · 4 execuções**

A pergunta não é "20 000 iterações dão mais PSNR" — isso já foi medido (+1,6 dB
entre ~4000 e 30 000). É **"o truncamento em 5000 distorceu a fronteira?"**

Configurações, cobrindo a faixa de capacidade:

| papel | configuração |
|---|---|
| leve | `T17 F2 L8` |
| candidata | `T19 F2 L8` |
| `base_json` | `T19 F4 L8` |
| pesada | `T19 F8 L16` |

**Critério fixado antes de rodar.** A ordem é considerada **preservada** se:

1. nenhum par separado por mais que o ruído (0,244 dB) a 5000 iterações inverter
   de sinal a 20 000; **e**
2. a distância de PSNR entre a leve e a pesada não crescer mais que 0,5 dB
   (2× o ruído) — crescimento maior indicaria que configurações de alta
   capacidade estavam sendo penalizadas pelo truncamento.

Caso contrário, a ordem é considerada **alterada**.

**Decisão:**

- **Preservada** → o grid do `bonsai` permanece válido; o truncamento entra como
  limitação declarada, com os ~1,6 dB quantificados. Segue para a Etapa 3.
- **Alterada** → **Etapa 2b**: refazer só o grid do `bonsai` a 20 000 iterações
  (~4,9 h).

`garden` não precisa do teste: o ganho total entre 5000 e 30 000 iterações ali
(0,239 dB) já é menor que o ruído medido (0,244 dB).

**Argumento que sustenta:** número de iterações escolhido por cena, com dois
fundamentos independentes — a curva medida e o cronograma do otimizador
(`decay_start: 20000` no `base.json`, início do decaimento da taxa de
aprendizado).

---

## Etapa 3 — Fronteira de viabilidade

**Opcional · GPU · ~15 min · condicionada ao ambiente**

Só roda se a linha de base estiver **abaixo de ~400 MB e estável** (oscilação
menor que 50 MB em 12 amostras). Uma única tentativa, no fator 1,62 já preparado,
sem ajustar a resolução até produzir o resultado desejado. Sem janela, vai para
trabalho futuro.

Uma execução que termine com `status=ok` mas com paginação para a RAM do host
(imagens a 4 B/px acima do pico medido, ou vazão abaixo de 40 % da mediana) é
classificada como **inviável**.

**Argumento que sustenta:**

- se rodar e funcionar, a demonstração *"o padrão não treina nesta resolução; a
  configuração X treina a Y dB"*;
- se não rodar, o próprio bloqueio é dado — mais de 10 % da placa comprometida
  pelo desktop, de forma imprevisível.

---

## Etapa 4 — Consolidação analítica

**Sem GPU · ~1 h**

1. **Fronteira de Pareto com espessura.** Refazer a figura principal com banda
   de ±0,244 dB. Pontos dentro da banda um do outro deixam de ser ordenados.
2. **Tabela-guia por orçamento de VRAM** — o entregável que o resumo do artigo
   promete: *"com até X MB livres, use Y; ganho de subir para Z: +W dB,
   mensurável ou não"*. Uma tabela por cena.
3. **Tabelas finais** de baseline, grid e variância, com procedência por linha.

**Argumento que sustenta:** o objetivo declarado no resumo — *"um guia prático
de configuração"* — entregue literalmente.

---

## Etapa 5 — Revisão do artigo

**Sem GPU · em conjunto**

Aplicar o `REVISAO-artigo-v1.md` (Tabela 1, `base.json` vs artigo original,
ordem `aabb_scale` → resolução, terminologia de "fator", placeholders) e o
enquadramento novo:

| de | para |
|---|---|
| "viabilizar o que não cabia" | "quanto os hiperparâmetros liberam, o que é real e o que é ruído, e onde está o teto" |
| mapa de viabilidade como contribuição | trabalho futuro, ou demonstração pontual se a Etapa 3 rodar |
| "5000 iterações validadas" | validado em `garden`; `bonsai` conforme resultado da Etapa 2 |
| "erros constantes por falta de memória" | pressão de memória e margem |

Escrever a Seção 4 (resultados), a Seção 5 (conclusão) e uma subseção explícita
de **limitações**.

---

## Etapa 6 — Preparação da defesa

**Sem GPU**

Documento com as perguntas previsíveis e respostas apoiadas em dado.

| pergunta provável | resposta |
|---|---|
| Por que Instant-NGP e não 3DGS ou Zip-NeRF? | menor VRAM entre métodos de qualidade competitiva; os alternativos são mais pesados e não caberiam no hardware-alvo |
| Por que abandonar o Synthetic-NeRF? | teto de 2981 MB em 54 execuções, zero OOM: não havia pressão de memória a otimizar |
| O grid tem n=1. Como confiar nele? | ruído medido (±0,25 dB) é ~25× menor que a amplitude do grid (6–7 dB); pontos suspeitos reverificados por critério declarado |
| Por que não há mapa de viabilidade? | o piso é o dado, não o modelo: as imagens de treino custam 1,6–2,7 GB e não respondem a `T`/`F`/`L` |
| Qual é o baseline "padrão"? | `base.json` (`T19 F4 L8`), não o do artigo original (`T19 F2 L16`); os dois foram medidos |
| Por que esse número de iterações? | curva medida por cena + cronograma do otimizador |

**Limitações a assumir de frente, antes que perguntem:** duas cenas, uma
máquina, uma seed, ambiente WSL compartilhado com o desktop, LPIPS calculado em
CPU, `n=1` por ponto do grid.

---

## Custo estimado

| cenário | GPU total |
|---|---|
| mínimo — ordem preservada, sem suspeitos, Etapa 3 bloqueada | **~1h30** |
| provável — alguns suspeitos, Etapa 3 bloqueada | **~2 h** |
| máximo — ordem alterada, Etapa 2b executada | **~7 h** |

**Ordem de execução:** 0 → 1 → 2 → (2b) → 3 → 4 → 5 → 6.

As Etapas 1 e 2 são as únicas com risco de mudar conclusões. Depois delas, o que
resta é análise e escrita.
