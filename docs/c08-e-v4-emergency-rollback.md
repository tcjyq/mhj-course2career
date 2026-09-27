# C08-E schema v4 紧急回退构建

状态：**仅预备，不是上线授权**。构建基于生产基线 `07d09de8225ecb72ca2739ecbebf5ee1c4211536`，分支为 `fallback/c08-e-v4-compatible`。它只用于 C08-E1 已将生产 PostgreSQL 从 schema 3 升至 4 后的紧急部署，不替代正常 E1 版本。

## WHEN_TO_USE

仅当 E1 上线后出现必须立即停止 E1 代码运行的故障，且生产库已经是 schema v4，并已确认该 fallback 提交的合成 PostgreSQL/CI 验证通过时使用。若数据库或 Secrets 本身故障，先按现有数据库故障流程处理；此构建不会修复不可连接的数据库。

**生产 schema 已到 v4 后，绝不能重新部署 E1 之前的 main。**旧 main 只接受到 schema 3，会在初始化时拒绝 v4。只使用本文件对应的、经过验证的 v4 兼容 fallback 分支及确定的提交。

## HOW_TO_DEPLOY

1. 操作员只读核对当前生产部署提交、数据库 schema 版本与故障范围，并记录拟部署的已验证 fallback 提交 SHA。此文档不授权本任务连接生产库。
2. 在 Streamlit Community Cloud 中将应用代码源切到该确定提交对应的 `fallback/c08-e-v4-compatible`；保持原有生产数据库、加密主密钥与其他 Secrets 原值。不得使用旧 main，也不得运行手工降级 SQL。
3. 等待平台更新后做只读/合成 smoke：页面可启动；已有账号登录、刷新恢复、登出；历史、Admin、Provider 配置可读；本地规则可用。使用自己已配置的 BYOK 时避免真实 Provider 请求，先核对解密和 UI 可见性。
4. 确认注册页显示维护提示，分析页无“系统AI”选项，服务层拒绝平台 System Key 调用。若这些保护缺失，立即停止使用该构建并排查部署 SHA。

## EXPECTED_FEATURE_DEGRADATION

- 公开注册暂停，页面提示“新账户注册暂时维护中，请稍后再试。”已有账号仍可登录。
- 所有平台资助的 System AI 暂停，包括管理员；原有平台 Key 即使仍在 Secrets 中也不触发调用。
- 本地规则、已配置的 BYOK、持久登录、历史记录、Developer Mode 和 Admin Dashboard 继续工作。BYOK 仍可能产生用户自有 Provider 费用。
- 紧急构建不提供 E1 的新增注册/安装标识配额；通过关闭这两条入口避免退回旧版无限制行为。

## DATABASE_INVARIANTS

- v3 数据库按既有 v3 迁移路径启动；已存在 v4 数据库只读兼容，不执行 v4→v3 迁移。
- v4 的 `users.registration_installation_hash`、`api_usage.installation_hash`、`api_usage.quota_class` 及索引保留。fallback 不删除、清空、回填这些列，不改写现有业务行或 `schema_migrations`。
- 生产连接仍要求 PostgreSQL、`sslmode=verify-full`、主机名验证与显式 certifi CA bundle；连接或配置失败时停止，不回退 SQLite。
- 加密主密钥必须保持原值，才能解密已有 BYOK 密文。服务端登录会话继续使用原有 schema 3 `auth_sessions` 结构。

## HOW_TO_RETURN_TO_NORMAL_E1

先在独立合成 PostgreSQL v4 中验证修复后的 E1 版本以及注册、配额和浏览器流程，再取得单独发布授权，将应用代码源切回已验证的 E1 修复提交。保留 schema v4 和全部数据；恢复前确认正式 Turnstile 生产配置齐备，恢复后重新做生产 smoke。不要将 fallback 分支合并进 E1 或 main 作为常规功能。

## WHAT_NOT_TO_DO

- 不部署 pre-v4 main；不 `DROP`、`SET NULL`、回退 schema 版本或恢复旧数据库快照覆盖现有生产数据。
- 不通过修改生产账号、Secret、TLS 等级或禁用服务端校验来绕过故障。
- 不在 fallback 中重新开放公开注册或平台 System AI；不调用真实 Provider API 来证明回退代码可用。
- 不把本地合成库测试或 CI 通过表述为生产回退演练成功。实际启用必须另获明确授权。
