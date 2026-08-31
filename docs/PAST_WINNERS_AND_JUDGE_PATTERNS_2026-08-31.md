# SafeHire：历届 BNB 获奖方向与本届评委偏好对照

> 核对日期：2026-08-31。外部事实只引用 BNB Chain 当前赛事页与官方获奖回顾；SafeHire 状态来自本仓库代码、证据文件和公开 API。本文是冲奖判断，不是主办方评分或获奖保证。

## 结论

### 本轮实施状态

代码层已补上原分析中可自动完成的主要缺口：外部 Agent 报价可继续进入人工逐笔确认的主网 ERC-8183 雇佣；首页分开展示实时探测、索引健康、反馈和运营方数；新增只读 provider intake；TermiX 新增真人计时与 A/B 盲评工具；PancakeSwap 新报告覆盖三档金额和估算 Gas 后净改善。

下面的缺口仍保留作为评审背景，但其中“没有统一雇佣页”和“没有证据工具”已从代码缺口变成人工验收缺口。本地 Python 检查、合约测试、Agent Studio 构建和 Docker 镜像构建已经通过；生产版本仍以 GitHub Actions 和 Render 的最新部署结果为准。尚未完成的关键事实是：外部 Agent 主网付费交付为 `0`，真人盲评为 `0`，独立运营方仍只有 `1`个。

SafeHire 已经是可提交的 Working MVP，差异化也成立：它把“选 Agent”从宣传页问题改成了身份、证据、权限、托管、交付、结算和撤销都能复核的信任问题。真正妨碍它打动评委的不是合约或协议数量，而是三条证据路径尚未合并：

1. 外部 BSC Agent 可以发现并取得实时 `0.10 U` 报价，但产品不会从该卡片继续创建、付款和等待交付；
2. 可以完整预演、限制权限和执行的页面使用的是四个本地 demo Agent；
3. 已结算的 ERC-8183 Job #808 是独立历史证据，不是当前外部 Agent 卡片产生的订单。

官方主赛明确要求普通用户能在几次点击内完成“找到、理解、启用 Agent”，不能遇到死路；TermiX 也会亲自从市场雇佣 Agent。若评委点击真实 Agent 后只得到报价，再发现真正的 Hire 控制台操作的是 demo Agent，这会同时伤害 Functionality、Data Quality、Marketplace Quality 和 Proven Agent Advantage。

## 本届官方评审重点

官方要求四个类别都达到同等深度，并主要看：端到端功能、实时且能支持选择的数据、四类 Agent 的多样性。TermiX 另看服务价值 30%、可证明 Agent 优势 30%、高风险类别与历史记录 20%、市场质量 20%；其报告至少要有三项真实任务，逐项提供 Agent 与不用 Agent 两条路径的耗时、成本、质量和完整输出。PancakeSwap 奖要求给交易者或 LP 带来真实好处。

来源：

- [The Smart Money Era 官方赛事页](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)
- [Build the Official BNB Agent Studio Marketplace](https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace)

## 历届获奖项目体现出的共性

| 官方获奖案例 | 被官方突出描述的能力 | 对 SafeHire 的启示 |
|---|---|---|
| Neural Alpha、Genesis、Gridora（AI Trading Agent Edition） | 读取市场条件、管理策略、进行链上执行，并更自主地运行 | 评委看闭环，不只看分析或报价 |
| DeFi Copilot | 实时分析、一键执行、PancakeSwap 自动管理 | 把复杂 DeFi 压成一条清楚的用户动作链 |
| BIBIM | 用直观可视界面创建、测试和变现策略 | 易懂、可试、可比较比协议名更有说服力 |
| DeFi Pro | 简单聊天命令连接 Pendle、Lista 与实时收益数据 | 用真实数据解决一个高级但明确的问题 |
| Midas | 实时社交数据、影响评估、模块化工作流、自动交易 | 从信号到决定再到行动，因果链必须看得见 |
| Outrun | 多个互相咬合的 DeFi 原语形成完整经济系统 | 技术模块必须共同服务一个产品结果，不能像附件拼装 |

官方来源：

