# TermiX 三组真实对照执行手册

## 当前状态

历史自动化基线已通过公开 Agent 采集。它使用赞助雇佣、直接公式计算和自动评分，**不是真人对照实验，也不能把它称为已完成的冲奖最终报告**。历史文件位于：

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


## 2026-09-08 冲刺：真人实验执行入口

打开 `https://safehire.eyesonchain.xyz/benchmark`，优先完成网格、收益比较、借贷安全三题。每题均保留同一输入文件；代理和真人都用这份输入，不给其中一方额外提示。

1. 先记录本题数据日期、情景假设、任务编号，不能把历史利率当成今天的利率。健康题当前仍是明确披露的情景输入，补真实仓位前不宣称已保护用户资产。
2. 代理侧从市场取得结果，保留完整回执、原始输出、起止时间、币种和实际费用；外部付费流程缺签名时记录失败，不能拿赞助回执补成付款。
3. 真人侧填写真实操作者，开始计时后自行查资料、计算和写完整答案。填写实际工具、费用，主动确认没有调用市场代理后下载记录。不要让 Codex 代写这份对照答案。
4. 使用同任务两份输出制作评审包。页面去掉传输层身份信息，单独的私有映射文件保留原始记录；答案内容仍可能暴露来源，评审理由必须披露。不要上传私有映射文件到公开仓库。
5. 另一位评审逐项评分并说明理由，确认评分前未看到映射。用项目虚拟环境运行 `scripts/unblind_termix_review.py` 合并；合并工具核对任务编号、确认声明、分数范围，并重算总分。
6. 三题完成后更新报告。不能填预设分数或把工具自动记录的耗时改成人工节省时间。使用收益/风控分析服务就按分析服务展示，不编造交易胜率。

本轮补强的是实验工具与检查；截至本次代码交付，真人操作、独立评审、外部付费三题及正式提交仍未完成。独立盲评是增强证据的方法，不是官方额外资格门槛。
