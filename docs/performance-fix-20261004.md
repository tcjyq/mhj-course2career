# Course2Career 性能修复实施报告（2026-10-04）

状态：本地候选，`RELEASE_READY=no`，`PRODUCTION_UNVERIFIED`。没有 merge、deploy、生产 DB tracing、读取生产 Secrets 或真实 Provider 请求。本轮不认证 Provider API 的真实性。

## 1. ROOT CAUSES FIXED

- **P1-A：已修复重复读取。** Developer / Analysis 在页面 render 的 context manager 中获取当前 Principal、BYOK 状态、Key metadata / updated_time 和 Provider profiles。只把无密钥元数据的只读映射传给展示路径；不写入 session_state、全局缓存或 service。退出 render 时使 view 失效，完整 Principal 不相同也拒绝复用。
- **P1-B：已实现受控连接复用。** 原先每次 repository 操作新建 PostgreSQL 连接；现在由缓存 repository 的 backend 持有有界 Psycopg pool，每次操作独占借还连接。SQLite 连接路径保持原行为。
- **P1-C：已去掉普通导航固定额外重跑。** 保留旧 page_slot 清空，以路由和身份输入 epoch 为 container key；普通导航同一轮直接渲染目标页。身份清理、存储写入确认、无效 token、登录跳转的必要重跑保留。
- **P2：已消除同轮 restore → refresh。** 仅用脚本局部布尔值标记刚完成的 restore；下一个脚本执行照常刷新服务端会话，角色、BYOK、停用和 revoke 不跨轮缓存。

敏感动作仍使用原有持久权限检查：Key 保存／更新／删除、BYOK 开关、创建 client、真正 AI 请求、需要 Key 的目录刷新、管理员操作都不接收 display view。Developer 保存表单的 Streamlit 回调先于脚本入口执行，因此补充回调内的 session token 复核，防止先前渲染的表单在服务端 revoke 后写入。

## 2. 基线与方法

原工作区 `fix/post-release-production-audit` / `c4efb6e385af401fb9e8f4c1b7f96f35b594ae93` 和四个原有未跟踪文件保留。执行 status、branch、HEAD、fetch、origin/main 后，确认 main 为 `62336cc9ea8541d670b054dc936a59d2d275773b`。独立 worktree 分支为 `perf/reduce-rerun-database-overhead`。

先对该 main 的不可变代码快照重测 BEFORE，再按 display → pool → navigation → restore 顺序分别运行相同合成账号、数据库、浏览器动作与 instrumentation。各有效阶段 94 个动作，外部请求尝试均为 0；每个主场景取三次 warm run。合成 BYOK 用户配置十家 Provider 的假 Key / profile；目录无需真实 HTTP。规则操作运行既有合成演示，不改评分算法。

环境：Windows、Python 3.12、Streamlit 1.60.0、psycopg 3.3.2、psycopg_pool 3.3.3、隔离 localhost PostgreSQL 18.6。仅合成 localhost DB 明确允许 `sslmode=disable`；生产代码保留 `verify-full` + certifi。CI 的 PostgreSQL 17 与真实远程 TLS 延迟另行验证，不能将本地时间当作生产延迟。

计数口径：SQL 是显式 repository execute，不含隐式 BEGIN / COMMIT，也不含 pool checkout 的空查询健康检查。Connect 是动作期间新建的物理连接，不是借连接次数；warm 0 表示池中已有连接，冷启动和断线恢复仍会新建，上限为每 backend 4。Python ms 为该动作所有已完成脚本入口时间之和，含 UI / 导出准备及 instrumentation 文件 I/O，不代表浏览器绘制时间。多阶段使用相同口径。

### BEFORE / AFTER

| Scenario | Before SQL | After SQL | Before Connect | After Connect | Before Runs | After Runs | Before ms | After ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 普通 BYOK Developer 导航 | 58 | 8 | 58 | 0 | 2 | 1 | 2382.98 | 148.95 |
| 普通 BYOK Analysis 导航 | 39 | 7 | 39 | 0 | 2 | 1 | 1389.93 | 125.39 |
| 普通 BYOK 本地规则演示 | 36 | 7 | 36 | 0 | 1 | 1 | 1440.23 | 221.32 |
| 普通用户 quota 导航 | 7 | 4 | 7 | 0 | 2 | 1 | 248.35 | 33.70 |
| 普通用户 membership 导航 | 7 | 4 | 7 | 0 | 2 | 1 | 247.64 | 35.77 |
| 游客首页 → 登录 | 0 | 0 | 0 | 0 | 2 | 1 | 35.02 | 22.60 |

三次 SQL / Connect / Runs 主场景计数完全一致。时间用中位数；Developer SQL 减少 50（86.2%）、新连接减少 58（100% warm）、导航少 1 轮，Python 时间减少 2234.03 ms（93.7%）。Analysis 减少 1264.54 ms（91.0%）；规则整页减少 1218.91 ms（84.6%）。

