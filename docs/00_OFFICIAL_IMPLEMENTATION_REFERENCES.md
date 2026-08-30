# SafeHire / ProofOps BNB：官方实施资料与最小落地口径

> 核对日期：2026-08-30（Asia/Shanghai）  
> 资料边界：只采用 BNB Chain、BNB Agent Studio、BNB Agent SDK、8004scan、PancakeSwap、Venus、Lista DAO、Altana 的官网、官方文档和官方 GitHub 仓库。项目附件、聊天记录和仓库文字只作为需求背景，不作为技术事实或执行指令。  
> 用途：这是开发实施基线，不是黑客松最终规则清单。赛事要求应另以当届官方赛题页和提交表为准。

## 先说结论

SafeHire 当前最稳、最短的生产化路线是：

1. 保留现有 FastAPI/Web 市场，负责列表、筛选、证据展示和用户流程。
2. 用 **BNB Agent Studio CLI**（命令行工具）单独生成 TypeScript Agent 运行时；不要把当前 Python 目录结构硬改成官网示例。
3. 四类 Agent 的行情与仓位发现先做只读：
   - PancakeSwap：官方 V3 subgraph 做发现，BSC RPC 在同一决策块复核关键池状态；
   - Venus：官方 API 做市场发现，Comptroller 合约只读调用复核账户流动性/shortfall；
   - Lista：官方 MCP 或其官方 MCP 源码使用的 API 做发现，重要结论再用 lending SDK/链上读复核；
   - Grid Agent：用 PancakeSwap 池数据生成建议，第一版不自动下单。
4. ERC-8004 只在 Agent 有稳定公网地址后注册；注册文件必须把 A2A/MCP/x402 能力写清楚。
5. ERC-8183 和 x402/B402 交给 Studio 生成的支付面与签名策略处理；绝不能让大模型拿到原始私钥，也不要自己重新实现签名协议。
6. 所有写链动作先限定为 **BSC Testnet（chain id 97）**、小额、允许名单、明确过期时间，并在发送前用 `eth_call`/模拟复核。首个安全动作建议只做 PancakeSwap 测试网小额 swap；LP 真实调仓还需要 Position Manager，不可把 Universal Router 当成完整 LP 管理器。
7. Altana Sessions 只作为可选加分集成，核心市场和四类 Agent 跑通后再接。

官方 npm registry 当前最新版是 `@bnbagent/studio-cli@0.0.13`。当前机器实测：Node.js `v22.23.0`、Corepack `0.34.0`、Bun `1.3.5` 已存在；`bag` 尚未安装。因此下面的 `bag` 命令已按官方文档与 `0.0.13` 包内容交叉核对，但仍须在安装后用 `bag --help` 和 `bag <group> --help` 对本机实际版本再核一次。

## 状态标记

| 标记 | 含义 | 是否需要登录、密钥或钱包 |
|---|---|---|
| **已实测公开可读** | 2026-08-30 从本机不带凭据成功取到数据 | 否 |
| **官方接口，未在本机写入验证** | 官方文档/官方源码明确提供，但本次没有发交易或创建云资源 | 视动作而定 |
| **需要凭据** | API key、云账号、LLM key 或服务账号是必需/生产建议 | 是 |
| **需要钱包** | 涉及注册、授权、支付或链上交易 | 是，并需要测试币/手续费 |
| **营销描述** | 产品页写了能力，但不能代替 CLI 帮助、接口定义或链上验证 | 不确定 |
| **截至本日仍不确定** | 官方资料互相不一致、未公布或可能变化 | 上线前必须再核 |

### 一眼状态表

| 能力 | 2026-08-30 状态 | 本次证据边界 |
|---|---|---|
| BSC Testnet RPC | **已实测公开可读** | `eth_chainId` 返回 `0x61` |
| 8004scan BSC 97 | **已实测公开可读** | `/chains` 和 `/agents?chain_id=97` 返回数据 |
| Venus API | **已实测公开可读** | `/pools?chainId=56` 返回池和市场 |
| Lista Moolah API | **已实测公开可读** | vault list 返回实时列表 |
| PancakeSwap subgraph | **官方接口，需要凭据/部署时复核** | 官方给出当前 subgraph，未使用 The Graph key 做本机查询 |
| Studio CLI | **官方包可下载，本机未安装** | npm 当前为 `0.0.13`，命令仍需安装后 smoke test |
| Studio 平台部署 | **需要账号/钱包** | 本次没有登录、部署或创建云资源 |
| ERC-8004 注册 | **需要钱包** | 地址/数据结构已核对，本次没有写链 |
| ERC-8183 完整 job | **需要钱包与测试 token** | 合约/CLI 已核对，本次没有创建 job |
| 正价 x402/B402 | **需要钱包与 Binance 商户凭据** | `price_usd=0` 不算支付验证 |
| Altana Session | **可选，需要钱包** | 只列官方 SDK 接法，本次不集成 |
| “一句 prompt 生产上线/自动赚钱” | **营销描述** | 不能作为完成证据 |

---

## 1. BNB Agent Studio：当前正确的项目形态

### 1.1 安装和前置条件

官方 Quickstart：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/quickstart/>  
官方 CLI Reference：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/cli-reference/>  
官方 npm 包：<https://www.npmjs.com/package/@bnbagent/studio-cli>  
`0.0.13` 元数据：<https://registry.npmjs.org/@bnbagent/studio-cli/0.0.13>

官方当前要求：

- Node.js 22 或以上；
- Corepack + pnpm 10；
- Bun 1.3+ 用于部署打包；
- Claude Code 或 Cursor 用于生成/修改 Agent；
- Docker 只在容器部署路径需要；
- AWS CLI 只在 AWS 配额/部署路径需要。

