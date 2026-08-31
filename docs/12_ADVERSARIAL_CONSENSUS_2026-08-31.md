# 十角色对抗评审与最终共识

> 日期：2026-08-31
> 对象：SafeHire / ProofOps 当前主分支状态
> 目标：不是让所有角色给高分，而是让相互冲突的评审要求收敛为一份可以执行、可验证、
> 不伪造现实证据的冲奖方案。

## 评审输入

委员会共同拿到以下事实，不允许各自发明补充事实：

- 四类外部 ERC-8004 Agent 已在 BSC mainnet 注册并能被发现；
- 当前四类来自同一运营方；
- live quote 可返回 `0.10 U` 商业条件；
- `/hire-live` 已实现 ERC-8183 主网交易计划；
- 外部 paid delivery 记录为 `0`；
- BSC Testnet Job #808 已完整结算；
- TermiX 三组 raw pair 与自动规则基线存在；
- human blind review 记录为 `0`；
- PancakeSwap same-block、多档 quote 和 gas-aware 报告存在；
- provider intake 已实现；
- Altana live session-key + revoke 证据不存在；
- Render 免费实例有冷启动风险。

## 第一轮：独立攻击

| 角色 | 认可 | 最强攻击 | 初始要求 |
|---|---|---|---|
| BNB Main Judge | 主线清楚，live hire 已连接 | 路径有实现但没有当前外部 paid outcome | 第一笔真实小额交付 |
| BNB Data Quality Judge | source/freshness 分层优秀 | identity/health 仍不能替代交付质量 | paid history + blind review |
| BNB Diversity Judge | 四类 skill 都有专属输入 | 一个运营方不像真正可选市场 | 第二 provider |
| TermiX Sponsor Judge | raw pair、hash、成本和时间可复核 | 自动规则不是独立质量判断 | 三项真人计时和盲评 |
| Pancake Reviewer | 同区块多档报价可重算 | quote benefit 仍非 realised use | 绑定一次受控真实任务 |
| Altana Reviewer | 权限架构概念契合 | 没有 session tx/revoke，不能申报 | 不申报或完成全套证据 |
| Security Red Team | wallet、policy、approval、kill switch 完整 | 为演示自动化 mainnet 会破坏价值 | 保留逐笔确认 |
| System Architect | modular monolith + isolated execution 合理 | 再加服务/链会增加故障 | 不做微服务扩张 |
| Solo Builder Attacker | 现有骨架已足够 | 同时补所有 sponsor 会耗尽时间 | 只做四个现实证明 |
| Evidence Auditor | live/testnet/sponsored/demo 边界明确 | 旧文档有“没有 hire 页”的过时结论 | 统一索引与状态源 |

第一轮没有安全或官方硬门槛 veto，但没有角色同意“现在已经 winner-ready”。

## 主要冲突

### 冲突一：增加更多功能，还是增加真实采用

- Product/主赛视角最初倾向再加排序、推荐和更多 provider UI；
- Schedule Attacker 认为任何新功能都会挤占现实证据；
- Evidence Auditor 指出，第一笔 paid outcome 会同时给排序、历史、TermiX 和 demo 提供数据。

**裁决：**不新增大功能。先把一笔外部任务完整走通，再用它填充现有界面和证据。

### 冲突二：是否申报 Altana

- Sponsor 视角认为多一个伙伴奖可能增加期望奖金；
- Security/Evidence 视角指出，没有真实 session-key tx 和 revoke，半成品集成会引发质疑；
- Schedule 视角认为全套 Altana 在当前时间窗口中不如完成 TermiX 和 external hire。

**裁决：**当前不申报。只有全套真实证据完成才改变状态。

### 冲突三：是否宣传 TermiX 已证明 Agent 更好

- Marketing 视角希望使用 `73.5 vs 66`；
- TermiX Reviewer 认可其回归测试价值，但认为同一作者自动规则不等于独立评审；
- Evidence Auditor 否决“研究证明”表达。

**裁决：**保留为 `reproducible automated baseline`；真人盲评完成前，winner scorecard
保持 conditional。

### 冲突四：四类是否已经满足 Diversity

- 官方类别覆盖确实完成；
- Marketplace 视角指出四类均来自 Brain On BNB AI；
- Diversity Judge 区分“category diversity”和“supplier diversity”。

**裁决：**四类深度判定 ready；整体 marketplace diversity 判定 conditional，并将第二
运营方列为人工门槛。

