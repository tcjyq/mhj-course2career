# 2026-09-21 优化复核与交付

复核起点：`main` / `04f1b32834a668813df30418cce414617c8952b7`。工作区原有两个未跟踪文件：任务规范与 `course2career_full_history.md`，均保留。没有提交、推送或发布。

## 修改前现状

| ID | 当前文件／函数 | 复现输入 | 实际结果 | 应有结果／最小方案 | 问题仍存在 |
| --- | --- | --- | --- | --- | --- |
| C01 | course_skill_map.json / map_courses_to_skills | 每门课程单独输入，学分3、成绩88、自评4 | Java/C/通用编程均产生 Python 83.9、pandas 76.9；Python也产生pandas；通用可视化及Power BI均产生两个BI产品 | 拆分具体工具词典，保留通用能力及其他真实来源 | 是 |
| C03 | analysis_page / exporter / _check_eligibility | 空门槛；未填经历 | 空checks但显示满足；完整度标签称结果可信度；None与空列表已有区别 | 共用展示函数；保留后端枚举及分数，准确命名完整度 | 前两项是，未知/没有已满足 |
| C02 | _build_technical_matches / _score_technical | 课程、项目、迁移、多来源、无来源 | sources只进账本且截断至3，技能表仅课程；自述未标明 | 复用sources、保留全部来源，增加可选快照字段及一致导出 | 是 |
| C04 | jd_analyzer / provider / 技能编辑表 | 固定模型返回JD中不存在的非空引用 | 仅结构校验，非空引用通过；已有人工编辑 | 在确认界面严格核对引用与技能别名；修正后重新核对，不增加模型调用 | 是；人工确认已满足 |
| C05 | analysis_page / course_parser | 游客本地规则 | 已有Excel下载上传与完整流程，无三方向预设 | 独立合成演示区域，复用规则、报告和导出，不回填用户输入 | 是 |
| C06 | adaptability._build_learning_modules | SQL缺口 | 泛化为完成项目模块并补测试，缺少任务和验收口径 | 当前主路径按缺口使用少量确定性模板，旧路径保留 | 是 |
| C07 | README / evaluation / showcase | 阅读入口及测试 | 占位clone命令；历史120项；人工评测是计划 | 补90秒入口、证据映射、真实验证及待审阅边界 | 是 |

首次基线测试受到系统临时目录 `pytest-of-ma041` 访问权限影响，44项在setup阶段报错；随后使用D盘独立临时目录验证，不更改业务断言或用户目录权限。

## C01—C07最终状态

| ID | 状态 | 本次交付与证据 |
| --- | --- | --- |
| C01 | 本次完成 | 拆开Python/pandas/BI工具规则，去除泛化课程到具体工具的推断；ASCII关键词增加词边界，JavaScript不误命中Java。[课程对照回归](../tests/test_optimization.py) |
| C02 | 本次完成 | 复用已有sources，保留全部来源（计分仍只使用最强三条）；区分直接名称、课程推断、迁移、自述与未体现。界面支持逐项阅读、Markdown保存完整来源；CSV保留原五列。旧快照不补造类型。[展示函数](../src/course2career/evidence_display.py) |
| C03 | 本次完成；部分能力原已满足 | 界面和Markdown以checks是否为空显示未设置／待确认；完整度及其等级准确命名。后端枚举、None和空列表语义、学历教育维度与门槛规则保持兼容。[评分回归](../tests/test_adaptability_scoring.py) |
| C04 | 本次完成；人工编辑原已满足 | 确认表逐字／连续空白折叠核对当前JD，单独标注技能推断；编辑后生成重新检查。无法定位仍可依原有人工勾选契约保留，报告限制保留待确认结论；空引用按原契约拒绝，需修正。固定响应测试不增加模型调用。[引用核对](../src/course2career/jd_analyzer.py) |
| C05 | 本次完成 | 三方向合成JSON、下载ZIP、合法Excel、独立运行／重置、报告与导出；未覆盖草稿和个人报告。游客规则演示与真实输入共用引擎。[案例输入](../data/demo_cases/cases.json)、[界面隔离测试](../tests/test_app.py) |
| C06 | 本次完成 | 当前主路径按真实低于50分的缺口生成至多8项任务，重要程度、低分、名称决定优先级；每项含交付和验收。未知技能使用通用练习，无缺口不凑数，旧路径未改。[主路径](../src/course2career/adaptability.py) |
| C07 | 本次完成 | 补业务对照回归、README 90秒入口、修复clone命令、同步专题文档及Showcase文案；能力／证据／讲述／局限、P2方法见[求职证据导航](candidate-evidence.md)。不声明实测业务准确率或本人未确认的贡献。 |

