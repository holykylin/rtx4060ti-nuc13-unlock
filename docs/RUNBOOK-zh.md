# RTX 4060 Ti 解锁：当前进度与操作卡

时间：2026-10-28 15:4x（Asia/Shanghai）。工作目录 `<你的工作目录>`。

## 结论：路线已定，工具已就绪

本机卡：ASUS RTX 4060 Ti 16GB，`10de:2805` / `1043:8921`，BDF `0000:01:00.0`，
VBIOS `95.06.25.00.d4`，驱动 617.42，165 W。

选用 **physicsdolphin/nv-uefi-unlocker v2.1.0（stable）**，理由：

1. 它**按芯片家族路由**（Ada `0x2600..0x28ff` → `ad102` 资产），本卡 `0x2805` 正落在
   已列出的范围（矩阵里 2805 标 🟢「上游硅验证」）。不需要把自己的 PROM/ROM 哈希
   编进二进制——这跟 ZeroHackz 那份（写死 Gigabyte `1458:4112` 的 PROM 视图哈希）
   有本质区别。
2. 它自己读**卡上 VBIOS** 里的 FWSEC（`PROM@BAR0+0x300000`，解析 V3 描述符），
   不依赖板卡哈希表；实测覆盖 AD106 桌面 2803 / 2805、AD103、AD107、GA10x、TU106。
3. 内置 **Bridge BME 修复**（PR #5）——我们这台 NUC 的上游桥 `00:01.0` 已经是
   `command=0x0007`（BME 已开），所以这一条本来就不是我们的坑，但留着是保险。
4. 它会自动**链回 `\EFI\Microsoft\Boot\bootmgfw.efi`**，日志写到 U 盘根 `\loader.log`；
   不写 ESP、不写 NVRAM、无持久化，断电即回原厂。

被否掉的路线：ZeroHackz/gpu-unlock-windows（写死 Gigabyte 板卡 pin，换卡即拒；
其 `assets.json` 与 `app_io.c` 里的资产名/哈希本身就对不上，`GU_BOARD_SUBSYSTEM`
还是编译期常量 `0x41121458`，本卡 `0x89211043` 会直接被 `ConfigCheck` 拦掉）。

## 已经做完的（本机实测/校验）

| 项目 | 结果 |
| --- | --- |
| 本卡冷态寄存器（证据：见 `docs/HARDWARE.md` 的采集值表） | chip `0x196000a1`、VRAM `0x3ffc`(=16380 MiB)、SS0 `0x76111154`、SS1 `0x4`、PLM `0xffffff8f`、PCI ROM `0x25e00`、PROM 视图哈希（作者未公开） |
| 上游桥 | `8086:a70d`，`command=0x0007`（BME 已使能，不需要修）；GPU 自身 `command=0x0003`（BME 关，loader 的 claim 会开） |
| 资产生成 | `make-usbroot.ps1 -Family ad102` 全绿，每个输入包按钉死 SHA-256 校验 |
| U 盘 | `G:`（Disk 4 ASolid USB，FAT32，1 GiB）已写入并逐文件比对哈希，`all match: True` |
| 基线 | `results\bench_stock_before_unlock.json`：FP16→FP32 acc 8192³ **45.78 TFLOPS**、BF16 8192³ **44.84**、FP32 4096² 11.95 |

U 盘当前是**回放模式**（没有放 `v67-ad102-four-plm.bin`）：走完整条链但**零解锁写入**。

```
G:\EFI\BOOT\BOOTX64.EFI          236544   loader v2.1.0 (sha b5e96f4e…)
G:\booter_load_ad102.bin         57672
G:\gsp_boot_ad102.bin            36864
G:\gsp_boot_desc_ad102.bin          84
G:\fwimage_ad102.bin          84226048
G:\fwsignature_ad102.bin          4096
G:\scrubber_ad10x.bin             8264
```

## 你要做的（物理步骤，我代替不了）

### 0. 先处理 BitLocker（管理员 PowerShell）

```powershell
manage-bde -status C:                                   # 看当前是 On / Suspended
Suspend-BitLocker -MountPoint C: -RebootCount 3         # 没有这个 cmdlet 就用：
# manage-bde -protectors -disable C: -RebootCount 3
```

本工具**不改** ESP、BCD、NVRAM、BootOrder，理论上不触发恢复；但关 Secure Boot 本身
会改变 PCR，所以先挂起最稳。恢复：`Resume-BitLocker -MountPoint C:`。

### 1. BIOS 关 Secure Boot

