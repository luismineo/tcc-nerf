# Protocolo de medição — exp02

Regras que toda execução do `exp02` segue. Qualquer número citado no artigo deve
ter sido produzido sob elas.

## Dados

| parâmetro | `garden` | `bonsai` |
|---|---|---|
| fator de redução | 2 — 2594×1681 | 2 — 1559×1039 |
| `aabb_scale` | 4 | 8 |
| divisão treino/teste | 161 / 24 | 255 / 37 |
| regra da divisão | `holdout_every=8`, por índice na ordem do JSON | idem |

`aabb_scale` vive no transforms da cena (gravado por `fixar_aabb_scale.py`), não
em flag de linha de comando.

## Treino

- configuração de referência: `vendor/instant-ngp/configs/nerf/base.json`
  intocado (T=19, F=4, L=8);
- `per_level_scale` dos pontos do grid derivado com `N_max = 2048 × aabb_scale`,
  o que faz L=8 reproduzir o valor que o Instant-NGP deriva do `base.json`;
- `training_batch_size` B = 262 144;
- `nerf_compatibility` desligado;
- seed 0.

## Avaliação

- todas as vistas de teste (`--test-stride 1`), `spp=8`;
- fundo preto, `snap_to_pixel_centers`, conversão linear → sRGB antes das
  métricas;
- PSNR, SSIM (skimage, sRGB 8 bits) e LPIPS AlexNet em CPU.

## VRAM

1. **Execução estritamente sequencial.** Nunca dois treinamentos simultâneos —
   cada processo leria como linha de base o que o outro já alocou. Os scripts
   compartilham trava `flock` em `runs/.calib.lock`.
2. **Linha de base amostrada antes de cada execução** (5 leituras), com média e
   desvio gravados por linha.
3. **Medida comparativa: `vram_peak_mb`** (pico menos linha de base).
   `vram_peak_device_mb` inclui a ocupação do Windows, que variou de 254 a
   1457 MB no projeto, e é registrada só como contexto.
4. **Viabilidade não é só ausência de OOM.** Uma execução com `status=ok` é
   classificada como **degradada** se as imagens de treino a 4 B/px excederem o
   pico medido, ou se a vazão cair abaixo de 40 % da mediana de execuções
   comparáveis — sinais de paginação para a RAM do host.

## Ruído de referência

Amplitude máxima observada entre execuções idênticas, sem outliers:
**0,244 dB** (`RELATORIO-exp02-validacoes.md` §2). Diferenças de PSNR menores que
isso não são usadas para ordenar configurações.
