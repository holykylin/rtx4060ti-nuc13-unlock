#!/usr/bin/env python3
"""检测 RTX 4060 Ti 当前是否处于「tensor 发射率解锁」状态。

原理：解锁改变的只有 FP16/BF16 -> FP32 累加的 tensor 吞吐（本机实测 37 -> 73
TFLOPS @4096²），其它维度（FP32、显存、频率标称值）都不变，所以用一次很短的
矩阵乘就能稳定区分两态。这是唯一能从 Windows 用户态读到的判据——SS0/SS1/PLM
是 GPU 内部寄存器，没有驱动接口暴露。

退出码：0 = 已解锁，1 = 未解锁（原厂），2 = 无法判定（后台有 GPU 负载等）。

用法：
    check-unlock.cmd                 # 双击或命令行运行
    python check_unlock.py --json    # 机器可读输出
"""
import argparse
import json
import subprocess
import sys
from statistics import median

# 本机 2026-10-28 实测（8192³，FP16 输入 / FP32 累加，中位值）
STOCK_TFLOPS = 45.8
UNLOCKED_TFLOPS = 73.5
CUT_TFLOPS = 58.0        # 两态中点，两侧各有 ~12 TFLOPS 余量
FP32_HEALTHY = 9.0       # FP32 对照低于此值说明 GPU 被别的进程占着
N = 8192


def smi(fields):
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def gpu_busy():
    util = smi("utilization.gpu").strip()
    apps = smi("name").strip()
    try:
        util_v = int(float(util))
    except ValueError:
        util_v = -1
    return util_v, apps


def bench(dtype, iters, torch_mod, n=N):
    torch = torch_mod
    dev = torch.device("cuda:0")
    a = torch.randn(n, n, device=dev, dtype=dtype)
    b = torch.randn(n, n, device=dev, dtype=dtype)
    for _ in range(4):
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
    del a, b
    torch.cuda.empty_cache()
    ms = median(samples)
    return 2.0 * (n ** 3) / (ms / 1e3) / 1e12, ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=12, help="FP16 计时次数（默认 12，12 次约 0.3 秒）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--nopause", action="store_true", help="兼容 cmd 包装器，无作用")
    args = ap.parse_args()

    util_v, _ = gpu_busy()
    before = smi(
        "name,driver_version,vbios_version,pci.bus_id,power.limit,"
        "temperature.gpu,power.draw,clocks.current.graphics"
    )

    try:
        import torch
    except ImportError:
        print("找不到 torch。请用 ComfyUI 的 venv 运行：")
        print(r'  E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI (1)\ComfyUI\.venv\Scripts\python.exe check_unlock.py')
        return 2

    torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False
    if not torch.cuda.is_available():
        print("CUDA 不可用（驱动或显卡异常）")
        return 2

    fp16_tf, fp16_ms = bench(torch.float16, args.iters, torch)
    fp32_tf, fp32_ms = bench(torch.float32, 10, torch, n=4096)

    if fp32_tf < FP32_HEALTHY:
        verdict, code = "无法判定：GPU 正被别的程序占用（关掉生成/渲染任务再跑）", 2
    elif fp16_tf >= CUT_TFLOPS:
        verdict, code = "已解锁 ✅", 0
    elif fp16_tf <= CUT_TFLOPS - 6.0:
        verdict, code = "未解锁（原厂状态）", 1
    else:
        verdict, code = "无法判定：数值落在两态之间，可能有后台负载，请重跑", 2

    result = {
        "verdict": verdict,
        "exit_code": code,
        "fp16_fp32acc_tflops": round(fp16_tf, 2),
        "fp16_median_ms": round(fp16_ms, 3),
        "fp32_control_tflops": round(fp32_tf, 2),
        "fp32_median_ms": round(fp32_ms, 3),
        "n": N,
        "fp32_n": 4096,
        "iters": args.iters,
        "gpu_before": before,
        "util_before_pct": util_v,
        "reference": {"stock": STOCK_TFLOPS, "unlocked": UNLOCKED_TFLOPS, "cut": CUT_TFLOPS},
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code

    parts = [p.strip() for p in before.split(",")]
    gpu = parts[0] if len(parts) > 0 else "?"
    drv = parts[1] if len(parts) > 1 else "?"
    vbios = parts[2] if len(parts) > 2 else "?"
    bus = parts[3] if len(parts) > 3 else "?"
    plimit = parts[4] if len(parts) > 4 else "?"
    temp = parts[5] if len(parts) > 5 else "?"
    power = parts[6] if len(parts) > 6 else "?"

    bar = "=" * 56
    print(bar)
    print("        RTX 4060 Ti 解锁状态检测")
    print(bar)
    print(f"GPU              : {gpu}")
    print(f"驱动 / VBIOS     : {drv} / {vbios}")
    print(f"PCI 位置         : {bus}")
    print(f"功耗上限         : {plimit} W   当前温度 {temp} C / {power} W")
    print(f"检测前 GPU 利用率: {util_v}%")
    print()
    print(f"FP16 -> FP32 累加 {N}³ : {fp16_tf:7.2f} TFLOPS   (中位 {fp16_ms:.3f} ms, {args.iters} 次)")
    print(f"FP32 对照       4096² : {fp32_tf:7.2f} TFLOPS   (中位 {fp32_ms:.3f} ms)")
    print(f"参考值           : 原厂 ~{STOCK_TFLOPS:.0f}   解锁 ~{UNLOCKED_TFLOPS:.0f}   判定线 {CUT_TFLOPS:.0f}")
    print()
    print(f"结论: {verdict}")
    if code == 1:
        print("      要用解锁：插上 U 盘并重启（BIOS 里 U 盘排在前面时会自动跑），")
        print("      开机后版本屏有 5 秒倒计时，什么都不按即自动解锁。")
    elif code == 0:
        print("      提示：解锁是易失的，重启/关机后需要再走一次 U 盘启动。")
    print(bar)
    return code


if __name__ == "__main__":
    sys.exit(main())