## 关键输入修改前后

课程输入均为单门课程，学分3、成绩88、自评4；表中为课程规则证据分，不代表熟练度。

| 输入 | 修改前 | 修改后 |
| --- | --- | --- |
| Java程序设计 | Java 83.9、Python 83.9、pandas 76.9 | Java 83.9 |
| C语言程序设计 | Python 83.9、pandas 76.9 | 无匹配，证据不足 |
| Python程序设计 | Python 83.9、pandas 76.9 | Python 83.9；pandas需要独立依据 |
| 通用编程 | Python 83.9、pandas 76.9 | 无匹配，证据不足 |
| 数据可视化 | 数据可视化83.9、Power BI 78.7、Tableau 78.7 | 仅数据可视化83.9 |
| Power BI课程 | 数据可视化83.9、Power BI 78.7、Tableau 78.7 | 数据可视化83.9、Power BI 78.7 |
| 数据库原理 | SQL 83.9、数据库设计82.1、数据建模75.2 | 分数不变，SQL属于课程规则间接推断，区别于名称明确提及 |
| 无门槛checks | 界面显示满足 | 未设置／待确认；存储枚举仍兼容PASS |
| 虚构非空引用 | 契约通过，界面无原文检查 | 无法定位，待确认；人工可修正或排除 |
| 项目／实习未填 vs 明确没有 | 已区分None和[] | 保持；资料100%完整不等于经历丰富 |

同一套当前课程规则分别运行HEAD版与本次版适配度引擎，三例总分及全部五维分一致（来源展示无评分漂移）。五维权重、迁移强度、技能阈值、15分基础、100分上限和解释账本舍入容差0.11不变。课程误映射修正会改变相关输入的分数，不保证任意历史输入保持原分数。

| 合成方向 | 总分（修改前→后） | 本次技术维度 | 完整度 | 关键解释 |
| --- | --- | --- | --- | --- |
| 实施／信息化支持 | 41.2→41.2 | 15.0 | 25% | 材料不足，门槛待确认 |
| AI应用／解决方案 | 39.8→39.8 | 44.9 | 90% | 相关基础、缺API／结构化输出证据、门槛未设置 |
| 数据分析 | 50.3→50.3 | 86.8 | 90% | 技术有支撑但毕业年份门槛失败；明确没有项目和实习 |

三例不以高分为目的，恰好未依赖被移除的错误映射；错误修复本身由上表单课程对照覆盖。

## 实际变更文件与理由

- `data/course_skill_map.json`、`course_skill_mapper.py`：消除具体工具误推断和ASCII子串误命中；`data/skill_transfer_rules.json`仅将两条“直接支撑／证明”说明改为“相关基础”，不改迁移强度。
- `models.py`：为SkillMatch增加可选sources，为LearningModule增加可选task与completion_criteria；无生产迁移。
- `adaptability.py`：完整来源及自述说明、别名来源查找兼容、确定性任务；保留评分公式。
- `evidence_display.py`、`jd_analyzer.py`：共用门槛／来源文案和严格引用核对。
- `ui/analysis_page.py`、`ui/candidate_profile_form.py`：完整度、核对提示、可读来源、演示及共用报告渲染；重提取时重置旧技能编辑状态。
- `report_exporter.py`：Markdown与界面语义一致，旧CSV契约和旧报告可读。
- `demo_cases.py`、`data/demo_cases/cases.json`：可复现的三方向合成输入与ZIP下载。
- `tests/test_optimization.py`、`tests/test_app.py`：课程、引用、别名、来源、历史字段、空门槛、完整但无经历、任务、下载和会话隔离回归；原上传预览断言改为定位课程表，避免新增演示表改变索引。
- README、需求、架构、评分、评估、用户指南、UI设计、开发日志、求职证据导航及本记录：同步语义、验证、边界和使用步骤。
- `showcase/public/index.html`：保留现有视觉与入口，修正学历说明，移除把历史测试数当当前状态的醒目标题，说明线上取决于部署版本。
- `screenshots/optimization-20260921/`、截图索引：真实浏览器合成场景截图；首页截图保持原文件。

