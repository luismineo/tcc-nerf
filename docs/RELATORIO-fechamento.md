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

---

## Etapa 3 — Fronteira de viabilidade: não executada

**Critério do plano:** executar apenas com linha de base abaixo de ~400 MB **e**
oscilação menor que 50 MB em 12 amostras.

**Medição em 2026-10-09 00:27**, GPU ociosa, nenhum aplicativo CUDA:

```
556 552 547 543 543 543 543 543 543 543 543 543   MiB
```

| condição | medido | critério | atende? |
|---|---|---|---|
| nível | ~545 MB | < ~400 MB | **não** |
| oscilação | 13 MB | < 50 MB | sim |

**Decisão: não executar.** O ambiente estava estável, e com essa estabilidade as
margens previstas no fator 1,62 (configuração padrão excedendo em ~125 MB,
configuração leve cabendo com ~278 MB) seriam 10–20× a oscilação — o teste
possivelmente funcionaria. Mas o critério foi fixado antes da medição, e
relaxá-lo depois de ver o valor é exatamente o tipo de decisão que o plano
existe para impedir. Nenhum processo do usuário foi encerrado e nenhuma
configuração do sistema foi alterada.

Pesa também o achado da Etapa 1: a configuração "leve" preparada para o teste
(`T15 F2 L8`) tem qualidade genuinamente baixa, ~14,7 dB em três medições. A
afirmação resultante — "o padrão não treina, a configuração leve treina a
14,7 dB" — seria fraca como demonstração mesmo se o teste desse certo.

**Encaminhamento:** trabalho futuro. Duas condições para retomá-lo com
proveito: linha de base abaixo de ~400 MB e uma configuração leve de qualidade
aceitável (por exemplo `T19 F2 L8` ou `T15 F8 L4`, ambas na fronteira de
`garden` com mais de 20 dB), o que exigiria recalcular o fator intermediário
para a nova janela.

**O que a medição registra, mesmo sem o teste:** a linha de base desta máquina
variou, ao longo do projeto, de 254 a 1457 MB — desta vez 543 MB estáveis. Mais
de 8 % da placa comprometida pelo desktop antes de qualquer experimento, numa
fração que muda de sessão para sessão.

---

## Etapa 4 — Consolidação analítica

**Script:** `scripts/consolidacao_final.py`
**Saídas:** `runs/exp02_final/` — `tabelas.md` (pronto para o artigo),
`guia_{cena}.csv`, `grid_{cena}.csv`, `baselines.csv`,
`pareto_espessura.png/.pdf`

### Duas decisões de método tomadas durante a consolidação

**1. Agregar todas as medições de cada configuração.** A primeira versão
comparava cada ponto do grid (n=1) contra **uma** medida do padrão — e o
"substituto do padrão" em `garden` saiu a −0,23 dB, no limite do limiar de
0,244. Mas o modelo padrão havia sido medido cinco vezes sem outlier em `garden`
(20,889 · 21,135 · 21,054 · 20,965 · 21,031) e seis em `bonsai`, e várias
configurações tinham três ou mais medidas. Cada ponto passou a ser a **média de
todas as medições a 5000 iterações** disponíveis (grid, baselines, variância,
triagem), com `n` e procedência registrados por linha. A execução anômala
`garden/base_json/rep2` fica excluída pelo critério já declarado em
`analise_variancia.py`. O padrão (`base.json`) é tratado como o ponto
`T19 F4 L8`, que é o mesmo modelo desde a correção do `per_level_scale`.

**2. Aplicar também o ruído de VRAM.** A validação de variância mostrou
amplitude de até **122 MB** em `vram_peak_mb` entre execuções idênticas.
Diferenças de VRAM menores que isso não são economia. O guia passou a exigir que
cada degrau seja mensuravelmente melhor (> 0,244 dB) **e** mensuravelmente mais
caro (> 122 MB) que o anterior; o "substituto do padrão" passou a exigir
economia maior que 122 MB.

### Guia por orçamento de VRAM

Construído como escada: cada degrau é a configuração mais barata que seja
mensuravelmente melhor que o anterior. Entre degraus, VRAM adicional não compra
qualidade mensurável.

**`bonsai`** (5000 iterações; valores absolutos ~1 dB abaixo de 20 000, ordem
preservada):

| degrau | config | n | VRAM | PSNR | ganho | custo |
|---|---|---|---|---|---|---|
| 1 | `T17 F2 L8` | 1 | 2905 | 26,50 | — | — |
| 2 | `T19 F2 L8` | 4 | 3131 | 27,69 | +1,18 dB | +226 MB |
| 3 | `T19 F4 L8` (padrão) | 6 | 3376 | 28,62 | +0,93 dB | +245 MB |
| 4 | `T19 F8 L8` | 1 | 3955 | 29,13 | +0,52 dB | +579 MB |
| 5 | `T19 F8 L16` | 1 | 5039 | 29,52 | +0,39 dB | +1084 MB |

**`garden`:**

| degrau | config | n | VRAM | PSNR | ganho | custo |
|---|---|---|---|---|---|---|
| 1 | `T19 F4 L4` | 4 | 4040 | 20,72 | — | — |
| 2 | `T19 F4 L8` (padrão) | 5 | 4319 | 21,01 | +0,29 dB | +278 MB |
| 3 | `T19 F4 L16` | 1 | 4845 | 21,28 | +0,26 dB | +526 MB |

### Achados

**O padrão está na borda eficiente nas duas cenas.** Em `bonsai` ele é um
degrau do guia e nenhuma configuração equivalente é mensuravelmente mais barata.
Em `garden` também é um degrau, mas existe um substituto: **`T19 F2 L8` —
−0,15 dB (dentro do ruído), −268 MB (−6,2 %), −16 % de tempo de treino.**

**Em `garden`, abaixo de ~4040 MB não há economia mensurável.** Quatro
configurações foram removidas do guia por custarem o mesmo que um degrau melhor:
`T15 F2 L8` (14,71 dB), `T15 F4 L4` (15,98), `T19 F2 L4` (17,80) e
`T15 F8 L4` (20,37), todas entre 3907 e 4035 MB. O consumo nessa faixa é
dominado pelas imagens de treino (2677 MB) e pelo custo fixo; escolher a
configuração mais fraca só perde qualidade.

**A "candidata" anterior de `garden` (`T15 F8 L4`) cai.** `T19 F4 L4` custa o
mesmo e rende +0,35 dB, diferença mensurável (confirmada também na validação de
variância). A única vantagem da candidata é o tempo de treino: 73 s contra 92 s.

**O topo do grid não compra qualidade mensurável em `garden`.** A configuração de
maior PSNR (`T19 F8 L16`, 21,47 dB, 5254 MB) não é um degrau: está a +0,19 dB de
`T19 F4 L16`, dentro do ruído, por +409 MB. Em `bonsai` o topo ainda é degrau
(+0,39 dB), mas o último degrau custa 1084 MB — mais que todos os anteriores
somados.

**A alavanca útil é menor que a alavanca bruta.** Medida de ponta a ponta do
grid, a VRAM varia ~1,3 GB em `garden` e ~2,1 GB em `bonsai`. Mas em `garden` a
faixa mensuravelmente útil vai de 4040 a 4845 MB, ~0,8 GB, por 0,56 dB de
ganho. É esse número, e não a amplitude bruta, que o texto deve usar.
