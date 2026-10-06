# 首页重构：研究与方向选择

研究日期：2026-10-06（UTC+8）。基线 `82047de0b50e051ca6f3ed4b4088cb17851c5211`，包含 PR #7 / #8。公开 Showcase 与 Streamlit 工具是两个实际表面；本轮仅改展示层及品牌样式。

## 产品审计

| 项目 | 结论与本地依据 |
| --- | --- |
| PRODUCT_PURPOSE | 将课程与经历转为可解释的岗位能力支撑，辅助学习决策，不预测录用概率。 |
| TARGET_USER | 准备实习、校招的大学生。 |
| CORE_VALUE | 材料来源、技能支撑、独立硬门槛、五维评估、逐项账本与下一步交付物。 |
| CORE_FLOW | 课程 / 教育 / 项目 / 实习 / 潜力 + JD → 语义提取 → 人工确认 → Python 规则 → 报告与学习路线。 |
| TRUST_MODEL | 来源可读；未填写与明确没有分开；直接材料、迁移、自述不等于外部验证。 |
| AI_ROLE | 可选 JD 语义提取；本地规则和合成案例可无 AI 完成。 |
| RULE_ENGINE_ROLE | 映射、技能迁移、五维权重、硬门槛、解释与学习任务，现有实现不修改。 |
| PRODUCT_DIFFERENTIATORS | 用户能确认输入并沿结果回看证据；门槛不作为技能分数乘数。 |

阅读 `app.py`、`ui/home_page.py`、`ui/styles.py`、`ui/analysis_page.py`、`ui/developer_page.py`、README、architecture、合成案例和规则引擎。公开站点以浏览器实访，桌面 / 移动 Before 保存在 `screenshots/homepage-20261006/`。原页面重复的编号、平铺栏目与抽象流程图弱化了产品含义；移动流程需横向滚动且连线消失，图示无法解释具体材料。

## 官方标准

