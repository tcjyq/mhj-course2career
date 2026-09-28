# ADR 008：注册防滥用与平台 AI 预算熔断

日期：2026-09-27。状态：C08-E1 分支实施；生产 Turnstile 配置已人工确认，合并、schema v4 迁移与生产 smoke 未完成。

## 背景

公开注册和按账号计数的免费 System AI 可以被批量账号绕过。认证 token 不能兼作设备标识。作品集 Demo 需要有限的注册摩擦和可证明的公共凭证调用上界，不承诺“一人一号”。

## 决定

公开注册先通过 Turnstile 服务端 Siteverify，校验成功、精确 hostname 和 `register` action；再计算密码哈希，并在同一数据库事务内按独立 installation 哈希限制滚动 24 小时 2 次、7 天 3 次成功注册。浏览器生成 32 字节随机 `c2c_installation_id`，仅本地保存原值，数据库只存 SHA-256。缺标识或验证失败只关闭新注册与受补贴 System AI，不影响已有登录、本地规则和 BYOK。

平台调用在发起任何 Provider 请求前原子预留。Guest 每会话 2 次、Free 每用户 5 次、Pro/Developer 套餐每用户 20 次；当前和注册来源 installation 的 `public_free` 池为 10 次、`assigned_20` 池为 20 次。Developer Mode 不改变 Plan 额度。非 Admin 全站当日上限 100 次，所有 System Key 调用含 Admin 的绝对上限 120 次。东八区自然日；失败和保留状态都计数，不自动返还。System AI 输出 token 上限 4096，已有更低上限保留；BYOK 不占平台补贴池。

Schema v4 仅给 `users` 增加可空来源哈希，给 `api_usage` 增加可空当前哈希与预留时额度类别。旧用户来源为空，不伪造补录。哈希在用量 8 天、来源 30 天后不再参与风控识别，并在后续相关写事务中限量清除；无定时任务，不声称精确物理删除。

## 结果与限制

此标识可被浏览器持有人重置或复制，共享设备可能共用额度；Turnstile 也不能阻止人工批量注册。全站与绝对熔断限制公共凭证的每日请求数，但不等于货币支出上限。Turnstile 处理其自身的浏览器挑战信号；本站不采集 IP 或设备指纹。公开测试键只供本地测试。Cloudflare 生产 widget 已由用户人工创建，hostname 为 `mhj-course2career.streamlit.app`；`TURNSTILE_SITE_KEY` 和 `TURNSTILE_SECRET_KEY` 已人工保存到 Streamlit Secrets，值未被读取、输出、提交或分享。真实注册与 System AI 生产 smoke 尚未完成，`RELEASE_READY=no`。详细威胁、测试与回退见 [C08-E 设计](../c08-e-registration-abuse-design.md)。
