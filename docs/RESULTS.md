# 测量结果

所有数据来自同一台机器（NUC13RNGi9 + ASUS RTX 4060 Ti 16 GB，VBIOS `95.06.25.00.d4`，
驱动 617.42），Python 3.13.12 / PyTorch `2.12.1+cu130`。原始文件在 [`../evidence/`](../evidence/)。

## 1. GEMM（`scripts/bench_unlock.py`，sha256 `af8366ee…9938c6`）

4096² 与 8192³ 方阵，FP16/BF16 输入、**FP32 累加**（`allow_fp16_reduced_precision_reduction = False`），
每种模式 3 次热身 + 10 次 CUDA event 计时取中位。FP32 作为"未受影响"的对照组。

| 模式 | 原厂 | 解锁 | 变化 |
| --- | ---: | ---: | ---: |
| FP16→FP32 acc 8192³ | 45.78 | **75.24** | **+64.4%** |
| FP16→FP32 acc 4096² | 37.77 | 73.14 | +93.6% |
| BF16→FP32 acc 8192³ | 44.84 | 68.80 | +53.4% |
| BF16→FP32 acc 4096² | 45.67 | 79.00 | +73.0% |
| FP32 4096²（对照） | 11.95 | 11.87 | −0.7%（噪声） |

复测一致性：解锁后四次独立测量分别为 **75.24 / 75.17 / 72.57 / 72–75**（最后一次是休眠唤醒后）；
原厂两次 45.78 / 45.65。数值精度自检 `max_rel_err = 3.15e-4`，解锁前后逐位相同。

`evidence/bench_stock_before_unlock.json`、`bench_unlocked_after_unlock.json`、
`bench_armed_run03.json`、`bench_hibernate_resume.json`、`bench_stock_verify.json`。

## 2. 持续负载（`scripts/stress_unlock.py`，75 s 连续 8192³）

| 指标 | 值 |
| --- | --- |
| TFLOPS | 中位 **75.88**，最低 62.82，末轮 74.08（无热衰减） |
| 功耗 | 中位 149.9 W，峰值 **156 W**（板限 165 W，撞墙） |
| 温度 | GPU 最高 **72 °C** |
| SM 频率 | 稳定约 **2310 MHz**（低于 boost 2760） |

结论：解锁把瓶颈从"发射率"换成了"165 W 墙"。频率下降约 16%，吞吐提升约 64%，
与"被禁用的 tensor 通路恢复工作"的解释一致（不是靠频率或电压）。

`evidence/stress_unlocked.json`。

## 3. ComfyUI A/B

### 方法

固定工作流（`scripts/comfy_qw21_ab.json`，走 `POST /prompt` + `/history` 轮询）：

- 模型：`redqw21UNLOCKEDREDGPTK2tAE_redqw21UNLOCKEDV1T2I_bf16.safetensors`（13.25 GB，**纯 bf16**）
- 文本编码器：`qwen3vl_8b_nvfp4.safetensors`；VAE：`qwen_image_2.1_vae_bf16.safetensors`
- 1024×1024、12 步、euler/simple、cfg 3.5，每轮更换 seed 绕开 ComfyUI 的节点缓存
- 判据取服务端 tqdm 的 `s/it`（纯采样段），同时采 `nvidia-smi`

| | 采样 s/it | 12 步采样 | wall | 功耗 | util | 同 boot GEMM 8192³ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原厂（拔 U 盘重启） | **3.39** | 40.7 s | 42.9 s | 155 W | 100% | 45.65 |
| 解锁 | **2.16** | 25.9 s | 28.6 s | 164 W | 100% | 72–75 |
| 变化 | **×1.57** | −14.8 s | −33% | +9 W | — | ×1.6 |

单轮值：解锁 2.13 / 2.15 / 2.17；原厂 3.39 / 3.40。两边都是 util 100%、顶在 165 W。
`s/it` 的 1.57× 与 GEMM 的 1.6× 自洽。

> wall-clock 不能单独作判据：两次测量跑在不同的服务器实例上，模型加载/换出状态不同。
> `s/it` 是纯采样段，才是可比量。

`evidence/comfy_ab_summary.json`、`comfy_a1_warmup.json`、`comfy_a2_measure.json`、
`comfy_a3_measure.json`、`comfy_b1_warmup.json`、`comfy_b2_measure.json`。

### 反例：量化 + 流式的大模型工作流 0% 收益

同一台机器、同一天，用户实际在跑的 MiniMaxH3 视频工作流（8 步）：

| | 采样 s/it | 总耗时 |
| --- | ---: | ---: |
| 原厂（10-02 多次记录） | 80.3 – 82.5 | 12:29 – 14:10 |
| 解锁（10-28） | **81.8** | **12:38** |

原因（日志原文）：

```
Model MiniMaxH3 prepared for dynamic VRAM loading. 19995MB Staged.
Using async weight offloading with 2 streams
Detected mixed precision quantization
Native ops: convrot_w4a4, w6a8_int8, float8_e5m2, asym_w4a8_int8, float8_e4m3fn, int8_tensorwise
CLIP: qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
```

19,995 MB 的模型装进 16,380 MB 显存 → 每步按块流式换入；计算走 W4A4/W4A8/int8/fp8 量化
张量通路，文本编码器是 NVFP4。瓶颈是显存容量/带宽，不是发射率。

**判据（给后来者）**：工作流要吃到这个解锁，需要 ①未量化 fp16/bf16、②能整块驻留显存、
③采样段 util 打满且贴近功耗墙。三者缺一，收益就会被带宽稀释。

## 4. 四次启动的 UEFI 侧结果

| # | 场景 | 结果 |
| --- | --- | --- |
| 1 | 只读启动（未按空格，30 s 超时） | 零写入；枚举/GOP/寄存器采样全绿；链回 Windows |
| 2 | 手动按空格 | `MAILBOX0=0x67b00001`、四写读回、选择器写入并穿 FLR |
| 3 | 武装模式（5 s 倒计时自动） | 与 #2 完全一致，8192³ 复测 75.17 |
| 4 | 休眠唤醒后 | 固件重新 POST → U 盘再跑一轮 → 解锁存活，8192³ 72.57 |

第 4 次同时说明：**休眠/睡眠不需要额外处理**，只要 U 盘在启动顺序里，唤醒路径也会重新解锁
（`LastBootUpTime` 未变，确认是 S4 恢复而非全新引导）。

## 5. 测量噪声与注意事项

- 4096² 的 FP16 数值对时钟状态敏感（冷态 35.6–37.8，热态可到 44.2），**不要用它做判定**；
  判定统一用 8192³（原厂 45.0–45.9，解锁 72.6–75.2）。
- 后台有 GPU 负载时 fp16 会掉到 50 以下、FP32 对照也会掉，`scripts/check_unlock.py`
  用 FP32 对照做交叉校验并输出"无法判定"。
- 功耗墙 165 W 是本机的硬约束，任何"再快一点"的尝试都要先处理散热与功耗，与本次解锁正交。
