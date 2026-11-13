# 数据构建可能性指南：用 spectragent 采什么、怎么采、怎么扩，以及 latent action 放在哪

2026-10-27。这份指南回答三个问题：要采哪些数据，在 spectragent 里一轮怎么采，怎么扩到全量 SFT 需要的量；另外评估 LAR（Latent Action Reparameterization）的思路能不能用在浏览器动作上。第 7 节是开工清单，照着做就能开始下一轮。

依据：GitHub `QLYYLQ/spectragent` 的 main（`380060f`，10 月 27 日拉取）里的 `docs/data_flywheel_runbook.md`（下称 runbook）、`lookahead/README.md`、`configs/lookahead/`、导出和 lookahead 的代码，以及项目历史 `.agents/skills/af-project-history/references/lookahead-rounds.md`（下称轮次记录）；之前的四份报告，简称原报告（《CUA SFT 数据管线与扩展调研》）、设计文档（《前瞻观察能力的训练管线与数据设计》）、采集评估（《spectragent 采集框架用于前瞻观察训练的评估》）、数据量估算（《全量 SFT 数据量估算》）；LAR 原文（arXiv 2605.18597v3）。脚本和示例在同目录的 `数据构建可能性指南_notes/`（下称 `_notes/`，文件列表见附 B）。不熟的词见附 A。

*标注沿用前几份报告：**论文报告**是论文或官方文档里能核对的；**项目数据**是仓库文档、配置、代码、轮次记录或你实跑里的数，我读代码得出的结论也归这一类；**本文实测**是这次我自己跑出来的（分词计数、任务加载、脚本在 fixture 演练产出上的试跑），只说明跑过的那部分；**推断**是由证据算出或推出的；**直觉**是没有直接证据的判断，附当时的想法；**建议**是具体做法。*

## 结论

1. **一轮怎么采的流程已经定了，下一轮在当前 main 上重录。** runbook 的“配置指南 101”和 `configs/lookahead/` 就是 10 月 24 日那轮实际跑的配置，命令在 `lookahead/README.md`（**项目数据**）。10 月 25 日所有原始录制和分叉都删了；10 月 24–25 日的三处改动（一步里有动作失败就停下，`send_keys` 执行浏览器自己的快捷键，页面没加载完时明确告诉 teacher）都改了 teacher 的提示词，旧录制本来也不能再按源历史分叉。所以下一轮换快网络、在当前 main 上重录。几项已合并的设置还没在一整轮上验证，这一轮顺手比（第 3.4 节）；导出有四个坑，靠改导出配置和一个后处理脚本解决（第 3.5 节）。
2. **数据分五族（A–E），计数单位各不相同。** A 录制轨迹按保留轨迹和监督步算；B 同任务分叉和 C 换任务分叉按可用决定算（judge 判为合理、且执行效果符合意图的决定）；D 前瞻观察按 transition 算，失败轨迹里的也能用；E 人工标注按条算，留出评测按站点和任务算。混在一起按“条”数，量会算错（**推断**，第 2 节）。
3. **扩量的数据瓶颈在任务和站点。** 数据量估算的推荐档要 ≥6,000 个任务、≥100 个训练站点（那份报告的**直觉**），上一轮是 15 个任务、5 个站点：任务差约 400 倍，站点差约 20 倍。自己写的任务文件能被 `spectragent bench --list` 原样列出（**本文实测**，没有真录），所以模板任务、以及把 variants 写成从检查点页面出发的新任务，都能接进录制（第 5 节）。吞吐的上限另外算：teacher API 限流、风控、一台机器能同时录几个站点，三样都没在扩量规模上量过。
4. **分叉不适合拿来凑 SFT 的量。** 分叉的一次决定和录制的一步一样带着全部历史：上一轮录制每步约 1.4 万 token，同任务分叉每个约 1.4 万，换任务约 1.6 万。10 月 24 日那轮，按意图执行的同任务分叉只占全部同任务分叉的 30%，换任务是 50%。折到每个可用决定，换任务分叉约为录制的 1.8 倍，同任务分叉约 2.5 倍（**推断**；分叉一侧算的是下限，录制一侧的 65% 保留率是**直觉**）。分叉的用处是同一状态的多个决定、换任务、不碰 live 站点，只拿来做这几类数据（第 4 节）。你说的视频区域隔离（媒体区域规则）让腾讯视频的分叉从一个都恢复不了变成 40/70 可评判，整轮可评判的比例到 69%，再补站点规则重跑到 75%（**项目数据**）。
5. **LAR 论文存在，NeurIPS 2026 录用没查到。** 它是 arXiv 2605.18597（v3，2026-09-27），在 ICLR 2026 MemAgents workshop 挂过 poster；PDF 附了 NeurIPS 的 checklist，我推断作者按 NeurIPS 准备过，投没投、录没录都查不到（**推断**）。它的 latent action 是从轨迹里挖出的高频 n-gram 片段，每类片段加一个新词表符号，再用 KL 蒸馏让模型学会；三个基准的输入都是文本或 HTML。唯一的网页基准 Mind2Web 上，Qwen3-8B 的动作 token 只少了 2.9%，Llama-3.1-8B 少了 20.8%（**论文报告**，第 6.1 节）。
6. **照搬到 click、drag、scroll 上省得很少。** 这些动作能预见的是语法，坐标才是决定，n-gram 压不掉坐标。用 Qwen 的分词表数，一个 UI-TARS click 15 个 token，其中 9 个是语法（**本文实测**）。语法和低熵的整行（scroll、hotkey）都换成宏符号，每步省 6–20 个 token，按 250 tok/s 是 25–80 ms（**推断**，第 6.2 节）。少一次 `wait()` 就省 1 秒，少一次模型调用约省 1 秒，抵得上十几到几十步的宏符号（**推断**）。
7. **LAR“缩短有效步数”的思路可以借，换一个单位用。** LAR 的有效步数按动作 token 数算；我把它延伸到模型调用次数，这一步是我的**推断**，论文没有做。浏览器上对应的是多动作 chunk：用录制里每个动作前的帧给 chunk 打“盲操作是否安全”的标签，把能合并的相邻步合成更长的 chunk 当 SFT 目标；转移类型（跳页、原地更新、弹窗、滚动露出）可以做成离散 token，和 `<predict>` 一起训。这三样都是**推断**和**直觉**，先用 `_notes/` 的两个脚本在第一次导出和 `steps.jsonl` 上量出 token 构成和可合并步的比例再定（第 6.4 节）。

## 1. 总图：数据从哪来，变成什么

```text
任务来源 ─► 录制（live；teacher = ui_tars + DeepSeek） ─► health 排除 ─► 分叉（离线回放录下的归档）
基准 / 模板 / variants / 探索       │                                        │
                                   ▼                                        ▼
                            A 录制轨迹                           B 同任务分叉   C 换任务分叉
                                   │                                        │
                                   ├──► 审核队列：stability / judge-forks / gold-queue ──► E 人工标注
                                   │
                                   ├──► export（openai_messages，每步一条，带 weight）
                                   │        └─► 外部后处理：排除坏录制、按 judge 筛分叉、整条打包、合并步 ──► SFT
                                   │
                                   └──► extract（steps.jsonl）──► 外部离线管线 ──► D 前瞻观察行（设计文档数据①②③⑤⑥）
```

后处理和离线管线都放在 spectragent 外面，这是你 10 月 21 日定的（**项目数据**）。导出代码已经冻结，唯一的例外是 10 月 25 日加的 `wait_actions`（runbook “导出 SFT 数据”）。

## 2. 要什么数据

### 2.1 清单

| 族 | 数据 | 训什么 | 在 spectragent 里从哪来 | 计数单位 | 现状 |
|---|---|---|---|---|---|
| A | 录制轨迹 | 策略 SFT 的主体 | `spectragent bench` 录制 | 保留轨迹、监督步 | 能产出、能导出 |
| B | 同任务分叉 | 同一状态的多个决定：多样性、决定稳不稳、偏好对 | `branch_same_task.yaml` | 可用决定 | 能产出；和导出一起用没在真实数据上验证（第 3.5 节） |
| C | 换任务分叉 | 同一屏、不同需求：任务条件化（设计文档数据④） | `lookahead variants` 加 `branch_task_variants.yaml` | 可用决定 | 同 B |
| D | 前瞻观察 transition | `<predict>`（设计文档的 P1、P2） | 录制里的帧、DOM/AX、落定记录、动作效果；`lookahead extract` | transition | 原料已经在录，离线管线没写 |
| E | 人工标注、留出评测 | 校准阈值和 judge、金标（设计文档数据⑧）、测泛化 | `stability`、`judge-forks`、`gold-queue` 三类队列，`spectragent view` 标注 | 条；留出站点 × 任务 | 队列能建，标注流程没完整走过 |

