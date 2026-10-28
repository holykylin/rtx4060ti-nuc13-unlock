#!/usr/bin/env python3
"""FP16/BF16 -> FP32-accumulate GEMM benchmark for the Ada tensor-unlock A/B test.

Protocol matches the published unlock reports (8192^3, fp32 accumulation forced via
allow_fp16_reduced_precision_reduction=False) plus a 4096^2 point and an FP32 control.
Run once at stock and once after the UEFI unlock; compare medians only.
"""
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import torch

# The tensor issue path the unlock doubles is FP16/BF16 multiply with FP32 accumulate.
torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False
torch.backends.cuda.matmul.allow_tf32 = False


def smi(fields):
    try:
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
            text=True, timeout=20,
        ).strip()
        return out
    except Exception as exc:  # noqa: BLE001
        return f"nvidia-smi failed: {exc}"


def bench(dtype, N, iters):
    dev = torch.device("cuda:0")
    a = torch.randn(N, N, device=dev, dtype=dtype)
    b = torch.randn(N, N, device=dev, dtype=dtype)
    for _ in range(3):
        a @ b
    torch.cuda.synchronize()
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    samples = []
    for _ in range(iters):
        start.record()
        a @ b
        end.record()
        end.synchronize()
        samples.append(start.elapsed_time(end))
    samples.sort()
    median_ms = samples[len(samples) // 2]
    flops = 2.0 * (N ** 3)
    del a, b
    torch.cuda.empty_cache()
    return {
        "median_ms": round(median_ms, 4),
        "tflops": round(flops / (median_ms / 1e3) / 1e12, 3),
        "min_ms": round(samples[0], 4),
        "max_ms": round(samples[-1], 4),
        "samples": len(samples),
    }


def correctness():
    """fp16 matmul with fp32 accumulate vs a float64 CPU reference, small N."""
    torch.manual_seed(7)
    N = 512
    a = torch.randn(N, N, dtype=torch.float16, device="cuda")
    b = torch.randn(N, N, dtype=torch.float16, device="cuda")
    got = (a @ b).float().cpu()
    ref = (a.cpu().double() @ b.cpu().double()).float()
    rel = (got - ref).abs().max().item() / ref.abs().max().item()
    return {"n": N, "max_rel_err": float(rel), "ok": bool(rel < 5e-3)}


def main():
    result = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": platform.node(),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": torch.cuda.get_device_name(0),
        "sm": torch.cuda.get_device_capability(0),
        "sms": torch.cuda.get_device_properties(0).multi_processor_count,
        "smi_before": smi("driver_version,vbios_version,pci.bus_id,pci.device_id,"
                          "pci.sub_device_id,memory.total,power.limit,temperature.gpu,"
                          "clocks.current.graphics,power.draw,utilization.gpu"),
        "correctness": correctness(),
        "modes": {},
    }
    for label, dtype, N, iters in [
        ("fp32_control_4096", torch.float32, 4096, 10),
        ("fp16_fp32acc_4096", torch.float16, 4096, 10),
        ("fp16_fp32acc_8192", torch.float16, 8192, 10),
        ("bf16_fp32acc_4096", torch.bfloat16, 4096, 10),
        ("bf16_fp32acc_8192", torch.bfloat16, 8192, 10),
    ]:
        result["modes"][label] = bench(dtype, N, iters)
        m = result["modes"][label]
        print(f"{label:22s} {m['median_ms']:9.3f} ms  {m['tflops']:8.2f} TFLOPS", flush=True)
    result["smi_after"] = smi("temperature.gpu,clocks.current.graphics,power.draw,"
                              "clocks.max.graphics,power.max_limit")
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps({k: v for k, v in result.items() if k != "modes"}, indent=1))
    return result


if __name__ == "__main__":
    res = main()
    tag = sys.argv[1] if len(sys.argv) > 1 else "run"
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    path = out / f"bench_{tag}.json"
    path.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {path}")