## 验证环境、命令与结果

2026-09-21，北京时间。Windows / PowerShell，项目既有 `.venv`：Python 3.12.14、Streamlit 1.60.0、pandas 3.0.3、Pydantic 2.13.4、openpyxl 3.1.5、OpenAI SDK 2.46.0、pytest 9.1.1、Ruff 0.15.22。未升级项目依赖。

```powershell
.venv/Scripts/python.exe -m pytest -o addopts='' -q -o cache_dir=D:/codex_study/_tmp/c2c-opt-cache --basetemp=D:/codex_study/_tmp/c2c-opt-verified --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
git diff --check
# 最后格式与说明措辞调整后的相关回归
.venv/Scripts/python.exe -m pytest -o addopts='' -q tests/test_optimization.py tests/test_adaptability_scoring.py tests/test_app.py -o cache_dir=D:/codex_study/_tmp/c2c-opt-cache --basetemp=D:/codex_study/_tmp/c2c-opt-final-text --tb=short
```

- 全量pytest：**150 passed，0 failed，0 skipped，25.56秒**。首次默认临时目录失败及D盘重跑如前述，未跳过业务测试。
- Ruff check：通过。全量测试后进行格式化及两条迁移说明措辞调整，相关54项回归再次通过（7.02秒）；format check：65 files already formatted。
- git diff --check：通过。Git另提示部分文本文件下次checkout会按现有配置转为CRLF，不是差异错误。
- 固定provider、空引用、引用别名与人工修正、provider异常处理使用本地测试；未调用付费API、未发送真实JD。
- UI：Chrome（Playwright CLI 0.1.21，工具缓存位于D盘，未加入项目依赖）；真实Streamlit localhost，桌面1440×1000、窄屏390×844，三例可运行并读取解释；桌面长门槛metric会省略，紧邻完整文案保证可读；窄屏提供逐项来源文本，表格可横向滚动，页面整体宽度390。
- 输入ZIP实际下载并重新读入Excel通过；AI案例Markdown和数据分析CSV实际浏览器下载内容与后端导出逐字节一致；旧版历史Markdown下载保留72分原值。
- 历史报告：使用隔离D盘数据库和既有AppTest合成夹具，旧版与v2.1都通过“重新打开这份报告”恢复；桌面、窄屏均无应用异常，旧快照来源不补造；未使用真实账户。
- 浏览器控制台：从首页导航的三例初轮及独立历史夹具均0 errors / 0 warnings。稍后直接访问`/analysis`时观察到`/analysis/_stcore/health`和`host-config`两次404探测，页面随后恢复；记录为Streamlit深链启动现象，未扩大修改为路由重构，不能称所有访问方式均零错误。
- 现行文档旧术语、占位clone、测试数与相对证据链接已检查；历史日期下的120项记录与ADR保留，不作为本次事实。

没有运行Python3.11本地矩阵、远端CI、真实模型质量评测、真实目标用户任务测试或生产部署。代码／契约通过不等于业务效果已校准，也不等于用户验收或已上线。

## 使用与后续范围

本地启动 `streamlit run app.py`，进入个人分析，展开“三个求职方向合成演示”，选方向并点击运行；下载输入ZIP后也可按README.txt手动走上传—资料—JD—规则提取—人工确认—报告流程。重新开始只清除演示结果，已有个人草稿及报告由隔离回归覆盖。

能力映射、面试讲述、简历和作品集建议段落、作者贡献边界及P2采集方法均在 [candidate-evidence.md](candidate-evidence.md)。尚需本人确认历史贡献；如需提交、推送或发布，需针对该操作另行授权。本次没有修改简历PDF或其他项目，没有自动发布。

## Release Candidate Verification

验证日期：2026-09-21（北京时间）。本节记录后续发布候选复核，前文实施阶段的验证结果和当时“未提交”状态保留为历史事实。

### 冻结范围与版本