另有两类不在 spectragent 里：通用数据，**建议**占整条打包时总训练 token 的约 30%，推荐档约 1 亿 token（数据量估算第 4 节，参照 OpenCUA 的配比）；和 latent action 有关的派生数据，见第 6.4 节。

### 2.2 每族怎么筛

- **A 录制轨迹**：按步筛，不按整条。teacher 没完成的轨迹也导出，每个样本带 `labels.step_status` 和判定，训练前再筛（runbook “导出 SFT 数据”）。WebSTAR 的实验里，步级过滤随数据增加一直在涨，轨迹级过滤很早就平了（**论文报告**，见数据量估算第 2 节）。要丢的：健康检查排除的整条录制（导出器不读排除文件，要在外部丢，第 3.5 节）；主文档没加载完的步（`exclude_unloaded_steps`，默认开）；动作失败的步（`step_status: action_failed`）；风控拦截页上的步（只能翻截图找）。首轮那个“没聚焦也报输入成功”的 bug，10 月 22 日那轮之前已经修了，没有聚焦的输入框时拒绝输入；修之前的录制也已删除（**项目数据**）。
- **B、C 分叉**：只要 `judge-forks` 判为 `judged` 的（检查点恢复了、分叉做出了决定），再要 judge 的两个回答都是 yes：`reasonable`（这一步对它的任务合理）和 `executed_as_intended`（下一屏显示了想要的效果）。导出时，同一组里检查点动作相同的样本标 `duplicate_of`，不删（runbook）；做偏好对和多样性统计时要用它。
- **D transition**：不要求任务成功，只要求 O_{t+1} 是真实的下一屏、帧已经稳定、证据和任务相关。失败轨迹里的 transition 也能用（原报告“扩展曲线”一节）。
- **E 人工**：稳定性审核用来定变化阈值，分叉判定审核用来核对 judge，金标 100 条起，calibration 和 test 各一半（设计文档）。

### 2.3 录制时就要存下的东西

D 和第 6 节的派生数据都靠录制时多存的东西，事后补不回来。下面这些在 `configs/lookahead/record_ui_tars_deepseek.yaml` 里已经开着，扩量时不要为了省磁盘关掉（**项目数据**，runbook “归档”；**建议**）：

- `browser.frames`：每个动作之前一帧（`before_action: true`），观测后约 1 秒一帧（`after_observation_delay_s: 1.0`）。帧让每个动作通常多等约 0.07 秒，agent 看不到这些帧。
- `browser.dom_raw`（DOMSnapshot 加 AX）、`browser.network`、`browser.storage`。
- `recording` 四项（metrics、errors、trajectory、observations）全开。`recording.metrics` 关着时不记动作起止时间，`pace: recorded_timeline` 会拒绝这样的源。
- 每步的 `capture_state`（落定结果、可见资源加载失败数、前台变化），每个动作的效果（点击点和命中元素、滚动前后、URL 前后、焦点）。

磁盘按每步约 4.5 MB 算：采集评估里实跑每步 p50 约 3.0 MB，首轮每步多拍约 3 帧，每帧按约 0.5 MB 算（1280×720 的 PNG，**推断**）。

## 3. 一轮怎么采

### 3.1 开跑前

照 runbook 的“录制前准备”。下面几条最容易出事（**项目数据**，另有标注的除外）：

- 换快网络。上一轮在慢网络上，约三分之二的采集等到了落定，约三分之一被 5 秒上限截断（多数只是 DOM 还在变），约 3% 截断时主文档还没加载完；离线回放瞬间应答，录到的“正在加载”在分叉里永远对不上。换好网络先录一两个任务，用 `lookahead extract` 写出的 `settle` 字段看一眼：`outcome` 是 `capped` 且 `waiting_for` 里有 `load` 的采集，就是截断时主文档还没加载完的，应接近 0（**建议**）。
- 一台机器同时最多录 3 个站点。5 个并行时页面下载被饿死，爱奇艺首页停在骨架屏。这是慢网络上量的，快网络上能开几个没量过。
- 整轮固定宿主的深色或浅色外观。headless Chrome 的原生滚动条跟随宿主外观，又不被记录，曾让一批分叉作废。runbook 的例子是一直用深色：开跑前 `defaults read -g AppleInterfaceStyle` 输出 `Dark`。
- `max_actions_per_step` 在录制、分叉、学生里都是 4。DeepSeek teacher 用 `coordinate_space: screenshot_pixels`，学生照旧 `normalized_1000`，导出时换算。
- teacher 的提示词一改就要重录，因为 `history_source: source` 的分叉要求前缀的提示逐字节相同。下一轮 teacher 走哪条 API 路由，runbook 写着还没定。
- `spectragent bench` 不读 `.env`，先 `set -a; . ./.env; set +a`。teacher 和 judge 不是同一家服务时，在 judge 那条命令前单独给 `OPENAI_API_KEY`。LexBench 等基准数据的位置用 `SPECTRAGENT_BENCHMARK_DATA` 指定。

### 3.2 命令

`lookahead/README.md` 的 “A collection round” 原样能跑。下面照抄，加了注释、`--token-limit` 和导出两步。`$R` 是这一轮的目录，`$N` 是 `_notes/` 目录：

```bash
set -a; . ./.env; set +a                  # bench 只读 shell 环境
R=tmp/lookahead/<轮次名>
N=$LOCAL_HOME/QLY/report/cu_model/数据构建可能性指南_notes
mkdir -p $R/{configs,logs,sessions}
cp configs/lookahead/*.yaml $R/configs/
sed -i '' "s|tmp/lookahead/round|$R|g" $R/configs/*.yaml   # Linux 的 GNU sed 写 -i，不带 ''

# 1 录制：每个站点一个 sweep，同时最多 3 个站点。下面是上一轮 B 站的三个任务
uv run spectragent bench --config $R/configs/record_ui_tars_deepseek.yaml \
  --benchmark lexbench_browser --subset L1 --task-id 6 --task-id 118 --task-id 158 \
  --no-eval --timeout 1800 --token-limit 1800000 \
  --session-dir $R/sessions/bilibili > $R/logs/record-bilibili.log 2>&1
# 2 健康检查：写 exclusions.json。分叉配置的 exclude_runs 和之后的 lookahead 命令都读它，导出不读（见 3.5）
uv run python -m lookahead health --root $R/record --viewer-root $R --out $R/out/health

# 3 换任务的变体：每条录制取 2 个检查点，每点 2 个新任务
uv run python -m lookahead variants --root $R/record --viewer-root $R \
  --exclude-runs $R/out/health/exclusions.json --steps-per-run 2 --per-step 2 \
  --judge-config $R/configs/judge_deepseek.yaml --out $R/variants/variants.json
# 4 三组分叉：先 --list 看任务 id。量大时把 id 分成几份，每个进程用 --task-id 传一份、用自己的 --session-dir
for c in branch_same_task branch_task_variants branch_task_variants_without_source_thoughts; do
  uv run spectragent bench --config $R/configs/$c.yaml --no-eval --list
  uv run spectragent bench --config $R/configs/$c.yaml --no-eval --timeout 1500 \
    --session-dir $R/sessions/$c > $R/logs/$c.log 2>&1
done

# 5 steps.jsonl 和三类审核队列
uv run python -m lookahead extract --root $R --viewer-root $R \
  --exclude-runs $R/out/health/exclusions.json --out $R/out/steps.jsonl
X="--viewer-root $R --exclude-runs $R/out/health/exclusions.json --annotations $R/annotations"
uv run python -m lookahead stability --root $R/record $X --out $R/out/stability \
  --media-areas configs/replay_rules
uv run python -m lookahead judge-forks --root $R $X --out $R/out/forks \
  --judge-config $R/configs/judge_deepseek.yaml
uv run python -m lookahead gold-queue --root $R/record $X --n 100 --out $R/out/gold
# 6 标注
uv run spectragent view --root $R --annotations $R/annotations --annotator <名字> --open

# 7 导出（导出 YAML 见 3.5）和外部后处理
uv run spectragent export --config $R/configs/export.yaml
python3 -I $N/export_postprocess.py --export datasets/<名字> --out datasets/<名字>_post \
  --exclusions $R/out/health/exclusions.json --judgments $R/out/forks/judgments.jsonl   # 整条打包再加 --pack
```

