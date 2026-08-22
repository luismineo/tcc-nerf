# Grid Search do Instant-NGP — Fronteira de Pareto em GPU de 6 GB

Pipeline do experimento do TCC: 54 treinos do grid (27 combinações × 2 cenas),
2 baselines e 3 runs de controle, medindo PSNR, SSIM, LPIPS, pico de VRAM e tempo
de treino.

## Estrutura

```
tcc-nerf/
├── README.md
├── scripts/
│   ├── grid_runner.py       orquestrador: monta o grid, dispara workers, consolida o CSV
│   ├── ngp_worker.py        1 processo = 1 combinação: treina, avalia, grava metrics.json
│   └── pareto_analysis.py   consome results.csv, calcula a fronteira e gera as figuras
├── data/nerf_synthetic/     lego/ e chair/ do Synthetic-NeRF
├── docs/
│   ├── SPEC-grid-search-ngp.md
│   └── prototipo-ngp_grid_search.py    protótipo inicial, arquivado
├── patches/                 alterações locais aplicadas ao fork do instant-ngp
├── runs/                    saídas dos experimentos
└── vendor/instant-ngp/      o fork do instant-ngp (repositório git próprio)
```

Nada em `scripts/` escreve dentro de `vendor/`. Os três caminhos são derivados da
localização do próprio script, então os comandos funcionam de qualquer diretório
de trabalho; `--ngp-root`, `--data-root` e `--out-root` sobrescrevem se preciso.

`vendor/instant-ngp` continua sendo um clone git independente, com o upstream
intacto e as alterações locais por cima. Isso mantém possível dar `git pull` no
upstream e reaplicar os patches.

**Os datasets são symlinks.** `data/nerf_synthetic/{lego,chair}` apontam para
`vendor/instant-ngp/data/nerf/downloads/`, porque aqueles diretórios pertencem a
`root` (foram extraídos com `sudo`) e movê-los exigiria senha. Para materializar:

```bash
sudo chown -R "$USER:$USER" vendor/instant-ngp/data/nerf/downloads
rm data/nerf_synthetic/lego data/nerf_synthetic/chair
mv vendor/instant-ngp/data/nerf/downloads/{lego,chair} data/nerf_synthetic/
```

Nenhuma mudança de código é necessária depois disso — o caminho já é o mesmo.

---

## Pré-requisitos

**A build do pyngp precisa corresponder à compute capability da GPU.** Uma build
compilada para `>=86` rodando numa RTX 2060 (cc 75) não falha: ela treina em
silêncio sem gerar nenhuma amostra, o loss fica cravado em zero e o
`while testbed.frame()` do `run.py` do instant-ngp entra em loop infinito. Para
recompilar do zero:

```bash
export PATH=/usr/local/cuda/bin:$PATH
cd vendor/instant-ngp && rm -rf build
cmake . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DTCNN_CUDA_ARCHITECTURES=75 -DNGP_BUILD_WITH_GUI=OFF
cmake --build build -j $(nproc)
```

Confira no log de qualquer execução que **não** aparece
`Insufficient compute capability 75 detected`.

### Alterações locais no instant-ngp

O pipeline depende de dois acréscimos a `src/python_api.cu`, arquivados em
`patches/0001-pyngp-expor-seed-e-contadores.patch`:

| binding | para quê |
|---|---|
| `seed` (leitura/escrita) | sem ele todas as runs usam `seed = 1337` e o worker grava `seed_supported: false` |
| `nerf.training.n_rays_per_batch` (leitura) | proxy de ocupação da cena |
| `nerf.training.measured_batch_size` (leitura) | confere que o controlador convergiu para B |

São `def_readwrite`/`def_property_readonly` puros, sem mudança de comportamento.
Se recriar o `vendor/` a partir do upstream, reaplique com:

```bash
git -C vendor/instant-ngp apply ../../patches/0001-pyngp-expor-seed-e-contadores.patch
```

Dependências Python:

