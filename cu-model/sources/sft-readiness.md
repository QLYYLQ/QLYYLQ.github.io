# CU/BU 下一观测预测：前期工作复盘与 SFT 数据就绪判断

日期：2026-09-27  
读者：项目 owner，以及准备下一轮数据、SFT 和评测的研究与工程人员  
范围：汇总 Stage 1、Phase 1b、Phase 1c 和 2026-09-25 全量语义审计；本报告没有启动模型、连接 worker 或提交作业

## 决策结论

现有数据已经足够做 SFT 工程 smoke，而且这一步已经完成：28 条 assistant-supported completion 在真实 Qwen3-VL-8B processor 上通过 completion-only mask，随后完成 28 个 optimizer step、双 causal 检查、冻结参数核验、adapter 保存和 fresh reload。这个结果证明训练链路能正确运行。

当前落盘数据还不够判断方法收益，也不够直接支撑面向 web、mobile、desktop 的泛化结论。28 条是来自 12 个 transition、10 个 session 的分支级 train completion，其中 12 条 predict、12 条 visible-check、4 条 missing-revisit；它们来自小规模、刻意分层的审查，只有 634 个 completion token。现有 adapter 也没有在冻结的 base/adapter 同协议评测中被加载，`adapter_inference_smoke` 仍为空。因此，不能把 loss 变化或 adapter 成功保存写成行为已经学会。

用户已经有设计好的 CU/BU agent framework，并可配合 WAL judge 或低成本视觉 judge，在真实 benchmark 运行中批量构建这类数据。这是用户提供的执行前提；本轮没有审查 framework 接口或 judge 准确率。建议直接开展规模化 silver 数据生成，不把旧池接纳率、逐例人工审查或先跑完方法收益验证作为产数前置条件。现有 28/205/83 和全量审计用于定义 schema、抽样层与已知错误，不代表未来数据容量。

对 session layout predict 本身，深核验后的判断是“有局部可测信号，方法收益尚未建立”。当前屏复用属于合法研究目标，已有 layout pair 和 14-case 结果支持继续训练与评测；早期用数据集重复率证明高频发生的论据不成立，111-transition 结果也没有显示更早历史带来净收益。full/oracle/model-crop 与 base/SFT 对照仍应用于定位瓶颈，但可与批量产数并行，不是产数前置条件。

## 1. 前期研究建立了什么

项目已把研究目标收敛为一条可观测行为链：

```text
已见历史 + 当前屏 + 已发 action/list
    -> <predict> 下一屏需要观察的区域
    -> 环境只返回获准的新像素
    -> <check> 证据充分则继续行动
               证据不足则 <revisit> 后再行动
```

预测发生时，下一屏像素、DOM、URL、未来动作、答案和目标派生描述都不可见；这些信息只可用于离线标签和评分。`current-only` 已包含当前屏与刚发动作，`warm` 只增加更早历史，所以 warm 没有领先不能否定 session 内布局复用。完整契约见 [Phase 1 protocol](phase1_protocol.md) 和 [研究审阅](phase1_research_review.md)。

前期资料还纠正了几类容易混淆的代理：layout 相似不等于空间坐标可复用，next-click bbox 不等于决策所需证据，strict JSON 或 exact alias 不等于语义能力，局部像素面积减少也不等于视觉 token 或时延已经下降。Stage 1 因此同时保留 current-only/warm、固定中心、动作位置复制、随机、完整目标图和受限观察链等对照，而没有用一个命中率代表整体能力。

组件调研核查了 GUI-Eyes、UI-Zoomer、FocusUI、AQuaUI、GUI-Actor 和 LASER。可立即借用的是观察动作与坐标回投、evidence-to-patch 标签、check 风险和“模型自产候选后用下游结果判优”的数据思路。位置保持、稀疏视觉和专用坐标 head 仍是后续组件实验，不能替代前置预测，也没有在本项目中形成模型结果。详见 [组件调研](RESEARCH_COMPONENT_REVIEW_20260923.md)。

## 2. 早期 session layout predict 主张的验证账本

