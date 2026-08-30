# SafeHire / ProofOps for BNB Chain

SafeHire 是一个 BNB Chain DeFi Agent 市场与权限防火墙。用户先比较工作证据，再给 Agent 一个有目标、方法、金额和时间限制的权限，每次执行还要单独批准，最后保留可复核回执并能随时撤销。

```text
Compare → Preview → Connect wallet → Set limits → Approve → Receipt → Revoke
```

## 已实现

- 四个真正可调用的确定性 Agent：LP 区间调整、网格、收益优化、健康因子。
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

## 诚实边界

开箱默认是 `demo` 模式。demo receipt 有合成 hash，但永远标记 `demo_fixture`，不会被提交门禁当成 BSC 交易。当前 `config/agents.json` 也明确是演示 Agent；在公开 Agent Studio endpoint、ERC-8004 注册和真实交易出现前，不能声称“已完成链上闭环”。

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
python scripts/build_termix_report.py /tmp/termix-manifest.json
```

live 模式会拒绝 fixture/demo 路径、缺文件、无时区时间和少于三个任务。

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
python scripts/submission_gate.py
```

`ready=false` 是本地环境的正常、诚实结果。它会继续拦住：本地 URL、非公开 GitHub、演示 Agent、缺真实合约/交易、缺 ERC-8004、缺 TermiX live 报告、缺五分钟视频。

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
