# GPT-OSS-20B on one NVIDIA H100

This experiment measures `openai/gpt-oss-20b` served by vLLM on a single
NVIDIA H100 80GB HBM3. NVIDIA AIPerf drives sequential concurrency sweeps and
records output throughput, request throughput, time to first token (TTFT),
inter-token latency (ITL), and KV-cache pressure.

**[Read the polished report with interactive charts](https://ravivooda.github.io/thoughts/gpt-oss-20b-h100-aiperf.html)**

## Directory contents

- `results/summary.json` — curated, machine-readable results used by the report
- `scripts/run_sweep.py` — configurable sequential vLLM/AIPerf sweep runner
- `README.md` — methodology, result summary, and reproduction instructions

Large AIPerf artifact directories and server logs are intentionally not checked
in. A new run writes them to `artifacts/` and `logs/`, respectively.

## Test platform

| Component | Configuration |
| --- | --- |
| GPU | 1× NVIDIA H100 80GB HBM3; approximately 79.18 GiB usable |
| Model | `openai/gpt-oss-20b` |
| Weight format | GPT-OSS MXFP4 mixture-of-experts weights |
| Model memory observed | Approximately 13.03 GiB |
| Inference engine | vLLM 0.26.0 |
| Load generator | NVIDIA AIPerf 0.12.0 |
| API | Streaming `/v1/chat/completions` |
| Tensor parallelism | 1 |
| KV dtype | `auto` |

## Experiment matrix

| Experiment | ISL / OSL | Max model length | KV policy | Concurrency |
| --- | ---: | ---: | --- | ---: |
| Short-context baseline | 256 / 128 | 4,096 | `gpu-memory-utilization=0.92`, ~56.5 GiB KV | 100–6,400 |
| Short-context high-memory | 256 / 128 | 4,096 | `gpu-memory-utilization=0.98` | 100–6,400 |
| Short-context half KV | 256 / 128 | 4,096 | Exact 28.26 GiB | 100–6,400 |
| Large-context stress | 2,048 / 512 | 16,384 | `gpu-memory-utilization=0.95`, ~57–61 GiB KV | 50–1,600 |
| Large-context half KV | 2,048 / 512 | 16,384 | Exact 28.26 GiB | 50–1,600 |
| Fixed maximum attempt | 256 / 128 | 4,096 | Exact 62.05 GiB | Startup OOM |

The two stress sweeps used 180-second profiles, a 30-second warmup, and a
request budget of `max(concurrency × 20, 5000)`.

## Main results

- The baseline short-context run peaked at **9,354 output tokens/s** at
  concurrency 800.
- The auto-KV large-context run peaked at **8,153 output tokens/s** at
  concurrency 800.
- A balanced large-context range was concurrency **200–400**. Moving from 200
  to 400 added only 3.4% aggregate output throughput while average TTFT
  increased from 2.59 to 4.82 seconds.
- Auto-sized KV reached 100% use at concurrency 1,600.
- Exact 28.26 GiB KV reached 85.5% use at concurrency 400 and 100% at
  concurrency 800.
- Cutting KV approximately in half increased average TTFT at concurrency 800
  from 9.96 to 18.35 seconds even though aggregate output throughput remained
  similar.

## Terminology

The experiment matches AIPerf client concurrency to vLLM's
`--max-num-seqs`. They are related, but neither is a conventional fixed tensor
batch:

- **AIPerf concurrency** is the number of in-flight client requests, including
  requests waiting for service.
- **`max-num-seqs`** is the scheduler's upper limit on sequences processed in
  an iteration.
- **Resident sequences** have KV state present and are actively scheduled.
- **Waiting requests** have been accepted but are not currently resident.

The report's caller fair-share estimate is:

```text
aggregate output tokens per second / configured concurrency
```

This is useful for capacity intuition, but is not a direct measurement of each
caller's streaming speed. Under queueing, waiting callers receive no tokens
while resident callers stream faster.

## Reproduce

Use an environment containing vLLM 0.26.0 and NVIDIA AIPerf 0.12.0. The runner
discovers `vllm` and `aiperf` from `PATH`; explicit paths can be supplied with
`--vllm-bin` and `--aiperf-bin`.

Auto-sized KV stress sweep:

```bash
python scripts/run_sweep.py \
  --batches 50,100,200,400,800,1600 \
  --max-model-len 16384 \
  --input-tokens 2048 \
  --output-tokens 512 \
  --gpu-memory-utilization 0.95 \
  --benchmark-duration 180 \
  --warmup-duration 30 \
  --output-name stress-auto-kv.json
```

Controlled half-KV sweep:

```bash
python scripts/run_sweep.py \
  --batches 50,100,200,400,800,1600 \
  --max-model-len 16384 \
  --input-tokens 2048 \
  --output-tokens 512 \
  --kv-cache-memory-bytes 30343943946 \
  --benchmark-duration 180 \
  --warmup-duration 30 \
  --output-name stress-half-kv.json
```

Each concurrency point starts a fresh vLLM process. The next point begins only
after AIPerf finishes and the previous server has stopped.

## Interpretation

KV cache is a capacity resource, not a direct token-generation accelerator.
With less KV, vLLM admits fewer resident sequences and queues the rest. If the
remaining resident set can still saturate the GPU, server-wide tokens per
second can stay flat while TTFT and queue depth deteriorate.

For production sizing, evaluate latency-constrained goodput, TTFT
distributions, queue depth, and KV utilization alongside aggregate throughput.