安装：

```bash
npm install --global @bnbagent/studio-cli@0.0.13
bag skills install
```

无人值守安装 Studio skills：

```bash
bag skills install --target both --scope user
```

安装后必须先记录实际版本和命令面：

```bash
bag --version
bag --help
bag init --help
bag deploy --help
bag erc8004 --help
bag erc8183 --help
bag x402 --help
```

这一步不需要钱包，但 `npm` 网络和全局安装权限必须可用。

### 1.2 初始化与目录

当前 `0.0.13` 初始化能力包括：

```bash
bag init safehireagents \
  --llm-provider pieverse-llm \
  --network bsc-testnet \
  --wallet-kind evm-local \
  --protocols A2A,MCP,X402 \
  --rails both \
  --erc8183-price 100000000000000000 \
  --b402-price 0.01 \
  --storage-provider ipfs \
  --destination self \
  --no-onboard
```

可选 wallet kind 包括 `evm-local`、`twak`、`altana`；Altana 不应作为第一版默认值。当前正式参数没有旧资料中的 `--framework`；`--protocol` 只是单协议兼容别名，优先用 `--protocols`。项目名必须以字母开头、只含 ASCII 字母/数字、最长 23 字符，不能含 `-`、`_`、`.`。ERC-8183 价格是 18 位原始整数，B402 价格是美元金额；不要混用单位。

当前默认值是 BSC Testnet、`evm-local`、`A2A,X402`、`rails=both`、ERC-8183 `0.1 U`、B402 `0.01 USD`。活动期裸 `bag init` 可能走 48 小时平台试用；准备自托管 AWS 时要显式 `--destination self`。

官方架构文档：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/architecture/>  
官方配置文档：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/configuration/>

当前生成项目的关键结构是：

```text
safehire-agents/
├── package.json
├── pnpm-workspace.yaml
├── AGENTS.md
├── agentcore/
│   ├── agentcore.json
│   └── aws-targets.json
├── .studio/
│   ├── .env.local
│   └── wallets/
└── app/
    └── agent/
        ├── studio.toml
        └── src/
            ├── sellerCore.ts
            ├── executor.ts
            ├── agentCard.ts
            ├── signing.ts
            ├── tools.ts
            ├── chainTools.ts
            ├── model.ts
            ├── requestLimits.ts
            ├── unifiedMain.ts
            ├── mcpMain.ts
            └── dualMain.ts
```

重点：

- `app/agent/studio.toml` 是 CLI 在工作区内解析的项目配置；
- 业务执行入口在 `app/agent/src/sellerCore.ts`，核心函数是 `runWork`；
- 签名策略位于 `app/agent/src/signing.ts`，签名必须是确定性代码，不能交给 LLM；
- `.studio/wallets/` 在部署代码之外，不能提交 Git；
- 当前 Studio 是 TypeScript 运行时。SafeHire 现有 Python/FastAPI 市场应通过 HTTP/A2A/MCP 与它连接，而不是照抄一个已经过时的 Python `app/service` 示例。

配置常用命令：

```bash
bag config show --project-root app/agent
bag config set payments.erc8183.min_price 100000000000000000 --project-root app/agent
```

敏感值不要出现在 shell 历史。`WALLET_PASSWORD`、LLM key、IPFS/云凭据放 `.studio/.env.local` 或官方 secrets manager；不要把真实密码直接写进 `bag env set ...` 示例或仓库。

### 1.3 本地开发

```bash
bag doctor
bag dev
```

当前官方默认面：

- A2A + x402：端口 `9000`；
- MCP：`http://localhost:8000/mcp`；
- x402 seller endpoint：`/x402`。

首次本地启动常用顺序：

```bash
bag wallet new
bag llm activate
bag wallet balance --all
bag doctor
bag dev
```

辅助命令：

```bash
bag dev --agent-only
bag dev --service-only
bag scan
bag mcp tools
bag audit ls
bag audit tail
```

SafeHire 应在本地自动检查：

1. A2A agent card 能被读取；
2. MCP 工具列表存在且读链工具不允许签名；
3. `/x402` 对未付款请求返回支付要求；
4. `notify_funded` 会重新读取链上 job 的 assignee、状态、预算和到期时间；
5. 审计日志不包含私钥、钱包密码和完整会话密钥。

### 1.4 部署

官方部署文档：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/deployment/>

```bash
bag deploy prepare
bag platform login
bag platform credit
bag deploy --provider bnb
bag deploy verify --provider bnb
bag deploy status --provider bnb
```

官方当前列出的 provider：

- `bnb`：BNB 托管的 48 小时测试网试用；官方明确提醒只用一次性测试钱包；
- `aws`：部署到自己的 Bedrock AgentCore；需要 AWS 账号、权限和可能的 Cognito 配置；
- `azure`：部署到自己的 Foundry/容器路径；需要 Azure 账号和云资源。

运维命令还包括 `bag deploy logs`、`bag deploy info`、`bag deploy destroy`。本地 storage 不满足部署就绪要求，部署路径应使用 IPFS 或官方支持的远端存储。

**需要凭据/钱包：**BNB 托管平台需要 GitHub device login、平台账号和一次性测试网钱包；AWS/Azure 需要各自账号、IAM/权限和费用。部署通常还需要 LLM key、存储凭据和 Agent 钱包。`bnb` 试用从首次部署开始计时，重新部署不会重置；48 小时后仍需迁移到自己的长期运行环境。

