# 比赛要求与验收映射

## 结论

SafeHire 必须用一条真实闭环证明价值：评委打开公开页面，看到四类可调用 Agent，比较证据，用钱包创建有限权限，批准一次 BSC Testnet 动作，在 BscScan 上打开交易，然后撤销权限。本地演示成功只能证明产品流程，不能代替公开部署和链上证据。

## 强制材料

| 要求 | 仓库实现 | 完成判定 |
|---|---|---|
| 公开可访问产品 | FastAPI + 静态 Web UI | HTTPS 链接无需登录即可打开 |
| 公开 GitHub | 完整源码、测试、文档 | `GITHUB_REPO_URL` 指向公开仓库 |
| 四类 Agent | LP、网格、收益、健康因子 | 每类有公开 HTTPS endpoint 和真实证据 |
| BNB Agent 身份 | ERC-8004 / Agent Studio | 注册交易、agent id、owner、可回读 URI |
| 有限授权 | 离链风险门 + `ScopedExecutionPolicy` | target/method/金额/时间/重放/撤销都能证明 |
| 真实交易 | BSC Testnet 小额动作 | RPC 回执成功且 BscScan 可打开 |
| 数据真实性 | PancakeSwap/Venus/Lista/8004scan 官方读取 | 显示来源、块高、时间；失败不回退成伪 live |
| TermiX 优势 | 同题 Agent vs 人工严格报告 | 至少 3 题、原始输出、时间、成本、统一评分 |
| 演示视频 | 评委路径脚本 | 不超过 5 分钟，链接公开 |

## 官方信息边界

官方命令、合约地址和接口可能更新，实施前以 [00_OFFICIAL_IMPLEMENTATION_REFERENCES.md](00_OFFICIAL_IMPLEMENTATION_REFERENCES.md) 中列出的官网和当前 CLI `--help` 为准。任何“一句 prompt 上线赚钱”都只是产品宣传，不能当验收证据。

## 当前证据等级

- 已自动验证：本地四类 Agent、钱包签名登录、权限状态机、风险拒绝、演示回执、证据链、Solidity 编译测试，以及官方 Agent Studio `0.0.13` TypeScript 运行时构建。
- 必须外部完成：GitHub 发布、HTTPS 部署、Agent Studio 部署、ERC-8004 注册、BSC 交易、TermiX 实测、视频和最终提交。
