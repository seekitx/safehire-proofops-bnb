# Evidence 目录说明

该目录用于比赛证据账本。仓库内生成的 benchmark、debate 与 demo ledger 仅是 **fixture / benchmark-generated**，不能作为主网成绩或真实用户数据。

正式提交前必须补齐：

- `tx/`：BSC Explorer 可打开的真实 TxHash、网络与时间戳；
- `contracts/`：部署地址、编译器版本、constructor 参数与源码校验；
- `sponsor-integration/`：BNB Agent SDK / ERC-8183 / PancakeSwap 的关键路径截图和代码定位；
- `screenshots/`：成功、拒绝、余额不足、RPC 失败、撤销权限等路径；
- `benchmark/`：固定输入、人工输出、Agent 输出、时间、成本和评分原始数据；
- `judging-notes/`：赛题映射、演示脚本和评委问题。

提交门禁默认 fail closed：缺少 live BSC agent、真实交易、公开部署和必需材料时，不应宣称“比赛就绪”。