文档仍提到 `bag deploy provision-cognito`，但 `0.0.13` 包内说明已把它标为废弃，Cognito OAuth 应由 AWS 部署自动创建。以实际 CLI 为准。

### 1.5 官方文档的矛盾点

官方安全页：<https://docs.bnbchain.org/developer-kit/bnbchain-studio/security/>

截至 2026-08-30，官网页面之间存在版本残留：

- 当前 Quickstart/Architecture/Deployment 是单运行时、TypeScript `signing.ts`；
- 安全/配置页面部分段落仍出现旧的 keyless service、Python `signing.py`、`app/service` 或 `auto_settle` 描述；
- 当前 Quickstart 明确写 ERC-8183 最终 settle 仍由 buyer 手工执行：

```bash
bag erc8183 settle <jobId>
```

实施裁决顺序：**本机已安装 CLI 的 `--help` > 当前 Quickstart/Architecture/Deployment > 较旧页面片段**。不能只因为官网还有旧文字，就同时保留两套架构。

BNB Agent Studio 产品页 <https://www.bnbchain.org/en/bnb-agent-studio> 中“一条命令/一个 prompt 上线”“自动赚钱”等属于产品能力描述；实际可调用面必须以上述 CLI 和部署验证结果为准。页面标成 `IN PROGRESS` 的能力不能进入完成清单。

---

## 2. BSC Testnet：网络、RPC、水龙头、浏览器

官方 JSON-RPC 文档：<https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/>  
官方钱包配置：<https://docs.bnbchain.org/bnb-smart-chain/developers/wallet-configuration/>  
官方水龙头说明：<https://docs.bnbchain.org/bnb-smart-chain/developers/faucet/>  
官方水龙头当前入口：<https://www.bnbchain.org/en/testnet-faucet>

| 项目 | 当前官方值 |
|---|---|
| Chain ID | 十进制 `97`，十六进制 `0x61` |
| Gas token | `tBNB` |
| RPC 1 | `https://bsc-testnet-dataseed.bnbchain.org` |
| RPC 2 | `https://bsc-testnet.bnbchain.org` |
| RPC 3 | `https://bsc-prebsc-dataseed.bnbchain.org` |
| Explorer | `https://testnet.bscscan.com/` |

无钱包的连通性检查：

```bash
curl -sS -X POST https://bsc-testnet-dataseed.bnbchain.org \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
```

2026-08-30 本机实测返回：

```json
{"jsonrpc":"2.0","id":1,"result":"0x61"}
```

官方公共 RPC 有频率限制，当前文档给出每 5 分钟 10,000 次的公共限制。线上评委路径至少要配置两个 RPC、超时、重试和熔断；不要把单个公共节点当 SLA（稳定性承诺）。

水龙头：官方页面当前说明每日最高约 `0.3 tBNB`，并可能要求钱包在 BSC 主网至少有约 `0.002 BNB`；政策可能调整。文档页同时引导 Discord/support bot 并列出第三方 faucet，第三方入口不能写成“BNB 官方水龙头”。领取需要钱包地址，可能还需要验证码、Discord/账号交互或主网余额。

---

## 3. ERC-8004：身份注册与注册文件

BNB Agent SDK TypeScript Quickstart：<https://docs.bnbchain.org/developer-kit/bnbagent-sdk/quickstart-typescript/>  
BNB Agent SDK 官方仓库：<https://github.com/bnb-chain/bnbagent-sdk>  
ERC-8004 EIP（当前仍是 Draft）：<https://eips.ethereum.org/EIPS/eip-8004>  
ERC-8004 官方合约：<https://github.com/erc-8004/erc-8004-contracts>  
8004scan 官方规范镜像：<https://best-practices.8004scan.io/docs/official-specification/erc-8004-official.html>

### 3.1 注册时机与 CLI

Agent 先有稳定公网 URL，再注册：

```bash
bag erc8004 register \
  --endpoint https://agents.example.com \
  --network bsc-testnet \
  --name "SafeHire ProofOps" \
  --description "..." \
  --protocol A2A \
  --version 0.3.0

bag erc8004 show --network bsc-testnet
bag erc8004 resolve <agentId> --network bsc-testnet

bag erc8004 update-endpoint \
  --endpoint https://agents.example.com \
  --protocol A2A \
  --version 0.3.0

bag erc8004 update-metadata --key <key> --value <value>
bag erc8004 get-metadata --key <key>
```

具体参数必须用本机 `bag erc8004 <command> --help` 核对。注册会产生 ERC-721 形式的 `agentId`，属于链上写操作；需要钱包，BSC Testnet 上还需要可用测试钱包。BNB Agent SDK 文档写明 ERC-8004 注册可经 MegaFuel 赞助 gas，但仍要保留“赞助服务不可用时”的 tBNB 兜底。

### 3.2 BSC 官方示例地址

SDK 当前 README 和 APEX 官方仓库均给出 BSC Testnet ERC-8004 Identity Registry：

```text
Identity Registry:   0x8004A818BFB912233c491871b3d84c89A494BD9e
Reputation Registry: 0x8004B663056A597Dffe9eCcC1965A193B7388713
```

官方仓库当前没有列出 BSC Validation Registry 地址，不得自行猜测。

SDK 网络文档刻意不重复所有地址，要求以上游官方仓库为准：<https://docs.bnbchain.org/developer-kit/bnbagent-sdk/networks/>。因此生产代码不要在多处复制地址；优先用 Studio/SDK 的 `bsc-testnet` 网络 preset，并在部署日志里记录最终解析出的 chain id、registry 地址和代码版本。

### 3.3 注册文件数据结构

