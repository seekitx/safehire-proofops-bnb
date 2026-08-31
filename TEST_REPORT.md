# 验收报告

基线验证日期：2026-08-31（Asia/Shanghai）

## 结论

提交 `7e59aed` 已完成本地、GitHub Actions 和 Render 公网验证。本次
`judge-ready` ZIP 在该基线上新增 Judge Scorecard、十角色对抗门禁和交付工作流；
这些新增改动合入后尚未重新运行测试、构建、推送或生产部署，因此不能沿用旧结果宣称
“当前工作区已全部通过”。

项目已经有公开网站、公开 GitHub、BSC Testnet 合约、ERC-8004 身份和 ERC-8183
Job #808 完整结算证据。仍不能声称“已获奖”或“winner-ready”，因为外部主网付费
交付、真人盲评、第二运营方和最终参赛者提交仍需现实操作。

## 自动验证结果

| 范围 | 结果 | 证据 |
|---|---|---|
| Python 功能 | 基线通过 | `7e59aed` 的 65 个 pytest 测试全部通过；本次新增测试待运行 |
| Python 覆盖率 | 基线通过 | `7e59aed` 为 75.76%，门槛 75%；本次改动待复测 |
| Python 代码质量 | 通过 | Ruff 0 问题，Mypy 0 问题 |
| 静态安全扫描 | 通过 | 未发现已写入的私钥/API key |
| 前端 JavaScript | 基线通过 | 新增 Judge Scorecard JavaScript 尚未重新检查 |
| 真实浏览器 | 基线通过 | `/hire-live` 与 `/benchmark` 已检查；Judge Scorecard 待部署后验收 |
| Solidity | 通过 | Hardhat 编译通过，3 个合约测试通过 |
| Solidity 生产依赖 | 通过 | `npm audit --omit=dev` 为 0 漏洞 |
| BNB Agent Studio | 通过 | 官方 CLI 0.0.13 生成，TypeScript 构建通过 |
| Studio 生产依赖 | 通过 | `pnpm audit --prod` 无已知漏洞 |
| Studio → SafeHire | 通过 | `safehire_preview` 实际调用 HF Shield 并返回确定性结果 |
| BSC Testnet 读链 | 通过/可降级 | 官方 Studio doctor 确认网络可达；RPC 偶发失败时 UI 明确显示不可用，不伪造数据 |
| Docker | 基线通过 | `7e59aed` 镜像和 `/health/ready` 通过；本次改动待重建 |
| GitHub Actions | 基线通过 | Python、contracts、agent-studio 三个 job 对 `7e59aed` 全部成功 |
| Render | 基线通过 | `7e59aed` 显示 `Live`；本次工作区尚未推送和部署 |

Python 测试仅有一条来自 Starlette TestClient 的废弃提示；它不影响当前功能，但升级测试客户端时应跟进。

## 官方 Agent Studio doctor

已通过：

- `studio.toml` 可解析；
- A2A + MCP + X402 组合入口可构建；
- BSC Testnet 可达；
- ERC-8183 固定价格 0.1 U，最高价格同为 0.1 U；
- LLM 自动充值关闭；
- x402 正价模式为 0.01 USD。

预期警告（需用户外部资源）：没有一次性钱包、钱包密码、Pieverse key、IPFS 存储凭据、B402 商户凭据和云部署账号。

## 提交门禁

`7e59aed` 使用公开 URL 配置运行时，结果为 `ready=true`、31 项中 26 项通过、
`P0 blockers=0`。其余项目是明确标注的 demo Agent 未上链和可选视频，不是伪装成
完成的硬门槛。

本次新增 `scripts/judge_scorecard.py` 进一步把 Functionality、Data Quality 和 Agent
Diversity 分开输出，并保留以下人工门槛：

1. 第一笔外部主网付费交付；
2. 至少三项真人 no-Agent 计时和独立盲评；
3. 第二个独立 ERC-8004 运营方；
4. 评审期稳定托管、短视频和参赛者最终提交。

下一次验收必须重新运行 Python、合约、Agent Studio、Docker、submission gate 和 judge
scorecard，再更新本报告；不能把本节的基线结果自动套用到尚未验证的工作区。
