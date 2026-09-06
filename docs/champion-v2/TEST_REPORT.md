# V2 实际测试报告

报告版本日期：2026-09-06。所有数字来自本轮实际运行，不沿用 V1 成功数充当新增用例。运行时 Python 3.13；项目目标 Python>=3.11，尚未在3.11/3.12矩阵复跑。

## 实际结果

| 检查 | 结果 | 不能推导出的结论 |
|---|---|---|
| 新增 `tests/arena/` | **126 passed** | 不代表真实市场数据正确或主网执行成功 |
| 全仓尝试 `pytest --continue-on-collection-errors -ra` | **264 passed，3个收集错误，命令非零退出** | 不是完整 CI 通过 |
| 四类合成 walkthrough | 每类一个本地参考通过，一个本地反例被拦截 | 不是两个真实代理的付费性能比较 |
| 隔离浏览器＋真实ASGI路由 | 1440×1000和390×844；无JS错误、无横向溢出 | 未跑完整主应用 lifespan/原生浏览器HTTP/钱包 |
| 编译与语法 | 新模块/脚本/main.py compileall、arena.js node --check通过 | 不替代 Ruff、mypy、依赖版本矩阵 |
| 仓库静态密钥规则 | static_security_check passed | 不等于完整安全审计或依赖漏洞扫描 |
| 供应商配置检查 | 四条配置通过；一个声明运营方；报价均关闭 | 不代表四家商户或实时存活验证 |
| 本次增量应用包 | 8项实际校验通过；详细记录在外层verification/package-tests.json | 不回滚线上数据或链上状态 |

## 原测试的三个收集错误

```text
tests/test_api_flow.py      ModuleNotFoundError: eth_account
tests/test_live_erc8183.py  ModuleNotFoundError: eth_abi
tests/test_wallet_auth.py  ModuleNotFoundError: eth_account
```

运行环境缺 eth-account、eth-abi、web3、Ruff、mypy，且容器外网DNS不可用；未删除/跳过后谎称完整通过。全仓命令继续执行能收集的测试，仅为识别其他回归。必须在你依赖完整的开发/CI环境重新运行普通 `python -m pytest -ra`。

## 浏览器边界

先尝试原生回环HTTP，Chromium被环境策略阻止：`ERR_BLOCKED_BY_ADMINISTRATOR`。该尝试失败，原始日志保留。随后用 `--offline-asgi`：真实Chromium执行页面JS，fetch经测试绑定调用真实隔离FastAPI路由和临时SQLite，非简单静态截图。

覆盖：四个分类的正反例、私有任务创建、原文保存、第二个失败方案、同任务比较、导出、保留token刷新状态。页面不自动请求供应商。测试临时DB与capability在完成后销毁，截图明确标合成/离线。

## 单元/API用例重点

时间戳缺时区/过期/未来、输入非有限数和布尔伪数字、参数额外字段、不同任务或快照混用；LP区间/spacing/无意义换仓/预算不够；网格两边成本和止损；收益留在原仓位的机会成本、容量不足和退出延迟；偿债向上取整、价格冲击和不足预算；不同task token不能串读；精确原文幂等冲突、两个并发写者版本冲突、数据库重启、配额不部分写入、原文/报告/事件/任务/尾部篡改；报价错误绑定/链/价格/过期，HTTP402/重定向/超时/超大响应/熔断，默认开关关闭、DNS私网拒绝；请求64000字节/JSON64层、状态码和no-store。

## 未验收

真实BSC RPC/链上状态重放、第二供应商连接、供应商签名、付费闭环、完整main lifespan、合约编译、Agent Studio TypeScript构建、Ruff/mypy、外部浏览器真实网络、公开部署、生产并发/长期可用性、独立人类质量评测。没有模拟执行这些再填“成功”。

## 重跑命令

```bash
python -m pytest tests/arena -ra
python -m pytest -ra
python -m compileall -q src/proofops/arena scripts/arena* apps/api/main.py
node --check apps/web/assets/arena.js
python scripts/static_security_check.py
python scripts/arena_check_providers.py config/arena-providers.json
PYTHONPATH=src python scripts/arena_browser_smoke.py --output .data/arena-browser
```

真实链上验收需先取得用户对网络、地址、金额、币种和动作的明确授权。本包没有这样的自动化资金权限。
