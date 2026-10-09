# Spec — Pipeline de Grid Search para Instant-NGP em GPU de 6 GB

**Projeto:** TCC — *Treinamento de modelos NeRF baseados em grid: otimização de hiperparâmetros em hardware de baixa especificação*
**Ambiente:** WSL2 (Ubuntu 22.04 LTS), instant-ngp já compilado com bindings Python (`pyngp`), RTX 2060 6 GB.
**Status:** documento de especificação para geração do script definitivo (substitui o protótipo `ngp_grid_search.py`).

---

## 0. Decisões que mudam em relação ao protótipo

O protótipo funciona como prova de conceito, mas tem quatro limitações que o inviabilizam para o experimento final. As decisões abaixo são premissas desta spec.

| # | Protótipo | Decisão | Motivo |
|---|---|---|---|
| D1 | Chama `scripts/run.py` via `subprocess` e extrai PSNR do stdout com regex | Usa `pyngp` diretamente dentro de um processo *worker* | `n_rays_per_batch` não existe no JSON de rede; só é ajustável pela API Python. Regex sobre stdout é frágil e silenciosamente retorna `None`. |
| D2 | Grid = `log2_hashmap_size` × `n_levels` × `n_features_per_level` | Grid = `log2_hashmap_size` (T) × `n_features_per_level` (F) × `n_rays_per_batch` (R) | O Quadro 2 do TCC define T, F e R. `n_levels` não é um dos três parâmetros da metodologia. |
| D3 | Mede só PSNR e SSIM (se aparecerem no log) | Mede PSNR, SSIM, LPIPS, pico de VRAM, tempo de treino e tempo de avaliação | Seção 4.6 do TCC exige as cinco métricas. |
| D4 | Um único processo Python roda todas as combinações | Orquestrador + um subprocesso por combinação | Isolamento de VRAM (medição limpa de pico, sem fragmentação acumulada) e tolerância a OOM: uma combinação que estoura os 6 GB não derruba as outras 53. |

---

## 1. Objetivo do software

Executar de forma automatizada, reprodutível e retomável **54 treinos** (27 combinações × 2 cenas) do Instant-NGP com 5.000 iterações cada, registrando para cada execução as métricas de qualidade visual e de custo computacional necessárias à análise de Fronteira de Pareto, mais **2 execuções de baseline** (configuração padrão, uma por cena).

O software **não** decide nada sobre a análise: ele produz um CSV canônico. A análise de Pareto é um segundo script, que consome esse CSV.

---

## 2. Arquitetura

Três componentes, três arquivos:

```
grid_runner.py    # orquestrador: monta o grid, dispara workers, consolida o CSV
ngp_worker.py     # 1 processo = 1 combinação: treina, avalia, escreve metrics.json
pareto_analysis.py# consome results.csv, gera fronteira e gráficos
```

### 2.1 `grid_runner.py` (orquestrador)

Responsabilidades:
1. Ler a definição do grid e a lista de cenas.
2. Para cada `(cena, T, F, R, seed)`, criar `runs/<exp_id>/<run_tag>/` e gerar o JSON de rede derivado do `base.json`.
3. Disparar `ngp_worker.py` como subprocesso (`subprocess.run`, `cwd` = raiz do instant-ngp), com **timeout** configurável.
4. Ler o `metrics.json` produzido pelo worker; se ausente ou o worker falhou, registrar linha com `status` de erro e seguir.
5. Escrever/appendar `results.csv` com `flush()` a cada linha.
6. Ao final, imprimir sumário: top-5 por PSNR, run de menor VRAM, contagem por `status`.

Não importa `torch` nem `pyngp`. Mantém-se leve de propósito.

### 2.2 `ngp_worker.py` (executor de uma combinação)

Recebe por CLI: `--scene`, `--network`, `--n-steps`, `--n-rays-per-batch`, `--test-transforms`, `--out-dir`, `--seed`, `--test-stride`, `--spp`. Fluxo:

