# 基座下一观测预测诊断：自然计划、空间映射与局部使用

> **2026-09-24 最终状态：** 8B/32B 核心链、32B value-mismatch 有界复核和 pod1/pod3 full-target exact reproduction 均已完成独立 audit。32B 主结果为 A 24 supported/3 uncertain/1 unsupported；plan warm/current-only 初次中心命中 12/23、10/23，direct 均为 2/23；四条件最终 strict 均为 3/24。full-target 两次均为 strict/flat 36/48，28/28 decode 逐项一致。[最终 fresh-context 科学审读](BASEMODEL_PREDICTION_DIAGNOSTICS_CLOSEOUT_REVIEW_20260924.md) PASS，本轮有界任务 `objective_complete=true`。没有新提交。

日期：2026-09-24  
读者：项目 owner，以及需要判断基座能力、提示差异和后续训练方向的研究同事  
范围：Qwen3-VL-8B-Instruct 与 32B-Instruct 在冻结 14 case 上、使用 scoped-fallback vLLM runtime 的近似自然提示 A/B/C 诊断；不包含用户原提示的严格复现  
状态：最终累计科学报告；8B/32B 核心链、pod3 full-target 控制、全部 CPU audit 与 fresh-reader 均已完成

## 结论

在本轮 14-case 近似提示对照中，8B 基座经自然语言提问后有 15/28 条观察计划获 supported、8 条 uncertain、5 条 unsupported。两名独立 assistant 盲审后由第三方仲裁分歧，判定不依赖唯一 evidence 字段，合理方案可以不同。用户原 prompt、模型设置和会话仍未知，因此这个结果不认证用户原体验，也不复现用户当时的条件。

在同一批 14 case、同一 8-cell controller 下，自然计划后映射的 pooled 空间代理描述性高于直接点。warm 的初次 evidence 中心命中为 5/23、字段加权 bbox coverage 15.8%，直接点为 1/23、6.1%；current-only 分别为 1/23、5.1% 和 0/23、0.6%。旧 Phase 1 的 111 例、用户原体验和本轮 14 例并非同条件，这组差值不能因果解释旧低分，只描述本轮近似对照的路线差异。

简单空间 baseline 进一步限制了 8B 的解释。固定中心在相同初次 8-cell controller 下达到 6/23、23.6%，高于 8B 四个模型条件；均匀原生点 Monte Carlo 的期望为 3.257/23、13.0%。只有 8B plan warm 描述性高于 random 均值，仍低于固定中心。8B plan→point 高于 direct 不能据此升级为模型超越位置先验或已学会下一观测预测。

几何差值尚未转化为受限字段读取。plan→point 和 direct 的 warm/current-only 四个条件，补看后的 required-new-field 严格准确率都是 0/24。预测阶段的 plan 路线由 A、B 两次调用组成，direct 只有一次，净多一次调用；完整分支的 token 与 request elapsed 也更高。当前证据是 A 有计划信号、B 有小样本几何差值、C 的字段读取未形成 strict gain。本次没有 next-action label 或在线动作执行，不能把 C 结论扩写成完整行动能力已经验证。

32B 在同一冻结协议上呈现更强的计划与几何信号。A 为 24 supported/3 uncertain/1 unsupported；plan warm/current-only 初次中心命中为 12/23、10/23，direct 两臂均为 2/23，固定中心为 6/23。实际补看后 plan 为 15/23、17/23，direct 为 12/23、10/23。四条件最终字段 strict 却都只有 3/24，说明几何优势仍未转化为 plan 相对 direct 的聚合功能收益。对 38 个 value mismatch 的有界复核发现 25 个明显等义 alias-coverage 缺口、4 个明确内容错误和 9 个不确定，因此 strict 低分同时混入评分规则与模型输出问题。

8B 完整目标图主分也不能直接当作基础视觉能力上界。8B 的严格 required-new-field 只有 warm 3/24、current-only 1/24；28 条响应中 27 条把 required values 放在顶层，而 scorer 要求嵌套 `fields`。一个不改 value/status/decision 的 post-hoc 结构诊断将 8B full-target required-new 从 4/48 提到 35/48。对 8B v2 最终选定的 check/revisit 回答应用同一结构诊断后，direct warm/current-only 为 0/24、2/24，plan→point warm/current-only 为 3/24、1/24。8B 完整图低分强烈混入输出结构，局部链即使去掉这层混杂仍很弱。