```bash
pip3 install scikit-image pynvml matplotlib
pip3 install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip3 install lpips
```

`torch` e `torchvision` **precisam vir do mesmo índice**. Misturar o torch
cpu-only com o torchvision do PyPI produz
`RuntimeError: operator torchvision::nms does not exist` na hora de carregar o LPIPS.

### Antes de rodar o grid completo

Feche navegador e demais consumidores de GPU no lado Windows. Em WSL2 a única
medição de VRAM disponível é a do device inteiro (veja "Limitações"), então
qualquer processo do Windows entra na conta. Verifique:

```bash
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

Com a área de trabalho ativa esta máquina apresentou **2,9 a 3,7 GB já ocupados**
dos 6 GB. O worker avisa quando a linha de base passa de 500 MB.

---

## Comandos

### 1. Teste de fumaça

Duas combinações, 600 passos, poucas vistas — cerca de 1 minuto. Deve terminar
com `status=ok` e PSNR não nulo nas duas.

```bash
python3 scripts/grid_runner.py --exp-id smoke01 --scenes lego \
  --n-steps 600 --test-stride 40 --baseline-test-stride 40 \
  --no-warmup --only lego_baseline lego_T15_F2_L16
```

`--baseline-test-stride` é essencial aqui: o padrão do baseline é 1, isto é, as
200 vistas de teste, o que num teste de fumaça domina o tempo inteiro.

### 2. Baseline

`base.json` intocado, avaliação sobre todas as 200 vistas.

```bash
python3 scripts/grid_runner.py --exp-id baseline01 --n-steps 5000 \
  --no-batch-sweep --only baseline
```

### 3. Grid completo

```bash
python3 scripts/grid_runner.py --exp-id exp01 --dry-run     # confere as 59 runs e a estimativa
python3 scripts/grid_runner.py --exp-id exp01               # executa (~4h20m com a GPU livre)
python3 scripts/grid_runner.py --exp-id exp01 --resume      # retoma após Ctrl+C
```

`--only SUBSTRING...` reexecuta configurações específicas; combinado com
`--resume` é como refazer um punhado de runs sem tocar no resto.

`--resume` pula apenas runs com `status=ok`; `oom`, `timeout` e `crash` são
reexecutados. O CSV recebe `flush()` e `fsync()` por linha, então um Ctrl+C nunca
deixa linha pela metade.

### 4. Análise

```bash
python3 scripts/pareto_analysis.py --csv runs/exp01/results.csv
```

Gera em `runs/exp01/analise/`: `pareto.csv`, `degradacao_baseline.csv`,
`varredura_batch.csv`, `incoerencias_lpips_psnr.csv`, `resumo.json` e as figuras
em PNG e PDF a 300 dpi. As runs de `kind="batch_sweep"` ficam **fora** das
fronteiras e vão para a própria tabela, para não misturar efeito de orçamento de
treino com efeito de capacidade do modelo.

---

## Estimativa de tempo: ~4h20m

Medida com runs completas de 5000 passos pelo próprio `ngp_worker.py`, cena Lego,
50 vistas de avaliação, B = 262 144, **GPU ociosa**:

| configuração | `n_encoding_params` | steps/s | t_train | pico de VRAM | PSNR |
|---|---|---|---|---|---|
| T=15 F=2 L=4 (menor) | 204 800 | 56,1 | 89 s | 1 732 MB | 26,23 dB |
| T=19 F=4 L=8 (baseline) | 11 681 792 | 33,8 | 148 s | 2 200 MB | 33,08 dB |
| T=19 F=8 L=16 (maior) | 48 784 960 | 16,4 | 304 s | 2 887 MB | **33,60 dB** |

Memória de cálculo, por run: `setup (15 s) + 5000 / steps_per_s + n_vistas × 1,3 s`.

```
18 runs L= 4  ×  2m49s  =  0h51m
18 runs L= 8  ×  3m47s  =  1h08m
18 runs L=16  ×  6m24s  =  1h55m
 2 baselines (200 vistas) =  0h13m
 3 runs da varredura de B =  0h10m
                    TOTAL ≈  4h17m
