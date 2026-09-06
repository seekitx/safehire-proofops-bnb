# 本地 API 施工示例

先运行 `PYTHONPATH=src python scripts/arena_local_server.py --port 8092`。以下只针对本地分析服务，不涉及钱包、真实代理、交易或外部报价。别把服务绑定到公网来跳过访问控制。

## 一个可以直接执行的流程

在另一个终端，用当前项目的 Python 环境执行：

```python
import json
import uuid
import httpx

BASE = "http://127.0.0.1:8092/api/arena"
with httpx.Client(timeout=10) as client:
    def call(method, path, **kwargs):
        response = client.request(method, BASE + path, **kwargs)
        response.raise_for_status()
        return response.json()

    # 合成数据，绝非历史/实时市场状态。
    task = call("GET", "/examples")["tasks"]["grid_trading"]
    preview = call("POST", "/preview", json=task)
    record = call("POST", "/tasks", json=task)
    headers = {"Authorization": "Bearer " + record["task_token"]}
    ids = []
    version = record["version"]

    for n in range(2):
        proposal = json.loads(json.dumps(preview["reference_proposal"]))
        if n:
            proposal["agent_ref"] = "local:deliberately-bad-example"
            proposal["parameters"]["stop_price"] = 999
        raw = json.dumps(proposal, ensure_ascii=False, separators=(",", ":"))
        result = call("POST", f"/tasks/{record['task_id']}/proposals",
                      headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
                      json={"proposal_text": raw, "expected_version": version})
        ids.append(result["proposal_id"])
        version = result["version"]
        print(proposal["agent_ref"], result["report"]["policy_accepted"])

    compared = call("POST", f"/tasks/{record['task_id']}/compare",
                    headers=headers, json={"proposal_ids": ids})
    assert len(compared["eligible_agent_refs"]) == 1
    assert compared["winner"] is None  # 通过约束不代表供应商质量冠军。
    bundle = call("GET", f"/tasks/{record['task_id']}", headers=headers)
    assert bundle["integrity"]["valid"]
    assert not bundle["paid_delivery_verified"]
    with open("synthetic-private-bundle.json", "w", encoding="utf-8") as stream:
        json.dump(bundle, stream, ensure_ascii=False, indent=2)
    # 不输出 capability token。保留独立 head 可检查今后是否改写。
    print("Journal head:", bundle["integrity"]["head"])
```

校验导出的原文、事件与报告的一致性：

```bash
python scripts/arena_verify_bundle.py synthetic-private-bundle.json
python scripts/arena_verify_bundle.py synthetic-private-bundle.json --trusted-head 你单独保存的实际head
```

退出码0是结构完整性验证通过；2是验证失败。没有 `--trusted-head` 时无法检查“相对于外部保留的最新版本”是否被回滚。

## 错误处理约定

收到409先保持同一个task token，用GET刷新版本；不能刷新网页丢掉内存token。对于结果未知的网络失败，第一次重试应重用相同Idempotency-Key及原始字节；变更业务请求则新键＋新版本。UI已保留未确认请求的键，并提供 Refresh task status，不必清空当前task。

收到过期结果不要改旧Task的observed_at来“刷新”：那会把旧数据伪装成新数据。真正重新拉取源快照，创建新的task。结果比较重新计算TTL，而非复用历史通过标记。

收到报价不可用、402、429或超时，先展示“未取得报价”，不自动换provider，也不回退成“Demo succeeded”。
