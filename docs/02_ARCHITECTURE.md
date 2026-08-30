# 总体架构

## 结论

市场和风险核心保持 Python 模块化单体，写链职责交给独立的 BNB Agent Studio TypeScript 运行时。这样评委路径简单，而私钥、支付和签名不会进入 Web 核心。

```text
Browser wallet
    |
    | sign-in only / explicit approval
    v
FastAPI marketplace -------------------- Official read-only sources
    |                                      8004scan / Pancake / Venus / Lista
    | cards, compare, policy, tasks
    v
Deterministic risk gate
    | allow only after simulation + approval
    v
Remote Agent Studio endpoint ----------- ERC-8004 / ERC-8183 / x402
    |
    | signed BSC Testnet transaction
    v
BSC RPC + BscScan receipt
    |
    v
Hash-chain evidence ledger + EvidenceAnchor
```

## 心跳与数据边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| Web UI | 发现、比较、填限额、批准、撤销、看回执 | 保存私钥 |
| FastAPI | 会话、权限、任务、证据、公开 API | 绕过钱包操作用户资产 |
| Agent engine | 可重放的建议和计算 | 最终授权 |
| RiskGate | 以确定性规则决定能否执行 | 依赖 LLM 判断 |
| Agent Studio | 签名、A2A/MCP、ERC-8183、x402/B402 | 管理市场排名 |
| SQLite | 单实例持久化和冪等 | 多区高可用 |
| Evidence ledger | 防篡改事件链 | 单独证明数据内容真实 |

## 请求流程

1. 用户读取 Agent Card 和带来源标签的 AgentProof。
2. 调用 `invoke` 仅生成预演，不创建交易。
3. 钱包签名一次性 challenge，得到 60 分钟会话；该签名不是链上交易。
4. 用户创建只包含允许 target/method、单次/日额度、slippage、到期时间的 policy。
5. 任务先预演，再进入 `approval_required`；必须单独批准。
6. 执行前 RiskGate 重新检查所有条件。
7. demo adapter 只返回明确标记的假 hash；生产 adapter 只调 HTTPS Agent endpoint 并要求真实 tx hash。

## 部署形态

- 本地：一个 FastAPI 容器 + 持久数据卷，`EXECUTION_MODE=demo`。
- 比赛：公开 FastAPI + 独立 Agent Studio endpoint + BSC Testnet，`remote_agent` 适配器。
- 生产化后：SQLite 换 PostgreSQL，增加 queue/outbox、多 RPC、监控和密钥管理。本次不应为黑客松过度拆微服务。