```

`python3 scripts/grid_runner.py --exp-id exp01 --dry-run` imprime essa conta. A tabela
`STEPS_PER_S_BY_L` no topo do `grid_runner.py` guarda as constantes; recalibre com:

```bash
python3 scripts/grid_runner.py --exp-id calib --scenes lego --n-steps 5000 \
  --no-warmup --no-batch-sweep \
  --only lego_baseline lego_T15_F2_L4 lego_T19_F8_L16
```

### O efeito de ter a GPU ocupada

Vale registrar porque é grande. As mesmas medições, com um jogo aberto no Windows:

| | GPU ociosa | GPU compartilhada |
|---|---|---|
| linha de base do device | 712–1 236 MB | 3 802 MB |
| baseline, steps/s | **33,8** | 2,96 |
| baseline, t_train | 148 s | 1 687 s |
| total estimado do grid | **4h17m** | 28h |

Onze vezes mais lento. Também explica a leitura maior de VRAM que a pressão de
memória produz. Rode o grid com a máquina livre.

Mesmo ociosa, a linha de base variou entre 903 e 1 236 MB nas três runs — essa é
a faixa de ruído sobre `vram_peak_mb`, já que em WSL2 o pico só pode ser medido
como diferença contra o device inteiro. Diferenças de VRAM menores que ~300 MB
entre configurações devem ser tratadas com cautela.

---

## Espaço de busca

```python
GRID = {
    "T": [15, 17, 19],   # encoding.log2_hashmap_size
    "F": [2, 4, 8],      # encoding.n_features_per_level
    "L": [4, 8, 16],     # encoding.n_levels
}
FIXED_BATCH_SIZE = 262144   # training_batch_size, variável controlada
```

São **59 runs**: 54 do grid (27 combinações × 2 cenas) + 2 baselines + 3 da
varredura de batch (§ "O que aconteceu com o batch").

Os três eixos são exatamente os hiperparâmetros do HashGrid da Tabela 1 do paper
do Instant-NGP, todos vivendo no JSON de rede. O baseline (`base.json` intocado:
T=19, F=4, L=8) **coincide com um ponto do grid**, então a tabela de degradação
compara exatamente a mesma coisa, e as duas execuções da mesma configuração dão
de graça uma checagem de reprodutibilidade.

### Por que o terceiro eixo é `n_levels` e não o tamanho do batch

A spec original definia o terceiro eixo como `n_rays_per_batch` (R). Isso não é
implementável nesta build e, mais importante, não era o parâmetro certo.

**Por que R saiu.** `n_rays_per_batch` não existe na API Python. O campo real é
`rays_per_batch`, membro de `Testbed::NerfCounters`
([testbed.h:477](vendor/instant-ngp/include/neural-graphics-primitives/testbed.h#L477)), e o
instant-ngp o **recalcula ao fim de todo passo**
([testbed_nerf.cu:2698](vendor/instant-ngp/src/testbed_nerf.cu#L2698)) para que o número de
*amostras* persiga `training_batch_size`. R não é um parâmetro que se escolhe: é
uma saída do controlador. Além disso ele quase não move a VRAM — no workspace de
treino ([testbed_nerf.cu:3009-3040](vendor/instant-ngp/src/testbed_nerf.cu#L3009-L3040)) os termos
proporcionais a `rays_per_batch` somam ~44 bytes por raio, menos de 400 KB com
R = 8192.

**Por que `training_batch_size` (B) também não serve como eixo.** B é o candidato
óbvio a substituto — é o que de fato move a VRAM de treino. Mas B **não é
hiperparâmetro do modelo**. Com o número de iterações fixo em 5000, reduzir B não
produz um modelo menor: produz o *mesmo* modelo treinado com menos amostras no
total. A queda de qualidade seria efeito de orçamento de treino, não de
capacidade — e numa Fronteira de Pareto isso beira a tautologia ("gastei menos
memória e treinei menos, logo ficou pior").

Isso é mensurável. Mesma rede (T=15, F=2), 5000 passos:

| B | PSNR | modelo |
|---|---|---|
| 65 536 | 28,72 dB | idêntico |
| 131 072 | 29,19 dB | idêntico |

Os +0,47 dB não vêm de capacidade nenhuma. Para tornar a comparação justa seria
preciso igualar o total de amostras — aumentando as iterações quando B cai — e aí
o eixo de tempo explode e a pergunta vira outra.

**Por que L serve.** T, F e L mudam a *capacidade* do modelo sob o mesmo orçamento
de treino. O artefato treinado é genuinamente menor e o resultado transfere para
qualquer GPU, não só para esta. E L é um eixo de VRAM legítimo: medido nesta
build, `n_encoding_params` em T=19/F=8 vai de 12,6 M (L=4) a 48,8 M (L=16), ou
seja de ~240 MB a ~930 MB de encoding.

> **Para aprofundar no TCC:** o ponto defensável é que uma busca de
> hiperparâmetros sobre *capacidade do modelo* e uma busca sobre *orçamento de
> treino* respondem perguntas diferentes. A primeira produz um modelo que cabe em
> 6 GB; a segunda produz um procedimento de treino que cabe em 6 GB. O título do
> trabalho — otimização de hiperparâmetros — pede a primeira. A varredura de B
> abaixo existe para que a segunda apareça declarada e controlada, em vez de
> ignorada.

### A armadilha do `per_level_scale`

O `base.json` **não** define `per_level_scale`, então o tiny-cuda-nn assume b = 2
(confirmado no log: `Nmin=16 b=2 F=4 T=2^19 L=8`). A resolução mais fina da grade
é `N_min × b^(L-1)`, então com b fixo:

| L | b = 2 fixo | resolução mais fina |
|---|---|---|
| 4 | 2 | 16 × 2³ = **128** |
| 8 | 2 | 16 × 2⁷ = **2048** |
| 16 | 2 | 16 × 2¹⁵ = **524 288** |

Variar L com b fixo mudaria o número de níveis **e** a resolução máxima em quatro
ordens de grandeza ao mesmo tempo, e todo o efeito seria atribuído a L. L=4 seria
um espantalho grosseiro; L=16 teria dez níveis redundantes batendo no teto da
tabela hash.

O runner deriva b para segurar a resolução mais fina constante:

```
b = (N_max / N_min) ** (1 / (L - 1))     N_min = 16, N_max = 2048
```

| L | `per_level_scale` | resolução mais fina | `n_encoding_params` (T=19, F=4) |
|---|---|---|---|
| 4 | 5,0397 | 2048 | 6 307 840 |
| 8 | **2,0000** | 2048 | 11 681 792 |
| 16 | 1,3819 | 2048 | 24 392 480 |

L = 8 devolve b = 2,0000 **exatamente**, ou seja, reproduz o `base.json` sem
ajuste nenhum — o baseline continua intocado. E 1,3819 para L = 16 está dentro da
faixa de 1,26 a 2 que o paper usa. A regra e o motivo ficam gravados no
`manifest.json`, em `per_level_scale_rule`.

### O que aconteceu com o batch

B fica fixo em 262 144 (o default do instant-ngp), registrado como variável
controlada. Para que o efeito dele não fique ignorado, o runner acrescenta **3
runs** varrendo B ∈ {65 536, 131 072, 262 144} numa configuração mediana de Lego
(T=17, F=4, L=8), marcadas com `kind="batch_sweep"` no CSV. Desligue com
`--no-batch-sweep`.

Fixos e registrados no `manifest.json`: `base_resolution`, arquitetura das MLPs,
otimizador e `loss.otype`, herdados do `base.json`.

### Contadores do controlador adaptativo

Com B fixo, quem flutua é o número de raios. Medido em Lego, B = 262 144:

| passo | `rays_per_batch` | `measured_batch_size` | amostras/raio |
|---|---|---|---|
| 1 | 1 024 | 1 273 155 | 1243,3 |
| 20 | 3 328 | 265 022 | 79,6 |
| 120 | 17 664 | 264 224 | 15,0 |

`measured_batch_size` converge para B, como esperado, enquanto `rays_per_batch`
sobe conforme a grade de densidade poda o espaço vazio. **Quantos raios uma cena
precisa para preencher o mesmo orçamento de amostras é um proxy de ocupação** — é
aí que Lego e Chair diferem, e é a frase que a §4.2 da spec queria na discussão.
Gravados por run em `n_rays_effective_mean`, `samples_per_batch_mean` e
`samples_per_ray_mean` (média de amostras a cada 100 iterações, descartando os
100 primeiros passos enquanto o controlador ainda converge).

---

## Protocolo de avaliação

Copiado do bloco `--test_transforms` de
[vendor/instant-ngp/scripts/run.py:257-317](vendor/instant-ngp/scripts/run.py#L257-L317), para que os números sejam
comparáveis aos da literatura:

| Item | Valor |
|---|---|
| `background_color` | `[0, 0, 0, 1]` — **preto** |
| `snap_to_pixel_centers` | `True` |
| `spp` | 8 |
| `render_min_transmittance` | `1e-4` |
| `render_with_lens_distortion` | `True` |
| Resolução | 800×800 nativa |

Render e referência passam pelo mesmo `testbed.render()` e pelo mesmo
`background_color`, então a composição de alpha é simétrica por construção — não
há o erro sistemático de vários dB que a composição divergente causaria.

Métricas: **PSNR** sobre sRGB, média das vistas (com mediana e desvio);
**SSIM** via `skimage.metrics.structural_similarity` com `channel_axis=-1` e
`data_range=255`; **LPIPS** com AlexNet, entradas em [-1, 1]. A coluna `ssim_ngp`
traz o SSIM próprio do instant-ngp ([common.py:175](vendor/instant-ngp/scripts/common.py#L175)), que
é luminância + blur de 5 taps e **não** é comparável ao do skimage — está ali só
para conferência com o `run.py`.

---

## Instrumentação de VRAM

`torch.cuda.max_memory_allocated()` não serve: o instant-ngp aloca pelo próprio
caminho CUDA e o PyTorch não enxerga nada disso.

O worker roda uma thread daemon amostrando NVML a cada 50 ms. Nesta máquina foi
verificado que `nvmlDeviceGetComputeRunningProcesses` **lista o PID** (nas versões
v1, v2 e v3) mas devolve `usedGpuMemory = None` sempre — comportamento de WSL2.
Um script que testasse apenas `if procs:` concluiria que funcionou e gravaria
zero. O worker testa `is None` explicitamente e cai para o consumo do device
menos a linha de base, gravando `vram_method="device_minus_baseline"`.

São gravadas quatro leituras: `vram_peak_mb` (a atribuível), `vram_peak_device_mb`,
`vram_baseline_mb` e `vram_device_min_mb`. A última existe para tornar
**detectável** a contaminação por processos do Windows: se `vram_device_min_mb`
cair bem abaixo de `vram_baseline_mb`, a linha de base estava inflada e aquela
linha do CSV merece desconfiança.

---

## Saídas

```
runs/<exp_id>/
  manifest.json      procedência: commit, driver, GPU, versões, base.json íntegro, ordem de execução
  results.csv        uma linha por run
  <run_tag>/
    network.json     JSON de rede desta combinação
    stdout.log       saída do worker e do instant-ngp
    metrics.json     tudo do CSV mais PSNR por vista e histórico de loss
    renders/         apagáveis com --no-keep-renders