pod1 的 32B full-target 原始 required-new 为 36/48，全部使用注册 `fields`；同一结构 readout 下，8B 为 35/48。pod3 的隔离 full-target 复测与 pod1 在 28/28 请求上 raw text、parsed JSON、完整 output token IDs、token counts、finish/EOS、prompt 与 image audit 都完全一致，strict 与 flat 仍为 36/48。该固定 panel 复现支持 decode 稳定性，不是一般视觉能力、速度或 platform 根因证据。

这些结论只属于近似提示和冻结 14 case。用户原始 prompt、模型设置和会话仍未知；split 为 8 train、3 calibration、3 test，不能把 pooled 值称为泛化。两模型结果都来自未加载本项目 adapter 的 base checkpoint；Phase 1c 的 28-step SFT 工程闭环不构成这里的能力收益证据。

8B 的 174 次 A/B/direct/check/revisit 调用全部来自绑定基础 checkpoint 的 scoped-fallback vLLM runtime，没有加载 r2 SFT adapter。现有 HF/vLLM 配对只覆盖 4 条 image-sanity、1 条 long decode 和 28 条 full-target，不覆盖核心 A/B/C。注册 schema 的 54/56 readout parity 中有 52 个字段在两侧都被读成 null，不能当作字段语义等价或 A/B/C 的 HF parity；应用已封存 flat adapter 后，HF/vLLM strict correct 为 40/56、41/56，仍保留内容差异。

## 1. 用户问题与诊断拆分

用户此前直接问模型“下一个 step 需要看什么地方”，主观上感觉回答可用。旧 Phase 1 则要求模型在下一屏不可见时直接输出固定网格，再靠局部 crop 完成 check/revisit，结果较弱。两者同时改变了提示、输出表达、预算、历史和评分标签，不能把差异直接归因于模型有或没有能力。

本轮将问题拆成三个阶段：

```text
A：原任务 + 已见 prefix + 当前屏 + 已发动作
   -> 自然语言观察计划

B：原样续接 A 的文本，下一屏仍不可见
   -> 一个 0..1000 整数原生点 -> 最近 8 个 8×8 cell

C：B 或 direct 的点封存后才取得目标图
   -> 返回选中像素 -> answer / revisit / abstain
   -> revisit 最多再取 8 个未见 cell
```

A 与 direct 都看不到 Phase 1c 预写的 evidence 字段；字段任务只在 C 的 restricted observation 到来后引入。v1 曾把 evidence need 提前放入 A/direct，审计发现后在任何模型运行前作废。当前 authority 是 `20260924_approx_plan_v2`。

自然提示是交接文档据用户描述写出的近似版本，prompt ID 为 `phase1c.approximate_natural_observation_plan.v2`。它明确要求说明下一步需要确认什么、预计去哪里看、依据来自哪些已见内容，以及哪些位置或状态仍不确定。它不是用户原 prompt 的复现条件。

## 2. 固定样本、对照和信息边界

### 2.1 样本与 split

诊断使用 Phase 1c 的 14 个 evidence case，SHA-256 为 `32ca544c9edce18eef1b8b39f73fcd931faca77b7ed6a48fdf466548ba1ea8b9`。split 为 8 train、3 calibration、3 test，14 个 session/split group 均不跨 split。

train 用于实现和必要开发，calibration 用于冻结 prompt/规则，test 只提供三个独立小案例。本文报告逐例和 pooled 描述，但 pooled 不是泛化估计。

每个条件有 24 个 requires-new-observation 字段。几何分母只有 23，因为 `p1c-map-airports-empty-cal` 的 `first_result_identity` 期望状态是 absent，没有可定义的 target bbox。target bbox 只在 A/direct/map 输出封存后用于离线评分，从未进入 pre-observation prompt、controller 输入或模型上下文。

### 2.2 两种方法与两种历史臂

| 维度 | 条件 |
|---|---|
| 方法 | `plan_then_point`：先 A 后 B；`direct_point`：直接预测点 |
| 历史 | warm：最多最近 6 张旧截图；current-only：不含更早截图 |
| 两臂共同输入 | 原任务、当前屏、已发动作 |
| 初次预算 | 最近 8/64 cell，名义面积 12.5% |
| 补看预算 | 最多另取 8 个未见 cell，累计不超过 16/64 |
| 生成 | greedy、seed 0，requested pixels 100352/401408 |

warm 减 current-only 只衡量额外旧历史价值。current-only 仍有当前 screen/session 布局信息，不是无 session baseline。

### 2.3 防未来信息与 lineage

A、B 和 direct 不读取 target image、labels、target DOM/URL、未来动作、未来字段值或 target-informed reference。B 只读取冻结 A 请求和 A raw text，并要求同模型、checkpoint、processor 和 greedy lineage。C 才读取目标图并构造实际 canvas。