1. Inicia a thread de amostragem de VRAM (§5.1) e mede a **linha de base** de memória antes de tocar no `pyngp`.
2. Instancia o `Testbed`, carrega a cena e o `network.json`.
3. Fixa `n_rays_per_batch` (§4.2) e a semente.
4. Loop de treino até `n_steps`, com `t0 = time.perf_counter()` imediatamente antes e leitura do tempo imediatamente após o último `frame()`.
5. Roda a avaliação no conjunto de teste (§4.3), gravando as imagens renderizadas em `renders/`.
6. Calcula PSNR e SSIM (NumPy/scikit-image) e LPIPS (torch + `lpips`) — **depois** do treino, para não competir por VRAM durante ele. Se a VRAM estiver apertada, o LPIPS roda em CPU (`--lpips-device cpu`, mais lento, porém seguro).
7. Escreve `metrics.json` e encerra. O processo morrendo é o que garante a liberação total da VRAM.

**Regra:** o worker nunca lança exceção não tratada para o orquestrador sem antes gravar um `metrics.json` com `status` e `error`. Falha silenciosa é o cenário que a Seção 4.4 do TCC quis eliminar.

---

## 3. Espaço de busca

```python
GRID = {
    "T": [15, 17, 19],        # encoding.log2_hashmap_size
    "F": [2, 4, 8],           # encoding.n_features_per_level
    "R": [2048, 4096, 8192],  # n_rays_per_batch (API Python, não vai no JSON)
}
SCENES = ["lego", "chair"]
N_STEPS = 5000
SEEDS   = [0]                 # ver §3.2
```

Fixos e explicitamente documentados no `manifest.json`: `n_levels=16`, `base_resolution=16`, `per_level_scale` (herdado do `base.json`), arquitetura das MLPs, otimizador, `loss.otype`.

### 3.1 Baseline
Duas execuções extras por cena com o `base.json` intocado e `n_rays_per_batch` deixado no comportamento padrão do instant-ngp. Marcadas com `is_baseline=true` no CSV. É contra elas que se mede a degradação de PSNR < 2 dB prometida na Seção 5.

### 3.2 Variância entre execuções
Com 5.000 iterações, a variação entre execuções idênticas não é desprezível. **Recomendação:** repetir 3 configurações representativas (a de menor VRAM, a mediana e o baseline) com 3 sementes cada, só na cena Lego. São 6 treinos extras (~15 min) e permitem reportar o desvio-padrão do PSNR — o que blinda a discussão contra a crítica de "diferença de 0,2 dB é ruído ou efeito?".

### 3.3 Ordem de execução
Ordem fixa e determinística (ordenada por cena, depois T, F, R), registrada no manifest. Uma execução de aquecimento descartada antes da primeira medição de tempo, para evitar que o primeiro treino carregue o custo de inicialização de contexto CUDA e de clock baixo da GPU.

---

## 4. Protocolo experimental

### 4.1 Configuração da rede
O JSON de cada run é gerado por *deep copy* do `base.json` com sobrescrita de `encoding.log2_hashmap_size` e `encoding.n_features_per_level`. Caminhos inexistentes devem abortar com erro explícito (o protótipo já faz isso via `validate_grid` — manter).

**Verificar antes de rodar o grid completo:** a saída da grade tem largura `n_levels × F`. Com `F=8` e `n_levels=16` são 128 dimensões alimentando a MLP de densidade. Confirmar que o tiny-cuda-nn aceita `n_features_per_level=8` na sua build (os valores suportados são potências de 2 até 8) e que a MLP `FullyFusedMLP` não cai para `CutlassMLP` silenciosamente — se cair, o tempo de treino muda de patamar e a comparação entre F's fica contaminada. Registrar no log qual implementação foi usada.

### 4.2 Fixação de `n_rays_per_batch` — **ponto crítico**
O instant-ngp ajusta dinamicamente o número de raios por batch para atingir um alvo de *amostras* por batch (`target_batch_size`). Isso significa que atribuir `testbed.nerf.training.n_rays_per_batch = R` uma única vez, antes do loop, **pode ser sobrescrito** já na segunda iteração.

Requisitos:
- Reatribuir `R` a cada iteração, imediatamente antes de `testbed.frame()`, **ou** desabilitar o controlador adaptativo se a sua versão expuser essa opção.
- Registrar em `metrics.json` o valor efetivo de `n_rays_per_batch` ao final do treino e a média amostrada a cada 100 iterações (`n_rays_effective_mean`). Se esse valor divergir de `R`, o experimento inteiro perde validade e o script deve marcar `status="rays_not_pinned"`.
- Registrar também o número de amostras por batch resultante, já que com R fixo ele passa a variar conforme a ocupação da cena. Essa é uma diferença metodológica real entre Lego e Chair e merece uma frase na discussão.

