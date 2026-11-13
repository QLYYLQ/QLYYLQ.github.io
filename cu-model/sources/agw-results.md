# AGW 数据扩展与下一观测链：累计技术报告（2026-10-06）

- 状态：`complete`。T1、T2 core、双 blind review、56 条读取对照、最终 case gallery 和无上下文读者测试均已完成，HOPE 作业已验证 `STOPPED` 并释放 16 个 H910C unit。
- 读者：项目负责人，以及后续接手 CU/BU 数据扩展、训练和评测的研究与工程人员。
- 范围：累计 Phase 1、Phase 1c、AGW-35B 论文与源码核查、2026-10-03 本地部署诊断，以及 2026-10-06 的 T1 自主动作候选和 T2 受限观察链。
- 证据边界：论文指标、本地旧 run 和本次新 run 分开报告。strict 原始输出与 post hoc adapter 分开报告。候选动作一致、来源框命中、字段读取和在线任务成功是不同指标。

## 1. 当前回答

用户提出的两个想法都已完成一部分核查，但都没有完成最终方法验证。

| 想法 | 已完成 | 本次补测 | 本次结束后仍需完成 |
|---|---|---|---|
| 让 AGW 参与真实 observation 驱动的数据 scaling | 已验证模型制品、H910C HF eager 单图与多图解码，并完成当前屏 grounding 和 prefix-only 观察点的离线诊断。旧结果没有通过原生格式门或下一观测门。 | T1 得到 28/28 正常解码，原生完整动作契约 10/28，来源动作类型序列一致 5/28，冻结文本和几何 proxy 全一致 0/28。T2 strict 主链因 point 格式失败为 B 56/56；8 条 adapter-valid final 中双审共同 OK 2、共同 L1 5、未决1，固定 56 agreement view 另含 B48。 | 可重置真实 CU/BU executor、环境最终状态、独立 QC、同基座 A/B，以及加入候选数据后的下游训练增益。T1/T2 是离线 replay，不能替代这些步骤。 |
| 复用 AGW 的合成数据方法 | 已核对 AutoGUIWorld 论文与固定源码。它从 GUI seed 构造任务和动作计划，再用图像编辑器生成后续截图并逐步 QC；AGW-35B 是由 79,266 条合成 step 样本训练出的 direct-action policy。 | 本次 NPU 作业不运行 Image2 或 AutoGUIWorld 合成链，只测 AGW 动作提议与下一观测接口。 | 接入可用的文本、视觉和图像编辑 backend，生成 before/action/after，做独立人审或 judge 校准，并在相同训练预算下比较真实数据、AGW 候选、通过 QC 的合成数据及混合数据。 |

本次 T1/T2 没有通过原生协议门。T1 观察到一批内容上可复核的离线候选，但原生动作契约只有 10/28；T2 strict 主结果为 B56/56。探索性 adapter 路线保留了少量受限观察案例，只能作为接口和错误归因证据。数据飞轮是否有效仍需 T3 的真实环境执行和训练对照；AutoGUIWorld 方法是否能迁移仍需 T4 的合成、QC 和训练对照。

## 2. 项目目标和既有证据

本项目要学习的行为链是：

```text
observed history + issued action
    -> <predict> 下一屏中需要观察的 evidence region
    -> restricted next observation
    -> <check>
    -> optional <revisit>
    -> next action
```

预测发生时，下一屏像素、DOM、URL、未来动作、答案和目标派生描述都不能进入模型输入。下一屏及未来信息只可用于离线标签、裁剪和评分。核心 T2 协议的 `current-only` 已包含当前屏与刚发动作，`warm` 只增加更早历史；两者的差值只测更早历史的边际作用。T1 测的是自主提出当前下一动作，为避免把来源动作喂回模型，它有意从输入中移除了当前 `issued_action`，不能与 T2 的 `current-only` 输入直接等同。

### 2.1 Phase 1 建立的基线

Phase 1 的冻结集含 111 个 transition，其中 web 80、mobile 31。未做本项目训练的 Qwen3-VL-8B-Instruct 和 32B-Instruct 在完整当前屏加明确控件 query 的来源框命中分别为 73/97 和 79/97；在下一屏不可见的 8-cell 预测中，warm 条件分别为 19/111 和 16/111，current-only 分别为 21/111 和 19/111。复制刚发动作位置的简单基线在同 24 例原生焦点诊断中为 10/24，高于 32B 原生焦点的 9/24。

这些标签主要来自下一点击框和轨迹动作，属于 silver proxy。明确控件定位不能代表下一屏预测，next-click agreement 也不是任务成功率。旧 HF 多轮实现还比一次完整目标屏调用慢约 5.9 倍和 7.9 倍，并未显示 token 或时延收益。

### 2.2 Phase 1c 建立的工程门和 14-case evidence cohort

Phase 1c 冻结了 14 个 case，包含 web 6、mobile 6、desktop 2，split 为 train 8、calibration 3、test 3。每个条件有 24 个需新观察字段，其中 23 个带 evidence bbox；warm 与 current-only 合计为 48 个配对字段单位。完整目标图和 oracle 连续 ROI 下，两模型的核心语义读取均为 48/48 supported。模型自选区域下，8B 的两条路线均为 0/48；32B 的 plan 路线为 9/48，direct 路线为 4/48。审查来自 assistant，样本小且不是 human gold。

28 条 assistant-supported completion 已在 Qwen3-VL-8B 上完成 completion-only mask、28 个 optimizer step、双 causal 检查、冻结参数核验、adapter 保存和 fresh reload。它们来自 12 个 transition、10 个 session，只有 634 个 completion token。后续冻结诊断没有加载该 adapter，因此这项结果只关闭训练工程门，不证明行为收益或泛化。

这 14 个 case 的 `labels_only.action_supervision_status` 都是 `unavailable_no_next_action_label`。它们适合测 evidence coverage、受限像素读取和 check/revisit，不能测下一动作正确率或环境任务成功。