每条请求、输出、图像和派生产物都绑定 SHA。缺失、错误、float point 或缺少 revisit point 保留在 exclusion/full denominator 中；不推断 0..1 到 0..1000 的缩放，也不从文字或另一臂补坐标。

## 3. 必要的旧证据

Phase 1 冻结评测有 111 个 transition：80 web、31 mobile。8B/32B 的明确 query 点定位为 73/97 和 79/97；下一屏不可见的 warm 前 8 格中心命中为 19/111 和 16/111，current-only 为 21/111 和 19/111。完整目标屏下一点击为 26/111 和 46/111；局部链最终动作落入记录框只有 2/111 和 1/111。

同一批 24 例的 warm 臂原生焦点对照中，32B 从网格 2/24 提高到 9/24，8B 为 4/24；复制当前操作点基线为 10/24。这个结果已经提示输出表达重要，但 24 例属于可进入 check 的子集，不能外推 111 例。

本轮 live 执行前，Phase 1b 已筛出 28 条 assistant-supported completion-only 记录。Phase 1c 在 8B 上完成 28-step `complete_engineering_fit_verified`，含 mask、双 causal、gradient、冻结参数、adapter 保存和 fresh reload。该 adapter 没有进入本报告的 base 诊断，工程完成和方法收益仍是两件事。

详细 runtime、SFT、vLLM fallback、平台抢占和权限证据见 [Phase 1c live 工程报告](PHASE1C_LIVE_RESULTS_20260924.md)。

## 4. A：自然观察计划是否合理

28 条 A 输出全部生成完成且文本非空。两名独立 assistant reviewer 只读取去模型、去 arm 的 public packets，对任务相关性、visible-prefix 依据、未来事实纪律、空间预期和不确定性给 verdict；20/28 一致，8 个分歧由第三名盲化 reviewer 仲裁。

| arm | supported | uncertain | unsupported |
|---|---:|---:|---:|
| current-only | 8 | 4 | 2 |
| warm | 7 | 4 | 3 |
| 合计 | 15 | 8 | 5 |

最终 review SHA-256 为 `83c29dba8bff86ce9913be845f7c36c980a43b728dab61e2c95dfd7c458191fd`。所有 reviewer 都标 `is_human_gold=false`。supported 的常见依据是计划与已发动作对齐、使用可见历史并明确未来不确定性；unsupported 包括把已完成的加购当成待办、忽略历史中已安装状态、误认刚点击的控件，或把未见推荐结论当作已知事实。

这个结果支持“自然提问能让 8B 经常说出合理的下一观察需求”。它不保证计划映射到正确像素，也没有证明未来屏上的事实。warm 的 supported 数没有超过 current-only，因此不能从 A 的语义 verdict 声称额外旧历史已有净收益。

## 5. B：计划能否映射到空间

### 5.1 格式与盲审

B map 28/28 都输出严格 0..1000 整数点。direct 为 27/28；warm `app-triller-reviewed` 输出 `[0.5,0.25]`，按协议保留失败。

两份非 human-gold B mapping 盲审只有 11/28 verdict 一致、17/28 分歧。reviewer one 的 consistent/partial/inconsistent/uncertain 为 11/9/4/4，reviewer two 为 8/14/3/3。两人分别把 12 和 17 条标为 single-focus limitation，同时标记的只有 7 条。

因此没有合成 B 的语义准确率，也没有选择一个 reviewer 来估计单焦点限制占比。B 的主证据采用可复核几何；盲审只说明“计划与一个点是否一致”本身有较高解释歧义。

### 5.2 初次 8-cell 几何

每个 case 的 required-new evidence 可以有多个字段，几何分母为 23 个带框字段；字段读取分母为 24 个 required-new field。

| 方法 / arm | 严格点 | evidence 中心命中 | 23 个 present-bbox field 的字段加权平均覆盖 |
|---|---:|---:|---:|
| direct / current-only | 14/14 | 0/23 | 0.6% |
| direct / warm | 13/14 | 1/23 | 6.1% |
| plan→point / current-only | 14/14 | 1/23 | 5.1% |
| plan→point / warm | 14/14 | 5/23 | 15.8% |

表中的 headline coverage 先按 23 个 present-bbox field 加权：plan 减 direct 的算术差为 current-only 4.56 个百分点、warm 9.70 个百分点。配对统计使用另一汇总单位，在 13 个 eligible case 内先求 coverage 均值再配对，差为 current-only `+0.0404`、warm `+0.0858`。warm 的 case 级结果是 3 个 plan 更好、3 个更差、7 个相同；current-only 是 2 个更好、0 个更差、11 个相同。自然计划路线的 pooled 空间代理在冻结样本上描述性更高，case 级方向并不稳定。