- 分支：`main`。本地起始HEAD、本地`origin/main`以及GitHub只读查询／`git ls-remote`核验的远端main均为`04f1b32834a668813df30418cce414617c8952b7`。
- 本地候选标识：`C01-C07-RC-20260921`，仅为文档标识，不是Git tag。本节所属独立本地提交为候选版本，提交信息为`feat: strengthen evidence boundaries and career analysis workflow`；最终SHA以该提交和交付报告为准。
- 初始暂存区为空；20个已跟踪文件修改、18个新增项目文件，另有2个未跟踪用户资料。完整差异审阅未发现C08／C09或其他意外功能修改。
- `Course2Career_Codex_Optimization_Spec.md`和`course2career_full_history.md`原位保留、不暂存，提交前以SHA-256核对未改变。
- C01—C07均完成本地复核。此次冻结阶段仅修正README、评估、UI设计和用户指南中4处说明偏差：海外院校的中性分不自动降低资料完整度；主观自评不自动降低完整度；当前学习路线按低分缺口生成任务，不是合并模块。未改核心代码、评分权重、CSV五列或历史读取协议。

本次候选完整文件清单（38个，其中12个PNG为公开合成场景截图）：

```text
README.md
data/course_skill_map.json
data/demo_cases/cases.json
data/skill_transfer_rules.json
docs/architecture.md
docs/candidate-evidence.md
docs/development-log.md
docs/evaluation.md
docs/optimization-review.md
docs/requirements.md
docs/scoring.md
docs/ui-design.md
docs/user-guide.md
screenshots/README.md
screenshots/optimization-20260921/ai-desktop.png
screenshots/optimization-20260921/ai-mobile.png
screenshots/optimization-20260921/data-desktop.png
screenshots/optimization-20260921/data-mobile.png
screenshots/optimization-20260921/digital-desktop.png
screenshots/optimization-20260921/digital-mobile.png
screenshots/optimization-20260921/history-v21-desktop.png
screenshots/optimization-20260921/history-v21-mobile.png
screenshots/optimization-20260921/legacy-desktop.png
screenshots/optimization-20260921/legacy-mobile.png
screenshots/optimization-20260921/sources-desktop.png
screenshots/optimization-20260921/sources-mobile.png
showcase/public/index.html
src/course2career/adaptability.py
src/course2career/course_skill_mapper.py
src/course2career/demo_cases.py
src/course2career/evidence_display.py
src/course2career/jd_analyzer.py
src/course2career/models.py
src/course2career/report_exporter.py
src/course2career/ui/analysis_page.py
src/course2career/ui/candidate_profile_form.py
tests/test_app.py
tests/test_optimization.py
```

### 自动验证与安全检查

使用既有Python 3.12.14虚拟环境，未安装或升级依赖。重新执行以下全量命令：

```powershell
.venv/Scripts/python.exe -m pytest -o addopts='' -q -o cache_dir=D:/codex_study/_tmp/c2c-release-cache --basetemp=D:/codex_study/_tmp/c2c-release-basetemp --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
git diff --check
node --check showcase/src/worker.js
```

- pytest：**150 passed，0 failed，0 skipped，24.63秒**；本轮直接使用D盘隔离临时目录，没有调整权限、跳过测试或放宽断言。
- Ruff：通过；format：65 files already formatted；diff空白检查及Showcase Worker语法检查通过。CRLF转换提示属于现有Git配置，不是失败。
- CI使用同样的pytest／Ruff流程，远端矩阵为Python 3.11与3.12。本机未运行3.11矩阵，未推送，故没有本次远端CI通过结论。
- 检查工作区、完整diff及候选清单，并扫描常见Provider令牌、JWT、私钥、密码哈希、带凭证URL和敏感变量字面量。工作区宽扫描命中1处权限枚举、3处固定测试字符串和1处明确测试占位，复核均非真实凭证；候选38文件扫描无疑似凭证命中。
- 未发现候选包含环境文件、数据库、真实用户课程／JD、个人联系方式、调试日志、缓存、虚拟环境或Playwright临时资产。截图均来自已标明的合成案例／隔离历史夹具。未安装gitleaks，本结论是本地模式扫描与内容审阅结果，不是对所有未知密钥格式的保证。
- 候选Markdown相对文件链接检查无失效目标；90秒入口、真实clone地址、历史测试数和贡献边界复核一致，P2仍为未实施。
- 暂存后另执行`git diff --cached --check`、`git diff --cached --stat`，复核暂存文件与上述白名单一致，并对暂存blob再次扫描；这些步骤通过后才创建本地提交。