上一轮各站点的 LexBench L1 任务 id：B 站 6、118、158，IGN 25、125、155，腾讯视频 28、128、263，爱奇艺 18、108、208，同花顺 44、134、233（README）。

`--token-limit` 是这次 sweep 记下的 token 上限：每跑完一个任务累加一次，累计到了上限就不再开新任务，退出码 4（**项目数据**，`spectragent bench --help`）。所以一次 sweep 最多超出最后那个任务的量。bench 不会自动跳过已经跑过的任务；要续跑，看 `--session-dir` 里这次的 session 文件，状态还是 `not_started` 的任务用 `--task-id` 再跑（**项目数据**，读了 `spectragent/core/benchmark_session.py`）。上一轮录制 580 万 token、15 个任务，每个任务约 39 万；上面按每个任务 60 万（留五成余量）乘 3 个任务给了 180 万（**建议**）。分叉的 sweep 也可以加。

### 3.3 跑完先看什么

- 翻截图。健康检查认不出风控拦截页，携程那轮就是翻截图才发现几乎全是拦截页（**项目数据**）。新站点至少翻每条录制的第一张和最后一张，拦截多的站整站丢掉。也可以让 judge 模型看这两张截图判断是不是拦截页，没试过（**直觉**）。
- 各站点可评判分叉的比例。10 月 24 日那轮补规则重跑之前：同花顺 58/68、B 站 52/56、IGN 42/64、腾讯视频 40/70、爱奇艺 37/72（**项目数据**）。哪个站掉下来，就看度量报告里的近邻 miss，补站点规则，只改 `site_rules`，在同一批录制上重跑分叉对比（runbook “回放与分叉”）。度量报告这样算：建一个目录，`traces/record` 链到 `$R/record`，`traces/branch` 里放分叉 run 的符号链接，再跑 `spectragent flywheel report --root <目录> --evidence live --out <输出目录>`（runbook “排错”）。
- 这一轮的 token 账：录制、同任务分叉、换任务分叉、变体生成、评判各多少。

### 3.4 下一轮顺手要比的

这些设置都已合并，还没在真实的一整轮上验证过（runbook “已知不行与还没验证的”）：

- `pace: recorded_timeline` 对 `recorded_llm_latency`：在同一批分叉上各跑一遍，比各站点可评判分叉的比例。离线加载快得多，分叉走到检查点时比录制当时早（按站点的中位数 3 到 35 秒），轮播、自动预告、弹窗这些页面计时器处在别的状态，这是剩下的失败的主要来源之一。
- 导出的 `wait_actions: drop_when_capped`，配一个真的改写模型（runbook 的例子是 `gpt-4.1-mini`）。上一轮约十分之一的步会受影响，只在 fixture 上测过。
- `send_keys` 执行浏览器自己的快捷键以后，teacher 离站卡住是不是变少了。上一轮因为离站丢了 23 个分叉。

### 3.5 导出的四个坑

一轮的 trace 在 `$R/record/` 和三个分叉目录下（各配置的 `trace_dir`）。导出 YAML 从发布的 `configs/flywheel/export_sft.yaml` 复制，其余照旧，改这几处：

```yaml
exporter:
  - exporter_id: openai_messages
    # ……其余照发布配置……
    sources_root: tmp/lookahead/<轮次名>
    sources: ["record/*", "branch_same_task/*", "branch_task_variants/*",
              "branch_task_variants_without_source_thoughts/*"]
    filters:
      exclude_restoration_diverged: false   # 坑 1
      max_document_misses: unlimited        # 坑 1
      exclude_sites: [<留出站点的注册域名>]   # 坑 3
    split: { by: task, validation_fraction: 0.1, salt: af-split-1 }   # 坑 3
    decontamination: { against: [<将来评测用的基准>], match: either }
    output_dir: datasets/<名字>
```

`match: either` 是说任务 id 相同、或者站点加指令相同，任一条就算撞上评测集（runbook）。

分叉 run 的源录制也必须在 `sources` 里，否则分叉会被筛掉；录制 run 自己也会出样本，没有只导出分叉的开关（runbook）。

1. **分叉多半会被整条排除。** 发布配置的 `exclude_restoration_diverged: true` 会把任何一步恢复检查判为 `warn` 或 `diverged` 的 run 整个排除，而分叉用 `verify: warn` 跑，前缀里常有没过的步。`max_document_misses: 0` 还会排除回放里有主文档 miss 的 run：fixture 演练故意做了一个提交 POST 表单的分叉，它就因为一次主文档 miss 被这条排除了（**本文实测**）。这两项和分叉还没在真实数据上一起导出过（runbook）。**建议**导出时设成上面的值，再用 `export_postprocess.py --judgments` 只留 `judge-forks` 判为 `judged`、两个回答都是 yes 的分叉；它拿导出样本的 `run_id` 去对 `judgments.jsonl` 的 `branch_run_id`。这样做是**推断**：分叉样本的目标是检查点上的新决定，前缀里没过的检查只在影响检查点画面时才要紧，而 `judge-forks` 只评判检查点画面恢复了的分叉。第一次导出时抽几条看检查点画面。
2. **导出器不读健康检查的排除文件。** 导出 YAML 没有按 run 排除的选项，`exclusions.json` 只有分叉的任务加载器和 lookahead 的几个命令读（**项目数据**，读了 `spectragent/export/settings.py` 和 README 的 health 一节）。不处理的话，页面一直没渲染出来的坏录制会进训练集。`export_postprocess.py --exclusions` 按 run id 把它们丢掉。
3. **按站点切分用的是完整主机名。** `split.by: site` 的键是起始 URL 的 hostname，`search.bilibili.com` 和 `www.bilibili.com` 是两个键（**项目数据**，读了 `spectragent/core/trace/sources.py` 的 `TaskIdentity.site`）。variants 变来的任务从检查点的深链接出发，主机名五花八门，按站点切会让同一个站跨进 train 和 validation。**建议**用 `split.by: task`，validation 只用来看站内的 loss；跨站泛化交给留出的站点测，它们用 `exclude_sites` 写注册域名（如 `bilibili.com`），按后缀匹配，能盖住子域名。
4. **整条打包要在外部做。** 导出器每步一条记录、带完整前文，之前的助手轮权重 0。推理保留完整历史时，整条打包的训练 token 约为按步展开的 1/7；这是数据量估算第 1 节按每条 20 步、留下 13 个监督步算的**推断**，步数越多差得越大，29 步时约 1/10。`export_postprocess.py --pack` 对每条 run 的每一段（导出器在不可译的步处把一条 run 断成几段）取最后一个监督步的记录，把监督步的助手轮权重设成 1、其余设成 0；这条记录导出器已经核过长度。分叉每条只有一个样本，打包前后一样。

`export_postprocess.py` 默认还会丢掉 `step_status` 不是 `ok` 的样本。它在 fixture 演练的真实导出上跑通了排除、筛分叉和打包，用的排除名单和 judge 结果是我手写的（**本文实测**）。

## 4. 产出和成本

### 4.1 一轮的实测数

10 月 24 日那轮：15 个 LexBench L1 任务，同花顺、爱奇艺、B 站、IGN、腾讯视频各 3 个；teacher 是 `deepseek-v4.1-flash-1017`，reasoning high（**项目数据**，轮次记录）。“可评判”指分叉的检查点画面恢复了，它的决定才能评判。

| 项 | 数 |
|---|---|
| 分叉 | 330：同任务 210、换任务 60、换任务且去掉源思考 60 |
| 可评判 | 229/330（69%）；只补站点规则、在同一批录制上重跑后 246/330（75%） |
| judge：同任务分叉（229 那次） | 可评判的 137 个里，合理 119，按意图执行 64 |
| judge：换任务分叉（229 那次） | 可评判的 92 个里，合理 83，按意图执行 60 |
| 规则和 judge 是否一致 | 同任务分叉上，两边对“意图是否相同”都下了结论时一致 58%；不一致的里有 39 个是规则判“不同”、judge 判“意图相同” |
| token | 共 1,168 万：录制 580 万，同任务分叉 295 万，换任务分叉 197 万，变体生成 6 万，评判 89 万（各项是四舍五入后的数） |
| 每次决定 | 录制每步约 1.4 万输入 token（轮次记录）；同任务分叉每个约 1.4 万（295 万 ÷ 210），换任务约 1.6 万（197 万 ÷ 120）；都带着全部历史 |

