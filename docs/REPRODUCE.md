# 复现步骤

目标：在一台 Windows 机器上，用 `nv-uefi-unlocker` 在 NVIDIA 驱动加载前完成解锁，并用
本仓库的脚本判定结果。以下命令以本机（NUC13RNGi9）实测路径为例，换成你自己的路径即可。

## 0. 前置条件

| 条件 | 怎么确认 |
| --- | --- |
| Secure Boot **关闭** | `Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\SecureBoot\State` 的 `UEFISecureBootEnabled` 应为 0；最终以 BIOS 为准 |
| BitLocker **已挂起** | 管理员：`manage-bde -status C:`；`Suspend-BitLocker -MountPoint C: -RebootCount 3` |
| 单卡、且是显示卡 | 多卡时用 `\tx-select-bdf.txt` 钉卡 |
| FAT32 U 盘 ≥ 256 MB | 资产约 85 MB |
| 备份 | 记录当前驱动版本、VBIOS、并保留一条能正常进 Windows 的启动路径 |

> 关 Secure Boot 会改变 TPM PCR。本工具不写 ESP/NVRAM，不会破坏引导，但**先挂起 BitLocker**
> 能把"需要恢复密钥"的意外降到零。

## 1. 取工具（不随本仓库分发固件）

1. 下载 `nv-uefi-unlocker` **v2.1.0** release zip：
   <https://github.com/physicsdolphin/nv-uefi-unlocker/releases/tag/v2.1.0>
2. 校验：

   | 文件 | SHA-256 |
   | --- | --- |
   | `BOOTX64.EFI` | `b5e96f4e0ca162b98693af00452a6933ea47dd7e24f0d4b3c804b48a05ec9dea` |
   | `assets-x86_64-windows.exe` | `59f311ffe0be8e62951e1cf350e1703f9d67f86f1a989c99c0b1511bceb0c1d4` |

   本机实测通过。

## 2. 现场再生资产

```powershell
Expand-Archive nv-uefi-unlocker-v2.1.0.zip -DestinationPath .\v210
.\v210\make-usbroot.ps1 -Family ad102 -Out .\usbroot -Work .\inputs
```

脚本会下载两个钉 SHA-256 的公开输入（NVIDIA kernel-module-source 610.43.03 与
CachyOS `nvidia-utils` 包），校验后本地再生。`-Family ad102` 对应 Ada（`0x2600..=0x28ff`），
本卡 `0x2805` 属于该段。本机产物：

| 文件 | 字节 |
| --- | ---: |
| `booter_load_ad102.bin` | 57,672 |
| `gsp_boot_ad102.bin` | 36,864 |
| `gsp_boot_desc_ad102.bin` | 84 |
| `fwimage_ad102.bin` | 84,226,048 |
| `fwsignature_ad102.bin` | 4,096 |
| `scrubber_ad10x.bin` | 8,264 |
| `v67-ad102-four-plm.bin` | 64,000 |

> 把 `v67-*.bin` 从 U 盘拿掉 = **回放/诊断模式**（走完整条链但零解锁写入），第一次接触新卡
> 建议先这样跑一次。

## 3. 布盘

FAT32 U 盘根目录：

```
\EFI\BOOT\BOOTX64.EFI        ← 工具本体（固件按这个标准路径找）
\booter_load_ad102.bin
\gsp_boot_ad102.bin
\gsp_boot_desc_ad102.bin
\fwimage_ad102.bin
\fwsignature_ad102.bin
\scrubber_ad10x.bin
\v67-ad102-four-plm.bin      ← 有它才是解锁模式
\i_know_what_i_am_doing.txt  ← 可选：武装模式（5 s 倒计时自动跑，任意键中止）
```

写入后逐个比对 SHA-256。

## 4. 启动

1. Windows 里点**重启**（不要"关机再开"，避免 dGPU 被 EC 断电停在 D3cold）。
2. 开机键进 BIOS 启动菜单（NUC 是 **F10**），选 `UEFI: <你的U盘>`。
3. 版本屏出现后：
   - 普通模式：30 秒内按**空格**；
   - 武装模式：5 秒倒计时自动开始，任意键中止。
4. 之后全自动：claim → scrubber → FWSEC → booter → 四写 → 选择器 → FLR → 链回 `bootmgfw`。
   中途黑屏几秒可能发生（本机因 GOP 不属于目标卡，实际全程有屏）。

## 5. 判读成功

U 盘根 `\loader.log` 里应出现：

```
BRIDGE-BME: Some((0,0,1,0)) command 0x0003 -> 0x0007     ← 若桥上 BME 未开才会出现
BOOTER forensic: ... MAILBOX0=0x67b00001                  ← 成功标记
POST-BOOT: FEAT_PLM=0xffffffff
SELECTOR RESULT: SS0=0x88888888 SS1=0x8
POST-FLR: verified (selectors survive AON)
FINAL: transaction complete, all DMA released
```

进 Windows 后：

```powershell
# 1 秒判定当前是否解锁（本仓库脚本）
.\scripts\check-unlock.cmd

# 完整 A/B 数据
python .\scripts\bench_unlock.py after
python .\scripts\stress_unlock.py 60
```

期望：`check-unlock` 报 **已解锁（≥58 TFLOPS）**，`bench_unlock.py` 的 8192³ FP16→FP32
在 **72–76 TFLOPS**（原厂 ~45.8）。

## 6. 常见异常

| 现象 | 含义 / 处理 |
| --- | --- |
| `CONFIRM: 30s timeout - ABORT` | 没按键，本次零写入。重新启动再来一次 |
| `POST-BOOT: SEC2 MAILBOX0=0x00000089` | booter 的 WPR 描述符校验失败，最常见根因是**上游 PCI 桥 Bus Master 未使能**。v2.1.0 会自动置位（日志 `BRIDGE-BME`），若仍失败，把完整 `loader.log` 提给上游 |
| `SEC2_CPUCTL ... [BADF_VARIANT]` | 读门毒值族，属正常分类输出，不影响点火 |
| `TU10x FEAT_PLM ... [PRIV_VIOLATION]` | Ada 上该偏移不存在，读到 `0xbadf5040` 属预期 |
| `PM: WARM ENTRY` | 入口不是 D0（休眠恢复等）。工具会把卡拉回 D0；要更严就放 `\tx-require-d0.txt` 让它直接 abort |
| 解锁成功但进系统没变快 | 见 [`RESULTS.md` §3](RESULTS.md#3-comfyui-ab)：量化/流式工作流不受益 |

## 7. 回滚

- 删掉 `\i_know_what_i_am_doing.txt` → 回到"必须按空格"；
- 把 Windows Boot Manager 移回启动顺序第一 / 拔掉 U 盘 → 完全不经过解锁器；
- 解锁本身易失：**断电一次即回原厂**，不需要任何清理。
