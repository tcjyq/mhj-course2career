# Course2Career

> 面向大学生的可解释岗位适配度评估助手

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.60-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-243F37)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live_Demo-Open_App-C65D3B?logo=streamlit&logoColor=white)](https://mhj-course2career.streamlit.app)

Course2Career 面向准备实习和校招的大学生，将课程、教育背景、项目、实习及成长条件与目标岗位 JD 转换为可解释的岗位适配度、硬门槛检查、能力差距和学习路线。项目采用“AI 提取语义、Python 规则负责评估、用户确认关键输入”的设计，不预测录用概率。

**Showcase：** [https://course2career.tcjyq.cc](https://course2career.tcjyq.cc)<br />
**Live Demo：** [https://mhj-course2career.streamlit.app](https://mhj-course2career.streamlit.app)

招聘展示先访问稳定 Showcase；Streamlit Live Demo 支持游客以“本地规则”完成完整核心流程，无需注册或平台 AI Key。平台未配置模型凭证时，应用不会显示“系统AI”选项。

![Course2Career 首页](screenshots/home.png)

## 90 秒了解与体验

这是一个 AI 辅助提取、人工确认、确定性规则和能力证据共同支持的学习决策原型。
要解决的问题是：课程和经历能支持岗位里的哪些要求，还缺什么材料，以及下一步交付什么。

1. 按下方快速开始运行，进入“个人分析”，展开“三个求职方向合成演示”。
2. 选择数字化实施／信息化支持、AI应用／解决方案或数据分析，查看输入后运行规则演示。
3. 对照硬门槛、资料完整度、材料来源和学习任务，下载输入包及报告；可独立重新开始。
4. 使用自己的资料时：上传课程 → 填写经历与门槛 → 提取 JD → 人工核对引用和技能 → 规则评分 → 导出。

三例均为**合成演示，不代表真实岗位或候选人**，分别展示材料不足、基础相关需补证据、技能较好但门槛不满足。无需登录或真实模型调用。演示区不覆盖正在填写的资料。

AI 只提取 JD 技能；原文引用核对、映射、评分、门槛与学习任务由 Python 完成。
直接材料不等于熟练掌握，自述及人工确认不等于外部验证；当前业务效果尚未通过真实用户或人工标注校准。

证据入口：[优化复核与验证](docs/optimization-review.md) · [能力与面试讲述](docs/candidate-evidence.md) · [合成输入](data/demo_cases/cases.json) · [回归测试](tests/test_optimization.py)。本次优化为本地结果，线上状态以部署版本为准。

## 核心能力

- 下载并上传课程 Excel 模板，提供字段、范围和重复值校验。
- 通过本地规则、已配置的系统 OpenAI/DeepSeek，或已启用开发者模式的登录用户及历史 Developer/Admin 自带 Key 的官方 Provider 预设提取岗位技能。
- DeepSeek 支持 Auto-Safe 模型发现：只在官方当前可用且列入历史兼容白名单的模型中自动选择，并在模型下线时执行一次受控回退；白名单不等于 C08-B2 当前真实验证状态。
- 规范化技能并允许用户在分析前人工确认。
- 采集教育、项目、实习、成长潜力和到岗条件，并区分“未填写”与“目前没有”。
- 通过课程、项目、实习和相邻技能迁移计算单项技能支撑分。
- 使用 Career Adaptability Model v2.1 计算技术、教育、项目、实习和潜力五维岗位适配度。
- 将学历、专业、毕业年份、到岗时间和城市等硬门槛独立展示；学历同时参与教育维度，门槛状态不作为总分乘数。
- 输出从 50 分基线展开的逐项加减分账本，能够解释“为什么是这个分数”。
- 输出优势、能力缺口、按实际缺口生成至多 8 项学习任务（无缺口不凑数量）及 Markdown/CSV 报告。
- 支持游客、普通用户、开发者和管理员权限。
- 支持 AI 日额度、历史分析记录和轻量管理员 Dashboard。
- 开发者 API Key 使用 AES-256-GCM 加密后保存。
- C08-B1 在本地分支提供十家受控官方预设，按四类协议适配；免费套餐系统 AI 仍固定 DeepSeek。[设计与边界](docs/c08-multi-provider-design.md) · [开源架构研究](docs/c08-open-source-research.md)。
- C08-B3 在本地分支允许普通登录用户免费启用开发者模式并管理自己的加密 API Key。启用或关闭不改变 Free/Pro 套餐及系统 AI 日额度；关闭后停止新的 BYOK 使用，已保存的 Key 保留，可重新开启。历史 Developer/Admin 权限继续可用。会员页的 Free/Pro 升级仍只是演示，线上状态以部署版本为准。
- C08-B2 增加模型级真实验证记录、固定合成 JD 套件及原生 schema adapter。2026-09-26 本机百炼 `cn-beijing` / `qwen3.8-flash` 达到 `SCHEMA_COMPATIBLE`，但仅通过 1/4 个固定样例，尚未 VERIFIED；OpenAI 与 Anthropic 的既有请求均为 401。后续显式运行验证脚本会将逐题技能缺失、误提和证据原文问题写入 gitignored 脱敏诊断文件，不记录 JD 或原始响应。连接成功、Schema 兼容、完整验证在页面中分开显示；失败不会删除 Key。[真实验证报告](docs/c08-provider-validation.md)。
- C08-C 在本地分支提供大陆六家优先、国际四家可选的官方模型目录：DeepSeek、百炼、SiliconFlow、MiniMax 等动态发现，Kimi/GLM 有日期的官方静态候选；能力、价格来源和 B2 真实验证分开展示。缓存按用户、端点、Workspace 和 Key 版本隔离，刷新失败保留过期目录；关闭开发者模式即禁止读取和刷新。当前仍无 VERIFIED；目录价格不等于实际账单。`deepseek-v4-flash` 作为兼容旧名提示，用户 Profile 不会自动迁移。[目录说明](docs/c08-model-discovery.md) · [官方来源矩阵](docs/c08-provider-matrix.md)。C08-D 才讨论自定义端点。
- 开发者 API Key 提交后立即清空输入框与对应会话状态，页面只保留末四位元数据。
- 页面切换采用隔离渲染，避免首页或上一页内容残留到当前页面。

## 工作流程

```text
课程 Excel ───────────┐
教育/项目/实习/潜力 ──┼─→ 证据建模 ───────────────┐
岗位 JD ─→ 技能提取 ─→ 人工确认 ─→ 技能映射与迁移 ├─→ 五维适配度
岗位硬性要求 ──────────────────────────────────────┘       ↓
                                  报告导出 ← 能力路线 ← 可解释账本
```

AI 只参与岗位技能提取。证据映射、迁移、硬门槛、五维评分和学习路线由确定性 Python 逻辑完成，便于测试、解释和复现。

## 技术栈

- Python 3.11+
- Streamlit
- pandas / openpyxl
- Pydantic
- OpenAI Python SDK
- SQLite
- cryptography
- pytest / Ruff

## 招聘展示部署

招聘展示采用三层结构：

1. [Course2Career Showcase](https://course2career.tcjyq.cc)：Cloudflare 静态资产 Worker，首屏不依赖 Python、Streamlit、数据库或 API Key；
2. [Streamlit Live Demo](https://mhj-course2career.streamlit.app)：可运行的游客本地规则体验。Community Cloud 长时间无访问后可能休眠，首次访问按平台提示唤醒即可；
3. [GitHub 源码](https://github.com/tcjyq/mhj-course2career)：实现、测试和文档证据。

Showcase 源码位于 [`showcase/`](showcase/)，只复用仓库的真实截图 `screenshots/home.png`。发布命令与域名绑定说明见 [`docs/deployment.md`](docs/deployment.md)。

## 快速开始

```powershell
git clone https://github.com/tcjyq/mhj-course2career.git
cd mhj-course2career
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

默认可直接使用本地规则模式，不需要模型凭证。

如需启用 AI 或开发者 API Key 模式：

```powershell
Copy-Item .env.example .env
```

随后只在本机 `.env` 中填写所需配置。不要提交 `.env`、数据库或真实密钥。

| 环境变量 | 用途 | 是否必需 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 平台 OpenAI 调用 | 仅 OpenAI 系统模式 |
| `OPENAI_MODEL` | OpenAI 模型名称 | 否 |
| `DEEPSEEK_API_KEY` | 平台 DeepSeek 调用 | 仅 DeepSeek 系统模式 |
| `DEEPSEEK_MODEL` | DeepSeek 模型名称 | 否 |
| `BAILIAN_REGION` | 百炼受控端点区域（北京/新加坡/美国/香港）；开发者页面可单独选择 | 否 |
| `BAILIAN_BASE_URL` | 可覆盖为注册表列出的官方百炼区域端点；拒绝任意 URL | 否 |
| `BAILIAN_INPUT_COST_PER_MILLION` / `BAILIAN_OUTPUT_COST_PER_MILLION` | 百炼估算费率，默认 0 表示未配置 | 否 |
| `OPENROUTER_INPUT_COST_PER_MILLION` / `OPENROUTER_OUTPUT_COST_PER_MILLION` | OpenRouter 估算费率，默认 0 表示未配置 | 否 |
| `DEEPSEEK_MODEL_MODE` | `auto_safe` 自动安全选择或 `pinned` 固定模型 | 否 |
| `DEEPSEEK_MODEL_PREFERENCE` | 历史兼容白名单内模型的优先顺序；不代表 B2 实测状态 | 否 |
| `DEEPSEEK_MODEL_CACHE_SECONDS` | 官方模型目录缓存时间 | 否 |
| `DEEPSEEK_MODEL_STALE_SECONDS` | 目录故障时允许使用旧缓存的时间 | 否 |
| `DEEPSEEK_MAX_OUTPUT_TOKENS` | DeepSeek 单次最大输出 Token | 否 |
| `SYSTEM_AI_ENABLED` | 平台 AI 紧急总开关 | 否 |
| `COURSE2CAREER_DATABASE_PATH` | SQLite 数据库路径 | 否 |
| `COURSE2CAREER_KEY_ENCRYPTION_KEY` | 加密开发者 API Key | 开发者模式 |

生成本地加密主密钥：

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

## 开发验证

```powershell
python -m pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

测试使用模拟模型响应，不访问真实网络，也不会产生 API 费用。

## 项目结构

```text
course2career/
├── .github/workflows/       # GitHub Actions
├── .streamlit/              # Streamlit 主题配置
├── data/                    # 技能别名、课程映射、学习资源
├── docs/                    # 架构、需求、评分、部署与开发文档
├── examples/                # 脱敏示例 JD
├── prompts/                 # LLM 提示词
├── screenshots/             # README 展示截图
├── src/course2career/       # 业务、数据访问与 UI 模块
├── tests/                   # 单元、集成和 Streamlit UI 测试
├── app.py                   # Streamlit 入口
├── pyproject.toml           # Python 项目配置
├── requirements.txt         # 固定版本的运行依赖
└── requirements-dev.txt     # 测试与代码质量依赖
```

## 设计文档

- [普通用户使用说明](docs/user-guide.md)
- [系统架构](docs/architecture.md)
- [MVP 需求](docs/requirements.md)
- [评分设计](docs/scoring.md)
- [Career Adaptability Model v2.1 决策记录](docs/decisions/001-career-adaptability-model-v2-1.md)
- [DeepSeek 模型发现与安全升级决策](docs/decisions/002-deepseek-model-discovery-and-safe-upgrade.md)
- [AI 评测方案](docs/evaluation.md)
- [权限设计](docs/access-control.md)
- [会员体系](docs/membership.md)
- [管理员 Dashboard](docs/admin-dashboard.md)
- [界面设计](docs/ui-design.md)
- [部署说明](docs/deployment.md)
- [开发规范](docs/development-guide.md)
- [开发日志](docs/development-log.md)

## 数据与安全

- `.env`、SQLite 数据库、日志、缓存和私钥文件均被 Git 忽略。
- 平台 API Key 和加密主密钥只从环境变量读取。
- 开发者 API Key 加密存储，页面和列表只显示末四位。
- AI 模式会把岗位 JD 发送给所选模型供应商，请勿输入个人隐私或招聘方机密。
- 课程信息不会作为模型 Prompt 发送。
- 官方新增模型只会触发待验证提醒，不会绕过兼容性测试直接接管线上调用。
- Streamlit Cloud 热更新期间若短暂保留旧仓储实例，调用结果仍会优先回写状态、Token 与费用，避免模型已计费但页面因接口版本差异中断。

公网部署前请先阅读 [部署说明](docs/deployment.md) 和 [安全策略](SECURITY.md)。
管理员初始化配置仅记录在部署说明中，README 不提供任何管理员凭证。

## 项目边界

- 岗位适配度用于比较当前证据与岗位要求，不代表招聘录用概率或个人能力认证。
- 院校和学历作为现实招聘筛选信号参与解释，但不代表个人能力上限。
- 院校分类不对海外教育质量作统一推断；无法可靠判断时使用中性分并说明判断限制。
- 未填写的信息使用中性值，不按零分处理，但会降低数据完整度和资料完整度等级。
- 课程、项目和实习均依赖用户提供的信息，无法替代招聘方核验和实际面试。
- 当前版本使用 SQLite，适合本地和单实例演示。
- 会员页面为权限模型演示，不接入真实支付。

## 参与贡献

贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按照 [SECURITY.md](SECURITY.md) 私密报告。

## 历史报告恢复

登录用户完成分析后，报告会以账号归属的快照保存。刷新、重新登录或再次进入“个人分析”后，可在“最近分析”中选择并重新打开历史报告。相同时间、岗位和分数的记录仍会按唯一报告 ID 分别保留。v2.1 上线前生成的报告会以“旧版技能匹配报告”原样展示，不会伪装成五维岗位适配度。课程 Excel、完整 JD 与表单编辑内容不会被自动回填，以减少长期保存的个人和招聘数据。

当前线上演示仍使用 SQLite。Streamlit Community Cloud 的临时磁盘不保证长期保存 SQLite 文件；C08-D0 分支已加入 PostgreSQL 生产路径，但尚未部署。正式 BYOK 上线必须配置持久数据库和长期加密主密钥，完成 PostgreSQL CI、独立远程库与备份恢复演练，以及大陆 Provider 真实验证。见 [持久化说明](docs/c08-production-persistence.md)和[备份恢复操作说明](docs/c08-backup-restore-runbook.md)。

## License

本项目采用 [MIT License](LICENSE)。