### 真实浏览器复测

Chrome／Playwright CLI 0.1.21；真实Streamlit应用监听本机8520端口，关闭系统AI，数据库位于D盘隔离目录。历史恢复使用既有AppTest合成夹具的独立本地服务8521；Showcase静态页使用8522。未使用真实账户、求职资料或付费模型。

- 公开首页、个人分析、本地规则与登录入口可访问。下载模板并实际上传，导入1门示例课程，粘贴合成JD，提取4项技能，经确认入口生成45.5分报告，无应用异常。
- 数字化实施／信息化支持、AI应用／解决方案、数据分析均运行、重置并导出；报告分别为41.2、39.8、50.3分。每例实际下载的ZIP可解压，Excel可重新解析，JSON／JD匹配预设；Markdown与CSV逐字节等于同一报告的后端导出（包含合成案例边界说明），CSV保留五列。
- 桌面1440×1000和390×844窄屏检查报告、来源解释、表格和控件。窄屏收起侧栏后解释可读，长表格局部滚动；数据案例、历史v2.1和Showcase测得页面宽度390，无整体横向溢出。桌面门槛metric可能省略长文本，紧邻完整说明保留。
- legacy历史恢复保留72分，v2.1恢复保留68分；两者桌面／窄屏均可展示，旧v2.1空checks显示“未设置／待确认”。新代码可读取不含可选新字段的旧快照，不补造来源。
- 游客分析流程与历史夹具无application exception、console error或warning。登录页另有2条Chrome DOM verbose提示（密码控件不在HTML form内），不是error或warning。直接新开`/analysis`复现`/analysis/_stcore/health`及`host-config`两次404探测，随后页面恢复正常，不能概括为所有访问方式零错误。
- Showcase本地静态页面、图片及链接目标检查通过，390宽无溢出、无损坏图片，控制台0 errors／0 warnings。未将此结果冒充Cloudflare Worker运行时、外部链接可达性或生产验收。
- 初轮自动脚本在窗口尺寸切换／页面重绘期间出现控件等待超时；改用稳定后的分步交互完成上述检查，没有通过修改产品或隐藏异常使脚本通过。下载校验脚本补入界面已有合成边界后逐字节比对通过。临时脚本、截图和下载保留在`D:/codex_study/_tmp/c2c-release-audit/`，不进入仓库；可分享的项目截图仍由[截图索引](../screenshots/README.md)管理。

### 回滚边界与后续授权

**本地候选验证通过，可进入授权发布流程；尚未发布或生产验收。** 未执行push、tag／release、远端Secrets修改、部署、域名／DNS更改、C08或C09。未验证真实AI质量、真实用户效果或人工Gold指标。

代码回滚单位是本节所属单一提交：经授权后可通过`git revert <候选SHA>`创建反向提交，保留历史，禁止force push；Streamlit与Showcase均需重新部署并验收。当前本地不执行回滚。

**数据库降级不是自动兼容的。** 额外使用基线Pydantic模型读取三个新合成快照，均因新增`sources`字段被拒绝，有学习任务的快照还包含`task`与`completion_criteria`。这是“新代码读旧数据”与“旧代码读新数据”的方向差别，不是本次旧历史恢复失败。

正式发布前应确认数据库持久化方式，保留可恢复的发布前一致性备份及平台配置版本；发生回退时先保留上线后的数据库，避免丢失新增报告／账户／额度记录。若使用发布前备份恢复，须明确中间写入的数据保留和恢复办法并取得相应授权；不能直接覆盖数据库。需要保留全部新写入时，应先单独评审兼容处理，不能声称只revert代码即可无损降级。本轮未触碰生产数据库或改变存储协议。

获得上线授权后的顺序：核对候选SHA→push main（不force）→检查远端SHA与CI→确认Streamlit实际自动部署绑定／更新状态→核对Cloudflare目标配置并同步已修改的Showcase→合成数据生产Smoke Test。由于main可能触发自动部署，推送前也应确认触发关系并完成备份准备，不能假定CI会阻挡所有平台的自动更新。生产成功后再记录Production SHA和部署日期，再讨论C08。

