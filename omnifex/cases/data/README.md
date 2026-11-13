# 案例数据

每个案例一份 `<id>.json`，UTF-8 编码。`scripts/build_cases.py` 按分组、`order`、`id` 排序生成详情页和索引；以下划线开头的 JSON 不参与构建。修改数据后先更新缩略图，再重建 HTML，最后运行 `python3 scripts/check_site.py`。

常用完整例子是 [489f2861.json](489f2861.json)。路径从 `omnifex/cases/` 起算，例如 `img/489f2861/agent_full.svg`。不写本机绝对路径。

| 字段 | 内容 |
| --- | --- |
| `id` | 与文件名一致，使用小写字母、数字和连字符；也用作详情页文件名。 |
| `group` | `grader`（判分问题）、`hard`（模型困难）、`round2`（第二轮问题）或 `source`（新题源）。 |
| `order` | 组内排序整数。 |
| `project` | 项目名称，可附上游仓库名。 |
| `short` | 卡片和翻页用的短标题。 |
| `title`、`description` | 详情页标题和一句话描述。 |
| `domain` | 字符串列表，如 `["PCB"]` 或 `["PCB", "外壳"]`。 |
| `level` | 难度或题源状态说明。 |
| `verdict` | 标签列表，每项为 `{"label": "未通过", "tone": "bad"}`；`tone` 为 `good`、`bad`、`warn`、`info`。 |
| `summary` | 开头的段落列表，先交代结论。 |
| `numbers` | 可选关键数字列表，每项为 `{"v": "19", "of": "25", "k": "初判通过的检查"}`；`of` 可省略，数字用字符串。 |
| `task` | 可选题面区：`heading`、`intro`（段落列表）、`rows`（`[标签, 文本或段落列表]` 的列表）。 |
| `steps` | 按实际发生顺序排列的步骤，结构见下表。 |
| `lesson` | 可选结尾段落列表。 |
| `sources` | 证据文件名和公开来源 URL 的字符串列表；`C/` 路径只展示为文字，不当作站内链接。 |
| `thumb` | 可选缩略图源路径；省略时从步骤中的图片、对比图或 3D 预览图取第一张。 |

段落列表的每项可以是字符串，也可以是一组字符串（渲染为项目列表）。行内只支持 `` `代码` ``、`**加粗**` 和 `[文字](链接)`。例如题面 `rows` 里的多条要求应写成 `["要做", [["第一条", "第二条"]]]`。

每个步骤至少有 `title`，通常也有 `label`（如“改前”“上游答案”“自动检查”“审计”）和 `text`（段落列表）。可按需要添加：

| 字段 | 内容 |
| --- | --- |
| `figures` | 图片列表：`src`、`caption`，可选 `alt` 和 `zoomable`（默认可打开原图）。`figrow: true` 让多图并排。 |
| `compare` | `before`、`after` 两张图片，及 `before_label`、`after_label`、`caption`。两张图应保持相同裁剪范围、比例和对齐方式。 |
| `model` | `models` 列表，每项有 GLB `src`、静态图 `poster`、`label`、`caption`；可选 `orbit` 和 `alt`。 |
| `checks` | 检查列表，每项有 `id`、`what`、`status`、`note`；`status` 为 `pass`、`fail`、`miss`、`fixed`，可用 `status_label` 写更准确的中文。 |
| `after_text` | 图或表格后的段落列表。 |

叙述区分自动检查、复核、审计和本页重跑的结果。数字注明来源；证据矛盾要写明，不把“没跑”写成“通过”。新题源尚未试做时，直接说明材料和可出的题，不补造模型结果。

图从原生文件生成，caption 先说明是什么，再指出看哪里。图片放 `img/<id>/`；尽量将单张 SVG 控制在 2.5 MB、单个 GLB 控制在 6 MB。案例卡片使用 `make_thumbs.py` 生成的 `thumb.jpg`，详情页保留原图。生成缩略图或 HTML 后，运行静态检查并用浏览器确认交互。
