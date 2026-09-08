# 外部代理候选核查（2026-09-08）

结论：优先使用 Brain 已实际返回结果的只读查询；尚无证据足够且兼容 SafeHire、可立即建议再次付费的替代代理。找到确实存在历史有效交付的替代供应商 ChainHelix，但还不能把它称为当前已验收可用。其较新的四笔已结算订单，原文全部是输入错误；不能再根据“在线、已接单、已结算”让用户付款。已停留 FUNDED 的 BNB LP Range Rebalancer #265375 不列为推荐。

本报告只进行了公开检索、供应商只读 HTTP 和 BSC 只读 RPC 查询；未下单、付款、签名、发送私人消息或执行交易。核查窗口约为 2026-09-08 11:00–11:20 北京时间。资料中出现的价格是当时页面展示，非付款授权。

## Brain 本轮主任务实测补充

以下由同一任务的主代理独立实查，原始记录存放于本地忽略目录 `.data/provider-search-2026-09-08/brain-independent-proof.json`：

- 历史 [56657](https://agent.brainonbnb.com/job?id=56657&format=json)：BSC RPC 返回 status=3、预算 1e17，原始 result 的 SHA-256 与其对应记录匹配，证明一笔历史已完成交付。
- [LP 仓位读取](https://agent.brainonbnb.com/lp/look?position=7319347)：本轮请求 1.71 秒返回 200，包含实际仓位结果，测量时间 03:17:07 UTC。它是目前可以先使用的只读能力。
- `/example?service=health_factor` 返回当日报告，但这是例子接口，不是本次指定钱包的运行证明。
- SafeHire 向 health agent #302257 请求报价，仍因缺少完整签名包失败；不能为它绕过付款校验。
- 对池 `0x36696169c63e42cd08ce11f5deebbcebae652050` 的 range-plan 请求实际返回 503，原因是日志查询范围被上游拒绝；不能把整个服务宣传为全部可用。
- `/dispatch` 虽 8.59 秒返回 200，实际 `answered_by` 是同一 172 服务器的 LendingGuardian #266933，不能归为 Brain 自营的独立替代交付。

## 候选比较

| 候选 | 核查到的原始证据 | 目前判断 |
|---|---|---|
| ChainHelix Portfolio Rebalancer #269223 | 官方卡可读；历史 #56603 有有效交易量计算；BSC 主网 COMPLETED、0.1 U、原文哈希与链上一致 | 可以继续做不付费的输入兼容和实时试运行；尚不能保证新订单交付 |
| ChainHelix Grid Trader #269224 | 历史 #56612 有 16 层具体价格/金额的网格；主网 COMPLETED、0.1 U、原文哈希与链上一致 | 有历史有效计算；同一运营方，不能算第二家独立企业 |
| ChainHelix Health Factor Monitor #269228 | 历史 #56613 输出健康系数、预警及单资产清算价；主网 COMPLETED、0.1 U、原文哈希与链上一致 | 输入由调用方提供，不是自动读取用户 Venus 仓位；新输入须先验证 |
| AgentCensus Health Factor Monitor | 自家站点在线；目录显示历史付费，但当前 ERC-8183 接口不可用；主任务实查 /erc8183 为 404 | 不推荐付款。目录在线不是卖家运行正常 |
| Otto AI Market Alpha | 官方文档列 ACP、x402、DApp 三种渠道和市场/收益分析服务 | 可作为跨协议研究后备；没有在本轮证明当前 BNB SafeHire ERC-8183 接入、报价、任务绑定与原始完成订单，不能直接替换 |

ChainHelix 当前首页显示四个服务每单 0.5 U；历史样例为 0.1 U。原始卡写明不提供卖家后台任务查询，而市场层另有 `/api/jobs/<id>` 读取链上状态。两者都不是可查看内部执行进度的凭据。

## ChainHelix：历史交付的独立核验

供应商原始来源：

- [市场与历史完整记录](https://agents.chainhelix.io/)
- [历史交易 JSON](https://agents.chainhelix.io/api/trace)
- [交付校验 JSON](https://agents.chainhelix.io/api/delivery)
- [Rebalancer agent card](https://agents.chainhelix.io/rebalancer/.well-known/agent-card.json)

本轮通过 `https://bsc-dataseed.bnbchain.org` 对官方 Commerce `0xEa4DAa3100A767e86FDed867729ae7446476EBA6` 调用 `getJob(uint256)`，取得状态、买卖家、任务、金额及 deliverable。对下面三个 URL 的完整响应字节计算 keccak256，均等于链上 deliverable。没有仅相信供应商写的 `verified:true`。

| Job | 原始交付 | 独立核验与内容 |
|---|---|---|
| 56603 | [response](https://agents.chainhelix.io/rebalancer/erc8183/job/56603/response) | status=3，预算 100000000000000000；原文哈希匹配。输入 BTC 0.5、ETH 8、价格 64000/1900，输出总额 47200、卖 BTC 0.13125、买 ETH 4.42105263。是计算结果，不是简单回显 |
| 56612 | [response](https://agents.chainhelix.io/gridtrader/erc8183/job/56612/response) | status=3，同金额；原文哈希匹配。输入价格 605.5、预算 10000、每侧 8 层、跨度 6%，生成 16 个价格和每层 625 的网格，并标记给定价格墙 |
| 56613 | [response](https://agents.chainhelix.io/healthmon/erc8183/job/56613/response) | status=3，同金额；原文哈希匹配。输入抵押、债务、价格与清算阈值，算 HF=1.3292、warning、BTCB 单资产清算价 44230.66666667 |

这三个订单买家都是 `0x9d16bb4b2ed89aafc8390998ed2d3254af6e513b`，供应商明确标为自己的测试钱包。它们证明历史付款及计算交付，不证明陌生用户体验、独立客户需求、投资收益或当前服务持续正常。

SHA-256（完整原始交付字节）：

- 56603: `4b1e24d3869cb84e1d039f9569077a8c95a0e5dfaad95518fb66961417d0cb03`
- 56612: `0280545be508f8800efe4adac9d122970a1f35c2136dc89020618539a531078f`
- 56613: `0a54ecb209f2e3500ec42e312d84baead0fa2da64733fd7249a0343ad25b4327`

## 必须保留的反证

供应商 `/api/trace` 把 56652–56655 列为 COMPLETED，其交付校验也显示 verified；本轮直接读取原文发现：

- [56652 rebalancer](https://agents.chainhelix.io/rebalancer/erc8183/job/56652/response)：`ok:false`，holdings 格式错误。
- [56653 gridtrader](https://agents.chainhelix.io/gridtrader/erc8183/job/56653/response)：`ok:false`，price 不是有限数字。
- [56654 yieldopt](https://agents.chainhelix.io/yieldopt/erc8183/job/56654/response)：`ok:false`，pools 格式错误。
- [56655 healthmon](https://agents.chainhelix.io/healthmon/erc8183/job/56655/response)：`ok:false`，collateral 格式错误。

因此“已结算”和“字节未被篡改”不能证明交付有用。历史输入支持对象，但较新错误信息要求数组，当前卡又列对象，存在版本或输入协议变化的疑点。未查明前，不应让用户再为同类风险试错。

## 其他来源与边界

- [Brain Plaza registry](https://brainonbnb.com/registry) 用于发现候选，非官方信誉评分；它列的旧报价与当前 ChainHelix 页面已不同。不可直接复制目录的成功率为验收结论。
- [AgentCensus](https://agentcensus.xyz/) 默认测试网，必须显式区分主网；网站可打开不代表其健康监测卖家路径可工作。
- [Otto 官方接入说明](https://ottowallet.mintlify.app/acp-swarm/access-paths) 列市场分析服务，提到 ERC-8183-ready；这不等于已接入 SafeHire 当前主网合约。
- [BNB 官方 SDK 文档](https://docs.bnbchain.org/developer-kit/bnbagent-sdk/) 说明服务框架与争议/提交机制，是协议依据，不是任一代理履约保证。

下一步应优先让一个候选对符合其公开输入规范的明确任务返回实际样例，再核对有效签名、现行输入版本和如何读取原文。完整满足后，才让用户审阅一笔具体新订单。不得要求候选生成其未实现的 `safehire-proposal/2` 后仅凭泛化签名推定它支持。
