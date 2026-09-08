# 主网订单 #56733 未交付排查

2026-09-08 排查结论：付款已成功，签名校验通过，链上没有提交交付物。故障边界位于外部供应商接单后的处理/存储/提交环节，具体运行异常尚需供应商日志确认。本报告不是已修复交付的声明。

## 已实际验证

- SafeHire `/api/live-hire/status/56733`：FUNDED，submitted_at=0，交付哈希全零；原始报价签名验证有效。
- SafeHire `/api/live-hire/delivery/56733`：400，job #56733 has no submitted delivery。
- 07:23:03 UTC 对已付款订单重新通知一次，供应商明确回复 accepted 与 delivery started；没有追加付款。
- 供应商 `/erc8183/job/56733/response`：404，no deliverable stored for job 56733。不是我们网站漏读了一份已公开文件。
- 供应商独立业务接口 `/health`、`/status`、`/positions` 返回 200，链上读取正常，仓位 #7319347 可读。它是供应商的公开示例仓位，不是用户钱包资产。
- 供应商钱包有非零 BNB 余额；这不能单独证明其模型、存储或签名运行环境正常。
- A2A 返回的 taskId 查询为 Task not found。官方卡已说明没有任务查询接口，所以不能据此断言任务被删除。

## 公开代码里复现的误导性回执

仓库 [criox4/BNB-LP-Range-Rebalancer](https://github.com/criox4/BNB-LP-Range-Rebalancer)，读取版本 d3456128c197808fb3ab2d82c0f83dd4296980d6。README 的域名和链上身份与当前供应商一致；未确认其实际部署版本。

`seller_core.py` 中：

1. notify_funded 在预校验失败或超时时仍可接受通知，留给后台重验。
2. _run_job 把成功和永久跳过都保留在 _inflight 集合。
3. _spawn_job 遇到已保留的编号直接返回，不创建任务。
4. notify_funded 不检查是否真正安排了工作，仍统一回复 delivery started。

隔离测试提取这三个公开方法，模拟已保留的任务编号与校验成功，实际得到 accepted，但工作调用次数为零。这个控制流程缺陷已经复现；它不能替代该笔生产订单的私有错误日志，不能断言它就是本单唯一根因。

## 本地修正与外部剩余工作

SafeHire 通知结果增加明确字段：只确认收到通知，未验证开始执行；界面不再声称供应商已开始工作或已验证其重试幂等性。签名、链上哈希、付款与退款规则保持原样。

供应商需从 seller-agent 日志提取 #56733 的预校验、模型执行、submit_workflow 异常和永久跳过原因，修复后在原订单、原签名条款下补交。不能靠再付一单、更换交付物或绕过签名来假装完成。技术故障报告已在本地准备；未经用户授权不向外部人员发送。

原始排查响应和隔离复现脚本保存在忽略目录 `.data/delivery-debug-2026-09-08/`，未公开私人配置或凭据。
