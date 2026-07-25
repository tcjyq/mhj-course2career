# 用户权限与请求链路

## 角色与套餐权限

角色控制安全边界，套餐控制产品能力。权限必须同时被当前角色和套餐允许。

| 套餐 | 平台AI | 保存记录 | 高级报告权限 | 自带Key | 管理权限 |
|---|---:|---|---|---|---|
| Free | 每天5次 | 允许 | 不允许 | 不允许 | 不允许 |
| Pro | 每天20次 | 允许 | 允许 | 不允许 | 不允许 |
| Developer | 每天20次 | 允许 | 允许 | 不限自带Key调用 | 不允许 |
| Admin | 不限 | 允许 | 允许 | 允许 | 允许 |

游客不持久化套餐，每个匿名会话每天可体验2次平台AI。

公开注册只能创建`user + Free`。Developer和Admin身份不能由注册表单选择。套餐变更必须经过服务端`MembershipService`，当前仅管理员能够执行。

## 请求链路

本地规则请求：

```text
页面请求
→ 读取当前Principal
→ 检查demo:use
→ 本地JD规则提取
→ 原有AnalysisService
→ 登录用户保存历史
```

平台AI请求：

```text
页面请求
→ 读取当前Principal
→ 检查ai:use_system
→ 查询角色日额度
→ SQLite事务预占一次调用
→ 使用平台Secrets创建模型客户端
→ 结构化JD提取
→ 将调用标记为成功或失败
→ 原有AnalysisService
→ 登录用户保存历史
```

开发者自带Key请求：

```text
页面请求
→ 检查ai:use_own_key
→ 确认角色为developer或admin
→ 按OpenAI或DeepSeek读取当前用户的密文
→ 使用环境变量中的主密钥在服务端解密
→ LLMProviderFactory创建统一供应商客户端
→ 记录调用次数但不扣平台日额度
→ 调用模型
→ 原有AnalysisService
```

## 安全边界

- 密码使用带随机盐的scrypt哈希，SQLite中不保存明文密码。
- SQL查询全部参数化。
- 开发者Key使用AES-256-GCM和随机nonce加密；SQLite只保存密文、nonce和末四位。
- 密文通过用户ID和供应商名称作为附加认证数据绑定，不能跨用户或供应商替换。
- 完整开发者Key不进入页面列表、日志、报告或错误信息。
- 平台Key只从环境变量读取。
- 加密主密钥只从`COURSE2CAREER_KEY_ENCRYPTION_KEY`读取，不写入数据库。
- 用户只能按自己的`user_id`读取分析历史。
- 管理状态查询在服务端验证`admin`角色。
- 额度按东八区自然日计算，时间戳以UTC保存。
- 当前游客额度绑定匿名Streamlit会话；公开部署前还需要网关级IP/设备限流。
