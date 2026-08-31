# TermiX 三组真实对照执行手册

## 当前状态

三组 live 对照已经在 2026-08-31 通过公开 Render Agent 完成，最终报告位于：

- `evidence/termix/agent-advantage-report.json`
- `evidence/termix/AGENT_ADVANTAGE_REPORT.md`
- `https://safehire-proofops-bnb.onrender.com/api/evidence/termix/report`

官方硬要求是至少三个真实任务，每题分别用“通过市场雇佣 Agent”和“不使用 Agent”完成，报告时间、成本、输出质量与实际输出；至少一题属于 trading、stock/equities 或 security。官方没有公开规定三题必须付费、必须上链结算或必须由独立人类评分。

## 本次怎么执行

| 任务 | 类别 | Agent 路径 | 对照路径 |
|---|---|---|---|
| `pancakeswap-grid-route` | trading / grid | 公开 A2A `hire_analysis` 赞助雇佣 | 同输入直接计算九档几何网格 |
| `venus-stablecoin-yield` | yield optimisation | 公开 A2A `hire_analysis` 赞助雇佣 | 同输入直接计算净收益与风险调整排序 |
| `venus-health-factor-response` | security / health factor | 公开 A2A `hire_analysis` 赞助雇佣 | 同输入直接计算健康因子和目标还款额 |

Agent 侧每次都返回完整结果和 hash-chain 雇佣回执。对照侧不调用 `/a2a`、`/api/agents` 或其他市场 Agent。两边实际成本都是零，不虚构人工工资。

## 重新采集

先确认公开端点已部署最新代码并含 `hire_analysis`：

```bash
curl --fail https://safehire-proofops-bnb.onrender.com/.well-known/agent-card.json
```

再执行：

```bash
PYTHONPATH=src python scripts/capture_termix_live_comparisons.py \
  --public-base-url https://safehire-proofops-bnb.onrender.com
```

脚本会覆盖 `evidence/termix/raw/`、`live-manifest.json` 和 `agent-advantage-report.json`。每次重新采集后都要提交新文件并重新部署，让公开证据页与 GitHub 同步。

## 评分和人工复核

五项规则是正确性、完整性、风险意识、可操作性、证据质量，每项 0–5 分。当前分数由公开固定规则生成，参赛者必须在正式提交前逐个打开六份原始输出并确认。

如果参赛者不接受某个分数，应修改清单和理由后重新生成；不能为了好看直接提高分数，也不能把自动评分写成“独立人类研究”。

## 不能夸大的地方

- 这三次是零成本赞助雇佣，不是 `0.1 U` 付费 ERC-8183 订单。
- Job #808 单独证明一次完整的 `0.1 U` 付费闭环，不算三组样本的付款。
- 直接公式计算在这三题更快，因此报告不声称 Agent 节省时间；优势在统一风险检查、来源、执行边界和雇佣回执。
- PancakeSwap 使用记录区块的真实只读报价，不是成交，也不包含之后的价格变化、gas 或真实滑点。
- Venus API 是索引数据，可能落后链上；健康因子题是披露过的基准情景，不冒充真实账户。
- `U` 是 Agent Studio 支付代币，不是测试网 USDT 或 USDC。
