# Evidence index

四份 `loader.log` 来自四类启动，均为 UEFI 应用写在本机 U 盘根的原始日志；`*.json` 是
Windows 侧测量脚本的输出。**为了不泄露设备指纹，做过两处最小化脱敏**（不改变任何结论）：

| 改动 | 位置 | 原因 |
| --- | --- | --- |
| `host` 字段：主机名 → `NUC13RNGi9` | `bench_*.json`、`stress_unlocked.json` | 去掉个人机器名 |
| `SAMPLE NV_PROM ... crc32 0x…` → `crc32 <redacted>` | 四份 `loader_*.log` 第 130 行 | VBIOS 指纹，作者选择不公开 |

除此之外未做任何编辑：日志里的 PCI 拓扑、寄存器值、BADF 分类、事务判据都是原样。
`docs/HARDWARE.md` 里 PCI ROM / PROM 的三类 SHA-256 同样替换成"作者未公开"。

| 文件 | 场景 | 结论 |
| --- | --- | --- |
| `loader_run01_readonly.log` | 只读启动（30 s 超时未确认） | 零写入；枚举/GOP/寄存器采样全绿；链回 Windows |
| `loader_run02_unlock.log` | 手动按空格解锁 | `MAILBOX0=0x67b00001`、四写读回、选择器穿 FLR |
| `loader_run03_armed.log` | 武装模式（5 s 倒计时） | 与 run02 一致，复测 75.17 TFLOPS |
| `loader_run04_hibernate_resume.log` | 休眠唤醒后 | 固件重新 POST → 再跑一轮 → 解锁存活，72.57 TFLOPS |
| `bench_stock_before_unlock.json` | 原厂基线 | 8192³ FP16→FP32 = 45.78 |
| `bench_unlocked_after_unlock.json` | 首次解锁后 | 75.24 |
| `bench_armed_run03.json` | 武装模式那次 | 75.17 |
| `bench_hibernate_resume.json` | 休眠唤醒后 | 72.57 |
| `bench_stock_verify.json` | 拔 U 盘回原厂复核 | 45.65 |
| `stress_unlocked.json` | 75 s 满载 | 中位 75.88 TFLOPS / 156 W / 72 °C |
| `comfy_*.json` | ComfyUI 解锁侧（a1–a3）与原厂侧（b1–b2） | 见 `comfy_ab_summary.json` |
