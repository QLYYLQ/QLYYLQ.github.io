# Session prediction 第一版训练方法决策

日期：2026-09-27  
读者：项目 owner，以及负责数据导出、SFT、controller 和评测的研究与工程人员  
范围：定义第一版可执行训练方法；用户已有 CU/BU agent framework 与低成本 judge，可随真实 benchmark 运行批量产数。本报告不评估产数难度，也没有启动模型、连接 worker 或修改训练脚本

## 决策摘要

第一版要训练的是一条受信息时间边界约束的行为链，而不是单独的 layout 分类器：模型在下一屏不可见时，根据合法 session prefix 和刚发 action/list 预测需要观察的任务证据区域；收到获准像素后判断证据是否充分，不足时提出补看。layout 复用用于生成候选和空间先验，任务证据充分性单独监督。

旧 28-row adapter 只证明 completion-only mask、causal、optimizer、冻结参数和 save/reload 链路可运行。它的旧 schema、三分支反事实上下文和固定工程步数不适合作为新方法的正式 trainer。新方法需要独立版本的数据 export、mask verifier 和训练入口，同时复用已经通过实机验证的 processor、causal audit、LoRA 保存与 fresh reload 组件。

第一版采用普通文本 ROI 的 completion-only SFT。`<predict>` 输出少量、可变长的 `[0,1000]` 归一化 `xyxy` 矩形列表；可选 `needs` 只写原任务或合法 prefix 已经确定的信息类型，不写未来值或长教师解释。先保留 single-rectangle 主基线，region list 用于可分离证据和后续扩展；区域数、initial/total 面积预算在 calibration 上配置，本报告不把任何候选常数写成最佳值。

第一版不加 GUI-Actor 风格 region head，也不直接做 DPO。先用 target-derived oracle evidence ROI 和 prefix-only 候选经后继状态验证后的多有效 positive 集合做 SFT；首轮 checkpoint 再采自己的候选，以成功样本或教师纠正 completion 做 rejection-SFT。只有同 prompt、同预算的候选已经能得到稳定效用差时才进入 DPO；只有文本坐标接口被证明确为瓶颈时才增加专用 head。

## 1. 信息时间线

```text
task + observed history + current O_t + issued action/list A_t
    -> <predict> 下一观察区域或区域集合
    -> environment 获取 O_(t+1)，只返回获准像素与位置元数据
    -> <check> 已有证据充分：回答字段或继续行动
               证据不足：<revisit> 新区域 -> 新观测 -> 再判断
```

`<predict>` 输入不得包含 `O_(t+1)` 像素、DOM/AX、target URL、未来 action、答案、教师 ROI、judge 对 target 的描述或任何 target-informed reference hint。完整 target 可以供离线教师和评分使用。当前屏 `O_t` 本来就是合法 session 证据；`warm` 只增加更早历史，不能把 current-only 写成无历史条件。协议依据见 [Phase 1 protocol](phase1_protocol.md)。

数据生成时应同时保存两份视图：模型可见的 `prediction_input` 白名单，以及永不直接串入 prompt 的 `labels_only`。后者记录 target、证据字段、候选区域、judge 版本、任务结果和 provenance。训练 export 再从两者构造 prompt/completion，并为每个被监督 turn 声明精确 loss 边界。

## 2. 第一版方法选择

预测 completion 使用简短、严格可解析的文本结构：

```json
{"regions":[[120,300,420,520],[650,280,900,480]],"needs":["result_identity","displayed_price"]}
```

`regions` 坐标满足 `0 <= x1 < x2 <= 1000`、`0 <= y1 < y2 <= 1000`。一个 completion 中的 region list 是一个需要整体观察的 bundle，内部是 AND；标签侧的 `acceptable_bundles` 是多个可替代 bundle 的 OR。例如 `OR[AND(rA,rB),AND(rC)]` 表示 `[rA,rB]` 与 `[rC]` 都可接受，不能把 `rA` 单独抽成完整正例。bundle 内矩形由 export 按固定 `(y1,x1,y2,x2)` 次序序列化。

