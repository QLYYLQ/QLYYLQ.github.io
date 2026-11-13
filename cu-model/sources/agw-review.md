# AGW-35B 与 AutoGUIWorld 对 CU/BU 下一观测预测的评估和执行交接（2026-10-03）

- 状态：HF eager r4 冻结评测已 `complete`，两张 NPU 上的权重加载、重复单图、七图 smoke、direct 28、plan 28、native grounding 97 均有终态回执。vLLM 仍因必需 Triton 核编译失败，没有有效模型文本。下一观测要求未通过：direct 原始输出严格点格式 0/28；事后只去步号头为 27/28，但在固定 46 个 field-arm 几何单位中只命中 1 个 assistant 标注证据框中心；plan 主观组件审阅四项齐备 0/28。当前屏原生格式也未过门：完整 Action+call 25/97，source-derived box hit 15/97。后看输出设计的标签盲语法容错可读出 95/97 个唯一 left-click 坐标、proxy hit 62/97，但它不是可执行接口或主结果。尚无完整 check/revisit、真实任务成功或 Chrome holdout。run `62628822` / app `psxg68txrs7fieen` 已停止并从 `efficient_910c` 资源视图释放，`hopex` 已解绑。
- 目的：判断 AGW-35B 是否值得在现有 CU/BU 协议上部署评测，以及 AutoGUIWorld 的训练数据生成方法能否补充本项目的下一观测区域监督。
- 证据边界：本文引用的 AGW 指标来自作者报告和模型卡，本项目尚未复现。本文不把论文结果写成当前 worker 结果，也不把完整屏 grounding、合成轨迹质量或聚合 benchmark 提升解释成下一观测预测能力。
- 上游来源：[论文 HTML](https://arxiv.org/html/2610.01215)、[AGW-35B 模型卡](https://huggingface.co/YangC777/AGW-35B)、[AutoGUIWorld 代码仓库](https://github.com/ImYangC7/AutoGUIWorld)。模型仓库固定 revision `855c909f96f604ff0533a9a8eee23e348c08df93`；代码核对的是 main commit `7d3a063f3538cb4a6216c7da9dbae320b010ca2d`。
- 本项目累计依据：[COMPREHENSIVE_REPORT_20260929.md](COMPREHENSIVE_REPORT_20260929.md)、[HANDOFF_20260930.md](HANDOFF_20260930.md)。

## 1. 结论

本项目已经完成一次有界离线部署与评测。AGW-35B 可通过 HF eager 在当前 H910C worker 上加载和多图解码，vLLM 路径仍不可用；模型没有通过原生动作格式门或下一观测协议门。当前不把它提升为下一观测基座、browser 主 teacher 或 judge，只保留为后续格式适配、训练和受控对照的候选。作者报告的 ScreenSpot-Pro 提升仍是选择它进入本轮评测的上游依据，不是本地结论。

现有公开证据不能证明它能完成本项目的核心行为。本项目要求模型在下一屏不可见时，根据合法历史和刚发出的动作预测需要观察的区域，再经过受限观察、`<check>` 和可选 `<revisit>` 决定下一步。AGW-35B 的训练目标是看过当前截图后直接预测下一个可执行动作；空间标签是当前截图上的动作目标点。论文没有训练或评测未来截图到达前的 evidence ROI、证据充分性判断、受限观察或补看。

浏览器能力必须单独设门。AutoGUIWorld 的训练集中 Chrome 有 35,209/79,266 行，占 44.4%，但 AGW-35B 在论文的两个 Chrome 分域都退化：OSWorld Chrome 为 39.0% 到 26.0%，分母 46 个任务；Windows Agent Arena Chrome 为 11.2% 到 0.0%，分母 17 个任务。聚合 benchmark 的提升不能覆盖这项回归。本项目同时研究 browser use，AGW 在通过同协议 Chrome 对照之前，不应成为浏览器造数的唯一 teacher、judge 或默认策略。

AutoGUIWorld 对本项目更直接的启发来自数据管线：先固定界面状态，再生成与该状态相容的任务和原子动作，逐步生成 `before/action/after`，给指向动作补空间标签，并对每个转移做质量检查。迁移时需要新增本项目的因果边界、evidence ROI、证据充分性和真实浏览器回放检查。合成轨迹适合作为候选和覆盖扩充来源；真实 CU/BU 轨迹仍需承担最终语义校准与回归评测。

本地冻结诊断给出两层结论。HF eager G1/runtime 证明该 checkpoint 能在当前 H910C worker 上加载并接受单图与多图输入，本批最高为七图；没有运行双图请求。vLLM 部署路径仍失败。模型在当前屏原生动作格式和下一观测零样本协议上都没有过门；标签盲事后容错显示大量输出仍含唯一坐标，但这是看到序列化错误后设计的诊断，不能替代可执行格式。现有 box 也只是 assistant 标注或 source-derived 代理。这个负面结果不影响对 AutoGUIWorld 纸面造数方法的借鉴，但该方法产出的数据仍需独立 QC 和真实环境验证。

## 2. 本项目当前要解决的问题

本项目的行为链是：

```text
observed history + issued action
    -> <predict> evidence regions before the next screenshot is visible
    -> restricted next observation
    -> <check>
    -> optional <revisit>
    -> next action
```

预测输入不能包含下一屏像素、目标 DOM 或 URL、未来动作、答案或从目标反推的描述。未来截图和动作可以离线生成标签和评分，但必须留在因果边界之外。

截至 09-30，本项目已经把主要断点定位到“看哪里”和“证据是否足够”：

- Phase 1 的 111 个 transition 上，模型排序前 8 格覆盖记录的下一次点击框中心为 16 至 21/111；复制刚发动作位置的简单基线为 56/111。这个标签是轨迹 silver 代理，不等同于任务证据。
- 14 个 evidence case 中，13 个有需新观察证据框，共 23 个带框字段。一个连续矩形在 12.5% 面积预算内可包住 13/13 个 case；任意 8 格可包住 12/13；现有“点到最近 8 格”控制器即使选最优点也只有 9/13。
- E2 的每模型每条件分母为 48 个需新观察字段，即 24 个字段 × 2 个历史臂；它们是配对字段，不是 48 个独立样本。完整目标图和 oracle 连续矩形下，两模型语义读取均为 48/48；模型自选区域下，8B 两条路线均为 0/48，32B 先计划再选区为 9/48、直接选区为 4/48。8B 直接选区的 triller warm 臂缺一条请求，对应 2 个字段仍留在固定的 48 分母中并按未读对计。语义终判来自 assistant 盲审，不是人标 gold。
- 现有正式新 schema 训练数据为 0 行。旧的 28 行 completion-only 数据只够工程回归，其中 11/12 个 transition 与 eval111 重叠，predict 标签仍是下一次点击框，训练后主要改善输出格式和模板。

本文后面的术语沿用累计报告。显式 query 97 条是“给完整当前目标屏并明确写出要定位哪个控件”的 grounding 集。语义类别中，AU 是证据不足时的合理不确定，CU 是值碰巧正确但合法可见证据不足。完整链断点里，OK 是完整受支持；L1 是 ROI 和补看都没有覆盖证据且模型合理放弃；L2 是看见局部像素后认错实例或读错；L3 是证据充分性判断错误；B 是协议或格式阻断。

因此，AGW 的首要评测应直接检验：它能否在严格因果输入下把 prefix 映射到下一屏的证据区域，并在受限像素上正确决定回答、补看或弃答。完整屏 grounding 只作为 sanity。

## 3. 模型、训练和交互契约

### 3.1 模型制品

2026-10-03 核对到的 Hugging Face revision 为 `855c909f96f604ff0533a9a8eee23e348c08df93`。模型卡标注 Apache-2.0、`transformers`、`image-text-to-text`，基座为 `Qwen/Qwen3.5-35B-A3B`。

模型有 16 个 BF16 Safetensors 权重分片。16 个 LFS 文件的物理 bytes 相加为 70,214,494,016，即 65.39 GiB；`model.safetensors.index.json` 的 tensor payload `total_size` 为 70,214,363,872 bytes，两种口径不能混用。`config.json` 声明：

- 架构为 `Qwen3_5MoeForConditionalGeneration`，`model_type=qwen3_5_moe`；
- 40 层，256 个 experts，每 token 选择 8 个 routed experts；
- 文本配置的 `max_position_embeddings` 为 262,144；
- 仓库配置由 Transformers 5.8.1 生成。

论文训练和官方 serving 示例都把运行上下文限制为 16,384 tokens。原生配置的更长位置上限不等于该 agent 已在更长 GUI 历史上训练过。

### 3.2 训练目标与历史窗口

AGW-35B 用 79,266 个 step-level GUI 样本对 Qwen3.5-35B-A3B 做 SFT。视觉编码器和 aligner 冻结，语言模型训练；`args.json` 记录 `tuner_type=full`、`loss_scale=last_round`，不是 LoRA。主要训练设置如下：

| 项目 | 设置 |
|---|---:|
| 训练轮数 | 3 epochs |
| 最终报告 checkpoint | step 469 |
| 最大序列长度 | 16,384，超长样本删除 |
| 学习率 | peak `1e-5`，minimum `1e-6` |
| warmup | 0.03 |
| weight decay | 0.1 |
| global / micro batch | 512 / 1 |
| 训练资源 | 4 nodes、32 GPUs |
| TP / PP / DP / EP | 2 / 1 / 16 / 8 |

训练输入的最近 5 步包含当前步，并保留这些步的截图；其中已经完成的步还保留 assistant response。再往前 5 步只保留动作描述，更早历史删除。每个样本只监督最后一个 assistant response，较早 assistant 消息作为上下文但不计 loss。这一点与本项目的 completion-only loss 边界相容，但监督内容不同。

### 3.3 输出接口

模型是 direct-action、non-thinking agent。输出包含一条 `Action:` 描述和一个或多个结构化 `computer_use` tool call。指向动作使用 0 至 999 整数坐标，动作空间含点击、拖动、键盘、输入、滚动、等待和终止，共 14 个 primitive。模型需要外部 executor 执行动作、抓取新截图并续接历史。

模型卡要求保留仓库 chat template，并在推理时关闭 thinking。论文评测通过 vLLM TP2 服务模型，四个交互 benchmark 每个任务最多 100 个 agent turns；任务最终状态由 benchmark evaluator 评分，不采信模型自己声明的 success。

这些是作者的 GPU 训练和评测配置。它们不证明当前 H910C 镜像已经支持该模型的 processor、Gated DeltaNet、MoE dispatch、视觉路径或 tool-call 模板。

## 4. 作者报告的结果与边界

### 4.1 数据构成

| 环境 | 训练样本 | 占比 |
|---|---:|---:|
| Chrome | 35,209 | 44.4% |
| Ubuntu | 24,250 | 30.6% |
| Windows | 14,778 | 18.6% |
| macOS | 5,029 | 6.3% |
| 合计 | 79,266 | 100%（分项四舍五入为 99.9%） |

每行训练实例由干净的 action 前截图、任务和近期历史组成，target 是计划动作及可选的动作点。生成系统本身不参与下游 SFT 推理。

### 4.2 实环境与 grounding 结果

| Benchmark | 固定分母 | 指标 | 基座 | AGW-35B | 变化 |
|---|---:|---|---:|---:|---:|
| OSWorld | 361 tasks | mean task score | 33.0% | 40.8% | +7.8 pp |
| Windows Agent Arena | 154 tasks | mean task score | 19.4% | 27.9% | +8.5 pp |
| macOSWorld | 231 tasks | task success | 28.1% | 45.0% | +16.9 pp |
| ScienceBoard | 143 tasks | task success | 14.0% | 32.2% | +18.2 pp |
| ScreenSpot-Pro | 1,581 examples | point-in-box accuracy | 31.7% | 57.1% | +25.4 pp |

ScreenSpot-Pro 的 1,581 条都是英文 positive-target 样本，其中 Windows 927、macOS 604、Linux 50；不可解析坐标计错，没有额外 tolerance。图标目标从 16.2% 升到 32.9%，文本目标从 41.2% 升到 72.0%。

四个交互 benchmark 使用不同指标。论文的“四 benchmark mean”给每个 benchmark 等权，并不按 361、154、231、143 个任务汇总。OSWorld 和 WAA 保留部分分，macOSWorld 和 ScienceBoard 计成功率。任何跨表比较都要保留这些分母和指标差异。

论文还比较了约 80k 合成样本的 AGW run 与约 350k AgentNet 样本的 run。两者虽然共享基座和 benchmark task set，但 inference 设置不同：AgentNet harness 开 thinking，AGW 关闭 thinking；训练步、tokens 和 compute 也没有归一化。因此这组结果只支持论文给出的具体 run 对比，不能推出合成数据普遍优于真实示范。

### 4.3 Chrome 回归

| Benchmark 分域 | 分母 | 基座 | AGW-35B | 变化 |
|---|---:|---:|---:|---:|
| OSWorld Chrome | 46 tasks | 39.0% | 26.0% | -13.0 pp |
| WAA Chrome | 17 tasks | 11.2% | 0.0% | -11.2 pp |

同一篇论文中，WAA Edge 从 23.1% 升到 30.8%（13 个任务）。这说明结果不能概括为所有 browser 都退化，也不能用 Edge 的提升抵消 Chrome 的两项退化。本项目需要按浏览器、任务类型和动作类型分层测量。

Chrome 回归与本项目高度相关，原因有三点：

1. 本项目同时覆盖 computer use 和 browser use；
2. Chrome 是作者训练数据的最大单域，样本量本身没有阻止回归；
3. 本项目现有 Phase 1 的 111 个 transition 中 web 为 80、mobile 为 31，若只看 pooled 指标，很容易掩盖 browser 方向的损失。

论文没有给出 Chrome 回归的因果分析。本文也不把它归因于某一种数据错误、训练混合比例或 harness 行为。部署后需要在相同基座、相同 prompt、相同 executor 和相同任务集下重测。

两个 Chrome 分域的分母只有 46 和 17，论文没有报告这些分域的置信区间。它们足以暴露风险，无法单独估计稳定的回归幅度。

## 5. AutoGUIWorld 的造数方式与质量控制

### 5.1 生成链

AutoGUIWorld 先从 OS substrate、视觉外观和初始 GUI state 采样一个世界描述，渲染 seed screenshot，再生成与 seed 可见内容相容的任务。Meta Planner 预先给出原子动作、预期视觉变化和目标元素；Voyager 读取当前干净截图、计划动作和 rollout context，展开下一屏渲染提示；Image2 以当前截图为参考编辑出下一屏。指向动作由 LocateAnything 等 grounding backend 在 action 前截图上定位。

生成轨迹按 step 转成训练样本：输入为任务、action 前截图和此前历史，输出为下一动作及其动作点。它建模的是 action-conditioned visual transition 和 direct-action policy data，不直接产生本项目所需的 evidence ROI 标签。

公开代码把实际模型调用留给外部 adapter。adapter 需要实现 `chat()` 和 `image()`；文本、视觉、QC、图片生成与编辑所用 provider 都不随仓库提供。默认 grounding 可接本地 LocateAnything，另有 MAI-UI 或配置的视觉模型。代码可以复用管线结构，但只有仓库代码无法重建论文同款 Image2、Voyager、planner、QC provider、成本和采样分布。

### 5.2 作者的 QC

作者用 Gemini VLM 对每个 trajectory step 检查适用维度；非视觉 action 的 transition 字段可以记 `na`：

- 目标是否在 action 前截图中存在；
- red box 是否命中目标且范围合理；
- action 在当前界面是否可执行；
- action 前后截图的视觉变化是否与 action 一致。

代码重新计算 structured verdict，避免直接信任模型给出的 overall。作者对 3,390 个可修复的 target box 重新 grounding，再次送审。目标不存在、action 无效、grounding 无法修复或转移不一致的 step 会被过滤。

desktop 审计的精确结果为：

| 审计口径 | 分母 | 不一致 | 比例 |
|---|---:|---:|---:|
| 全部可评 desktop transitions | 42,526 | 1,293 | 3.04% |
| 只保留 active actions，并排除 action 无效、目标不存在、grounding 错误后 | 39,351 | 818 | 2.08% |

过滤后按动作类型的不一致率为：drag 7.58%、scroll 7.09%、text entry 6.35%、hotkeys 3.23%、key presses 2.16%、clicks 0.67%。主要失败包括精确文本或命令被替换、一步提前生成最终排版、action 没产生预期效果、无关内容被改写。

这些是 Gemini VLM checker 的结构化判定。论文没有给出一份独立人审样本来估计该 checker 的漏判和误判，因此 3.04% 和 2.08% 是该审计协议下的检出率，不是合成转移真实错误率的无偏估计。

这些比例不能写成 Chrome 的误差率。论文表 12 只列 Ubuntu 23,625、Windows 14,429、macOS 4,472 个可评 transitions，三者合计正好是 42,526；没有 Chrome 分母。论文的过滤图还明确说明，Chrome 只给出最终保留的 35,209 行，它的此前 stage 数量按 desktop retention ratio 推算。

### 5.3 许可和可复现边界

AGW-35B 模型卡给模型权重标注 Apache-2.0。2026-10-03 核对 AutoGUIWorld 仓库根目录时未见 `LICENSE` 文件，README 也没有声明代码或生成数据许可；79,266 行训练集没有随模型仓库或代码仓库发布。模型权重许可不能自动替代代码和数据许可。若要把仓库代码或作者数据接入正式生产流程，需要先确认相应授权；内部只读研究和方法复现也要保留来源与 revision。

## 6. 对下一观测预测的适配判断

### 6.1 可以直接借用的部分

- 历史输入。AGW 保留近期 screenshot-action history，适合检验较早历史是否能帮助下一观测决策。
- completion-only 边界。作者只监督最后一轮 assistant response，与本项目不监督上下文中 counterfactual `<predict>` 的要求相容。
- 坐标接口。AGW 用 0 至 999 整数点，本项目 ROI 允许 0 至 1000 的 xyxy 边界；两者接近但不完全相同。adapter 必须明确点到矩形的转换、右下边界和 off-by-one 规则，再做几何审计。
- 转移数据。AutoGUIWorld 原生保存 task、before、action、after、grounding 和生成 provenance，可以扩展出 prefix-only ROI 候选、证据充分性和补看分支。
- professional interface 覆盖。AGW 的 grounding 增益提示其视觉定位可作为完整屏 sanity 和候选生成信号，但仍需在本项目 evidence ROI 任务上重测。

### 6.2 不能从论文结果推出的部分

1. ScreenSpot-Pro 在输入里已经给出目标指令和完整截图。它测的是当前屏元素定位；本项目在 `<predict>` 时看不到下一屏，也不能得到目标派生描述。
2. AutoGUIWorld 的空间标签是 action 前截图上的点击目标点。本项目需要的是 action 后下一屏中支持后续决策的证据区域，二者的位置和语义经常不同。
3. AGW 训练成 direct-action agent。让它输出观察计划或 ROI 会改变训练接口，零样本可能回到 `computer_use` tool call、复制刚发动作坐标或依赖固定位置先验。
4. 作者用合成 next screenshot 训练 policy，但没有让 policy 生成 next screenshot。AGW-35B 本身不是公开的 Image2 生成器，不能拿模型权重直接替代 AutoGUIWorld 的 image adapter。
5. 本项目已经看到完整目标图和连续 oracle ROI 下两模型均为 48/48。AGW grounding 更强即使复现，也可能只强化已有的读取端，不一定修复 prefix 到证据区域的映射。

## 7. 建议的数据生成改造

### 7.1 从 AutoGUIWorld step 构造本项目监督

每条候选保留完整但分层隔离的记录：

```text
legal prefix h_t
issued action a_t
hidden next screenshot o_(t+1)
offline task/evidence annotations
acceptable ROI bundles
restricted observation branch
check / revisit / next-action outcome
```

推荐流程如下：

1. 从真实 framework trace 或通过 QC 的合成轨迹取得 `(h_t, a_t, o_(t+1))`。生成期间的 Meta Planner 目标、未来动作和 after 描述只放在离线标签侧。
2. 在隐藏的 `o_(t+1)` 上标出完成下一决策所需的 evidence，生成一个或多个 `acceptable_bundles`。bundle 内各区域是 AND，不同 bundle 之间是 OR。
3. 用合法 prefix 生成候选 ROI。输入只含已观察历史和刚发动作；对下一屏像素、未来动作、答案和 target-derived hint 做字段级 denylist 与扰动审计。
4. 只渲染获准的连续 ROI，运行 reader 和 `<check>`。证据不足时产生 `<revisit>` 分支；首次 ROI 没有完整覆盖不自动成为负例，要根据完整计划效用分层。
5. 把完整屏、oracle ROI、模型 ROI、固定中心、复制动作和随机位置作为并列对照。旧拼格 renderer 留作实验对照，不作为默认显示方式。

合成数据优先填补真实轨迹稀缺的界面状态、同布局换内容、布局变化 hard negative、无变化或等待动作、精确 revisit。它不应把 GUI-Xplore 这类缺任务意图的数据改写成“真实任务预测”。

### 7.2 本项目必须新增的 QC

| 层 | 检查 | 失败处理 |
|---|---|---|
| 因果输入 | prefix 中是否出现下一屏、未来动作、答案、target-derived 描述 | 整行隔离，不做自动修补 |
| action 前状态 | 目标是否存在、action 是否可执行、grounding 是否正确 | 修 grounding 后重审，仍失败则剔除 |
| action 后转移 | 局部效果是否正确，精确文本/数值是否保真，未触及内容是否保持 | transition 剔除或重生成 |
| evidence | ROI 是否包含支持下一决策的充分证据，`not_present` 是否有终止性证据 | 改标签或剔除，不把“没看到”当“不存在” |
| branch | predict、实际 crop、check、revisit、结果是否由 hash 和 lineage 绑定 | 分支整体隔离 |
| split | seed、site、session、任务模板、近重复布局是否跨 split | 以最粗相关组重新切分 |
| judge | 低成本 judge 与独立复核在各 action/domain 上的分歧 | 分层报告，不用 pooled 接受率替代 |
| Chrome | 真实浏览器回放、DOM 外最终状态、登录/动态内容、滚动与输入 | 独立报告，不沿用 desktop retention ratio |

AGW、planner、Image2 和 QC judge 不能组成没有独立检查的闭环。尤其不应让 AGW 同时提出浏览器动作、给 evidence ROI、判定 transition 合格，再用这些行训练 AGW 系模型。小份独立复核要按平台、动作类型、任务阶段、是否合成、是否需补看分层；复核者身份和是否看过完整下一屏要记录。

每行至少保存以下 provenance：source 和原始许可、seed/site/session/task family、planner 和 image backend revision、grounder、judge 版本、before/action/after hashes、真实授权 pixel mask、ROI bundle、renderer、branch lineage、split、审查状态。训练时只读通过门的 completion-only export；原始产物保持 append-only。

## 8. 部署和评测门

### G0：制品门

- 固定模型 revision `855c909f96f604ff0533a9a8eee23e348c08df93`；
- 固定所参考的 AutoGUIWorld commit `7d3a063f3538cb4a6216c7da9dbae320b010ca2d`；
- 16/16 权重分片、index、config、processor、tokenizer、chat template 均存在且可读；
- 核对 70,214,494,016 个 LFS file bytes、70,214,363,872 个 tensor payload bytes 和每个 LFS SHA；
- 记录模型卡与配置快照，不把进行中的目录当完整 checkpoint。
- 模型卡和 Hub metadata 的 `license=apache-2.0` 按固定 revision 记录；模型仓库树中没有独立 `LICENSE` 文件，因此本文不另行确认其法律效力。代码、生成数据或外部 provider 进入正式流程前，单独取得并记录使用授权。

### G1：H910C 运行时门

在目标 worker 内核对实际 Python、torch_npu、Transformers、vLLM/vLLM-Ascend 版本，确认它们识别 `qwen3_5_moe`、视觉 processor、Gated DeltaNet 和 MoE。模型卡的 GPU `vllm serve` 命令只作参考，不能直接作为 NPU 通过证据。

先做 config/processor smoke，再做 BF16 权重加载。TP 数量根据 worker 实测和实现约束确定，不从论文的 GPU TP2 或现有 Qwen3-VL 经验外推。引擎加载后保持常驻，避免为每个 stage 重复启停。

G1 按 backend 分开判定，vLLM 与 HF eager 不能互相代替。功能通过至少需要：该 backend 的全部 rank 就绪；没有阻断执行的缺算子、fallback 精度错误或 shard 缺失；一张真实截图能产生非空模型文本；设备映射有回执。这里的“产生文本”是运行时门；原生 `Action:` / tool-call 合规属于 G2，pre-observation ROI 或点格式属于 G3。CPU、FakeEngine 或只读 config 检查不算 NPU 成功。HBM 和吞吐另列为部署资源测量，不改变功能门结论。

### G2：原生交互契约门

用仓库 chat template、`enable_thinking=false`、greedy decoding，检查：

- 单图和多轮 screenshot-action history 都能生成；
- `Action:` 与 `<tool_call>` 结构稳定；
- 0 至 999 坐标合法，动作参数可被 executor 解析；
- `terminate` 的成功声明不代替环境 evaluator；
- 当前屏 grounding 与文本读取用明确分母报告。

单条请求可以用于加载排障，但不能关闭 G2。G2 的最低实测集合是冻结的 97 条显式 query grounding，其中 web 76、mobile 21；请求 ID、hash 和 decode 参数必须在第一次模型输出前写入 manifest。97/97 都要有注册输出，parser failure、越界坐标和非法 action schema 留在固定分母中。这个实验没有在输出前冻结一个小于全量合规的数值容忍度，因此不能事后发明通过阈值；25/97 完整 `Action:` + call 明确没有满足全量 contract，也不足以作为可靠工具接口。box hit 另报，不参与格式合规。若继续优化，接受阈值要在新 held-out 前冻结。这个集合测 current-screen 接口与坐标，不覆盖多轮历史；warm/current-only 历史由 G3 的冻结 cohort 检查。

### G3：下一观测协议门

冻结一个 AGW adapter prompt，让同一常驻模型分别执行：

1. prefix-only `<predict>`，输出连续矩形 ROI；
2. 获得受限下一屏后执行 `<check>`；
3. 证据不足时给一次 `<revisit>`；
4. 获得补看后输出下一动作或弃答。

请求生成前运行 leakage audit。模型若持续输出 direct-action tool call，先报告格式不相容；不要把 parser 后处理伪装成模型已经学会 ROI 行为。

G3 使用冻结的 14-case cohort，不以任意小样本关闭：direct/current-only、direct/warm、plan/current-only、plan/warm 各 14 条，共 56 个 final responses。四个阶段的适用请求都要注册；parser failure 留在分母并编码为 B，runner 自身不得丢输出。所有请求必须通过 leakage audit。模型合法弃答计入研究结果。ROI 命中和最终语义没有在本文预设通过阈值，它们由 G4 calibration 冻结后判断。

### G4：冻结评测矩阵

| 目的 | 数据与分母 | 条件 | 主读数 |
|---|---|---|---|
| 完整屏 sanity | 显式 query 97 条 | 完整目标屏 | semantic grounding；strict 并列 |
| 读取 sanity | evidence fields 48 个 | 完整目标图、oracle 连续 ROI | 语义读对；格式单列 |
| 几何诊断 | 13 个带框 case、23 个字段 | AGW ROI、固定中心、复制动作、随机、oracle | evidence center/area coverage、case hit |
| 单轮受限读取 | 14 cases；每条选区路线合计 48 个 field-arm 单位，每历史臂 24 | current-only/warm；AGW ROI | 读对、AU、CU、错误、证据可见性 |
| 完整行为链 | 14 cases × 4 条件 = 56 final responses | predict、check、一次 revisit | OK/L1/L2/L3/B；调用与像素成本 |
| 旧 proxy 回归 | eval111：web 80、mobile 31 | 同协议输出 | next-click proxy，明确不是 evidence 或 success |
| Browser task 回归 | 新冻结真实 Chrome 任务集 | base Qwen3.5 对 AGW | 环境 task score/success、action 类型分层 |

AGW 与 Qwen3.5-35B-A3B 基座必须用同一 harness、prompt、processor、decode 和 executor 比较，才能估计 AutoGUIWorld SFT 的变化。Qwen3-VL-32B 可以作为项目现状参照，但不能替代同基座 A/B。

表中的 48 是同一批 24 个需新观察字段在 warm、current-only 两个历史臂上的配对读数。8B direct/warm 缺一条请求，其 2 个字段仍留在 48 分母中。报告配对差异时不得把 48 当作独立样本数。

完整行为链的四个条件沿用现有诊断：直接选区 × current-only、直接选区 × warm、先写观察计划再选区 × current-only、先写观察计划再选区 × warm。每条件 14 个 case，所以每模型共有 56 个 final responses。

现有 14 cases 含 8 train、3 calibration、3 test，6 个 case 是同一 OSM 模板；eval111 也不是纯 held-out。它们适合 smoke 和诊断。最终判断需要新的 session/site/task-family clean split，阈值在 calibration 后、查看 held-out 前冻结。

### G5：Chrome 决策门

下列条件全部满足后，才能把 AGW 用作 browser 数据主 teacher：

- 相对同基座的真实 Chrome task 指标没有不可接受回归；允许幅度需在看 held-out 前冻结；
- typing、scroll、drag、动态页面、登录态和跨页状态分别有分母；
- prefix-only ROI 相对固定中心、复制动作和随机基线有增益；
- 受限观察后的错误没有被完整屏 grounding 分数掩盖；
- judge 在 Chrome 上有直接审计分母，不能套用 desktop retention ratio；
- 聚合得分、Chrome 分域和 CU/BU 回归同时报告。

角色分三级。通过 G0 至 G3 后，AGW 可以提出候选，但标签与接受决定必须来自独立证据和 judge。非 browser 分域通过对应的 G4 评测后，才可以成为该分域的主要 teacher；browser 还必须通过 G5。现有证据不支持把 AGW 设为任何分域的唯一 teacher 或唯一 judge。

G5 的真实 Chrome task set、评分规则和允许回归幅度仍由用户与主实验协议决定，必须在查看 held-out 前冻结。本文冻结时 G5 为 `not_measured`，没有通过。

如果 Chrome gate 失败，AGW 仍可作为 desktop 或 full-screen grounding 的候选提议器，也可提出 hard negative；每个用途仍需独立验证。browser 主线继续以真实 framework trace 和通过独立 QC 的数据为准。

## 9. 当前执行状态和后续追加位置

截至 2026-10-03 06:41:40 CST（UTC+08:00）：

本节按时间顺序保留排障过程。前面各阶段写的“尚无 ready”或 `not_measured` 是当时状态，后面的终态条目覆盖它们。`vLLM runtime r4` 与 `HF eager r4` 属于两个独立运行族。

- `$data` 在本文指 `$DATA_ROOT`。第一次下载因网络 `IncompleteRead` 退出 1，固定 revision 的第二次续传退出 0；`reports/agw_20261003/model_verification.json` 对 16/16 分片逐一核对大小和 SHA256 全部通过。`artifact_audit.json` 同时核对了 index、config、processor、tokenizer、chat template 和两种 bytes 口径，G0 为 PASS。
- r1 作业 `62627704` / `psxg5t6xrs7fieen` 提交到 `efficient_910c`，配置为 1 worker、16 个 H910C die。它在进入 worker 脚本前失败，平台 stderr 为 `bash: cu_model/jobs/phase1c/worker_bootstrap.sh: No such file or directory`。提交 cwd 把项目内容直接打包到 `/workdir`，脚本路径仍多写了一层 `cu_model/`。这是一项 bootstrap 路径失败，不是模型加载、processor、NPU kernel 或 decode 失败。共享目录里预建的空 `WORKER_READY` 文件不能证明 r1 worker 就绪。
- 用户提供的新镜像为 `registry-offlinebiz.sankuai.com/custom_prod/com.sankuai.data.hadoop.gpu/aipnlp/serving_h910c_vllm030_rollout_a7a67786:1.0.0`。r2 尝试从父目录提交，HOPE 在生成 app 前开始复制项目外的历史模型；主执行代理终止了本地打包，清理了它的私有临时副本，没有生成 r2 作业。r3 从项目目录提交，将 worker 脚本相对路径改为 r1 实际落盘的 `jobs/phase1c/worker_bootstrap.sh`；run `62628822` / app `psxg68txrs7fieen` 已通过 `hopex` creator/container 身份门，共享 `WORKER_READY` 非空。配置与回执见 `jobs/agw/`、`logs/agw_20261003/submit_r3.log`。
- r3 worker 内 `query_pkg_version.sh` 报 CANN runtime、acl 和 hccl 9.1.0。`probe/runtime_r1.json` 记录 Python 3.11.13、torch 2.10.0+cpu / torch-npu 2.10.0.post4、Transformers 5.14.1、vLLM 0.30.0+empty、vllm-ascend 0.1.dev1+gb64b4d714.d20260929；16 个 NPU 可见，`Qwen3_5MoeConfig`、`Qwen3VLProcessor`、单图模板占位符和 vLLM Ascend plugin 导入通过。这个早期回执只关闭 G1 的配置和导入部分；后续 vLLM 与 HF eager 结果分别见本节末尾。
- vLLM CLI 初次启动在模型加载前失败：Ascend Triton 用 `/usr/bin/clang++` 编译 `npu_utils` 时，编译器报 `Error waiting for child process: No child processes`，却返回 0、没有写出 `.so`。同一 worker 内将 `CC` 只对命令设为 `/usr/bin/g++` 后，扩展编译生成 709048-byte `.so`，`vllm serve --help` 退出 0。后续服务命令将带这个环境变量；这证明 CLI 初始化可恢复，尚不证明 AGW 权重加载或图像 decode。
- 加载日志同时出现 `GDN decode kernel: cuda`。上游 [vLLM 默认值与打印代码](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py#L506-L528)会打印该标签；[vLLM-Ascend 的 GDN patch](https://github.com/vllm-project/vllm-ascend/blob/4ebb3090fc3c13c26557dcaae353882e70246649/vllm_ascend/patch/worker/patch_qwen3_5.py#L205-L225)随后将 forward/decode 替换为 Ascend 实现。因此这行本身不足以判定在 NPU 上调用 CUDA，也不足以判定通过；当前定制镜像仍需真实多 token 图像解码验证。
- 首次服务 jid `jmurd5fhjkwb` 在加载中被主动停止：只读审计发现该命令遗漏了冻结协议的 `min_pixels=100352`、`max_pixels=401408` 和显式多图上限。主执行代理只终止了同一 worker 内属于这次服务的进程组，pod 和身份门仍健康；旧评测等待进程也在首个模型输出前停止，旧输出目录为空。此过程没有重提 HOPE 作业。
- 修正版 `scripts/agw/start_server.sh`（SHA `de67d6c0dd26fc5cbac1ee256292993d3238e5584e6c537fa0809de54718c1df`）在原 pod 启动为 jid `jmure7gsxhzz`，日志 `$data/cu_model/agw_20261003/run_vllm030_r3/logs/server_r2.log` 显示实际参数含 `image:9` 和上述像素范围。04:17 时权重加载到 15/16，尚无 ready 或真实截图 decode。`reports/agw_20261003/eval_manifest_r2.json` 在首个输出前封存 17 个文件 SHA、固定请求与独立 `outputs/runtime_r2/`；开发机和目标 worker 的前置检查都通过。新评测等待进程 jid `jmurem16y4pa` 只会在 API ready 后依次执行两次单图、一次七图烟测，再跑 28 direct、28 plan 和 97 native grounding。烟测通过只说明多模态 HTTP 接受与有限文本解码；视觉内容正确性和任务能力由后续样本单列。
- 该 runtime r2 服务随后完成 16/16 权重加载，但在 vLLM 计算 KV 可用内存的首次 forward 中失败。日志定位到 `vllm_ascend/ops/triton/layernorm_gated.py`：镜像内 Triton-Ascend 给 bundled `hivmc` 传入 `--enable-triton-kernel-compile=true`，后者不识别该参数；一个不加载 AGW 权重的小 NPU layernorm 探针复现同错。r2 服务和等待进程已停，`outputs/runtime_r2/` 仍为空，不能把它当作 AGW 模型失败或视觉推理分数。
- 同一 pod 的 runtime r3 采用更窄的 [vLLM 原生 custom-op 配置](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/config/compilation.py#L502-L514)：只关闭 `rms_norm_gated` 的 [Ascend Triton 实现](https://github.com/vllm-project/vllm-ascend/blob/4ebb3090fc3c13c26557dcaae353882e70246649/vllm_ascend/ops/layernorm.py#L128-L215)，让 vLLM 使用 [原生 PyTorch forward](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/model_executor/layers/layernorm.py#L197-L311)。镜像包、CANN/Triton 安装文件均未改。`eval_manifest_r3.json` 在首个输出前重新冻结脚本 SHA 和 `outputs/runtime_r3/`；开发机与 worker 的 17 项文件/请求前置检查再次通过。服务 jid `jmurf373khh9`、评测 jid `jmurf3h1qqy2` 已启动；本段冻结时尚无 ready 或模型输出。
- runtime r3 也在 API ready 前失败。原因是该镜像的 vLLM-Ascend 平台初始化把 CLI 的 `['all','-rms_norm_gated']` [覆盖回 `['all']`](https://github.com/vllm-project/vllm-ascend/blob/4ebb3090fc3c13c26557dcaae353882e70246649/vllm_ascend/platform.py)，随后再次进入同一 `hivmc` 错误。r3 评测没有模型输出。主执行代理在 worker `/tmp/cu_agw_ascend_overlay_r1/` 放了一份 `vllm_ascend` Python 包副本，只改这项覆盖逻辑，使显式负项保留；原安装包、CANN、Triton 和开发机 ML 环境均未改。补丁前后 SHA、范围与目标路径写在 `probe/ascend_overlay_r1.json`。
- runtime r4 使用这个局部副本，`eval_manifest_r4.json` 在首个模型输出前冻结 19 项文件 SHA、像素预算、禁用项和独立 `outputs/runtime_r4/`。开发机与 worker 的前置检查都通过；服务 jid `jmurfdqekm6s`、评测等待 jid `jmurfe0ld6gk` 已启动。启动日志里 CLI 与 EngineCore 的 `custom_ops` 均保留 `['all','-rms_norm_gated']`，这是配置生效证据；本段冻结时仍需模型加载、profile 和真实图像 decode。
- runtime r4 后来又在同一 Triton 算子失败。轻量 NPU dispatch 探针发现 Ascend OOT 注册会把该类命名为大小写敏感的 `RMSNormGated`：只禁用 `-rms_norm_gated` 仍走 `forward_oot`，禁用 `-RMSNormGated` 则走 `forward_native`。结构化回执在 `$data/cu_model/agw_20261003/run_vllm030_r3/probe/custom_op_dispatch_r5.json`。r4 服务和等待进程已停，输出目录为空。runtime r5 在同一局部插件副本上同时列出这一个算子的两个名称 `['all','-RMSNormGated','-rms_norm_gated']`；`eval_manifest_r5.json` 于首个模型输出前冻结 21 项文件 SHA 与独立 `outputs/runtime_r5/`。本地和 worker 的前置检查通过，服务 jid `jmurfskh23om` 的 CLI、EngineCore 日志均保留这两个负项；profile 和真实图像 decode 仍待实测。
- 后续分层排障揭示这个镜像的编译器错配影响不止一个核：r5 绕过 gated norm 后，Qwen3.5 多模态 split-QKV/MRoPE 融合核失败；r6 在局部插件副本里用已有拆分 QKV/norm 与原生 MRoPE 路径，模型、KV 内存和多模态 encoder profile 通过，却被无条件执行的 `penalties` Triton 预热阻断；r7 只跳过可选预热后 API 达到 ready，但首条注册单图请求在必需的 `compute_slot_mapping.py` Triton 核处返回 HTTP 500，EngineCore 退出。三个版本各有独立冻结 manifest 和空/错误回执目录，没有可用模型回答。r7 的 `probe/eval_sequence_r7.rc=1` 与 `outputs/runtime_r7/smoke_single_a.jsonl` 只证明一次 0.461 秒的 HTTP 错误，不能当视觉能力结果。主执行代理已清理该服务，HOPE worker 仍在，准备独立的 Transformers eager smoke。
- vLLM 路径截至本次更新仍为失败。HF eager 的 G1/runtime 通过不能改写 vLLM 结论：vLLM 没有产生一条有效视觉回答，连 G1 都未通过。
- HF eager r4 由 `reports/agw_20261003/hf_eval_manifest_r4.json` 在首个输出前冻结：revision `855c909f…`、BF16 eager、`max_model_len=8192`、`100352..401408` 像素预算、两张 NPU 的 device map、请求和 scorer SHA、独立输出根。`hf_eager_r4/model_ready.json` 记录 `Qwen3_5MoeForConditionalGeneration` 在 `npu:0`、`npu:1` 完成加载，device-map SHA 与预期一致。两次相同单图请求都 `status=ok`、各 55 completion tokens、文本逐字相同；七图请求 `status=ok`，生成 64 tokens 后以 `length` 结束。`smoke_audit.json` 为 PASS。这些结果验证 HF processor、两 NPU 权重加载和有限 eager decode，不是视觉内容正确率。
- direct 的主结果使用未改写原始输出 `$data/cu_model/agw_20261003/run_vllm030_r3/hf_eager_r4/outputs/direct_all.jsonl` 和预注册严格 scorer。28/28 请求均 `status=ok` 且以 `stop` 结束，但所有回答都在点 JSON 前加了 `# Step N:`，严格点解析为 0/28；因此严格几何为 0/46 个 eligible field center。几何 scorer 把模型点映射为 8×8 网格中离它最近的 8 个格心；assistant 标注 evidence box 的中心格落入这 8 格才算 hit。23 个有框字段 × warm/current-only 两臂形成 46 个配对的 field-arm 单位，不是 46 个独立样本；旧 E2 的 48 个语义单位还包括每臂 1 个没有 evidence box 的字段。几何命中不等于任务准确率、在线成功或完整 check/revisit 链成功。
- 两套事后文件只用于诊断格式错位：`hf_r4_direct_step_wrapper_posthoc_audit.json` 要求完整匹配 `# Step N:\nPAYLOAD` 且 N 等于请求当前步加一，然后原样把 PAYLOAD 交给同一个严格点 parser，不读标签、不修坐标。28/28 的头和步号匹配；去头后 27/28 可解析，剩余一条多一个 `}`。`hf_r4_direct_step_wrapper_posthoc_geometry_summary.json` 在 warm 为 1/23 field-center hit、current-only 为 0/23，合计 1/46。该结果不能替代原始输出严格 0/28，也不进入主结果。
- plan 原始输出已完成 28/28，全部 `status=ok`；finish reason 为 20 条 `stop`、8 条 `length`，后者触及 192-token 上限。`hf_r4_plan_blind_summary.json` 是 fresh-context、模型辅助的主观审阅，只读取冻结 plan 请求和原始输出，未访问 evidence、标签、未来或目标图、scorer 和本报告。它只判断回答是否明确包含提示要求的组件：下一屏具体信息 17/28、近似屏幕位置 9/28、具体可见历史依据 1/28、显式不确定性 17/28。这四项是可重叠的独立二值判断，各自分母均为 28；四项全部具备 0/28。另有 11/28 被标为 `truncated`：8 条以 `length` 结束，另 3 条虽为 `stop` 但句子或结构不完整。缺失组件无法与截断影响干净分离；这些数不评预测正确性、证据覆盖、任务成功或历史增益。
- `hf_eager_r4/terminal_audit.json` 为 `status=complete`、`stage=complete`，绑定 manifest SHA `5bd05204bd43865892fb51246b82364fd64617c15e30dc1a5d509132c42675ba`。固定计数为重复单图 2、七图 1、direct 28、plan 28、native grounding 97；worker app 为 `psxg68txrs7fieen`，两张 NPU 可见。这个 terminal audit 说明冻结的 HF eager 序列完整落盘，不等于 G2/G3 能力通过。
- native grounding 的主 scorer 使用全部 97 条原始输出和 source-derived target boxes。97/97 有响应；严格 `{point, confidence}` JSON 为 0/97；原生 `computer_use(left_click)` 工具调用与完整 `Action:` + call envelope 都是 25/97，有 15/97 的坐标落入 source-derived box。web 为有效格式 17/76、box hit 9/76；mobile 为 8/21、6/21。工具格式和完整 contract 在本批恰好给出相同计数，不表示两个检查定义相同。box 不是 human gold，15/97 也不是 grounding accuracy 或任务成功率。
- native 的标签盲事后语法审计另行保留主 scorer 不变。`adapt_native_serializer_posthoc.py` 是看过输出语法后才定义的固定 token grammar，先核对 97 条请求、输出和 lineage，再在不打开标签的情况下分类并提取唯一 `left_click` 坐标，最后才与 source boxes 连接。它容忍的错误只限两个已枚举的键标点损坏；不修 JSON、不搜任意数字、不忽略尾部文字，也不在多个坐标中择一。结果为 95/97 可解析、source-box hit 62/97，其中包括主结果已有的 25 条合法格式和 15 个 hit，并额外恢复 70 条损坏格式与 47 个 proxy hit；web 为 75/76、47/76，mobile 为 20/21、15/21。97 条互斥类别是：主格式合法 25、`arguments` 键损坏 51、`arguments` 与 `coordinate` 键同时损坏 18、仅 `coordinate` 键损坏 1、外壳或 tool body 不完整 1、合法 JSON 但动作为 `long_press` 1。`hf_r4_native_posthoc_audit.json` 对脚本与全部源 SHA 复核为 PASS。由于规则是在看过输出语法后制定，这 95/97 与 62/97 只能诊断 serializer，不是预注册格式合规、可执行 tool interface、human-gold grounding accuracy 或任务成功。
- `hf_r4_latency_summary.json` 记录同一常驻模型在两张 NPU 上顺序执行请求的离线 HF eager 时延：模型加载 8.145 秒；direct 28 条的中位数 7.356 秒，plan 28 条 20.698 秒，native 97 条 14.778 秒。它不是 vLLM 服务时延，也没有测并发吞吐或 TTFT。
- HF eager 仍未执行受限观察、`<check>`、`<revisit>`、真实任务 rollout 或同基座 Chrome A/B。当前证据关闭 G0；按 backend 判，HF eager G1 为 PASS，vLLM G1 为 FAIL。G2 未通过，原生完整 Action+call 只有 25/97。G3 未通过，direct 严格点为 0/28、plan 四项齐备为 0/28，且完整链没有运行。G4 只得到 proxy 读数，G5 为 `not_measured`。任何后续 adapter 诊断都要与严格原始结果并列，不能替换。
- 自有作业 run `62628822` / app `psxg68txrs7fieen` 在评测和审计落盘后执行 `hope stop`，返回 rc 0；随后 live `hope status --nocache` 为 `STOPPED`，`efficient_910c` queue resource JSON 不再包含该 app，`hopex` 已解绑。`reports/agw_20261003/stop_verified.json` 在 2026-10-03 06:25:26 CST 固化平台状态、queue absence、stop CLI log SHA 和 terminal-audit SHA。平台接受停止和资源实际释放均已核对，当前不占用该队列资源。

![三面板横向条形图。左图是 28 条下一屏点请求：Response 28/28、Strict JSON 0/28、事后去 step 头的点 27/28。中图是 46 个 assistant 标注 evidence field-arm 单位：严格命中 0/46、事后命中 1/46。右图是 97 条当前屏 grounding：Response 97/97、Tool valid 25/97、Tool hit 15/97、Full contract 25/97、Full + hit 15/97。图下注明事后解析不是协议合规，box agreement 不是任务成功。](../reports/agw_20261003/figures/hf_r4_gates.png)

图 AGW-HF-01｜HF eager r4 的冻结离线门。Direct 的 28 条是 14 case × warm/current-only 两臂；几何的 46 个单位是每臂 23 个有框字段，按两臂配对，不能当作 46 个独立样本。右图只画 native 主 scorer，不含后看输出定义的语法容错。整图不包含 plan 主观组件审阅、真实任务或 Chrome holdout。配套可复算数据为 `reports/agw_20261003/figures/hf_r4_gates.table.json`，SVG 为同目录 `hf_r4_gates.svg`。PNG 已按原分辨率检查，中图已标为 “46 paired field-arm units”，条形数值、分母说明和限制脚注与 table JSON 一致。

![两个横向条形图。左图比较从 97 条原生工具输出中取得唯一 left-click 坐标的数量：完整可执行 contract 25/97，事后固定语法容错 95/97。右图比较坐标落入 source-derived box 的数量：完整 contract 15/97，事后语法容错 62/97。图下注明事后语法从损坏文本读取唯一坐标，这些调用不是可执行 JSON，也不是任务成功证据。](../reports/agw_20261003/figures/hf_r4_native_serializer_gap.png)

图 AGW-HF-02｜当前屏 native serializer 的主结果与事后诊断差距。橙色 95/97 包含原本合法的 25 条和额外恢复的 70 条；只有这 70 条是损坏且不可按主 contract 执行的格式。橙色条来自看过输出语法后定义、标签盲并独立复核的固定 grammar；它可以诊断大部分回答仍含唯一坐标，不能提升 25/97 的完整 contract 主分。source boxes 是记录动作框代理，不是 human gold。配套数据为 `reports/agw_20261003/figures/hf_r4_native_serializer_gap.table.json`，SVG 为同目录 `hf_r4_native_serializer_gap.svg`。PNG 已按原分辨率检查，标题、数值、坐标轴和限制脚注可读且与 table JSON 一致。

下一步若继续方法验证，应另行构造 G3 的受限观察、`<check>`、`<revisit>` 完整链和真实 Chrome holdout；现有 97 条 current-screen proxy 不能替代。vLLM 的必需 Triton 核编译问题仍是独立部署阻断，HF eager G1/runtime 通过不能关闭它。当前 worker 已停止并释放；任何后续提交遵循项目 HOPE 规则。

## 10. 事实核查记录

| 事实 | 一手证据 | 本文用法 |
|---|---|---|
| 模型 revision、16 shards、BF16、配置 | AGW-35B 模型仓库 API、`config.json`、`model.safetensors.index.json` | 制品门和运行时假设 |
| 79,266 样本及四域构成 | 论文 §4.1、模型卡 Training Data | 保留各域分母 |
| 训练设置和 last-round loss | 论文 Appendix B、模型仓库 `args.json` | 与本项目 completion-only 边界比较 |
| 五个 benchmark 的分母和指标 | 论文 §5、Appendix C、模型卡 Results | 不混合 mean score、success、grounding accuracy |
| Chrome 46 和 17 个任务的回归 | 论文 Figure 9 及 §5.2 | 独立 Chrome gate |
| desktop transition audit | 论文 Appendix F，42,526 与 39,351 两个分母 | 不外推为 Chrome 质量 |
| Chrome 上游数量为推算 | 论文 Figure 16 caption | 要求 Chrome 直接 QC |
| 外部 adapter 不随仓库提供 | AutoGUIWorld `docs/backend.md` | 说明代码可复现边界 |
| 本项目 111、23、48、56 等分母 | 累计报告 §2、§3、§6、§7、§8 | 设计本地评测矩阵 |
| HF eager r4 模型加载与 smoke | `hf_eval_manifest_r4.json`、`hf_eager_r4/model_ready.json`、`smoke_audit.json` 和三份 smoke 原始输出 | 只证明加载、processor 与有限 decode |
| direct 严格 0/28 | `hf_eager_r4/outputs/direct_all.jsonl`、`hf_r4_preobs_direct_summary.json` | 主格式与几何结果 |
| 去 step 头后 27/28、1/46 | `hf_r4_direct_step_wrapper_posthoc_audit.json`、`hf_r4_direct_step_wrapper_posthoc_geometry_summary.json` | 事后格式诊断，不替代主结果 |
| plan 组件盲审 | `hf_r4_plan_blind_rows.jsonl`、`hf_r4_plan_blind_summary.json` | 主观结构审阅，不评正确性 |
| native 97 条原生格式与 box proxy | `hf_eager_r4/outputs/native_grounding_all.jsonl`、`hf_r4_native_grounding_summary.json` | source-derived box agreement，不是 human gold 或任务成功 |
| native 事后语法容错 95/97、62/97 | `adapt_native_serializer_posthoc.py`、`hf_r4_native_posthoc_{audit,summary,rows}` | 后看语法诊断，不是可执行 contract 或主结果 |
| HF r4 完整落盘 | `hf_eager_r4/terminal_audit.json`、manifest SHA `5bd052…` | 证明固定序列 complete，不证明协议能力 |
| HF eager 离线时延 | `hf_r4_latency_summary.json` | 双 NPU 常驻顺序请求，不是 vLLM 服务时延 |
| HF r4 汇总图 | `hf_r4_gates.{png,svg,table.json}` | 只画冻结 offline proxy；PNG 已视觉检查 |
| Native serializer 差距图 | `hf_r4_native_serializer_gap.{png,svg,table.json}` | 主格式与事后 grammar 并列；PNG 已视觉检查 |
| r3 生命周期终态 | `stop_verified.json`、stop CLI log、live no-cache `STOPPED`、queue resource 无 app、`hopex` 解绑 | 证明平台停止且资源释放 |

本文把作者报告与本地实测分开。本地 HF eager 序列已经 complete，包含加载、smoke、direct、plan 和 97 条 native grounding；其中 direct 严格、plan 主观组件和 native source-box proxy 的证据层级不同。完整行为链、真实任务与 Chrome A/B 仍未测。运行结果追加时应保留失败、严格分母和负面分域，不用事后解析或聚合均值替换。

## 11. 读者测试与文字检查

无前文上下文的读者只看本文后，能够正确回答：当前完成和未测的边界；AGW direct-action 目标与下一观测预测的时序差异；两项 Chrome 回归及分母；AutoGUIWorld 可复用部分与新增 QC；成为 browser 主 teacher 前的门。

运行前的第一轮读者测试发现代码 commit 未固定、AU/CU/L1 至 L3/B 未定义、48 与 56 的单位容易误读、G2/G3 覆盖不足、teacher 角色和许可门含糊、动态状态缺时间。该轮协议文字复读留下真实 Chrome held-out 集和允许回归幅度尚未冻结这一依赖，本文在 G4/G5 中保留为待校准项目。

HF eager 中间结果写入后又做了一轮无前文读者测试。它正确区分了 vLLM 失败、HF eager smoke、direct 严格主结果、事后去头诊断、plan 主观组件审阅和当时仍在运行的 native 阶段；同时指出 G1 backend 口径、46 与 48、field-center 算法、plan 多标签计数和两个 r4 命名需要写明，以上均已修订。最终复读还把 pre-observation direct 格式诊断从 G2 更正到 G3 前置诊断。

独立事实核查逐项对照论文、固定 revision 的模型文件、固定 commit 的代码仓库、累计报告和 09-30 交接。修正了 aligner 冻结、历史窗口、active-action 审计口径、坐标边界、E2 缺失请求、两种权重 bytes 口径和 r1 失败状态。最终复核没有发现其余材料性数字错误或越界结论。最后的文字检查只改表达，没有改动数字、路径、引用、失败记录或不确定性。

本次 HF eager 更新另由独立代理核对 manifest、model-ready 与 smoke 回执、原始 direct/plan 输出和对应 scorer。28/28、严格 0/28、事后 27/28、1/46、20/8 finish reason 及 plan 盲审计数均与源文件一致；复核后修正了 `truncated` 的定义。终态追加后再次核对 terminal audit、native 97 条主 scorer、时延摘要、两套图表 JSON 和停止回执；第一张图已按事实核查重绘为 46 个配对 field-arm units。

终版无上下文读者能把 25/97、15/97 识别为 native 主结果，把 95/97、62/97 识别为后看语法诊断，并正确列出未测的完整链、真实任务与 Chrome holdout。读者指出第二图的 95 条包含 25 条原本合法格式；正文补写了 25 + 70 和 15 + 47 的关系，第二图也重绘脚注，只把额外 70 条称为不可执行 JSON。终版事实代理复核 posthoc 的 web/mobile 分母、六个互斥类别、G1 至 G5、时延、两图和 STOPPED 生命周期后返回 PASS。