## 3. AGW-35B 与 AutoGUIWorld 的关系

用户记忆中的“前置论文方法”是 [AutoGUIWorld 论文](https://arxiv.org/html/2610.01215)。AGW-35B 没有另一篇独立的方法论文；它是该论文用合成 step 数据训练出的下游 checkpoint，也不是公开的下一屏图像生成器。模型接收任务、当前截图和近期历史，输出 `Action:` 描述及 `computer_use` tool call；外部 executor 执行动作并返回新截图。上游制品入口为 [AGW-35B 模型卡](https://huggingface.co/YangC777/AGW-35B)和 [AutoGUIWorld 代码仓库](https://github.com/ImYangC7/AutoGUIWorld)。

模型仓库固定 revision 为 `855c909f96f604ff0533a9a8eee23e348c08df93`，代码核对 commit 为 `7d3a063f3538cb4a6216c7da9dbae320b010ca2d`。作者记录的训练集共有 79,266 条 step 样本：Chrome 35,209，Ubuntu 24,250，Windows 14,778，macOS 5,029。训练只监督最后一轮 assistant response；视觉编码器和 aligner 冻结，语言模型 full-tune，共 3 epochs，最大长度 16,384，global batch 512。

### 3.1 作者报告与 browser 风险

| Benchmark | 分母 | 基座 | AGW-35B | 变化 |
|---|---:|---:|---:|---:|
| OSWorld | 361 tasks | 33.0% | 40.8% | +7.8 pp |
| Windows Agent Arena | 154 tasks | 19.4% | 27.9% | +8.5 pp |
| macOSWorld | 231 tasks | 28.1% | 45.0% | +16.9 pp |
| ScienceBoard | 143 tasks | 14.0% | 32.2% | +18.2 pp |
| ScreenSpot-Pro | 1,581 examples | 31.7% | 57.1% | +25.4 pp |

这些是作者报告，本项目尚未同协议复现。四个交互 benchmark 使用不同指标，论文的聚合均值按 benchmark 等权，也没有把各任务分母合并。

两个 Chrome 分域发生回归：OSWorld Chrome 在 46 个任务上从 39.0% 降到 26.0%，WAA Chrome 在 17 个任务上从 11.2% 降到 0.0%。Chrome 占训练样本 44.4%，较大训练占比没有阻止回归。WAA Edge 同时从 23.1% 升到 30.8%（13 个任务），所以风险需要按浏览器和动作类型分层测量，不能概括成所有 browser 一致退化。

### 3.2 AutoGUIWorld 的生成链和 QC

AutoGUIWorld 的公开方法按以下顺序生成数据：

1. 从 OS substrate、外观和初始 GUI state 采样世界描述并渲染 seed screenshot。
2. 根据 seed 中实际可见的内容生成任务。
3. Meta Planner 生成原子动作、预期视觉变化和目标元素。
4. Voyager 根据当前干净截图、计划动作和 rollout context 写下一屏渲染提示。
5. Image2 编辑当前截图得到下一屏，LocateAnything 等 backend 在 action 前截图上定位指向动作。
6. 将 task、before、action、after、grounding 和历史展开成 step 训练样本，并做逐步 QC。

作者用 Gemini VLM 检查目标是否存在、red box 是否命中、action 是否可执行，以及前后截图变化是否符合动作。3,390 个可修复 target box 会重新 grounding 并再次送审。desktop 可评转移中，checker 在 42,526 条里标出 1,293 条不一致，即 3.04%；排除 action 无效、目标不存在和 grounding 错误后，在 39,351 条 active action 中标出 818 条，即 2.08%。这些是该 checker 的检出率，论文没有独立人审来估计漏判或误判，也没有给出对应的 Chrome 审计分母。

该管线生成的是 action-conditioned visual transition 和 direct-action policy data。action 点位于 action 前截图，本项目需要的 evidence ROI 位于 action 后下一屏，二者必须分字段保存和独立标注。

## 4. 数据和模型能否直接下载

本文中的 `$data` 固定指 `$DATA_ROOT`。

截至本次核查：

- AGW-35B 权重可从[官方模型仓库](https://huggingface.co/YangC777/AGW-35B)下载。模型卡标注 Apache-2.0。本地固定 revision 的 16 个 BF16 shard 已于 2026-10-03 完整下载并核验，当前共享路径为 `$data/models/AGW-35B`。
- AutoGUIWorld 的[官方代码仓库](https://github.com/ImYangC7/AutoGUIWorld/tree/7d3a063f3538cb4a6216c7da9dbae320b010ca2d)可下载，但实际文本、视觉、QC 和图像编辑 provider 由外部 adapter 提供。仓库不包含论文同款服务配置。
- 原始 79,266 条 AGW 训练 step 及其源轨迹没有随模型仓库或代码仓库发布。代码仓库排除了 `data/`。截至 2026-10-06，作者官方仓库中的 [issue #2](https://github.com/ImYangC7/AutoGUIWorld/issues/2) 仍为 open；该 issue 由 Hugging Face 团队成员发起，询问是否上传数据，作者尚未回复或给出下载入口。这是公开托管状态的证据，不代表作者确认了后续发布决定。目前不能直接下载作者训练集做逐行审计或原样续训。
- 2026-10-03 核对时，AutoGUIWorld 仓库根目录没有 `LICENSE`，README 也没有给代码或生成数据声明许可。模型权重许可不能代替代码和数据许可。
- [AgentNet](https://huggingface.co/datasets/xlangai/AgentNet) 是论文中的另一组真实 demonstration 对照数据，不是 AutoGUIWorld 的合成源数据；官方 dataset card 标注 MIT。本地已有 `$data/data/xlangai/AgentNet`，但本报告没有冻结其本地 snapshot revision，不能把它记作 AGW 的 79,266 条训练集。

用户记得的 HDFS 副本在当前已知位置没有找到。开发机和 worker 已检查 `$CHECKPOINT_ROOT/models` 及其 `qwen`、`ours`、`experiments` 命名子目录，没有 `AGW-35B`。本次作业直接读取 DolphinFS 的 `$data/models/AGW-35B`。如果另有精确 HDFS 路径，应先核对目录和分片再切换，不能凭记忆猜路径。

本次按用户要求没有重新计算 70.2 GB 权重哈希。runner 绑定 2026-10-03 的 16/16 全量 SHA 回执，同时核对当前 shard 名称和大小，以及 config、chat template、index 等小文件 SHA，并记录 `live_weight_sha_recomputed=false`。r3 从 DolphinFS 读取模型并在 NPU 0/1 达到 model-ready 的 `load_elapsed_s` 为 940.912 秒，约 15 分 40.912 秒。该时间是本次共享存储到 HF eager 两设备放置的实测账本，不外推为稳定带宽或其他 worker 的加载时间。

## 5. 2026-10-03 的本地 AGW 基线

旧 run `62628822` / app `psxg68txrs7fieen` 在 CANN 9.1.0、Transformers 5.14.1 上完成 HF eager 两 NPU 加载，重复单图 2/2、七图 1/1 smoke 通过。vLLM 在实际视觉 decode 的必需 Triton kernel 上失败，没有有效模型文本，不能把权重加载当成 vLLM 推理通过。

### 5.1 下一观测点和计划

14 case 的 current-only/warm 两臂共 28 条 direct 请求。原始 strict 点 JSON 为 0/28，23 个带框字段乘两臂得到的 46 个几何单位中命中 0/46。所有 strict 解析失败都带生成的 `# Step N:` 头。

冻结结果之后才设计的标签盲 wrapper adapter 只移除精确步号头，得到 27/28 可解析和 1/46 evidence-center 命中。它没有改变原始输出，但属于 post hoc 探索性诊断，不能计作原生协议合规。

28 条 plan 的盲审结果为：说明下一步所需信息 17/28，说明下一屏大致位置 9/28，明确引用合法可见历史 1/28，表达不确定性 17/28，四项同时具备 0/28。11 条输出被截断或结构不完整，其中 8 条达到 192-token 上限。它们只测计划内容覆盖，没有给出完整 check/revisit 或真实任务结果。

### 5.2 当前屏原生动作格式

冻结的 97 条显式目标 grounding 请求全部返回模型输出。主结果如下：

| 口径 | 全部 | web | mobile |
|---|---:|---:|---:|
| 原生完整 `Action:` 加 `computer_use` left-click | 25/97 | 17/76 | 8/21 |
| 原生点落入 source-derived target box | 15/97 | 9/76 | 6/21 |

独立、标签盲的 post hoc grammar adapter 可从 95/97 个输出解析出唯一 left-click 坐标，来源框命中为 62/97，其中 web 47/76、mobile 15/21。原始 serializer 的主要问题是 key 标点损坏。这个诊断说明输出中常有可恢复坐标，却不能把 95/97 或 62/97写成原生可执行率、human-gold grounding 或在线成功率。

这组旧结果支持继续测有界 adapter 和候选提议，尚不支持把 AGW 设为 browser 主 teacher、唯一 judge 或默认执行策略。

## 6. 本次 T1/T2 的冻结设计

### 6.1 T1：真实轨迹观察上的自主动作候选

T1 使用同一 14-case cohort，比较 `current_only` 和 `history` 两臂，共 28 条请求。当前屏截图来自真实轨迹；记录动作单独保存在 label 文件中，不送给模型。history 最多保留最近 5 个含当前步的截图，并追加最多 5 个更早 action-only 描述。

T1 prompt 由 AGW 模型卡的紧凑 system contract 加本项目任务指令组成，不声称复现作者未公开的完整 evaluation harness。该测试主动移除了当步已记录动作，目的是让模型自主提出候选；它与 T2 的 prefix-only evidence point 接口是两个不同任务。

冻结输入 authority 为 [task_proposal_manifest.json](../reports/agw_20261006/requests/task_proposal_manifest.json)：

- evidence 源文件：`$data/cu_model/phase1c/data/evidence_samples.jsonl`
- evidence SHA-256：`32ca544c9edce18eef1b8b39f73fcd931faca77b7ed6a48fdf466548ba1ea8b9`
- current-only：14 行，SHA-256 `259f9eee81d6ec14609239228cbab062e1612057149f5f5825da520f24c84671`
- history：14 行，SHA-256 `6eefde46beddafa64654cc2c9be6758a1cddde64d50c95fe4d053ef64e50559f`
- 离线 labels：14 行，SHA-256 `72d79a78becd2b38f7a1eb6522085033a4b0a136c42e3fe20324e00a154fa703`
- 图像 SHA 引用检查：79 次通过
- `max_model_len=8192`，`max_new_tokens=256`

模型输入排除了 `prediction_input.issued_action`、原始 `action_history`、当前帧的 `action_after`、`labels_only`、目标像素、目标 DOM/URL、未来动作、答案和目标派生提示。真实 processor 的单图和五图 probe 分别为 536 和 2,467 个输入 token，通过固定预算门。

T1 固定报告 28/28 注册输出、原生 schema 合法率、动作类型和坐标可执行率，以及按 case 配对的 history 变化。来源动作只是一条非 human-gold 轨迹示范；与它一致不等于动作唯一正确或任务成功。语义合理性需逐例复核，并记录复核者是 assistant、model-assisted 还是用户。

### 6.2 T2：下一观测受限链

T2 固定为：

```text
14 cases x 2 history arms x 2 point methods = 56 final branches
```

history arms 为 `current_only|warm`，point methods 为 `direct_point|plan_then_point`。direct 分支绑定 2026-10-03 的旧 raw direct 输出；plan 分支绑定旧 raw plan 输出，并在本次 run 新执行 28 条 plan-to-point map。旧输出不会被记成本次作业的新结果。

冻结 authority 为 [T2 preflight](../reports/agw_20261006/t2_preflight/README.md)和 [freeze manifest](../reports/agw_20261006/t2_preflight/freeze/manifest.json)：

- plan 请求 SHA-256：`71f2014a3af5ca9c017d6fa69ce46a64e13affc1003d0aaa97f9711f0cf5b223`
- direct 请求 SHA-256：`d72677a1daf9ac50d9d7c1b04832b54ce74bb773fafd52a2ee929044759b76e6`
- map 请求：28 行，SHA-256 `70309d74a70b24da031554670cdd6bc2774ab96e64bd8213a417a9417e137d99`
- branch ledger：56 行，SHA-256 `aba2d58d8f74bb5f0649a1e2f7411486afc0802c51ee955e9903e63ac2a2256d`
- prediction 图像引用 192 次，对应 79 张唯一图；target 图像进入 prediction 的次数为 0

主解析器只接受仅含 `point:[int,int]` 的 strict JSON。探索性 adapter 只接受精确 `# Step N:\nPAYLOAD`，再把未改动 payload 交给 strict parser。direct 是 prefix 后第一条 assistant response，要求 `N=current_step+1`；plan-to-point map 是第二条 assistant response，要求 `N=current_step+2`。步号规则由冻结 prefix lineage 推导，两条路线的结果分开保存。

合法点映射到 8x8 网格中最近的 8 个 cell。check 只能看到这些真实 crop 及其与 target SHA 绑定的 authorization mask。若模型请求 revisit，最多再开放 8 个此前未授权 cell，累计上限为 16/64。冻结 control 记录含连续 oracle ROI、oracle cell union、完整屏引用、固定中心和 issued-action position；完整屏与 oracle ROI 作为独立 reading controls 执行，不计入 core 56 分支。所有错误、缺失和非法输出继续留在 56 分母中并记为 B。

最终逐分支需报告 evidence coverage、合法证据支持的字段语义、check/revisit 决策、调用次数、输入/输出 token、视觉 token、时延和授权像素预算。OK/L1/L2/L3 需要绑定准确 request/output SHA 的独立审查；若审查由 assistant 完成，须标为 non-human-gold。由于 cohort 没有 next-action label 或 executor，T2 不评分动作正确率和任务成功。

## 7. 新 NPU 作业的执行账本

用户授权一次新作业。唯一提交为 run `62807442`、app `psxhlfcxrs7fieen`、creator `luyuquan`，配置 [agw35b_20261006_hf_task_r1.hope](../jobs/agw/agw35b_20261006_hf_task_r1.hope)，资源为 1 worker、16 个 H910C unit，队列 `root.hldy_training_cluster.hadoop-aipnlp.efficient_910c`。`hope run` 退出 0，`hopex` creator/container identity gate 通过。作业结束后没有自动重提授权。

共享 run root 为：

```text
$data/cu_model/agw_20261006/run_hf_task_r1/
```

输出目录已在开发机预建，worker 对 `probe/shared_write_r1.txt` 的写入通过。运行时为 CANN 9.1.0、torch 2.10.0+cpu、torch-npu 2.10.0.post4、Transformers 5.14.1，16 个 NPU 可见。`accelerate==1.10.1` 只安装在该 worker 的 `/tmp/cu_agw_pydeps`，没有修改开发机或镜像基础环境。

本次同一 worker 上的尝试按时间为：

| evaluator jid | 状态 | 是否加载权重 | 是否产生模型输出 |
|---|---|---:|---:|
| `jmuvk8dszy27` | preflight 发现 runner 会在慢共享存储重算 70.2 GB shard SHA，主动停止，rc143 | 否 | 否 |
| `jmuvkg95u65v` | fail closed：旧检查读取不存在的 processor direct attrs；实际像素限额在 `size.shortest_edge=100352` 和 `size.longest_edge=401408` | 否 | 否 |
| `jmuvklq504y1` | 修正 runner；model-ready PASS，T1 和 T2 map 均完成 28/28，terminal exit 0 | 是，NPU 0/1，940.912 秒 | T1 28/28；T2 map 28/28 |
| `jmuvlt7sgo9h` | T2 check r1 在模型加载前失败；`/workdir` snapshot 缺冻结 branch manifest，错误回执保留 | 否 | 否 |
| `jmuvlvvgyukt` | 补齐并核验精确文件后的 T2 check r2，terminal exit 0 | 是，缓存热后 6.898 秒 | check 35/35 |
| `jmuvmk34ojd1` | T2 revisit r1，terminal exit 0 | 沿用同一 runtime contract | revisit 9/9 |
| `jmuvmr2krp0p` | 独立 reading controls，terminal exit 0 | 是，同一 runtime manifest | full-target 28/28；oracle-rect 28/28 |

当前 runner 为 `scripts/agw/t1_run_hf_eager.py`，SHA-256 `90c21367a2b2c7ae7f38bf91e320546a5d7e5f09c00aab439930e9300e46755a`。模型从 `$data/models/AGW-35B` 加载到 NPU 0/1。T1 输出 root 为 `outputs/t1_hf_r3/`，T2 map 目标为 `outputs/t2/map_r3.jsonl`。

只有满足以下条件才接受本次输出：

1. `model_ready.json` 和固定 runtime manifest 存在，实际 checkpoint、worker、processor 和 runner identity 一致。
2. T1 的 28/28 request ID 都有注册输出，错误也在固定分母内。
3. T2 map 的 28/28 request ID 都有注册输出，check/revisit 保持同一 runtime lineage。
4. terminal audit 绑定输入、输出和脚本 SHA；HOPE `RUNNING` 本身不算模型就绪或解码成功。

以上四项均已通过。

NPU 工作完成后，`hope stop` 退出 0。2026-10-05 19:48:48 UTC 的 fresh status 返回 run `62807442` / app `psxhlfcxrs7fieen` 为 `STOPPED`，queue resource listing 中已无该 app；队列 allocated gcores 从 368 降到 352，remain 从 16 升到 32，与本作业 16 个 unit 的释放一致。本流程没有停止其他作业。权威 [stop receipt](../reports/agw_20261006/stop_verified.json) SHA-256 为 `8a6ea2ff0eb8fcfa2887b5779c0fc3f9ffc3d2c5a147706c3532e759a37242e4`。这是该时间点的终态证据，不替代未来时刻的实时平台查询。

## 8. T1 结果

T1 原始输出 28/28 为 `status=ok`，SHA-256 为 `6024f9fc3432f6466990a87aa77e9b0cc6d20cc642bd061aa4a7a007fd8fe9a5`。权威 [execution receipt](../reports/agw_20261006/t1_preflight/execution_receipt_r3.json) SHA-256 为 `dc43f7371432a9dc00a2de0ff4f9b34b285ab7775554c10f4f957af51e4b2dbd`；它绑定 run/app/worker、model-ready、runtime manifest 和 terminal audit。strict summary 为 [t1_action_summary.json](../reports/agw_20261006/results/t1_action_summary.json)，SHA-256 `3d8292b25b44ce52945a7b7e2f23703abd1d07c9f4158213100b671a22464836`；逐行 scorer SHA-256 为 `b70d06783ae5e63d89262f45ec1b401196dbd147b3a25de151e684ca8fb6b8d4`。

| 指标 | current-only，分母 14 | history，分母 14 | 配对差异 |
|---|---:|---:|---:|
| 注册输出 | 14/14 | 14/14 | 全 14 case 两臂齐全 |
| 正常解码 | 14/14 | 14/14 | 全 14 case 相同 |
| 原生完整 `Action:` 加 `computer_use` 契约 | 3/14 | 7/14 | history 更好/相同/更差为 5/8/1 |
| strict 合法的指向动作 | 2/14 | 4/14 | 合计 6/28；未单独冻结配对方向 |
| 来源动作类型序列完全一致 | 2/14 | 3/14 | history 更好/相同/更差为 1/13/0 |
| 冻结类型、文本和几何 proxy 全一致 | 0/14 | 0/14 | history 更好/相同/更差为 0/14/0 |
| blind reviewer A：supported/plausible、partial、unsupported | 13/0/1 | 9/3/2 | 全部为 22/3/3 |
| blind reviewer B：supported/plausible、partial、unsupported | 12/2/0 | 8/4/2 | 全部为 20/6/2 |

按两臂合并后的 strict 原生契约，desktop 为 4/4，web 为 4/12，mobile 为 2/12。10 个合法输出中的动作类型为 `click` 3、`left_click` 3、`type` 2、`key_press` 1、`terminate` 1。冻结来源标签为 6 条 `CLICK`、3 条 `click`、5 条 `action_list`；展开后只有 5/28 个模型输出的动作类型序列完全一致，最终文本和几何 proxy 仍为 0/28。本 cohort 没有预先确认的 scroll 或 drag 分母。

18 个 strict 失败分为 `tool_call_is_not_strict_json` 8、`invalid_computer_use_arguments` 5、`trailing_or_malformed_tool_envelope` 5。标签盲的 [post hoc syntax audit](../reports/agw_20261006/results/t1_posthoc_syntax_summary.json) 没有应用 repair，也没有恢复额外 tool call，原因是失败横跨空 action、递归或截断结构、来源 schema 拷贝、未解析 placeholder、alias 和非规范 key。探索性结果仍是 10/28，不替换上表的原生格式结果。

两名 reviewer 都只看到冻结的模型可见输入、截图和 raw 输出，没有看到离线动作标签、target screenshot、strict scorer、gallery、既有结论或对方判断。两者精确类别一致 25/28：共同判为 supported/plausible 20、partial 3、unsupported 2，另有 3 条分歧。对比文件 [t1_blind_comparison.json](../reports/agw_20261006/reviews/t1_blind_comparison.json) SHA-256 为 `8f9ee648a6fafb1f1a410e0c28af01902c2ddb0230d94d767097a47d6f5dbbbe`。这些是 non-human-gold 的局部动作内容合理性，不是 action accuracy 或任务成功。两位 reviewer 的格式 rubric 不一致，格式只采用预注册 strict scorer 的 10/28。

T1 说明更早历史在这批 case 上改变了 serializer 合规率，但还没有证明动作语义变好。history 的 strict 合规从 3/14 升到 7/14；两位 reviewer 的 supported/plausible 数反而分别从 13 降到 9、从 12 降到 8，完整来源 proxy 两臂都是 0/14。这个小型、单次解码、assistant-reviewed 结果不足以判断历史有害，至少没有给出历史提高动作语义的证据。desktop 的 4/4 只来自 2 个 case 的两臂，不能外推平台能力。T1 能回答的是 AGW 是否产生可保存、可复核的离线候选；它不能回答候选执行后是否完成任务，也不能用来源动作一致率替代在线成功。

## 9. T2 结果

固定分母和探索性续接的流失关系为：

```text
56 fixed branches
  -> 35 adapter-valid point branches enter check; 21 blocked
  -> 9 adapter-valid check branches request revisit; 26 blocked
  -> 8 adapter-valid final branches; 1 blocked
  -> blind review: agreed OK 2, agreed L1 5, unresolved L3/L1 1

strict-primary track: B 56/56 throughout
```

| 阶段 | 固定分母 | strict 原始输出 | 探索性 adapter | 终态 |
|---|---:|---:|---:|---|
| plan-to-point map | 28 | 28/28 注册输出；strict point 0/28 | exact-header point 8/28 | terminal complete，raw SHA-256 `0c9a7669889c4399c9d1b2753d135269ea458d4a53324db4529790689f72e04c` |
| direct point | 28 | strict point 0/28 | exact-header point 27/28 | 绑定 2026-10-03 raw direct 输出，不冒充本次新输出 |
| 初次 restricted check | 固定 56 ledger；35 个 adapter-valid point 实际进入 check | strict check 0/35 | exact-header check 9/35，全部请求一次 revisit | raw 35/35 `status=ok`，SHA-256 `1e9685d81dcb1c95244006722806d4b7c01148d3b6d25662c35408d6a4f48e7a` |
| revisit | 9 个真实、合法 revisit 请求；最终仍以 56 分支报告 | strict final 0/9 | exact-header final 8/9 | raw 9/9 `status=ok`，SHA-256 `d0ae7f703f8db63a475d65a7a7b8f6cabbe113d52928e391bf7f00374248d7c4` |
| final branch | 56 | B 56/56 | reviewer A：B48、OK2、L1 5、L3 1；reviewer B：B48、OK2、L1 6 | 双审 agree 7/8，一条 L3/L1 分歧保留未决 |

四条件逐项结果：

| 条件 | 分母 | strict / adapter point | evidence center hit，初次到最终，分母23 | exact/alias 字段匹配，分母24 | strict；exploratory reviewer A / B | 调用、prompt/completion token、累计时延 |
|---|---:|---:|---:|---:|---|---|
| direct + current-only | 14 | 0/14 / 13/14 | 0/23 到 4/23 | 2/24 | B14；A B9+OK1+L1 3+L3 1 / B B9+OK1+L1 4 | 32；49,918/1,907；535.828秒 |
| direct + warm | 14 | 0/14 / 14/14 | 1/23 到 2/23 | 1/24 | B14；A/B 均 B12+OK1+L1 1 | 30；104,236/1,666；529.809秒 |
| plan + current-only | 14 | 0/14 / 3/14 | 0/23 到 0/23 | 0/24 | B14；A/B 均 B13+L1 1 | 33；32,850/2,942；755.836秒 |
| plan + warm | 14 | 0/14 / 5/14 | 1/23 到 1/23 | 0/24 | B14；A/B 均 B14 | 33；101,333/1,818；567.299秒 |

表中的 exact/alias 字段匹配合计只有 3/96，但它没有检查答案是否由授权像素支持，不能称语义正确。initial/final center hit 和 bbox coverage 都使用 assistant-reviewed evidence box，属于几何 proxy。四条件的初次到最终平均 bbox coverage 依次为 0.50% 到 18.50%、3.85% 到 11.54%、0.50% 到 0.50%、3.85% 到 3.85%。

固定 56 分支的 machine rows SHA-256 为 `29456422bfda8b9584223457913bef61d449514655f964bad5a1c9e4f35b3ef3`，summary SHA-256 为 `8cfea99800c681a3c3cc06b892cfd62ed0a6c03d038e3fcf7e8433a6619bf018`。模型调用、token 和时延账本包含冻结的 direct/plan prefix 调用及本次 map/check/revisit；时延是各调用记录值之和，不是作业墙钟时间。

探索性 adapter 最后保留的 8 条分支由两名 fresh-context assistant reviewer 根据真实授权 crop、revisit 像素和离线字段独立分类。两者在 7/8 条上一致，其中共同 OK 2、共同 L1 5；`p1c-app-instagram-reviewed:current_only:direct_point` 上 A 判 L3、B 判 L1。项目没有用多数投票或合成 consensus 消除分歧。[agreement view](../reports/agw_20261006/t2_preflight/independent_review/agreement_view.json) 的固定 56 分母为 B48、OK2、L1 5、未决1，SHA-256 `c3f3b89b763a47642cc5b5b247baad9dcd694a311ea0c64d34e786b3f0abcbd5`。审查来自 assistant，属于 non-human-gold；strict 主结果仍为 B56，不受探索性审查覆盖。

共同 OK 的准确口径是 8 条 adapter-valid final 中的 2 条。它不能改写成 2/8 或 2/56 的 AGW 下一观测 accuracy：原始 strict 仍是 B56/56，cohort 只有 14 个 assistant-reviewed case，并且没有真实任务执行或成功标签。

双审逐行 comparison SHA-256 为 `5b8270d237e2773757d628443fe5ade47d835cba0fc7359c5e7a199c1a38bc89`，summary SHA-256 为 `7f21383fc13246799c173bebff66fbedd4131900cf2aaea68d5dec547ee2e687`。reviewer A 固定 56 summary 为 [results_reviewer_A/summary.json](../reports/agw_20261006/t2_preflight/results_reviewer_A/summary.json)，SHA-256 `36c16dad4eafd0bbababc446941f04db3656e31f896d36e2fb11d9fa5f57ab48`；reviewer B summary 为 [results_reviewer_B/summary.json](../reports/agw_20261006/t2_preflight/results_reviewer_B/summary.json)，SHA-256 `5f229b026d7882f768eb431483623def2ee21c566d98b3cd224e4e6623e84632`。

几何侧的连续 oracle ROI、oracle cell union、固定中心和 issued-action position 已冻结。完整屏与 oracle 连续 ROI 的读取结果如下。

### 9.1 完整屏和 oracle ROI 读取对照

这组对照与 core 56 分支分开。它固定同一 14 case 的两条历史臂，共 28 条完整目标屏和 28 条 oracle 连续矩形请求；目标像素在 reader 输入中可见，因此只诊断读取端和输出结构，不测 prefix-only 选区。

| 条件 | 请求正常返回 | native strict JSON | 预注册 step-only adapter | post hoc control-only payload | required-new exact/alias | prompt/completion token | 累计时延 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 完整目标屏 | 28/28 | 0/28 | 0/28 | 3/28 | 5/48 | 61,132/3,419 | 894.035秒 |
| oracle 连续矩形 | 28/28 | 0/28 | 0/28 | 2/28 | 4/48 | 58,412/3,300 | 865.076秒 |

控制输出出现了精确 `# Step N:` 加完整小写 `json` fence 的重复结构。项目在读取字段标签或做语义评分前冻结了仅供 controls 使用的 full-match 规则：步号必须等于请求推导值，移除 fence 后的原 payload 仍须通过原 strict field schema。56 条中 36 条匹配完整 fence，只有 5 条内部 payload 合法；它没有改 raw、native strict、预注册 step-only 结果、字段值或 core 56 分支。

因此，完整屏 5/48 与 oracle ROI 4/48 的差 1 个字段不能解释成完整屏读取能力更强，也不能写成 reader accuracy。51/56 请求在该 post hoc control-only 结构诊断下仍被阻断，而且没有独立像素语义审查。标签是 assistant-reviewed exact value 或预声明 alias，也不是 human gold。

control result [summary](../reports/agw_20261006/t2_preflight/control_results/summary.json) SHA-256 为 `d62026f41f8f44f61af4bc3c8ab5c4afde9a42e852d5185cff722242cc3c76db`；rows SHA-256 为 `45c533d1e998a3a266e8a5383853dcf3b3fdebe84a294a0e8077eafe9a6b89cb`。标签盲 [post hoc audit](../reports/agw_20261006/t2_preflight/controls/posthoc_audit.json) SHA-256 为 `64dd4502377ca8257c7dfab2107ff3f0d474b68b58359420eae92607e6732d87`。

T2 的冻结来源、所有 NPU 输出、review、controls、执行代码和停止回执汇总在 [FINAL_PROVENANCE.json](../reports/agw_20261006/t2_preflight/FINAL_PROVENANCE.json)，SHA-256 `24f6d618bf8f6521b30e379f8b0ba55d71a5c80e508cf32b1eca10c2ed52b7d9`。最终 `py_compile`、`ruff check`、`ruff format --check` 和 selftest r8 均通过。

T2 的 strict 主结果已经被 point wrapper 阻断为 B 56/56。探索性链仍按预定顺序解释：先看几何是否覆盖 evidence，再看模型是否只依赖获准像素读出正确实例，最后看它是否正确判断 sufficient/revisit。若 point 不覆盖 evidence，后续失败主要属于选择问题；若 evidence 已完整可见仍读错，属于局部读取或实例识别问题；若值正确但合法像素不支持，则不能算 supported。

## 10. 供用户后续人工复核的逐例图片

本次实验保留了让人可以直接判断的 case 级产物。终态交付包含：

- T1 每个 case 的当前屏、合法历史缩略图、原始模型输出、strict parse、post hoc parse、来源动作和独立 assistant/model-assisted 语义审查。
- T2 每个分支的目标整图，仅供离线审查；初次授权 mask；实际 8-cell crop；revisit 新增 mask 和累计 16-cell crop；evidence 标注；原始 check/revisit 输出；最终错误分类。
- 同一 case 并排显示 direct/plan、current-only/warm、模型选区与 oracle/固定中心/issued-action 对照。
- 所有图片显示 case ID、branch ID、platform、split、输入和输出 SHA。图注说明颜色代表授权区域或 evidence box，不写成 attention。
- gallery 中同时保留成功、格式失败、几何失败、wrong-instance、false-sufficient、无益 revisit 和不确定案例，不能只挑成功图。

这些图片用于用户在实验结束后逐例检查。报告冻结时如果只有 assistant 或 model-assisted review，应明确标为 non-human-gold，不能写成用户已经完成复核或 human-gold 标签。

早期 T1-only gallery 保留不变。最终 gallery generation 为 `final-with-controls-r3-v2`，包含 T1 14 张、T2 core 56 张和 reading controls 56 张，共 126 张 PNG、67,219,284 bytes。每张图的 SHA、大小和 Pillow decode 均已核验；第一次合并 render 因 namespace join bug fail closed，未写出文件，修复后才生成本版本。

可从[最终紧凑索引](../reports/agw_20261006/figures/case_gallery_final-with-controls-r3-v2.md)逐例打开，索引 SHA-256 为 `23cbf684779caf26adc177e9af0ef1beacd1b92437caff9b99909cc978e3a79f`，本地 manifest SHA-256 为 `3b970522a49984c0006aa742ef6749c420c2d3d754b1b77b5492e04b99e6d516`。共享 HTML 为 `$data/cu_model/agw_20261006/run_hf_task_r1/case_gallery/final-with-controls-r3-v2/index.html`，SHA-256 `4cf2ed98a7579720e2a16e560f1242b5db1d863bc25e186e95f430b3bc51afc6`；共享 manifest SHA-256 为 `8a5189d6d7b1d05644e9c62cc39021bc9401fb99df2a42687a27a0b7e32c4355`。

gallery 显示模型可见截图、raw output、strict 与 adapter 分栏、授权 crop/mask、review class 和 control 分支，并保留失败案例。它明确用于 `MANUAL REVIEW ONLY`；用户尚未完成逐例人工复核，现有 assistant review 仍是 non-human-gold。

## 11. 本次结束后的决策门

### 11.1 AGW 参与真实数据 scaling

继续到 T3 前，需要先修复 serializer 或 prompt，并在新的 held-out 上冻结和通过原生接口门。T3 再在冻结、可重置的真实 CU/BU 环境中执行候选动作，保存真实 observation 和环境最终状态，由独立 QC 决定是否入库。当前拟议的首批只是一项 12-task 工程 smoke，Chrome 6、Ubuntu 6，并覆盖 click、text、scroll、drag；任务尚未冻结或运行，这个规模也不能估计总体能力。Chrome 要单列，并与同基座 Qwen3.5-35B-A3B 使用相同 harness、prompt、processor、decode 和 executor 配对。Qwen3-VL-32B 只能作项目现状参照，不能替代同基座 A/B。

只有在相同初始化、训练 token 或样本预算、随机种子、去重规则和 session-clean held-out 下，加入 AGW 合格候选的数据相对真实数据基线带来可复现增益，才能说 AGW 数据扩展有效。候选保留率、新任务或状态覆盖、NPU 成本和人工成本需要同时报告。

### 11.2 AutoGUIWorld 合成方法

T4 需要另接可用的 Image2、planner、视觉和 QC adapter。每个合成 step 保存 seed、task、before、action、after、renderer prompt、provider revision、grounding、judge verdict 和成本。当前拟议的首批是 24 个真实 before/action/after 配对，即 Chrome、Ubuntu乘 click、text、scroll、drag，每格 3 条；单步通过后再测 4 条五步链。样本尚未选定或运行。盲审需覆盖精确文本、数值、无关内容保持、Chrome 动态状态和多步误差累积。

合成数据训练对照至少包括：真实数据、真实数据加 AGW 候选、真实数据加通过 QC 的合成数据，以及混合条件。AGW 权重不能替代 Image2；AGW 也不应同时提动作、标 evidence、判合格并训练自身而没有独立检查。

## 12. 产物和复核入口

- 上游论文和本地 AGW 总结：[AGW-35B 与 AutoGUIWorld 评估](AGW_35B_REVIEW_20261003.md)
- 2026-10-03 执行账本：[reports/agw_20261003/STATUS.md](../reports/agw_20261003/STATUS.md)
- 本次冻结任务定义：[AGW 数据扩展测试清单](AGW_DATA_SCALING_TEST_ADDENDUM_20261006.md)
- 本次执行账本：[reports/agw_20261006/STATUS.md](../reports/agw_20261006/STATUS.md)
- T1 manifest：[task_proposal_manifest.json](../reports/agw_20261006/requests/task_proposal_manifest.json)
- T1 CPU contract receipt：[cpu_contract_receipt.json](../reports/agw_20261006/t1_preflight/cpu_contract_receipt.json)
- T1/T2 map execution receipt：[execution_receipt_r3.json](../reports/agw_20261006/t1_preflight/execution_receipt_r3.json)
- T1 strict 结果：[t1_action_summary.json](../reports/agw_20261006/results/t1_action_summary.json)、[t1_action_score_rows.jsonl](../reports/agw_20261006/results/t1_action_score_rows.jsonl)
- T1 标签盲 syntax audit：[t1_posthoc_syntax_summary.json](../reports/agw_20261006/results/t1_posthoc_syntax_summary.json)
- T1 双 blind assistant review：[t1_blind_A_summary.json](../reports/agw_20261006/reviews/t1_blind_A_summary.json)、[t1_blind_B_summary.json](../reports/agw_20261006/reviews/t1_blind_B_summary.json)、[t1_blind_comparison.json](../reports/agw_20261006/reviews/t1_blind_comparison.json)
- T1 逐例图索引：[case_gallery_t1-r3.md](../reports/agw_20261006/figures/case_gallery_t1-r3.md)
- 最终 T1/T2/control 图集：[case_gallery_final-with-controls-r3-v2.md](../reports/agw_20261006/figures/case_gallery_final-with-controls-r3-v2.md)
- T2 preflight：[README.md](../reports/agw_20261006/t2_preflight/README.md)
- T2 core machine score：[results_r2/summary.json](../reports/agw_20261006/t2_preflight/results_r2/summary.json)、[results_r2/rows.jsonl](../reports/agw_20261006/t2_preflight/results_r2/rows.jsonl)
- T2 双审保守视图：[agreement_view.json](../reports/agw_20261006/t2_preflight/independent_review/agreement_view.json)、[comparison/summary.json](../reports/agw_20261006/t2_preflight/independent_review/comparison/summary.json)
- T2 读取对照：[control_results/summary.json](../reports/agw_20261006/t2_preflight/control_results/summary.json)、[controls/posthoc_audit.json](../reports/agw_20261006/t2_preflight/controls/posthoc_audit.json)
- T2 总 provenance：[FINAL_PROVENANCE.json](../reports/agw_20261006/t2_preflight/FINAL_PROVENANCE.json)
- 提交与 worker preflight：[submission_r1.json](../reports/agw_20261006/submission_r1.json)、[worker_preflight_r1.json](../reports/agw_20261006/worker_preflight_r1.json)
- 作业停止与资源释放：[stop_verified.json](../reports/agw_20261006/stop_verified.json)
- Phase 1 冻结结果：[PHASE1_RESULTS_20260923.md](PHASE1_RESULTS_20260923.md)
- Phase 1/1b 累计背景：[STAGE1_COMPREHENSIVE_20260923.md](STAGE1_COMPREHENSIVE_20260923.md)
- Phase 1c 和训练就绪边界：[PROJECT_REVIEW_SFT_READINESS_20260927.md](PROJECT_REVIEW_SFT_READINESS_20260927.md)
- 本报告无上下文读者测试：[report_fresh_reader_20261006.md](../reports/agw_20261006/report_fresh_reader_20261006.md)

## 13. 事实核查和无上下文读者测试

终态数字和 SHA 已逐项回查 execution receipt、T1/T2 scorer、双审 comparison、reading controls、gallery manifest、final provenance 和 stop receipt。本报告的本地 Markdown 链接均存在。

fresh-context 读者只读取本文，没有打开链接或其他项目文件。它能从报告独立回答预设的八个问题，包括两个想法的验证边界、数据下载状态、模型加载来源、T1/T2 各层分母、reading controls 的解释、gallery 位置和资源释放证据。测试暴露的两个主要阅读成本是 `$data` 未展开，以及 T2 的 56/35/9/8 分母需要跨段拼接；终稿已补上绝对路径和单行流失图。测试记录 SHA-256 为 `76facb335dccc3dedf8caaea2048e36f54fc43f92303f4aeb32050c0c5168879`。

补入上述修正后，第二名独立 fresh-context 读者对终稿的四个定向问题全部通过，未发现新矛盾或实质歧义；[复测记录](../reports/agw_20261006/report_fresh_reader_final_20261006.md) SHA-256 为 `3d23f93f10de41e23766822a1447394c2aa052b94ba8a9d22d041dc339cc0e5f`。

报告仍不尝试独立列出 16 个 shard 的旧 SHA、完整 reviewer rubric 或未来时刻的平台实时状态；这些材料分别由已链接的制品回执、review 文件和平台查询承担，不影响本文的实验结论。
