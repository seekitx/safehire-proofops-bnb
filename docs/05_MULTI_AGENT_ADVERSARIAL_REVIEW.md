# 多角色对抗评审

## 结论

“多 Agent”在这里不是多个聊天窗口，而是七个利益不同的评审角色同时拆方案。它们只输出评审意见，确定性门禁仍然是最后裁决者。

## 七个角色

| 角色 | 主要质疑 |
|---|---|
| Product judge | 用户是否在 30 秒内明白价值 |
| Sponsor judge | BNB/Pancake/TermiX 是否真正影响产品，还是硬贴 logo |
| Smart-contract reviewer | 重放、越权、无限授权、过期和撤销 |
| Backend reliability reviewer | 冪等、并发、重试、RPC 故障和数据污染 |
| Evidence auditor | 是否把 fixture、自报分、索引分当成链上事实 |
| Adversarial user | 参数边界、过期会话、账户切换、重复点击、恶意 JSON |
| Demo editor | 五分钟内是否只展示可复核主线 |

## 评审协议

1. 所有角色拿到同一份 proposal，不先看其他人结论。
2. 每个角色输出 `severity / finding / evidence / remediation`。
3. P0 表示会造成资产损失、伪证据或无法参赛；有 P0 即拒绝。
4. 意见冲突时，安全和证据要求优先于演示效果。
5. 决策和少数意见一起写入 `evidence/judging-notes/`，不只保留漂亮的部分。

## 本项目的关键裁决

- 拒绝“所有 Agent 共用一个高分”：不同类别保留专属指标，AgentProof 只做共同证据上限。
- 拒绝“演示 hash 就是交易”：demo receipt 永远标 `demo_fixture`。
- 拒绝“Universal Router = LP 调仓”：第一个写链动作只做小额 swap，LP 保持建议。
- 拒绝“模型决定能不能付钱”：RiskGate 不接收 LLM 覆盖。
- 拒绝“一次钱包登录就永久授权”：会话、policy、人工批准是三个不同层级。
