# 安全与威胁模型

## 高风险资产

用户资产、Agent 签名钱包、平台 token、B402 RSA 密钥、授权 policy、交易证据和评委信任都是需要保护的资产。黑客松代码未经审计，只允许一次性 BSC Testnet 钱包和小额动作。

## 主要威胁与对策

| 威胁 | 后果 | 现有对策 |
|---|---|---|
| 假钱包会话 | 他人创建/撤销权限 | 一次性 challenge、EIP-191 签名恢复、限时 session、token hash 存储 |
| 重放任务 | 重复执行 | 创建 idempotency 唯一约束、链上 `consumedIntent` |
| 越权目标/方法 | 任意合约调用 | 离链 target/method allowlist + 链上 target/selector allowlist |
| 超额/slippage | 损失扩大 | 单次、当日、总额和 slippage 上限 |
| 过期权限 | 无限期控制 | 服务端和合约双重 expiry，随时 revoke |
| 模型提示注入 | 诱导发交易 | LLM 不持有私钥，RiskGate 不读自由文本授权 |
| 假 live 数据 | 误导评委/用户 | 来源枚举、证据上限、严格 schema、失败不回退 fixture |
| RPC/Indexer 撒谎 | 错误决策 | 索引只发现，关键值用 RPC 回读；部署增加多 RPC |
| 证据篡改 | 无法审计 | JSONL hash chain、原始文件 SHA-256、可选 EvidenceAnchor |
| 秘密泄露 | 钱包/平台失窃 | `.env` 忽略、静态扫描、Agent Studio secret store、不记录完整 token |

## 仍未解决的风险

- Solidity 合约只有自动测试，没有第三方审计。
- SQLite 适合演示，不适合多实例高并发；切多实例前必须换数据库和分布式锁/outbox。
- 数字美元风险额度与链上 native wei 不是同一单位；写链适配器必须固定报价和 token decimals，不能直接把 USD 数值传给合约。
- Agent Studio、ERC-8004/8183、B402 仍在变化；实际 CLI 版本和部署地址必须被保存到证据。
- 对外上线前还需要反向代理 rate limit、WAF、告警和备份恢复演练。

## 上线底线

mainnet 只能在合约审计、独立签名器、金额极小、综合监控、故障演练和用户二次确认都完成后再考虑。黑客松阶段保持 `ALLOW_BSC_MAINNET=false`。

## 2026-08-31 external ERC-8183 buyer hardening

The external mainnet hire path now treats the provider quote and deliverable as
hostile input until verified:

- the buyer recomputes request, response and negotiation hashes;
- the provider signature must recover to the quoted provider (EOA) or pass
  ERC-1271 on BSC Mainnet;
- chain ID, Commerce address, payment token, exact price and quote expiry are
  fail-closed;
- the exact signed JobDescription, including the canonical task input, ERC-8004
  token ID and nonce, is anchored by `createJob`;
- job expiry covers provider ETA, the on-chain dispute window and a safety buffer;
- resumed jobs rebuild policy, budget and allowance progress from BSC state;
- deliverable URLs accept only HTTPS/IPFS, reject non-public DNS/IPs, cap redirects,
  content type and response size, then compare the canonical manifest hash with the
  on-chain commitment;
- success-criteria satisfaction remains a human decision; the client can dispute
  during the policy window or settle only after a final verdict;
- browser activity JSON is explicitly unverified. Paid history is counted only from
  a server-rebuilt dossier that verifies completion and the provider token transfer.

Residual risks remain explicit: public RPC availability, off-chain storage
availability, third-party provider correctness, contract-level vulnerabilities and
lack of an independent audit. Use a disposable low-value contest wallet.