### 逐项 benchmark

下表每格为 `SQL / 新连接 / runs / Python median ms`。

| 阶段 | Developer | Analysis | 本地规则 |
| --- | --- | --- | --- |
| main BEFORE | 58 / 58 / 2 / 2382.98 | 39 / 39 / 2 / 1389.93 | 36 / 36 / 1 / 1440.23 |
| FIX 1 + FIX 2 展示 view 与 Key version | 11 / 11 / 2 / 523.86 | 10 / 10 / 2 / 456.03 | 7 / 7 / 1 / 438.56 |
| FIX 3 有界 pool | 11 / 0 / 2 / 188.49 | 10 / 0 / 2 / 150.36 | 7 / 0 / 1 / 239.99 |
| FIX 4 单轮普通导航 | 8 / 0 / 1 / 150.20 | 7 / 0 / 1 / 118.09 | 7 / 0 / 1 / 规则路径不变 |
| FIX 5 同轮 restore 去重后复测 | 8 / 0 / 1 / 148.95 | 7 / 0 / 1 / 125.39 | 7 / 0 / 1 / 221.32 |

FIX 1 / 2 是同一展示 view 的代码路径，先单独验证 view 测试，再在 pool 实施前共同做页面基准。FIX 5 对稳定导航无结构性收益，稳定时间的小幅浮动不作该项收益证明；入口测试直接断言 restore 一次、同轮 refresh 零次、后续 rerun refresh 一次。F5 仍受 storage / installation hydration 影响：最终三次为 4 / 2 / 2 轮，SQL 7 / 4 / 4；不将启动握手计为普通导航，也不声称所有 F5 只运行一次。

### 三次 warm Python ms（原始样本）

| Scenario | BEFORE 三次 ms | AFTER 三次 ms |
| --- | --- | --- |
| Developer | 2145.96, 2382.98, 2439.05 | 145.81, 152.70, 148.95 |
| Analysis | 1604.34, 1342.09, 1389.93 | 125.39, 114.78, 133.80 |
| 本地规则 | 1475.30, 1440.23, 1192.57 | 204.64, 221.32, 230.89 |
| quota | 306.15, 245.57, 248.35 | 35.57, 33.70, 33.65 |
| membership | 247.64, 231.94, 286.95 | 33.87, 35.77, 35.90 |
| 游客登录 | 29.26, 37.93, 35.02 | 20.61, 28.33, 22.60 |

可审阅的[各阶段计数和样本](performance/20261004/benchmark-summary.json)、[最终动作与 SQL/checkout 时间](performance/20261004/final-warm-actions.json)、[浏览器安全结果](performance/20261004/security-browser.json)随报告保存。完整原始 trace、launcher、合成 seed、基准浏览器脚本和测试日志保留在实施机器 `D:/codex_study/_tmp/c2c-perf-20261003`，其中 `baseline-verified`、`display-verified`、`pool`、`navigation`、`restore` 为有效阶段；其它试跑不用于结论。原 trace 不记录 SQL 参数、token、密钥或 HTTP 业务载荷。

## 3. PostgreSQL pool 与依赖决策

