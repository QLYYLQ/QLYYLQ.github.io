# 采集任务来源核查（2026-11-01）

标准（Cyrus 11 月 1 日）：论文里声称的数据、任务或轨迹能在 Hugging Face 或 GitHub 上下到，才算可执行；只放代码的不算。下面每一项都对照了论文说法和实际发布的内容。查的是 HF 数据集页、HF datasets-server 的统计接口、GitHub 页面和 GitHub API 的目录列表，都在 11 月 1 日。

一共核了 12 个采集来源：过关 5 个，没过关 5 个，不合适 2 个；另有 WebWorld 归到相关工作。作为参照：我们 10 月 28 日试采平均每条 15.6 步；Odysseys 上各模型平均 42 到 86 步。

## 过关的来源

| 来源 | 论文说法 | 实际能下到的 | 许可 | 对我们的用处和问题 |
|---|---|---|---|---|
| WebChain（arXiv 2603.05295） | 31,725 条人工轨迹、31.8 万步 | HF webagentlab/WebChain：清洗后 31,675 条、317,682 步；视口和整页截图、DOM、动作和坐标；公开，不用申请 | CC BY 4.0 | 真人在真实网站上完成的任务和轨迹，428 个域名；平均约 10 步、1.07 分钟（论文对清洗前全量的统计），偏短 |
| WebSTAR（arXiv 2512.10962，ACL 2026） | 1,326 个查询、13,338 条成功轨迹、10 万个打过分的步 | HF microsoft/WebSTAR：63.8 GB，截图和轨迹分卷压缩；卡片没写条数 | CDLA-Permissive-2.0 | 每步有 1 到 10 分的评审分，可以做步级筛选；轨迹由 OpenAI computer-use-preview 在真实网站上跑出，拿来训练前要看 OpenAI 的使用条款。步数口径对不上：表 8 写平均 22.1 步，表 2 却说成功轨迹一共 9.7 万步（约每条 7.3 步），论文没解释 |
| AgentNet（OpenCUA，arXiv 2508.09123） | 22,625 条人工任务（Windows 12K、macOS 5K、Ubuntu 5K），平均 18.6 步 | HF xlangai/AgentNet：200 GB，meta_data_merged.jsonl 加分卷 images.zip；有截图、pyautogui 动作和反思式思考；数据查看器读不出行数 | MIT | 桌面任务，含浏览器操作；动作空间和 Odysseys（OSWorld 加 pyautogui）一致，适合训整屏底座 |
| InSTA（arXiv 2502.06776） | 15 万个站点的任务；另称有 220 万张截图、220 万条动作轨迹、15 万条评审记录 | HF data-for-agents/insta-150k-v1、v2、v3 都只有任务。论文指定的官方版 v2 有 146,746 行，字段只有 domain 和 task；v3 加了计划步骤和成功标准 | MIT | 站点覆盖最广的任务池，但任务短：v3 训练集（143,508 行）计划步骤平均 4.74、中位数 5、最多 43，八成在 6 步以内；成功标准平均 3.05 条。截图和轨迹没有放出 |
| VeriWeb（原名 VeriGUI，arXiv 2508.04026） | 302 个长链信息检索任务，平均 4.3 个子任务；人工演示平均每个任务 272.5 步、每个子任务 63.5 步 | HF 2077AIDataFoundation/VeriGUI 和 GitHub VeriGUI-Team/VeriWeb：302 个任务的完整人工演示（data.json 加录屏），共 86.2 GB；任务、子任务和答案在查看器里能看到 | Apache-2.0 | 唯一放出完整演示的长任务集；量小，论文定位是评测，没有训练和测试划分；任务偏研究检索，一次标注 1 到 2 小时 |

## 没过关或不合适的来源

| 来源 | 问题 |
|---|---|
| GTA（ACL 2026） | 只有代码，仓库没有许可证文件，任务没放出（已放弃） |
| Explorer（arXiv 2502.11357） | 论文称有 9.4 万条成功轨迹（平均 7.7 步），正文没有发布声明，HF 上也找不到 |
| Fara-7B 的 FaraGen | 论文称有 145,603 条轨迹（平均 6.9 步），只放了权重和 609 个任务的 WebTailBench，训练轨迹没放 |
| AgentTrek（arXiv 2412.09605） | HF 上只有一个 1.81 GB 的文本 JSON（52,594 轮对话），页面没写许可证，也看不到截图 |
| NNetNav-live | HF 上有 53,709 行（Apache-2.0），但只是文本格式的训练对话，卡片是空的，没有截图 |
| WebLINX | 对话式导航，有指导者参与，和我们一条指令做到底的设定不同 |
| Multimodal-Mind2Web（HF osunlp/Multimodal-Mind2Web） | 能下到（训练集 1,009 个任务、7,775 个动作），但都是 2023 年录的离线快照短任务，平均约 7.7 步 |
| 采自 WebArena 四个站的数据 | WebChoreArena 用的就是这四个站，拿来训练会污染第二套评测 |

