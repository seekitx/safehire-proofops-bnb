# 演示与提交

## 五分钟演示脚本

| 时间 | 画面 | 必须说清的话 |
|---|---|---|
| 0:00–0:30 | 首屏 + 问题 | “Agent 能做事，但用户不知道该信谁、该给多少权限。” |
| 0:30–1:15 | 四类 Agent + 比较 | 不同类别保留专属指标，证据弱就被封顶 |
| 1:15–2:00 | 官方数据 + 预演 | 展示 source/block/time，说明预演不会发交易 |
| 2:00–3:00 | 钱包签名 + 限额 | 签名只登录；target/method/额度/slippage/expiry 都可见 |
| 3:00–3:45 | 批准 + BSC Testnet 执行 | 只有单独批准后才进 RiskGate |
| 3:45–4:20 | BscScan 回执 + evidence ledger | 打开真实 tx，不展示 demo hash |
| 4:20–4:40 | 故意超额/撤销 | 展示系统如何拒绝，这比再展示一个成功更有说服力 |
| 4:40–5:00 | TermiX 报告 + GitHub | 给出原始输出 hash、节省时间、质量差值和公开代码 |

## 提交前命令

```bash
python -m pytest -q
ruff check src apps tests scripts
mypy src apps scripts
python scripts/static_security_check.py
(cd contracts && npm test && npm audit --omit=dev)
(cd agent-studio/safehireagents && corepack pnpm install --frozen-lockfile && corepack pnpm --dir app/agent build)
python scripts/submission_gate.py
```

## 屏幕证据清单

- 公开首页和四个 Agent card。
- BSC RPC 实时块高。
- ERC-8004 resolve/8004scan 与 RPC 回读。
- ERC-8183 任务从 funded 到 settled。
- 如申请 x402/B402，显示正价 402 challenge 和付款，不是 price 0。
- 成功 tx、超额拒绝、撤销后拒绝、RPC 失败界面。
- TermiX 三组原始文件和统一评分。

## 绝对不能出现

- 伪造交易 hash、把 demo receipt 改名为 live。
- 视频里手动跳过未完成步骤，却在 README 写“完整闭环”。
- 显示私钥、wallet password、API key、B402 凭据。
- 把 8004scan score、API 返回的 APY 或自报成绩当成无需复核的链上事实。
