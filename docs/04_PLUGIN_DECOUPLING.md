# 插件解耦设计

## 为什么用插件

Agent 评分、证据、基准测试、对抗评审和 Pancake 策略会持续换版本。它们通过 manifest 声明“我提供什么、依赖什么”，核心应用只依赖能力名，不直接绑定实现类。

## 生命周期

1. 读取 `config/plugins.json`。
2. 验证 id、version、entrypoint、provides/requires。
3. 对依赖图排序；缺少必需能力或循环依赖即停止启动。
4. 依次 load；关键插件失败时回滚已启动插件。
5. 运行时通过 capability resolver 获取实例。
6. 关闭时倒序 unload。

## 安全界面

- manifest 是本地信任配置，不应允许用户从 Web 界面上传 Python entrypoint。
- 插件可生成提案和证据，不拥有最终执行权。
- 所有插件事件进入 trace subscriber 和 hash-chain ledger。
- 钱包私钥、平台密钥、B402 RSA 密钥不进入 plugin config。
- 第三方 Agent 只通过 HTTPS 协议边界接入，不动态 import 不受信任代码。

## 如何添加新能力

1. 定义稳定的 capability 名和输入/输出协议。
2. 在 manifest 声明必需与可选依赖。
3. 插件测试覆盖正常启动、缺依赖、重复能力、回滚和 unload。
4. 如果能力可影响资金，只能返回意图，不直接发交易。
