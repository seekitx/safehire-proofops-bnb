# 应用、运行与验收手册

## 1. 使用范围与安全默认

此包是**增量升级**，不是独立运行的完整仓库。对照版本是 `267e4978c56adc2c566ab82fc134b18b0a5a7708`。保留你的最新 `evidence/`、Agent Studio 工程、部署配置、私有环境文件及其他未修改文件。不要将历史 bootstrap 仓库覆盖到当前主分支。

提供的 `apply_overlay.py` 默认只检查；必须使用 `--apply` 才写入。它验证每个修改前文件和 payload 的 SHA256，拒绝冲突、符号链接和路径越界，并在修改前保存可回滚备份。它不是签名发布系统：校验和检测意外损坏和基线漂移，不证明发行者身份。生产服务正在读取这些文件时不应热替换；先在分支/独立工作树验收，再通过自己的发布流程上线。

## 2. 应用补丁

先解压 ZIP，再进入自己的仓库建立分支。以下路径应替换成实际路径，仓库路径不要填写 ZIP 的 `overlay` 目录。

```bash
cd /your/path/safehire-proofops-bnb
git switch -c feat/evidence-first-decision-desk
python /your/path/SafeHire_BNB_Champion_Upgrade_2026-09-05/apply_overlay.py . --check
python /your/path/SafeHire_BNB_Champion_Upgrade_2026-09-05/apply_overlay.py . --apply
git diff --stat
git status --short
```

若基线校验失败，脚本不覆盖任何源文件。对照包内 `changes.patch` 手工合并，而不是删除校验或强制拷贝整个旧目录。已经应用且内容完全一致时再次执行会报告幂等。

脚本打印备份目录及回滚命令：

```bash
python /your/path/SafeHire_BNB_Champion_Upgrade_2026-09-05/apply_overlay.py /your/path/safehire-proofops-bnb --rollback /path/printed/by/apply
```

回滚前仍验证当前文件等于补丁版本；有后续编辑时拒绝覆盖。回滚删除本次新增文件，恢复被修改文件；不会删除后来产生的目录内其他内容。

## 3. 本地启动与页面

```bash
cd /your/path/safehire-proofops-bnb
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export EXECUTION_MODE=demo
export EXECUTION_ADAPTER=demo
export ALLOW_ONCHAIN_EXECUTION=false
export ALLOW_BSC_MAINNET=false
ADMIN_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export ADMIN_API_KEY
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/decision`。首页已加入入口。以上是安全演示配置，不代表钱包付费流程已具备上线条件。

预览 API 不发网络请求、不签名、不执行交易。市场列表仍会读取已有公开索引/A2A；第三方不可达时应显示不可用，不能伪造实时成功。原有公共部署所需的 HTTPS、管理员密钥、CORS、鉴权、真实支付开关等继续遵守原项目配置文档。

```bash
curl -fsS http://127.0.0.1:8000/api/decision/examples
curl -fsS 'http://127.0.0.1:8000/api/decision/market?category=grid_trading'
```

`POST /api/decision/preview` 的结构为 `{"category":"grid_trading","input":{...}}`；具体字段以 `/examples` 和页面可编辑 JSON 为准。示例均标记为合成输入；网格示例若缺成本会故意返回不可执行预览。补齐 `fee_bps_per_side`、`slippage_bps_per_side`、`gas_usd_per_order` 后才会估算净价差。

`POST /api/decision/compare` 传 `{"agent_ids":["从列表获取的ID1","从列表获取的ID2"]}`；必须是同一类别的 2–3 个不同 ID。一个候选不允许虚构第二个。此版本未知供应商即使展示，也不能被错误送入既有单供应商雇佣适配器。

## 4. 真实付费交付重放：仅在已有真实任务时运行

本次没有代用户支付、授权、签名或广播任何主网交易。先在原有手动钱包流程中逐笔确认小额预算与正确网络；保留供应商的**精确交付承诺原文**。不要重排 JSON 字段或改变换行，文件应与链上 keccak256 承诺的 UTF-8 字节完全相同。只拿到 URI、交易哈希或处理后的页面摘要都不够。

claim 是自己真实任务的声明，不是证明本身。必须填真实值，以下占位值不能通过校验：

```json
{
  "chain_id": 56,
  "job_id": 123,
  "settlement_tx_hash": "REPLACE_WITH_REAL_SETTLEMENT_HASH",
  "buyer": "REPLACE_WITH_BUYER_ADDRESS",
  "provider": "REPLACE_WITH_PROVIDER_ADDRESS",
  "token_id": 302258,
  "skill_id": "grid_plan",
  "commitment_scheme": "keccak256_exact_utf8_bytes"
}
```

```bash
python scripts/verify_paid_delivery.py /private/job/claim.json /private/job/deliverable.txt --root .
python scripts/judge_scorecard.py --paid-claim /private/job/claim.json --deliverable /private/job/deliverable.txt --output .data/judge-scorecard-replayed.json
```

依赖不全、RPC 不支持 EIP-1898 精确区块查询、确认不足、未知 ABI、任务/身份/交付/转账不匹配时应非零退出。不要为了视频效果绕过失败。