这里的规则是 `judge-forks` 的规则判定：比较分叉和源 run 在检查点上的动作（点中的元素、输入的文字、下一页的 URL），只在证据强时判“相同”或“不同”；judge 模型另外回答两者是否意图相同（README）。两边一致得少，所以 runbook 说规则只适合预筛。judge 自己也要先拿人工的分叉判定审核核对过，才能用它筛数据（第 7 节第 5 步）。分叉的两个 token 数是 provider 报的总用量除以分叉数，录制的 1.4 万是轮次记录说的输入 token，口径不完全一样；轮次记录自己的说法是两者差不多。

可评判比例一轮轮涨上来，靠的是回放修复和站点规则：10 月 21 日 51/318（16%），22 日 20%，23 日 24%，冻结后台标签页后 41%，加上媒体区域规则等之后 69%，再补规则到 75%（**项目数据**）。

### 4.2 每个可用决定花多少

可用决定指 `judge-forks` 判为 `judged`、`reasonable` 和 `executed_as_intended` 都是 yes 的分叉决定。轮次记录分别给了两个回答的数，没给两者同时为 yes 的数，所以下表拿“按意图执行”的数当可用决定数。这个数是上限，每个可用决定的花费因此是下限（**推断**）：

| 来源 | 可用决定占比 | 每个可用决定约多少 token |
|---|---|---|
| 同任务分叉 | 64/210 = 30%（占可评判的 47%） | 至少约 5.4 万 |
| 换任务分叉 | 60/120 = 50%（占可评判的 65%） | 至少约 4.0 万 |
| 录制的步 | 约 65%（**直觉**，数据量估算的保留率假设） | 约 2.2 万 |

算法：分叉的 token，加上评判（89 万 ÷ 229 个可评判分叉，每个约 3,900），换任务再加变体生成的 6 万，除以可用决定数；录制是每步 1.4 万除以 65%。换任务分叉约为录制的 1.8 倍，同任务分叉约 2.5 倍。分叉按意图执行的比例低，一部分是回放环境造成的（页面计时器、离站、加载），不全是 teacher 的问题。

分叉的价值在别处：同一状态有几个决定，能换任务，能换 teacher，不碰 live 站点，没有风控和限流。B 用来看决定稳不稳、做偏好对，C 用来做任务条件化和前瞻的反事实对（设计文档数据④）。量按这些用途定，不拿来凑 SFT 的条数（**建议**）。做偏好对要注意，上一轮 137 个可评判的同任务分叉里只有 18 个被判不合理，“一好一坏”的对不会多。

### 4.3 墙钟和磁盘

- 录制每步 p50 16.7 秒，观测的落定等待 p50 756 ms、p95 5,001 ms（采集评估，实跑的 479 个策略步）。
- 分叉要按录下的模型等待重放前缀，靠后的检查点单个要近 20 分钟，所以 `--timeout 1500`（runbook）。分叉省掉的是对 live 站点的访问，墙钟并不省。上一轮同任务分叉开了 8 个进程，两组换任务分叉各 4 个；重页面加 8 路并行时，网络归档 5 秒的写盘预算不够，IGN 有 3 个分叉记录不全（**项目数据**）。

### 4.4 三档的采集量

把数据量估算的三档折成采集资源（**推断**）。要录的步 = 保留轨迹 × 1.3 × 20。保留轨迹是过了轨迹级质检、进入训练的轨迹（那份报告的定义）。1.3 是录制系数，即录下的轨迹数是保留轨迹数的多少倍，也是那份报告的**直觉**，前提是 teacher 在挑过的任务上大多能完成：只留成功轨迹、teacher 成功率又只有一半时要翻倍，按步筛、失败轨迹里的好步也留下时会低一些。20 是那份报告假设的每条步数，取在实跑的 15.5 步和首轮的 29 步之间。65% 的步保留率只影响监督步数，这张表没用到。

| | 最低档 | 推荐档 | 扩展档 |
|---|---|---|---|
| 保留轨迹 | 约 1 万 | 约 3 万 | 10 万以上 |
| 要录的步 | 26 万 | 78 万 | 260 万 |
| teacher 输入 token（每步 1.4 万） | 约 36 亿 | 约 109 亿 | 约 364 亿 |
| worker 时（每步 16.7 秒） | 约 1,200 | 约 3,600 | 约 12,000 |
| 机器日（每台同时 3 个站点，全天跑） | 约 17 | 约 50 | 约 170 |
| 磁盘（每步 4.5 MB） | 约 1.2 TB | 约 3.5 TB | 约 12 TB |

读这张表要注意：

- 每步 16.7 秒是中位数，4.5 MB 是中位数 3.0 MB 加上多拍的帧（第 2.3 节）。耗时和磁盘的分布右偏，总量会比表里多。
- 只算了录制，不含分叉、评判、变体生成和推理输出的 token，也没折成钱。
- 步数是最大的变数。上一轮 LexBench L1 任务每条约 28 步（每个任务约 39 万 token ÷ 每步 1.4 万），首轮（10 月 21 日那轮）约 29 步。任务都这么长的话，要录的步、worker 时、机器日和磁盘都要乘约 1.45，每步 token 按 1.4 万算正好；轨迹真到 20 步，每步 token 会少一些，因为每次决定都带着全部历史（**推断**）。这些 token 大部分是前缀，能命中缓存。
- 采集速度的上限可能在 teacher API 的限流、风控和每台机器能并行几个站点，三样都没在扩量的规模上量过（**推断**）。

## 5. 怎么扩

### 5.1 先扩任务和站点

原报告的结论：扩展曲线都是凹的，先扩页面族和困难分层，最后才扩同一模板内的量（**论文报告**：UGround、ScaleCUA、InSTA、EvoCUA 的曲线；Jedi 混多种数据到 400 万条还在涨）。数据量估算的推荐档是 ≥6,000 个任务、≥100 个训练站点，每个任务最多保留 5 条，另留 10–20 个站点、每站 20 个以上任务只做测试（**直觉**，那份报告第 6 节）。上一轮是 15 个任务、5 个站点，所以第一件事是任务生成器。

### 5.2 任务从哪来

按成本从低到高排。

**① 现成基准。** spectragent 注册了 `lexbench_browser`（子集有 L1、L2、L3-api、L3-security、omw、private 等）、`online_mind2web`（All、Hard）和 `browsecomp`（**项目数据**，`spectragent/core/data_loader/task/`）。数据目录不在仓库里，各有多少任务要你那边数。将来要拿来评测的，导出时写进 `decontamination.against`，否则会漏进训练。

**② 模板任务。** 每个站点写一批模板，填槽位，再让 LLM 改写措辞，比如“在<站点>搜索<关键词>，按<排序>排，告诉我第<n>条的<字段>”。模板按任务类型分：搜索加排序加读取、筛选后比较、详情页取字段、先找 A 再找 B、表单填到提交前、滚动查找、多标签页。用哪个 LLM 写都行，约束照 `lookahead variants` 给 judge 的那几条：不登录也能答、具体、答案能核对、用站点的语言。任务文件的格式我实测过（**本文实测**）：

```text
<数据根>/browser/lexbench_browser/data_info.json
    {"split": {"All": "generated_v0.jsonl"}}
<数据根>/browser/lexbench_browser/generated_v0.jsonl，每行一个任务：
    {"task_id": "gen-bili-search-0001", "task_text": "在哔哩哔哩搜索…", "start_url": "https://www.bilibili.com",
     "language": "zh", "benchmark": "generated_v0", "domain": "video",
     "tags": ["template:search_sort_read"], "metadata": {"template_id": "...", "slots": {...}}}
```

必填的是 `task_id`、`task_text`、`start_url`。`<数据根>` 用一个单独的目录，别放进你存 LexBench 数据的那个目录，否则会盖掉它的 `data_info.json`。两种接法我都试过，都只验证到 `--list` 列出任务，没有真录：

