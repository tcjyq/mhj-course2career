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

页面包含原创 SVG 折译轨道和三个公开合成报告。数值由仓库输入与既有 Python 规则离线生成，不在浏览器执行评分，也不调用 Provider。更新数据：

```powershell
python scripts/build_showcase_demo.py
```

本轮 PR #9 继续保留折译轨道：手机是单路径有序流程；报告包含可展开的实际贡献原因、独立门槛和技能来源。材料可以进入数据分析示例的对应技能，再沿实际来源返回材料。关键字级至少 13px，所有运动支持 reduced-motion；未加入动画库。[审查后的同版本对比](../docs/homepage-pr9-review-iteration.md)。

`public/site.js` 只请求同源 `/demo.json`，增强技能路径、报告切换与移动导航。无 JS 时默认数据分析报告及 CTA 仍可用；不存在用户数据存储、远程 JS 或新增 tracking。Manrope 拉丁字体在 `public/fonts/` 托管，并附 SIL OFL 许可证；中文使用系统字体。

真实 Streamlit 首页截图 `screenshots/home.png` 的复制版本位于 `public/course2career-home.png`，测试保证字节一致。重构候选未部署；[设计研究](../docs/homepage-design-research.md) · [完整验收](../docs/homepage-design-review.md)。
