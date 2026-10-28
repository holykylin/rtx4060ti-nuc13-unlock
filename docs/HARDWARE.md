# 本机硬件档案与采集值

本文件把 UEFI 采集（照片形式，未发布）与本项目几次启动的读数整理成文本，方便同一批次
VBIOS 的用户对照。**这些是设备指纹，公开前请自行判断是否需要脱敏。**

## 主机

| 项 | 值 |
| --- | --- |
| 主机 / 主板 / 版本 | Intel NUC13RNGi9 / NUC13SBBi9 / `M58736-304` |
| BIOS | `SBRPL579.0068.2026.0625.1114`（2026-06-25） |
| CPU 平台 | Intel Raptor Lake，PCH `8086:7a84`（Z790 家族） |
| 核显 | Intel UHD Graphics 770，`8086:a780` @ `0000:00:02.0` |
| 独立显卡 | ASUS GeForce RTX 4060 Ti 16 GB，`10de:2805`，子系统 `1043:8921` |
| 显卡音频功能 | `10de:22bd` @ `0000:01:00.1` |
| PCIe 根端口 | `8086:a70d` @ `0000:00:01.0`，pri/sec/sub = 0/1/1，class `060400` |
| 上游桥（RC） | `8086:a700` @ `0000:00:00.0` |
| VBIOS / 驱动 | `95.06.25.00.d4` / 617.42 |
| 显存 / 功耗墙 | 16,380 MiB（寄存器 `0x3ffc`）/ 165 W（max 182 W） |

## PCI 资源（`loader_run02_unlock.log`）

| BAR | 值 | 说明 |
| --- | --- | --- |
| BAR0 | 32-bit mem `0x93000000`，16 MiB | GPU 寄存器窗口；**基址由固件分配、每次启动可能不同，不要写进 profile** |
| BAR1 | 64-bit mem `0x0000006000000000`，64 MiB | 显存窗口（按 PSTRAPS 解码为 64 MiB） |
| BAR3 | 64-bit mem `0x0000006400000000` | 2×BAR0 |
| BAR5 | I/O `0x3000` | |
| PCIe cap | `DEVCAP 0x112c8de1`（FLR yes），`LINKCAP 0x00457884` | FLR 能力存在 |
| ReBAR | `0x0bb0`：**0 个** resizable BAR | 本机未开 ReBAR |

## 冷态寄存器（只读采样）

| 名称 | 偏移 | 值 | 说明 |
| --- | --- | ---: | --- |
| PMC_BOOT_0（chip-id） | `0x000000` | `0x196000a1` | AD106 ✓ |
| FB_SIZE_MIB | `0x1183a4` | `0x3ffc` | 16,380 MiB |
| VGA_WORKSPACE | `0x625f04` | `0x00000001` | bit3=0，D0（`0xbadf1301` 才是 D3 门控） |
| GFW_PLM | `0x118128` | `0x00008b8f` | GFW 侧 PLM |
| GSP_CPUCTL | `0x110100` | `0x00000010` | |
| PGC6_BSI_SCRATCH15 | `0x1180fc` | `0x201021bb` | |
| MMU_PLM | `0x1fa7c8` | `0x0045cb8f` | bit0=1（锁位健全） |
| MMU_LOCK_LO / HI | `0x1fa82c` / `0x1fa830` | `0x00100000` / `0x03cfbff0` | 高地址不是 FB 顶 → 工具按"锁无效"处理 |
| WPR2_LO / HI | `0x1fa824` / `0x1fa828` | `0x1ffffe00` / `0x00000000` | 事务前 WPR2 未建立 |
| SEC2_CPUCTL | `0x840100` | `0xbadf5620` | **BADF_VARIANT**：读门毒值族，仅分类记录，不参与点火判定 |
| FUSE_OPT_FEAT_OVR_DISABLE | `0x8203f0` | `0x00000000` | |
| FUSE_VER / VER_DECODE | `0x824140` / `0x8241c0` | `0x00000001` / `0x00000001` | |
| AD1xx XVE_PLM | `0x88ff4` | `0xffffff8f` | |
| ADA WPR_PLM / WPRCFG_PLM | `0x1fa7c4` / `0x1fa7cc` | `0x0004cb8f` / `0x0004cb8f` | |
| ADA FBPA_PLM | `0x9a0148` | `0xffffff0f` | |
| TU10x 偏移 | `0x409650` / `0x409664` | `0xbadf5040` | Ada 上不存在，读到 `badf` 属预期 |

### FEAT 集群（解锁目标，`0x823800` 起）

| 偏移 | 冷态值 | 说明 |
| --- | ---: | --- |
| `0x823800` | `0xffffff8f` | FEAT_READOUT_0 |
| `0x823804` | **`0xffffff8f`** | **FEAT_PLM**——解锁后变 `0xffffffff` |
| `0x823808` | `0x01100282` | |
| `0x82380c` | `0x00888888` | |
| `0x823810` | `0x00aaaaaa` | |
| `0x823814` | `0x00000233` | |
| `0x823818` | `0x00410080` | FEAT_READOUT_1（`0` = 全速；`0xbadf5040` = PLM 仍关闭） |
| `0x82381c` | **`0x76111154`** | **SS0**——解锁值 `0x88888888`；引导间会漂移（也见过 `0x72111154`、`0x72111155`、`0x56111154`） |
| `0x823820` | **`0x00000004`** | **SS1**——解锁值 `0x8` |
| `0x823824` | `0x00000000` | |
| `0x823828` | `0x00000001` | |
| `0x82382c` | `0x0000000a` | |
| `0x823b00` | `0x00004b8f` | |

## VBIOS / PROM

| 项 | 值 |
| --- | --- |
| BAR 内 PROM 偏移 | `0x300000`（1 MiB 窗口） |
| PCI ROM image size | `0x25e00`（155,136 B） |
| PCI ROM SHA-256 | `<作者未公开>` |
| PROM 全 1 MiB SHA-256 | `<作者未公开>` |
| PROM 视图 `[0, 0xd6c00)` SHA-256 | `<作者未公开>` |
| 读回状态 | `0`（成功） |

> 上面的 PROM/ROM 哈希与上游两张 Gigabyte 卡（`profile.json` 里 `ebb63e82…` / `603baffe…`）
> 完全不同，这也是为什么本项目走**家族路由 + 从卡上 VBIOS 现读 FWSEC**，而不是把哈希编进二进制。

## GOP / 显示

- UEFI 下 1 个 GOP handle，3840×2160 `Bgr`。
- 解锁事务那次日志显示 `DETACH: GOP ... is not on the target GPU (multi-GPU) - left untouched`，
  即工具判定控制台 GOP 不属于目标卡，**没有断连**，因此本机全程有屏、没有出现黑屏窗口
  （与笔记本单卡路径的行为不同）。