当前 `HKLM:\SYSTEM\CurrentControlSet\Control\SecureBoot\State\UEFISecureBootEnabled = 1`
（即现在是开的，之前那轮观察器跑完后被开回去了）。

开机按 **F2** → `Security` → `Secure Boot` → 取消勾选 → `F10` 保存退出。

### 2. 从 U 盘启动（回放模式，第一次）

1. Windows 里点**重启**（不要"关机再开"，避免 dGPU 被 EC 断电进 D3cold）。
2. 开机按 **F10** 进启动菜单 → 选 `UEFI: ASolid USB`（或名字里带 UEFI + USB 的那项）。
3. 版本屏出现后按 **空格**（30 秒不按会自动回 Windows）。
4. 之后全自动：断 GOP → scrubber → FWSEC → booter → FLR → 链回 Windows。
   中途**黑屏/花屏几秒是正常的**，别断电。
5. 回到 Windows 后告诉我，我读 `G:\loader.log` 判读链路。

**第一次没有 v67，所以不会解锁**，只看链路是否成立（`MAILBOX0`、`booter status`、
`TX: execution verified`、`POST-FLR: verified` 这几行）。

### 3. 第二次才是真解锁

链路绿了之后，我把 `v67-ad102-four-plm.bin` 放到 U 盘根，重复上面第 2 步。
成功判据（日志）：`SELECTOR RESULT: SS0=0x88888888 SS1=0x8` +
`POST-FLR selectors: ss0=0x88888888 ss1=0x8` + `FINAL: transaction complete`。

然后我立刻跑同一个 `bench_unlock.py` 做 A/B：预期 8192³ FP16→FP32 acc 从 **45.8**
跳到 **68–77 TFLOPS**（公开报告 46.6→75.3/77.5）。

## 第一次启动结果（16:05，已判读）

日志：`logs\loader_run01_readonly.log`（已从 U 盘归档）。**没按空格，30 秒超时自动回
Windows**，所以 `no GPU writes this boot`——卡现在仍是原厂状态，45.78 TFLOPS 基线有效。

这次拿到的信息（全部来自本机，非推断）：

| 项 | 值 | 含义 |
| --- | --- | --- |
| `CONFIRM: 30s timeout` | 无按键 | 零写入，只跑了只读 M1 采样 |
| 枚举 | 38 个 PciIo；唯一目标 `0000:01:00.0 10de:2805` | 单卡，BDF 正确，无歧义 |
| BAR0 | `0x93000000`（32-bit mem） | 与上一轮照片一致 |
| PCIe cap | `DEVCAP 0x112c8de1 (FLR yes)` | 需要的 FLR 能力在 |
| GOP | 1 个，3840×2160 | dGPU 是显示卡 = 工具的 display 路径 |
| chip | `0x196000a1` | AD106 ✓ |
| FB_SIZE_MIB | `0x3ffc` = 16380 MiB | ✓ |
| VGA_WORKSPACE | `0x00000001` | **D0 有电有工作区**（不是 D3 门控的 `0xbadf1301`） |
| FEAT PLM `0x823804` | `0xffffff8f` | 门锁着，正是要开的那道 |
| FEAT SS0/SS1 | `0x72111154` / `0x4` | 未解锁（解锁值是 `0x88888888` / `0x8`）；SS0 与照片里 `0x76111154` 差一位，属引导间漂移 |
| FEAT sweep | 13 ok / 0 badf / 0 all-ones | PL0 读门全通，不是被门控的芯片 |
| `SEC2_CPUCTL` | `0xbadf5620 [BADF_VARIANT]` | 读门毒值族（与 4050 笔记本 `0xbadf1301` 同类），只用于分类记录，不参与点火判定 |
| 链回 | 找到 `\EFI\Microsoft\Boot\bootmgfw.efi` 并 `LoadImage` | 自动回 Windows 这条路通了（最容易翻车的一环已过） |

## 第二次：真解锁（v67 已放上 U 盘）

`G:\v67-ad102-four-plm.bin`（64000 B，`44c36b2d…dc8cb`，已比对）。这次按 **空格** 才会
真正执行：claim → scrubber → FWSEC → booter → **四写** → 选择器 → FLR → 链回 Windows。

成功后日志里要出现：

```
SELECTOR RESULT: SS0=0x88888888
SELECTOR RESULT: SS1=0x8
POST-FLR: verified (selectors survive AON)
FINAL: transaction complete, all DMA released
```

## 出事怎么办

