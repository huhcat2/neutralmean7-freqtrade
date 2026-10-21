# NeutralMean7 + Freqtrade

BTC/USDT 现货动态仓位研究策略与本地 Freqtrade 2026.9 源码快照。

## 内容

- `freqtrade/`：本地部署的框架源码，含上游许可证；来源见 `UPSTREAM.md`。
- `user_data/strategies/`：从校验通过的策略包安装的独立策略、冻结模型与历史状态种子。
- `release/`：NeutralMean7.qstrat、安装器、回测报告、图表、26 页 PPT 与讲解稿。
- `config.example.json`：无密钥的 BTC 单仓现货配置，默认 dry_run，初始状态 stopped。
- `requirements-tested.txt`：本机已安装依赖的版本记录；不含虚拟环境二进制。

## Windows 部署

安装 Python 3.13，然后在仓库根目录运行：

```powershell
./setup.ps1
Copy-Item config.example.json config.local.json
./.venv/Scripts/freqtrade.exe list-strategies --userdir ./user_data
```

安装脚本只准备环境与策略，不启动交易。Python 环境验证基于 Windows / Python 3.13.12，其他平台没有在此交付验证。
首次依赖安装需要网络和适配平台的安装包。

## 下载行情与回测

```powershell
./.venv/Scripts/freqtrade.exe download-data -c config.local.json --userdir ./user_data --timeframes 1h 5m --timerange 20220101-20261021
./.venv/Scripts/freqtrade.exe backtesting -c config.local.json --userdir ./user_data -s NeutralMean7Portable --timerange 20230101-20261020 --fee 0.0015
```

以上是部署后的常规命令示例，不声称与报告的分钟级终点完全相同。报告精确截止到 2026-10-20 07:00 UTC，另包含五分钟盯市和独立账本审计；参见 `release/验证与回测报告.md`。
压力情景使用 `NeutralMean7PortableLag2`，单边费用 0.003。
包内历史只用于指标状态，不替代 Freqtrade 标准行情文件。持续运行须保留 `user_data/neutralmean7_state/`；长时间断线需补齐历史。

## 策略与研究边界

仅 BTC 现货多头和现金，不加杠杆。冻结 Ridge 的最近七日得分均值与带 ±2% 缓冲的 MA48 趋势采用“或”逻辑，基础目标为 99.5% 或 25%。日频检查，至少一小时信息滞后；实际订单受现金、3 个百分点调仓阈值和冲击后禁止加仓等约束。

2023 年后的数据已用于反复研究，多起点窗口大量重叠，不能视为独立盲测。实现一致性不等于未来收益保证。详见报告与 PPT；PPT 文件保留交付版本，PDF 是此前完整版本，页数不同。

`.qstrat` 是本项目定义的校验 ZIP 格式，必须经随附安装器部署，非 Freqtrade 原生导入格式。
`release/校验清单.json` 是原始交付时的清单，后续精简 PPT/讲稿以本仓库根目录的 `UPLOAD_MANIFEST.json` 为准。

## 凭据与运行数据

仓库不含交易所密钥、GitHub 令牌、账户数据库、运行日志或虚拟环境。使用本机忽略的 `config.local.json` 管理私有配置，勿提交真实密钥。
