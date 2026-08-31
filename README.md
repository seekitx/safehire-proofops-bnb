# SafeHire / ProofOps for BNB Chain

SafeHire 是一个 BNB Chain DeFi Agent 市场与权限防火墙。用户先比较工作证据，再给 Agent 一个有目标、方法、金额和时间限制的权限，每次执行还要单独批准，最后保留可复核回执并能随时撤销。

```text
Compare → Preview → Connect wallet → Set limits → Approve → Receipt → Revoke
```

评委公开入口：

- 市场：https://safehire-proofops-bnb.onrender.com
- 链上证据总页：https://safehire-proofops-bnb.onrender.com/proof
- 公开 A2A Agent Card：https://safehire-proofops-bnb.onrender.com/.well-known/agent-card.json
- GitHub：https://github.com/seekitx/safehire-proofops-bnb

## 当前已经有的真实证据

- BSC Testnet 已部署 `AgentRegistry`、`EvidenceAnchor`、`ScopedExecutionPolicy` 三个合约，部署回执和链上代码均已回读。
- 已在官方 ERC-8004 Registry 注册 Agent #2032，owner、Agent 钱包和公开 URI 已回读校验。
- 已完成官方 ERC-8183 Job #808：签名报价、0.1 U 托管、Agent 交付、15 分钟异议窗口、结算和 Agent 收款全部在 BSC Testnet 有成功回执。
- `/proof` 是给评委看的公开证据总页，会展示 7 笔 Job 回执、ERC-8004 身份、交付物和三个合约的 BscScan 入口。

对应原始证据：[ERC-8183 Job #808](evidence/sponsor-integration/erc8183-job-808.json)、[ERC-8004 注册](evidence/sponsor-integration/erc8004-registration.json)、[Agent Studio 部署](evidence/sponsor-integration/agent-studio-deployment.json)、[BSC Testnet 合约](deployments/bsc-testnet.json)。

## 本地产品能力

- 四个本地可调用的确定性演示 Agent：LP 区间调整、网格、收益优化、健康因子。
- 按类别比较的 AgentProof；证据弱或仅是 fixture 时自动限分。
- 钱包签名 challenge/session，钱包私钥不进后端。
- 持久化 permission/task，覆盖预演、人工批准、风险门、执行、回执和撤销。
- target/method allowlist、单次/每日额度、slippage、expiry、idempotency、kill switch。
- 8004scan、Venus、Lista 官方只读适配器；PancakeSwap V3 官方 subgraph 适配器。
- BSC RPC 链身份、块高和交易回执验证。
- 可防篡改的 hash-chain 证据账本。
- 严格 TermiX “Agent vs 人工”原始证据报告生成器。
- `AgentRegistry`、`ScopedExecutionPolicy`、`EvidenceAnchor` 合约，含 Hardhat 编译、测试和 BSC Testnet 部署脚本。
- 官方 `@bnbagent/studio-cli@0.0.13` 生成的 A2A + MCP + X402 卖方 Agent，已接通 SafeHire 只读预演。
- 完整 Web 评委路径、FastAPI、Docker、CI 和 fail-closed 提交门禁。

## 真实 BSC Agent 市场供给

首页会展示四个由外部运营方 `Brain On BNB AI` 在 BSC mainnet 注册的 ERC-8004 Agent，分别覆盖调仓、网格、收益优化和健康因子四类能力。`GET /api/live-market` 每次只调用免费的 A2A `list` 发现接口，不会签名、充值或创建 ERC-8183 订单。

这部分证明的是“真实 Agent 可被发现”，不是“SafeHire 已验证它们的质量”。当前还没有为这四个外部 Agent 支付主网 `0.10 U`，也没有把它们的交付输出写进 TermiX 报告。

每次提交前要用只读链上检查刷新这份证据：

```bash
PYTHONPATH=src python scripts/refresh_live_agent_catalog.py
```

脚本会确认 BSC mainnet chain id、四笔注册交易都成功，并且四个 skill 仍在 A2A 免费列表里。它不会签名或发起付费。

## 诚实边界

开箱默认是 `demo` 模式。demo receipt 有合成 hash，但永远标记 `demo_fixture`，不会被提交门禁当成 BSC 交易。当前 `config/agents.json` 里四个类别卡片仍是本地演示 Agent；它们与首页上方的外部 BSC mainnet Agent 分开展示。Job #808 证明了 SafeHire 一次真实的注册和雇佣闭环，不代表已验证外部 Agent 的交付质量。

原 BNB 托管 Agent Studio 卖方运行时是 48 小时试用，到期时间是 2026-09-01T13:54:15Z，只作为 Job #808 的历史采证环境。评委期公开入口已换成 Render 上的市场 Agent Card 和只读 A2A 预演桥；它不会伪装成 Agent Studio 签名卖方，也不会保存或使用钱包私钥。

Render 免费实例长时间无访问会休眠，首次唤醒可能需要等待约 50 秒。这不影响链上证据，但对评委首次打开体验有风险；如果要去掉休眠，需要用户另行确认付费方案。

合约未经第三方审计，BSC mainnet 默认禁用。比赛写链只应使用一次性 BSC Testnet 钱包和小额资产。

Agent Studio 的签名仍在官方固定入口中，AI 只能调用只读预演。报价固定为 0.1 U 且有同值上限，自动充值默认关闭。

## 快速启动

需要 Python 3.11+。

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,bnb]'
python scripts/seed_demo.py
uvicorn apps.api.main:app --reload --port 8000
```

打开 <http://localhost:8000>。看 OpenAPI：<http://localhost:8000/docs>。

## 测试

```bash
python -m pytest -q
ruff check src apps tests scripts
mypy src apps scripts
python scripts/static_security_check.py

