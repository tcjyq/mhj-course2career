# ADR 005：开发者模式作为独立的自助 BYOK 能力

日期：2026-09-23。状态：C08-B3 本地实施，生产未发布。

## 背景

原权限要求 `Role.DEVELOPER` 与 `Plan.DEVELOPER` 同时成立，但会员页的 Developer 升级只是演示。普通注册用户无法通过产品界面获得 BYOK。把自带 Key 能力绑定付费套餐也会错误提升平台系统 AI 日额度。

## 决定

保留现有 Role、Plan 枚举及历史用户数据。Role 负责身份和管理权限，Plan 负责平台额度；普通登录用户的开发者模式由 `user_byok_settings(user_id, byok_enabled, updated_at)` 独立持久化。用户自行启用或关闭，不改变 Role/Plan。Admin 与历史 `Role.DEVELOPER` 或 `Plan.DEVELOPER` 继续具有 BYOK 权限。

Key、Provider Profile 和用户 Key 调用在服务边界重新读取持久化开关，不依赖旧会话中的权限快照。关闭后拒绝新 BYOK 操作，保留原加密 Key；重新开启后可继续使用。`key_mode=system` 仍按原 Plan 额度计数，`key_mode=user` 不占平台额度。模式表随现有 SQLite 初始化事务创建，重复初始化不覆盖状态；失败时回滚。

## 结果与限制

普通 Free/Pro 用户可直接使用自己的 Key，会员页仅保留 Free/Pro 套餐演示。此开关不改变供应商费用归属，也不完成真实 Provider 模型验证。现有 Streamlit Community Cloud SQLite 持久化限制仍在；生产发布前需要备份与恢复演练。C08-C 模型发现与 C08-D 自定义端点分别处理。
