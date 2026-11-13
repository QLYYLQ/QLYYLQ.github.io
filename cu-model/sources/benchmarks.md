# 长程网页评测候选（2026-10-31 查证）

用途：论文主张是长程任务通过率，Cyrus 要求任务“越长越好”。下面是查到的候选，数字都来自论文原文或官方页面。

## Odysseys（arXiv 2604.24964，ICML 2026）

- 200 个任务（easy 45、medium 46、hard 109），由真实浏览会话改写，每个任务至少跨两个网站，平均涉及 1.9 个 SimilarWeb 类别。
- 在真实互联网上运行；环境是 OSWorld 的 Ubuntu 虚拟机加 Chrome，观察是截图，动作是 pyautogui 式坐标点击、输入、按键、滚动。
- 步数上限 100（附录有 200 步消融）。各模型平均步数：Opus 4.6 81.3、Sonnet 4.6 80.4、GPT-5.4 64.4、GPT-5.4-mini 41.7、Qwen-3.5-9B 78.3、Qwen-3.5-4B 86.4、Qwen-3.5-35B-A3B 86.1、UI-TARS-1.5-7B 76.6。
- 评分：每题中位数 6 条细则（3 到 12，共 1,225 条），每条一次 LLM judge（gemini-3.1-flash-lite-preview）；报细则平均分和全对率。和人工的一致性：细则平均 κ 0.788，全对 κ 0.849。
- 结果（全对 / 细则平均）：Opus 4.6 44.5% / 68.9%，GPT-5.4 33.5% / 55.4%，Sonnet 4.6 31.0% / 49.8%，Qwen-3.5-9B 13.5% / 42.6%，Qwen-3.5-4B 10.7% / 42.9%，GPT-5.4-mini 10.5% / 38.4%，Qwen-3.5-35B-A3B 6.5% / 28.5%，UI-TARS-1.5-7B 1.0% / 10.0%。hard 档 Qwen-3.5-35B-A3B 全对 0.0%。
- 200 步预算下 Opus 4.6 全对从 44.5% 升到 76.5%；Qwen-3.5-9B 几乎不涨，论文归因于能力上限。
- 论文没有报告上下文长度或记忆相关的失败分析，失败归因于规划、跨站一致性和高扇出任务结构。

## WebChoreArena（arXiv 2506.01952）

- 532 个任务，跑在 WebArena 的四个可复现环境上：Shopping 117、Shopping Admin 132、Reddit 91、GitLab 127、跨站 65；117 个模板。
- 三类难点：Massive Memory（大量信息的记忆与检索）、Calculation、Long-Term Memory（跨多个页面保持信息）；66.5% 的任务只属于一类。
- 步数上限 50，论文没给平均步数。
- 451 个任务任意观察形式都能做，69 个只能用文本，12 个必须看截图。
- 结果（Overall）：BrowserGym + Gemini 2.5 Pro 44.9%（同框架 WebArena 59.2%），AgentOccam + Gemini 2.5 Pro 37.8%，BrowserGym + GPT-4o 2.6%。

## Online-Mind2Web（OSU NLP 排行榜）

- 300 个任务，136 个真实网站；按人工所需步数分 Easy 1 到 5、Medium 6 到 10、Hard 11 步以上。
- 自动评测用 WebJudge（推荐 o4-mini），提交另做人工复核。
- 对本项目偏短，适合当短任务对照。

## GTA（ACL 2026 long 856）：11 月 1 日已放弃

- 长任务生成框架：爬取、检索式种子、in-context 生成、自动质检，产出带可执行轨迹的任务；覆盖 50 多个网站（电商、政府、论坛、新闻）。
- 5,000 个站内任务、600 个跨站任务；Browser Use（GPT-4o）站内多在 20% 到 30% 以下，跨站 4.2% 到 12.5%，人类 85%。
- 论文正文没给步数统计。
- 11 月 1 日查 GitHub：只有代码，没有许可证文件，任务没放出来。Cyrus 的标准是论文说的任务或轨迹要能在 HF 或 GitHub 下到，所以不用。替代来源见 `collection_task_sources_20261101.md`。

## 发布情况复核（11 月 1 日）

- Odysseys：GitHub ljang0/Odysseys，`data/odysseys.json` 是 200 个任务，评分细则在每个任务里；评审脚本和转 OSWorld 格式的脚本都在；MIT；没有放轨迹。
- WebChoreArena：GitHub WebChoreArena/WebChoreArena，`BrowserGym/config_files/` 下有 `test_webchore.raw.json`（1,278,600 字节）和按站拆开的五个文件，另有 `small_set_ids.txt`；Kaggle 有镜像；仓库许可证 Apache-2.0。

## Online-Mind2Web 发布情况和用法（11 月 3 日）

- 任务在 HF `osunlp/Online-Mind2Web`：门控数据集，要登录、同意条款并留下联系方式才能下；一个 JSON，97.3 kB；300 个任务，136 个网站；字段是 `task_id`、`website`、`task_description`、`reference_length`（人做完用的步数）；CC BY 4.0，卡片写明只为研究发布。没有放智能体轨迹；GitHub 仓库 OSU-NLP-Group/Online-Mind2Web 放了人工评测标签（`human_label.json`）和 WebJudge 的结果，代码 MIT。
- Cyrus 11 月 3 日定：加进来当短任务对照，它的网址和任务也进采集（可以换任务）。进过采集的网站不能再当评测，所以报告建议按网站留出约三分之一不采，对照只在这部分上报。
- 来源：https://huggingface.co/datasets/osunlp/Online-Mind2Web ，https://github.com/OSU-NLP-Group/Online-Mind2Web

## 来源

- Odysseys: https://arxiv.org/pdf/2604.24964 ，https://icml.cc/virtual/2026/67951
- WebChoreArena: https://arxiv.org/abs/2506.01952v1 ，https://arxiv.org/pdf/2506.01952
- Online-Mind2Web: https://huggingface.co/spaces/osunlp/Online_Mind2Web_Leaderboard/blame/main/content.py
- GTA: https://arxiv.org/abs/2605.29218 ，https://aclanthology.org/2026.acl-long.856.pdf
- Odysseys 发布：https://github.com/ljang0/Odysseys
- WebChoreArena 发布：https://github.com/WebChoreArena/WebChoreArena ，https://api.github.com/repos/WebChoreArena/WebChoreArena/contents/BrowserGym/config_files
