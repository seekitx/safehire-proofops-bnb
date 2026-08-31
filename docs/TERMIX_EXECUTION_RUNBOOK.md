# TermiX 三组真实对照执行手册

## 先说结论

三份固定任务已经放在 `evidence/termix/tasks/`。现在还不能直接花 U 跑，因为云端 Agent 必须先能访问公开的 SafeHire HTTPS 接口；电脑上的 `127.0.0.1` 对云端不可见。

完成顺序必须是：公开部署 SafeHire → 给 Agent 配置公开地址并重新部署 → 验证只读调用 → 三次真实下单 → 三次人工同题 → 独立评分 → 生成报告。

## 1. 发布前的硬门槛

1. SafeHire 站点有公开 HTTPS 地址，`POST /api/agents/<agent-id>/invoke` 可从外网访问。
2. Agent Studio 运行环境设置 `SAFEHIRE_API_BASE_URL=https://你的公开域名`。
3. 通过官方 `bag deploy --provider bnb` 或用户自有 AWS 重新部署；不能把本地 `.studio/wallets` 放进包。
4. 用一份不支付的本地/远程调用先确认 `safehire_preview` 能返回结果，再开始 ERC-8183 订单。
5. BNB 48 小时试用只适合临时采证，不能作为覆盖到评审结束的长期运行环境。

## 2. 三份固定任务

| 顺序 | 文件 | 类别 | 证明重点 |
|---|---|---|---|
| 1 | `evidence/termix/tasks/pancakeswap-grid-route.json` | 网格交易 | 用同区块 PancakeSwap 报价生成有边界的九档网格 |
| 2 | `evidence/termix/tasks/venus-stablecoin-yield.json` | 收益优化 | 区分 Venus API 实测值和公开的基准假设，做风险调整排序 |
| 3 | `evidence/termix/tasks/venus-health-factor-response.json` | 健康度监控 | 计算风险状态和恢复到目标健康度的还款量，不冒充真实账户 |

Job #808 只作为“缺少输入时安全拒绝”的补充证据，不算三组 Agent 优势主样本。

## 3. 每个 Agent 订单怎么跑

在 `agent-studio/safehireagents/app/agent` 目录中，为当前任务准备一个新的、已验签的报价：

```bash
SAFEHIRE_TASK_FILE=evidence/termix/tasks/<task-file>.json node scripts/prepare-remote-quote.mjs
```

脚本会把任务文件路径和 SHA-256 文件指纹一起保存到 `.data/erc8183/browser-plan.json`。然后打开 `/hire-agent`，由测试钱包逐笔确认创建、登记预算、授权 U、充值等交易。任何交易都必须在钱包里看清网络、合约和金额后由用户确认。

资金到账后，用新 Job 编号通知 Agent：

```bash
SAFEHIRE_JOB_ID=<job-id> \
CONFIRM_NOTIFY_FUNDED=JOB_<job-id>_BSC_TESTNET \
node scripts/notify-funded.mjs
```

时间与成本按下面规则记录：

- Agent 开始时间：`fund` 交易所在区块时间；
- Agent 结束时间：`submitResult` 交易所在区块时间；
- Agent 成本：实际 `0.1 U`，同时在 `cost_usd` 记录当时用于汇总的美元估值；
- 原始输出：保存链上 deliverable URL 返回的原文，不做润色；
- 交易哈希、Job ID、任务文件 SHA-256 一起保存。

## 4. 人工同题怎么跑

1. 人工操作者只能看到与 Agent 完全相同的任务 JSON；不能给额外提示。
2. 开始前记录带时区的时间，完成后立即记录结束时间。
3. 保存完整人工过程和最终答案，允许使用浏览器与普通计算器，但不能调用 SafeHire Agent。
4. 人工成本只记录真实工具费用；不要为了让 Agent 显得便宜而虚构人工工资。

## 5. 独立评分和报告

复核人不能是 Agent 输出或人工输出的作者。每一方按正确性、完整性、风险意识、可操作性、证据质量分别打 0–5 分，并留下姓名或可识别的复核人标签。

复制并填写模板：

```bash
cp templates/termix/live-manifest.template.json evidence/termix/live-manifest.json
PYTHONPATH=src python scripts/build_termix_report.py evidence/termix/live-manifest.json
```

生成器会拒绝下面这些无效材料：少于三题、缺原始文件、时间倒置、fixture/demo 路径、占位复核人、全零评分、越出项目目录的文件路径。

## 6. 不能夸大的地方

- Venus 官方说明 API 是索引数据，可能落后链上；报告必须保留这个限制。
- PancakeSwap 报价是记录区块上的只读比较，不是成交，也不包含之后的价格变化和真实 gas。
- `U` 是 Agent Studio 测试支付代币，不是测试网 USDT/USDC。
- 三次支付成功只证明商业流程成立；只有同题人工对照、原始输出和独立评分齐全，才能声称 TermiX Agent Advantage。
