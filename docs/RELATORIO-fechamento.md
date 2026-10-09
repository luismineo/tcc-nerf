# Relatório de fechamento — execução do plano

Registro da execução de `PLANO-fechamento.md`, etapa por etapa. Os critérios de
decisão foram fixados no plano **antes** de cada execução; aqui ficam os
resultados e a decisão tomada.

---

## Etapa 0 — Congelamento

Commit `350a860`, tag `exp02-pre-fechamento`. Protocolo de medição registrado em
`PROTOCOLO-medicao.md`.

Ao inspecionar a árvore, 16 CSVs apareciam como alterados sem alteração de
conteúdo: o módulo `csv` do Python grava CRLF e o commit anterior havia sido
feito do lado Windows, que normalizou para LF. Adicionado `.gitattributes` com
`eol=lf` para encerrar a oscilação. Três arquivos `Zone.Identifier` com o
caractere privado U+F03A no lugar de `:` haviam sido versionados e foram
removidos; o padrão do `.gitignore` foi ampliado para cobri-los.

---

## Etapa 1 — Triagem de pontos suspeitos

**Script:** `scripts/triagem_monotonicidade.py`, `scripts/reverificar.py`
**Saídas:** `runs/exp02_triagem/`

### Triagem

Critério: aumentar `T`, `F` ou `L` com os outros fixos não deveria reduzir o
PSNR em mais de 0,47 dB. Das 54 configurações, **3 violações, 2 pontos
suspeitos**, ambos em `garden`:

| eixo | de → para | PSNR de | PSNR para | queda |
|---|---|---|---|---|
| L | `T15 F2 L4` → `T15 F2 L8` | 16,216 | 14,805 | 1,411 dB |
| F | `T19 F4 L4` → `T19 F8 L4` | 20,677 | 19,271 | 1,405 dB |
| T | `T17 F8 L4` → `T19 F8 L4` | 20,181 | 19,271 | 0,909 dB |

O número de suspeitos coincide com o esperado pela taxa de falha observada na
validação de variância (1 em 24, ou ~2 em 54).

### Reverificação

Cada suspeito reexecutado 2 vezes, mesmo protocolo e seed.

| ponto | grid | reexecuções | amplitude | Δ média vs grid | decisão |
|---|---|---|---|---|---|
| `garden T15 F2 L8` | 14,805 | 14,543 · 14,774 | 0,231 | −0,146 dB | **manter** |
| `garden T19 F8 L4` | 19,272 | 19,497 · 19,344 | 0,153 | +0,149 dB | **manter** |

As reexecuções concordam entre si e com o grid dentro do ruído de referência.
**Nenhum ponto foi substituído.** `grid_corrigido.csv` é idêntico ao original em
PSNR, acrescido da coluna de procedência.

### Interpretação

As duas não-monotonicidades são **comportamento reprodutível do modelo**, não
falha de convergência. Em dois regimes, mais capacidade rende menos a 5000
iterações:

- **`T=15` com mais níveis.** Uma tabela de 2¹⁵ entradas com 8 níveis, todos
  saturando a tabela nos níveis finos, produz mais colisões que com 4 níveis.
- **`L=4` com `F=8`.** Com apenas 4 níveis, o `per_level_scale` derivado é 8,0 —
  resoluções 16, 128, 1024 e 8192, saltos grandes entre níveis. Dobrar as
  features nesse arranjo piora em vez de melhorar, e o efeito se repete ao
  aumentar `T`.

São hipóteses compatíveis com o mecanismo do hash grid, não verificadas
diretamente. O dado sólido é a reprodutibilidade: três medidas independentes de
cada ponto, todas dentro de 0,23 dB.

### Consequências

1. **O grid do `exp02` não tem falha de convergência detectável** por este
   critério. A falha observada na validação de variância (`base_json` rep2)
   ocorreu numa execução avulsa, não no grid.
2. **Limitação do critério:** ele só detecta falhas que quebram a
   monotonicidade. Uma falha num ponto cujos vizinhos também tenham PSNR baixo
   passaria despercebida.
3. **A configuração "leve" do teste de viabilidade (`T15 F2 L8`) tem qualidade
   genuinamente baixa** — ~14,7 dB, confirmada três vezes. Se a Etapa 3 vier a
   rodar, a demonstração "o padrão não cabe, a leve cabe" seria feita contra uma
   configuração de qualidade ruim, o que enfraquece o argumento.

---

## Etapa 2 — Teste de ordenação do `bonsai` a 20 000 iterações

**Script:** `scripts/teste_ordenacao.py`
**Saídas:** `runs/exp02_ordenacao/` (`ordenacao.csv`, `ordenacao.png`,
`veredito.txt`)

Quatro configurações cobrindo a faixa de capacidade, uma execução cada a 20 000
iterações. Referência a 5000: média de 3 repetições onde disponível
(`exp02_variance`), valor do grid nas demais.

| config | T F L | PSNR 5000 | origem | PSNR 20 000 | ganho | VRAM 20k |
|---|---|---|---|---|---|---|
| leve | 17 2 8 | 26,503 | grid n=1 | 27,503 | +1,000 | 3069,9 |
| candidata | 19 2 8 | 27,682 | média n=3 | 28,803 | +1,122 | 3180,6 |
| `base_json` | 19 4 8 | 28,611 | média n=3 | 29,681 | +1,069 | 3442,6 |
| pesada | 19 8 16 | 29,522 | grid n=1 | 30,530 | +1,008 | 5054,6 |

### Veredito: **ORDEM PRESERVADA**

| critério | resultado | limite |
|---|---|---|
| inversões entre pares separados por mais que o ruído | **0** | 0 |
| crescimento da distância leve → pesada | **+0,008 dB** (3,019 → 3,027) | 0,5 dB |

Os ganhos variam entre si apenas 0,12 dB (1,000 a 1,122), abaixo do ruído de
referência. **O truncamento em 5000 iterações é um deslocamento uniforme de
~1,05 dB, não uma distorção.** Configurações de alta capacidade não foram
penalizadas: a pesada ganhou o mesmo que a leve.

**Decisão:** o grid do `bonsai` a 5000 iterações permanece válido. Etapa 2b
dispensada. O truncamento entra como limitação declarada: valores absolutos de
PSNR do `bonsai` subestimados em ~1 dB em relação a 20 000 iterações (e ~1,6 dB
em relação a 30 000), ordenação e fronteira preservadas.

### Observação sobre VRAM

O pico de VRAM a 20 000 iterações ficou entre +16 e +165 MB acima do medido a
5000, dentro da faixa de variação observada entre execuções idênticas (até
122 MB). Confirma que execuções curtas capturam o pico de alocação, premissa já
validada anteriormente.

### Argumento para o texto

O número de iterações deixa de ser uma escolha a defender e passa a ser uma
escolha **testada**: a 5000 iterações, `garden` está a menos que o ruído do seu
valor final, e `bonsai` está ~1 dB abaixo, mas com a ordenação entre
configurações — que é o que uma Fronteira de Pareto afirma — intacta.
