# SafeHire / ProofOps：Build the Era 官方要求与当前缺口

> 状态说明：本文前半部分保留官网核对当时的原始缺口快照。后续已经补齐公开 Render 市场、GitHub、四类 live BSC Agent 发现与报价、三组 TermiX live 对照，以及 PancakeSwap Agent 交付绑定。当前提交状态以 `HACKATHON_FINAL_SUBMISSION_CHECKLIST_2026-08-31.md` 和公开 `/proof` 页为准。

核对日期：2026-08-31（Asia/Shanghai）

## 先说结论

SafeHire / ProofOps 参加的是 BNB Chain 的 **The Smart Money Era: Build the Era**，目标是做“BNB Agent Studio 的 Agent 市场”，不是只交一个 Agent。提交截止时间是 **2026-09-09 12:00 UTC，也就是北京时间 2026-09-09 20:00**；评审期是 9 月 9 日到 9 月 23 日，11 月 5 日公布获奖者。[BNB Chain 专题页](https://www.bnbchain.org/en/hackathons/smart-money-era) [官方报名/提交表单](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form) [BNB Chain 发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

下面七项是 2026-08-31 首次官网核对时的原始缺口，保留用于说明项目从哪里开始；其中第 1–5 项后来已经补齐或形成公开证据，第 6 项 Altana 仍不具备资格，第 7 项最终表单仍等待参赛者：

1. **当时没有能撑过评审期的公开 HTTPS 市场；现已补齐。**Render 公开站点覆盖评审入口，免费实例仍有冷启动风险。
2. **当时市场里的四类 Agent 仍是演示数据；现已补齐真实供给。**四个外部 ERC-8004 Agent 覆盖全部类别，本地 `config/agents.json` 预演仍保持 `demo_fixture` 标记，不混淆。
3. **当时没有公开 GitHub；现已补齐。**仓库已公开供评委访问。
4. **当时缺 TermiX Agent Advantage Report；现已补齐。**三组真实“Agent vs 不使用 Agent”对照、实际输出、时间、成本、质量和 hash 已公开。
5. **当时缺 PancakeSwap 可复核收益证据；现已补齐。**真实同区块四池比较已经绑定 Agent 交付，并保留只读报价边界。
6. **Altana 奖项目前不具备资格。**自建 `ScopedExecutionPolicy` 不是 Altana session；当前没有 Altana 钱包、链上 session、限额、撤销和 Altana Explorer 交易。
7. **尚未填写并提交官方表单。**在用户最终检查和明确确认前，不应代替用户提交。

### 实现后更新（2026-08-31）

公开基础交付现已完成：市场部署在 https://safehire-proofops-bnb.onrender.com，代码仓库是 https://github.com/seekitx/safehire-proofops-bnb，并提供评委可直接访问的 `/proof` 和 `/.well-known/agent-card.json`。Render 免费实例可能休眠，所以“已公开部署”不等于“没有冷启动风险”。

上面是官网核对时的原始缺口快照。随后已补充一项重要能力：首页现在会通过 ERC-8004 注册证据和免费 A2A `list` 接口，发现四个由 `Brain On BNB AI` 外部运营、真实注册于 BSC mainnet 的 Agent，覆盖调仓、网格、收益优化和健康因子四类。实时发现在 Chrome 中观察到 `4/4 skills callable`。

这使“四类真实 BSC Agent 存在且当前可发现”从未完成变成已有证据，但不能扩大成“SafeHire 已验证它们的交付质量”：它们属于外部运营方，SafeHire 还没有为它们支付 BSC mainnet `0.10 U`。TermiX 报告使用 SafeHire 自有公开 Agent 的赞助雇佣，与外部 Agent 的身份和报价证据分开。本地 `config/agents.json` 的四个预演仍明确标为 demo。

PancakeSwap 伙伴奖证据也已补充：`evidence/pancakeswap/live-benefit-report.json` 在同一 BSC mainnet 区块上，通过官方 V3 Factory 发现四个 WBNB/USDT 直连手续费池，并用官方 QuoterV2 比较 `0.1 WBNB` 的输出。该报告已绑定公开 Agent 交付，是可重复抓取的真实主网只读报价，不是交易或利润承诺。

TermiX 后续执行也已完成：三次公开 SafeHire A2A 赞助雇佣分别覆盖 grid trading、yield optimisation 和 health-factor security，并与不调用市场 Agent 的直接计算做同题对照。原始输出、时间、真实零成本、统一质量评分和文件 hash 均在 `evidence/termix/` 公开。它们不冒充付费样本或人类研究；Job #808 继续单独证明 `0.1 U` ERC-8183 付费闭环。

## 1. 赛事身份、时间和奖金

| 项目 | 官方当前信息 |
|---|---|
| 名称 | The Smart Money Era: Build the Era |
| 主办方 | BNB Chain |
| 形式 | 全球线上比赛，个人或团队都可以参加 |
| 构建期 | 2026-08-05 12:00 UTC 至 2026-09-09 12:00 UTC |
| 北京时间截止 | 2026-09-09 20:00 |
| 评审期 | 2026-09-09 至 2026-09-23 |
| 公布结果 | 2026-11-05 |
| 主赛冠军 | 当前专题页写“价值 30,000 美元的奖励”，发布文章写 30,000 USDT；两处官方口径略有差别 |
| TermiX | 第一名 6,000 美元、第二名 3,000 美元、第三名 1,000 美元 |
| PancakeSwap | 最佳项目 1,000 CAKE |
| Altana | 一支队伍获得 50,000 Altana XP；分配机制仍标记待确认 |
| AltLayer | 8004scan Pro 方案和 AltLLM credits，数量仍标记待确认；专题页没有公布独立现金奖或独立评审标准 |

时间和奖金来源：[赛事专题页](https://www.bnbchain.org/en/hackathons/smart-money-era)、[官方发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)。

## 2. 参赛资格和法律边界

本场专题页明确要求：

- 全球开放，可个人参赛，也可组队；
- 每支队伍只能交一个作品；
- 项目在评审期间必须功能正常且公开可访问；
- 市场里展示的 Agent 必须真实在线于 BSC。[赛事专题页：Eligibility](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

BNB Chain 的通用活动条款另外规定：参赛者需年满 18 岁、具有完全法律行为能力，并拥有提交项目的合法权利；获奖不是保证，主办方可要求获奖者接受额外条款，税费由获奖者承担。提交者仍拥有自己的作品，但同时授予主办方非常广泛、不可撤销、全球、非独占、免版税的使用许可。[BNB Chain Event Participation Terms](https://www.bnbchain.org/en/event-terms)

当前官方材料**没有公布**本场的地区禁限清单、KYC（领奖身份核验）清单或团队人数上限。表单允许选择 `5+` 人，因此不能从表单推导出“最多 5 人”。领奖时是否需要进一步 KYC、税务或制裁地区审查，需要主办方后续通知。

## 3. 当前官方表单到底要求提交什么

赛事专题页的 `Submit Project` 按钮和发布文章的 intake form 都指向同一个 Google Form：

- 短链接：[https://forms.gle/9g9XPNFwnYaHAz9L8](https://forms.gle/9g9XPNFwnYaHAz9L8)
- 直接链接：[Build the Era Hackathon Registration](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)

表单虽然由赛事页面标成 `Submit Project`，自身标题仍叫 `Build the Era Hackathon Registration`。截至本次核对，没有发现第二个公开的最终提交表单。当前表单字段如下：

| 字段 | 是否必填 | 说明 |
|---|---:|---|
| Full Name | 是 | 姓名 |
| Email Address | 是 | 邮箱 |
| Telegram Handle | 是 | Telegram 用户名 |
| X (Twitter) Handle | 是 | X 用户名 |
| Discord Handle | 否 | 可选 |
| How did you hear about this hackathon? | 是 | 来源渠道 |
| Country and Timezone | 是 | 国家和时区 |
| Solo builder or team | 是 | 个人或团队 |
| Number of Teammates | 是 | 选项为 1、2、3、4、5+ |
| Teammate Names, Emails, and Roles | 表单技术上可空 | 组队时说明文字要求列出所有成员、邮箱、职责，并为每人提供至少一个社交资料链接 |
| Project Name | 是 | 项目名 |
| One-Line Pitch | 是 | 一句话介绍 |
| Project Description | 是 | 最多 800 个字符，说明市场有什么独特之处和重点优化功能 |
| Sub-prize tracks | 是 | 可多选：PancakeSwap、AltLayer、TermiX、Not sure |
| Project GitHub Repo Link | 是 | GitHub 仓库链接 |
| Prototype Stage | 是 | Fresh idea / Early prototype / Working MVP |
| BSC/EVM Experience Level | 否 | 可选 |
| Comfortable areas | 否 | Solidity、Agent 框架、链上数据/API、前端 |
| Mentorship | 是 | 是否需要导师支持 |
| Availability | 是 | 确认构建期和评审期可联系/可参与 |
| Prize wallet | 是 | 可接收 ERC-20/BEP-20 的领奖钱包地址 |
| Additional Notes | 否 | 可补充公开站点、报告、交易和奖项说明 |
| Terms of Participation | 是 | 接受参赛条款 |

### 需要特别注意的表单不一致

1. 专题页和发布文章都列出 **Altana** 奖项，但当前表单的奖项选项没有 Altana，反而有 **AltLayer**。如果要冲 Altana，应在 `Additional Notes` 明确写明，并在截止前通过赛事官方 Telegram 向主办方确认选择方式。
2. 当前表单没有单独的公开网站、Agent Advantage Report、演示视频、Deck、合约地址或交易哈希输入框。最稳妥的做法是让 GitHub README 成为证据总入口，并在项目描述或 Additional Notes 放公开站点、TermiX 报告、BscScan 交易和钱包信息。
3. **视频、Deck、宣传推文、至少两笔合约交易**是其他 BNB Hack 活动里常见的要求，但没有出现在本场当前专题页和当前表单中，不能冒充本场硬门槛。演示视频仍然值得做，因为能降低评委理解成本，但应标成加分材料，而不是“官方必交”。

## 4. 主赛必须做成什么

官方要求的是一个能让用户“发现、理解、比较并启用 Agent”的市场前端，而不是只展示自己做的一个 Agent。完整用户路径应做到：进入市场、按类别找 Agent、理解它做什么、查看可信数据、用尽量少的步骤启用或雇佣，且不熟悉 Agent Studio 的用户也不会卡住。[赛事专题页：Main Track](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [官方发布文章：The Challenge](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

### 四类 Agent 必须同等深入

当前专题页列出的四类为：

1. Rebalancing：管理 LP 区间并重置仓位；
2. Grid Trading：放置并管理网格订单；
3. Yield Optimisation：把流动性路由到更高 APR；
4. Health Factor Monitoring：保护借贷仓位免于清算。

专题页明确写明：只做单一类别会得低分，四类都达到相同深度才是标准。早期发布文章曾把四类称为“指导而不是固定标准”，但当前专题页的最新详细规则把 `Agent Diversity` 明确列为评审项，因此应以当前专题页为准。[赛事专题页：What You're Building / How You're Judged](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

### 主赛当前公布的评审标准

| 标准 | 评委看什么 |
|---|---|
| Functionality | 全流程真的能跑：进入、发现、理解、启用/雇佣，无明显死路，非专业用户也能完成 |
| Data Quality | 实时、准确、超过简单数量统计，足以帮助用户做雇佣判断 |
| Agent Diversity | 四个类别同等深入，不能把其余三类当陪衬 |

页面表头虽然写了 `Weight`，但没有给这三个标准发布数字百分比。页面还写明第二阶段会增加更多评审标准，但 `Phase 2` 仍为 `[REDACTED]`，因此数字权重和第二阶段要求目前都是未知项。[赛事专题页：How You're Judged / Timeline](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

## 5. 伙伴奖项要求

### 5.1 TermiX Challenge

这是 SafeHire 当前最匹配、也最应该完成的伙伴奖。官方要求：

- 至少三项真实任务，每项都分别用“从市场雇佣的 Agent”和“不使用 Agent”完成；
- 每项记录时间、成本和输出质量；
- 附上双方的真实完整输出；
- 至少一项属于交易、股票或安全；
- 不能只口头声称 Agent 更快、更好，`Agent Advantage Report` 是资格材料。[赛事专题页：TermiX](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)

TermiX 独立评分：服务价值 30%、可量化 Agent 优势 30%、高风险类别和历史记录 20%、市场质量 20%。交易 Agent 还应展示真实历史记录，包括胜率、统计窗口和为取得结果承担的风险。

### 5.2 PancakeSwap Challenge

Agent 必须给 PancakeSwap 交易者或流动性提供者带来真实收益。官方例子包括：更聪明的流动性管理、找到更好的收益、研究市场需求并指出新池的流动性效率机会，或在不让用户资金暴露于不必要风险的情况下执行安全自动交换。[赛事专题页：PancakeSwap](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [PancakeSwap Developer Portal](https://developer.pancakeswap.finance/)

本场没有公布 PancakeSwap 的数字评分表，也没有规定必须做主网交易。对 SafeHire 来说，至少要用 PancakeSwap 的真实池子/仓位数据产生可复核建议，并在演示和 README 里明确说明“用户因此得到什么”和“怎样避免资金风险”。

### 5.3 Best Built with Altana

Altana 资格门槛是：

- Agent 使用自己的 Altana wallet；
- session 有真实的合约/方法 allowlist、花费上限和到期时间；
- session 注册到链上 Keystore；
- 通过 session key 真实发送链上交易；
- 用户能在产品内看到 Agent 权限并撤销；
- Altana Explorer 必须能看到真实交易，测试网可算，主网更强；
- 提交时提供相应钱包地址。[赛事专题页：Altana](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks) [Altana Sessions](https://docs.altana.network/concepts/sessions)

使用 Altana SDK 通过 ERC-8183 雇佣 BNB Agent Studio Agent，以及通过 x402/B402 售卖服务，只是 bonus，不是 Altana 基础资格的替代品。[Altana ERC-8183 SDK](https://docs.altana.network/sdk/erc8183) [Altana x402 server](https://docs.altana.network/sdk/x402-server)

### 5.4 AltLayer / 8004scan

专题页把 8004scan 作为 Agent 身份、能力、所有权、信誉、反馈和网络数据来源，并提供黑客松期间的 API 权益。它很适合解决主赛的“实时、准确、可比较”数据要求。[赛事专题页：8004scan](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=resources) [8004scan Builder Hub](https://8004scan.io/developers)

但截至本次核对，专题页没有发布独立 AltLayer 现金奖、独立评分标准或必须集成 8004scan 才有主赛资格的规则。表单却把 AltLayer 列为可选伙伴赛道，这一项应向主办方确认，不能自行假设。

## 6. Agent Studio、ERC-8004、ERC-8183 在本场各自是什么地位

- **明确硬门槛**：市场展示的 Agent 要真实在线于 BSC，项目在评审期公开可用。
- **强烈相关但没有被单独写成主赛硬门槛**：ERC-8004 身份。BNB Agent SDK 把它定义为 Agent 的链上身份和可发现资料，官方市场挑战也以这些身份与历史记录为数据基础。[BNB Agent SDK](https://docs.bnbchain.org/developer-kit/bnbagent-sdk/)
- **很强的功能证据，但没有被写成主赛硬门槛**：ERC-8183 真实雇佣。它证明用户确实能创建工作、托管预算、收取交付并结算；本场只在 Altana 奖项中把“通过 Altana SDK 用 ERC-8183 雇佣”明确列为 bonus。[ERC-8183 草案](https://eips.ethereum.org/EIPS/eip-8183) [BNB Agent SDK](https://docs.bnbchain.org/developer-kit/bnbagent-sdk/)
- **Agent Studio 48 小时试用不能当评审期部署**：官方 Quickstart 明确写明 BNB 托管试用只有 48 小时，到期后禁用；长期公开运行要换成自己控制的 AWS/Azure 或其他可靠托管。[BNB Agent Studio Quickstart](https://docs.bnbchain.org/developer-kit/bnbchain-studio/quickstart/)

因此，Job #808 的完整 ERC-8183 付款闭环应该保留并重点展示，但它不能替代公开市场、四类真实 Agent、实时数据和长期部署。

## 7. 当前仓库和官方门槛的对照

下面是对当前本地文件的只读核对，不代表比赛官网替项目背书。

| 要求 | 当前证据 | 结论 |
|---|---|---|
| 真实 BSC 合约 | `deployments/bsc-testnet.json` 有三个合约及成功交易 | 已有真实测试网证据 |
| ERC-8004 身份 | `erc8004-registration.json` 有 Agent #2032、所有者和 URI 回读 | 已完成一个身份 |
| ERC-8183 雇佣 | `erc8183-job-808.json` 有 create/register/budget/approve/fund/submit/settle，全链路成功 | 已完成一单，可作为强证据 |
| Agent Studio 公开端点 | 48 小时签名卖方作为历史采证；Render 持久公开 Agent Card/A2A 预演与赞助雇佣作为评委入口 | 已分开记录，不冒充长期签名卖方 |
| 公开市场 | Render 公开 HTTPS 市场、证据页和 API 已可访问 | 已完成；免费实例有冷启动风险 |
| GitHub 链接 | `https://github.com/seekitx/safehire-proofops-bnb` 公开可访问 | 已完成表单必填项 |
| 四类真实 Agent | `evidence/marketplace/live-agent-catalog.json` 有四个外部 BSC mainnet ERC-8004 注册、A2A skill 和实时报价；本地四类预演仍是 demo | 真实市场供给已可发现和询价；外部质量尚未验证 |
| 实时高质量数据 | ERC-8004 身份/报价、PancakeSwap 同区块报价、Venus API 快照均有来源；外部历史表现仍缺 | 部分满足 Data Quality，边界已明示 |
| TermiX 报告 | 三组公开赞助雇佣和 without-Agent 对照，含完整输出、时间、真实零成本、质量和 hash | 已具备公开资格材料；自动评分待参赛者浏览 |
| PancakeSwap 收益证据 | `live-benefit-report.json` 有同区块 V3 Factory + QuoterV2 四池比较、改善量和 Agent 交付 | 已证明只读路由选择的可量化帮助；未声称已交易或获利 |
| Altana | 有自建权限合约，但没有 Altana wallet/session/Keystore/Explorer 证据 | 不具备 Altana 资格 |
| 最终提交 | `submission/submission.json` 和表单文案已补公开链接；官方表单尚未由参赛者确认提交 | 正式提交前一步，未提交 |

## 8. 后续执行状态

### P0：已完成的主赛门禁

1. Render 公开 HTTPS 市场、证据页、Agent Card 和 API 已上线；免费实例仍有冷启动风险。
2. 四个外部 BSC Agent 的 ERC-8004 注册和 A2A 存活已保存；提交日前仍应刷新一次。
3. 外部 Agent 当前只声称身份、可调用性和实时报价，不声称质量已经验证。
4. GitHub 已公开，README 已汇总公开市场、报告和链上证据。

### P1：TermiX 和 PancakeSwap 已完成的证据

1. 三组同题对照已完成，覆盖 trading/grid、yield optimisation 和 health-factor security。
2. Agent / without-Agent 双方原始输出、时间、实际零成本、统一评分和 SHA-256 已公开。
3. PancakeSwap 主网同区块数据、改善量、风险边界和 Agent 调用绑定已刷新。
4. 自动评分仍需参赛者浏览；邀请独立复核者只属于可选加分，不是官网硬规则。

### P2：是否冲 Altana

Altana 不是“把现有权限合约换个名字”就能拿。要冲就必须正式接入 Altana wallet/session/Keystore/Explorer，并在产品里做可见权限和撤销。若时间不够，应把精力留给主赛、TermiX 和 PancakeSwap，避免勾选一个没有资格证据的奖项。

### P3：提交材料

1. 准备 Project Name、One-Line Pitch 和 800 字符以内英文 Project Description。
2. 在 GitHub README 汇总公开站点、TermiX 报告、Agent Studio、ERC-8004、ERC-8183、合约和交易证据。
3. 演示视频可以做成 3–5 分钟加分材料，但当前不是本场表单硬门槛。
4. 从无登录浏览器检查所有链接。
5. 用户最后检查表单内容、参赛条款、领奖钱包后再亲自确认提交。

## 9. 仍需向主办方确认的未知项

以下内容截至 2026-08-31 没有完整官方答案：

- `Phase 2` 的实际形式和新增评审标准；
- 主赛三项标准的数字权重；
- 当前名为 Registration 的 intake form 是否就是唯一最终提交入口，还是截止前还会新增正式提交表；
- 为什么表单有 AltLayer 而没有专题页已公布的 Altana 伙伴奖，以及 Altana 应如何勾选；
- 主赛“live on BSC”是否明确接受所有测试网 Agent。官方提供 BSC Testnet Faucet 和 48 小时 testnet trial，说明测试网很可能用于参赛开发，但主赛资格文字没有像 Altana 条款一样明确写“testnet or mainnet”；
- 团队人数上限、KYC 和领奖地区限制；
- AltLayer 伙伴赛道的最终奖金、权益和独立评审标准。

这些问题应通过赛事官方支持群确认：[官方 Telegram 支持群](https://t.me/+MhiOLT0YUnlmNWFk)。

## 10. 官方来源清单

- [赛事专题页与当前赛道规则](https://www.bnbchain.org/en/hackathons/smart-money-era)
- [BNB Chain 官方发布文章](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)
- [官方 Google Form 直接链接](https://docs.google.com/forms/d/e/1FAIpQLSdFb30r24sZcFJVDbMqXNJ1_45BJHanc7eFqwUniScDYZfX9A/viewform?usp=send_form)
- [BNB Chain 通用活动条款](https://www.bnbchain.org/en/event-terms)
- [BNB Agent Studio Quickstart](https://docs.bnbchain.org/developer-kit/bnbchain-studio/quickstart/)
- [BNB Agent SDK：ERC-8004 与 ERC-8183](https://docs.bnbchain.org/developer-kit/bnbagent-sdk/)
- [ERC-8183 官方 EIP 草案](https://eips.ethereum.org/EIPS/eip-8183)
- [8004scan Builder Hub](https://8004scan.io/developers)
- [Altana Sessions](https://docs.altana.network/concepts/sessions)
- [Altana ERC-8183 SDK](https://docs.altana.network/sdk/erc8183)
- [Altana x402/B402 server](https://docs.altana.network/sdk/x402-server)
- [PancakeSwap Developer Portal](https://developer.pancakeswap.finance/)

## 资料边界

本报告只把 BNB Chain 官方赛事页面、BNB Chain 官方文档/博客、赛事页面链接的正式 Google Form，以及官方赞助方/协议文档当作事实来源。聊天记录和仓库旧清单只用于定位项目背景，不被当作比赛规则。没有执行编译、测试、部署、钱包交易或外部提交。