cd contracts
npm install
npm run compile
npm test
npm audit --omit=dev

cd ../agent-studio/safehireagents
corepack pnpm install --frozen-lockfile
corepack pnpm --dir app/agent build
```

Hardhat 只是开发工具，不进入 Python 运行容器。`npm audit --omit=dev` 用于确认部署产物没有 Node 生产依赖。

## 官方数据接口

- `GET /api/sources/readiness`
- `GET /api/sources/8004scan/agents`
- `GET /api/sources/venus/pools`
- `GET /api/sources/lista/vaults`
- `GET /api/sources/pancakeswap/positions/{position_id}`（需服务端 `THE_GRAPH_API_KEY`）

接口失败会返回错误，不会用演示数据伪装实时数据。影响资金的关键值还必须用 BSC RPC 或官方 SDK 复核。

## TermiX 证据

```bash
cp templates/termix/live-manifest.template.json /tmp/termix-manifest.json
# 改成至少 3 组真实任务并放入原始输出
PYTHONPATH=src python scripts/build_termix_report.py /tmp/termix-manifest.json
```

live 模式会拒绝 fixture/demo 路径、缺文件、无时区时间、占位复核人、全零评分和少于三个任务。三份固定任务在 `evidence/termix/tasks/`，逐笔执行方法见 `docs/TERMIX_EXECUTION_RUNBOOK.md`。Venus 输入可用 `PYTHONPATH=src python scripts/capture_venus_yield_snapshot.py` 重新抓取，但刷新后必须同步冻结任务文件里的数值，不能让 Agent 和人工看到不同输入。

## PancakeSwap 真实路由收益证据

`scripts/capture_pancakeswap_live_benefit.py` 会在同一个 BSC mainnet 区块，从 PancakeSwap 官方 V3 Factory 发现 WBNB/USDT 的直连手续费池，再用官方 QuoterV2 比较 `0.1 WBNB` 的输出。当前报告保存在 [evidence/pancakeswap/live-benefit-report.json](evidence/pancakeswap/live-benefit-report.json)，记录了区块、四个池、报价、选择结果和风险边界。

```bash
PYTHONPATH=src python scripts/capture_pancakeswap_live_benefit.py
```

这是真实主网只读报价，不是交易或利润承诺。实际交易前仍要刷新 quote，并经过 slippage、deadline、allowance 和钱包确认。

## 合约部署

```bash
cd contracts
# Inject BSC_DEPLOYER_PRIVATE_KEY from a secret manager or hidden shell prompt.
export BSC_TESTNET_RPC_URL='https://bsc-testnet-dataseed.bnbchain.org'
export POLICY_EXECUTOR='0x...'
export POLICY_TARGET='0x...'
export POLICY_SELECTOR='0x12345678'
export POLICY_MAX_PER_CALL_WEI='0'
export POLICY_MAX_TOTAL_WEI='0'
npm run deploy:testnet
```

部署脚本锁定 chain id 97，默认拒绝覆盖已有 deployment evidence。不要把真实私钥写入 `.env.example`、shell 历史、日志或 Git。

## 抓取真实 BSC 回执

```bash
python scripts/capture_bsc_evidence.py 0xREAL_TX_HASH \
  --chain-id 97 \
  --label bounded-test-swap
```

该工具只读 RPC，不需要私钥。交易找不到或失败时不会生成证据文件。

## 提交门禁

```bash
PYTHONPATH=src python scripts/submission_gate.py
```

线上环境配置好公开 URL 后，主赛 `P0` 应该全部通过。本地 demo Agent 的未上链状态仍是 `P2` 明示警告，四类实时市场供给由独立的 ERC-8004/A2A 证据门检查。PancakeSwap 同区块 V3 路由收益报告已通过 `P1`，当前伙伴奖只剩 TermiX 三组真实对照。演示视频是 `P2` 可选加分项，不是官方表单硬门槛。

## 距离正式提交还差什么

1. 提交前重新抓取四个外部 Agent 的 ERC-8004/A2A 状态；如果要声称已验证质量，还要用主网资产真实雇佣并保存交付回执。
2. 真实跑完 TermiX 三组 Agent/人工同题对照；PancakeSwap 已有真实同区块 V3 报价收益证据，提交前再刷新一次。
3. 用无登录窗口检查所有链接，最后由用户核对姓名、邮箱、联系方式、领奖钱包和参赛条款并提交官方表单。

## 仓库结构

```text
apps/api                 FastAPI 公开 API 和组装根
apps/web                 无构建评委页面
src/proofops/agents      四类可调用 Agent
src/proofops/domain      领域对象和不变条件
src/proofops/execution   权限、任务、风险门和执行适配器
src/proofops/integrations BSC 与官方数据源
src/proofops/evidence    TermiX 证据构建
src/proofops/harness     插件生命周期和 trace bus
contracts/src            Solidity 合约
contracts/test           Hardhat 合约测试
agent-studio/safehireagents 官方 BNB Agent Studio 卖方运行时
docs                     要求、架构、安全、演示、运维和最后清单
evidence                 演示与真实证据的明确分区
templates                部署、TermiX 和提交模板
```

## 先看哪些文档

1. [官方实施资料](docs/00_OFFICIAL_IMPLEMENTATION_REFERENCES.md)
2. [比赛要求映射](docs/01_COMPETITION_REQUIREMENTS.md)
3. [总体架构](docs/02_ARCHITECTURE.md)
4. [建设蓝图](docs/07_CONSTRUCTION_BLUEPRINT.md)
5. [演示与提交](docs/08_DEMO_AND_SUBMISSION.md)
6. [外部完成清单](docs/10_EXTERNAL_COMPLETION_CHECKLIST.md)
