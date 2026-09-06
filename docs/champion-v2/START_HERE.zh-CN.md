# SafeHire 冠军冲刺 V2：开工说明

版本日期：2026-09-06。目标：BNB「The Smart Money Era: Build the Era」主赛。**本包是功能增强，不是夺冠保证或生产安全审计。**

## 1. 从哪一版继续

本次基于你已提交的 `feat/evidence-first-decision-desk-2026-09-05` 分支，提交：

```text
447095f73f7d17338d7ec2c35cc19ce1a99da384
```

不是停留在 `main` 的 `267e4978`，也不是再次发上一次补丁。GitHub 已核对分支、提交和源目录 Git tree 哈希。受运行环境网络限制，工作副本由之前的原始归档及 V1 完整文件重建，再与上述提交的 `apps/src/scripts/tests/config/AGENTS.md` 哈希逐一对上；修改范围内的基线一致。其他未同步历史目录不作为“最新全仓快照”交付。

**本 ZIP 是带完整修改文件内容的增量源码包，不是完整仓库。** `overlay/` 内每个文件都是完整源代码，不只是片段。它保留你目前的链上证据、Agent Studio 目录、钱包配置、旧入口和部署数据。不要把 `overlay/` 当成新项目目录单独启动。

## 2. 本轮落地的产品主线

不是再注册几个自营 Agent，而是把“目录里有谁”推进成：

> 固定任务、快照和约束 → 取得方案 → 独立重算约束 → 同任务比较 → 保留原始交付和校验记录。

新增 `/arena`，不替换已有 `/`、`/decision`、`/hire-live`、`/proof`。`/arena` 没有签名、批准、转账、下单或自动结算权限。

已经落地：四类验收计算；可配置的身份＋技能报价路由；只读报价熔断；私有任务 SQLite 记录；并发版本控制；精确原文幂等；离线完整性校验；四类无 JSON 操作的合成引导；测试与应用/回滚材料。

还未落地为真实业务：第二家已核验独立供应商、自动获取可信链上状态、供应商交付签名认证、Arena 任务和已付款链上任务的认证桥接、四类实际受限执行、独立人工质量评价及公开部署联调。不能从“测试通过”推导出这些完成。

## 3. 安全应用

在你自己的仓库目录先检查状态，保留尚未提交的更改；不要使用 `reset --hard` 清空工作区。

```bash
git fetch origin
git switch feat/evidence-first-decision-desk-2026-09-05
git status --short
git switch -c feat/task-acceptance-arena-v2

# 将路径换成实际解压位置；默认也是只检查。
python3 /解压位置/SafeHire_BNB_Champion_V2_2026-09-06/apply_overlay.py . --check
python3 /解压位置/SafeHire_BNB_Champion_V2_2026-09-06/apply_overlay.py . --apply
```

脚本逐文件核对旧/新 SHA-256。基线冲突、源包被篡改、路径逃逸或符号链接都会拒绝；不会强行覆盖你提交后的更改。先完整备份再写入，打印回滚路径。应用期间请暂停编辑这些文件；这不是跨进程文件系统锁。

## 4. 最快验证新功能

推荐 Python 3.11+，沿用仓库原依赖，不新增支付 SDK。依赖完整的开发环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,bnb]'
python -m pytest tests/arena -ra
python -m pytest -ra
python scripts/arena_check_providers.py config/arena-providers.json
```

仅查看本轮分析功能，不启动原链上组件：

```bash
PYTHONPATH=src python scripts/arena_local_server.py --port 8092
# 浏览器访问 http://127.0.0.1:8092/arena
```

这是仅绑定回环地址的本地分析服务器，强制关闭外部报价；它不是完整 marketplace，也不能验证旧雇佣流程。页面有明显 LOCAL/SYNTHETIC 标识。默认数据库 `.data/arena-local.sqlite3`，不要上传 `.data`。

完整应用测试环境（按原部署方式启动亦可）：

```bash
export SAFEHIRE_ARENA_ENABLED=true
export SAFEHIRE_PROVIDER_QUOTES_ENABLED=false
PYTHONPATH=src uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

`SAFEHIRE_ARENA_ENABLED` 默认 `false`：公开预览和合成引导可用，私有任务创建关闭。报价还需要全局开关和逐路由的 `quote_enabled`，二者缺一不可。不要为录视频打开未经核验的真实报价或支付。

## 5. 接下来读什么

| 文档 | 用途 |
|---|---|
| `GAP_AND_COMPETITORS.zh-CN.md` | 业务、创新、评委、竞品四维差距与依据 |
| `CONSTRUCTION_BLUEPRINT.zh-CN.md` | 模块、状态、公式、接口、施工顺序与验收 |
| `PROVIDER_AND_REAL_EVIDENCE.zh-CN.md` | 第二供应商接入、真实数据与付费交付如何补证 |
| `RELEASE_AND_DEMO.zh-CN.md` | 灰度发布、威胁边界、三分钟演示和回滚 |
| `API_EXAMPLES.zh-CN.md` | 可执行本地 API 示例，零真实付款 |
| `TEST_REPORT.md` | 本轮实际执行结果及未通过/未运行部分 |
| `backlog.json` | 给 coding agent 的具体任务状态和验收目标 |

任何 coding agent 修改前应读根 `AGENTS.md`。不能把本地 fixture 改名成竞争对手，不能把输入里的 `paid:true` 或 `verified:true` 当作真实链上证据。
