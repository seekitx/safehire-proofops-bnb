# TermiX 原始证据

这里不能放“我们自称 Agent 更快”的总结冒充证据。真实报告至少需要三组相同任务，分别保留 Agent 和人工的完整输入、输出、开始/结束时间、成本，以及同一套五项评分。

操作顺序：

1. 复制 `templates/termix/live-manifest.template.json`，补成至少三项真实任务；
2. 把每次原始输出放在 `evidence/termix/raw/<task-id>/`；
3. 让独立复核者按正确性、完整性、风险意识、可操作性、证据质量各打 0–5 分；
4. 运行 `python scripts/build_termix_report.py <manifest>`；
5. 检查生成的 `agent-advantage-report.json` 中仍为 `evidence_mode=live`，文件 hash 与原始输出一致。

fixture 或 synthetic 路径会被 live 模式直接拒绝。
