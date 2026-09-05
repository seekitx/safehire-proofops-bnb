# SafeHire：BNB 主赛竞争调研

调研日：2026-09-05。目标：The Smart Money Era: Build the Era 的 BNB Agent Studio Marketplace 主赛，而非 MemoryGuard/Sibyl，也不是历史 OpenClaw 比赛。

## 1. 可确认的比赛约束

官方主赛页面给出的日期是 2026-08-05 至 **2026-09-09（UTC+0）**。本轮未确认具体截止时分，不沿用旧材料里可能出现的 9 月 10 日；应提前提交并以官方表单为准。冠军奖励为 **30,000 美元等值**，官方页面还列明成为 BNB Agent Studio marketplace 的采用机会。主赛评审维度是 Functionality、Data Quality、Agent Diversity，没有公开数值权重；第二阶段另有未公开标准。[S1]

四类都须作为一等功能：LP Rebalancing、Grid Trading、Yield Optimisation、Health Factor Monitoring。核心是发现、理解、选择、激活 Agent 的完整市场体验，不是单一交易机器人的收益榜。[S1][S2]

TermiX 是独立评审，其 Agent Advantage Report 要求三个实际任务的“雇佣 Agent / 不使用 Agent”对照，包含时间、成本、质量和原始输出。不能把模拟任务、机器人自动评分或者自己改名的供应商当成真实独立验证。[S1][S3]

## 2. 本届公开自述参赛作品

**这不是完整官方提交名单。** 没有获得所有参赛团队的最终提交、评委打分或隐藏阶段要求，因此不提供虚构的夺冠概率。

| 作品 | 直接核对材料 | 实际可支持的判断 | 不能据此确认的事 |
|---|---|---|---|
| HIREDESK | 项目 README、仓库树、`src/app/api/jobs/[id]/execute/route.ts` | 四类桌面、限额/白名单/过期/撤销、两分钟引导；执行路由有 Altana SDK 分支，也有明确的 demo 分支 | 未在本轮连接其钱包或重放其链上收据，不能把代码分支存在等同现场成功 |
| minia2a | 面向 Build the Era 的公开 pitch deck | 将发现、试用、按调用付费、开放上架作为主张；展示其自报服务规模，支付描述包含 Base；BSC 适配在该文档中属于建设计划 | 用户量、真实收入、BSC 全闭环和最终参赛版本没有独立核验 |
| SmartSentinels | 创始人的公开参赛公告 | 自称参与 Smart Money Era 并建设 Agent Marketplace，说明同题竞争不是空白 | 该公告不足以验证合约、四类能力或完整交付质量；不据此给技术排名 |

### HIREDESK 的具体启示

源码中的执行路由先判断配置、会话密钥及钱包，未满足时返回 `onchain:false` 和明确的 demo 说明；未编码的 category 也返回 demo。具备条件才调用 `client.execute({ session, calls })`。因此：

- “有限权限 + 一键撤销 + 四类导航”已经有人实现，不足以成为 SafeHire 唯一卖点。
- 学其压缩用户路径的方式，但不要将其可执行分支说成已验证的真实主网表现。
- SafeHire 应把差异做在**为什么选择这个 Agent、证据缺在哪、实际交付是否绑定正确任务**。[S4][S5]

### minia2a 的具体启示

不建议用短期堆上架数量来对抗其“广覆盖”的叙事。文档自报规模可以作为其市场定位的信号，但不是可复核的 BSC 有效 Agent 数量。SafeHire 更适合先做到少量、同类、可验证、有真实比较价值，再扩展来源。不得把对手写在 roadmap 的 BSC、ERC-8004 和四类接入当成已经完成。[S6]

## 3. 历史获奖作品：只作模式参考

BNB 的 Good Vibes Only: OpenClaw Edition 官方获奖页列有 AGOS Clawjob Marketplace、Aegis Protocol、ProceedGate。前者强调 Agent 付费服务与链上验证，后两者分别涉及可核验保护行动和执行治理。[S8]

它们**不是已确认的本届对手**，也不能用旧比赛偏好替代本届规则。我的推断是：只有支付、监控、权限这些标签，不足以自然形成差异；应展示真正可核验的用户结果。这是产品策略判断，不是官方额外评分标准。