### 5.3 16-cell 诊断与实际补看

若只从初始点离线取最近 16 格，plan warm/current-only 的中心命中为 13/23、10/23，coverage 48.7%、41.7%；direct 为 10/23、6/23，coverage 31.1%、23.6%。它是固定点扩预算的几何诊断，不是实际 revisit。

实际补看后，plan warm/current-only 为 8/23、6/23，coverage 25.8%、24.3%；direct 为 6/23、4/23，coverage 22.0%、18.5%。实际链低于 nearest-16，说明第二次点、合法 revisit 和控制器时序仍是独立瓶颈。

### 5.4 简单几何 baseline

这些 baseline 在 8B outputs 完成后实现，但其概念已在 2026-09-23 交接中预注册；实现不读取或调参到模型输出。它们使用同一 0..1000 原生点和 exact integer nearest-cell controller。

| baseline | 初次 8-cell center hit / 23 | 初次 coverage | nearest 16 center hit / 23 | nearest 16 coverage |
|---|---:|---:|---:|---:|
| 固定中心 `(500,500)` | 6/23，26.1% | 23.6% | 7/23，30.4% | 29.3% |
| 复制当前已发动作点 | 0/23 | 0.0% | 10/23，43.5% | 25.6% |
| 均匀原生点 Monte Carlo，seed 0，n=4096 | expected 3.257/23，14.2% | 13.0% | expected 6.906/23，30.0% | 28.2% |

固定中心的初次几何高于 8B 的四个模型条件。8B plan warm 是唯一同时在初次 center hit 和 coverage 上高于 random Monte Carlo 均值的模型条件，但 Monte Carlo 没有报告置信区间，这仍是冻结 case 的描述。nearest-16 下，8B plan warm 为 13/23，plan current-only 和 direct warm 为 10/23；它们高于固定中心/随机均值，但 nearest-16 不是实际 revisit。

当前 action point copy 在 14/14 case 可用：6 个来自显式 action bbox center、2 个来自 desktop `point_xy_norm`、6 个来自已发 click 的首点。相对旧记录的 12/14，这是明确支持两条 desktop point 的口径扩展，不是从 target 猜坐标；初次 8-cell 仍为 0，不能当成一个强 baseline。14 case 没有独立 action-target label，因此这些 baseline 只比较 decision-evidence geometry，不比较下一动作或任务成功。

fixed-center 只比 plan-warm 多一个 center hit，样本很小且 Monte Carlo 没有置信区间，不能据此排序一般能力。权威产物见 [`prediction_geometry_baselines_20260924`](../reports/prediction_geometry_baselines_20260924/summary.md)，独立 audit 未发现 controller、tie-break、分母或未来几何泄漏问题。

## 6. C：局部像素能否支持字段读取

两种方法共完成 55 条 initial check 和 35 条 revisit。plan check 为 4 answer、5 abstain、19 revisit；15 个 revisit 有合法点。direct check 为 1 answer、4 abstain、22 revisit；20 个有合法点。两方法合计有 8 条真实九图 revisit。

| 方法 / arm | 初次 required-new strict | 最终 strict | 初次 unknown/abstain | 最终 unknown/abstain |
|---|---:|---:|---:|---:|
| direct / current-only | 0/24 | 0/24 | 2/24 | 12/24 |
| direct / warm | 0/24 | 0/24 | 6/24 | 13/24 |
| plan→point / current-only | 0/24 | 0/24 | 4/24 | 11/24 |
| plan→point / warm | 0/24 | 0/24 | 6/24 | 7/24 |

四个条件都没有 strict field recovery，plan→point 相对 direct 的最终配对差全为 0。自然计划路线的几何描述性差值没有转化为严格字段值。unknown/abstain 表示该字段未按 strict contract 回答；逐例 abstain 可能是对不足 crop 的合理反应，不能一律称为视觉误识别。

14 case 没有可用 action-target label，因此 action-target 和 action-outcome 保持 `not_measured`。本轮 C 测的是 evidence 字段读取，不是在线动作执行或完整任务成功。

## 7. Full-target、response schema 与 label 边界

full-target 28/28 都生成直接 JSON，但主 scorer 要求 required values 位于 `fields` 对象。27/28 响应把值放在顶层，严格 required-new 因而只有 warm 3/24、current-only 1/24。

