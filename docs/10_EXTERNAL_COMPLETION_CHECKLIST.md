# 需要用户账号、钱包或真人的最后清单

## 结论

以下步骤不能在没有你授权的情况下真实完成。代码、模板、验证工具已准备好；做完一项就运行提交门禁，不要一次性填假数据。

## 按顺序执行

- [ ] 确认当届黑客松报名、地区/KYC/领奖资格和截止时间。
- [ ] 创建公开 GitHub 仓库，推送代码，确保无 `.env`、私钥、wallet/session 文件。
- [ ] 创建公开 HTTPS 部署，评委无需 VPN/登录即可打开。
- [x] 用官方 `@bnbagent/studio-cli@0.0.13` 生成 Agent Studio TypeScript workspace，并完成 SafeHire 只读能力接入。
- [ ] 在 `.studio/.env.local` 配置 LLM/存储/平台凭据和一次性测试网钱包（不得提交）。
- [ ] 部署 Agent endpoint，跑 `bag deploy verify`、A2A card、MCP tools、audit。
- [ ] 在 BSC Testnet 领取足够 tBNB/测试 token；如水龙头要求验证，由你手动完成。
- [ ] 部署三个合约，用 BscScan 确认地址和交易，保存 deployment manifest。
- [ ] 注册 ERC-8004，保存 registry、agent id、owner、tx、endpoint，用 resolve/8004scan/RPC 交叉复核。
- [ ] 跑一单完整 ERC-8183 job，保留 funded/submit/settle 证据。
- [ ] 如申请 B402 奖项，申请 Binance 商户、RSA 凭据和固定出口 IP，完成一次正价付费。
- [ ] 配置 The Graph API key，用 Pancake 官方 V3 subgraph 读 position/pool，用 BSC RPC 复核关键块高。
- [ ] 用小额完成一次 BSC Testnet 受控动作，保存真实回执；不做未验证的 LP 自动调仓。
- [ ] 找一位独立复核者，跑至少三组 TermiX 同题对照并评分。
- [ ] 录制不超过 5 分钟演示，上传公开链接。
- [ ] 补 `submission/submission.json`，运行 `python scripts/submission_gate.py`直至 `ready=true`。
- [ ] 从新浏览器/无登录环境打开所有链接，再正式提交。

## 你不用担心的事

本地代码没有要求你把私钥给 FastAPI 或模型。钱包签名登录、合约部署、Agent Studio 签名是三个分开边界。但黑客松合约未审计，仍只能使用一次性测试网钱包。
