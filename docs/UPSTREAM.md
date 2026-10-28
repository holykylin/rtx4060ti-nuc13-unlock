# 要不要"合并到原始项目"？——贡献方式与现成材料

先澄清一个说法：开源里没有"把我的资料合并进别人的项目"这个操作。实际有三种，力度从小到大：

| 方式 | 是什么 | 适合我们什么 |
| --- | --- | --- |
| **Issue / Discussion** | 提交一个数据点或异常报告，维护者决定要不要记进矩阵 | ✅ **首选**。我们的价值是"2805 + NUC 平台全链成功"这一条新证据 |
| **Pull Request** | 改代码或文档的补丁，维护者 review 后合入 | ✅ 可选。把兼容性矩阵里 `2805` 从 🟢 改成 ✅，并加一份 `docs/evidence/` 报告 |
| **Fork / 独立仓库** | 自己的仓库，链回上游 | ✅ 本仓库就是这个：报告 + 日志 + 测量脚本 |

一句话：**代码和矩阵改动走 PR，数据和报告走 Issue/Discussion，长报告放自己的仓库并在 Issue 里链接。**

## 上游的规矩（必须遵守，否则 PR 会被拒）

`nv-uefi-unlocker` 的 `AGENTS.md` / README 安全宪法里有几条硬约束：

1. **不分发 NVIDIA 固件**——`booter_*`、`fwimage_*`、`fwsignature_*`、`gsp_*`、`v67-*`、
   `scrubber_*` 一律不入库，由公开输入本地再生；
2. **读回是唯一成功判据**——不接受"状态码/返回值/屏幕提示"当证据；
3. **证据即提交**——他们的 `docs/evidence/<milestone>-<platform>/` 里放日志原文 + 结论；
4. 只读链式加载 ESP、不写 NVRAM、不做常驻引导项。