`top_level_declared_fields_adapter_v1` 做了一个只读 post-hoc 诊断：只在完全缺 `fields` key 时，把已存在的顶层 declared string/null 复制进内存 `fields`；不改 raw、value、status、decision、instance、alias 或输出文件。v2 最终响应选择与主 scorer 完全一致：初次 decision 为 revisit 时选实际 revisit output，否则选 initial check；缺失保持缺失。

| 条件 / required-new 分母 | 主 strict | 窄结构诊断后 |
|---|---:|---:|
| full-target pooled | 4/48 | 35/48 |
| direct / warm 最终响应 | 0/24 | 0/24 |
| direct / current-only 最终响应 | 0/24 | 2/24 |
| plan→point / warm 最终响应 | 0/24 | 3/24 |
| plan→point / current-only 最终响应 | 0/24 | 1/24 |

结构问题强烈压低 full-target 主分，却只能在 v2 局部最终回答中恢复 0 到 3 个字段。35/48 和各条件 adapted 值都是 structure diagnostic，不是 human-gold accuracy 或全链成功率。

独立 label-blind review 支持已审 canonical map 状态/identity 和 Rainbow CSV Install 标签，同时确认两个 exact-answer coverage risk：prompt 明说 `populated`，但 populated-case aliases 没有该词；两条 supermarket case 没有覆盖 short-name 加完整地址、但不含泛类前缀的合理组合。它只支持未来另版本 sensitivity analysis，不修改本轮主分。

joint identity/new-field 的 eligible 分母是 13：Rainbow CSV 的两个 required field 都已从 prefix 知道。现有 scorer 报 current-only 0/13、warm 1/13；只有明确采用“全部 14 case、非 eligible 也保留为未成功”的另一个分母时，才写 0/14 和 1/14。

独立 [`diagnostic_8b_independent_audit.json`](../reports/prediction_diagnostics_runs/20260924_approx_plan_v2_8b_reviewed_r1/diagnostic_8b_independent_audit.json) 复算 174 个真实调用、四类分母、coverage、paired differences、cost ledger、A review hash 和 post-hoc final-response chooser，status 为 `pass`，没有 material issue。它也确认 raw request/output 没有被 post-hoc 诊断修改。

### 7.1 32B full-target 中间结果

pod1 的 28 条 32B full-target 已完成独立结构审计；本小节只用它约束 response-schema 解释，pod3 核心结果另见 7.2。32B 每条响应都使用注册 `fields` 对象，raw strict required fields 为 40/56，required-new 为 warm 18/24、current-only 18/24，flat adapter 应用 0 次。这些文件在 pod1 NPU critical 前完成；它们保留为一次有效 attempt 的审计产物，同时由 pod3 新路径复测稳定性。

pod3 隔离复测也完成 28/28 status-ok，并通过 [`persistent_full32_pod3_audit`](../reports/phase1c_live_20260924/persistent_full32_pod3_audit.md)。新旧 28 条逐请求的 raw text、parsed JSON、完整 output token IDs、input/visual/output token counts、finish/stop/EOS、rendered-prompt hash、prompt-token hash 和 image audit 全部完全一致；28 条均 `stop` 且观察到 EOS。strict required-new 都是 36/48，eligible joint group 都是 14/26；flat adapter 在两端均应用 0 行，结果不变。

两次 full-target 使用相同软件、模型/processor/generation 配置、模板、包、checkpoint 元数据和 overlay；预期差异是 persistent runner/session provenance、device 0,1 对 2,3，以及不参与 parity 结论的 load timing。core 第八阶段 receipt 到隔离 full-target 启动间隔 103.906 秒，没有推理重叠。旧 request 的 124 个 image block 没有 declared SHA；audit 通过 93 个当前文件的 byte SHA 与两次独立 runtime image audit 重建验证 path、role 和顺序，不能写成 request 文件本身预绑了图像字节。该控制不测 speed、有效 pixel resizing、权重 shard 内容或 teardown 根因。

8B 的 raw strict 是 4/56、required-new 4/48；同一 flat structure diagnostic 后为 41/56、35/48。32B raw 相对 8B raw 的巨大差距主要混入 response schema：在同一结构 readout 下，8B/32B 反而是 41/56 对 40/56、35/48 对 36/48。这个中间结果禁止把 raw 跨模型分差直接写成视觉能力提升。

pod1 full-target 剩余未满足项被分为 12 个 value/alias mismatch 和 4 个 status 未满足，仍需逐例解释；aliases、status 和主分都没有修改。这些 full-target 项不替代 7.2 的 A/B/C 核心结果。

### 7.2 32B 核心链正式主结果

