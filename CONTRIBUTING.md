# 参与贡献

感谢你关注 Course2Career。提交改动前，请先阅读
[开发规范](docs/development-guide.md)。

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

## 提交流程

1. 从 `main` 创建短期分支，例如 `fix/excel-validation`。
2. 一个提交只处理一个明确问题。
3. 使用 `feat:`、`fix:`、`docs:`、`test:`、`refactor:` 或 `chore:` 前缀。
4. 提交前运行测试和 Ruff，并确认没有密钥、数据库或个人数据。
5. Pull Request 应说明改动原因、验证方式和潜在影响。

功能建议和缺陷报告请通过 GitHub Issues 提交。安全问题请不要公开披露，处理方式见
[SECURITY.md](SECURITY.md)。
