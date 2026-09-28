# C08-E1 生产发布记录

日期：2026-09-28（北京时间）。范围：公开注册防滥用与平台 System AI 补贴额度／熔断；本记录不把其他旧路径的未执行手工回归写成通过。

## 发布与回退

- [PR #3](https://github.com/tcjyq/mhj-course2career/pull/3) 已合并到 `main`，merge/main SHA 为 `f8f99406d04948ff227354394c4344ab7f75753b`。[main CI run 36411890289](https://github.com/tcjyq/mhj-course2career/actions/runs/36411890289) 的 quality 3.11/3.12/3.14、PostgreSQL integration 3.12/3.14 五项作业全部成功。
- Streamlit 生产环境已运行 E1；独立 production PostgreSQL 的 schema v4 加法迁移通过。Cloudflare 生产 Turnstile widget 与精确 hostname `mhj-course2career.streamlit.app` 已验证；所需 Streamlit Secrets 由用户人工配置，值未写入仓库或本记录。
- 应急回退分支 `fallback/c08-e-v4-compatible` 保留在 `7fd7ae90f21df862802f404614f66ccd4555eb27`。schema v4 后不能直接部署只理解 schema v3 的旧版 main；回退边界见[该提交的应急说明](https://github.com/tcjyq/mhj-course2career/blob/7fd7ae90f21df862802f404614f66ccd4555eb27/docs/c08-e-v4-emergency-rollback.md)。

## 生产 smoke 证据

| 项目 | 结果与边界 |
|---|---|
| 注册与认证 | 真实生产 widget、公开注册、F5/Ctrl+R/新标签页登录保持、登出后刷新均通过；旧账号登录不要求重新经过注册 Turnstile。 |
| 数据与本地规则 | schema v4 只读核验通过；游客本地规则分析通过。 |
| System DeepSeek | 经正常生产页面只提交一次最小 JD；页面提取 2 项技能。只读核验 `api_usage` 从 0 增至 1，唯一新记录为 `system / deepseek / deepseek-flash / public_free / success`，输出 84 tokens，无重复预留或自动返还。 |
| 四个额度桶 | Guest 日额度、当前 installation 的 `public_free` 桶、非 Admin 公开全局计数、全部 System Key 绝对计数均由 0 增至 1；每项只计一次逻辑预留。 |
| Provider 内部尝试 | 成功记录中的模型为 `deepseek-flash`。Auto-Safe 的实际 fallback 使用情况及 SDK 内部 HTTP 尝试次数未安全观测，记为 `UNKNOWN`，不能从一条 `api_usage` 推断只有一次 HTTP 尝试。 |
| Secret 暴露检查 | 本次浏览器页面、URL 与控制台扫描未观察到生产凭证；未读取生产 Secret 值，Cloud 服务端日志未核验。仓库静态模式扫描不替代未知格式的完整凭证审计。 |

### 测试账号凭证事件

生产注册 smoke 所建的一次性测试账号，其随机密码曾出现在任务工具日志中；**事件确实发生过**。随后在仅针对该唯一账号的一个生产数据库事务内，以应用现有 scrypt 实现写入无人知晓的新随机密码哈希、递增 `session_version`，并撤销该账号全部未撤销的服务端会话。提交后只读核验：目标仍唯一、凭证哈希已替换、版本递增、未撤销会话为 0、schema 仍为 v4。旧泄露密码没有从日志取回或再次用于登录测试，因此 `OLD_PASSWORD_REJECTED=NOT_RETESTED`；凭证替换与会话失效是访问中和依据。账号状态仍为 `active`，**没有声称停用账号**；注册审计、`api_usage` 和安全记录保留。`TEST_ACCOUNT_CREDENTIAL_INCIDENT=contained`，不等于“从未泄露”。

## 最终状态与剩余手工项

`C08_E1_CODE_READY=yes`、`CI_READY=yes`、`PRODUCTION_CONFIG_READY=yes`、`ROLLBACK_READY=yes`、`REGISTRATION_PRODUCTION_SMOKE=yes`、`SYSTEM_AI_PRODUCTION_SMOKE=yes`、`PRODUCTION_SMOKE_READY=yes`、`RELEASE_READY=yes`。

`ADMIN=MANUAL_PENDING`、`DEVELOPER_MODE_AUTHENTICATED=MANUAL_PENDING`、`BYOK_SMOKE=MANUAL_PENDING`，均为本次 E1 非阻断项，**不是 PASS**。E1 核心范围是注册保护及平台 System AI 补贴额度；BYOK 独立且不扣 System 额度，Developer Mode 不提升 Free 用户 System AI 额度并已有自动化覆盖，旧账号与管理员登录不需要注册挑战。目前没有证据表明这些旧路径被 E1 破坏；后续手工回归仍应如实补记。