```

`run_tag` = `{cena}_T{T}_F{F}_B{B}_s{seed}`, ou `{cena}_baseline_s{seed}`.

`status` ∈ `{ok, oom, timeout, crash, interrupted}`. Colunas de qualidade ficam
**vazias** quando `status != ok` — nunca zero, para não poluir médias. As colunas
de VRAM e de tempo são preenchidas mesmo em falha: num OOM, elas são justamente
o dado interessante.

---

## Limitações e ressalvas

1. **A GPU precisa estar ociosa.** Em WSL2 a única medição de VRAM disponível é a
   do device inteiro, então tudo que o Windows estiver usando entra na conta — e
   o tempo de treino sofre ainda mais. Numa primeira rodada de calibração com a
   máquina em uso, a mesma configuração variou de 6,6 a 56 steps/s e o custo de
   avaliação por vista variou 10×; a linha de base do device passou de 712 MB
   (ociosa) para 3 802 MB. **Nenhum número de tempo ou de VRAM colhido com a GPU
   compartilhada tem valor para o TCC.** O worker avisa quando a linha de base
   passa de 500 MB; trate esse aviso como bloqueante.

2. **`--nerf-compatibility` está LIGADO nas 59 runs.** Reproduz o protocolo do
   NeRF original: `color_space = SRGB`, `cone_angle_constant = 0` e
   `random_bg_color = False` ([run.py:164-188](vendor/instant-ngp/scripts/run.py#L164-L188)). Dois
   desses três mexem no **treino**, não só na avaliação, então os PSNRs não são
   comparáveis a execuções com a opção desligada. O valor fica gravado no
   manifest e na coluna `nerf_compatibility` do CSV. Se mudar, mude para todas.

3. **`loss_final` usa uma janela de 800 passos por padrão** (`--loss-window`). O
   instant-ngp só recalcula o loss quando `training_step % 16 == 0`
   ([testbed.cu:4625](vendor/instant-ngp/src/testbed.cu#L4625)), avaliado *antes* do incremento — o
   worker lê logo após `train()`, então as amostras caem em `training_step`
   1, 17, 33… e são sempre valores crus e distintos, nunca repetidos. Com 800
   passos são ~50 amostras; `loss_final_n_samples` registra quantas entraram.

4. **A semente e os contadores dependem de dois patches em `src/python_api.cu`**
   feitos para este trabalho (`seed`, `n_rays_per_batch`, `measured_batch_size`).
   São `def_readwrite`/`def_property_readonly` puros, sem mudança de
   comportamento, mas o repositório fica divergente do upstream. Registre isso na
   seção de reprodutibilidade do TCC; `manifest.json` grava `git_dirty: true`.

5. **`matplotlib` não estava na lista de dependências permitidas da spec**, mas a
   §8 pede figuras em PDF/PNG a 300 dpi. O `pareto_analysis.py` gera todos os CSVs
   sem ele e só pula as figuras, avisando, se não estiver instalado.

6. **A deriva térmica ao longo de horas não foi caracterizada.** A run de
   aquecimento descartada cobre o clock inicial baixo; a deriva ao longo de uma
   execução de muitas horas não foi medida. Se o tempo de treino for entrar como
   resultado, vale registrar a temperatura por run e checar correlação com a
   ordem de execução.

7. **`n_levels` do `base.json` é 8, não 16** como a §3 da spec afirmava. O valor
   real foi mantido (o baseline precisa ser o `base.json` intocado) e L = 8
   aparece no grid, então nada se perde — mas o texto do TCC precisa corrigir a
   afirmação.

8. **Uma semente só (`SEEDS = [0]`).** A §3.2 da spec sugeria repetir 3
   configurações com 3 sementes para reportar desvio-padrão entre execuções. Com
   o binding de `seed` disponível isso agora é executável, mas não está no grid
   padrão. O baseline coincidir com um ponto do grid dá uma comparação de duas
   execuções da mesma configuração, o que é um começo, mas não substitui o
   estudo de variância.
