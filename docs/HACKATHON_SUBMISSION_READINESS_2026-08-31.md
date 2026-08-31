# SafeHire / ProofOps 黑客松提交就绪度

> 当前状态日期：2026-08-31。本文替代同日较早版本中“live card 只有身份链接、没有直接
> 雇佣按钮”的结论；`/hire-live`、benchmark lab 和 provider intake 已经落地。

## 结论

SafeHire 可以作为 **Working MVP** 进入最终准备，但当前
`winner_readiness=conditional_manual_proof_gates`。

它不是因为代码缺一条主流程而 conditional，而是因为下面四类现实证据不能由代码伪造：

1. 外部主网付费交付；
2. 独立真人盲评；
3. 第二运营方；
4. 评审期稳定托管和最终演示。

## 官方主赛映射

| 项目 | 当前判定 | 事实 |
|---|---|---|
| Functionality | Conditional | 发现、quote、`/hire-live`、结算/退款计划和 Job #808 已存在；外部 paid delivery 为 0 |
| Data Quality | Conditional | 当前 A2A 探测、ERC-8004 身份、注册交易、8004scan 信号、raw output hash 可查；结果历史仍薄 |
| Agent Diversity | Conditional | 四个官方类别具有同一六维深度包络；当前 live listing 仍来自一个 operator |

官方没有发布三项数字权重，因此不得使用项目自算“官方总分”。实时判定入口：

- `/assets/judge-scorecard.html`
- `/api/submission/validate`
- `python scripts/judge_scorecard.py --output judge-scorecard.json`

## 已实现的端到端路径

```text
Live ERC-8004 discovery
→ free commercial quote
→ reviewed task input
→ wallet network check
→ ERC-8183 create/register
→ exact budget and allowance
→ fund
→ provider delivery
→ settle or refund
→ verifiable receipt
```

`/hire-live` 会生成并校验交易数据，但每笔写链必须由用户钱包确认。当前没有保存第一笔
外部 mainnet paid delivery，因此不将此路径冒充 paid track record。

## 伙伴奖状态

### TermiX — Conditional

已完成：

- 三组 Agent/no-Agent raw output；
- 输入、输出、时间、成本和 SHA-256；
- 可复现自动规则基线；
- `/benchmark` 的真人计时和隐藏 A/B 工具。

未完成：

- 至少三项真实 human no-Agent timing；
- 另一位真实 reviewer 的 blind review；
- 至少一项最好使用当前 external paid Agent output。

自动规则只能称为 baseline，不能称为 independent research。

### PancakeSwap — Conditional

已完成 live same-block、多档 WBNB 金额、fee tier 和 gas-aware 净改善报告，并保留：

- observed block；
- pool/quote 来源；
- Agent invocation；
- gasEstimate 不是最终 Router gas；
- quote improvement 不是 realised profit。

如能把一次受控 external hire 与该决策绑定，会显著增强“真实用户好处”。

### Altana — Not claimed

没有真实 session-key transaction 和 in-product revoke 证据，因此当前不勾选、不写入 pitch、
不借用 Sponsor logo。

## 最终提交前 P0

1. 用一次性低价值钱包完成一笔 live external `0.10 U` 任务；
2. 保存 create、fund、delivery、settle/refund 和 provider output；
3. 在 benchmark lab 完成三项真人对照；
4. 由另一人不看 mapping 完成 blind review；
5. 完成第二 provider intake 和人工审核；
6. 将 Render/公开服务切换为评审期不休眠方案；
7. 录制 2–3 分钟 Judge Scorecard → Market → Hire → Proof → Benchmark；
8. 无痕窗口验证所有入口；
9. 刷新 48 小时内 live catalog；
10. 参赛者本人核对身份、联系方式、领奖钱包和条款后提交。

## 可提交与可获奖不是同一个门槛

`submission_gate.ready=true` 只说明：

- 必要文件和结构存在；
- 公开地址/证据格式符合本项目门禁；
- 没有 P0 结构阻断。

它不证明：

- 官方已确认资格；
- 外部 Agent 交付优质；
- 有真实用户采用；
- TermiX 人工盲评已经完成；
- PancakeSwap 已产生真实利润；
- 项目一定获奖。

## 当前唯一主叙事

> SafeHire is the proof-carrying marketplace for BNB Chain Agents: compare verified
> work, cap authority, hire through ERC-8183, and settle against a reviewable delivery.

不要再使用“AI trading platform”“four Agent demos”“secure wallet assistant”等更弱、更泛的定位。

## 进一步阅读

- `docs/11_JUDGE_WINNING_STRATEGY_2026-08-31.md`
- `docs/12_ADVERSARIAL_CONSENSUS_2026-08-31.md`
- `docs/PAST_WINNERS_AND_JUDGE_PATTERNS_2026-08-31.md`
- `docs/MANUAL_COMPLETION_GATES_2026-08-31.md`
- `agent.md`
