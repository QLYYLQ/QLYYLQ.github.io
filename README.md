# QLYYLQ.github.io

个人主页，发布在 https://qlyylq.github.io/ （GitHub Pages，master 分支根目录，纯静态，`.nojekyll` 关掉了 Jekyll）。

- `index.html`：主页
- `omnifex/`：Omnifex 项目（PCB 到 CAD 的 agent 工具包和 gym）的文档，来自 claude.ai artifact 的本地副本
- `assets/site.css`：主页和项目索引页共用的样式

## 更新 Omnifex 文档

artifact 的本地副本在 Omnifex 工程的 `artifacts/` 目录。改完后：

```sh
python3 scripts/sync_omnifex.py <Omnifex 工程>/artifacts
git add -A && git commit -m "Sync Omnifex pages" && git push
```

脚本只去掉 claude.ai 的页面外壳、补 doctype、把互相引用的 artifact 链接换成站内链接，正文不动；源文件和输出的 sha256 记在 `omnifex/manifest.json`。新增页面要在脚本的 `PAGES` 里登记，再在 `omnifex/index.html` 加一行。
