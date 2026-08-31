# SafeHire / ProofOps 黑客松提交就绪度复核

复核日期：2026-08-31（Asia/Shanghai）

## 结论

**SafeHire 现在已经可以填写并作为 `Working MVP` 提交主赛，但还不应该称为“最终冲奖版”。**

原因是：公开网站、公开 GitHub、四类 BSC 主网 Agent 发现、ERC-8004 身份、ERC-8183 完整测试网雇佣回执和 PancakeSwap 真实主网报价都已经有公开证据；但当前页面上的四个真实 Agent 只能发现和查身份，不能在它们的卡片上直接雇佣，而官方主赛明确把“发现、理解、激活/雇佣”的完整路径列为 Functionality 评审核心。[BNB Chain 官方赛事页：Main Track 与评审标准](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

按奖项分开看：

- **主赛：可以交 MVP，但竞争力还差两个关键闭环。**四类真实 BSC Agent 已在线，但真实 Agent 直接激活/雇佣路径、以及能帮用户作出雇佣决策的真实质量/历史数据仍偏弱。
- **TermiX：现在不具备资格，不应在最终提交时勾选。**官方把 Agent Advantage Report 写成资格材料；当前仓库只有三份任务和报告模板，没有三组真实 Agent/人工同题输出与最终报告。[BNB Chain 官方赛事页：TermiX Required Report](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)
- **PancakeSwap：已经有真实、可量化的候选证据，但还不是强冲奖证据。**现有同区块 QuoterV2 报告证明了选择费率池可令 `0.1 WBNB` 报价改善 `0.042343798536122283 USDT`（`6.0244 bps`），但它是只读脚本产出，尚未与一份已验证的真实雇佣 Agent 交付物绑定。官方要求的是“Agent 给 PancakeSwap 交易者或 LP 带来真实收益”，没有要求必须真实下单，但证明是 Agent 产出会更有说服力。[BNB Chain 官方赛事页：PancakeSwap Challenge](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

## 能不能现在填表

**可以现在打开官方表单并把信息填完；如果这次提交要当作最终版，建议暂时不要按最后的 Submit。**

官方当前唯一公开入口仍是 `Build the Era Hackathon Registration` Google Form，表单自身写明构建期于 **2026-09-09 12:00 UTC** 结束，即北京时间 **2026-09-09 20:00**；评审期为 9 月 9 日至 9 月 23 日。[BNB Chain 官方提交表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form) [BNB Chain 官方发布文章：How to Enter](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

表单已经能填入当前项目材料：

| 表单项 | 当前内容 | 就绪度 |
|---|---|---|
| Project Name | `SafeHire / ProofOps` | 已就绪 |
| One-Line Pitch | `Compare proof, limit permissions, and hire BNB Chain DeFi agents with verifiable on-chain receipts.` | 已就绪 |
| Project Description | 现有英文版 686 字符，低于表单 800 字符上限 | 已就绪 |
| Prototype Stage | `Working MVP` | 已就绪 |
| GitHub | [seekitx/safehire-proofops-bnb](https://github.com/seekitx/safehire-proofops-bnb) | 已就绪 |
| Public marketplace | [safehire-proofops-bnb.onrender.com](https://safehire-proofops-bnb.onrender.com) | 已就绪 |
| Proof dossier | [Public on-chain proof](https://safehire-proofops-bnb.onrender.com/proof) | 已就绪 |
| 个人身份和领奖信息 | 姓名、邮箱、Telegram、X、国家/时区、团队、领奖钱包、条款接受 | 必须由参赛者核对 |

官方表单没有公开承诺“提交后一定可以修改”，而且 TermiX 与 PancakeSwap 是在同一份表单里选择的。因此在距截止时间还有余量的情况下，最稳妥的做法是先把表单文案和个人信息备齐，等下面三项关键证据完成后再正式提交。

## 官方要求与现有证据

### 1. 主赛硬性资格

官方列出的资格是：全球个人或团队可参加，每队一个作品，作品在评审期功能正常并公开可访问，市场展示的 Agent 必须真实在 BSC 上运行。[BNB Chain 官方赛事页：Eligibility](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

| 要求 | 2026-08-31 实际核对 | 判定 |
|---|---|---|
| 公开可访问 | 首页和 `/proof` 都实际返回 HTTP 200；`/health/ready` 返回 `status=ready` | 通过，但 Render 免费实例可能冷启动 |
| 公开代码 | GitHub API 回读 `private=false` 且 `visibility=public` | 通过 |
| 四类 Agent | `/api/live-market` 当场回读调仓、网格、收益、健康因子四类 Agent，全部 `currently_callable=true` | 通过“身份和可发现性”，未验证交付质量 |
| 真实 BSC 身份 | 四个外部 Agent 都有 BSC mainnet ERC-8004 ID 和注册交易；SafeHire 自有 Agent #2032 在 BSC Testnet 完成 owner/wallet/URI 回读 | 通过身份证据 |
| 评审期持续运行 | Render 公开 Agent Card/A2A 无试用到期时间，但只有发现、证据读取和确定性预览；真实 ERC-8183 卖方仍是 BNB 48 小时试用 | 部分通过；真实雇佣运行时不覆盖评审期 |

本次实际访问的公开证据：[Marketplace](https://safehire-proofops-bnb.onrender.com) · [Proof dossier](https://safehire-proofops-bnb.onrender.com/proof) · [Agent Card](https://safehire-proofops-bnb.onrender.com/.well-known/agent-card.json) · [Submission gate](https://safehire-proofops-bnb.onrender.com/api/submission/validate) · [Live BSC catalog](https://safehire-proofops-bnb.onrender.com/api/live-market) · [GitHub](https://github.com/seekitx/safehire-proofops-bnb)。

### 2. 主赛评分面

官方按 Functionality、Data Quality、Agent Diversity 评分，但当前没有公布三项的数字权重。[BNB Chain 官方赛事页：How You're Judged](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

| 评分项 | 现状 | 竞赛判定 |
|---|---|---|
| Functionality | 已能打开市场、发现四类真实 Agent、查身份/交易，且 Job #808 有完整雇佣历史；但真实 Agent 卡片只有身份链接，没有当前可用的直接雇佣按钮 | **黄色**：有 MVP，评委重走完整路径时会碰到断点 |
| Data Quality | 四个真实 Agent 有身份、技能、当前价格和可调用状态；交付质量和历史表现没有实测。页面下半部的比较指标来自明确标注的 demo fixture | **黄色偏红**：诚实，但尚不足以让用户强确信地决定雇谁 |
| Agent Diversity | 四类真实 BSC Agent 以相同卡片深度展示，并有对应技能 | **绿色** |

### 3. TermiX 资格

官方要求至少三项真实任务，每项都要用“通过市场雇佣 Agent”和“不用 Agent”两种方式做一次，记录时间、成本、质量并附完整输出，且至少一项属于交易、股票或安全。该报告占 Proven Agent Advantage 的 30% 分数，并被官方明确写为 eligibility 材料。[BNB Chain 官方赛事页：TermiX](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [BNB Chain 官方发布文章：Partner Tracks](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

当前仓库状态：

- [三份固定任务](../evidence/termix/tasks/) 已存在；
- [TermiX 执行手册](TERMIX_EXECUTION_RUNBOOK.md) 和 [live manifest 模板](../templates/termix/live-manifest.template.json) 已存在；
- `evidence/termix/raw/`、`live-manifest.json` 和 `agent-advantage-report.json` 不存在；
- 公开 [submission gate](https://safehire-proofops-bnb.onrender.com/api/submission/validate) 也明确返回 `termix_live_advantage_report=false`。

因此 TermiX 当前是**硬性未达标**，不是“有报告模板就算完成”。

### 4. PancakeSwap 资格

官方没有公布固定报告格式、数字评分表或“必须真实下单”的要求；要求是 Agent 为 PancakeSwap 交易者或 LP 带来真实利益，示例包括更聪明的流动性管理、寻找更好收益、研究新池需求、安全自动交换。[BNB Chain 官方赛事页：PancakeSwap](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [PancakeSwap 开发者门户](https://developer.pancakeswap.finance/)

现有 [PancakeSwap 真实收益报告](../evidence/pancakeswap/live-benefit-report.json) 包含：

- BSC mainnet 区块 `118995462`；
- PancakeSwap V3 Factory 和 QuoterV2 官方合约地址；
- 同一区块的四个 WBNB/USDT 直连费率池报价；
- 相比 `0.05%` 基准池，`0.01%` 池的只读报价提高 `0.042343798536122283 USDT`，即 `6.0244 bps`；
- 明确声明这不是交易、不是利润承诺，也不包含真实 gas 和后续价格变化。

这已经比合成数据强，也能证明一个实际的交易者改善量。但最稳妥的冲奖证据应再补一步：让真实可雇佣 Agent 在交付物中产出或使用这个决策，保留原始输出、Job ID、成本和时间。

## 最终提交前的三个必做项

1. **把真实 Agent 的“发现”接到“雇佣”。**评委从真实 Agent 卡片出发，应能直接进入任务输入、报价、钱包确认和交付查看；不能只把历史 Job #808 当成当前功能。
2. **完成三组 TermiX 真实对照并公开报告。**每题保留 Agent/人工完整输出、时间、实际成本和同一质量标准；至少一题是 trading/security。
3. **把 PancakeSwap 报告绑定到一次真实 Agent 交付，并在提交前刷新数据。**在 README 和 Additional Notes 给出原始输出、区块、改善量和风险边界。

另有两个运营上的必要复查：在截止前 48 小时重新刷新四个外部 Agent 的 ERC-8004/A2A 存活证据；从无登录新浏览器打开所有公开链接，并确保 Render 服务在 9 月 9 日至 9 月 23 日的评审期可用。

## 证据边界

- 公开 SafeHire submission gate 当前返回 `ready=true` 、`25/31` 通过且 `P0 blockers=0`；这只是项目自己的证据结构门禁，不是 BNB Chain 官方给出的资格认证。[SafeHire public submission gate](https://safehire-proofops-bnb.onrender.com/api/submission/validate)
- Job #808 证明 BSC Testnet 上 `create → register → budget → approve → fund → submit → settle` 的 0.1 U 闭环曾经完成；它不能证明四个外部 Agent 都已被雇佣或评委现在仍能完成同样路径。[SafeHire public proof](https://safehire-proofops-bnb.onrender.com/api/public-proof)
- Render 公开 Agent Card 是长期的只读市场助手；它明示的技能是 `list_live_agents`、`preview`、`public_proof`，并不是长期 ERC-8183 签名卖方。[SafeHire public Agent Card](https://safehire-proofops-bnb.onrender.com/.well-known/agent-card.json)
- 本报告只进行官网、公开 API、公开 GitHub 和仓库文件的只读核对；没有运行构建、测试、部署、钱包交易或提交表单。

## 一手来源

- [The Smart Money Era 官方赛事页](https://www.bnbchain.org/en/hackathons/smart-money-era)
- [BNB Chain 官方发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)
- [Build the Era 官方报名/提交表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)
- [PancakeSwap Developer Portal](https://developer.pancakeswap.finance/)

