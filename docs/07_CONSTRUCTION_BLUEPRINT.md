# 建设蓝图

## 已完成的代码层

1. 可调用四类 Agent 和严格输入校验。
2. AgentProof 证据上限、类别指标和 fixture 惩罚。
3. 钱包 challenge/session，权限和任务 SQLite 持久化。
4. 创建、预演、批准、执行、回执、撤销状态机。
5. 本地 demo adapter 和 HTTPS remote Agent adapter。
6. BSC RPC 状态/交易回执验证。
7. 8004scan、Venus、Lista 公开读适配器，Pancake V3 subgraph 带 key 适配器。
8. 严格 TermiX 报告生成器和 BSC 证据抓取工具。
9. 三个 Solidity 合约、Hardhat 编译/测试/部署脚本。
10. 无构建 Web UI、Docker 和 fail-closed 提交门禁。

## 外部实施顺序

### 第 1 阶段：公开代码与页面

- 创建公开 GitHub 仓库，启用 CI。
- 部署 FastAPI 至 HTTPS，设置强随机 `ADMIN_API_KEY`。
- 从外网无登录打开首页、Agent Card、OpenAPI 和 health。
- 更新 `PUBLIC_BASE_URL` / `GITHUB_REPO_URL`。

### 第 2 阶段：Agent Studio

- 按官方当前版本安装 `bag`，保存 `bag --version` 和 help。
- 新建独立 TypeScript Agent workspace，不改成伪 Python Studio。
- 实现 A2A/MCP card 和 seller `runWork`；签名在确定性 `signing.ts`。
- 部署并用 `bag deploy verify`、`scan`、audit 确认。
- 将四个 endpoint 写回 `config/agents.json`。

### 第 3 阶段：身份、雇佣和支付

- 有稳定 URL 后再注册 ERC-8004，用 resolve + 8004scan + RPC 回读。
- 跑一个完整 ERC-8183 job：create/fund/notify/submit/fetch/settle。
- 如冲 B402 奖项，申请商户账号、RSA 凭据和固定出口 IP；正价付费才算。

### 第 4 阶段：最小写链

- 仅使用一次性 BSC Testnet 钱包和小额 tBNB/token。
- 先部署合约，保存 deployment manifest 并从 BscScan 复核。
- 第一个动作只做 allowlisted Pancake V3 testnet swap；先 `eth_call`/估 gas，再人工确认。
- 用 `capture_bsc_evidence.py` 抓真实回执。

### 第 5 阶段：证据和提交

- 跑至少三个 TermiX 同题对照，让独立人按同一标准评分。
- 录制 5 分钟内视频，包含一条成功和一条拒绝路径。
- 补 `submission/submission.json`，运行 `submission_gate.py`。
- 最后用隐身窗口和新设备检查所有公开链接。