pod3 的持久 session 最终完成 183 次真实模型调用：28 plan、28 direct、28 map、两路各 28 initial check，以及 18/25 条条件式 revisit。八个 stage receipt 均完整，retry 和 error 都为 0；所有 stage 使用同一 engine UUID、`engine_load_count=1`，stage 间 prefix、multimodal 和 encoder cache reset 均通过。独立 [`persistent_core32_audit_final.json`](../reports/phase1c_live_20260924/persistent_core32_audit_final.json) 状态为 `pass_complete`；正式结果的 [independent audit](../reports/prediction_diagnostics_runs/20260924_approx_plan_v2_32b_reviewed_r1/independent_audit.json) 复算 raw records、分母、几何、字段分、调用数、review hash 和结构诊断，status `pass`、无 material issue。

32B A 的非 human-gold 盲审最终为 24 supported、3 uncertain、1 unsupported；current-only 为 13/1/0，warm 为 11/2/1。两名 reviewer 原始判断先在 22/28 上一致，6 条分歧由第三名 fresh reviewer 盲审裁决为 2 supported、3 uncertain、1 unsupported。最终 review SHA-256 为 `08c10b575e3629ca283b1746b1e00e1eff1471e3bce4d29bc0b13c7d04467026`。28 条 plan 中 13 条以 192-token `length` 截断；reviewer 评的是这些已封存 raw outputs，因此 supported 仍只是对可见计划文本的合理性判断，不是正常 EOS、未来事实准确率或 human gold。

两名 B reviewer 只在 16/28 上 verdict 一致，12 条分歧。reviewer one 为 9 consistent、14 partial、5 uncertain，reviewer two 为 19 consistent、9 partial；single-focus limitation 分别标记 21/28 和 9/28，共同标记 8 条。这里保留两份原始判断，不裁成单一 B 语义准确率。B 的主可复核结果仍是严格点格式和几何覆盖。

| 方法 / arm | 严格点 | 初次中心命中 | 初次 bbox 覆盖 | 实际补看后中心命中 | 实际补看后 bbox 覆盖 | 最终 required-new strict |
|---|---:|---:|---:|---:|---:|---:|
| direct / current-only | 14/14 | 2/23 | 8.4% | 10/23 | 43.3% | 3/24 |
| direct / warm | 14/14 | 2/23 | 8.7% | 12/23 | 54.8% | 3/24 |
| plan→point / current-only | 14/14 | 10/23 | 29.1% | 17/23 | 63.7% | 3/24 |
| plan→point / warm | 14/14 | 12/23 | 53.7% | 15/23 | 67.3% | 3/24 |

![32B 四条件 nearest-8 选格频率。每个 panel 保留全部 14 case，并使用相同的 0 到 14 色标；数值是 controller 选择次数。](../reports/prediction_diagnostics_runs/20260924_approx_plan_v2_32b_reviewed_r1/figures_r2/qwen3vl32b_nearest8_selection_counts.png)

图 3：32B 初次 nearest-8 选择频率。它显示的是模型输出点经 controller 后的行为分布，不是 attention、confidence、evidence coverage 或准确率。首版图只有标题误写成 8B；audited model、records、panels、case IDs 和 counts 一直是 32B，旧图与 `TITLE_ERRATUM.md` 已保留，正文只引用修正标题后的 `figures_r2`。

这些 coverage 是对 23 个 present-bbox field 的字段加权平均，不是 13-case paired mean。初次 plan warm/current-only 的 12/23、10/23 都高于固定中心 6/23；direct 两臂只有 2/23。正式 paired case-mean 中，plan 减 direct 的初次 coverage 差为 warm `+0.4365`、current-only `+0.2216`。这说明在本轮同样本、同 controller 的 32B 近似提示中，plan route 的初次几何代理明显高于 direct 与固定中心；14 case 小样本、无置信区间和提示近似边界仍然存在，不能外推为一般能力或用户原例复现。

更好的几何没有形成方法间的聚合 strict 字段差：四个条件最终都是 3/24。逐 case paired final-field mean difference 虽为 warm/current-only 各 `+0.03846`，但分别只有 2 better/2 worse/9 ties 和 1 better/1 worse/11 ties；它不支持 plan route 有稳定的功能收益。post-hoc flat adapter 只把 plan warm 从 3/24 提到 5/24，其他三条件仍为 3/24。96 个 required-new field-condition 中，12 个主 strict 正确、2 个仅由结构适配恢复、44 个为 status mismatch/missing、38 个在现有 value/alias 下 mismatch。

