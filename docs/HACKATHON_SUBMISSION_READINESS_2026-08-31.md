# SafeHire / ProofOps 黑客松提交就绪度复核

> 状态说明：这是 2026-08-31 较早时的缺口快照，后续已经补齐公开实时报价、三组 TermiX live 对照和 PancakeSwap Agent 交付绑定。当前结论以 `HACKATHON_FINAL_SUBMISSION_CHECKLIST_2026-08-31.md`、`evidence/termix/agent-advantage-report.json` 和公开 `/proof` 页为准。

复核日期：2026-08-31（Asia/Shanghai）

## 结论

**SafeHire 的比赛内容已经达到正式提交前一步，可以作为 `Working MVP` 勾选主赛、TermiX 和 PancakeSwap。**

公开网站、公开 GitHub、四类 BSC 主网 Agent 发现、实时报价、ERC-8004 身份、ERC-8183 完整测试网雇佣回执、三组 TermiX live 对照和 PancakeSwap 主网只读报价均有公开证据。当前外部 Agent 路径会停在实时报价，不代替用户执行主网钱包付款；付费可行性由 Job #808 的完整测试网闭环单独证明。[BNB Chain 官方赛事页：Main Track 与评审标准](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

按奖项分开看：

- **主赛：可以交 Working MVP。**四类真实 BSC Agent 已在线并能返回当前报价；外部质量/历史数据仍是可继续加分的方向，不冒充已验证成绩。
- **TermiX：资格材料已完成，建议勾选。**三组公开赞助雇佣与不使用 Agent 的同题对照、完整输出、耗时、真实零成本、质量评分和文件指纹均已公开。[BNB Chain 官方赛事页：TermiX Required Report](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)
- **PancakeSwap：建议勾选。**最新同区块 QuoterV2 报告证明 `0.01%` 池相对 `0.05%` 基线改善 `0.003880692718573066 USDT`（`0.5652 bps`），并已绑定一次公开 Agent 交付。它仍只声称报价改善，不声称成交或利润。[BNB Chain 官方赛事页：PancakeSwap Challenge](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

## 能不能现在填表

**可以现在打开官方表单并把信息填完；如果这次提交要当作最终版，建议暂时不要按最后的 Submit。**

官方当前唯一公开入口仍是 `Build the Era Hackathon Registration` Google Form，表单自身写明构建期于 **2026-09-09 12:00 UTC** 结束，即北京时间 **2026-09-09 20:00**；评审期为 9 月 9 日至 9 月 23 日。[BNB Chain 官方提交表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form) [BNB Chain 官方发布文章：How to Enter](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

表单已经能填入当前项目材料：

| 表单项 | 当前内容 | 就绪度 |
|---|---|---|
| Project Name | `SafeHire / ProofOps` | 已就绪 |
| One-Line Pitch | `Compare proof, limit permissions, and hire BNB Chain DeFi agents with verifiable on-chain receipts.` | 已就绪 |
| Project Description | 现有英文版 766 字符，低于表单 800 字符上限 | 已就绪 |
| Prototype Stage | `Working MVP` | 已就绪 |
| GitHub | [seekitx/safehire-proofops-bnb](https://github.com/seekitx/safehire-proofops-bnb) | 已就绪 |
| Public marketplace | [safehire-proofops-bnb.onrender.com](https://safehire-proofops-bnb.onrender.com) | 已就绪 |
| Proof dossier | [Public on-chain proof](https://safehire-proofops-bnb.onrender.com/proof) | 已就绪 |
| 个人身份和领奖信息 | 姓名、邮箱、Telegram、X、国家/时区、团队、领奖钱包、条款接受 | 必须由参赛者核对 |

官方表单没有公开承诺“提交后一定可以修改”。比赛证据已经补齐；现在只等待参赛者复核自动评分、补个人信息、核对领奖钱包并亲自接受条款和提交。

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

- [三份固定任务](../evidence/termix/tasks/) 和六份实际原始输出已存在；
- [TermiX 执行手册](TERMIX_EXECUTION_RUNBOOK.md)、`live-manifest.json` 和 [Agent Advantage Report](../evidence/termix/AGENT_ADVANTAGE_REPORT.md) 已存在；
- 公开 [submission gate](https://safehire-proofops-bnb.onrender.com/api/submission/validate) 返回 `termix_live_advantage_report=true`。

因此 TermiX 的公开资格材料已经完成。自动评分仍要由参赛者人工浏览确认，报告不冒充独立人类研究，也不声称节省时间。

### 4. PancakeSwap 资格

官方没有公布固定报告格式、数字评分表或“必须真实下单”的要求；要求是 Agent 为 PancakeSwap 交易者或 LP 带来真实利益，示例包括更聪明的流动性管理、寻找更好收益、研究新池需求、安全自动交换。[BNB Chain 官方赛事页：PancakeSwap](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [PancakeSwap 开发者门户](https://developer.pancakeswap.finance/)

现有 [PancakeSwap 真实收益报告](../evidence/pancakeswap/live-benefit-report.json) 包含：

- BSC mainnet 区块 `119108691`；
- PancakeSwap V3 Factory 和 QuoterV2 官方合约地址；
- 同一区块的四个 WBNB/USDT 直连费率池报价；
- 相比 `0.05%` 基准池，`0.01%` 池的只读报价提高 `0.003880692718573066 USDT`，即 `0.5652 bps`；
- 公开 Agent 调用 `inv_20260831070737081187` 使用同一区块输入生成交付；
- 明确声明这不是交易、不是利润承诺，也不包含真实 gas 和后续价格变化。

这已经证明一次公开 Agent 对真实 PancakeSwap 主网报价的可量化路线帮助，同时保留“不是真实交易或利润”的边界。

## 最终提交前的三个必做项

1. **参赛者浏览六份 TermiX 原始输出。**确认自动评分和“零成本赞助雇佣、没有时间优势”的公开边界可以接受。
2. **用无登录窗口走一遍评委路径。**从四类 Agent、实时报价、SafeHire 交付到 `/proof` 和 GitHub，确认所有链接能打开。
3. **参赛者补齐个人字段并亲自提交。**重点复核领奖钱包首尾、联系方式、团队、条款和 TermiX/PancakeSwap 勾选。

另有两个运营上的必要复查：在截止前 48 小时重新刷新四个外部 Agent 的 ERC-8004/A2A 存活证据；从无登录新浏览器打开所有公开链接，并确保 Render 服务在 9 月 9 日至 9 月 23 日的评审期可用。

## 证据边界

- SafeHire submission gate 本次执行返回 `ready=true`、`26/31` 通过、`P0 blockers=0` 且没有伙伴奖缺口；这只是项目自己的证据结构门禁，不是 BNB Chain 官方给出的资格认证。[SafeHire public submission gate](https://safehire-proofops-bnb.onrender.com/api/submission/validate)
- Job #808 证明 BSC Testnet 上 `create → register → budget → approve → fund → submit → settle` 的 0.1 U 闭环曾经完成；它不能证明四个外部 Agent 都已被雇佣或评委现在仍能完成同样路径。[SafeHire public proof](https://safehire-proofops-bnb.onrender.com/api/public-proof)
- Render 公开 Agent Card 是长期市场助手；它明示 `list_live_agents`、`preview`、`hire_analysis` 和 `public_proof`。`hire_analysis` 是赞助雇佣，不是长期 ERC-8183 签名卖方。[SafeHire public Agent Card](https://safehire-proofops-bnb.onrender.com/.well-known/agent-card.json)
- 后续执行已完成公开部署和远程 CI；没有新增钱包交易，也没有提交官方表单。

## 一手来源

- [The Smart Money Era 官方赛事页](https://www.bnbchain.org/en/hackathons/smart-money-era)
- [BNB Chain 官方发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)
- [Build the Era 官方报名/提交表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)
- [PancakeSwap Developer Portal](https://developer.pancakeswap.finance/)
