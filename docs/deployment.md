# 部署说明

## 当前定位

当前版本适合本地运行、作品集演示和受控测试。开放系统 AI 能力前，应先完成限流、真实 Token/费用统计、权限会话失效和全局预算熔断。

## 环境配置

从 `.env.example` 复制本地配置，不要提交 `.env`。生产环境应通过部署平台的 Secret 管理功能设置：

- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `COURSE2CAREER_KEY_ENCRYPTION_KEY`
- `COURSE2CAREER_DATABASE_PATH`

只使用本地规则模式时，模型凭证和加密主密钥可以留空。

## 启动

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## 发布前检查

1. 测试、Ruff 和格式检查全部通过。
2. 仓库中不存在 `.env`、数据库、日志、缓存或真实凭证。
3. 使用 HTTPS，并在反向代理层设置请求速率、并发和上传大小限制。
4. 备份数据库与 API Key 加密主密钥，但两者分开保存。
5. 不把用户课程、完整 JD、密码或 API Key 写入日志。
6. 公开页面提供隐私说明和第三方模型数据传输提示。