## 4. 当前 SafeHire 的审计结论

本轮锁定主分支提交 `267e4978c56adc2c566ab82fc134b18b0a5a7708`。最新 catalog 的观测时间为 `2026-09-01T03:27:47.925352Z`，四个 token 为 304494、302258、304493、302257，运营方均列为 Brain On BNB AI；catalog 明确没有该供应商的 SafeHire 主网付费交付记录。[S9]

这证明的是仓库所保存的观测和作者披露，不是本轮对 9 月 5 日的实时链上再次验证。

关键缺口：

1. **四个注册身份不等于四个独立卖家。** 同类只有一个候选时，不应展示“最佳 Agent”的虚假竞争排名。
2. **Portfolio rebalance pricing 不等于 LP range reset。** `rebalance_plan` 的描述是组合换仓分析，与主赛 Rebalancing 的 LP 区间管理存在范围差异。
3. **接口存在不等于执行深度。** 六项路径/字段齐备只能说明结构完整，不能证明四类都完成任务。
4. **证据接收过宽。** 原 scorecard 可凭本地 `paid:true`、`external_provider:true` 和形式合法交易哈希计数；盲审也依赖自填布尔值。这样会高估完成度。
5. **部分估算存在数学问题。** 原 Yield 引擎线性展开 APY；对负净收益使用乘法风险折扣会使高风险亏损看起来更优。Grid 缺少完整交易成本时仍给出可执行预览。

## 5. 最值得投入的方向

推荐定位：**先验证能力与交付，再授予有限权限的 BNB Agent 市场。**

优先顺序是：真实同类选择 → 清晰证据边界 → 可复现任务结果 → 稳定演示，而不是再加治理币、跨链、复杂 Agent 数量或不可验收的密码学名词。

本次补丁把比较、证据新鲜度、失败关闭、收益数学、付费重放和盲测材料生成落到代码；它不会自动获得第二家供应商、真实付费记录、独立评审或比赛奖项。完整施工顺序见 `BLUEPRINT.zh-CN.md`。

## 来源索引

来源等级：A=官方规则/规范；B=项目原始材料；C=作者公告。B/C 只证明该作者公开宣称或仓库存在相应实现，不自动证明上线效果。

| ID | 来源 | 可复核位置 |
|---|---|---|
| S1 / A | BNB 当前赛事页 | `https://www.bnbchain.org/en/hackathons/smart-money-era` |
| S2 / A | 官方主赛说明博客 | `https://www.bnbchain.org/en/blog/build-the-era-build-the-official-bnb-agent-studio-marketplace` |
| S3 / A | Agent Family 活动页 | `https://www.agent.family/campaigns/bnb-build-the-era` |
| S4 / B | HIREDESK README | `https://github.com/timmyspurs12/hiredesk/blob/main/README.md` |
| S5 / B | HIREDESK 执行路由 | `https://github.com/timmyspurs12/hiredesk/blob/main/src/app/api/jobs/[id]/execute/route.ts` |
| S6 / B | minia2a pitch deck | `https://minia2a.uk/hackathon/bnb-pitch-deck.html` |
| S7 / C | SmartSentinels 作者公告 | `https://www.linkedin.com/posts/andrei-galea_bnbchain-web3-aiagents-activity-7494835646889615362-hPjU` |
| S8 / A | 历史 OpenClaw 获奖页 | `https://www.bnbchain.org/en/hackathons/good-vibes-only-openclaw-edition` |
| S9 / B | SafeHire 锁定版本 catalog | `https://github.com/seekitx/safehire-proofops-bnb/blob/267e4978c56adc2c566ab82fc134b18b0a5a7708/evidence/marketplace/live-agent-catalog.json` |
| S10 / A | ERC-8004，尤其 getAgentWallet | `https://eips.ethereum.org/EIPS/eip-8004` |
| S11 / A | JSON-RPC | `https://ethereum.org/developers/docs/apis/json-rpc/` |
| S12 / A | EIP-1898，精确区块绑定 | `https://eips.ethereum.org/EIPS/eip-1898` |

没有查询到完整官方参赛/决赛名单；没有独立确认竞争者的营收、用户量或最终主网交付，因而本报告只能支持能力与策略差异判断，不能支持确定冠军排名。