对这 38 个 field-instance 的有界、非 human-gold post-hoc review 将其分为 25 个明显等义但未被注册 alias 接受、4 个明确内容/identity 错误和 9 个不确定。25 个等义项包括 19 个 prompt 允许的 `populated`、2 个 airport `not_present`、3 个正确 bar alias 加不矛盾地址，以及 1 个 Triller `Installed`。明确错误是 Triller `Sform` 后缀、Walmart 首条选错、chocolate 第二商品及其价格；不确定项包含 Hilton/restaurant 截断乱码和 3 个泛 Walmart 值。按 14 个 case-field 去重后为 8 个仅等义、3 个仅错误、2 个仅不确定、1 个错误/不确定混合。该 review 不改 raw、aliases 或正式 strict，也不能把 25 直接加回得到新准确率；它只证明 strict 的现有 value 规则存在实质混杂，38 个 mismatch 不能全部归因于模型读错。

正式 scorer 的 run status 使用保守的 `attempted` 标签；这不是阶段缺失。持久 session audit 已确认 183 次 constructed 调用全部 terminal。action target、action outcome 和在线任务成功仍为 `not_measured`。隔离 pod3 full-target 的 28/28 输出及 pod1/pod3 exact parity 已独立审计通过；它使用另一个 engine/device pair，不与 core 并行，也没有执行 teardown。

## 8. 调用成本

### 8.1 8B

下表汇总 output row 的 request-level token 与 elapsed，不含每个 stage 的 engine model-load 时间，也没有 prefill、decode、TTFT、ITL 分解。

| 方法 / arm | calls | input token | visual token | output token | request elapsed |
|---|---:|---:|---:|---:|---:|
| direct / current-only | 39 | 67,906 | 23,262 | 1,306 | 102.2 s |
| direct / warm | 36 | 135,396 | 85,680 | 1,075 | 111.0 s |
| plan→point / current-only | 51 | 78,886 | 26,617 | 3,104 | 203.3 s |
| plan→point / warm | 48 | 169,756 | 110,066 | 2,994 | 235.4 s |

plan→point 的预测由 A、B 两次调用组成，direct 只有一次，因此预测阶段净多一次调用；后续还保留更长对话。当前实现没有显示效率收益。面积预算、视觉 token、总 token 和墙钟时间必须分别报告。

独立 paired audit 按 14 case 复算后，plan→point 相对 direct 每 case 平均多 `0.857` 次实际调用。current-only 平均多 784 input、240 visual、128 output token 和 7.22 秒；warm 平均多 2,454 input、1,742 visual、137 output token 和 8.89 秒。各方法的 revisit 条件不同，所以这些是完整分支实际成本差，不是固定 stage 的纯延迟消融。

### 8.2 32B persistent session

| 方法 / arm | model calls | input token | visual token | output token | request elapsed |
|---|---:|---:|---:|---:|---:|
| direct / current-only | 40 | 69,935 | 23,447 | 1,372 | 194.4 s |
| direct / warm | 41 | 160,387 | 99,006 | 1,427 | 240.5 s |
| plan→point / current-only | 52 | 82,845 | 26,510 | 3,835 | 518.7 s |
| plan→point / warm | 50 | 182,600 | 116,299 | 3,711 | 552.6 s |

四行合计 183 次调用。`request elapsed` 与 8B 一样只累加 image load、prompt render、generate 和 output parse；不含 engine load、cache reset 或 session hold。32B 本轮只有一个 engine instance，model load 为 382.73 秒，只计一次；八个已完成 stage 的 cache reset 合计 0.353 秒，另列且不混入 request elapsed。receipt wall time 与逐请求时间重叠，session hold 只是运维驻留，两者都不能再次加成推理时延。没有 prefill、decode、TTFT、ITL 或细分 HBM 指标。

## 9. 如何回答用户最初的疑问

本轮在同一冻结 14 case、prompt v2、controller 和 scorer 下分别完成 8B 与 32B 的 plan route/direct 对照。两模型使用不同执行 session；旧 111-transition 协议、24-case warm native-focus 子集和用户原体验仍只作历史动机，没有在这里原样复现。当前证据支持以下表述：

