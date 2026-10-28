#!/usr/bin/env python3
"""Sustained-load check for the unlocked RTX 4060 Ti (165 W board limit).

Runs 8192^3 FP16->FP32-accumulate GEMM back to back for `seconds`, sampling
power/temperature/clocks between iterations, then reports the time series.
"""
import json
import subprocess
import sys
import time

import torch

torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
N = 8192
ITERS = 10


def smi():
    out = subprocess.check_output(
        ["nvidia-smi",
         "--query-gpu=power.draw,temperature.gpu,clocks.current.graphics,"
         "clocks.current.memory,utilization.gpu,pstate",
         "--format=csv,noheader,nounits"],
        text=True, timeout=20,
    ).strip().split(",")
    return [float(x) if i < 4 else x.strip() for i, x in enumerate(out)]


def main():
    a = torch.randn(N, N, device="cuda", dtype=torch.float16)
    b = torch.randn(N, N, device="cuda", dtype=torch.float16)
    for _ in range(3):
        a @ b
    torch.cuda.synchronize()

    samples = []
    t_end = time.time() + SECONDS
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    while time.time() < t_end:
        start.record()
        for _ in range(ITERS):
            a @ b
        end.record()
        end.synchronize()
        ms = start.elapsed_time(end) / ITERS
        power, temp, clk, mclk, util, pstate = smi()
        samples.append({
            "t": round(time.time(), 2),
            "ms": round(ms, 3),
            "tflops": round(2.0 * N ** 3 / (ms / 1e3) / 1e12, 2),
            "power_w": power, "temp_c": temp, "sm_mhz": clk,
            "mem_mhz": mclk, "util": util, "pstate": pstate,
        })

    tf = [s["tflops"] for s in samples]
    pw = [s["power_w"] for s in samples]
    tp = [s["temp_c"] for s in samples]
    cl = [s["sm_mhz"] for s in samples]
    print(f"iterations={len(samples)} over {SECONDS:.0f}s")
    print(f"TFLOPS   median={sorted(tf)[len(tf)//2]:6.2f}  min={min(tf):6.2f}  max={max(tf):6.2f}  last={tf[-1]:6.2f}")
    print(f"power W  median={sorted(pw)[len(pw)//2]:6.1f}  max={max(pw):6.1f}   (limit 165)")
    print(f"temp  C  median={sorted(tp)[len(tp)//2]:6.0f}  max={max(tp):6.0f}")
    print(f"SM  MHz  median={sorted(cl)[len(cl)//2]:6.0f}  max={max(cl):6.0f}")
    print("first 5:", [(s['tflops'], s['power_w'], s['temp_c'], s['sm_mhz']) for s in samples[:5]])
    print("last  5:", [(s['tflops'], s['power_w'], s['temp_c'], s['sm_mhz']) for s in samples[-5:]])
    out = {"seconds": SECONDS, "samples": samples,
           "median_tflops": sorted(tf)[len(tf) // 2],
           "max_power": max(pw), "max_temp": max(tp), "max_clock": max(cl)}
    from pathlib import Path
    p = Path(__file__).resolve().parent / "results" / "stress_unlocked.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