- 设 `SPECTRAGENT_BENCHMARK_DATA=<数据根>`，用 `--benchmark lexbench_browser --subset All`；
- 不设环境变量，在录制 YAML 末尾加一个 `task_loader` 块：`benchmark_name: lexbench_browser`、`subset: All`、`data_dir: <数据根>/browser/lexbench_browser`。

两种都对整次 sweep 生效，所以生成的任务和 LexBench 的 L1 任务分开跑 sweep。要一个站点一个 sweep，就在 `data_info.json` 里每个站点写一个 split，比如 `{"split": {"bilibili": "gen_bilibili.jsonl", "ign": "gen_ign.jsonl"}}`，每个 sweep 用 `--subset bilibili` 这样选一个（**本文实测**，`--list` 只列出那个文件里的任务）。loader 读回来时，`benchmark` 保留文件里写的值（没写时才填 loader 自己的名字），`tags` 和 `metadata` 原样保留，`www.10jqka.com.cn` 这样的裸主机补成了 `https://`。示例文件在 `_notes/task_file_example/`。

模板先让 teacher 在几个任务上试跑，成功率太低或答案没法核对的模板丢掉。Go-Browse 的 FeasibilityChecker 就是这么做的，筛掉 403 个任务，省了约 13% 的步（**论文报告**，原报告 notes）。

**③ 把 variants 变成新的 live 任务。** `lookahead variants` 让 judge 看着录下的检查点截图，写出同一站点上不同的信息需求（**项目数据**，README）。现在这些任务只用来跑离线分叉，每个分叉一个决定。分叉没法一直走下去：离线回放的应答只来自录下的归档，走到没录过的页面就 miss（**推断**，分叉配置写的是 `miss_policy: strict`）。把它们写成任务文件，从检查点所在页面的 URL 出发，就能 live 录成完整的新轨迹：

```bash
python3 -I $N/variants_to_tasks.py --variants $R/variants/variants.json \
  --steps $R/out/steps.jsonl --out <数据根>/browser/lexbench_browser --min-path
```

它读 variants 文件和 `extract` 的 `steps.jsonl`，查出检查点的 URL，写出上面格式的任务文件，并在已有的 `data_info.json` 里加一个以 benchmark 名命名的 split（默认 `gen_variants_v0`，录制时用 `--subset gen_variants_v0`），不动模板任务的 split；`--min-path` 跳过停在裸首页的检查点（**本文实测**：在 fixture 演练的真实 `steps.jsonl` 上跑通，variants 文件是我手写的，产物能被 `--list` 列出）。没把状态写进 URL 的页面（单页应用的面板、POST 提交的搜索）重新打开会是别的样子。录完拿新 run 的第一张截图和源检查点的截图比，差得多的丢掉；可以借 `lookahead stability` 的 32 像素网格差分来比，现在没有现成命令（`spectragent flywheel diagnose` 比的是录制和回放，不比两次录制）。

**④ 探索生成。** Go-Browse、Explorer 这类管线：从站点首页开始探索，看着页面提任务，teacher 试做、确认可行后再录。原报告 notes 里的成本：Go-Browse 每条成功轨迹约 0.10 美元，Explorer 约 0.28 美元，InSTA 只有约 5% 的尝试能用（**论文报告**）。这要在 spectragent 外面写，等模板饱和了再上。事后给轨迹补写任务（NNetNav、OS-Genesis 的做法）会把 t+1 之后才出现的实体写进任务，拿来做前瞻数据会泄露，要标出来、分开用（原报告 notes）。

新站点可以先从 runbook 量过的里面挑：V2EX、21 世纪经济报道、起点、豆瓣读书在 12 站那条链上原路径回放校验全过（那时 pinned 还是每文档一个时钟，换成共享时钟后没重测）；东方财富已经有站点规则，但有滑块验证码（**项目数据**，runbook “各类网站的表现”）。

### 5.3 站点：广度和深度分开

分叉恢复率是靠回放修复和站点规则一轮轮涨上来的（**项目数据**：从不到两成到 75%）。每加一个站点，分叉要恢复就可能要补规则；录制本身不需要规则。所以**建议**把站点分成两类：

- 广度站：只录制，产出 A。数量往 100 个以上扩，避开风控重的站。
- 深度站：录制加分叉，产出 B、C、D。挑规则已经补齐、可评判比例高的页面类型，比如可评判分叉 ≥60% 才做深度站（**直觉**阈值）。runbook “各类网站的表现”按页面类型给的可评判比例：行情选股近九成（上一轮的行情站只有同花顺），B 站九成以上，IGN 补规则重跑后八成多，腾讯视频近六成，爱奇艺约一半。

要做分叉的视频站，开跑前确认 `media_areas` 声明了它的视频页。占满屏幕的自动预告（涂黑超过 75% 时不涂）、shadow root 里 iframe 中的播放器，规则还处理不了（runbook）。

### 5.4 难度分层

- 保留滚动、弹窗、键盘和拖动这些分层，不要照搬 Explorer 删掉“滚动超过 2 次”的轨迹那种过滤（原报告）。
- 多动作步照样保留（`max_actions_per_step: 4`）。你 10 月 21 日的判断是，只有单动作数据的话，模型会偏向每次只出一个动作。
- 难例多采。HATS 只用 1,000 条专挑难动作的轨迹，效果就比 OS-Genesis 的数据好（**论文报告**）。对应到前瞻数据，就是多采两条基线（附 A）预测失败的 transition。

### 5.5 节奏

1. 试点：在当前 main 上重录上一轮的 15 个任务，加 5 个新站点的模板任务，量四个数：每步真实 token（用 Qwen3-VL 的 processor 数）、每条步数、步过滤通过率、teacher 成功率，替换数据量估算里的假设。同时导出一次，跑第 6.4 节的两个脚本。
2. 录到 1 万条保留轨迹，按数据量估算第 6 节训六次（8B 在 2,500、5,000、1 万的嵌套子集上各一次，30B-A3B 在 5,000、1 万上各一次，8B 的 rank 128 LoRA 在 1 万上一次），看留出站点上的学习曲线。
3. 8B 从 5,000 到 1 万还明显在涨，就扩到 3 万（那份报告给的**直觉**阈值是涨 3 个百分点以上，且明显大于评测噪声）；涨不动就加站点和难例，不加同类数据。

## 6. Latent action：LAR 能借什么

### 6.1 论文核对

**论文报告**（来源：arXiv HTML 全文、arXiv 摘要页、ICLR 2026 页面）：

| 项 | 内容 |
|---|---|
| 题目、编号 | Latent Action Reparameterization for Efficient Agent Inference，arXiv 2605.18597，v1 2026-05-18，v3 2026-09-27 |
| 发表情况 | ICLR 2026 Workshop on Memory for LLM-Based Agentic Systems（MemAgents）的 poster。PDF 附了 NeurIPS Paper Checklist |
| latent action 是什么 | 动作片段在“转移等价”下的等价类，每一类用一个新的词表符号表示；没有编码器、码本或连续的隐空间。按我的理解，转移等价是说两个片段在环境里引起同样的状态转移，就算同一类 |
| 怎么找片段 | 在句内挖词级 n-gram：频次 ≥ f_min，下一个词的熵 ≤ H_max，按“频次 ÷（熵 + 1）”排序，和已选片段重叠超过 ρ=0.7 的去掉，取前 K 个。Mind2Web 上另外挖重复的 HTML 标签序列 |
| 超参 | TriviaQA：n 取 3–5，f_min 2000，200–1000 个符号；KodCode：n 取 2–6，f_min 10，约 100 个；Mind2Web：n 取 2–6，f_min 1000，约 100 个；H_max 都是 10 |
| 怎么训 | 原轨迹 τ 用最长匹配改写成 τ̂。冻结的原模型读 τ，学生（LoRA r=8，加上新符号的 embedding，约占 0.1% 参数）读 τ̂，在两边文本相同的位置上做 KL 蒸馏，温度 2.0；AdamW，学习率 1e-4，3 个 epoch |
| 有效步数 | 论文的有效决策步数 H_eff 是轨迹里各步动作的 token 数之和，换成新符号后变短 |
| 轨迹从哪来 | 各模型自己的 rollout；KodCode 抽了 2 万条。三个基准的输入都是文本或 HTML，没有截图 |
| 结果（表 1） | Qwen3-8B：TriviaQA 80.09（动作 token −27.1%），KodCode 54.30（−9.2%），Mind2Web 39.84（−2.9%）。Llama-3.1-8B：72.46（−23.3%）、35.10（−9.8%）、28.30（−20.8%），其中 TriviaQA 低于 Vanilla 的 73.63 |
| 效率 | 只报了吞吐（表 8），没报墙钟延迟。Qwen 的吞吐在 TriviaQA 上从 127.8 到 150.2 tok/s，KodCode 和 Mind2Web 基本不变 |

