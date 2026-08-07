#!/usr/bin/env python3
"""Run sequential vLLM + NVIDIA AIPerf concurrency sweeps."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def parse_batches(value: str) -> list[int]:
    try:
        batches = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError("batches must be comma-separated integers") from error
    if not batches or any(batch < 1 for batch in batches):
        raise argparse.ArgumentTypeError("at least one positive batch is required")
    return batches


def resolve_executable(explicit: str | None, name: str) -> str:
    candidate = explicit or shutil.which(name)
    if not candidate:
        raise FileNotFoundError(
            f"Could not find {name!r}. Pass --{name}-bin or activate its environment."
        )
    return str(Path(candidate).expanduser().resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--batches", type=parse_batches, default=parse_batches("50,100,200,400,800,1600"))
    parser.add_argument("--max-model-len", type=int, default=16_384)
    parser.add_argument("--input-tokens", type=int, default=2_048)
    parser.add_argument("--output-tokens", type=int, default=512)
    parser.add_argument("--benchmark-duration", type=int, default=180)
    parser.add_argument("--warmup-duration", type=int, default=30)
    parser.add_argument("--warmup-request-count", type=int, default=32)
    parser.add_argument("--request-count-mult", type=int, default=20)
    parser.add_argument("--request-count-floor", type=int, default=5_000)
    parser.add_argument("--ready-timeout", type=int, default=900)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.95)
    parser.add_argument(
        "--kv-cache-memory-bytes",
        type=int,
        help="Exact KV cache allocation. When set, it replaces auto KV sizing.",
    )
    parser.add_argument("--vllm-bin", default=os.environ.get("VLLM_BIN"))
    parser.add_argument("--aiperf-bin", default=os.environ.get("AIPERF_BIN"))
    parser.add_argument(
        "--output-name",
        help="Result filename under results/. Defaults to a timestamped name.",
    )
    return parser


def health_ok(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}/v1/models", timeout=5
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def stop_process_group(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=10)


def start_vllm(
    args: argparse.Namespace,
    vllm_bin: str,
    batch: int,
    logs_dir: Path,
) -> tuple[subprocess.Popen[str] | None, TextIO | None, Path]:
    log_path = logs_dir / f"vllm_bs{batch}_{utc_timestamp()}.log"
    command = [
        vllm_bin,
        "serve",
        args.model,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--max-num-seqs",
        str(batch),
        "--max-model-len",
        str(args.max_model_len),
        "--disable-uvicorn-access-log",
    ]
    if args.kv_cache_memory_bytes is not None:
        command.extend(
            ["--kv-cache-memory-bytes", str(args.kv_cache_memory_bytes)]
        )
    else:
        command.extend(
            ["--gpu-memory-utilization", str(args.gpu_memory_utilization)]
        )

    log(f"Starting vLLM at concurrency {batch}")
    output = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    deadline = time.time() + args.ready_timeout
    while time.time() < deadline:
        if process.poll() is not None:
            output.close()
            log(f"vLLM exited during startup; see {log_path}")
            return None, None, log_path
        if health_ok(args.host, args.port):
            log(f"vLLM ready at concurrency {batch}")
            return process, output, log_path
        time.sleep(5)

    stop_process_group(process)
    output.close()
    log(f"vLLM readiness timed out; see {log_path}")
    return None, None, log_path


def stop_vllm(process: subprocess.Popen[str] | None, output: TextIO | None) -> None:
    stop_process_group(process)
    if output is not None and not output.closed:
        output.close()
    time.sleep(3)


def metric_avg(data: dict[str, object], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        average = value.get("avg")
        if isinstance(average, (int, float)):
            return float(average)
    return None


def parse_vllm_log(path: Path) -> dict[str, float | int | str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    result: dict[str, float | int | str] = {}
    patterns = {
        "available_kv_cache_gib": r"Available KV cache memory: ([\d.]+) GiB",
        "kv_cache_tokens": r"GPU KV cache size: ([\d,]+) tokens",
        "max_context_concurrency": (
            r"Maximum concurrency for [\d,]+ tokens per request: ([\d.]+)x"
        ),
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).replace(",", "")
            result[key] = float(raw) if "." in raw else int(raw)

    usages = [
        float(value)
        for value in re.findall(r"GPU KV cache usage: ([\d.]+)%", text)
    ]
    waiters = [
        int(value)
        for value in re.findall(r"Waiting: (\d+) reqs", text)
    ]
    if usages:
        result["max_kv_cache_usage_pct"] = max(usages)
    if waiters:
        result["max_waiting_requests"] = max(waiters)
    return result


def run_aiperf(
    args: argparse.Namespace,
    aiperf_bin: str,
    batch: int,
    artifacts_dir: Path,
) -> dict[str, object]:
    artifact_dir = artifacts_dir / f"bs{batch}_{utc_timestamp()}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    request_count = max(
        batch * args.request_count_mult,
        args.request_count_floor,
    )
    command = [
        aiperf_bin,
        "profile",
        "--model",
        args.model,
        "--tokenizer",
        args.model,
        "--url",
        f"{args.host}:{args.port}",
        "--endpoint-type",
        "chat",
        "--endpoint",
        "/v1/chat/completions",
        "--streaming",
        "--concurrency",
        str(batch),
        "--benchmark-duration",
        str(args.benchmark_duration),
        "--request-count",
        str(request_count),
        "--isl",
        str(args.input_tokens),
        "--isl-stddev",
        "0",
        "--osl",
        str(args.output_tokens),
        "--osl-stddev",
        "0",
        "--extra-inputs",
        "ignore_eos:true",
        "--extra-inputs",
        f"min_tokens:{args.output_tokens}",
        "--artifact-dir",
        str(artifact_dir),
        "--warmup-request-count",
        str(args.warmup_request_count),
        "--warmup-duration",
        str(args.warmup_duration),
    ]
    output_path = artifact_dir / "aiperf_stdout.log"
    log(f"Running AIPerf at concurrency {batch}, request budget {request_count}")
    with output_path.open("w", encoding="utf-8") as output:
        completed = subprocess.run(
            command,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": f"AIPerf exited {completed.returncode}",
            "stdout_log": str(output_path),
            "artifact_dir": str(artifact_dir),
        }

    profile_path = artifact_dir / "profile_export_aiperf.json"
    if not profile_path.exists():
        return {
            "ok": False,
            "error": "profile_export_aiperf.json missing",
            "stdout_log": str(output_path),
            "artifact_dir": str(artifact_dir),
        }

    data = json.loads(profile_path.read_text(encoding="utf-8"))
    output_tps = metric_avg(data, "output_token_throughput")
    return {
        "ok": True,
        "output_token_throughput_tok_s": output_tps,
        "input_token_throughput_tok_s": metric_avg(
            data, "input_token_throughput"
        ),
        "total_token_throughput_tok_s": metric_avg(
            data, "total_token_throughput"
        ),
        "request_throughput_req_s": metric_avg(data, "request_throughput"),
        "ttft_ms_avg": metric_avg(data, "time_to_first_token"),
        "itl_ms_avg": metric_avg(data, "inter_token_latency"),
        "aiperf_output_token_throughput_per_user_tok_s": metric_avg(
            data, "output_token_throughput_per_user"
        ),
        "request_count": metric_avg(data, "request_count"),
        "actual_benchmark_duration_s": metric_avg(data, "benchmark_duration"),
        "caller_fair_share_tok_s": output_tps / batch if output_tps else None,
        "configured_request_count": request_count,
        "profile_json": str(profile_path),
        "stdout_log": str(output_path),
        "artifact_dir": str(artifact_dir),
    }


def main() -> int:
    args = build_parser().parse_args()
    vllm_bin = resolve_executable(args.vllm_bin, "vllm")
    aiperf_bin = resolve_executable(args.aiperf_bin, "aiperf")

    logs_dir = EXPERIMENT_ROOT / "logs"
    artifacts_dir = EXPERIMENT_ROOT / "artifacts"
    results_dir = EXPERIMENT_ROOT / "results"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    result_name = args.output_name or f"sweep_{utc_timestamp()}.json"
    if not result_name.endswith(".json"):
        result_name += ".json"
    output_path = results_dir / Path(result_name).name

    summary: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "max_model_len": args.max_model_len,
        "gpu_memory_utilization": (
            None
            if args.kv_cache_memory_bytes is not None
            else args.gpu_memory_utilization
        ),
        "kv_cache_memory_bytes": args.kv_cache_memory_bytes,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "benchmark_duration_s": args.benchmark_duration,
        "warmup_duration_s": args.warmup_duration,
        "batches": args.batches,
        "caller_fair_share_formula": (
            "output_token_throughput_tok_s / concurrency"
        ),
        "runs": [],
    }
    runs: list[dict[str, object]] = []
    summary["runs"] = runs

    for batch in args.batches:
        process: subprocess.Popen[str] | None = None
        log_output: TextIO | None = None
        run: dict[str, object] = {
            "max_num_seqs": batch,
            "concurrency": batch,
            "status": "pending",
        }
        try:
            process, log_output, vllm_log = start_vllm(
                args, vllm_bin, batch, logs_dir
            )
            run["vllm_log"] = str(vllm_log)
            if process is None:
                run["status"] = "server_failed"
                run.update(parse_vllm_log(vllm_log))
                runs.append(run)
                break

            metrics = run_aiperf(args, aiperf_bin, batch, artifacts_dir)
            run.update(metrics)
            run.update(parse_vllm_log(vllm_log))
            run["status"] = "ok" if metrics["ok"] else "aiperf_failed"
            runs.append(run)
            log(
                f"concurrency={batch}: "
                f"output={metrics.get('output_token_throughput_tok_s')} tok/s, "
                f"fair_share={metrics.get('caller_fair_share_tok_s')} tok/s"
            )
            if not metrics["ok"]:
                break
        except Exception as error:  # noqa: BLE001
            run["status"] = "error"
            run["error"] = repr(error)
            if run not in runs:
                runs.append(run)
            log(f"Error at concurrency {batch}: {error!r}")
            break
        finally:
            stop_vllm(process, log_output)

        summary["updated_at"] = datetime.now(timezone.utc).isoformat()
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"Final results: {output_path}")
    return 0 if any(run.get("status") == "ok" for run in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
