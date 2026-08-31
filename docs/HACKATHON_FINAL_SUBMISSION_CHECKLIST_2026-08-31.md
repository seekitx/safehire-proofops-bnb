# SafeHire / ProofOps 最终提交前清单（2026-08-31）

> 用途：这不是“已提交”证明，而是点击官方表单 `Submit` 之前的最后门禁。
> 核对时间：2026-08-31（Asia/Shanghai）。比赛规则可能继续更新，正式提交当天仍要重新打开官方页和表单。
> 事实来源只使用 BNB Chain 官方赛事页、官方文章、赛事页链接的官方 Google Form，以及 PancakeSwap 官方开发者资料。仓库文件只用来标记 SafeHire 当前证据状态，不被当成比赛规则。

## 先说结论

**比赛内容已经推进到正式提交前一步。**TermiX 三组 live 对照、PancakeSwap 最新同区块数据与 Agent 交付绑定、公开市场、GitHub、链上证据和提交文案均已完成。现在只剩参赛者本人处理的最后门禁：

1. 浏览三组 TermiX 原始输出，确认接受公开的自动评分和“零成本赞助雇佣、不声称节省时间”的边界。
2. 补齐官方表单中的姓名、联系方式、国家/时区、团队信息、领奖钱包，并按真实情况选择经验、技能和可参与时间。
3. 亲自阅读并决定是否接受参赛条款，最终点击 `Submit`；当前公开表单没有保证提交后可修改，因此第一次提交应当视为最终版。

官方表单的公开页面**没有承诺提交后可修改**。本次没有用假资料试投，因此无法确认提交后是否会出现编辑链接。最安全的做法是：**把第一次提交当作最终提交，不要先交半成品占位。**

## 1. 截止时间和公开期要求

| 事项 | 官方当前信息 | 提交前动作 |
|---|---|---|
| 构建/提交截止 | **2026-09-09 12:00 UTC** | 北京时间是 **2026-09-09 20:00**；不要把“9 月 9 日”理解成北京时间当天 24:00。 |
| 评审期 | 2026-09-09 至 2026-09-23 | 公开站点、GitHub 和 Agent 在评审期不能下线或改成私有。 |
| 获奖公布 | 2026-11-05 | 保持表单中邮箱、Telegram/X 可联系。 |

精确到 `12:00 UTC` 的时间来自当前官方 Google Form 页首；赛事页和官方文章只写了 `Aug 5 - Sep 9`。以更精确的表单时间为提交门禁。

