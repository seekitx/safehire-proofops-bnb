# SafeHire 正式提交前的人工门槛

## 现在不要做的事

- 不要把私钥、助记词、密码或 API key 粘贴进页面、聊天或 GitHub。
- 不要给 `U` token 无限授权。新流程只生成精确 `0.10 U` 授权。
- 不要把 PancakeSwap 只读报价写成真实成交或利润。

## 1. 外部 Agent 真实付费交付

1. 等待这批代码通过检查并部署后，从首页选一个外部 Agent，取得当前报价，进入 `/hire-live`。
2. 钱包只保留演示所需的小额 BNB Gas 和 `0.10 U`。这里的 `U` 是合约 `0xcE24439F2D9C6a2289F741120FE202248B666666`，不是 USDT 或 USDC。
3. 连接 BSC Mainnet，确认任务 JSON 不含秘密，先生成只读计划。
4. 逐笔人工确认：Create job → Bind policy → Set budget → Approve exactly 0.10 U → Fund escrow。
5. 点击通知 Agent，等待链上交付。检查交付内容后，再决定结算。过期且未交付时才走退款。
6. 下载 JSON 回执，另存 BscScan 链接和交付全文。

## 2. TermiX 真人计时和盲评

1. 在 `/benchmark` 选择任务，输入真实操作者名称，点击开始后才做无 Agent 工作。
2. 完成后下载 manual JSON，不要修改开始、结束和耗时字段。
3. 准备同题的完整 Agent JSON 和 manual JSON，生成盲评包与秘密映射。
4. 只把盲评包发给另一位评审人。评审人完成五项 1–5 分后下载 review JSON。
5. 收回 review 后才用 `scripts/unblind_termix_review.py` 与秘密映射合并。

## 3. 外部供给和真实使用

- 用首页 `OPEN MARKET INTAKE` 输入第二个独立运营方的 ERC-8004 token ID。读取档案不等于通过审核。
- 请一位外部用户或 Agent 提供方走完主路径，留下可公开的任务回执、GitHub issue 或简短评价。

## 4. 发布和官方提交

1. 先运行项目检查，再推送 GitHub，等待 Render 远程构建完成。
2. 用无登录窗口重走首页、实时报价、主网雇佣、证据页和评测实验室。
3. 录制 2–3 分钟单线演示：外部 Agent → 证据与风险 → 0.10 U 托管 → 交付 → 结算/退款 → 回执。
4. 用户最后核对姓名、联系方式、领奖钱包和参赛条款，亲自点击官方 `Submit`。