最小建议：

```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "SafeHire LP Rebalancer",
  "description": "Read-first LP risk and rebalance recommendations for BSC.",
  "image": "https://safehire.example/assets/lp-agent.png",
  "services": [
    {
      "name": "web",
      "endpoint": "https://safehire.example/agents/lp-rebalancer"
    },
    {
      "name": "A2A",
      "endpoint": "https://agents.example.com/.well-known/agent-card.json",
      "version": "0.3.0"
    },
    {
      "name": "MCP",
      "endpoint": "https://agents.example.com/mcp",
      "capabilities": [],
      "version": "2025-06-18"
    }
  ],
  "x402Support": true,
  "active": true,
  "registrations": [
    {
      "agentId": 123,
      "agentRegistry": "eip155:97:0x8004A818BFB912233c491871b3d84c89A494BD9e"
    }
  ],
  "supportedTrust": ["reputation"]
}
```

注册 URI 可用 HTTPS、IPFS 或 data URI。最终证据至少保存：注册交易 hash、chain id、registry、token id/agent id、owner、解析后的 URI 和 8004scan 页面/API 返回。

当前 CLI 自动生成 URI 的核心字段是 `type/name/description/image/services/registrations/supportedTrust`，不保证自动补齐 `x402Support` 和 `active`。如果完整元数据是验收项，要用自定义 `--agent-uri` 或官方更新流程补全后，再用 `resolve` 和 8004scan 回读。平台托管部署优先走 `bag deploy verify --endpoint <public-url>` 的中继注册路径。

---

## 4. 8004scan API：市场发现层，不是链上真相

官方 Developer Hub：<https://8004scan.io/developers>  
官方 OpenAPI：<https://api.8004scan.io/openapi.json>  
官方 issue tracker：<https://github.com/alt-research/8004scan-issue-tracker>

基础地址：

```text
https://api.8004scan.io/api/v1
```

公开读取：

```bash
curl 'https://api.8004scan.io/api/v1/agents?chain_id=97&limit=20&offset=0'
curl 'https://api.8004scan.io/api/v1/agents/search/semantic?q=liquidity+risk'
curl 'https://api.8004scan.io/api/v1/agents/97/<tokenId>'
curl 'https://api.8004scan.io/api/v1/agents?owner_address=0x...'
curl 'https://api.8004scan.io/api/v1/stats/global'
curl 'https://api.8004scan.io/api/v1/feedbacks'
curl 'https://api.8004scan.io/api/v1/chains'
```

`GET /agents` 当前返回结构是：

```json
{
  "items": [
    {
      "agent_id": "97:0xRegistry:2022",
      "token_id": "2022",
      "chain_id": 97,
      "contract_address": "0xRegistry",
      "owner_address": "0xOwner",
      "name": "...",
      "supported_protocols": [],
      "x402_supported": true,
      "total_score": 0.0,
      "health_score": null,
      "total_feedbacks": 0
    }
  ],
  "total": 1983,
  "limit": 1,
  "offset": 0
}
```

2026-08-30 本机实测：

- `/chains` 成功返回 BSC mainnet `56` 和 BSC Testnet `97`；
- BSC Testnet 显示 `enabled: true`、provider status `available`；
- `/agents?chain_id=97&limit=1` 无凭据成功返回数据。

鉴权要分两类：

1. Developer Hub 宣传用 `X-API-Key` 提升数据 API 配额；匿名配额页面当前写 30 次/分钟、1000 次/天，免费 key 写 600 次/分钟、100,000 次/天。生产 key 必须只放后端。
2. OpenAPI `0.4.355` 还定义了钱包签名登录取得 JWT，再用 `X-Access-Token` 或 `Authorization: Bearer` 访问账号/写入类接口。

公开读取不需要钱包；高配额需要 API key；账号修改需要钱包登录/JWT。官方两页对鉴权重点表述不同，不能把 JWT 当成公开列表的硬要求，也不能把匿名配额当生产保障。

风险边界：8004scan 的 `total_score`、`health_score`、排名和搜索结果是索引/派生数据。Agent 身份 owner、URI、链和 token id 必须再通过 ERC-8004 registry/BSC RPC 复核。

---

## 5. ERC-8183：雇佣、托管、提交与结算

ERC-8183 EIP（当前仍是 Draft）：<https://eips.ethereum.org/EIPS/eip-8183>  
BNB Agent SDK Quickstart：<https://docs.bnbchain.org/developer-kit/bnbagent-sdk/quickstart-typescript/>  
APEX 合约官方仓库：<https://github.com/bnb-chain/apex-contracts>

当前官方生命周期：

```text
OPEN -> FUNDED -> SUBMITTED -> COMPLETED
                         \-> REJECTED
       \--------------------> EXPIRED
```

过期后可退款；OPEN 状态可取消。Provider 收到 funded 通知后仍必须重新验证：

- job 的 assignee 是自己；
- 状态确实为 FUNDED；
- budget 不低于最低价；
- expiry 仍有效；
- payment token 与当前 Commerce 合约一致。

CLI 主路径：

```bash
bag config set payments.erc8183.price 0

bag erc8183 buy \
  --provider <provider-address> \
  "任务说明" \
  --budget-u <amount> \
  --deadline-min <minutes> \
  --network bsc-testnet

bag erc8183 status <jobId>
bag erc8183 fetch <jobId>
bag erc8183 submit <jobId> "交付内容" --metadata-json '{"key":"value"}'
bag erc8183 settle <jobId> --action approve
bag erc8183 settle <jobId> --action dispute
bag erc8183 settle <jobId> --action reject
```

