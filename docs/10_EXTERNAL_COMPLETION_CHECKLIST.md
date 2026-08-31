# 需要用户账号、钱包或真人的最后清单

## 结论

以下步骤不能在没有你授权的情况下真实完成。代码、模板、验证工具已准备好；做完一项就运行提交门禁，不要一次性填假数据。

## 按顺序执行

- [x] 核对官网截止时间、当前表单和已公布赛道要求；地区/KYC/领奖审核细节仍等主办方后续通知。
- [x] 已创建公开 GitHub 仓库并推送代码；私密 `.env`、私钥、wallet/session 文件仍被忽略。
- [x] 已创建 Render 公开 HTTPS 部署，评委无需 VPN/登录即可打开；免费实例有休眠冷启动风险。
- [x] 用官方 `@bnbagent/studio-cli@0.0.13` 生成 Agent Studio TypeScript workspace，并完成 SafeHire 只读能力接入。
- [x] 已在 `.studio/.env.local` 配置并使用一次性 BSC Testnet Agent 钱包；该目录仍被 Git 忽略。
- [x] 已部署并验证 BNB 48 小时试用 Agent endpoint，并把评委期只读 Agent Card/A2A 预演桥改为 Render 公开托管；历史签名卖方与长期只读端点没有混为一件事。
- [x] 已在 BSC Testnet 获得并使用小额 tBNB 和 U，不需再为已完成的 Job 领币。
- [x] 已部署三个合约，并保存 BscScan 交易和 deployment manifest。
- [x] 已注册 ERC-8004 Agent #2032，并回读 owner、Agent 钱包和公开 URI。
- [x] 已完成 ERC-8183 Job #808，保留 create/register/budget/approve/fund/submit/settle 七笔成功回执。
- [x] 已接入四个外部 BSC mainnet ERC-8004 Agent 的公开身份和 A2A 只读发现；尚未支付主网 0.10 U 或验证输出质量。
- [ ] 如申请 B402 奖项，申请 Binance 商户、RSA 凭据和固定出口 IP，完成一次正价付费。
- [x] 已在同一 BSC mainnet 区块用 PancakeSwap 官方 V3 Factory + QuoterV2 比较四个 WBNB/USDT 直连池，不需 The Graph key；如后续补指定 LP position 才需要 subgraph key。
- [x] 已通过 ERC-8183 Job #808 用 0.1 U 完成一次 BSC Testnet 受控支付和结算；没有做未验证的 LP 自动调仓。
- [x] 固定三份 TermiX 同题任务、原始证据目录、成本字段和防占位校验。
- [x] 保存 Venus 官方索引 API 的 BSC 主网稳定币收益快照，并明确它不能替代链上执行读数。
- [x] 已部署公开 SafeHire HTTPS 接口；原 Agent Studio 试用配置不再被当作评审期长期运行时。
- [ ] 找一位独立复核者，真实跑完三组 Agent/人工同题对照并评分。
- [ ] 可选：录制不超过 5 分钟演示并上传公开链接；当前官方表单没有把视频列为必填。
- [x] 已补 `submission/submission.json`；还要在这次 Render 重新部署后复查线上门禁为 `ready=true`。
- [ ] 从新浏览器/无登录环境打开所有链接，再正式提交。

## 你不用担心的事

本地代码没有要求你把私钥给 FastAPI 或模型。钱包签名登录、合约部署、Agent Studio 签名是三个分开边界。但黑客松合约未审计，仍只能使用一次性测试网钱包。
