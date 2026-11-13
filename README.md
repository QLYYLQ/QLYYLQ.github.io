# QLYYLQ.github.io

个人主页，发布在 https://qlyylq.github.io/ （GitHub Pages，master 分支根目录，纯静态，`.nojekyll` 关掉了 Jekyll）。

- `index.html`：主页
- `omnifex/`：Omnifex 项目的索引和报告。四份报告来自 claude.ai artifact 的本地副本。
- `omnifex/cases/data/`：案例正文 JSON，是案例页的编辑入口；字段见 [数据说明](omnifex/cases/data/README.md)。
- `omnifex/cases/img/`：从原生 KiCad、STEP 等工件渲染的图、交互模型和缩略图。
- `scripts/build_cases.py`：从 JSON 生成案例详情页、案例索引及项目页案例数。
- `assets/site.css`：主页、项目索引和案例页共用的样式。
- `cu-model/`：与 Omnifex 同级的 CU Model 项目页、25 份研究报告、23 张实验图和 14 例 AGW 画廊。

站点没有 npm 依赖或服务端。Python 3 标准库即可构建 Omnifex 案例、检查和预览全站；CU Model 报告转换使用下文固定版本的 Markdown。浏览器的 3D 模型使用 `assets/vendor/model-viewer/` 中的固定版本，加载失败时保留静态预览。

本仓库已独立放在 `~/QLY/code/QLYYLQ.github.io`，拥有自己的 `.git` 和原 GitHub remote，不依赖 Omnifex 工程的目录层级。网页和已收录资料都随仓库保存，预览和发布不需要挂载研究工程。

## 更新 CU Model

`cu-model/reports.json` 登记报告标题、日期和本地来源。`sources/` 保存供网页使用的 Markdown 快照；`media/` 保存原图和对照 CSV；`index.html` 的概述单独维护，报告目录由脚本更新。现有 GitHub Pages 直接提供生成好的 HTML，访客不需要 Markdown 渲染器或 Claude 登录。

首次同步或研究稿有变更时（源目录只读）：

```sh
uv run scripts/build_cu_model.py --source ~/QLY/report/cu_model
python3 scripts/check_cu_model.py --source ~/QLY/report/cu_model
python3 scripts/check_site.py
```

只改快照或页面模板时，运行 `uv run scripts/build_cu_model.py`。构建脚本用内嵌依赖声明固定 `Markdown==3.7`，由 uv 提供隔离环境；普通检查和预览仍只依赖 Python 标准库。不要直接改生成的报告 HTML。

转换保留研究正文和数值，将个人机器与内部存储位置泛化；源文件原始哈希记录在 `provenance.json`，快照、网页及图表哈希记录在 `manifest.json`。原报告引用但本站未收录的文件会显示为带提示的虚线文字，明细在 `unbundled-references.json`。未复制实验大包、模型、运行凭证、Claude 记忆和远程作业配置。历史报告按原日期保留，最新方案以 2026-11-03 路线为准。

## 更新 Omnifex 文档

artifact 的本地副本在 Omnifex 工程的 `artifacts/` 目录。改完后：

```sh
python3 scripts/sync_omnifex.py <Omnifex 工程>/artifacts
python3 scripts/check_site.py --artifacts <Omnifex 工程>/artifacts
```

脚本只去掉 claude.ai 的页面外壳、补 doctype、把互相引用的 artifact 链接换成站内链接，正文不动；源文件和输出的 sha256 记在 `omnifex/manifest.json`。新增页面要在脚本的 `PAGES` 里登记，再在 `omnifex/index.html` 加一行。

## 更新案例

正文和图上的数字来自 Omnifex 工程的 `data/answer_mining_20261107/construct/`、对应的改前快照、模型交付文件、自动检查、复核与审计记录；稚晖君题源另见 `data/peng_zhihui_20261112/`。各案例的 `sources` 列出具体记录和上游公开链接。`C/<id>/…` 是 `data/answer_mining_20261107/construct/<id>/…` 的缩写。本站保存展示材料，原始工程、完整判分器和临时转换文件留在研究工程里。

先改 JSON 和原始渲染图，再生成缩略图，最后重建 HTML。不要直接编辑生成的 `omnifex/cases/*.html`。

```sh
python3 scripts/make_thumbs.py
python3 scripts/build_cases.py
python3 scripts/check_site.py
python3 -m http.server 8765 --bind 127.0.0.1
```

浏览器打开 `http://127.0.0.1:8765/`，检查桌面和窄屏、前后对比滑块、3D 模型切换。静态检查会核对 JSON、资源和站内链接、生成结果、案例数量以及报告哈希；它不会验证 CAD 几何、电路结论、外部链接可用性或浏览器交互。

`make_thumbs.py` 使用本机 Chrome 和 macOS `sips`，默认按源图时间跳过已有缩略图；可传案例 ID 只更新一例，或加 `--force` 重做。它也生成首页和项目索引的封面图。只有正文变化时可以跳过缩略图步骤。

重新制作原始图时，`scripts/render/pcb_svg.py` 要用带 `pcbnew` 的 KiCad Python，`scripts/render/step_glb.py` 要用装有 build123d 的环境；两者的 spec 格式见脚本开头。`scripts/render/glb_poster.py` 用 Chrome 为 GLB 生成静态预览图。不要用截图替代缺失的原生证据；无法核实的地方在正文中说明。

核对 `git diff` 和新增文件后提交并推送 `master`，GitHub Pages 会发布根目录。发布后检查 GitHub 的 Pages 部署结果和线上页面。