| 现象 | 处理 |
| --- | --- |
| 屏幕 `STOP` / 异常中途失败 | **同一次开机会话绝不重试**。长按电源键 10 s 断电，等 10 s，拔 U 盘，正常开机进 Windows |
| 黑屏、链式启动失败 | 强制重启，走原来的 Windows 引导项；本工具没动任何固件/ESP |
| 进 Windows 后设备管理器报 Code 43 / 花屏 | 完全断电一次即回原厂（解锁是易失的）；仍异常再断电 + DDU 重装驱动 |
| U 盘认不到 | 换 USB 口（优先后置），BIOS 里确认 USB 启动没被禁 |

## 之后可做的（可选）

- 解锁后功耗墙还是 165 W：`Pwr` 会先撞墙，实际收益取决于负载。ComfyUI 里真正吃到
  这条通路的是 fp16/bf16 GEMM（attention、LoRA、大矩阵），解码类 token 生成不受益。
- 想放开功耗墙是另一条线（nvoc / 电压曲线），与本次解锁正交，先别混。

## 固化方案 A：武装模式 + 启动顺序（2026-10-28 已配好 U 盘侧）

前提认知：**解锁没有硬件持久态**（目标是活寄存器，写它们必须由签名固件在特权态执行，
Ada 的 VBIOS/固件又都验签）。所谓固化只是"每次开机自动重放"，不改变功耗墙、不改变风险。

### 已做（U 盘侧）

`G:\i_know_what_i_am_doing.txt`（409 B）已放置。效果：确认环节从"按空格/30 s 超时"
变成**5 秒倒计时后自动执行**，倒计时内按任意键仍然中止（零写入）。

### 还要你做（一次性，BIOS）

1. 插着 U 盘，开机 **F2** 进 BIOS。
2. `Boot` → `Boot Priority` / `Boot Devices`，把 `UEFI: ASolid USB`（或名字里带 UEFI+USB 的
   那项）**移到第一位**；`F10` 保存退出。
3. 之后每次开机流程自动变成：
   `固件 → U 盘 BOOTX64.EFI → 5 s 倒计时 → 事务 → 自动链回 bootmgfw → Windows（已是解锁态）`

### 日常表现

- 开机多十几秒（负载不在 Windows 侧，看不到窗口，只是慢一点）。
- 事务失败也**照样进 Windows**，只是没解锁（日志里能看到原因），不会死循环。
- 不插 U 盘时固件落到下一项，正常进 Windows（未解锁）。
- 想只解锁一次：拔掉 U 盘 → 用到时再插 → F10 一次性启动菜单选 U 盘。

### 回退（两件都做才彻底）

1. 删 `G:\i_know_what_i_am_doing.txt` → 回到"必须按空格"。
2. BIOS 里把 Windows Boot Manager 移回第一位 / 移除 U 盘启动项。

### 已知会失效的情况

- BIOS 更新、清 CMOS、个别 Windows 大版本更新可能重置启动顺序 → 表现为"开机没解锁、
  直接进 Windows"，无害，重排一次即可。
- 休眠/睡眠唤醒后解锁是否保持**未验证**：唤醒后跑一次
  `bench_unlock.py`（`_unlock` 目录）看 8192³ 是 ~45.8（已失效）还是 ~75（仍在）。
- Secure Boot 必须保持关闭（本 EFI 未签名）；要重开就得走自签证书入 db 那条路。

## 一键检测当前是否处于解锁态

```powershell
E:\Codex\ComfyUI_H3\_unlock\check-unlock.cmd              # 双击也行，带中文判读
E:\Codex\ComfyUI_H3\_unlock\check-unlock.cmd --nopause --json
```

判据：解锁只改变 FP16/BF16 → FP32 累加的 tensor 吞吐，所以跑一次 8192³ 矩阵乘就能分辨。
本机实测两态：**原厂 45.0–45.9 TFLOPS，解锁 72.6–75.2 TFLOPS**，判定线 58。

| 实测值 | 结论 | 退出码 |
| --- | --- | --- |
| ≥ 58 | 已解锁 | 0 |
| ≤ 52 | 未解锁（原厂） | 1 |
| 52–58 或 FP32 对照 < 9 | 无法判定（后台有 GPU 负载，关掉再跑） | 2 |

耗时约 1 秒（12 次 8192³ + 10 次 FP32 对照）。阈值来自本卡 2026-10-28 的实测，
换卡/换驱动后应重新标定。这是唯一能从 Windows 用户态拿到的判据——SS0/SS1/PLM 是
GPU 内部寄存器，没有驱动接口暴露，只能靠吞吐反推。




