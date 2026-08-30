# U、USDT/USDC 与本场比赛的关系核对

核对日期：2026-08-30

## 结论

当前公开的 BNB Chain「The Smart Money Era: Build the Era」规则，没有要求参赛者持有或使用 U、USDT、USDC。现在不领取 U 是正确决定。

原始 SafeHire / ProofOps 设计中的 USDT、USDC，是用户要比较收益、监控风险或执行 DeFi 策略的资产；它们不是 Agent 的雇佣付款币。后续接入 BNB Agent Studio 后，当前 `studio.toml` 才把 ERC-8183 付费雇佣配置成 0.1 U。

## 三种币不能混为一谈

| 名称 | 当前项目中的用途 | 是否为同一种币 |
|---|---|---|
| USDT / USDC | DeFi 收益比较、资金池、借贷和风险分析的用户资产 | 否 |
| U | BNB 当前 ERC-8183 / B402 付费轨道使用的 United Stables 代币 | 否 |
| tBNB | BSC Testnet 的 Gas，也就是支付链上操作手续费 | 否 |

当前 BSC Testnet 合约 `0xc70B8741B8B07A6d61E54fd4B20f22Fa648E5565` 的链上 `name()` 是 `United Stables`，`symbol()` 是 `U`，精度为 18。它不是 USDT，也不是 USDC。BNB 官方 `mpp-sdk` 也把 BSC 主网的 `U` 与 BSC Testnet 的 `TEST_USDT` 分成两个独立资产。

官方仓库 `apex-contracts` 的 README 曾把上述测试网地址写成“USDC on testnet”，但 BNB 官方 SDK、水龙头和合约链上元数据都把它识别为 United Stables U。因此，实际集成必须以运行时合约和当前 SDK 为准，不能把那句旧标签当作币种事实。

## 比赛要求

- 主赛要求公开可用的 Agent 市场、完整的发现到激活路径、实时准确数据、四类 Agent 同等深度，并要求展示的 Agent 已在 BSC 上线；没有规定必须收费，也没有规定支付币种。
- Altana 奖要求受限 Session、Session Key 真实链上交易和用户可撤销权限。ERC-8183 雇佣和 x402/B402 只列为 Bonus，不是资格门槛。
- TermiX 奖要求至少三组真实的 Agent 与人工对照任务，并记录时间、成本和输出质量；没有要求 U、USDT 或 USDC。
- PancakeSwap 奖要求给交易者或 LP 带来真实价值；没有指定必须持有哪一种稳定币。

因此，报名、主奖和当前三个伙伴奖都不要求领取 U。

## 当前项目为什么会出现 U

当前 `agent-studio/safehireagents/app/agent/studio.toml` 配置了：

- ERC-8183 固定价格 `0.1 U`；
- B402 卖方当前设为 `0 USD` 免费直通，避免缺少 Binance 商户凭据时阻塞主 Agent；它不算付费 B402 证据。真正的付费演示仍是 ERC-8183 的 `0.1 U`。

这意味着：如果保留“真实付费雇佣并托管”的演示路径，买方钱包才需要 U。它是后续实现选择，不是原始业务资产，也不是比赛硬要求。

如果本阶段只完成主赛需要的 Agent 发现、比较、激活、链上身份、受控动作和真实数据，可以把付费轨道设为免费或暂不启用，不需要领取 U。这个改动需要单独实施和测试，本次核对没有修改代码。

## 现在的决定

1. 不领取 U，当前钱包 U 余额保持为 0。
2. 保留已领取的 0.3 tBNB，用于部署、注册和测试网交易手续费。
3. USDT/USDC 继续作为产品内的分析和策略资产；只有未来真的执行对应测试网代币交易时，才按具体协议和池子领取正确的测试代币。
4. 只有确定要把“0.1 U 付费 ERC-8183 完整闭环”作为提交证据时，再领取 U。

## 官方来源

- [BNB Chain 本场赛事与赛道规则](https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks)
- [BNB Agent Studio Quickstart](https://docs.bnbchain.org/developer-kit/bnbchain-studio/quickstart/)
- [BNB 官方 bnbagent-sdk](https://github.com/bnb-chain/bnbagent-sdk)
- [BNB 官方 mpp-sdk 资产矩阵](https://github.com/bnb-chain/mpp-sdk)
- [BNB 官方 apex-contracts 部署信息](https://github.com/bnb-chain/apex-contracts)
- [ERC-8183 草案](https://eips.ethereum.org/EIPS/eip-8183)