### 4.3 Avaliação no conjunto de teste
- Usar `transforms_test.json` do Synthetic-NeRF, resolução nativa 800×800.
- Antes de renderizar: desligar o treino, ativar `snap_to_pixel_centers`, definir `spp` (padrão 8) e reduzir `render_min_transmittance`. Copiar exatamente o bloco de avaliação do `scripts/run.py` da sua própria cópia do repositório — é o protocolo de referência com o qual os números da literatura são comparáveis.
- **Fundo branco.** O Synthetic-NeRF tem PNGs RGBA e o protocolo canônico compõe sobre branco. Render e referência precisam usar a mesma composição; divergência aqui custa vários dB silenciosamente. Qualquer que seja a escolha, ela precisa constar do TCC e ser idêntica nas 56 execuções.
- `--test-stride N` amostra 1 a cada N vistas de teste (200 no total). Com `N=1` a avaliação pode dominar o tempo total do grid. Sugestão: `N=4` (50 vistas) para o grid, `N=1` para o baseline e para as configurações da fronteira de Pareto, com a diferença registrada por run na coluna `test_views`.

### 4.4 Métricas de qualidade
- **PSNR** — sobre imagens sRGB 8 bits, média das vistas. Calcular por vista e guardar também a mediana e o desvio.
- **SSIM** — `skimage.metrics.structural_similarity` com `channel_axis=-1`, `data_range=255`.
- **LPIPS** — pacote `lpips`, rede **AlexNet** (padrão da literatura NeRF), entradas normalizadas para [-1, 1]. Fixar a versão do pacote no manifest.
- Gravar também `loss_final` (média dos últimos 100 passos, não o valor de um único passo — o protótipo pegava um valor instantâneo, que oscila).

---

## 5. Instrumentação

### 5.1 Pico de VRAM
`torch.cuda.max_memory_allocated()` **não serve**: o instant-ngp aloca pelo seu próprio caminho CUDA e o PyTorch não enxerga nada disso.

Abordagem: thread daemon amostrando NVML (`pynvml`) a cada 50 ms:
- Preferencial: memória do próprio PID via `nvmlDeviceGetComputeRunningProcesses`.
- **Ressalva de WSL:** em WSL2 a consulta por processo frequentemente retorna vazio ou zero. O script deve detectar isso e cair automaticamente para `nvmlDeviceGetMemoryInfo(handle).used` **menos** a linha de base medida antes de inicializar o `pyngp`, com a GPU ociosa.
- Gravar as duas leituras (`vram_peak_process_mb`, `vram_peak_device_mb`, `vram_baseline_mb`) e um campo `vram_method` indicando qual foi usado. Não escolher silenciosamente — a metodologia precisa declarar como o pico foi medido.
- Fechar o navegador e demais consumidores de GPU durante o experimento; o script deve avisar se a linha de base exceder um limiar (ex.: 500 MB).

### 5.2 Tempo
- `t_train_s`: `time.perf_counter()` cercando **apenas** o loop de treino, com sincronização de GPU antes da leitura final.
- `t_eval_s` e `t_setup_s` separados. O tempo reportado no TCC como "custo computacional" deve ser o de treino; misturar avaliação distorce a comparação entre valores de R.
- `steps_per_s` derivado.

### 5.3 Procedência
`manifest.json` por experimento: commit do instant-ngp, versão do driver NVIDIA, nome da GPU, versão de CUDA, versões de Python/numpy/scikit-image/torch/lpips, conteúdo integral do `base.json`, grid, data/hora e ordem de execução. Sem isso o experimento não é reproduzível seis meses depois, na hora de responder à banca.

---

## 6. Contratos de dados

### 6.1 `results.csv` (uma linha por run)

```
run_tag, scene, is_baseline, seed, T, F, R, n_steps,
psnr, psnr_std, ssim, lpips, loss_final,
vram_peak_mb, vram_peak_device_mb, vram_baseline_mb, vram_method,
t_train_s, t_eval_s, steps_per_s,
n_rays_effective_mean, samples_per_batch_mean, test_views, spp,
status, error, timestamp
```

`status` ∈ `{ok, oom, timeout, crash, rays_not_pinned, skipped}`.
Colunas numéricas vazias quando `status != ok` — nunca zero, para não poluir médias.

### 6.2 `metrics.json` (por run)
Mesmos campos, mais o vetor de PSNR por vista e o histórico de loss subamostrado (a cada 50 passos), útil para gerar curvas de convergência por configuração.

