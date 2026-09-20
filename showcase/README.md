# Course2Career Showcase

此目录是独立于 Streamlit 的静态招聘展示页：不运行 Python，不读取 API Key，不写入用户数据。

本地预览：

```powershell
npx wrangler dev --config showcase/wrangler.jsonc
```

发布并绑定 `course2career.tcjyq.cc`：

```powershell
npx wrangler deploy --config showcase/wrangler.jsonc
```

页面只复用了仓库已有的真实首页截图 `screenshots/home.png`，复制版本位于 `public/course2career-home.png`。