## 2026-09-22 Final Pre-Publish Audit / RC2

本节取代前文的当前候选及后续发布顺序；前文保留为历史记录。原RC为`2dccf9cf0ef5587827d4411c9b24695ab416ddc3`，本节所属新提交为RC2，不amend原提交。生产运行时信息由用户在本轮确认：Python 3.14、Sharing为Public and searchable，Secrets无`COURSE2CAREER_DATABASE_PATH`；本轮没有修改任何生产设置。

### Git与发布坐标

起始分支main、HEAD仍匹配原RC，暂存区和已跟踪工作区干净；两个未跟踪用户文件SHA-256与初始记录一致。GitHub插件及`git ls-remote`发现实际远端已从原Base `04f1b32834a668813df30418cce414617c8952b7`前进到`2df8f317f39da20fc39162702728da82e2e26072`，新增提交`Added Dev Container Folder`仅增加`.devcontainer/devcontainer.json`（33行）。只读fetch已刷新本地origin/main，未将该提交合并或rebase到RC，也未改写任何历史。

因此后续PR必须面向届时最新main，保留远端Dev Container文件，验证实际PR差异及合并结果；不能继续声称远端仍是原Base。此独立配置新增不改变本地兼容性结论，不因它中止本轮自主技术审计。

README、仓库结构、app.py入口及公开URL与`tcjyq/mhj-course2career` / `main` / `app.py`高度一致。公开HTTP请求可返回200，但没有返回可证明内部绑定的仓库／分支／入口元数据：**部署坐标高度一致但平台内部绑定无法从当前授权渠道直接读取**。不将这一观测限制冒充已确认事实，也不再要求用户逐项人工检查。

后续顺序以本轮授权为准：release branch → PR CI（3.11／3.12／3.14）→单独授权合入main → Streamlit立即smoke test → Showcase。当前仅创建本地RC2，不创建远端分支或PR，不push、merge、部署或修改Secret。

### Python 3.14兼容性

使用本机已有CPython **3.14.2**创建独立环境`D:/codex_study/_tmp/c2c-py314/`，没有修改系统默认Python或原`.venv`。从原`requirements-dev.txt`完成全新安装，全部直接依赖pin保持不变，`pip check`无冲突。下载缓存及验证产物位于D盘；初次pip构建的少量自动临时文件使用系统TEMP，后续验证显式使用D盘TEMP／TMP。

| 固定依赖 | 安装元数据Requires-Python | 3.14实际安装 |
| --- | --- | --- |
| Streamlit 1.60.0 | >=3.10 | 通过 |
| pandas 3.0.3 | >=3.11 | 通过，cp314 wheel |
| Pydantic 2.13.4 | >=3.9 | 通过，pydantic-core有cp314 wheel |
| openpyxl 3.1.5 | >=3.8 | 通过 |
| cryptography 49.0.0 | >=3.9，排除3.9.0／3.9.1 | 通过，cp311-abi3 wheel |
| OpenAI SDK 2.46.0 | >=3.9 | 通过 |
| python-dotenv 1.2.2 | >=3.10 | 通过 |