发表情况是这样查的：10 月 27 日用论文标题加 “NeurIPS 2026” 搜索，结果只有 arXiv、ICLR 和第三方页面，没有 neurips.cc 的论文页。附了 checklist 只能说明作者按 NeurIPS 的格式准备过（**推断**）。我们的学生是 Qwen 系，所以下面主要看 Qwen 那一行。

我读原文时注意到的问题（数字都能在论文里核对，判断是我的）：

- 没有“用同样的 LoRA 预算在原格式轨迹上微调”的对照。对照组是没微调的模型，所以分不清提升来自新符号，还是来自在自己的轨迹上多训了一遍。
- 都是单次运行，没有误差棒；表格之间有对不上的数：Qwen 的 KodCode 在表 1 是 54.30、在表 7 是 58.28；Mind2Web 的 34.15 在表 1 标 CoT、在表 3 标 ReAct。
- 换掉的片段太多时性能会突然崩（原文 5.3 节的“崩溃阈值”），但没给阈值是多少；三个领域合起来训时压缩得更少，Mind2Web 还变差了（附录 A.9）。
- 扩展性只在 Qwen3-32B 的 TriviaQA 上测了一次（73.20 到 75.26）。
- 没写清 Mind2Web 的动作格式。checklist 里写了代码地址 `github.com/EZ-hwh/LAR`，我没去核对。

### 6.2 浏览器动作的 token 实测

**本文实测**：用 Qwen 的 BPE 词表（dashscope 2.0.2 里的 `qwen.tiktoken`，151,643 个普通 token）数 spectragent 的 UI-TARS 动作行。Qwen2 的技术报告说沿用 Qwen 的分词器；Qwen3-VL 的 `tokenizer.json` 我没能下载下来逐个核对（huggingface 返回 403）。Qwen 的 BPE 把数字一位切成一个 token，所以 `(523, 817)` 是 10 个 token。导出的目标轮就是这种写法，fixture 演练的导出里是 `Action: click(point='(125, 244)')`。脚本是 `_notes/action_tokens.py` 和 `format_tokens.py`。

| 动作（例子） | token | 其中参数 | 其中语法 |
|---|---|---|---|
| `click(point='(523, 817)')` | 15 | 6 | 9 |
| `type(content='贵州茅台', point='(412, 96)')` | 19 | 7 | 12 |
| `scroll(direction='down')` | 7 | 1 | 6 |
| `hotkey(key='enter')` | 8 | 1 | 7 |
| `drag(start_point='(102, 540)', end_point='(688, 540)')` | 29 | 12 | 17 |
| `wait()` | 4 | 0 | 4 |

每行都算上了 `Action:` 前缀和换行。同一个点击换三种写法：按 Qwen 的 computer_use 工具调用格式写约 34 个 token（含两个 `<tool_call>` 标签），UI-TARS 15 个，紧凑写法 `click(523,817)` 10 个（不带 `Action:` 前缀，算了换行）。

把每段连续的语法换成一个新符号、参数照旧，是 n-gram 宏符号在这种格式上大致能做到的程度：

| 一步的动作 | 原来 | 只换语法（参数照旧） | 再把每个坐标换成一个 token |
|---|---|---|---|
| click > wait | 19 | 9 | 5 |
| scroll × 3 | 21 | 7 | 7 |
| type > hotkey | 27 | 13 | 10 |
| click | 15 | 9 | 5 |
| drag | 29 | 17 | 9 |

scroll 的方向和 hotkey 的键名熵很低，LAR 的算法会把它们连同语法挖成整行的宏：这样 scroll × 3 能压到 1–3 个 token，type > hotkey 从 13 再降到 11。最后一列相当于给坐标换一套专用词表，LAR 挖片段的做法做不到，列出来只当参照。

实跑的 479 个策略步里，click > wait 有 93 步，连续 2–4 次 scroll 有 70 步，type > send_keys 有 10 步（**项目数据**，采集评估）。

省下的部分占一步输出多少，取决于 thought 有多长。下表按“只换语法”算，每步还加了 `Thought:` 标签和换行的 3 个 token：

| thought 长度 | 三种常见步（click > wait、scroll × 3、type > hotkey）的输出少多少 |
|---|---|
| 0 | 45–58% |
| 30 token | 19–26% |
| 60 token | 12–17% |
| 100 token | 8–11% |
| 150 token | 6–8% |

我们数据里的 thought 有多长还没量过，60 是取的中间值，第一次导出后用审计脚本量。单个 click 在 thought 60 token 时只少约 8%。算上整行宏，每步省 6–20 个 token，按 250 tok/s（你给学生定的速度下限）是 25–80 ms，150 tok/s 时乘 1.67（**推断**）。

### 6.3 “可预见”在哪里成立

你说浏览器动作除了快捷键，就是 click、drag、scroll 这些可预见的动作。拆开看（**推断**）：

- 语法可预见。选了 click，后面的 `(point='(` 就是确定的。LAR 能压这部分，约束解码也能压，约束解码还不用训练（第 6.5 节“推理”一行）。
- 无参动作可预见。spectragent 的 UI-TARS `scroll` 只带方向，距离固定 300 像素；`wait` 固定 1 秒。它们整行就是一个宏。
- 坐标不可预见。点哪里、从哪拖到哪，正是这一步的决定，每屏都不同。在 LAR 的算法里，坐标处的下一个 token 熵很高，挖不成片段。要“预见”坐标得看懂画面，这是 grounding 的事，n-gram 压缩帮不上。
- 效果可预见。滚动会露出下面 300 像素，点搜索结果会跳页，输入框会出字。这一点和 LAR 关系不大，对我们更有用：它决定一次调用能不能连发几个动作，也是 `<predict>` 能成立的前提。

### 6.4 可以做的四件事，按建议的先后

#### ① 先审计导出数据（零成本）

`_notes/action_token_audit.py` 读导出的 `train.jsonl`（按步的或打包后的都行），把目标轮的 token 拆成 thought、动作语法、动作参数和其他（以后的 `<predict>` 落在这里），统计动词和每步的动作序列，再按 LAR 的算法 1 在 token n-gram 上挖宏符号，报压缩率和每步省多少毫秒。参数默认按 LAR 取 K=100、ρ=0.7；f_min 和 H_max 要按数据量调：LAR 的 H_max=10 是在词级 n-gram 上取的，脚本在 token 级按 bit 算熵，我先给 3（**直觉**）。它只量 token 构成，有多少步能合并要用下面的 `chunk_candidates.py` 另外量。脚本在一个 3,000 条的合成文件和 fixture 演练的真实导出上都跑通了（**本文实测**；这两份数据只用来测脚本，不当证据）。

```bash
python3 -I $N/action_token_audit.py --data datasets/<名字>_post/train.jsonl \
  --tokenizer /path/to/Qwen3-VL-8B-Instruct        # 没装 transformers 时：--tiktoken-ranks qwen.tiktoken
```

怎么用结果（**直觉**阈值）：宏符号每步省下的 token 不到目标轮的 20%，就不改词表。当时的想法：改词表要训新 embedding、要做对照实验，部署端的解析也要改，收益不够大不值得。

#### ② 盲操作标签：多动作 chunk 里，后面的动作该不该先看一眼

一次调用连发几个动作时，后面的动作是对着旧屏幕做的。实跑的 991 个动作里，516 个之后没有紧跟的截图（**项目数据**，采集评估）。现在每个动作之前都有一帧（`frame-<cycle>-before-<i>.png`），还有每个动作的效果，所以能离线判断第 i 个动作（i>1）执行时屏幕变没变（**推断**的做法）：

- 动作点周围（比如 64×64 像素）在动作前那一帧和 O_t 上是否一致，用 stability 的 32 像素网格差分来判；
- 前面的动作有没有导航或滚动；
- 第 i 个动作命中的元素（role、name）是不是 O_t 的 DOM 在那个点上的元素。

