# TermiX 原始证据

这里不能放“我们自称 Agent 更快”的总结冒充证据。真实报告至少需要三组相同任务，分别保留 Agent 和人工的完整输入、输出、开始/结束时间、成本，以及同一套五项评分。

操作顺序：

1. 使用 `evidence/termix/tasks/` 中的三份固定任务定义；Agent 和人工必须看同一份文件，不能临时给其中一方补提示；
2. 把每次原始输出放在 `evidence/termix/raw/<task-id>/`，并记录真实开始、结束时间；
3. Agent 侧同时记录实际支付的 `0.1 U` 和用于汇总的美元估值；人工侧记录实际工具成本，不把自己的时间强行折算成美元；
4. 让一位没有参与产出的人按正确性、完整性、风险意识、可操作性、证据质量各打 0–5 分；
5. 运行 `PYTHONPATH=src python scripts/build_termix_report.py <manifest>`；
6. 检查生成的 `agent-advantage-report.json` 中仍为 `evidence_mode=live`，文件 hash 与原始输出一致。

fixture 或 synthetic 路径、占位复核人、全零评分都会被 live 模式直接拒绝。Job #808 可以作为“缺少输入时安全拒绝”的补充案例，但不应冒充 Agent 优势主样本。