- [AI Trading Agent Edition 获奖回顾](https://www.bnbchain.org/en/blog/meet-the-winners-of-bnb-hack-ai-trading-agent-edition)
- [2025 年 7 月 BNB Hack 获奖回顾](https://www.bnbchain.org/en/blog/congratulations-to-the-latest-bnb-hack-winners-july-21-batch)
- [BNB Hack Abu Dhabi 获奖回顾](https://www.bnbchain.org/en/blog/bnb-hack-abu-dhabi-highlights-from-the-hackathon-and-demo-night)
- [BNB Hack Buenos Aires 评审维度](https://www.bnbchain.org/en/blog/bnb-hack-buenos-aires-recap-highlighting-builders-innovation-and-the-winners)
- [BNB Hack 2024 Q4 获奖回顾](https://www.bnbchain.org/en/blog/bnb-hack-2024-q4-winners-a-celebration-of-innovation)

跨届共性可以概括为五点：

1. 真实输入，不是漂亮的静态卡片；
2. 真实动作或交付，不止一条推荐；
3. 用户收益可以重新计算；
4. 复杂能力被压缩成低门槛界面；
5. 有真实使用、交易、任务量或持续运行记录时，可信度明显更高。

Buenos Aires 的官方评审维度还明确包含设计与易用性、创新、可扩展性与技术深度、开源贡献、生态契合。Abu Dhabi 官方总结强调真实用户需求、快速测试、保持产品简单，以及持续迭代。

## SafeHire 当前强项

1. **定位有差异**：不是再做一个交易 Agent，而是做 Agent 金融市场的信任与结算层。
2. **安全边界具体**：权限范围、单次和每日额度、过期、单独批准、撤销、回执，不是只写“安全”。
3. **链上证据比一般 MVP 扎实**：ERC-8004 身份、ERC-8183 Job #808、三个 ProofOps 合约和公开 proof dossier 都可复核。
4. **诚实边界做得好**：代码明确区分 live、quote-only、sponsored、demo fixture 和未成交报价，没有把预演冒充利润。
5. **四类目录已经出现**：外部 BSC mainnet Agent 覆盖四个官方类别，当前公开 API 也能实时确认四项能力可调用。

这部分最适合形成一句冲奖叙事：

> SafeHire is the trust and settlement layer for BNB Chain agents: compare verified outcomes, cap authority, hire in a few clicks, and settle only after a provable delivery.

## 当前最影响获奖的缺口

### P0：必须先补

1. **把真实外部 Agent 卡片接入同一个 Hire 流程。**从外部 ERC-8004 身份和报价开始，在同一页面选择任务、显示价格、创建/资助 ERC-8183、等待交付、验收、结算或退款，最后把回执回写到该 Agent 的履历。可以先使用 BSC Testnet 和小额 `0.1 U`，但必须让评委亲自走通。
2. **重做 TermiX 三组证据。**现报告的不用 Agent 路径是同一脚本里的确定性函数，耗时显示 0 秒；Agent 反而慢 2.65 秒。三项质量分又由代码固定为同一组 `24.5 vs 22`，复核人仍是 `entrant review pending`。结构看起来合规，但无法经受评委追问。应改成真实人工工作流计时、盲评或至少由非输出作者按逐项证据评分，并让三项分数根据实际输出变化。
3. **至少让一笔 TermiX 任务来自可公开雇佣的外部 Agent。**当前三次 sponsored hire 调用的是 SafeHire 自己的 A2A 确定性能力，外部四个 Agent 只参与发现和报价。TermiX 会亲自雇佣，这两条路径不能分离。

### P1：显著提升胜率

4. **用表现数据做“选择”，而不只是展示身份。**每个 Agent 至少补充成功/失败任务数、最近 10 笔结果、交付时延分布、真实价格、用户反馈、证据新鲜度、可复核输出，以及适合本类别的风险指标。8004scan 官方 API 已能提供身份、能力、所有权、reputation、feedback 和网络信息，本项目目前没有把 reputation/feedback 变成排序或推荐依据。
5. **增加运营方和同类候选。**现有四个 live Agent 全来自 Brain On BNB AI，且每类只有一个。它满足“四类出现”，却不像能让用户比较选择的市场。至少引入第二个独立提供方，或给每类两种不同风险/价格方案。
6. **补齐 Rebalancing 的真实深度。**TermiX 三组任务覆盖网格、收益和健康因子，没有调仓；四类中的调仓仍主要是外部报价和本地 fixture。至少做一笔真实 LP 区间分析/调仓交付，并给出费用、预期增益、无常损失、gas、触发阈值和不执行理由。
7. **把 PancakeSwap 收益从“0.0039 USDT 单点报价”升级成可感知结果。**当前证据真实但很小，而且没有计 gas、没有交易。更强版本应比较多个区块/时段、不同交易规模或 LP 周期，报告累计节省、失败率、gas 后净收益和风险；最好让一次 Agent 选择实际产生测试网或受控执行回执。

### P2：最后包装和可靠性

8. **提供 Agent 上架/验证入口。**主赛赢家会被官方采用为 BNB Agent Studio 市场；只有硬编码目录难以证明能扩展。做一个最小 provider onboarding：提交 Agent Card/8004 ID，自动校验端点、类别、价格、协议和证据完整度，再进入待审核状态。
9. **消除 Render 免费休眠风险。**评委第一次打开如果等待几十秒，会直接削弱 Functionality 印象。至少准备稳定托管、健康监控和故障降级页；不要让 live 数据失败时回退成 demo。
10. **录制 2–3 分钟单线演示。**视频不是当前表单硬门槛，但应该只讲一条 wow path：真实 Agent → 可比较证据 → 0.1 U 雇佣 → 权限上限 → 交付 → 结算/退款 → Agent 履历更新。不要按模块逐页念。
11. **取得一条独立使用证据。**邀请一个外部 Agent 提供方或真实用户走完流程，保留公开评价、任务回执或 GitHub issue。历届官方回顾会突出用户数、交易数、任务量和成交量，说明真实采用是强信号。

## 建议的提交前冲刺顺序

1. 真实外部 Agent 端到端雇佣闭环；
2. 用该闭环重新做三组 TermiX 对照和真实评分；
3. 每类真实履历/反馈/风险数据，同类可比较；
4. 强化 PancakeSwap 的净收益证据和 Rebalancing 深度；
5. 稳定托管、短视频和独立用户证言。

不要优先继续部署新合约、增加 Logo 或再做第五类 Agent。它们不会修复评委最容易撞见的死路。

## 最终判断

- **提交资格层面：**已经达到有公开产品、公开代码和链上证据的认真作品水平。
- **进入 shortlist 的说服力：**有，尤其是 ProofOps 权限与可核验结算的差异化。
- **成为官方 canonical marketplace 的说服力：**目前不足。最大的反对理由会是“真实外部市场只能报价，能完成 Hire 的却是 demo；因此还不是给真实用户用的统一市场”。
- **最可能翻盘的方向：**不再扩功能，把 SafeHire 定义成“真实 Agent 雇佣的信任与结算层”，然后用一条无断点的外部 Agent 订单和可信报告证明它。