`needs` 可省略；其词项必须由 task/prefix 预先定义，target 只能补真实答案、状态和 evidence ROI，不能反写新的学生任务。Qwen3-VL 的官方技术报告使用 `[0,1000]` 坐标，现有模型也支持普通文本的 boxes/points 与多图输入；这只支持接口可行性，不证明训练效果。[Qwen3-VL 技术报告](https://arxiv.org/html/2511.21631v1)、[官方代码](https://github.com/QwenLM/Qwen3-VL)

| 决策轴 | 第一版选择 | 理由与后续进入条件 |
|---|---|---|
| 输出 | 普通文本 `regions` 列表，可选短 `needs` | 可直接审计和复用现有 decode；不生成未来值、长 CoT 或教师解释 |
| ROI 形状 | 归一化矩形；single rectangle 为主基线，少量 multi-ROI 为扩展 | 当前 14 case 未证明多 ROI 必要；保留 list 避免接口锁死 |
| 正标签 | 保存 `acceptable_bundles`；`label_source` 区分 `oracle` 与 `prefix_sampled_validated`；`prefix_predictability` 区分 `prefix_supported`、`target_state_dependent` 与 `unknown` | 未来数据可作监督标签，不可作学生输入；predictability 是离线启发式分层，不保证模型可预测；不把唯一最小框或 recorded click 强制成真值 |
| CE 采样 | 每个 transition/epoch 抽一个完整 positive bundle，跨 epoch 轮换；四类行按固定 type quota 或 transition 内归一权重 | 防止 positive 多、分支多或失败链长的 transition 获得更大权重 |
| 无窄 positive | 保留为 wide/fallback、有效 revisit 或 uncertainty 监督 | 不因预算不足或新布局静默丢样本；错误 predict 不作为正确 completion |
| check/revisit | 与 predict 同属 completion-only SFT，分行训练 | evidence sufficiency 与 layout 标签分开；首次不充分可以是有用计划的一部分 |
| 后续迭代 | 当前 checkpoint 重新采候选，做 rejection-SFT | DPO 等到候选效用差稳定；region head 等到文本空间接口瓶颈得到证据 |

[本地 geometry 复算](../reports/method_decisions_20260927/region_geometry.json)显示，14 case 中 13 条有 required-new bbox，另 1 条无需新信息。在 12.5% 原图面积预算下，任意 8 个 grid cell 只能完整覆盖 12/13；一个 enclosing rectangle 可覆盖 13/13，最大面积 6.612%。四边各加 1% 的敏感性版本最大为 8.024%，也全部容纳。它只证明 annotation geometry 可由单矩形表达，不证明 prefix 能预测、crop 可读、证据充分或 token 更省；1% padding 也不是已选配置。

## 3. 监督记录应表达什么

| 监督层 | 必需字段 | 明确不能混入的含义 |
|---|---|---|
| 时序与来源 | benchmark、task/session、step、action boundary、图像 SHA、split group | 目录顺序猜时序、跨 session 拼历史 |
| layout/state | exact revisit、same template、spatial reusable、scroll/modal/keyboard/error/absence | same template 自动等于坐标可复用 |
| task evidence | required field、instance binding、known from prefix、requires new observation、evidence ROI | next-click bbox 自动等于全部决策证据 |
| predict teacher | 一个或多个合法 ROI、预算、teacher/judge provenance、可接受替代区域 | target 内容或答案进入 predictor prefix |
| restricted observation | 实际授权像素、renderer、原图坐标映射、可读性与字段覆盖 | 看过隐藏全图后重新挑区并称为预测 |
| check/revisit | sufficient、missing evidence、terminal absence、ambiguous、revisit target、最终任务结果 | crop 未含 action bbox 就机械标 revisit |
| 审查与权重 | judge 版本、置信或分数（若有）、独立抽查结果、拒绝/不确定原因 | silver 或模型一致自动改称 human gold |

监督审计区分 `prefix_known`、`seen_present`、`present_but_hidden`、`visibly_absent` 与 `unknown/unreadable`。其中 `present_but_hidden` 是教师看完整 target 才能给出的审计状态，不能强制学生知道未观察区域内是否存在该字段；学生只按合法 prefix/crop 回答已知、已见、可见缺失证据或 unknown，并在需要时请求 revisit。hidden 不等于不存在；即使完整环境状态确认字段不存在，当前授权 crop 没有显示 absence evidence 时，也不能把它标成视觉 `visibly_absent`。

### 四类 completion-only 训练行

| 行类型 | prompt 中的合法信息 | 唯一参与 loss 的末尾 completion |
|---|---|---|
| predict | task、已见 history/current、已发 action/list | `<predict>` 的 `regions` 与可选短 `needs` |
| sufficient-check/action | 合法 prefix、实际授权 crop、此前协议 turn | 证据充分的 `<check>`，以及任务字段或下一行动 |
| insufficient/revisit | 合法 prefix、实际授权但缺证据的 crop | 证据不足的 `<check>` 与新的 `<revisit>` ROI |
| post-revisit | 上述历史、实际补看的新 crop | 新的 `<check>`，随后回答/行动，或合约允许的 fallback |

每行只监督最后一个 assistant completion。prompt 中旧 assistant turn 即使包含模型自己的错误 predict，也必须全部 mask；它们是 causal context，不是正确标签。mask 只消除这些 token 的 loss，不消除它们对后续 completion 的 conditioning，因此每条派生行必须保持同一 branch lineage：predict ROI、由它生成的真实 crop 像素与累计授权 mask、crop reader 结果、check/revisit 和最终 outcome 逐项绑定 hash。不能在 prompt 保留坏 predict，却换成 oracle 好 crop 的 action 标签。

一个 transition 可以派生四类行和多个 ROI completion，但四类行按固定 type quota 或 transition 内归一权重，避免长失败链因行数更多而主导 loss。统计独立性仍按 session 聚类，同一 target 的所有分支固定在同一 split。

### Positive 集合与效用

第一轮允许 target-derived oracle label 做 bootstrap，也允许只看 prefix 的候选在后继状态出现后验证。项目协议允许未来数据提供监督标签；限制是教师答案、target 描述和 ROI 不得进入学生 prompt。来源轴记录 `oracle` 或 `prefix_sampled_validated`，可预测性轴另记 `prefix_supported`、`target_state_dependent` 或 `unknown`；oracle ROI 可读不等于从 prefix 可预测。不能要求 base 先采出正确 ROI 才允许 bootstrap，也不能只保留唯一全图最小框。

prefix-only 候选在 target 揭晓前封存。揭晓后可把多个同预算、能支持任务的完整 bundle 加入 `acceptable_bundles`，并保存来源。预测 CE 每个 transition 每个 epoch 均衡抽一个完整 bundle、跨 epoch 轮换，不能从多矩形 bundle 中只抽一个框。没有窄 positive 的 new-layout 或预算不足样本仍保留，用 wide/fallback、有效 revisit 或 uncertainty 监督；错误、无益的 predict 不能作为正确 completion。

首次 crop 不充分不自动等于坏预测。第一版分别记录：

| 判断层 | 含义 |
|---|---|
| `initial_roi_utility` | 初始 ROI 是否提供有用任务证据；`useful`、`no_gain` 或 `not_measured` |
| `check_correctness` | 模型是否正确判断现有证据充分、缺失、模糊或终止 |
| `whole_plan_utility` | 在 total budget 内，predict、check、revisit 合起来是否恢复字段或任务 |
| `action_utility` | 真实执行后的任务结果；未执行的反事实 crop 必须是 `not_measured` |

有用但不充分的初始 ROI 加正确 revisit 可以成为 positive plan。其初始 bundle 可以进入 `<predict>` CE，但必须标记 `positive_scope=multi_step`，并通过 `plan_id` 绑定同一 branch 中正确的 insufficient-check、revisit 和预算内恢复；不得标成 `one_shot` sufficient bundle。训练先抽一个完整 positive plan，再取其 initial bundle 和同分支派生行，不能分别抽取其他分支的 check/revisit。`initial_roi_utility=no_gain` 的初选即使最后 fallback 成功，也不作为 predict 正例。recorded click 也不是唯一正确动作，未命中它不能自动成为 hard negative。

### Judge 的三个逻辑角色

| 角色 | 可见信息与职责 | 边界 |
|---|---|---|
| task condition / hidden truth | 原 task 与合法 prefix 预先定义所需信息类型；target 离线补真实答案、证据和实际状态 | 不从 target 挑容易字段后反写 `needs` |
| authorized-crop reader | 只读学生合法 prefix 与实际授权 crop，判断可见字段、instance 和 sufficiency | 不看隐藏 full target，不用教师答案补证据 |
| verdict aggregator | 合并 layout/state、reader 结果、WAL/benchmark outcome、预算和规则，形成 silver 与权重 | layout judge 只给 layout；未执行分支的 action utility 保持未测 |

三者是逻辑隔离，不要求额外三次 VLM 调用。现有线上 agent 可以承担实际 crop reader，WAL/benchmark 结果可直接复用，模板、规则或结构化事实能判定时无需另起 teacher。便宜视觉 judge 负责可规模化 silver，小份分层校准用于发现系统偏差，不把 judge 自述或 agent 自评当真值。

## 4. 训练顺序与控制矩阵

| 阶段 | 数据与目标 | 进入下一阶段的依据 |
|---|---|---|
| S0 export/contract | 冻结新 schema、split、ROI renderer、completion-only mask 与 causal audit | 真实 processor 下 prompt/视觉 token 全 mask，只有声明 completion 参与 loss |
| S1 text-ROI SFT | oracle evidence positives 加 prefix-sampled validated positives；四类监督行 | base/SFT 同协议结果、session-clean held-out、完整观察 CU/BU 回归 |
| S2 rejection-SFT | 用当前 checkpoint 只看 prefix 重采候选；接纳成功 completion，失败例写入教师纠正 completion | 模型自选 ROI 分布上的 evidence、check、whole-plan 改善 |
| S3 optional DPO | 同 prompt、同预算下有稳定、可审计效用差的 candidate pair | pair 方向在独立抽查和真实 outcome/proxy 上可靠；否则继续 SFT |
| S4 optional region head | 文本 plan 合理但坐标格式/映射持续成为主要瓶颈 | head 只读合法 prefix，且在相同数据预算下超过文本 ROI |

S1 不等待 S0 之外的所有方法组件完成；S2 也不把 rejected predict 当正确 loss。GUI-Actor 的原 head 以已经可见的 image patch 为 key/value，直接搬到未知下一帧会泄漏，所以这里只保留“合法 prefix 到固定坐标 basis”的后续改造可能。[GUI-Actor 论文](https://arxiv.org/html/2506.03143)、[固定代码](https://github.com/microsoft/GUI-Actor/blob/d98d1bbd01862f9112114b83b032f492c365a173/src/gui_actor/modeling.py)

LASER 的候选与后续成功判优启发 S2/S3，但原任务读取完整当前图，其 DPO click 上下文还保留 full image 与 crop，不能直接当本项目 restricted-observation 数据。迁移后所有学生分支必须重建为合法 prefix 加授权 crop。[LASER 论文](https://arxiv.org/html/2509.04243v1)、[固定代码](https://github.com/wwfnb/Laser/blob/74f49186fb981b89a48b2b44ae01ac0b86184293/src/laser/processor/single_step_dpo_processor.py)

| 比较 | 固定项 | 回答的问题 |
|---|---|---|
| base vs SFT | prompt、schema、controller、renderer、预算、sampling、split | 训练是否改变选区、check 和任务行为 |
| full-target vs oracle evidence ROI vs model ROI | 同例任务与回答字段；oracle/model ROI 同 renderer 和局部预算 | 失败来自完整图读取、局部表示，还是选区 |
| current-only vs warm | 同一 target、action、预算和 controller | 更早历史是否有边际价值；不把 current-only 当无 session |
| model ROI vs center/action-copy/random | 同一预算与 target | 模型是否超过简单位置先验 |
| teacher ROI vs model-error ROI | 同一 checkpoint 与任务字段 | 只在教师 crop 拟合是否造成部署分布偏移 |
| restricted chain vs full-observation CU/BU | 同一任务族与冻结回归集 | 新行为是否损伤原有 grounding/行动能力 |

主指标至少包括 ROI 格式有效率、evidence coverage、合法可见证据支持的字段正确性、instance binding、false-sufficient、无益 revisit、补看恢复、任务结果、视觉/文本 token、调用数和时延。`supported + plausible` 不写成 accuracy；response、field、ROI 和 task outcome 使用各自分母。

controller 必须记录 requested ROI、实际授权 pixel mask、自动扩边/合并后新增的像素和 initial/total budget。single rectangle 与 multi-ROI 是正式对照；改变几何后不能把差异叫作纯 renderer 收益。full-target 单列为完整观察 control，wide/fallback 使用独立 budget mode。ROI 面积也不等于视觉 token，多张碎 crop 可能因 processor 最小分辨率放大成本，必须读实际 processor 输出。

## 5. 现有代码可复用什么

| 组件 | 已有能力 | 新方法不能直接复用的边界 | 第一版处理 |
|---|---|---|---|
| [`verify_loss_mask.py`](../scripts/phase1c/verify_loss_mask.py) | 真实 processor 展开后的 completion-only mask、视觉 token 屏蔽和结构 fingerprint | 第 143 至 228 行只接旧 schema、train split、assistant-supported 层；prompt 中 assistant 必须是反事实 `<predict>` | 新建版本化 verifier，复用 token suffix 定位与逐 token 报告，不放宽旧 verifier |
| [`train_smoke.py`](../scripts/phase1c/train_smoke.py) | 模型加载、LoRA、双 causal、gradient/freeze audit、adapter 保存和 fresh reload | 第 1418 行固定 28-row corpus；CLI 固定 20 至 40 steps、rank 8、最后四层 q/v；状态写明 engineering fit only | 新建正式 trainer/CLI，复用经过验证的 audit 与保存链；不得仅换 input 绕过合约 |
| [`build_evidence_requests.py`](../scripts/phase1c/build_evidence_requests.py) | request/output SHA、原图坐标、最近 cell controller、crop sidecar 和位置文字 | 当前只有 native point 到最近 8 个 8×8 cell；第 661 行 renderer 把 tile 排成最多四列 canvas，没有正式 multi-ROI 连续 crop trainer | 新建 ROI renderer/export 版本；旧 grid/canvas 保留为对照，不静默改语义 |
| 现有 scorer 与语义账本 | strict、schema、alias、合法可见证据和错误 taxonomy 的分层审计 | strict JSON、exact alias、point hit 不能单独代表任务效果 | 为新 schema 增加 ROI set、evidence sufficiency 和 task outcome 指标，旧结果只读 |

## 6. 尚需 calibration 和实证验证的配置

- `regions` 最大数量、initial/total 面积、是否允许 wide/fallback 都在 calibration 上冻结；不把候选配置写成已证最优。
- single rectangle 与 multi-ROI 是同 total budget 下的 geometry/selection 对照。renderer 对照必须固定完全相同的 ROI pixel union，再比较连续 crop、位置保持表示或现有 8-tile canvas 的可读性、processor token 和时延。
- 用户 framework 是否支持 snapshot/fork 未经本轮核验。默认只有已执行分支有真实 outcome；其他 crop 只能使用 evidence/reader proxy，`action_utility=not_measured`。
- judge 的分层抽查要覆盖多有效 ROI、替代动作、terminal absence、错误实例和补看。真实 outcome、crop reader 与便宜 proxy 分列，先验证偏差再决定 loss 权重。
- 新协议需要学习曲线、session-clean held-out、model-error ROI 和完整观察 CU/BU 回归。旧 28-row adapter 只作工程回归，不参与方法 headline。

[GUI-Libra](https://arxiv.org/html/2602.22190)报告长 CoT 监督可能损害 grounding，并指出单 demonstration 会错误惩罚多有效 action；这支持首版短 ROI/decision 输出与多 positive 标签，不代表其 RL 配方已经适用于本项目。[MobileJudgeBench](https://arxiv.org/html/2608.11434)支持“简单视觉 judge 为主体、小份分层校准”的组织方式，但其跨域数值不能当作本项目 judge 已可靠。

[Interactive Reward Agent](https://arxiv.org/html/2607.25904v2)的 propose/verify 条件与证据分离可作为 judge 逻辑参考；[AgentRewardBench](https://arxiv.org/html/2504.08942v2)则提醒 judge 精度和信任 agent 自述存在风险。这里采用的是角色隔离与证据账本，不声称这些论文验证了 pre-observation prediction。

批量 benchmark 产数、S0/S1 工程实现、judge 小份抽查和 full/oracle/model-ROI 对照可以并行推进。第一版只同时引入新 ROI schema、completion-only trainer 和连续 ROI renderer；head 与 DPO 按上述进入条件后移，以免数据标签、输出接口和优化目标同时变化。

## 7. 第一版交付与通过标准

1. 数据 manifest 固定 benchmark/task/session split、图片与 prompt hash、`acceptable_bundles`、teacher provenance、judge 版本、branch lineage 和实际授权 pixel mask；train 与 held-out 无 session 或近重复交叉。
2. 新 verifier 在真实 processor 上逐 token 证明 prompt、旧 assistant turn 和全部视觉 token 为零 loss，只有末尾 completion 参与监督；未来图像扰动不改变更早 prefix logits。
3. 新 trainer 保留 finite loss/gradient、冻结参数 digest、adapter save/reload 和独立 terminal audit。训练步数、ROI 数量与预算写入新版本 config，不继承旧工程 smoke 的 28-row/20–40-step 限制。
4. base/SFT 在 session-clean held-out 上按同 prompt、同 controller、同 renderer 报告 ROI、check、whole-plan、成本和 CU/BU 回归；full-target、oracle ROI 与 model ROI 分列。
5. judge 的小份分层抽查报告多有效 bundle、替代动作、absence、错实例和 revisit 的分歧，不能只报总体 agreement。DPO/head 不属于第一版通过条件。

具体收益阈值和允许的 CU/BU 回归幅度应在 calibration 后、查看 held-out 前冻结。第一版即使没有收益，也必须保留完整失败分母和错误 taxonomy，才能判断下一轮应改监督、renderer、训练规模还是输出接口。

本轮来源核验、几何复算和独立检查见 [方法决策核查记录](SESSION_PREDICTION_TRAINING_DECISIONS_CHECKS_20260927.md)。
