# TermiX 原始证据

三组 live 对照已经完成。这里保留的是实际输入输出，不是只写一句“Agent 更好”的宣传稿。

- `tasks/`：三份冻结任务；Agent 和不使用 Agent 的对照侧读取同一输入。
- `raw/<task-id>/agent-output.json`：公开 SafeHire A2A 赞助雇佣的完整请求、响应、耗时和 hash-chain 回执。
- `raw/<task-id>/manual-output.json`：不调用市场 Agent 的直接公式计算和风险边界。
- `live-manifest.json`：双方时间、真实成本、统一五项评分和方法。
- `agent-advantage-report.json`：带原始文件 SHA-256 指纹的机器可核验报告。
- `AGENT_ADVANTAGE_REPORT.md`：给评委看的大白话摘要。

三次赞助雇佣的真实成本是 `0 U`，不是 `0.1 U` 付费订单。官方 TermiX 要求报告真实成本，但没有公开规定每个样本都必须付费或上链结算。独立的 Job #808 只用来证明 SafeHire 具备完整 `0.1 U` ERC-8183 付费闭环，不冒充这三次样本的付款。

当前自动评分必须由参赛者在最终提交前浏览确认。官方要求同题实际输出、耗时、成本和质量；没有公开要求独立人类评分人。SafeHire 仍明确披露“自动规则评分、参赛者复核待完成”，不把它写成人类研究。

重新采集：

```bash
PYTHONPATH=src python scripts/capture_termix_live_comparisons.py \
  --public-base-url https://safehire-proofops-bnb.onrender.com
```

fixture 或 synthetic 路径、缺文件、占位评分标签、全零评分和少于三题都会被 live 模式拒绝。
