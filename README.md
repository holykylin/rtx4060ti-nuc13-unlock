# RTX 4060 Ti 16 GB (AD106) tensor unlock on Intel NUC 13 — Windows UEFI evidence report

> 中文主文档 · [English summary](#english-summary) at the bottom.
> 本仓库只放**报告、日志、测量脚本**，不含任何 NVIDIA 固件。

在 **ASUS RTX 4060 Ti 16 GB（`10de:2805` / `1043:8921`）+ Intel NUC13RNGi9** 上，用
[`physicsdolphin/nv-uefi-unlocker`](https://github.com/physicsdolphin/nv-uefi-unlocker) v2.1.0
完成 pre-driver tensor 发射率解锁，并给出 Windows 侧 GEMM、持续负载与真实 ComfyUI 工作流的
A/B 数据。**本卡此前在该项目兼容性矩阵里只有"上游硅验证 🟢"，这份报告是它的 EFI 全链实证。**

## TL;DR

| 指标 | 原厂 | 解锁 | 变化 |
| --- | ---: | ---: | ---: |
| FP16→FP32 累加 GEMM 8192³ | 45.78 TFLOPS | **75.24 TFLOPS** | **+64%** |
| BF16→FP32 累加 GEMM 8192³ | 44.84 | 68.80 | +53% |
| FP32 对照 4096² | 11.95 | 11.87 | 不变（不是超频） |
| ComfyUI：稠密 bf16 图像工作流（12 步 1024²） | 3.39 s/it | **2.16 s/it** | **×1.57** |
| ComfyUI：量化视频工作流（H3，20 GB 流式） | 81.8 s/it | 81.8 s/it | **0%（预期）** |
| 75 s 满载 | — | 75.9 TFLOPS / 156 W / 72 °C | 顶到 165 W 墙 |

## 这是什么，不是什么

NVIDIA 在消费级 GeForce 上用 fuse 把 FP16/BF16（和 TF32）**FMA 进 FP32 累加**的 tensor
发射率钳到约一半（速度选择器 `SS0=0x88888888` / `SS1=0x8` 被禁，PLM `0xffffff8f` 只允许
特权固件写）。解锁 = 在驱动加载前的 UEFI 窗口里复刻内核的引导链，让**已签名的 NVIDIA 固件
自己**写 PLM 寄存器并放开选择器，随后 FLR、交棒 Windows 原版驱动。

- **不是** 超频 / 改功耗墙 / 刷 VBIOS：FP32 对照完全不变，满载频率反而从 2760 降到约 2310 MHz。
- **是** 易失的：不写 VBIOS、不写 ESP、不写 NVRAM，断电即回原厂，每次冷启动重放一次。

## 硬件与软件

| 项 | 值 |
| --- | --- |
| 主机 / 主板 / BIOS | Intel NUC13RNGi9 / NUC13SBBi9 / `SBRPL579.0068.2026.0625.1114` |
| GPU | ASUS GeForce RTX 4060 Ti 16 GB，`10de:2805`，子系统 `1043:8921` |
| PCI 位置 | `0000:01:00.0`（上游桥 `8086:a70d` @ `00:01.0`），音频功能 `01:00.1`（`10de:22bd`） |
| VBIOS / 驱动 | `95.06.25.00.d4` / 617.42 |
| 显存 / 功耗墙 | 16,380 MiB / 165 W |
| 系统 | Windows 11 Pro build 26300，Secure Boot 关闭，PyTorch 2.12.1+cu130 |
| 冷态寄存器 | chip `0x196000a1`、VRAM `0x3ffc`、SS0 `0x76111154`、SS1 `0x4`、PLM `0xffffff8f` |

## 怎么复现

工具链不随本仓库分发 NVIDIA 固件，全部资产由官方公开输入现场再生（钉 SHA-256）：

```powershell
# 1) 取 nv-uefi-unlocker v2.1.0 release（BOOTX64.EFI + assets-x86_64-windows.exe + make-usbroot.ps1）
#    https://github.com/physicsdolphin/nv-uefi-unlocker/releases/tag/v2.1.0
#    本机用到的 BOOTX64.EFI = b5e96f4e0ca162b98693af00452a6933ea47dd7e24f0d4b3c804b48a05ec9dea
# 2) 从钉死 SHA-256 的公开输入再生 ad102 家族资产（约 500 MB 下载、85 MB 产物）
.\make-usbroot.ps1 -Family ad102 -Out .\usbroot -Work .\inputs

# 3) 拷到 FAT32 U 盘：资产放根目录，EFI 放 \EFI\BOOT\BOOTX64.EFI
#    放 v67-ad102-four-plm.bin 才是解锁模式；不放 = 回放/诊断模式（零写入）
# 4) BIOS 关 Secure Boot，U 盘启动，版本屏按空格（或放 i_know_what_i_am_doing.txt 走 5 s 倒计时）
```

判读与排障见 [`docs/REPRODUCE.md`](docs/REPRODUCE.md)，本机操作卡见
[`docs/RUNBOOK-zh.md`](docs/RUNBOOK-zh.md)。解锁后随时可用
[`scripts/check-unlock.cmd`](scripts/check-unlock.cmd) 判定当前状态（约 1 秒，退出码 0/1/2）。

## 本机实测的关键日志行

完整日志在 [`evidence/`](evidence/)（四次启动：只读、手动解锁、武装模式、休眠唤醒后自动重放）。

```
DMA-PATH[pre-fire]  bridge 8086:a70d command 0x0003 (BME off)
BRIDGE-BME: Some((0,0,1,0)) command 0x0003 -> 0x0007   ← 工具自动补上游桥 Bus Master
BOOTER forensic: MAILBOX0=0x67b00001                    ← V67 载荷成功标记
POST-BOOT: FEAT_PLM=0xffffffff  SS0=0x76111154  SS1=0x4
POST-BOOT: WPRCFG=0xfffff0ff  FBPA=0xffffff0f  WPR=0xffffffff
SELECTOR RESULT: SS0=0x88888888 SS1=0x8
POST-FLR selectors: ss0=0x88888888 ss1=0x8
POST-FLR: verified (selectors survive AON)
FINAL: transaction complete, all DMA released
HANDOFF-OUT: plm_open=true ss0_unlock=true ss1_unlock=true
```

## 三条值得记录的新发现

1. **`10de:2805` 在本平台的 EFI 全链实证**（此前矩阵里只有 🟢）。产品 ID 与子系统都不同
   于上游已实测的两张 Gigabyte 卡（`1458:4112`），说明该项目的**按家族路由**（Ada
   `0x2600..=0x28ff` → `ad102` 资产）在跨板卡上是成立的：FWSEC 从卡自己的 VBIOS 现读现解析，
   不需要把 PROM 哈希编进二进制。
2. **上游桥 Bus Master 的状态会随启动路径变化**：同一台机器，白天只读采集读到
   `command=0x0007`（BME 已开），解锁那次启动读到 `0x0003`（BME 关），由工具自动置位后
   booter 才成功。也就是说 PR #5 那个 `0x89` 修复在这台 NUC 上**不是可选项而是必需项**。
3. **端到端收益取决于工作流形态**：同一个 ComfyUI，稠密 bf16 图像工作流 +57%，
   而 20 GB 流式 + W4A4/int8/fp8 量化的视频工作流 0%。详见
   [`docs/RESULTS.md`](docs/RESULTS.md#3-comfyui-ab)。

## 仓库内容

```
docs/      结果、复现步骤、硬件档案、操作卡、向上游提交的建议
evidence/  loader 日志 ×4、GEMM/压力/ComfyUI 原始 JSON
scripts/   bench_unlock.py、stress_unlock.py、check_unlock.py(+cmd)、comfy_ab.ps1、工作流 JSON
```

## 不发布的内容

- **任何 NVIDIA 固件/载荷**（`booter_*`、`fwimage_*`、`gsp_*`、`v67-*`、`scrubber_*`）——
  由官方公开输入本地再生，遵守上游项目的资产纪律。
- 恢复密钥、BitLocker 相关信息、机器序列号、本机用户目录与主机名（证据 JSON 里的 `host` 已替换为机型）。
- UEFI 采集时拍摄的屏幕照片（内容已解码成 [docs/HARDWARE.md](docs/HARDWARE.md) 的表格）。
- 本卡 VBIOS 的三类 SHA-256 与日志里的 PROM crc32（设备指纹，作者选择不公开；脱敏清单见
  [evidence/README.md](evidence/README.md)）。

## 安全与回滚

解锁触及启动链与 GPU 寄存器，属于**有风险操作**：可能黑屏一次、需要断电重启；错误使用
可能让卡进需要断电恢复的状态。本仓库的记录不构成对你机器的兼容性保证。

- 只在**单卡、显示卡**、Secure Boot 关闭、BitLocker 已挂起的前提下操作；
- 失败后**同一次开机会话绝不重试**：长按电源 10 s 断电 → 拔 U 盘 → 正常开机；
- 恢复：断电即回原厂（易失），本工具不写任何持久存储。

## 上游与致谢

- [`physicsdolphin/nv-uefi-unlocker`](https://github.com/physicsdolphin/nv-uefi-unlocker)（GPL-2.0-only）——本次使用的 Windows UEFI 实现、资产管线与 BME 修复
- [`JustAResearcher/gpu-unlock-ada`](https://github.com/JustAResearcher/gpu-unlock-ada)——AD10x 四写链与 `2805` Linux canary
- [`Zagitta/gpu-unlock`](https://github.com/Zagitta/gpu-unlock)、[`TOTORONG/AD103_win_unlocker`](https://huggingface.co/TOTORONG/AD103_win_unlocker)——事务链与 Windows EFI 载具先例
- [`ZeroHackz/gpu-unlock-windows`](https://github.com/ZeroHackz/gpu-unlock-windows)——早期对照（其板卡 pin 不适用于本卡，见 [`docs/UPSTREAM.md`](docs/UPSTREAM.md#为什么没有选-zerohackz-那份)）

## License

本仓库的文档与脚本：MIT（见 [`LICENSE`](LICENSE)）。上游代码与 NVIDIA 固件各从其原许可。

---

## English summary

A reproducibility report for unlocking the FP16/BF16→FP32 tensor issue rate on an **ASUS
RTX 4060 Ti 16 GB (`10de:2805`, subsystem `1043:8921`)** inside an **Intel NUC13RNGi9**,
using `nv-uefi-unlocker` v2.1.0 on Windows 11. The card previously had only upstream-silicon
evidence in that project's compatibility matrix; this is the first full UEFI-chain run on it.

Measured (same boot, same Python/PyTorch): FP16→FP32 GEMM 8192³ **45.78 → 75.24 TFLOPS
(+64%)**, BF16 44.84 → 68.80, FP32 control unchanged (11.95 → 11.87, i.e. not an overclock).
A dense bf16 ComfyUI image workflow (12 steps, 1024²) went **3.39 → 2.16 s/it (×1.57)**;
a quantised, weight-streaming video workflow showed **no gain**, as expected — the unlock
targets tensor issue rate, not memory bandwidth. The unlock is volatile (replayed on every
boot, no VBIOS/ESP/NVRAM writes) and the repo contains logs, measurement scripts and
documentation only — no NVIDIA firmware.