官方来源：[The Smart Money Era 赛事页](https://www.bnbchain.org/en/hackathons/smart-money-era) · [BNB Chain 官方发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace) · [Build the Era 官方表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)

## 2. 主赛最终复核

官方要的是 **BNB Chain Agent 市场**，不是只展示一个自家 Agent。参赛作品必须在评审期间能公开访问，市场里展示的 Agent 必须 live on BSC（真实在 BSC 上存在/运行）。官方还规定每个团队只能交一个作品。

| 评分项 | 官方要求（大白话） | SafeHire 最后验收动作 |
|---|---|---|
| **Functionality** | 从进入市场、按类别找到 Agent、理解能做什么，到真正启用/雇佣，全程要走通；不懂 Agent Studio 的人也不能遇到死路。 | [ ] 用无登录浏览器从首页重走一遍“找到→理解→启用/雇佣→看到结果/回执”；[ ] 四类真实 Agent 不能只有身份链接而没有可用的下一步。 |
| **Data Quality** | 数据必须实时、准确，不能只是 Agent 数量等简单统计；用户看完要真的能判断该雇谁。 | [ ] 每张真实 Agent 卡都有来源、观测时间/区块、能力、价格、可用状态和可复核的表现证据；[ ] demo/fixture 始终明标，官方数据失败时不偷换成演示数据。 |
| **Agent Diversity** | Rebalancing、Grid Trading、Yield Optimisation、Health Factor Monitoring 四类必须同等深度；只主做一类、其他三类陪衬会得低分。 | [ ] 四类都有真实 BSC Agent、同级的证据字段、同级的比较维度和可执行下一步；[ ] 不把其中三类降成仅有标题和一句话。 |

**不要伪造数字权重。**官方页当前列出这三个标准，但没有给主赛三项公开的数字权重；而且官方明说第二阶段还会考察更多标准，这些新标准截至本次核对尚未公布。

官方来源：[赛事页 Main Track、How You're Judged 与 Eligibility](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

## 3. TermiX：三组真实 Agent vs 人工对照

TermiX 不要求产品接入 TermiX API。它要判断的是：“通过这个市场雇佣/使用 Agent，是不是真的比不用 Agent 更好？”官方明确把 **Agent Advantage Report** 写成参奖资格材料。

### 3.1 不可缺少的官方条件

- [ ] 至少 **3 个真实任务**。
- [ ] 每个任务都跑两遍：一遍是通过 SafeHire 雇佣 Agent，一遍是不用 Agent 完成。“不用 Agent”是官方用词，在本项目里对应记录清楚的人工流程。
- [ ] 每组都报告 **耗时、成本、输出质量**，并附上 Agent 和人工的**完整实际输出**。
- [ ] 至少一个任务来自 **trading、stock/equities 或 security**。
- [ ] 最终 Agent Advantage Report 从 GitHub README 或 Additional Notes 中可公开打开。

**付费/链上边界：**官方原文要求 Agent 是 `hired through your marketplace`，并要求报告实际 cost；但资格条款没有明确写每个对照任务都必须付费、必须链下单或必须链上结算。因此必须如实记录成本（包括真实为零时说明为什么），但不能把 SafeHire 选择做的 `0.1 U`/ERC-8183 支付扩大为 TermiX 公布的普遍硬门槛。

### 3.2 SafeHire 已固定的三组任务

| # | 同题任务 | Agent 侧要保存 | 人工侧要保存 | 现状 |
|---|---|---|---|---|
| 1 | `pancakeswap-grid-route` | 公开赞助雇佣记录、原始输出、开始/结束时间、0 U 成本 | 同一任务文件、直接计算完整输出、开始/结束时间、0 USD 成本 | **已完成** |
| 2 | `venus-stablecoin-yield` | 同上 | 同上 | **已完成** |
| 3 | `venus-health-factor-response` | 同上 | 同上 | **已完成** |

为了让比较可信，Agent 和人工必须看同一份冻结输入，用同一套标准评分，评分人不应是两份输出的作者。这是为了将官方要的“measured, not asserted”做成可复核证据；**官方没有要求 human/manual 一侧必须由某种身份的人完成，也没有要求独立 reviewer**。同一评分细则和独立评分人是 SafeHire 自己的证据方案，不是官方公布的固定报告格式。

**本次执行更新：**`evidence/termix/raw/`、`live-manifest.json` 和最终 live Agent Advantage Report 均已生成。三次 Agent 侧都通过公开市场 A2A 完成零成本赞助雇佣并取得 hash-chain 回执；对照侧不调用市场 Agent。可以在表单勾选 TermiX，但必须保留“自动评分待参赛者浏览、不是人类研究、没有时间优势、样本没有付费”的真实边界。

TermiX 公布的独立评分是：服务价值 30%、可证明 Agent 优势 30%、高风险类别和历史记录 20%、市场质量 20%。交易 Agent 还应有真实记录，包括胜率、统计窗口和为取得结果承担的风险。

官方来源：[赛事页 TermiX Challenge 与 Required Agent Advantage Report](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) · [BNB Chain 官方文章 TermiX 概述](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

## 4. PancakeSwap：“真实用户收益”证明

### 4.1 官方硬要求

Agent 必须给 PancakeSwap 交易者或流动性提供者（LP）带来**真实好处**。官方举例包括：

- 更聪明的流动性管理；
- 找到更好的收益；
- 研究市场需求，找到新池能改善流动性效率的机会；
- 使用 PancakeSwap 产品做安全自动兑换，但不将用户资金暴露在不必要的风险中。

截至本次核对，官方**没有**公布 PancakeSwap 伙伴奖的数字评分表、固定报告格式，也没有写“必须完成真实主网交易”。不能把自己的证据格式冒充成官方硬门槛。

### 4.2 SafeHire 应准备的可复核证据包

下面是根据官方“真实好处”要求做的 SafeHire 证据方案，不是官方指定模板：

- [ ] 明确受益者是 trader 还是 LP，以及 Agent 帮他优化了什么。
- [ ] 保留 Agent 原始输入、原始输出、Agent/雇佣标识和交付时间，证明结果是 Agent 交付。
- [ ] 使用 PancakeSwap 官方可核对的数据或合约，保留 chain id、区块高度、观测时间、token、数量和合约/池地址。
- [ ] 写出基线、Agent 选择和可量化改善量，让评委能重算，而不是只写“更好”。
- [ ] 写清风险边界：是报价还是成交、是否计 gas/滑点/价格变化，实际交易是否需要新报价、最小到账、截止时间、授权审查和钱包确认。
- [ ] 把证据链接放到公开 README 和官方表单 `Additional Notes`。

PancakeSwap 官方开发者资料当前列出 BSC 的 V3 Factory 和 QuoterV2 地址，也列出可追踪价格、交易量和流动性的 BSC V3 subgraph。这些能用来证明数据来自 PancakeSwap，但不会自动证明“用户得到好处”；后一点仍要用上面的基线和改善量来证明。

**本次执行更新：**`evidence/pancakeswap/live-benefit-report.json` 已刷新到 BSC mainnet 区块 `119108691`（`2026-08-31T07:07:36Z`），比较 V3 Factory + QuoterV2 四个 WBNB/USDT 直连池；最佳 `0.01%` 池相对 `0.05%` 基线多返回 `0.003880692718573066 USDT`（`0.5652 bps`）。报告已绑定公开 Agent 调用 `inv_20260831070737081187`，仍明确是只读报价，不是真实成交或利润证明。可以勾选 PancakeSwap。

官方来源：[赛事页 PancakeSwap Challenge](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) · [BNB Chain 官方文章 PancakeSwap 概述](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace) · [PancakeSwap V3 官方合约地址](https://developer.pancakeswap.finance/contracts/v3/addresses) · [PancakeSwap 官方 subgraph 资料](https://developer.pancakeswap.finance/apis/subgraph)

## 5. 官方表单字段：谁来补什么

官方文章说通过 intake form 提交 build，其链接先进入赛事页；赛事页的 `Submit Project` 当前进入 [Build the Era Hackathon Registration](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)。表单自身仍叫 `Registration`。截至本次核对，未发现第二个公开的最终提交表。

表单还提示会记录回应邮箱，同时又有一个必填的 `Email Address` 文本字段。提交时最好让两者一致，并勾选“将回应副本发给我”，保留提交证明。

| # | 官方表单字段 | 必填 | 谁处理 | 提交前状态/动作 |
|---:|---|:---:|---|---|
| 1 | Full Name | 是 | 参赛者 | [ ] 填真实或用于参赛的姓名，与后续联系/领奖信息一致。 |
| 2 | Email Address | 是 | 参赛者 | [ ] 填并确认能收信。 |
| 3 | Telegram Handle | 是 | 参赛者 | [ ] 填。 |
| 4 | X (Twitter) Handle | 是 | 参赛者 | [ ] 填。 |
| 5 | Discord Handle (Optional) | 否 | 参赛者 | [ ] 有则填。 |
| 6 | How did you hear about this hackathon? | 是 | 参赛者 | [ ] 从 X / Discord / Telegram / BNB Chain Website / Partner Announcement / Friend/Colleague / Other 中选真实来源。 |
| 7 | Country and Timezone | 是 | 参赛者 | [ ] 填真实国家和时区，例如 `China, UTC+8 (Asia/Shanghai)`。 |
| 8 | Solo builder or team | 是 | 参赛者 | [ ] 选 Solo 或 Team。 |
| 9 | Number of Teammates | 是 | 参赛者 | [ ] 选 1 (Solo) / 2 / 3 / 4 / 5+。 |
| 10 | Teammate Names, Emails, and Roles | 表单技术上否 | 参赛者 | [ ] 如果选 Team，按表单说明列全成员姓名、邮箱、职责，并为每人附至少一个 X/LinkedIn 等社交资料链接。 |
| 11 | Project Name | 是 | 已备稿 | [x] `SafeHire / ProofOps`。 |
| 12 | One-Line Pitch | 是 | 已备稿 | [x] 见 `submission/form-draft.md`；粘贴后再检查无换行/截断。 |
| 13 | Project Description | 是 | 已备稿 | [x] 见 `submission/form-draft.md`；官方限制 **800 字符以内**。[ ] 提交时再看表单是否接受。 |
| 14 | Sub-prize tracks | 是 | 参赛者 + 证据门禁 | [ ] 只在对应证据达标时勾选 PancakeSwap/TermiX；不确定时可选 Not sure。当前表单还有 AltLayer，但没有赛事页已列出的 Altana，不要把两者当成同一个。 |
| 15 | Project GitHub Repo Link | 是 | 已备稿 | [x] `https://github.com/seekitx/safehire-proofops-bnb`。[ ] 退出 GitHub 后复查可访问。 |
| 16 | Prototype Stage | 是 | 已备稿 | [x] `Working MVP`。 |
| 17 | BSC/EVM Experience Level | 否 | 参赛者 | [ ] 按真实情况选 Beginner / Intermediate / Advanced。 |
| 18 | Comfortable areas | 否 | 参赛者 | [ ] 按真实情况选 Solidity / AI agent frameworks / Onchain data/APIs / Frontend development。 |
| 19 | Mentorship | 是 | 参赛者 | [ ] 选是否需要导师支持。 |
| 20 | Availability | 是 | 参赛者 | [ ] 确认构建期和评审期可联系/参与。 |
| 21 | Prize wallet (ERC-20/BEP-20 compatible) | 是 | 参赛者 | [ ] 亲自核对领奖钱包地址；不要从截图手抄，不要提交私钥/助记词。 |
| 22 | Additional Notes (Optional) | 否 | 已有初稿 | [ ] 用 `submission/form-draft.md` 为底稿，但只保留最终实际成立的奖项声称和可公开证据链接。 |
| 23 | Terms of Participation | 是 | 参赛者 | [ ] 亲自阅读后决定是否接受；不由脚本代勾。 |

当前表单**没有单独的**公开产品 URL、Agent Advantage Report、演示视频、Deck、合约地址或交易哈希字段。因此 GitHub README 要作为证据总入口，产品站点、proof dossier、Agent Report 和链上证据链接放到 `Additional Notes`。演示视频可以降低评委理解成本，但它不是这份当前表单的必填项。

## 6. 当前项目状态快照

以下是 2026-08-31 的只读核对，不等于 BNB Chain 官方认证：

- [x] 公开市场 `https://safehire-proofops-bnb.onrender.com` 返回 HTTP 200。
- [x] 公开 proof dossier `https://safehire-proofops-bnb.onrender.com/proof` 返回 HTTP 200。
- [x] 公开 GitHub `https://github.com/seekitx/safehire-proofops-bnb` 返回 HTTP 200。
- [x] 项目自建 submission gate 返回 `ready=true` 和 `26/31`，没有 P0 阻塞或伙伴奖缺口；四个本地 demo Agent 的 `P2` 提醒和可选演示视频仍保留。**这是项目自查，不是官方发的“可提交”证书。**
- [x] PancakeSwap 同区块报价改善证据已刷新并绑定 Agent 交付。
- [x] TermiX 三组 live 对照和 Agent Advantage Report 已生成；参赛者人工浏览自动评分仍是最终提交前动作。
- [ ] 仍需人工在无登录环境验收主赛全流程和四类真实 Agent 的同等深度。HTTP 200 只证明网址可连接，不证明交互流程没有死路。

## 7. 最后一小时的执行顺序

### A. 任一项未通过就先不提交

- [ ] 正式提交当天重新打开官方赛事页和表单，确认截止时间、字段和奖项选项未变。
- [ ] 退出账号/无痕模式打开产品、proof dossier、GitHub 和所有 Additional Notes 链接。
- [ ] 按 Functionality 标准完整重走一次主赛路径，不只看首页和 HTTP 200。
- [ ] 核对四类 Agent 都是 live on BSC 的真实目录项，并有同等深度的可审查数据和可用下一步。
- [ ] 刷新所有“live”数据的时间/区块，失败时不把 fixture 冒充成 live。
- [ ] 按实际证据决定是否勾选 PancakeSwap 和 TermiX；不达标就不勾选，不写过度声称。

### B. 表单预览

- [ ] 将 `submission/form-draft.md` 中的项目文案逐项粘贴到表单。
- [ ] 由参赛者填完第 5 节中所有“参赛者”项。
- [ ] 检查 Project Description 未超过 800 字符，链接未被截断，项目名称、邮箱和团队信息前后一致。
- [ ] 钱包地址用复制后核对首尾和网络兼容性；不在表单任何位置填私钥或助记词。
- [ ] 参赛者亲自阅读条款和本项目的奖项声称。
- [ ] 在点击前截取整份回答或将文字存在本地，因为当前无法确认提交后可修改。

### C. 参赛者最后点击（本清单在这里停止）

- [ ] 勾选“将我的回应副本发送给我”。
- [ ] 参赛者亲自点击 `Submit`。
- [ ] 保存成功页截图、邮件回执、提交时间，以及如果成功页实际给出的编辑链接。

## 8. 仍未被公开官方资料确认的事项

- 当前名为 `Registration` 的 intake form 之外，截止前是否还会新增第二份最终表单。
- 该表单提交后是否开启回应编辑；公开页没有给保证。
- 主赛 Functionality / Data Quality / Agent Diversity 的数字权重。
- 第二阶段新增评审标准的具体内容。
- 表单为什么有 AltLayer 而没有赛事页列出的 Altana，以及 Altana 应如何选择。
- PancakeSwap 伙伴奖的固定报告格式、数字评分权重或必须主网成交的要求；官方当前只公布了“Agent 带来真实好处”及示例。

如果官方页面在提交日仍没有更新，上面这些问题应通过官方表单页首链接的赛事 Telegram 支持群向主办方确认，不应由项目自行猜测。

## 官方一手来源

- [The Smart Money Era: Build the Era 官方赛事页](https://www.bnbchain.org/en/hackathons/smart-money-era)
- [Build the Era: Build the Official BNB Agent Studio Marketplace](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)
- [Build the Era Hackathon Registration 官方 Google Form](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)
- [PancakeSwap V3 官方合约地址](https://developer.pancakeswap.finance/contracts/v3/addresses)
- [PancakeSwap 官方 Subgraph 资料](https://developer.pancakeswap.finance/apis/subgraph)

## 本次执行边界

已完成公开 Agent 部署、三组 TermiX 赞助雇佣、PancakeSwap 证据刷新和提交材料整理；没有执行新的钱包交易，也没有提交官方表单。最终表单中的身份、联系方式、领奖钱包和条款必须由参赛者本人确认。
