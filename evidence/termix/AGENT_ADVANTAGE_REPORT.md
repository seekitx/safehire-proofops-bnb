# SafeHire TermiX Agent Advantage Report

采集时间：2026-08-31 15:29（Asia/Shanghai）

公开市场：https://safehire-proofops-bnb.onrender.com

机器可核验报告：https://safehire-proofops-bnb.onrender.com/api/evidence/termix/report

## 结论

SafeHire 已在公开市场完成三次真实的零成本赞助雇佣，并把每次 Agent 返回、雇佣回执、不使用 Agent 的对照输出、开始/结束时间、成本、统一评分和 SHA-256 文件指纹保存下来。

这三题里，Agent 的优势不是速度：直接公式计算更快。可量化优势是输出质量总分 `73.5 / 75`，高于直接计算的 `66 / 75`。Agent 每次都额外提供统一格式、风险检查、来源标签、是否可执行的判断，以及可核验的市场雇佣回执。

## 三组结果

| 任务 | 类别 | Agent 耗时 | 不使用 Agent 耗时 | Agent 成本 | Agent / 对照质量 | 原始输出 |
|---|---|---:|---:|---:|---:|---|
| PancakeSwap grid route | Trading / Grid | 1.816 s | 0.000100 s | 0 U | 24.5 / 22.0 | [Agent](raw/pancakeswap-grid-route/agent-output.json) · [对照](raw/pancakeswap-grid-route/manual-output.json) |
| Venus stablecoin yield | Yield optimisation | 0.350 s | 0.000654 s | 0 U | 24.5 / 22.0 | [Agent](raw/venus-stablecoin-yield/agent-output.json) · [对照](raw/venus-stablecoin-yield/manual-output.json) |
| Venus health-factor response | Security / Health factor | 0.484 s | 0.000109 s | 0 U | 24.5 / 22.0 | [Agent](raw/venus-health-factor-response/agent-output.json) · [对照](raw/venus-health-factor-response/manual-output.json) |

精确时间和所有文件指纹以 [agent-advantage-report.json](agent-advantage-report.json) 为准。报告汇总将亚毫秒对照时间显示为 `0.000 s`，原始文件保留了更高精度。

## 比较方法

1. 两边读取同一份冻结任务 JSON。
2. Agent 侧调用公开 SafeHire A2A `hire_analysis`，完成一次赞助雇佣并写入 hash-chain 回执。
3. 对照侧不调用 SafeHire A2A 或任何市场 Agent，只按任务公开公式直接计算。
4. 两边真实费用都是零；没有虚构人工工资，也没有把赞助任务冒充付费订单。
5. 用正确性、完整性、风险意识、可操作性、证据质量五项规则评分，每项 0–5 分。

## 评分为什么不同

两边的核心数值一致，所以正确性都是 5 分。Agent 侧还返回标准化风险检查、来源标签、执行权限边界、置信度、调用编号和雇佣回执，因此在完整性、风险意识、可操作性与证据质量上更高。

这是公开规则下的自动评分，参赛者必须在最终提交前浏览原始输出并确认；它不是独立人类研究，也不声称统计显著性。

## 付费与链上边界

- 三次 TermiX 样本是零成本赞助雇佣，成本如实记录为 `0 U`。
- 它们没有连接钱包、授权代币、创建付费 Job 或移动资金。
- 独立的 BSC Testnet [ERC-8183 Job #808](../sponsor-integration/erc8183-job-808.json) 已证明 `0.1 U` 的创建、托管、交付、异议窗口、结算和提供方收款闭环；它不被冒充为这三次样本的付款。
- PancakeSwap 样本使用记录区块的真实只读报价，不是交易或利润承诺。