1. 近似自然提示确实产生了可审阅的计划文本。8B A 为 15 supported/8 uncertain/5 unsupported，32B 为 24/3/1，均来自非 human-gold 盲审。32B 有 13 条计划因 192-token 上限截断，且用户原 prompt/会话未知，因此不能把 24/28 写成原体验复现或一般准确率。
2. 32B 给出了比 8B 更清楚的同批路线差异：plan warm/current-only 初次中心命中为 12/23、10/23，direct 为 2/23、2/23，也高于固定中心 6/23。8B plan warm/current-only 只有 5/23、1/23。这个结果说明在本 14 case 的近似提示下，先说观察计划再映射可以明显改变 32B 的空间代理；它没有随机化模型规模，也没有置信区间，不能据此形成一般 8B/32B 能力排序或因果解释旧 111 例。
3. B 语义仍有主观性。8B 两 reviewer 只在 11/28 一致，32B 为 16/28；32B reviewer one/two 的 consistent 数分别是 9 和 19。单焦点难以表达多区域需求，两模型都没有可辩护的单一 B 语义准确率。
4. 32B 的局部字段读取从 8B 的四条件 0/24 提高到四条件 3/24，但 plan 与 direct 的聚合 strict 完全相同。更好的初次几何没有转化成 plan route 相对 direct 的稳定字段收益。结构适配只额外恢复 plan warm 的 2 个字段；对其余 value mismatch 的有界复核又发现 25 个明显等义 alias-coverage 缺口、4 个明确错误和 9 个不确定。主 strict 保持不变，但低分不能全部解释成 response schema，也不能全部归为模型读错。
5. Full-target 与局部链衡量不同问题。8B full-target 强烈受扁平 schema 影响；32B full-target 在 pod1/pod3 两次 exact decode reproduction 中均为 36/48。这个固定-panel 一致性支持输出可复现，却不能把完整图分数当作局部链或一般视觉能力上界。
6. 本轮 C 只测 auxiliary 字段读取，没有 next-action label、action outcome 或在线执行。即使 A/B 几何较好，也没有验证完整行动能力。

因此，用户的直觉在这批近似 32B 对照中获得了方向一致的 case-study 证据：自然计划提示能产生较多 supported 计划，并在描述统计上提高初次空间代理。这个证据不复现用户原设置，且 strict 字段读取没有出现 plan 相对 direct 的聚合优势。8B 只呈现较弱的同向信号。更准确的结论是“提示路线会影响这批 case 的计划文本和几何选择，模型规模可能参与差异”，而不是“旧低分已被解释”或“模型已经学会完整下一观测行为”。

## 10. 限制与下一步

- 自然 prompt 是近似版本。用户原模型、系统 prompt、完整会话和下一屏可见性拿到后，应另建原例复现条件，不能覆盖 v2。
- 14 case 很小，split 为 8/3/3；pooled 与 paired 值都是 case study。两轮 A/B review 均为 assistant blind review，不是 human gold。
- 32B 有 13/28 条 A 输出以长度上限结束。它们进入盲审与 B 映射，但不能当作完整自然回答或 EOS 成功。
- A 的合理方案不受唯一 evidence 字段约束；C 的 auxiliary 字段也不是 A 计划的唯一真值。B 仍只允许一个焦点，两个 reviewer 对映射判断分歧明显。multi-ROI 需要另一个冻结、配对版本。
- fixed/action/random baseline 只比较几何，没有运行 C 字段读取，不能充当功能上界。14 case 没有独立 action-target label，next action 与在线成功保持 `not_measured`。
- 主 strict、flat structure diagnostic 和 value-mismatch review 必须分层保留。32B 的 38 个 value mismatch 中有 25 个明显等义 alias-coverage 缺口、4 个明确错误和 9 个不确定；该 review 非 human gold，不改 alias 或正式分，也不能据 25 个等义项补算新准确率。
- 8B 的 HF/vLLM 配对只覆盖 33 条 sanity/long/full-target 请求，不覆盖核心 A/B/C；32B 没有 HF paired core。跨 backend 一致性不能从当前结果补推。
- 32B persistent engine 在一次 load 下完成了 183-call core，解决了本次执行的反复 teardown 风险；pod1/pod2 的两次 health event 仍只有约 25 秒的退出时间相关，根因未证，也不能保证未来 teardown 或长期运行稳定。
- pod3 隔离 full-target 与 pod1 在 28/28 raw/parsed/token/finish/EOS/prompt/image audit 上完全一致，strict/flat 均为 36/48。旧 request image block 未声明 SHA，byte integrity 来自当前字节与两次 stored runtime audit 的重建核对；这不提供 speed、pixel-budget、weight-shard 或 teardown 结论。
- SFT 已完成工程闭环，但本报告的 8B/32B 结果都来自未加载 adapter 的 base checkpoint。adapter/base 能力对比属于 Stage 2，不能回填本轮结果。

本轮有界实机、CPU audit 与 [fresh-context 科学审读](BASEMODEL_PREDICTION_DIAGNOSTICS_CLOSEOUT_REVIEW_20260924.md) 均已完成，未发现阻断项。用户原 prompt 到手后，另做原样案例和独立 test case；不能用当前成功例替代复现。