### 冲突五：是否在 Judge Scorecard 给一个高总分

- Demo 视角认为单个高分容易传播；
- Data/Evidence 视角指出主赛权重未公开，数字会被误解为官方预测；
- BNB Judge 更关心三项逐一证据。

**裁决：**禁止总分。只输出 criterion status、checks、proof links 和 manual gates。

## 第二轮：让步与收敛

每个角色必须回答“为了共同目标愿意放弃什么”。

| 角色 | 放弃 | 换取 |
|---|---|---|
| BNB Main Judge | 放弃新增聊天入口 | 单线 live hire 演示 |
| Data Quality Judge | 放弃一次性建设完整数据仓库 | 一笔 paid outcome + 清楚 freshness |
| Diversity Judge | 放弃每类立刻两个 provider | 先取得第二独立运营方 |
| TermiX Judge | 接受自动 baseline 继续公开 | 明确边界并补 human blind review |
| Pancake Reviewer | 不要求冒险做大额交易 | 小额、可重算、带回执的真实使用 |
| Altana Reviewer | 不要求本轮集成 | 不允许使用其名称获取虚假加分 |
| Security Red Team | 接受用户多次点击 | 不自动签名、不无限授权 |
| System Architect | 接受模块化单体 | 不拆服务、不重写主干 |
| Schedule Attacker | 接受四项人工动作 | 全部新功能延期 |
| Evidence Auditor | 接受 conditional 状态 | 所有 claim 都有明确证据等级 |

## 最终一致意见

十个角色共同签署以下执行顺序：

1. 保留 Proof-carrying Agent Marketplace 作为唯一定位；
2. 先完成外部 paid delivery；
3. 用该交付参与 TermiX 的一项真实 Agent 路径；
4. 完成三项 no-Agent 真人计时和另一人的 blind review；
5. 引入第二 provider；
6. 稳定托管并录一条 2–3 分钟 wow path；
7. 只刷新文档、scorecard 和提交材料，不继续扩 scope；
8. Altana 保持 not claimed；
9. 每个主网步骤继续由钱包单独确认；
10. 最终提交前用无痕窗口和机器可读门禁双重验收。

## 最终决议状态

```json
{
  "accepted": true,
  "average_score": 89.0,
  "vetoes": [],
  "decision": "accepted_with_manual_proof_gates",
  "winner_readiness": "conditional"
}
```

`accepted=true` 表示方案值得继续并可作为 Working MVP 提交，不表示官方获奖，也不表示
人工门槛已经完成。

## 非谈判项

- 评委路径不能在发现后死路；
- 四类必须同等深度；
- 数据必须带来源、新鲜度和不确定性；
- LLM 不能越过资金门禁；
- demo/sponsored/testnet/paid 不得混淆；
- TermiX raw pairs 必须保留；
- Altana 无真实 tx/revoke 不得申报；
- 自检不得冒充官方分数；
- 外部付费、真人评审和第二 provider 不得由代码伪造。

## 延期范围

- 多链；
- 第五类 Agent；
- 通用聊天；
- 新 token 或激励经济；
- 高级预测模型；
- 自动 mainnet 执行；
- 新合约；
- 无法进入三分钟演示主线的 Sponsor 集成。

## 落地映射

| 共识 | 文件 |
|---|---|
| 十角色实现 | `src/proofops/plugins/adversarial.py` |
| veto/缺口回归 | `tests/test_lp_benchmark_debate.py` |
| 官方 criterion 自检 | `src/proofops/judging/scorecard.py` |
| 评委页面 | `apps/web/assets/judge-scorecard.html` |
| 机器可读输出 | `scripts/judge_scorecard.py` |
| 根行为约束 | `AGENTS.md` |
| 工作索引 | `agent.md` |
| 冲奖策略 | `docs/11_JUDGE_WINNING_STRATEGY_2026-08-31.md` |
| 决议证据 | `evidence/judging-notes/adversarial-consensus-2026-08-31.json` |

## 何时重新开会

下面任何事实变化后必须重新运行对抗委员会并更新决议：

- 新增或移除 official category；
- live hire 路径被改变；
- provider_count 变化；
- paid external deliveries 变化；
- human blind reviews 变化；
- 申报新的 sponsor track；
- 放宽资金权限或签名边界；
- submission gate 出现 P0；
- 官方赛题/评分规则变化。