三样都过，标“盲操作安全”，否则标“该重新看”。先当过滤器，丢掉后面动作盲点出错的 chunk；量够了再当监督信号，教模型什么时候该停下来重新看。spectragent 现在一步里有动作失败就停下，失败的那个动作有记录。

`_notes/chunk_candidates.py` 先做不用看图的那部分：在 `steps.jsonl` 上数多动作步占多少，后面的动作里有多少已经能判为“该重新看”（前面导航了、滚动了、整步的 URL 变了、在失败之后被跳过），剩下多少要做像素和 DOM 核对、其中多少有动作前的帧。像素和 DOM 的核对它没做。命令是 `python3 -I $N/chunk_candidates.py --steps $R/out/steps.jsonl`。

#### ③ 合并步：把能合并的相邻步合成一个更长的 chunk

LAR 缩短的是动作 token 数，这里把同样的想法用在模型调用次数上，是我的延伸（**推断**）。延迟上这项收益最大：少一步，就少一次观测的落定等待（p50 756 ms）、一次 prefill 和这一步 thought 与动作的解码（thought 60 token 时约 0.3 秒）。合起来约 1 秒，是宏符号每步省下的 25–80 ms 的十几到几十倍（**推断**）。

两种造法：

- 离线合并，便宜。相邻两步 t、t+1 同时满足下面几条就合成一步：两步都执行了动作、没出错；第 t+1 步不是结束任务；第 t 步没有 `wait()`、没有滚动、动作都成功；动作数合计 ≤4；第 t 步前后 URL 不变；O_{t+1} 在约 1 秒内落定（**直觉**阈值）；第 t+1 步要操作的元素在 O_t 上同一位置就能看到（按 DOM/AX 的框或像素区域判）。最后一条最要紧：合并以后两步的动作连着执行，中间不再拍观测（一步之内的动作之间不重新读页面，architecture_design），第 t+1 步的动作只能对着 O_t 做。合成后的训练样本，上下文到 O_t 为止，训练目标是两步的动作，两段 thought 交给改写模型合成一段，比如 runbook 给 `drop_when_capped` 举例用的 `gpt-4.1-mini`。做法和导出器的 `drop_when_capped` 一样（让一步整个消失、改写受影响的 thought、带缓存），只是在外部做。`chunk_candidates.py` 检查除最后一条以外的所有条件，报每条条件筛掉多少对、通过的对是什么动作组合、按动作数上限贪心合并能少掉多少步。最后一条要看图，所以它报的是上限。在 fixture 演练的录制上，它挑出的是“输入关键词 | 点搜索”这样的对（**本文实测**，只说明脚本能跑）。
- 让 teacher 自己出更长的 chunk，要花分叉。分叉配置可以挂 `prompt_contribution` hook，给检查点那一步的 teacher 加一句提示，比如“能确定的连续动作可以一次发出”，再用 judge 判、看执行结果。hook 已经有了（runbook “teacher 采样”），这种提示没跑过。

风险是模型学会该看的时候不看。所以合并步要和盲操作标签一起用，合并出来的 chunk 也要过②的检查，单步动作数上限保持 4。你 10 月 21 日的判断（有多动作数据，模型才愿意一次多发）是这一项的前提。

#### ④ 转移类型 token：和 `<predict>` 一起训

设计文档的数据②本来就要给转移分类（动作类型、URL 是否变化、变化框、版面聚类）。可以把它压成十来个离散类，比如跳新页、同模板刷新、原地更新、弹窗、下拉展开、滚动露出、焦点进输入框、没变化、加载中，作为 `<predict>` 的一个字段一起输出（**直觉**）。当时的想法来自 LAWA（arXiv 2608.24882，机器人领域的预印本，我只读了摘要）：它把“未来意图”表示成离散码本里的 latent action，推理时去掉生成未来视频的分支，延迟比对应的 Joint-WAM 变体低 42.9%，性能相当（摘要里的数，**论文报告**）。对我们来说，“下一屏会是哪一类”就是不生成下一屏也能有的那份预期。先用规则分类，规则不够用了，再从帧差分和动作效果上学码本。P1 里做一组有、无这个字段的对照，看它能不能让选区更准。

### 6.5 各阶段放什么

| 阶段 | 做什么 | 数据 | 预期收益 | 证据 |
|---|---|---|---|---|
| 采集和导出 | 保留多动作步；`drop_when_capped` 去掉慢网络上的等待；盲操作标签；合并步 | 第 2.3 节存下的帧和效果 | 每少一个 `wait()` 省 1 秒；每少一步省约 1 秒 | 等待时长是**项目数据**，其余是**推断** |
| SFT | 用合并后的长 chunk 当目标；转移类型字段并进 `<predict>`；宏符号只在审计过线时试，而且要配一组原格式的对照 | 导出加外部后处理 | 少调用次数；宏符号每步几十毫秒 | **推断**、**直觉** |
| RL（以后） | 每条轨迹调用次数少了，同样的环境时间能多跑几条 rollout | 模型自己的 rollout | 环境步数少了，token 省得不多 | **推断**。LAR 说用了 latent action 后 GRPO 更稳，只有一张图、单次运行，算弱证据 |
| 推理 | 约束解码的 jump-forward：动词定了，后面确定的语法一次填上，不逐个 token 解码；同时保证动作能解析 | 不需要 | 每步省十来个 token 的解码；更要紧的是不再有解析失败 | SGLang 团队的博客说，在 JSON 任务上延迟最多降一半（博客里的数，不是论文；llama-7B、A10）；用在我们的短动作行上能省多少没测 |

### 6.6 没展开的两条

- n-gram 投机解码（prompt lookup）能加速重复出现的语法。我没能打开 vLLM 的文档（抓取被 robots 拒绝），细节没核对。
- 从录屏视频学动作，量大但标签粗，适合在预训练阶段扩广度，当 SFT 的金标不合适：Video2GUI（arXiv 2605.14747）用 Gemini 给视频标动作，得到 1,270 万条轨迹，ScreenSpot-Pro 上 Qwen2.5-VL-7B 从 26.8 到 41.9；VideoAgentTrek 的按键召回只有 0.08（**论文报告**）。

## 7. 开工清单

1. 拉 main，按第 3.1 节准备机器、网络和外观。在新网络上先录一两个任务，看 `settle` 里截断时主文档还没加载完的采集是否接近 0。
2. 准备第一批任务：上一轮的 15 个 L1 任务直接用 LexBench（id 见第 3.2 节）；再给 5 个新站点各写 10 个模板任务，每个站点一个 split，放在单独的数据根下（第 5.2 节②）。先 `--list` 核对。
3. 录制，每个 sweep 设 `--token-limit`。录完跑 `health`，翻截图。
4. 跑 `variants` 和三组分叉；在同一批分叉上比较 `pace: recorded_llm_latency` 和 `recorded_timeline`，看各站点的可评判比例。
5. 建审核队列。稳定性队列默认 60 条（`--queue-size`）；分叉判定队列列出全部可评判分叉，先标 51 条左右（首轮你本地 review 视图排的量）；金标 `--n 100`，先标 calibration 那一半。分叉判定标完，先算人和 judge 的一致率，再决定能不能用 judge 筛分叉。
6. 导出三份，每份只改一个变量：(a) 发布配置只改 `sources_root`、`sources`（加上分叉目录）和 `output_dir`，看分叉被排除了多少；(b) 按第 3.5 节放开 `exclude_restoration_diverged` 和 `max_document_misses`；(c) 在 (b) 上再开 `wait_actions: drop_when_capped`。拿 (b) 的配置再导出一次，核对逐字节相同。然后对要用的那份跑 `export_postprocess.py`。
7. 在后处理过的导出上跑 `action_token_audit.py`，记下每步 thought、动作语法、参数各多少 token，最常见的动作序列，宏符号能省多少。
8. 在 `steps.jsonl` 上跑 `chunk_candidates.py`，记下多动作步的比例、要做像素核对的动作数、通过的相邻步对、贪心合并能少掉的步数；再从通过的对里抽 50 对人工看，第 t+1 步的目标在 O_t 上看不看得到。
9. 用试点的四个数（每步 token、每条步数、步通过率、teacher 成功率）更新数据量估算，再定一次录多少。
10. 跑 `variants_to_tasks.py`，把这一轮的 variants 变成下一轮的 live 任务；录完拿第一张截图和源检查点比。

## 8. 猜测汇总