表格依据实际安装包元数据与pip解析，不把最低版本声明单独当作运行正确证明；完整测试和真实启动见下。官方包发布信息可在[PyPI固定版本](https://pypi.org/project/cryptography/49.0.0/)复核。项目`requires-python >=3.11`、无相冲突classifiers，Ruff `target-version=py311`表示最低语法兼容目标，无需修改。源码编译检查通过；未发现cgi、cgitb、asyncore、asynchat、distutils、imp等已移除模块引用。没有发现需要更改业务源码的3.14兼容性缺陷。

### 本轮验证结果

```powershell
.venv/Scripts/python.exe -m pytest -o addopts='' -q -o cache_dir=D:/codex_study/_tmp/c2c-rc2-cache --basetemp=D:/codex_study/_tmp/c2c-rc2-py312 --tb=short
D:/codex_study/_tmp/c2c-py314/Scripts/python.exe -m pip install --cache-dir D:/codex_study/_cache/pip -r requirements-dev.txt
D:/codex_study/_tmp/c2c-py314/Scripts/python.exe -m pip check
D:/codex_study/_tmp/c2c-py314/Scripts/python.exe -m pytest -o addopts='' -q -o cache_dir=D:/codex_study/_tmp/c2c-rc2-cache --basetemp=D:/codex_study/_tmp/c2c-rc2-py314 --tb=short
# 两个环境分别执行
python -m ruff check .
python -m ruff format --check .
git diff --check
node --check showcase/src/worker.js
```

- Python 3.12.14：**150 passed，27.46秒，0 failed／0 skipped**。
- Python 3.14.2：**150 passed，22.82秒，0 failed／0 skipped**。
- 两环境Ruff通过，format均为65 files already formatted；diff及Showcase Worker语法检查通过。
- C01—C07、legacy／v2.1历史恢复、旧快照字段兼容、权限、加密及热重载等由完整测试覆盖；没有删除测试、skip或放宽关键断言。
- Python 3.11本轮未在本机执行，保留CI矩阵。CI仅增加3.14，仍对PR和push main执行同一安装、Ruff、format、pytest流程。本地Windows实测不能替代GitHub Linux三版本CI；本次没有远端CI结果。
- 使用3.14真实启动`streamlit run app.py`，关闭dotenv载入与系统AI，使用D盘合成数据库。首页→个人分析→三个演示→重置／导出正常；分数分别41.2／39.8／50.3。模板下载上传→合成JD→规则提取→确认→45.5分报告正常。
- 桌面1440×1000、窄屏390×844截图复核通过，三个演示页面无整体横向溢出、无应用异常。长门槛metric仍可能省略，紧邻完整文案保留。初轮脚本在窗口重绘后等待下拉选项超时，分步重选及后续键盘交互完成验证，没有修改产品来回避失败。
- 三份实际浏览器下载ZIP／Excel／JSON／JD合法，Markdown／CSV与相同输入的后端导出逐字节一致，CSV保留五列。临时截图、脚本和下载均在`D:/codex_study/_tmp/c2c-rc2-browser/`等D盘临时目录，不加入候选。
- 本轮首页导航的浏览器流程0 console errors／0 warnings；先前已记录的直接深链`_stcore`两次404保留为已知限制，本轮不声称所有访问方式零错误。未调用真实AI或执行生产写操作。

### 数据、安全与最终边界

用户明确当前为作品集Demo，未发现代码或配置声明不可丢失生产数据。默认路径确为`instance/course2career.db`，文件被Git忽略。重复初始化前后6张SQLite表的schema一致，管理员幂等性由现有测试覆盖；C01—C07无SQL schema migration。

本轮在3.14再次验证基线模型读取新合成快照，仍拒绝sources／task／completion_criteria；这是JSON降级兼容边界，新代码读取旧数据正常。Demo本地状态的非持久性不作为本轮阻断；依然禁止擅自覆盖／删除生产数据。C08正式上线前持久化account、report、encrypted API key、quota、usage、provider profile的技术债已写入[部署文档](deployment.md)，未实施C08。

对原候选及新增CI／部署文档共40个候选文件重新检查常见令牌、私钥、JWT、密码哈希、敏感字面量与禁止产物路径，未发现疑似真实凭证；相对文档链接检查通过。原有12张截图保持不变，均为已审阅合成示例。环境文件、数据库、上传、日志和临时浏览器产物未进入候选；两个用户资料保持不变。提交前再次核对本轮暂存白名单及差异，安全检查不输出凭证正文。

本轮修改仅为CI matrix、部署说明及验证／开发记录，不改变评分、CSV、数据模型或用户界面，不新增项目依赖。原RC被RC2取代，创建新本地提交`fix: align release candidate with production runtime`。最终SHA以该提交及交付报告为准。

**本地发布前审计通过，无已知本地技术阻断；就绪程度是可进入release branch与PR CI，不是已上线。** 尚需授权后运行三版本远端CI、检查最新main合并结果及生产实际版本。Cloudflare稳定回退参考仍为Version `4237f2e9-3a30-4216-8a91-dec73a45bb10`、Deployment `2e1800ab-6b55-4cba-b9ad-ef4b8d9f2b3d`（前轮只读查询及用户确认）；本轮未部署，正式发布前应刷新。未验证真实模型质量或用户效果，不进入C08／C09。