真实 RPC 适配器本次尚未运行验收；单元测试验证的是注入 Reader 的逻辑。它支持固定 BSC 部署和直接 `settle(uint256,bytes)` 路径，并不声称兼容任意 ERC-8183 变体。12 个确认是项目策略而非绝对终局保证。验证通过也不证明服务正确、资金未来安全、双方为独立公司或策略盈利。

`judge_scorecard` 只计入同进程刚得到的验证对象；不能把保存的 JSON 手工标记 `paid:true` 导入为真。付费结果持久化、自动独立评审验证、结果回灌市场页仍是蓝图待办。

## 5. 配对实验与盲测材料

至少为参赛报告准备三项真实任务，并至少含交易/股票/安全类任务。每项任务保存一份不可变 prompt、一份 Agent 原始输出、一份不用该 Agent 的人工原始输出，记录实际开始/结束时间、可解释的费用以及哈希。不要用脚本瞬间生成“人工结果”来宣称节省时间。

目录约定如下，实际文件名可以不同，但 manifest 内必须是包内相对路径：

```text
my-experiment/
  manifest.json
  task-001/prompt.txt
  task-001/agent.txt
  task-001/manual.txt
```

manifest 结构示意（时间、费用及哈希需要用真实记录替换，不能直接作为参赛证据）：

```json
{
  "schema_version": "safehire-paired/1",
  "tasks": [{
    "task_id": "task-001",
    "category": "grid_trading",
    "prompt_path": "task-001/prompt.txt",
    "prompt_sha256": "REPLACE_SHA256",
    "agent": {
      "prompt_sha256": "REPLACE_SAME_PROMPT_SHA256",
      "output_path": "task-001/agent.txt",
      "output_sha256": "REPLACE_AGENT_OUTPUT_SHA256",
      "started_at": "REPLACE_REAL_ISO8601_WITH_TIMEZONE",
      "finished_at": "REPLACE_REAL_ISO8601_WITH_TIMEZONE",
      "cost_usd": 0,
      "cost_basis": "REPLACE_ACTUAL_BILLED_COST_AND_EXCLUSIONS"
    },
    "manual": {
      "prompt_sha256": "REPLACE_SAME_PROMPT_SHA256",
      "output_path": "task-001/manual.txt",
      "output_sha256": "REPLACE_MANUAL_OUTPUT_SHA256",
      "started_at": "REPLACE_REAL_ISO8601_WITH_TIMEZONE",
      "finished_at": "REPLACE_REAL_ISO8601_WITH_TIMEZONE",
      "cost_usd": 0,
      "cost_basis": "REPLACE_ACTUAL_COST_AND_LABOUR_ACCOUNTING"
    }
  }]
}
```

```bash
python scripts/paired_benchmark.py /private/my-experiment/manifest.json
python scripts/paired_benchmark.py /private/my-experiment/manifest.json \
  --public-dir /private/evaluation-public-new \
  --private-dir /private/evaluation-reveal-new
```

只将 public 目录交给评审，不公开 reveal。评审人身份、利益冲突、是否认出输出作者应另行记录。生成 A/B 包不等于完成独立评审，不自动产出质量提升或冠军分数。本地校验器支持 1–100 项便于调试；“能通过校验”不等于满足 TermiX 的三项真实任务参赛门槛。

## 6. 回归测试与上线阻塞项

```bash
python -m pytest
python scripts/static_security_check.py
ruff check src apps tests scripts
mypy src apps scripts
node --check apps/web/assets/decision.js
```

完整项目原有 CI 还包括合约编译、覆盖率门槛、Docker 和 Agent Studio TypeScript 构建。以上全绿、真实钱包流程验收、公开站点可访问后才进行正式发布。

在本次受限环境中：可运行测试 138 项通过；完整 pytest 因缺 `eth_account` / `eth_abi` 在三个测试文件收集时中断。Ruff、mypy、合约、TypeScript 和 Docker 未运行，不宣称原 CI 全绿。完整日志见发行包 `verification/` 与测试报告。

浏览器测试需要独立安装测试工具：

```bash
python -m pip install playwright
python -m playwright install chromium
PYTHONPATH=src python scripts/champion_browser_smoke.py --output .data/champion-browser
```

这是隔离的 DOM + ASGI 合成测试；页面内的 fetch 被测试桥接替代，不测试原生浏览器网络、完整应用生命周期、真实供应商、钱包或链。截图带明确合成标识，不能当作已上线证明。

## 7. 提交前必须补的真实证据

先接第二家同类真实供应商并完成适配，再展示具体成本/输出/执行范围的比较；补齐四类真实深度，尤其 LP 区间管理；用用户明确批准的小预算取得真实交付；完成三个配对任务和实际独立评审；最终录制公开版本上的发现→比较→风险预览→用户确认→交付核验，另展示一次失败被阻止。

官方日期为 2026-09-09（UTC+0），具体时分本轮未核实，应提前提交。额外供应商、盲审和付费回放是本项目冲刺证据建议，不能说成官方指定的所有参赛条件；准确规则见竞品报告来源索引。