完整参数以本机 CLI 帮助为准。当前官方说明最终 settle 是 buyer/manual，不应在没有版本证据时启用旧页面中的 `auto_settle`。

BSC Testnet 当前官方上游地址：

```text
Commerce: 0xa206c0517B6371C6638CD9e4a42Cc9f02A33B0DE
Router:   0xd7d36d66d2f1b608a0f943f722d27e3744f66f25
Policy:   0xd6a4217588f6b1f5657a92a3e94e6422ad771cea
Test payment token shown by APEX: 0xc70B8741B8B07A6d61E54fd4B20f22Fa648E5565
```

地址仍应在部署时从官方 preset/上游 [`scripts/addresses.ts`](https://github.com/bnb-chain/apex-contracts/blob/main/scripts/addresses.ts) 和运行时 `commerce.paymentToken()` 读取。旧 README/搜索缓存曾出现 `0x4f4678...`，但当前 `scripts/addresses.ts` 与 SDK `0.5.5` 均为 `0xd6a421...`；不能靠聊天记录或复制旧资料固化。

**需要钱包：**创建、fund、submit、settle 都是写链。买方需要 U 测试 token；首次 approve 可能不能走 paymaster，钱包最好留少量 tBNB。`price=0` 只会跳过 ERC-20 托管，链上状态交易仍需 gas 或 paymaster。交易前先模拟并记录 BscScan testnet 链接。

当前 Studio 更接近“卖方 Agent + 手动买方 CLI”，没有证据证明它自带独立且永久可靠的 ERC-8183 后台轮询器。卖方履约依赖 `notify_funded` 或运行时被重新唤醒；要宣传 24/7 自动履约，必须另加事件监听/调度并提供真实运行证据。

---

## 6. x402/B402：付费 HTTP 服务

Studio 当前直接提供 `/x402`，CLI 提供：

```bash
bag x402 quote https://agents.example.com/x402
bag x402 trust <merchant-or-url> --cap <usd> --network bsc-testnet --yes
bag x402 buy https://agents.example.com/x402 --max-usd <n> --network bsc-testnet
bag x402 sell init --price-usd <amount>
bag x402 sell status
```

具体参数以本机帮助为准。SafeHire 最小实现应让 Studio 处理 seller endpoint、报价、付款验证和签名，不自行拼协议 header。

如果未来确实需要自建服务，可参考 BNB 官方 MPP SDK：

- 文档：<https://docs.bnbchain.org/developer-kit/mpp-sdk/quickstart/>
- 仓库：<https://github.com/bnb-chain/mpp-sdk>

其官方 B402 包可直接对接 x402：

```bash
pnpm add @bnb-chain/b402 @x402/core @x402/fetch viem
```

安全底线来自 Studio/SDK：

- LLM 只能提出调用意图，不能看到原始钱包或私钥；
- 校验 payee、from、chain、verifying contract、primary type 和有效期；
- 设置每次调用上限和累计预算；
- 配置 `[payments.x402].allowed_hosts`；
- 当前签名策略允许受限 EIP-3009，默认拒绝 ERC-2612 与 Permit2 `PermitSingle`/`PermitBatch` 这类长期 allowance 签名；
- 用 `bag budget show/enable/disable` 与 `bag audit` 跟踪预算和审计。

当前 Studio 的 seller rail 实际接 Binance B402。通用 x402 v2 规范：<https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md>，核心 headers 是 `PAYMENT-REQUIRED`、`PAYMENT-SIGNATURE`、`PAYMENT-RESPONSE`。但不能因此假设任意 facilitator 都能直接替换 Studio 的 B402。

通用 x402 v2 的 `PaymentRequired` 核心结构：

```json
{
  "x402Version": 2,
  "error": "payment required",
  "resource": {
    "url": "https://agents.example.com/x402",
    "description": "SafeHire paid result",
    "mimeType": "application/json",
    "serviceName": "SafeHire ProofOps"
  },
  "accepts": [
    {
      "scheme": "exact",
      "network": "eip155:97",
      "amount": "10000000000000000",
      "asset": "0xPaymentToken",
      "payTo": "0xMerchantWallet",
      "maxTimeoutSeconds": 60,
      "extra": { "name": "U", "version": "1" }
    }
  ],
  "extensions": {}
}
```

正价 B402 还需要 Binance 商户账号，官方资料：

- 账号申请：<https://developers.binance.com/en/docs/products/onchainpay-x402/basics/6.apply-developer-account>
- 请求签名：<https://developers.binance.com/en/docs/products/onchainpay-x402/basics/3.request-signing>
- Base URL：<https://developers.binance.com/en/docs/products/onchainpay-x402/basics/4.base-urls>

商户申请需要项目/企业信息、收款 EVM 钱包、1024-bit RSA 公钥、固定出口 IP allowlist；测试和生产环境分别申请。Binance 发放 `clientId`、`accessToken`，Base URL 当前也需要向 Binance 获取。相关环境变量包括 `B402_BASE_URL`、`B402_CLIENT_ID`、`B402_ACCESS_TOKEN`、`B402_PRIVATE_KEY_B64`/`B402_PRIVATE_KEY`。密钥签名用 RSA-SHA256，内容是精确 JSON body + 毫秒时间戳；两种 private key 变量不要同时配置。

B402 认证 API 路径：

```text
POST {B402_BASE_URL}/papi/v2/b402/supported
POST {B402_BASE_URL}/papi/v2/b402/verify
POST {B402_BASE_URL}/papi/v2/b402/settle
```

认证头：

```text
X-Tesla-ClientId
X-Tesla-SignAccessToken
X-Tesla-Signature
X-Tesla-Timestamp
```

**需要钱包/商户凭据：**真实购买需要支付钱包和 token；只查询 quote 通常不需要签名。`price_usd=0` 是免费直通，不会产生真实 402 challenge，也不会经过 B402 verify/settle，不能写成“零金额 B402 支付成功”。exact wire、支持 token 和 B402 环境仍可能随 Studio 版本变化，必须做两端实测。

---

## 7. PancakeSwap：只读实时数据 + 最小安全动作

### 7.1 只读数据方案

官方 Subgraph 入口：<https://developer.pancakeswap.finance/apis/subgraph>  
官方 subgraph 源码：<https://github.com/pancakeswap/exchange-v3-subgraphs>  
历史/配套官方仓库：<https://github.com/pancakeswap/pancake-subgraph>

官方页面当前链接的 Exchange V3 BSC subgraph ID：

```text
Hv1GncLY5docZoGtXjo4kwbTvxm3MAhVZqBZE4sUT9eZ
```

The Graph 生产 gateway 端点模板：

```text
https://gateway.thegraph.com/api/<THE_GRAPH_API_KEY>/subgraphs/id/Hv1GncLY5docZoGtXjo4kwbTvxm3MAhVZqBZE4sUT9eZ
```

这个 URL 的服务商是 The Graph，但 subgraph 部署链接来自 PancakeSwap 官方开发页。上线前仍要从官方页重新打开并检查 chain/schema，不能把 2026-08-30 的 ID 当永久常量。

建议：

1. Subgraph 用于池、position、tick、TVL、交易量发现；
2. 决策关键值在同一 `blockNumber` 用 BSC RPC 读取 V3 pool/PositionManager 复核；
3. 返回结果保存 `source`、`chainId`、`blockNumber`、`fetchedAt`、`lagBlocks`；超过延迟阈值就不输出“实时”结论。

V3 position 示例查询：

```graphql
query Position($id: ID!) {
  position(id: $id) {
    id
    owner
    liquidity
    tickLower { tickIdx }
    tickUpper { tickIdx }
    pool {
      id
      tick
      sqrtPrice
      liquidity
      feeTier
      token0 { id symbol decimals }
      token1 { id symbol decimals }
    }
    depositedToken0
    depositedToken1
    withdrawnToken0
    withdrawnToken1
    collectedFeesToken0
    collectedFeesToken1
  }
}
```

PancakeSwap 文档链接到 The Graph 的当前 V3 BSC subgraph 页面。The Graph 网关的生产调用通常需要 API key；subgraph id、schema 和网关 URL 可能调整，所以应在部署时从官方页面确认，并在 CI 做 schema introspection（结构探测）。不要复用旧博客里的 hosted-service URL。

### 7.2 Universal Router 的最小用途

官方地址：<https://developer.pancakeswap.finance/contracts/universal-router/addresses>

| Router | BSC Mainnet | BSC Testnet |
|---|---|---|
| Infinity Universal Router | `0xd9C500DfF816a1Da21A48A732d3498Bf09dc9AEB` | `0x87FD5305E6a40F378da124864B2D479c2028BD86` |
| V3 Universal Router | `0x1A0A18AC4BECDDbd6389559687d1A73d8927E416` | `0x9A082015c919AD0E47861e5Db9A1c7070E81A2C7` |

SafeHire 第一版只需要 V3 testnet Router 做受控小额 swap：

- 固定 chain id `97`；
- Router/Token allowlist；
- 限制输入金额、`minOut`、slippage 和 deadline；
- `eth_call`/估 gas/模拟成功后才弹出用户确认；
- 不授予无限 allowance；
- 保存交易 hash、输入、quote、模拟结果和最终 receipt。

Universal Router 负责路由交换，不等于完整 LP 调仓。集中流动性仓位的 mint/decrease/collect 还需要官方 V3 Position Manager/periphery 合约。官方 V3 Pool 技术参考：<https://github.com/pancakeswap/pancake-developer/blob/master/docs/pages/contracts/v3/pancakev3pool.md>。在 Position Manager 地址、ABI、授权回收、fork/testnet 测试补齐前，LP Agent 只给建议，不能声称“已安全自动调仓”。

---

## 8. Venus：市场发现与健康检查

官方 API 文档源码：<https://github.com/VenusProtocol/venus-protocol-documentation/blob/main/services/api.md>  
官方 Swagger：<https://api.venus.io/docs/swagger.json>

基础地址：

```text
Mainnet: https://api.venus.io
Testnet: https://testnetapi.venus.io
```

注意：没有额外 `/api` 前缀。公开读取示例：

```bash
curl 'https://api.venus.io/pools?chainId=56'
curl 'https://api.venus.io/markets?chainId=56&limit=100'
curl -H 'accept-version: next' 'https://api.venus.io/markets?chainId=56&limit=100'
curl 'https://api.venus.io/markets/history?asset=<vToken>&chainId=56&period=month'
curl 'https://api.venus.io/markets/tvl?chainId=56'
```

2026-08-30 本机实测 `/pools?chainId=56` 不带 key 成功返回池、Comptroller、oracle 和 market 数据。

SafeHire 需要的主要字段：

- pool：`address`、`priceOracleAddress`、`closeFactorMantissa`、`liquidationIncentiveMantissa`、`minLiquidatableCollateralMantissa`、`markets`；
- market：`address`、`chainId`、`poolComptrollerAddress`、`underlyingAddress`、`underlyingSymbol`、`underlyingDecimal`、`borrowApy`、`supplyApy`、`liquidityCents`、`tokenPriceCents`、`isListed`。

API stable 和 `accept-version: next` 数据结构不同，并可能返回 Warning 299 迁移提示；写 adapter 时必须分别校验 schema，不可假定永远相同。

健康检查必须读合约：

- Isolated Pools Comptroller 官方文档：<https://docs-v4.venus.io/technical-reference/reference-isolated-pools/comptroller/comptroller>
- Core Pool ComptrollerLens：<https://docs-v4.venus.io/technical-reference/reference-core-pool/comptroller/comptroller-lens>
- PoolRegistry：<https://docs-v4.venus.io/technical-reference/reference-isolated-pools/pool-registry/pool-registry>

关键只读函数：

```solidity
getAccountLiquidity(address account)
  returns (uint256 error, uint256 liquidity, uint256 shortfall)

getBorrowingPower(address account)

getHypotheticalAccountLiquidity(
  address account,
  address vTokenModify,
  uint256 redeemTokens,
  uint256 borrowAmount
)
```

Venus 不直接给一个跨池通用的“health factor”标量；Health Shield 应展示池、净流动性、shortfall、抵押/借款和计算口径。API 用于发现，合约读用于告警依据。repay/补仓是写链动作，第一版只在测试网、模拟成功并经用户确认后开放。

---

## 9. Lista：优先官方 MCP/REST 只读，链上动作后置

Lista 官方 MCP server：<https://github.com/lista-dao/lista-mcp-server>  
Lista 官方 Lending SDK：<https://github.com/lista-dao/lending-sdk>  
Lista 官方 skills：<https://github.com/lista-dao/lista-skills>

远端 MCP：

```text
https://mcp.lista.org/mcp
```

官方 MCP 暴露的相关只读工具：

- `lista_get_lending_vaults`
- `lista_get_borrow_markets`
- `lista_get_position`
- `lista_get_oracle_price`

其官方源码 `src/api-client.ts` 与 `src/tools/lending.ts` 使用：

```bash
curl 'https://api.lista.org/api/moolah/vault/list?sort=depositsUsd&order=desc&zone=0&chain=bsc'
curl 'https://api.lista.org/api/moolah/overall'
curl 'https://api.lista.org/api/moolah/borrow/markets?sort=liquidity&order=desc&zone=0,3&chain=bsc&smartLendingChecked=false'
curl 'https://api.lista.org/api/moolah/borrow/<wallet>'
curl 'https://api.lista.org/api/moolah/supply/apy?userAddress=<wallet>'
curl 'https://api.lista.org/api/moolah/one/holding?userAddress=<wallet>&type=market'
```

2026-08-30 本机实测 vault list 无 key 成功返回数据。常用字段：

- vault：`address`、`name`、`apy`、`emissionApy`、`depositsUsd`、`assetSymbol`、`curator`、`zone`、`chain`、`collaterals`；
- borrow market：`id`、`loan`、`collateral`、`lltv`、`liquidityUsd`、`rate`、`supplyApy`、`zone`、`chain`；
- position：loan/collateral 数量与美元值、borrow rate、cdps；`LTV = loanUsd / collateralUsd`，再与该 market 的 LLTV 比较。

这些 REST 路径来自官方 MCP 源码，但不是一个独立版本化的公共 API 合约，可能无预告变化。必须加 schema 校验、超时与错误降级；重要决策用官方 lending SDK 的 `getMarketList`、`getMarketInfo`、`getMarketUserData`、`getVaultList`、`getHoldings` 或链上读复核。

不要把已归档的旧 `lista-dao-contracts` 当当前主入口。第一版只读不需要私钥；实际 supply/borrow/repay 需要钱包、token approve、gas 和交易模拟。

---

## 10. Altana Sessions：可选集成，不阻塞核心提交

官方文档：<https://docs.altana.network/>  
官方 SDK：<https://github.com/altananetwork/altana-sdk>

安装：

```bash
npm install @altananetwork/sdk viem
```

官方 session 的核心是给一个临时 signer 有边界的权限，而不是把主钱包私钥交给 Agent：

```ts
const session = await client.grantSession({
  wallet,
  signer: wallet.signer,
  permissions: {
    calls: [{ to: "0xAllowedContract..." }],
    spend: [{
      token: "0xAllowedToken...",
      limit: 100_000_000n,
      period: "day"
    }]
  },
  expiry: Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60
});

await client.execute({
  session,
  calls: [{ to: "0xAllowedContract...", data, value: 0n }]
});
```

默认 session 可注册到 KeyStore；`register: false` 可先创建未列出的 session，之后再 `registerSessionKey`；撤销用 `revokeSession`。Studio 初始化也支持 `--wallet-kind altana`。

接入条件：

- 用户钱包/私钥或 passkey；
- 创建/注册 session 的 gas；
- 明确的合约 allowlist、token、周期额度和 expiry；
- session secret 本地文件权限 `0600`，不能提交 Git、日志或发给 LLM；
- 产品页让用户看见权限、到期时间和撤销入口；
- Explorer/链上证据能证明真实 session-key 交易。

这不是 SafeHire 四类 Agent 的前置依赖。只有核心 Agent、8004 身份、实时数据和市场完整流程都已跑通，才值得开启 Altana 支线。

---

## 11. 凭据与动作矩阵

| 能力 | 无登录可做 | 需要 API/云账号 | 需要钱包/测试资产 |
|---|---|---|---|
| BSC RPC 读链 | chain id、block、`eth_call` | 生产私有 RPC 建议要 key | 发交易需要 |
| 8004scan | 列表、详情、搜索、chains、stats | 高配额用 `X-API-Key` | 账号写入/JWT 登录需要 |
| PancakeSwap | RPC 读池；subgraph 页面/公开层 | The Graph 生产 gateway 常需 key | swap、LP mint/burn、approve 需要 |
| Venus | `/pools`、`/markets`、合约 view | 无公开硬要求；私有 RPC建议 | supply/borrow/repay 需要 |
| Lista | MCP/REST 只读 | 当前官方源码未要求 key | supply/borrow/repay 需要 |
| ERC-8004 | 解析已注册身份 | IPFS/托管可能要凭据 | 注册、更新 endpoint 需要 |
| ERC-8183 | 列表/状态读取 | LLM/存储/运行时凭据 | create/fund/submit/settle 需要 |
| x402/B402 | quote/支付要求读取 | facilitator/运行时可能需要 | buy/付款需要 |
| Studio 部署 | 本地 `doctor/dev` | BNB/AWS/Azure、LLM、storage | Agent 钱包/注册支付需要 |
| Altana Session | 文档/只读状态 | relay/服务能力视配置 | grant/register/execute/revoke 需要 |

---

## 12. SafeHire 推荐实施顺序

### P0：先让评委看到真实、可复核的数据

1. 给每个数据源写独立 adapter，统一返回 `source`、`chainId`、`blockNumber`、`fetchedAt`、`isLive`、`warnings`。
2. Pancake/Venus/Lista 的展示数据接官方只读源；fixture 只保留测试，线上默认路径禁止回退成“看起来像 live”的假数据。
3. 对决策关键值加 BSC RPC 复核，并把 block number 展示在证据页。
4. 四个 Agent 输出统一 `recommendation`、`evidence`、`risks`、`nextActions`；写链动作默认为 `disabled`。

### P1：生成 Studio 运行时并打通市场

1. 安装 CLI，记录版本和 `--help`；
2. 在独立子目录 scaffold TypeScript runtime；
3. `bag doctor`、`bag dev`；
4. FastAPI/Web 通过 A2A/MCP 调用；
5. 验证 `/x402`、audit、budget 和签名 policy；
6. 不把 `.studio/.env.local`、wallet、session secret 提交仓库。

### P2：部署、注册、雇佣和付款

1. 用一次性 BSC Testnet 钱包；
2. 部署到稳定公网环境并 `bag deploy verify`；
3. 分别注册四个 Agent 的 ERC-8004 身份；
4. 用 8004scan + RPC 双重核验；
5. 跑一单完整 ERC-8183：`buy`（创建/配置/注资）、`status`、`submit`、`fetch`、`settle --action approve`；
6. 跑一单正价 x402/B402：`quote`、`trust`、`buy`、返回付费结果，并证明不是 `price_usd=0` 免费直通；
7. 保存每一步交易 hash、endpoint、时间、输入、输出和截图。

### P3：最小写链和可选 Altana

1. 先只做 PancakeSwap V3 testnet 小额 swap；
2. 用户明确确认前不得发送；
3. LP 调仓、Venus/Lista repay 等高风险动作保持只读建议；
4. 核心验收后再接 Altana bounded session。

---

## 13. 截至 2026-08-30 的不确定项

1. **BNB Studio 文档残留旧架构。**当前 CLI 帮助和生成代码必须作为最终裁决，特别是 service 分层、文件名和 auto-settle。
2. **CLI npm 版本已锁定为 `0.0.13`。**本仓库通过 `npx --package @bnbagent/studio-cli@0.0.13` 生成 `agent-studio/safehireagents`，并保留 `pnpm-lock.yaml`；不依赖全局 `latest`。npm 元数据声明源码为 `bnb-chain/bnbagent-studio`，该 GitHub 地址当前不能公开访问；公开 npm tarball 能下载，但源码透明度仍是不确定项。
3. **BNB 托管 48 小时不是长期线上保障。**评审期间需要自己的长期部署或明确续期方案。
4. **ERC-8183 地址可能更新。**旧资料已有过 Policy 地址漂移；部署前同时核对 SDK preset、APEX `scripts/addresses.ts` 和运行时 `commerce.paymentToken()`。
5. **8004scan 鉴权文档两套说法并存。**匿名读、API key 配额和钱包 JWT 是不同能力；以具体 endpoint 的 OpenAPI security 与实测状态为准。
6. **8004scan 是索引层。**BSC 97 当前已启用，但索引延迟和派生 score 不等于链上事实。
7. **PancakeSwap subgraph URL/schema 可变化。**只从官方 Subgraph 页面发现当前部署，保存 subgraph id，启动时探测 schema。
8. **Subgraph/API 都可能延迟。**“实时”必须附 block/time/lag，并对链上关键值复核。
9. **Universal Router 不完成 LP 调仓。**实际 LP 写入还要 Position Manager/periphery、授权与资产会计测试。
10. **Venus API stable/next 正在迁移。**adapter 必须同时处理版本警告，健康依据用合约 view。
11. **Lista REST 未独立承诺版本稳定。**以官方 MCP 源码为当前证据，增加 schema 防护，并准备 lending SDK/链上 fallback。
12. **x402/B402 wire 和 facilitator 可随 Studio 版本演进。**正价 B402 还需要商户审核、RSA 凭据和固定出口 IP；不要自行复制旧 header，用 Studio 两端实测。
13. **Altana 不应成为核心依赖。**其 wallet/session/relay/Explorer 细节要在决定冲伙伴奖时单独做真实交易验收。

只有以上不确定项在具体安装版本和部署环境里重新验证后，才能把“官方资料已覆盖”升级成“端到端已完成”。
