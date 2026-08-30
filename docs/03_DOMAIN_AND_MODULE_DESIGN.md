# 领域与模块设计

## 核心对象

- `AgentDescriptor`：Agent 身份、类别、endpoint、链、合约、指标和证据。
- `EvidenceRef`：证据等级、来源、tx hash、chain id、时间。
- `ProofBreakdown`：加权分、证据上限、扣分和优点，不把不同策略的收益横向乱比。
- `PermissionPolicy`：owner、agent、chain、target/method allowlist、额度、slippage、到期和撤销。
- `TaskRecord`：从 draft 到 simulated、approval_required、approved、executing、succeeded/failed/revoked。
- `ExecutionIntent`：执行前的完整快照，包含冪等 key 和数据来源。
- `ExecutionReceipt`：链、hash、gas、成本、数据来源和原始结果。

## 四类 Agent

| 类别 | 输入 | 输出 | 关键保护 |
|---|---|---|---|
| Rebalancing | 价格区间、波动、APR、流动性、成本、本金 | rebalance/hold 及可解释计算 | 区间校验、成本收益阈值 |
| Grid trading | 上下界、层数、资金、回撤限制 | 几何网格和单笔资金 | 层数、回撤上限，不承诺收益 |
| Yield | 至少两个协议、APY、风险、TVL、交易成本 | 风险调整后排名 | 扣交易成本、惩罚风险分 |
| Health factor | 抵押、债务、清算阈值、告警/目标 HF | monitor 或 repay/add collateral | 正债务、阈值范围、只读优先 |

## 数据来源规则

`demo_fixture`、`benchmark_generated`、`testnet_evidence`、`live_onchain` 是不同等级，不得混用。官方 API 只做发现，影响资金的关键值必须用同一块高的 RPC 或官方 SDK 复核。上游格式变了就报错，不在后台换成 fixture。

## 不变条件

1. 没有预演不能执行。
2. 要求人工批准时，没批准不能执行。
3. 过期、撤销、kill switch、超 target/method/额度/slippage 任意一项即拒绝。
4. BSC mainnet 默认关闭。
5. 每个创建和执行都有冪等 key。
6. LLM 可以解释或质疑，不能改分或绕过 RiskGate。
