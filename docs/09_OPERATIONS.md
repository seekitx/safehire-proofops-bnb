# 部署与运维

## 本地运行

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,bnb]'
python scripts/seed_demo.py
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

本地默认 demo，不需要钱包私钥。浏览器钱包签名只用于验证 owner，不进入服务器日志。

## Docker

```bash
cp .env.example .env
docker compose up --build
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

容器使用非 root 用户、只读文件系统、去除 Linux capabilities，只对 `.data` 持久化。

## 生产环境变量

- `APP_ENV=production`
- `PUBLIC_BASE_URL=https://...`
- `GITHUB_REPO_URL=https://github.com/...`
- 长随机 `ADMIN_API_KEY`
- `EXECUTION_MODE=bsc_testnet`
- `EXECUTION_ADAPTER=remote_agent`
- `ALLOW_ONCHAIN_EXECUTION=true`
- `ALLOW_BSC_MAINNET=false`
- `REMOTE_AGENT_AUTH_TOKEN` 从 secret manager 注入
- 生产 RPC、The Graph key、8004scan key 从 secret manager 注入

## 监控

| 信号 | 告警条件 |
|---|---|
| `/health/live` | 进程无响应 |
| `/health/ready` | 证据链无效 |
| BSC RPC | chain id 不匹配、块高长时间不动、超时率高 |
| official source adapters | schema 错误或连续失败；不转 fixture |
| tasks | executing 长时间不结束、failed 激增 |
| risk decisions | 重复 key、越权 target、超额拒绝异常增多 |
| sessions | 签名失败和 401 异常增多 |

## 备份与恢复

- 每日备份 SQLite 主库和 WAL/SHM 一致快照，每次提交前导出 evidence head。
- 证据 JSONL 不原地编辑；有损坏就从已验证备份恢复。
- 恢复后先跑 ledger verify，再开 remote execution。
- kill switch 默认能在数据库中立即打开；事故期间不重启绕过它。

## 发布回滚

1. 发布前备份数据库和 ledger head。
2. 发布新容器，只做 read-only smoke test。
3. 跑钱包登录、预演、超额拒绝；不默认发链上交易。
4. 出现 schema/证据链错误立即打 kill switch 并回滚容器。