本仓库已经按这个纪律组织：只有日志、JSON、脚本和文档，没有任何固件（见 [README §不发布的内容](../README.md#不发布的内容)）。

## 我们这份材料能给上游什么

1. **`10de:2805` 的 EFI 全链实证**。上游矩阵里这一行目前是
   `4060Ti 2803 ✅ 实测；4060Ti 16G 2805 🟢 上游硅验证`。我们这次跑通了完整事务
   （`MAILBOX0=0x67b00001`、四写读回、选择器穿 FLR），可以把它升到 ✅，并补上
   ASUS 子系统 `1043:8921` 这个新板卡点。
2. **PR #5（Bridge BME）在这台机器上确属必需**。同一台机器白天采集到上游桥
   `command=0x0007`，解锁那次启动读到 `0x0003`；工具自动置位成 `0x0007` 后 booter 才成功。
   这是"该位的状态会随启动路径变化"的一个直接证据。
3. **Windows 侧端到端数据**（上游目前主要是寄存器/微基准层面）：稠密 bf16 工作流 +57%、
   量化+流式工作流 0%，以及 75 s 满载的功耗/温度曲线。

## 现成的 Issue 草稿（可直接粘贴）

> **标题**：AD106 4060 Ti 16G（`10de:2805` / ASUS `1043:8921`，Intel NUC13RNGi9）全链实测成功 + Windows 侧 GEMM/ComfyUI 数据
>
> **正文**
>
> 用 v2.1.0 在一张 ASUS RTX 4060 Ti 16 GB 上跑通完整事务，板卡与平台在该项目矩阵里此前只有
> 上游硅验证，这里补一个桌面平台的实证。完整报告、日志与测量脚本放在
> `<你的仓库链接>`（不含任何 NVIDIA 固件）。
>
> 环境：NUC13RNGi9 / BIOS `SBRPL579.0068.2026.0625.1114`；GPU `10de:2805`、子系统
> `1043:8921`、BDF `0000:01:00.0`、上游桥 `8086:a70d` @ `00:01.0`；VBIOS `95.06.25.00.d4`；
> 驱动 617.42；165 W；Secure Boot 关闭。
>
> 关键日志（`\loader.log`）：
>
> ```
> DMA-PATH[pre-fire]: bridge 8086:a70d command 0x0003
> BRIDGE-BME: Some((0,0,1,0)) command 0x0003 -> 0x0007
> BOOTER forensic: CPUCTL=0x00000010 MAILBOX0=0x67b00001
> POST-BOOT: FEAT_PLM=0xffffffff SS0=0x76111154 SS1=0x4
> POST-BOOT: WPRCFG=0xfffff0ff FBPA=0xffffff0f WPR=0xffffffff
> SELECTOR RESULT: SS0=0x88888888 SS1=0x8
> POST-FLR selectors: ss0=0x88888888 ss1=0x8
> FINAL: transaction complete, all DMA released
> HANDOFF-OUT: plm_open=true ss0_unlock=true ss1_unlock=true
> ```
>
> Windows 侧（同 boot，PyTorch 2.12.1+cu130、驱动 617.42）：
>
> | 模式 | 原厂 | 解锁 |
> | --- | ---: | ---: |
> | FP16→FP32 acc 8192³ | 45.78 | **75.24** TFLOPS |
> | BF16→FP32 acc 8192³ | 44.84 | 68.80 |
> | FP32 对照 4096² | 11.95 | 11.87（不变） |
> | 75 s 满载 | — | 75.9 TFLOPS / 156 W / 72 °C |
>
> ComfyUI 端到端（固定工作流，纯 bf16 13 GB 模型，1024²、12 步）：采样 **3.39 → 2.16 s/it（×1.57）**；
> 而 20 GB 流式 + W4A4/int8/fp8 量化的视频工作流 **0%**（预期，瓶颈在带宽）。
>
> 另外两个观察，供参考：
>
> 1. 上游桥 Bus Master 在本机**并非恒定**：同一天的只读采集读到 `0x0007`，解锁那次启动读到
>    `0x0003`，靠 loader 的 `BridgeMaster` 置位后 booter 才拿到 `MAILBOX0=0x67b00001`。
>    PR #5 在这个平台上不是可选项。
> 2. 本机控制台 GOP 被判为"不属于目标卡"（`GOP ... is not on the target GPU - left untouched`），
>    所以全程有屏、没有黑屏窗口；与笔记本单卡路径表现不同。
>
> 如果认可，我可以提 PR 把矩阵里 `4060Ti 16G 2805` 从 🟢 升到 ✅，并按
> `docs/evidence/` 的格式补一份报告与脱敏日志。

## 如果要提 PR，改动范围建议（最小化）

```
README.md                          # 兼容性矩阵那一行：2805 🟢 → ✅ 实测（链接到证据目录）
docs/evidence/ad106-2805-nuc13/
    report.md                      # 与我们仓库 docs/RESULTS.md 同结构，压缩到一页
    loader-unlock.log              # 脱敏（已去掉主机名/用户名/绝对路径）
    bench-before-after.json
```

不要动 loader 代码（我们没改过它），也不要带固件。PR 描述里引用本 Issue 编号即可。

### 补丁已经做好了

**当前状态（2026-10-28）**

| 项 | 链接 |
| --- | --- |
| 上游 Issue | [physicsdolphin/nv-uefi-unlocker#30](https://github.com/physicsdolphin/nv-uefi-unlocker/issues/30) |
| PR 分支（fork） | [`holykylin:report/ad106-2805-nuc13`](https://github.com/holykylin/nv-uefi-unlocker/tree/report/ad106-2805-nuc13) @ `e487e51` |
| 开 PR 的 compare 页面 | [compare/main...holykylin:report/ad106-2805-nuc13](https://github.com/physicsdolphin/nv-uefi-unlocker/compare/main...holykylin:report/ad106-2805-nuc13?expand=1) |

改动 3 个文件、+439/−2：`README.md` 矩阵一行，加 `docs/evidence/ad106-2805-nuc13/{report.md,loader-unlock.log}`。
基于上游 `main` @ `51bc8b4` 生成（`git apply --check` 通过），原始补丁与 Issue/PR 文案在
`../upstream-patch/`：

| 文件 | 用途 |
| --- | --- |
| `0001-evidence-AD106-...patch` | 可直接 `git am` 的提交：README 矩阵一行 + `docs/evidence/ad106-2805-nuc13/{report.md,loader-unlock.log}` |
| `issue-body.md` | 开 Issue 时直接粘贴 |
| `pr-body.md` | 开 PR 时直接粘贴 |
| `README.md` | fork → clone → `git am` → push → 开 PR 的完整命令 |

## 与上游 `tools/ssdiag`、`tools/diag-unlock.py` 的关系

上游在 2026-10-28 合并了"进系统后读 FEAT 簇"的工具（Linux 走 sysfs mmap，Windows 走
`pmxdrv.sys` 物理内存传输）。与本仓库 `scripts/check_unlock.py` 是互补的两条路：

| | 上游 ssdiag / diag-unlock.py | 本仓库 check_unlock.py |
| --- | --- | --- |
| 方式 | 读 `FEAT_PLM / SS0 / SS1` 寄存器 | 测 8192³ FP16→FP32 吞吐（功能判据） |
| 依赖 | Linux 需 root；Windows 需安装 Intel 签名的 `pmxdrv.sys` | 只要 PyTorch + CUDA，零驱动 |
| 额外能力 | 可在"门还开着"时**免重启重写** SS0/SS1 | 只判定，不写 |
| 用时 | 毫秒级 | 约 1 秒 |

两者可以互相校验：本机两态 45.8 / 75.2 TFLOPS 与寄存器判据（`SS0=0x88888888`）应当一致。
如果你的机器装不了那个驱动，用功能判据同样能确认"解锁有没有活着"。


## 为什么没有选 ZeroHackz 那份

`ZeroHackz/gpu-unlock-windows` 也支持 `10de:2805`，但它把 **Gigabyte 板卡**的值钉死在编译期：
全局子系统 `1458:4112`、`GU_BOARD_SUBSYSTEM 0x41121458`、PROM 视图哈希 `53715948…`。
我们的卡是 `1043:8921`，会在 `ConfigCheck`/`GuIsTarget` 阶段直接被拒；其 `assets.json` 与
EFI 内 `app_io.c` 的资产名/哈希也对不上（`booter_load_ga102` vs `booter_load_ad102`）。
按它的"未知配置"流程（把 pin 置零）虽然能跑，但等于放弃全部板卡校验，风险高于收益。

相反，`nv-uefi-unlocker` 按**芯片家族**路由、FWSEC 从卡自己的 VBIOS 现读现解析，
所以同一份二进制跨板卡可用——这正是我们这张 ASUS 卡能跑起来的原因。