| 需要核查的判断或路线 | 当前证据 | 结论与最小验证 |
|---|---|---|
| Mobile3M 约 68% 重复访问、ProCUA 约 64% 含环，说明任务 session 内“同布局新内容”高频 | [Mobile3M](https://arxiv.org/html/2409.14818v2) 是按 app 构建的 BFS/random-walk 图并做近重复节点剪枝；[ProCUA](https://arxiv.org/html/2606.17321v1) 的 cycle 是 visual-state graph 回路，含 backtracking/recovery。两者都没有给出本项目所需频率 | 撤销这个频率证明。后续只按真实任务 session 统计 query A→B、changed-instance 和可复用布局的漏斗 |
| URL/任务模板近似 layout 真值，现成 embedding 普遍不适用 | 相同 URL 可有 modal、滚动、空结果等变化；WebArena 的 [241 templates](https://arxiv.org/html/2307.13854v4) 是 task intent 模板。[UISearch](https://arxiv.org/html/2511.19380v1) 只给金融 UI pair cosine 分布，没有本项目 hard-pair PR，也不能由 cosine 范围窄推出 DINO 等排序失效 | URL、结构和 embedding 都只作候选信号。在独立审过的 hard pairs 上比较 precision/recall、排序与拒答，不预设单一路线胜出 |
| 原 attention pilot 与 hidden-state probe 是否验证了预观测信号 | 两者都没有运行。目标可见后的 attention 方案不能测提前预测；只读合法 prefix 的 hidden-state probe 即使成功，也只说明相关信息可读。[研究审阅](phase1_research_review.md)已把它们降为可选诊断 | 不补做为造数前置门。若以后运行，只读预测时刻的合法 prefix，并与行为指标分开解释 |
| 更早同 session 历史应提高下一屏选区 | 全请求分母上，8B warm/current-only 为 19/111 对 21/111，32B 为 16/111 对 19/111；严格 matched 与 earlier-reference 子集的 bootstrap 区间也都跨 0。[Stage 1 报告](STAGE1_COMPREHENSIVE_20260923.md) | 当前没有更早历史净收益证据。`current-only` 已含当前屏和已发动作，因此该结果不否定当前布局复用；需在 session-clean changed-instance 数据上重测 |
| 自动 layout 信号足以直接扩训练集 | 现有 240 pair 的 assistant review 为 spatial yes 118、partial 20、no 102。8B 接纳的 134 对中为 118/14/2，32B 接纳的 149 对中为 117/16/16。几何分数对 review yes/no 的 AUC 为 web 0.977、mobile 0.926，但 cohort 由几何等规则构造，review 非 human-gold。本次只做交叉复算，没有新增视觉审查。[交叉复算](../reports/project_review_20260927/layout_reuse_crosscheck.json) | 这说明简化几何在本样本有信号，也显示 VLM 接纳会混入不可直接复用页面。尚未验证自动标签精度、召回和规模收益；用持续分层抽查估计质量与偏差，不要求逐例审核 |
| 自然计划已经带来可用的局部观察收益 | 14 case 上，32B plan 的初次中心命中为 current/warm 10/23、12/23，direct 均为 2/23；四条件 strict 最终字段仍都是 3/24。事后 assistant response review 的 clean-supported 为 plan 5/14、7/14，direct 3/14、5/14，属于小样本后验信号。[基座诊断](BASEMODEL_PREDICTION_DIAGNOSTICS_20260924.md)、[语义账本](../reports/semantic_rollout_audit_20260925/diagnostic_32b/final_response_ledger.jsonl) | 计划改变了几何并出现描述性 response 信号，还没有统一字段或任务收益。优先做同例 full-target、oracle evidence crop、模型自选 crop 对照 |
| 局部观察已经更省 token 或时间 | 旧 HF 实现中，多轮链平均 13.23/30.63 秒，单次 full-target 为 2.23/3.86 秒，约慢 5.9/7.9 倍；当时也没有视觉 token 节省。[功能链账本](../reports/phase1_20260923/functional_chain.md) | 当前实现的效率结论是负面，不是未测；它不代表带缓存、区域合并或稀疏编码的上限。后续在固定任务与预算下重新实测 |
| SFT 训练与现代组件的效果 | 28 row 只关闭 mask、causal、optimizer、保存/reload 工程门。hidden head、PosPad 等编码层位置保持和稀疏视觉均未在本项目实现；相关论文多在看到当前图后选择或压缩区域。[实机报告](PHASE1C_LIVE_RESULTS_20260924.md)、[组件调研](RESEARCH_COMPONENT_REVIEW_20260923.md) | 现有结果不能回答方法收益，也不必在造数前实现所有组件。bottleneck 与 base/SFT 对照和批量产数并行，用结果调整监督和后端优先级 |

## 3. 不同数据视图不能按总行数相加

| 数据视图 | 当前规模 | 已确认用途 | 主要限制 |
|---|---:|---|---|
| Phase 1 冻结评测 | 111 个 target transition，80 web、31 mobile；另有 240 个 layout pair | 零训练预测、几何、layout 与 check/revisit 诊断 | 是评测 cohort，不是 SFT 行数；next-click 和 action bbox 都是代理标签 |
| 旧 SFT 原型 | 111 个全 train 候选，94 web、17 mobile，展开 333 条三分支记录；32B-layout-approved 视图为 101 transitions、303 条，94 web、7 mobile | 格式和分支协议 bootstrap | 与冻结 eval 恰好同为 111，但两池只重叠 54 个 sample ID；三分支含反事实 predict，不能做 all-assistant loss |
| 已审 completion-only | 28 条，来自 12 transitions、10 sessions，全部为 train；12 predict、12 visible、4 missing | 已完成真实 processor 和 28-step 工程 fit | 11/12 transitions 与冻结 eval 重叠，10/10 sessions 都出现在 eval；非 human-gold，覆盖很窄 |
| 三个新来源质量视图 | 205 条、70 sessions，split 为 169/8/28；137 条有位置标签，train 中 121 条 | 真实任务轨迹、位置弱监督和后续审查入口 | train 含 8 条已审 perception、3 条已审 trajectory、158 条未审；36 条 held-out 全部未审 |
| search A→B v2 | 83 条、63 sessions、54 个 query pair，split 为 70/7/6；其中 75 条未出现在旧池 | 最贴近同 session 新实例的 evidence 标注入口 | 全部无空间标签；机械隔离后的 strict train 仅 45 条、40 sessions、17 query pairs，仍未获语义批准 |
| Phase 1c evidence | 14 case、14 sessions，train/calibration/test 为 8/3/3 | 字段、区域、absence 和 check/revisit 的冻结诊断 | 3 个 calibration 和 3 个 test session 均与 SFT 训练 session 不交叉；8 个 train 中有 1 个 Hilton/web33 交叉；全部无 next-action label |
| 全量 rollout 语义账本 | 4,555/4,555 条 raw，去重后 4,039/4,039 个语义单元 | 筛选 train 侧失败、格式错误、wrong-instance 和错误停止候选 | 含历史协议、重复输出和同 case 多条件；它是输出审计，不是 4,039 个独立训练样本 |

205 与 83 是不同视图，尚未做跨视图去重；28 又是旧池的已审分支。4,555 条 raw 还包含重复和历史输出。将这些数字直接求和会同时重复计算样本、混合监督单位，并把未审候选写成已接纳数据。

A→B 的 83 条来自两个已下载来源的全量扫描，不是少量抽样：OpenHands 808 个 record 扫出 43 条，GUI-Odyssey 8,334 个 episode 扫出 40 条。但“全量”只覆盖这两个来源。OpenHands 43 条由 OpenStreetMap 33、GitLab 8、Magento admin 1、Reddit 1 组成，browser storefront shopping 为 0；GUI-Odyssey 40 条由 Ebay 32、Play Store 7、Shazam 1 组成，却只有 11 个 unique query pair。完整漏斗见 [A→B 挖掘报告](phase1b_in_session_mining.md)。

现有 A→B 只显式看图复核了 6 条，其中 4 条 changed-instance 正例、1 条 recovery、1 条 empty retry；其余 77 条未审。Phase 1c 的 14 case 中虽有 12 条来自这 83 条，但后续只补了字段/evidence 标签，不能反向升级为 12 条 layout positive。另有自动门未接纳的 171 条 review/reject 可按失败类型抽样复核，它们只供离线失败审查，旧 v1 的 target-informed `prediction_input` 不得用于模型。三个新来源的 205 条也只经过 18 条、16 sessions 的独立视觉抽审，并未穷尽底层数据。[A→B 视觉复核](phase1b_mined_visual_review.md)、[新来源视觉复核](phase1b_new_source_visual_review.md)

这些数描述当前落盘快照的覆盖偏差，不是未来产数上限。browser storefront shopping 为 0、AgentNet 只有 6 个 session，说明 framework 批量运行时要显式安排 browser shopping、desktop、mobile、地图和其他任务层，而无需先穷尽旧下载或评估采集难度。judge 可以规模化产生 silver；保留小份按任务、状态和来源分层的独立抽查，用来校准标签语义和失效类型。assistant 或模型 judge 仍是 non-human-gold。

Phase 1 的 base 结果发生在这次 28-row 训练之前，所以历史零训练结论没有被训练污染；原 eval111 的 split 本来就是 train/calibration/test 87/6/18，也从未作为纯 held-out。未来加载 adapter 时，eval111 中有 14 条来自上述 10 个训练 session，按 session 排除后剩 97 条，可作旧 action-proxy 回放；这 97 条仍含原 train 73 条，也尚未排除近重复和模板关系，不能自动升级成严格 held-out。Phase 1c 的 6 个 calibration/test case 可做 session-disjoint 的 tiny 诊断；更大的方法结论需要新建 session-clean held-out。

## 4. 工程、基座和语义审计给出的共同诊断

14-case 诊断每个条件有 24 个需要新观察确认的字段，其中 1 个真实不存在、没有 bbox，所以几何命中分母是 23；完整图两种 history 条件合计为 48 个字段。它们不是 23 或 48 个独立任务，response-level 则每条件为 14 条回答。

Phase 1c 已关闭主要工程门。8B 完成 28 条真实 mask、28 个 optimizer step 和 adapter save/reload；8B/32B vLLM vision 已跑通单图、多图、长生成与真实 crop/check/revisit，32B persistent core 完成 183 次调用，其中 13 条是九图 revisit。它们证明运行时和训练器可执行，不能说明 adapter 有能力收益。此前 9 月 23 日“尚无真实 optimizer step 或 vLLM vision”的状态已经过时，当前证据见 [Phase 1c 实机报告](PHASE1C_LIVE_RESULTS_20260924.md)。

基座诊断把问题拆成计划、空间映射和局部像素使用三层。32B 在冻结 14 case 上的自然计划和初次几何明显强于 direct 路线，但四个条件的最终 required-new strict 都是 3/24；8B 四条件都是 0/24。严格分又混入字段容器和 alias 问题，不能直接解释成视觉读错。最新独立 assistant QA 在完整目标图上复核了这 14 case：每个模型的 48 个 required-new 字段核心语义均为 48/48 supported；8B 若要求完整 annotation value 为 47/48。两模型 response-level 均为 26/28 supported，而不是整题全对。这仍是 non-human-gold 小样本。

14-case 完整图上的较好表现没有修复受限观察链。8B 的 v2 restricted 90 条输出中，只有 4 条整份回答同时满足指定辅助字段、合法可见证据和决定。32B 的 56 个最终条件中，20 条同时有正确事实、合法可见证据且无实质额外错误；另有 1 条值正确但证据不足。两套 rubric 和汇总层级不同，不能据此做 8B/32B accuracy 排名。共同暴露的训练目标是：把计划映射到足够的区域，只用获准像素识别正确实例，并判断何时证据已经充分。详见 [全量语义审计](ROLLOUT_SEMANTIC_AUDIT_20260925.md)。

## 5. 已有 framework 下的监督目标

在用户提供的 framework 和低成本 judge 前提下，可以直接随真实 benchmark 运行批量生成 silver supervision。当前研究重点是把监督定义清楚：

1. 每个样本从真实 benchmark 轨迹取得，先冻结模型在预测时合法可见的任务、历史观察、当前屏和已发 action/list。环境返回新观察的边界决定 `<predict>` 插入位置，不靠动作名猜测。
2. 对 target 离线记录 exact revisit、same template、`spatial_reusable=yes|partial|no`，以及内容变化、modal、滚动、键盘、错误页和 terminal absence。模板相同与坐标可复用保持分列。
3. 另标任务所需字段、正确实例、prefix 已知信息、必须从新屏确认的信息及 evidence region。layout similarity、next-click bbox 和任务证据充分性是不同标签，不能互相自动替代。
4. 从真实证据构造 `<check>/<revisit>` 监督，覆盖证据充分、缺关键字段和意外状态，并保留模型自产的 wrong-instance、错区、false-sufficient、无益补看和有效恢复。
5. WAL judge 或视觉 judge 可以批量产生 silver，无需把逐例人工批准设为产数前置。每条保存 judge 版本、输入边界、判据或分数（若有）和 provenance；另取小份跨任务、状态、平台的独立样本，检查标签语义、偏差和失效类型。
6. SFT 只监督合法 completion。反事实 predict 和 earlier assistant context 保持零 loss；future target、DOM、答案、教师区域和未来动作只进入 `labels_only`，不注入 predictor prefix。benchmark train 与 held-out 按 task/session 和近重复簇隔离，并在产数前冻结评测侧。

现有 28/205/83、4,555 条 raw 审计和 14 case 可作为 schema 回归、错误 taxonomy 与抽查种子。它们不限制 framework 的生成规模，也不要求先被逐条清洗完。browser shopping、desktop、mobile、地图，以及 current-as-reference、older-reference、empty/modal/state-change 可直接作为批量采样分层。

## 6. 训练与评测怎样和产数并行

批量产数无需等待方法验证完成；下列对照用于判断训练学到了什么，并及时修正监督：

- 对 base 与各 SFT checkpoint 固定 prompt、renderer、controller、schema、像素预算和 session split，做同例比较。旧 28-row adapter 只补评测接线和退化检查；训练重叠、session 排除后的旧 97 条回放、6 个 Phase 1c session-disjoint case 与新 benchmark held-out 分开报告。
- 同例保留 full-target、独立审过的 oracle evidence crop 和模型自选 crop。oracle 与模型 crop 使用相同 renderer 和局部预算，full-target 单列为完整观察对照；逐字段区分选区错误、crop 不可读、实例错误、错误停止和 scorer coverage。
- 保留 current-only/warm、固定中心、动作位置复制和随机基线；计划路线增加调用时，还要报告视觉 token、输出 token、revisit 次数和时延。
- 主要行为指标包括格式有效率、evidence coverage、合法证据支持的字段正确性、false-sufficient、无益 revisit、补看恢复和任务下一步结果。`supported + plausible` 不写成 accuracy。
- 另设完整观察的 CU/BU 回归集，检查训练是否损伤原有 grounding 和任务行为。主 held-out 由 framework 产数时按 task/session 冻结；14-case 继续作为小规模诊断，不反复调参后包装成泛化结果。
- 按 judge 版本和数据分层持续抽查 silver 的 precision、主要分歧与系统性偏差。抽查发现问题时版本化修订标签规则，不覆盖旧数据和既有结果。

直接依托已有 framework 随 benchmark 批量产数，同时推进小份独立标签抽查、三方观测对照和分阶段 SFT。这里不设固定样本上限，也不要求逐例人工审批；重点是监督接口和学习效果，每轮训练仍需绑定数据与 judge 版本，并在 session-clean held-out 和 CU/BU 回归上报告结果。

## 复核入口

- [本报告事实核查与读者测试](PROJECT_REVIEW_SFT_READINESS_CHECKS_20260927.md)
- [第一阶段综合报告](STAGE1_COMPREHENSIVE_20260923.md)
- [Phase 1b 数据扩展](phase1b_data_expansion.md)
- [Phase 1c evidence 数据](phase1c_evidence_data.md)
- [各工作线综合](SUBAGENT_SYNTHESIS_20260925.md)
- [全量 rollout 语义审计](ROLLOUT_SEMANTIC_AUDIT_20260925.md)