- [Awwwards Evaluation](https://www.awwwards.com/about-evaluation/)：浏览器可读取，Design / Usability / Creativity / Content 权重为 40 / 30 / 20 / 10。网页抓取服务超时不代表未查看；原始浏览器文本留在本机研究 JSON。
- [Awwwards Mobile Excellence](https://www.awwwards.com/mobile-excellence-guidelines.pdf)：关注可读性、目标尺寸、资源与加载、设备适配。
- [Webby 2026/2027 Judging Criteria](https://www.webbyawards.com/judging-criteria/)：内容、结构导航、视觉、功能、交互、创新、整体体验；同时考虑认知与带宽差异。
- [FWA 官方说明](https://thefwa.com/FWA25/25.html)与[官方策展](https://thefwa.com/FWA25/RobFWA.html)：创新、原创性和技术执行。此处不虚构 FWA 的固定七项权重。

## Reference board

仅提炼原则，页面没有复制参考的资产、独特图形、文案、版式或交互。研究为浏览器桌面首屏、中段、尾部、390px 首屏及局部交互；历史获奖页面与目前 live 版本可能不同。Webby 提名与获奖分别记录，FWA 策展不冒充另一种奖项。截图只用于本机研究，不向仓库再分发第三方素材。

每个案例的字段顺序为 WHY_IT_WORKS / TYPOGRAPHY / LAYOUT / WHITESPACE / VISUAL_HIERARCHY / MOTION / INTERACTION / RESPONSIVE / ORIGINAL_SIGNATURE / WHAT_NOT_TO_COPY。

### Awwwards

1. [Anime.js](https://www.awwwards.com/sites/anime-js)，2025 SOTM / Developer；[live](https://animejs.com/)：动效本身证明产品 / 厚重无衬线短句 / 主图承担首屏重心 / 工具入口留足距离 / 动画引擎先于细节 / 功能演示各自运动 / 文档与曲线入口可见 / 手机重组而非压缩 / 可运行的引擎形态 / 不复制发光圆盘、色环或节奏。首轮 full-page 有大量未触发区域，随后重访并截图实际动态首屏，提示本项目不能依赖滚动才能显示内容。
2. [Turn.io](https://www.awwwards.com/sites/turn-io)，2025 SOTD / Developer；[live](https://www.turn.io/)：具体使用场景先于功能 / 粗体清晰 / 用户情景与说明并置 / 大区块换色停顿 / 一个主要 CTA / 对话显示因果 / tour 与产品入口 / 手机上文本先行 / 消息情景 / 不复制同色品牌、患者图像、客户墙或指标。
3. [Seasoned](https://www.awwwards.com/sites/seasoned)，2025 SOTD / Developer / Typography；[live](https://seasoned.koto.studio/)：把学习内容做成可探索对象 / 书本与内容标题形成对比 / 内容集合 / 少量对象占据大片空间 / 内容本身是入口 / 状态变化与阅读关联 / 分类与阅读 / 手机保持内容层级 / 数字书架 / 不复制书本视觉、书架、字体。最初误用域名连接失败，已从官方 Visit Site 链接纠正。
4. [We are Büro](https://www.awwwards.com/sites/we-are-buro)，2025 SOTD / Developer；[live](https://burocratik.com/)：鲜明语气贯穿 / 大小文字敢于拉开 / 满幅图像与开放式文字区转换 / 密度高低交替 / 图像记忆先于解释 / 首屏编排 / 底部导航 / 手机调整信息密度 / 品牌作品舞台 / 不复制影像、胶囊导航、编号排版。

### Webby

5. [Bézier](https://winners.webbyawards.com/2025/websites-and-mobile-sites/features-design/best-visual-design-function/324140/bzier)，2025 Best Visual Design – Function Winner；[live](https://bezier.com/)：字体即内容 / 字体样本承担展示 / 样本到分类再到试用 / 给字体看清自身的空间 / 内容分层 / 样本变换 / 测试与许可清晰 / 手机保持样本阅读 / 可试用字体展示 / 不复制字体模型、产品色块与试字界面。首屏早期加载为空，滚动后可见样本，作为负面加载教训记录。
6. [Writing Examples](https://winners.webbyawards.com/2025/websites-and-mobile-sites/general-desktop-mobile-sites/education/333865/writing-examples)，2025 Education Winner；[live](https://writingexamples.com/)：先示例后理论 / 题材文字各有个性 / 内容目录 / 每个主题有呼吸空间 / 题目直接回答学习问题 / 状态服务阅读 / 主题选择 / 单列保留题目 / 内容策展 / 不复制书封、插图、米色底或装饰字。
7. [Climate TRACE](https://www.webbyawards.com/press/press-releases/29th-annual-webby-awards-announce-2025-winners/)，2025 Sustainability & Environment Winner；[live](https://climatetrace.org/)：可追查数据来源 / 标题与数据分层 / 从叙事进入开放数据 / 图表留出尺度 / 数据与行动分开 / 数据加载可见 / 数据入口 / 保留关键统计语境 / 排放视图 / 不复制地图、统计或图表。需等待数据加载，不能将 loader 截图当完整界面。
8. [AW Portfolio](https://winners.webbyawards.com/winners/websites-and-mobile-sites/features-design/best-home-page)，2025 Best Home Page Winner；[live](https://wodniack.dev/)：统一视觉决断 / 极强的压缩字形 / 模块连续 / 强弱空间反差 / 首屏记忆点 / 场景运动 / 作品入口 / 手机主动换行 / 强红色线场 / 不复制红色、密集线场、字形和动画。

### FWA 官方策展

9. [Messenger](https://thefwa.com/FWA25/RobFWA.html)，官方 2025-10 策展；[live](https://messenger.abeto.co/)：交互世界表达主体 / 空间文字 / 可探索场景 / 场景空域 / 开始入口 / 运动来自探索 / 场景操作 / 手机上独立入口构图 / 可玩的世界 / 不复制场景、人物、镜头或交互概念。
10. [Bruno's Portfolio](https://thefwa.com/FWA25/RobFWA.html)，官方 2025-12 策展；[live](https://bruno-simon.com/)：作品能力由操作展示 / 场景为主 / 沉浸世界 / 导航空间 / 先加载再进入 / 物理运动 / 操作说明 / 手机上触控策略 / 场景驾驶 / 不复制车、地图、任务、镜头或紫色光效。本轮初始截图主要停在加载阶段，因此不会根据它编造完整体验质量。
11. [ASTRODITHER](https://thefwa.com/FWA25/RobFWA.html)，官方 2025-10 策展；[live](https://astrodither.robertborghesi.is/)：单一技术表达做到极致 / 极少标签 / 单一场域 / 留白保护视觉 / 进入操作明确 / 像素与流体变化 / 点击反馈 / 全屏场域适配 / 实验性视觉材质 / 不复制 dither、流体、音频或输入手势。
12. [Studio Null](https://thefwa.com/FWA25/RobFWA.html)，官方 2025-04 策展；[live](https://www.madebynull.com/)：一个对象建立品牌记忆 / 清晰简短无衬线 / 开放舞台 / 极大空域 / 作品对象与行动 / 对象运动 / Info 入口 / 保留对象主导 / 几何对象 / 不复制三角体、蓝色材质、镜头或空间布局。

参考的实际加载问题同样影响方向选择：Course2Career 不能把可读内容藏在动画、loader 或重型场景之后。

## 三个方向与评审（编码前）

使用情景：大学生在宿舍桌前或通勤途中，用笔记本 / 手机快速对照一份岗位要求；情绪是有点不确定，但愿意核查自己的学习材料。选择浅中性底以支持中文字与证据阅读，深绿色承接已有品牌，朱橙只标出转换与待核对的节点。

| 字段 | A 证据索引 | B 成长星图 | C 折译轨道（选择） |
| --- | --- | --- | --- |
| CORE_VISUAL_IDEA | 课程档案打开后成为来源索引 | 能力节点连接岗位 | 未整理材料经过确认折点，展开为可追溯的岗位支撑 |
| LAYOUT_LANGUAGE | 档案式长页、边注 | 空间中心、探索路径 | 开放首屏、折线图、独立结果章节、完整结束动作 |
| TYPE_SYSTEM | 档案标题 + 阅读字 | 短标签 + 大标题 | Manrope 拉丁字 + 系统中文黑体；数字等宽 |
| COLOR_SYSTEM | 灰白 / 深绿 / 橙 | 深绿 / 浅绿 / 蓝 | 中性白 / 墨绿 / 明确语义的朱橙 |
| MOTION_LANGUAGE | 展开与标记 | 节点聚集与探索 | 线条穿过确认折点；选择技能后只高亮对应路径 |
| SIGNATURE_ELEMENT | 档案切口 | 关系星座 | 开口折线与确认节点：形状同时成为品牌记号、路径与章节转场 |
| WHY_COURSE2CAREER | 证据可查 | 映射关系 | 直译“材料 → 人工确认 → 规则 → 岗位支撑” |
| RISK | 容易退回普通编辑式网站 | 手机密度 / 误导关系 / 性能 | 连线若没有内容意义会沦为装饰，因此每条关联具体课程和技能 |
| PRODUCT FIT / ORIGINALITY / IMPACT / USABILITY | 9 / 7 / 7.5 / 9 | 8 / 8 / 9 / 6.5 | 9 / 9 / 9 / 9 |

这些是方向选择的主观比较，不是完工评分。最终分数必须另行根据实际截图和检查记录给出。

## 实施约束

Showcase 用本地 HTML / CSS / 小型 JS / SVG；没有框架迁移、远程 JS 或 tracking。浏览器原生动画已足够表达选中路径，因此不引入 GSAP 依赖。渐进增强：无 JS 时能阅读完整内容和默认示例，所有 CTA 为真实链接。Streamlit 使用同一色彩与开口折线语言，保留原导航和恢复机制。演示只来自仓库合成案例，以离线规则结果生成，证据来源和完整输入可下载；首页不调用 Provider。

最终迭代与质量记录见 [首页验收](homepage-design-review.md)。
