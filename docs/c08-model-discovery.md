# C08-C 模型发现、能力与价格目录

状态：2026-09-24 本地分支实现，未发布。大陆主流六家优先显示；国际四家置于折叠区。Provider Preset 声明接入协议和目录策略，目录适配层解析官方响应，`ModelCapability` 合并官方元数据与按 Provider × endpoint × exact model 保存的 B2 验证记录。官方列出模型或宣称 JSON 能力均不自动升级为 `VERIFIED`。

## 使用流程

普通登录用户在“我的 AI Provider”免费启用开发者模式。保存自己的加密 Key 后，选择受控区域端点；百炼北京/美国目录还需业务空间 ID。点击“刷新模型”请求官方目录；静态 Kimi/GLM 目录可直接查看。选取目录 ID 并“保存配置”才改变用户 Profile，刷新不会自动迁移旧模型。DeepSeek 旧 `deepseek-v4-flash` 标为 `COMPATIBILITY_ALIAS`，建议用户主动改为 `deepseek-flash`。系统 Free AI 仍固定 DeepSeek；此处的 BYOK 不消耗平台系统额度。

目录条目显示官方 Structured Output、Course2Career 验证、上下文及可核实的每百万 token 价格。未知价格保持 `None`；币种不同不换算或相加。DeepSeek 价格是非高峰价，百炼仅在返回 `Default` 档和可识别单位时展示，Kimi 为官方平台快照；地区、峰时、缓存写入或其他 tier 可能改变账单。目录中的价格仅供选模参考，不替代使用量账单或分析页现有成本估算配置。

## 缓存和安全

动态目录支持 30 分钟 TTL、手动强制刷新、失败后保留最近一次成功目录并标 `STALE`；显示上次成功时间。缓存键包含用户、Provider、官方端点 ID、百炼 Workspace ID 和 Key 更新时间。关闭开发者模式后即使旧会话或缓存仍在，服务层也拒绝目录查看与刷新；重新开启可恢复该会话中的无密钥缓存与已保存 Key/Profile。浏览器会话丢失或进程重启后缓存会消失，重新刷新即可。请求禁止重定向，错误只显示本地脱敏文案，不回显供应商原始响应、URL 或凭证。无任意自定义 Base URL。

DeepSeek、百炼、SiliconFlow、MiniMax、OpenRouter、OpenAI、Anthropic、Gemini 用动态 API；Kimi、GLM 在未核实稳定模型目录 API 前使用有日期和来源的短静态目录。DeepSeek 新增 ID 可出现在发现结果中，但在专用调用适配器与 Auto-Safe 白名单扩展前不进入可保存下拉。百炼与 Anthropic/Gemini/OpenRouter 分页有界；无效模型 ID 和异常价格不会进入目录。SiliconFlow 当前 models API 未提供可信的精确价格/上下文，保持未知。Kimi/GLM 静态快照需维护者定期复核官方页；动态目录可能受到用户账户权限、区域及上游变更影响。

## 发布前剩余证据

本地 fake 测试证明解析、权限和缓存契约，不证明供应商真实模型输出。当前 B2 只有 OpenAI、Anthropic 两次 401；十家均无 VERIFIED。合法大陆 Key 可由持有人主动执行低成本 `GET models`，不要自动触发收费的 B2 固定 JD 验证。发布前需逐区域和精确模型跑 B2，核对结构化输出、返回模型、usage、计费与安全边界；随后复核生产持久化、隐私和浏览器行为。[Provider 矩阵](c08-provider-matrix.md) · [B2 报告](c08-provider-validation.md)。