`WHY_DEPENDENCY_NEEDED`：官方 pool 是与 psycopg 分开发布的包，提供有界借还、线程独占连接、故障检查、空闲收缩和后台恢复。它替代每操作连接；没有缓存裸连接或 transaction state。依据 [Psycopg 官方 pool 指南](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)及 [API](https://www.psycopg.org/psycopg3/docs/api/pool.html)，并核对安装的 3.3.3 源码与实际 PostgreSQL 回归。

`VERSION_BOUND`：部署锁定 `psycopg_pool==3.3.3`；项目依赖范围 `>=3.3.3,<3.4`，与现有 `psycopg[binary]>=3.3,<4` 兼容。不升级其它依赖。

`SECURITY/TLS_IMPACT`：生产 pool 显式覆盖 URL 的 TLS 参数为 `sslmode=verify-full`、`sslrootcert=certifi.where()`；低 TLS 配置仍拒绝。生产不可用时 fail-closed，无 SQLite fallback。后台 worker 原始错误可能带 DSN，logger filter 仅保留固定事件和 severity，不输出原始凭证。

pool 延迟初始化并受锁保护，`min_size=0`、默认 `max_size=4`、`max_waiting=16`、借连接 timeout 8 秒、connect timeout 8 秒、`max_idle=60` 秒、`max_lifetime=1800` 秒、reconnect timeout 8 秒、2 个后台 worker。每次 checkout 做官方健康检查；异常事务 rollback，未提交的手工 close 由 pool 清理，坏连接丢弃并替换。正常上下文成功仍 commit；各线程不共享租出的 transaction。显式 backend.close、GC / cache 替换及正常进程退出 finalizer 关闭资源。Streamlit 多会话共享缓存 backend 的池；多 worker / replica 各自持有池，部署时连接预算要按进程数计算。进程强制被杀依赖操作系统关闭 socket，不承诺优雅退出。

健康检查保留成本：最终 Developer 8 次 checkout / 8 次空查询检查；Analysis 和规则均 7 次；quota / membership 均 4 次。这些检查没有假装成零网络工作。池 worker 建连失败最终可能只体现为 acquisition NETWORK timeout，不能保证区分每一种 TLS / DNS 根因；安全策略与脱敏保持，诊断精细度为已知限制。

## 4. SECURITY REGRESSION

| 检查 | 状态 | 证据和范围 |
| --- | --- | --- |
| SESSION_REVOCATION | PASS | 下一脚本入口检查 revoke；刚 restore 后下一轮照常刷新；旧 Key 保存回调复核 token 后拒绝写入 |
| LOGOUT | PASS | 当前标签退出立即清理页面与 Provider 输入；双标签下一操作拒绝，F5 不恢复已撤销身份 |
| ACCOUNT_ISOLATION | PASS | view 的完整 Principal 绑定 / 生命周期拒绝；A 十家配置对 B 不可见 |
| BYOK_DISABLE | PASS | 旧展示 view 不能授权 Key 读写、client、目录请求；浏览器关开切换通过 |
| KEY_ROTATION | PASS | 合成 Key 更新 / 删除使新 view 的 version cache key 改变，旧目录不能命中；未删除 version invalidation |
| DEEP_LINK | PASS | Guest / 登录后指定 analysis 深链、F5、新标签；无效 token 清理 |
| A_GUEST_B | PASS | A 的 JD 和未保存 Provider 模型输入在 Guest / B 均为空或默认，不复用 |

真实本地 Chromium 7 组检查全部 PASS，普通 6 页 × 3 次导航分别断言一个 script start / finish，且旧首页 / JD 表单不残留。原浏览器存储没有 storage-event 推送：另一个静止标签可暂时保留上次画面，但没有授权继续执行；下一次操作进行 server-side 复核。这里不声称静止标签即时擦除。TLS 策略 PASS 是配置 / mock 边界验证，真实远程 TLS 与生产多会话压力为 UNVERIFIED。

## 5. TESTS

所有 Python 命令使用项目已有 Python 3.12 venv、UTF-8，新增 pool 仅安装至 D 盘临时依赖目录，通过 PYTHONPATH 使用；测试数据库均是本轮新建的 localhost 合成 DB。

| 命令 / 检查 | 结果 |
| --- | --- |
| `python -m pytest -p no:cacheprovider --basetemp <D:/临时目录>`（设置 C08_TEST_DATABASE_URL） | 330 passed, 1 skipped, 66.66 s；唯一跳过为 restore DB 尚未设置，已在下一项补跑 |
| `python -m pytest -m postgres -q -p no:cacheprovider --basetemp <D:/临时目录>` | 13 passed（含复用、异常回滚、未提交归还、坏 socket 替换、并发事务隔离、池耗尽、有界等待、关闭） |
| `pg_dump -Fc` → `createdb` → `pg_restore --exit-on-error` | PASS，隔离合成 source → 独立 restore DB |
| `python -m pytest -m postgres_restore -q -p no:cacheprovider --basetemp <D:/临时目录>`（另设 C08_TEST_RESTORE_DATABASE_URL） | PASS；恢复账号、Key 解密、profile、分析历史等既有 CI 门禁 |
| `python -m ruff check .` | PASS |
| `python -m ruff format --check .` | PASS |
| `git diff --check` / 提交前 `git diff --cached --check` | PASS |
| `node scripts/verify_performance_browser.cjs` | 7 groups PASS，18 次普通导航均一轮 |

新增 display view 与版本隔离测试；增强 session restore、身份清理、Key 回调和 TLS 单测。没有真实 AI / 远程模型目录调用。远程 Python 3.11 / 3.12 / 3.14 与 PostgreSQL 17 CI 结果以 Draft PR 当前 checks 为准，不把本机 3.12 当作其它版本已通过。

浏览器脚本只允许 localhost，阻止非本地主机请求，不点击连接测试或 AI。运行需要本地 Playwright / Chromium 和合成账号 `audit_byok` / `audit_user`（密码为脚本中的固定合成测试值）；可设 `C2C_PLAYWRIGHT_MODULE`、`C2C_CHROMIUM`、`C2C_BASE_URL`、`C2C_BROWSER_REPORT`。不要指向生产服务。

## 6. CHANGED FILES

| 文件 | 修改理由 |
| --- | --- |
| `app.py` | route / identity container、正常导航单轮、同轮 restore 去重 |
| `src/course2career/provider_display.py` | 无 Secret 的 render scope view、owner / 生命周期检查 |
| `src/course2career/model_discovery.py` | peek / selected_model 纯展示复用 metadata version，不改远程协议 |
| `src/course2career/ui/developer_page.py` | Provider cards 复用 view；保存回调复核当前会话 |
| `src/course2career/ui/analysis_page.py` | Provider controls 复用同轮 view |
| `src/course2career/ui/byok_mode_controls.py` | 只复用展示 enabled 状态，写操作原检查保留 |
| `src/course2career/ui/identity_state.py` | 切换账号清除 Provider 表单、偏好和反馈状态 |
| `src/course2career/database_backend.py` | 有界 pool、健康检查、借还事务、TLS 和日志脱敏 |
| `requirements.txt` | 部署 pin 唯一新增 pool 依赖 |
| `pyproject.toml` | 包依赖范围保持 pool 3.3 系列 |
| `tests/test_provider_display.py` | view 不跨账号 / 不跨 render、版本轮换、敏感动作拒绝旧状态 |
| `tests/test_postgres_pool.py` | 实际 PG 生命周期、回滚、坏连接、耗尽和并发回归 |
| `tests/test_auth_restore_state.py` | 普通导航入口和 restore / refresh / revoke / 角色状态检查 |
| `tests/test_post_release_fixes.py` | 账户切换清理 Provider 输入 |
| `tests/test_c08_d1.py` | 原 TLS / 错误测试适配 pool factory，断言不弱化 |
| `tests/test_app.py` | 保存表单使用真实合成 session，核对写入成功 |
| `tests/test_c08_b1.py` | Key 增改删表单 fixture 具有有效合成 session |
| `scripts/verify_performance_browser.cjs` | 本地浏览器导航与安全验收，可重复执行 |
| `README.md` | 区分本性能候选与既有生产发布证据 |
| `docs/requirements.md` | 性能验收和安全条件 |
| `docs/architecture.md` | 当前 view、pool、导航与 restore 语义 |
| `docs/c08-model-discovery.md` | 展示 lookup 与真实目录刷新边界 |
| `docs/c08-production-persistence.md` | PG pool / session 生命周期与失效行为 |
| `docs/deployment.md` | 新依赖、池预算和生产未验收边界 |
| `docs/user-guide.md` | 普通导航、身份清理、双标签可见边界 |
| `docs/ui-design.md` | 页面内容与隔离保持一致，链接合成截图 |
| `docs/evaluation.md` | 本候选测试 / benchmark / 生产未知状态 |
| `docs/development-log.md` | 按实施顺序保留性能证据 |
| `docs/performance-fix-20261004.md` | 本实施报告与复现条件 |
| `docs/performance/20261004/*.json` | 三份脱敏数值与安全验收证据 |
| `screenshots/performance-provider-synthetic-20261004.png` | 合成账号最终 Provider 页，不代表 Provider 认证或生产截图 |

示例、页面文案与评分逻辑未改变；现有三例本地规则演示参与 benchmark。检查 screenshot / 页面隔离，不需要改评分文档或 schema。未改 Provider model ID、协议、兼容策略、API Key 内容、真实认证逻辑、pricing、System AI quota。

## 7. RESIDUAL BOTTLENECKS / PR

最终 trace 中 Developer 每轮 8 次读取：session / user 各 1、BYOK settings 4、Key metadata 1、profile 1。仍保留静态目录原有安全门禁，不为省两次检查改变 refresh / authorization 语义。Analysis / 规则为 7 次：session / user 各 1、BYOK 2、metadata / profiles / history 各 1。

实测 Developer checkout（包含健康检查）约 7.2–9.6 ms，SQL 3.6–4.1 ms；Analysis checkout 5.2–14.7 ms、SQL 2.7–7.6 ms；规则 checkout 6.2–7.2 ms、SQL 3.0–9.2 ms。连接建立已非 warm 主因。规则整页仍约 221 ms，剩余主要是规则结果 / 导出准备、Streamlit UI 及 instrumentation 文件 I/O；这里未单独精确拆分所有 CPU 子项，不再沿用“89% 是 connect”的旧结论。未扩展到 UI 重写、规则算法、capability、service 构造或 settings 缓存。

BRANCH = `perf/reduce-rerun-database-overhead`；BASE = `62336cc9ea8541d670b054dc936a59d2d275773b`。HEAD / Draft PR / CI 由本轮最终交付和 PR checks 提供，报告不写自引用 commit SHA。

`RELEASE_READY = no`。公开匿名线上性能复测为可选 baseline，本实施轮未重跑；未部署的分支不可能提供 production AFTER。生产远程 DB RTT、真实 TLS、Cloud pool 空闲 / 冷启动、多用户高并发、真实 Provider 请求均 UNVERIFIED，需单独授权 merge / deploy 后验收。