### 6.3 Layout em disco
```
runs/<exp_id>/
  manifest.json
  results.csv
  <run_tag>/
    network.json
    stdout.log
    metrics.json
    renders/        # apagáveis via --keep-renders=false
```
`run_tag` = `{scene}_T{T}_F{F}_R{R}_s{seed}` — legível e ordenável, melhor que as iniciais do protótipo (`lhs19_nfpl4`).

---

## 7. Robustez

- **OOM:** capturar a exceção de alocação, gravar `status="oom"` com a VRAM no momento da falha e retornar código 0 (falha esperada, não erro do script). As combinações que estouram os 6 GB **são um resultado do trabalho**, não um problema: elas delimitam a fronteira de viabilidade da RTX 2060.
- **Timeout** por run (padrão: 20 min) com encerramento do processo e `status="timeout"`.
- **`--resume`:** pula runs cujo `metrics.json` existe com `status="ok"`; reexecuta os demais. Melhoria sobre o protótipo, que só verificava a presença de PSNR no log.
- **`--dry-run`:** lista os runs, o tempo estimado total e o espaço em disco previsto sem executar nada.
- **Ctrl+C:** encerra o worker atual e o CSV permanece íntegro (o `flush()` por linha do protótipo já cobre isso — manter).

---

## 8. Análise (`pareto_analysis.py`)

Entrada: `results.csv`. Saída: `pareto.csv` + figuras em PDF/PNG a 300 dpi.

- Objetivos: maximizar PSNR, minimizar `vram_peak_mb`, minimizar `t_train_s`. Conjunto não dominado calculado **por cena**, mais a interseção entre as duas cenas (as configurações que se sustentam nos dois perfis — exatamente o que a Seção 4.5 promete verificar).
- Também a fronteira 2D PSNR × VRAM, que é a figura que vai para o texto.
- Tabela de degradação em relação ao baseline: `ΔPSNR`, `ΔVRAM %`, `Δtempo %`, com destaque para as linhas com `ΔPSNR > -2 dB`.
- Verificação de coerência: apontar configurações em que LPIPS e PSNR discordam de sinal. São os casos interessantes para a discussão sobre ruído de hash, previstos na Seção 2.13.

---

## 9. Riscos conhecidos

| Risco | Impacto | Mitigação |
|---|---|---|
| `n_rays_per_batch` sobrescrito pelo ajuste dinâmico | Uma das três variáveis do TCC não varia de fato | §4.2 — verificação obrigatória com `status="rays_not_pinned"` |
| NVML sem dados por processo em WSL2 | Pico de VRAM não mensurável do modo preferido | §5.1 — fallback por device com linha de base |
| LPIPS carregado durante o treino | OOM induzido pela própria medição | Avaliação após o treino, opção de LPIPS em CPU |
| Composição de alpha divergente entre render e referência | Erro sistemático de vários dB em todas as linhas | §4.3 — teste de sanidade do §10 |
| `F=8` cair para implementação não fundida da MLP | Tempos entre F's deixam de ser comparáveis | §4.1 — registrar a implementação em log |
| Térmico/clock da GPU ao longo de horas | Deriva no tempo de treino | Run de aquecimento, ordem fixa, registrar temperatura no início de cada run |

---

## 10. Critérios de aceitação

O script está pronto quando:

1. `--dry-run` lista 56 runs (54 do grid + 2 baselines) com estimativa de tempo e disco.
2. Uma execução de fumaça com `--n-steps 100 --test-stride 20` sobre 2 combinações termina com `status="ok"`, PSNR não nulo e `metrics.json` completo em ambas.
3. **Teste de sanidade da avaliação:** avaliar uma cena treinada com 5.000 passos e obter PSNR na faixa esperada para o Instant-NGP em Lego (ordem de 30 dB). Um valor perto de 12–15 dB indica erro de fundo/composição, não modelo ruim — foi exatamente o que a Tabela 1 do TCC mostrou com 100 iterações e é o modo de falha mais provável.
4. Uma combinação forçada a OOM (ex.: `T=21, F=8, R=16384`) produz linha com `status="oom"` e o grid continua.
5. Interromper com Ctrl+C e retomar com `--resume` não duplica nem perde linhas.
6. `n_rays_effective_mean` coincide com `R` (tolerância de 1%) em todas as linhas `ok`.