## 评测集按同一标准复核

- Odysseys：GitHub ljang0/Odysseys，data/odysseys.json 里是 200 个任务（easy 45、medium 46、hard 109），评分细则写在每个任务里；评审脚本和转 OSWorld 格式的脚本都在；MIT。没有放轨迹，评审要我们自己提供运行记录。
- WebChoreArena：GitHub WebChoreArena/WebChoreArena，BrowserGym/config_files 下有 test_webchore.raw.json（1.28 MB）和按站拆开的 test_shopping、test_shopping_admin、test_reddit、test_gitlab、test_cross，还有子集清单 small_set_ids.txt；Kaggle 上有镜像；仓库许可证 Apache-2.0。

## 相关工作（不当采集来源）

WebWorld（Qwen，arXiv 2602.14721）是网页世界模型：给定当前页面和动作，预测下一页的文本状态（A11y 树、HTML 等），不预测截图。数据在 HF Qwen/WebWorldData，卡片写 1,059,348 条轨迹，查看器估计 462,645 行，两者对不上；Apache-2.0。和我们“界面可预测”的主张直接相关，论文的相关工作里要提。

## 建议的用法（推断，没有实验支撑）

- 整屏底座：AgentNet、WebChain 和 WebSTAR（只用评审分 7 分以上的步算损失）合起来训整屏底座。
- 采集任务：WebChain 的任务（真人做完过，确认可行）和 InSTA 的任务（站点多）当种子，在同站或跨站串成 3 到 6 段的长任务，后一段要用前一段读到的值。InSTA 自带的成功标准可以直接当分段判据。串任务是我们自己的步骤，长度和可行率要在试采里量。
- 长演示：VeriWeb 的人工演示可以直接用来做上下文腐烂预测试；也可以拆成大约 1,300 个子任务（302 × 4.3，估算）当中长任务。
- 站点过滤：从 data/odysseys.json 里抽出 Odysseys 用到的域名，采集任务和底座数据都去掉这些站；WebArena 系列的任务和轨迹都不用。

## 11 月 3 日补充

- Online-Mind2Web 按同一标准过关：300 个任务、136 个网站，在 HF `osunlp/Online-Mind2Web` 能下（门控，同意条款后下载，CC BY 4.0），只有网址、任务描述和人做完用的步数，没有轨迹。细节记在 `eval_benchmarks_20261031.md` 的同日小节。
- Cyrus 定的用法：上面过关的来源，加上 Online-Mind2Web 和 VeriWeb，任务和网址都拿来多造数据，不只照原任务跑：在不同的步上分叉、同一网址换任务、串长任务，多出相似布局的数据。VeriWeb 不再当评测。
- 报告里的倾向（还没定）：Online-Mind2Web 按网站留出约三分之一不采，做短任务对照；VeriWeb 留 10 到 20 条任务不采，用来测更长历史上的上下文衰减。Odysseys 的域名和 WebArena 四个站照旧不采。

## 来源

- WebChain：https://huggingface.co/datasets/webagentlab/WebChain ，https://arxiv.org/abs/2603.05295
- WebSTAR：https://huggingface.co/datasets/microsoft/WebSTAR ，https://arxiv.org/html/2512.10962v2
- AgentNet：https://huggingface.co/datasets/xlangai/AgentNet ，https://arxiv.org/html/2508.09123v3
- InSTA：https://huggingface.co/datasets/data-for-agents/insta-150k-v2 ，https://huggingface.co/datasets/data-for-agents/insta-150k-v3 ，https://arxiv.org/html/2502.06776v2 ，统计接口 https://datasets-server.huggingface.co/statistics?dataset=data-for-agents/insta-150k-v3&config=default&split=train
- VeriWeb：https://huggingface.co/datasets/2077AIDataFoundation/VeriGUI ，https://github.com/VeriGUI-Team/VeriWeb ，https://arxiv.org/pdf/2508.04026
- Explorer：https://arxiv.org/html/2502.11357v4
- Fara-7B：https://www.microsoft.com/en-us/research/wp-content/uploads/2025/11/Fara-7B-An-Efficient-Agentic-Model-for-Computer-Use.pdf
- AgentTrek：https://huggingface.co/datasets/xlangai/AgentTrek
- NNetNav-live：https://huggingface.co/datasets/stanfordnlp/nnetnav-live
- Odysseys：https://github.com/ljang0/Odysseys
- Online-Mind2Web：https://huggingface.co/datasets/osunlp/Online-Mind2Web ，https://github.com/OSU-NLP-Group/Online-Mind2Web
- WebChoreArena：https://github.com/WebChoreArena/WebChoreArena ，https://api.github.com/repos/WebChoreArena/WebChoreArena/contents/BrowserGym/config_files
- WebWorld：https://huggingface.co/Qwen/WebWorld-32B ，https://huggingface.co/datasets/Qwen/WebWorldData