| 判断 | 类型 | 怎么来的 | 怎么验证 |
|---|---|---|---|
| 分叉每个可用决定约为录制的 1.8–2.5 倍 | 推断 | 每次决定的 token 相近；可用决定按“按意图执行”的数算（上限），录制保留率按 65% 算（直觉） | 试点量录制步的通过率；在 `judgments.jsonl` 上数两个回答都是 yes 的分叉 |
| 导出分叉时放开两项筛选，在外部按 judge 筛 | 推断 | 分叉样本的目标在检查点上，检查点画面 judge 已经核过 | 第一次导出时抽查分叉样本的检查点画面 |
| variants 能变成从检查点 URL 出发的 live 任务 | 推断（格式已实测） | 任务文件能被加载；很多页面把状态写在 URL 里 | 录完比第一张截图和源检查点 |
| 广度站只录制、深度站才分叉；深度站门槛是可评判 ≥60% | 建议；门槛是直觉 | 恢复率靠站点规则，录制不需要规则 | 在新站上不补规则跑一次分叉，看可评判比例 |
| `--token-limit` 按每个任务 60 万给 | 建议 | 上一轮录制每个任务约 39 万，留五成余量 | 看试点的 token 账 |
| 宏符号省不到 20% 就不改词表 | 直觉 | 改词表的工程和实验成本 | 审计脚本 |
| 少一次调用的收益是宏符号每步的十几到几十倍 | 推断 | 落定 p50 756 ms 加上解码，对比每步省 6–20 个 token | 部署时实测每步墙钟的构成 |
| LAR 的“缩短有效步数”可以换成缩短调用次数 | 推断 | LAR 按 token 算有效步数；浏览器上每次调用的固定开销远大于几个 token | 合并步的对照训练 |
| 盲操作标签能离线算 | 推断 | 每个动作前有帧，有命中元素和 URL | `chunk_candidates.py` 加像素核对，抽 50 条人工看 |
| 合并步不会教坏模型；落定阈值取约 1 秒 | 直觉 | 只合并目标在 O_t 上就看得到的步 | 合并前后各训一版，比留出站点的成功率和误点率 |
| 转移类型 token 能帮 `<predict>` | 直觉 | LAWA 在机器人上的结果 | P1 里有、无这个字段的对照 |
| 轨迹更短时每步 token 少于 1.4 万 | 推断 | 每次决定带着全部历史 | 试点量 |

## 9. 还不确定的

- 吞吐：快网络上一台机器能并行录几个站点，teacher API 在扩量规模下怎么限流，新站点的风控有多重，都没量过（第 3.1、4.4 节）。下一轮 teacher 走哪条 API 路由也还没定。
- judge 可不可靠：规则和 judge 只一致 58%，judge 和人的一致率还没量（第 4.1 节，第 7 节第 5 步）。
- 分叉和导出一起用、`drop_when_capped`、`recorded_timeline`、两个“没加载完”的筛选（导出的 `exclude_unloaded_steps` 和分叉的 `exclude_unloaded_checkpoints`），都只在 fixture 或小样本上测过（第 3.4、3.5 节）。
- 标注流程还没完整走过一遍，谁来标金标还没定。
- 盲操作标签和合并步的像素、DOM 核对还没写，`chunk_candidates.py` 给的是上限（第 6.4 节）。
- LAR 的做法在我们的动作格式上能不能保住准确率，没有测，论文自己也缺原格式微调的对照；Qwen3-VL 的分词器我没逐个 token 核对。

## 附 A 术语

| 词 | 意思 |
|---|---|
| O_t、O_{t+1} | 第 t 步模型看到的截图（观测），和执行完这一步的动作之后的下一张 |
| transition | 一组（O_t，这一步的动作，O_{t+1}），前瞻观察数据的基本单位 |
| 检查点、分叉 | 从一条录下的 run 里选一步当检查点，离线回放前缀、恢复到这一步的画面，让 teacher 在同一屏上重新决定一次；这样的一次重跑叫一个分叉。同任务分叉用原任务，换任务分叉用 `variants` 写的新任务 |
| 可评判 | 分叉的检查点画面恢复成功（恢复器对检查点的校验是 ok），它的决定才能评判 |
| 可用决定 | `judge-forks` 判为 `judged`，`reasonable` 和 `executed_as_intended` 都是 yes 的分叉决定 |
| 源思考 | 换任务分叉的历史里带着源 run 当时的 thought；“去掉源思考”是不带它们的对照组 |
| sweep | 一次 `spectragent bench` 调用跑的一批任务；录制时一个站点一个 sweep |
| worker 时 | 一个 sweep 进程跑一小时 |
| 保留轨迹、监督步 | 保留轨迹是过了轨迹级质检、进入训练的轨迹；监督步是其中过了步级过滤、算 loss（权重 1）的步（数据量估算的定义） |
| 段 | 导出器在不可译的步处把一条 run 断开，连续可导出的一截叫一段 |
| 落定（settle）、capped | 每次截图前等页面加载完、DOM 安静、视口里有内容，最多等 5 秒；等到了是 settled，到上限还没等到是 capped，`waiting_for` 写着差哪一样（`load`、`dom`、`content`） |
| 主文档 miss | 离线回放时，主 frame 的文档请求在录下的归档里找不到应答 |
| 近邻 miss | 离线回放时请求在归档里找不到匹配的应答，度量报告列出最相近的录下请求，用来写站点规则 |
| 度量报告 | `spectragent flywheel report` 算出的报告，含按站点和端点汇总的近邻 miss（第 3.3 节） |
| pinned、时钟 | `replayability: pinned` 固定随机种子、时间、时区、语言等，让录制能离线回放；`clock: shared` 让各标签页共用一个时钟，旧的 `per_document` 每个文档一个 |
| `pace` | 分叉恢复时重放前缀的节奏：`recorded_llm_latency` 按录下的模型等待时长走（上一轮用的），`recorded_timeline` 按录制的整条时间线走 |
| 离站 | teacher 点了广告或跳到别的网站，离开了任务所在的站点 |
| 12 站那条链 | runbook 里更早的一次完整链路：12 个中文站点，脚本化模型，录制加原路径回放 |
| 页面族、页面类型 | 同一类模板的页面，比如搜索结果页、详情页、行情页；runbook 按页面类型列了各类站点的表现 |
| fixture、fixture 演练 | 仓库自带的本地测试站点；演练（`tests/_helpers/flywheel_rehearsal.py`）用脚本化模型在上面跑一遍录制、回放、分叉和导出，不花模型费用 |
| `<predict>` | 设计文档给前瞻观察加的输出段：动作之后，预测下一屏哪里会出现下一步要用的信息 |
| 设计文档数据①–⑧ | ① 带完整下一屏的真实 session，② 转移类型与版面聚类，③ teacher 输出与保真度标签，④ 反事实需求对（来自 C），⑤ 不确定与回退样本，⑥ 读取器适配数据，⑦ 全观察回归集（公开基准加自己的），⑧ 人工金标评测子集（在 E 里）。D 指①②③⑤⑥ |
| P0–P3 | 设计文档的训练阶段：P0 定观测合同、做诊断，不训练；P1 训选区（`<predict>`）；P2 在自己选出的画面上训读取；P3 用模型自己的采样迭代 |
| 两条基线 | 设计文档里不用模型的前瞻预测：下一步要用的信息出现在这一步动作的位置附近，或者在屏幕中心 |
| hotkey、send_keys | UI-TARS 的 `hotkey` 动作在 spectragent 里执行为 `browser.send_keys` |

## 附 B `_notes/` 里的文件

| 文件 | 用途 |
|---|---|
| `export_postprocess.py` | 第 3.5 节：排除健康检查标出的录制，按 judge 筛分叉，丢掉非 `ok` 的步，可选整条打包 |
| `chunk_candidates.py` | 第 6.4 节②③：多动作步里的盲操作统计，相邻步可合并的上限 |
| `action_token_audit.py` | 第 6.4 节①：导出数据的 token 构成，以及 LAR 式宏符号能省多少 |
| `variants_to_tasks.py` | 第 5.2 节③：把 variants 变成 live 任务文件 |
| `action_tokens.py`、`format_tokens.py` | 第 6.2 节的分词计数 |
| `task_file_example/` | 第 5.2 节②：任务文件示例（`data_info.json` 和三条任务） |
| `README.md` | 每个脚本怎么跑、测到什么程度 |
