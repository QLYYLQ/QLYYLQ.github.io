# OLMo-3-7B RL-Zero 训练动力学：最终报告与数据

先打开 `FINAL_REPORT.html`。它是离线单文件，图已内嵌，正文里的证据链接指向本目录下的数据文件，在本目录中打开即可点开。`FINAL_REPORT.md` 是同一份报告的 Markdown 版。

| 路径 | 内容 |
|---|---|
| `FINAL_REPORT.html`、`FINAL_REPORT.md` | 最终报告 |
| `figures/` | 报告中的图（PNG，部分附 PDF 与 SVG）；`figures/data/` 是各图的数值表 |
| `data/inputs/` | 评测题目：8 个 benchmark 与 AIME |
| `data/weight_geometry/` | 权重几何：逐层逐投影的轨迹与谱统计（`K4096/`）、派生结果（`derived/`）、bf16 阈值扫描（`bf16_eta/`）、OFT 随机对照面板（`oft_null/`） |
| `data/extrapolation/` | 外推 checkpoint 的逐层重构误差与 PCA-Q 外推的权重差 |
| `data/functional/` | 功能评测的逐 cell 聚合与逐题结果：AIME 外推网格、89×8 网格、Code 16×8、标准 MBPP、MMLU true pass@1、Code AIME、PCA-Q 配对、8,192-token 预算、评分口径对照 |
| `data/runtime_geometry/` | 推理隐状态几何：89×8 网格（m448）、m-grid、short128、Code 16×8、标准 MBPP、AIME（m2048）、Code 与标准 MBPP 的同窗关联、T1 |
| `data/continuation/` | 两条密集续训的协议、运行快照、逐 update 一致性检查、checkpoint 发布记录、训练批次正确率与 bf16 抽样 |
| `code/` | 分析、评测、几何前向（含按层 RoPE 模块）与续训统计的代码；续训的训练代码在 codelab 的 `my_rl_job` 目录（`$REMOTE_HOME/my_rl_job/`），不在包内 |
| `DATA_DICTIONARY.md` | 各数据目录的内容、label 命名、字段与口径 |
| `MANIFEST.tsv`、`SHA256SUMS` | 每个文件的相对路径、字节数与 SHA-256 |

包内没有生成全文（97.45 GB）、SVD 因子（约 2.95 TB）和模型权重。cell 聚合文件里的 `ckpt` 与 `samples_file` 字段记录了权重与生成全文在共享存储上的位置，报告第 11 节也列出了这些数据的位置。

在本目录运行 `shasum -a 256 -c SHA256SUMS`（macOS）或 `sha256sum -c SHA256SUMS`（Linux）可以核对所有文件，结果应全部为 OK。
