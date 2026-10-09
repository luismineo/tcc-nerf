# Tabelas finais — exp02

Ruído de referência: **0.244 dB** (maior amplitude entre execuções idênticas, `RELATORIO-exp02-validacoes.md` §2). VRAM = pico do processo descontada a linha de base (`vram_peak_mb`). `bonsai` a 5000 iterações: valores absolutos ~1 dB abaixo de 20 000, ordenação preservada (`RELATORIO-fechamento.md`, Etapa 2).

Cada configuração é a **média de todas as medições a 5000 iterações** disponíveis (grid, baselines, validação de variância e reexecuções da triagem); `n` varia de 1 a 6. A execução anômala `garden/base_json/rep2` está excluída pelo critério declarado em `analise_variancia.py`. O padrão (`base.json`) é tratado como o ponto `T19 F4 L8`, que é o mesmo modelo.

## bonsai

Fronteira 2D (PSNR × VRAM): **10** de 27 configurações. Não dominadas de forma mensurável (nenhuma outra tão barata e > 0.244 dB melhor): **11**.

### Guia por orçamento de VRAM

Cada degrau é a configuração mais barata **mensuravelmente melhor** (> 0.244 dB) que o anterior, e **mensuravelmente mais cara** (> 122 MB, o ruído de VRAM). Entre degraus, VRAM adicional não compra qualidade mensurável.

| degrau | config | n | VRAM (MB) | PSNR | SSIM | LPIPS | treino (s) | ganho | custo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `T17 F2 L8` | 1 | 2905 | 26.50 | 0.783 | 0.314 | 87 | — | — |
| 2 | `T19 F2 L8` | 4 | 3131 | 27.69 | 0.837 | 0.248 | 126 | +1.18 dB | +226 MB |
| 3 | `T19 F4 L8` | 6 | 3376 | 28.62 | 0.865 | 0.218 | 150 | +0.93 dB | +245 MB |
| 4 | `T19 F8 L8` | 1 | 3955 | 29.13 | 0.878 | 0.202 | 195 | +0.52 dB | +579 MB |
| 5 | `T19 F8 L16` | 1 | 5039 | 29.52 | 0.890 | 0.189 | 371 | +0.39 dB | +1084 MB |

### Configuração padrão e seu substituto

Padrão (`base.json`, T19 F4 L8, média de n=6): **28.62 dB, 3376 MB, 150 s** de treino.

Nenhuma configuração é ao mesmo tempo equivalente em PSNR (≥ padrão − 0.244 dB) e mensuravelmente mais barata (> 122 MB a menos). **O padrão já está na borda eficiente desta cena.**

Maior PSNR do grid: `T19 F8 L16` — 29.52 dB, 5039 MB, 371 s.

## garden

Fronteira 2D (PSNR × VRAM): **12** de 27 configurações. Não dominadas de forma mensurável (nenhuma outra tão barata e > 0.244 dB melhor): **19**.

### Guia por orçamento de VRAM

Cada degrau é a configuração mais barata **mensuravelmente melhor** (> 0.244 dB) que o anterior, e **mensuravelmente mais cara** (> 122 MB, o ruído de VRAM). Entre degraus, VRAM adicional não compra qualidade mensurável.

| degrau | config | n | VRAM (MB) | PSNR | SSIM | LPIPS | treino (s) | ganho | custo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `T19 F4 L4` | 4 | 4040 | 20.72 | 0.450 | 0.621 | 92 | — | — |
| 2 | `T19 F4 L8` | 5 | 4319 | 21.01 | 0.495 | 0.558 | 146 | +0.29 dB | +278 MB |
| 3 | `T19 F4 L16` | 1 | 4845 | 21.28 | 0.526 | 0.528 | 267 | +0.26 dB | +526 MB |

Removidos por custarem o mesmo que um degrau melhor (diferença de VRAM ≤ 122 MB): `T15 F2 L8` (14.71 dB, 3907 MB), `T15 F4 L4` (15.98 dB, 3919 MB), `T19 F2 L4` (17.80 dB, 3931 MB), `T15 F8 L4` (20.37 dB, 4035 MB). Abaixo de ~4040 MB não há economia mensurável: a partir de 3907 MB o consumo é dominado pelas imagens de treino e escolher a configuração mais fraca só perde qualidade.

### Configuração padrão e seu substituto

Padrão (`base.json`, T19 F4 L8, média de n=5): **21.01 dB, 4319 MB, 146 s** de treino.

Mais barata estatisticamente equivalente ou melhor (PSNR ≥ padrão − 0.244 dB): **`T19 F2 L8`** — 20.86 dB (-0.15 dB, dentro do ruído), 4051 MB (**-268 MB**, -6.2 %), treino 123 s (-16 %).

Maior PSNR do grid: `T19 F8 L16` — 21.47 dB, 5254 MB, 319 s.

## Baselines (configuração padrão, `base.json`)

| cena | n | PSNR | amplitude | SSIM | LPIPS | VRAM (MB) | treino (s) |
|---|---|---|---|---|---|---|---|
| bonsai | 6 | 28.62 | 0.20 | 0.865 | 0.218 | 3376 | 150 |
| garden | 5 | 21.01 | 0.25 | 0.495 | 0.558 | 4319 | 146 |
