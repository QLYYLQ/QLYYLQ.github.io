# CU/BU 下一观测区域预测：第一阶段综合报告

日期：2026-09-23  
读者：项目 owner，以及熟悉 VLM、但没有参与前序讨论的研究同事  
范围：Phase 1 基座评估与 Phase 1b 数据扩展/独立审查；不包含尚未发生的 SFT、RL 或在线任务训练结果

## 结论

第一阶段已经回答了两个问题。其一，这个研究问题可以被写成严格、可复查的训练与评测协议：模型在下一屏仍不可见时，根据已见 session、任务和刚发出的动作预测观察区域；环境随后只返回这些区域，模型再决定行动或补看。其二，现成 Qwen3-VL-8B-Instruct 和 32B-Instruct 能完成基础控件定位与部分布局判断，但零训练的“网格预测、独立 crop、一次补看”还不是可靠或省成本的执行策略。

这组结果支持继续训练路线，但不支持宣称模型已经学会该能力。32B 在同一批 24 例上改用原生焦点坐标后，8-cell 中心命中从网格的 2/24 提高到 9/24，说明输出接口会遮蔽部分空间能力；同批“复制当前操作位置”基线是 10/24，且原生 warm 与 current-only 都是 9/24，因此提升不能归因于额外旧历史。完整链路中，8B 和 32B 最终给出的动作落入记录框只有 2/111 和 1/111。当前实现也没有节省 token 或时间。

Phase 1b 把数据问题推进了一步，但没有把候选自动变成训练集。三份新来源经机械检查和审查隔离后留下 205 条候选，其中 169 条属于 train split；205 条里有 194 条仍未做逐例视觉审查。另有 83 条真实 search A→B 候选，覆盖 54 个不同 query pair，其中 75 条转移不在旧候选池，但它们没有 next action、point 或 bbox，仍需标任务证据区域。旧 SFT 原型经独立语义审查后，仅有 28 条分支级 completion 得到 assistant 支持。completion-only 文件已经导出，实际 tokenizer/collator 的 token mask、多模态因果顺序和 packing 隔离尚未验证。

下一阶段先把少量真实 changed-instance 轨迹补成有语义证据的训练例，用独立复核保留非 gold 标记，验证 loss 边界后做小规模 SFT 和受限观测评测。候选池扩容、3B 和 RL 排在这些工作之后。

## 1. 研究问题和演化

### 1.1 从数据设想到 session 内预测

项目文档经历了三次收敛：

| 阶段 | 保留的价值 | 当前定位 |
|---|---|---|
| 旧 proposal | 数据源清单、区域预算、`predict/check/revisit` 接口 | 作为数据 collection 资料，不再以跨实例固定位置先验为主问题 |
| `in-session-predict.md` | 同一 session 的已见页面、action 后观测边界、warm/current-only 对照 | 当前研究意图的核心 |
| `detecting_layout.md` | 内容变化下的结构召回、几何特征、VLM pair judge | 造数和候选筛选工具，不替代预测实验 |

最终目标是为 browser use 和 computer use 训练一种交互式感知行为。以“先搜商品 A，再搜商品 B”为例，模型可从当前仍可见的 A 结果页或更早的同型页面，预期 B 结果中标题、价格和结果身份会出现在哪里。预测对象是要观察的区域，未来像素生成不在任务范围内。

项目也不要求建立 world model、证明某个 tag 的因果机制，或学习跨任务不变的固定位置先验。核心证据来自可观察行为：区域在下一屏出现前被选中，局部观测能支持行动，缺信息时补看有效，并且总成本可测。attention 只能作为附加诊断，不能代替这条功能链。

### 1.2 时序与信息边界

第一阶段固定的交互顺序是：

```text
任务 G + 已观察历史 + 当前观察 O_t + 已发动作 A_t
    -> <predict> 下一观察区域 R_(t+1)
    -> 环境取得 O_(t+1)，只返回 R_(t+1) 对应的真实区域
    -> <check> 信息足够则给 A_(t+1)
               信息不足则 <revisit> 额外区域，再给 A_(t+1)
```

预测输入不能包含 `O_(t+1)`、目标 DOM/AX/XML、目标 URL、未来动作、未来 bbox、未来描述或离线 judge 结论。未来信息只能在离线构造中生成标签。观察边界由环境是否返回新观测决定；click、输入、focus、键盘弹出都可能触发它，不能靠手写一组“翻页动作”来判断。

现有请求 ID 中的 `cold` 应读作 current-only。它仍包含 `O_t + A_t`，而 `O_t` 可能就是可复用的 session 布局。warm 只是在相同 target 上增加更早历史，所以 warm 减 current-only 测的是“额外旧历史”的边际价值。它不比较“有 session”与“无 session”，也不决定整个思路是否成立。`reference_step < current_step` 只是较早历史支线；current-as-reference 是合法且重要的主场景。

第一阶段使用的是尚未做本项目训练的 Qwen3-VL-8B-Instruct 和 Qwen3-VL-32B-Instruct。这里的 starting model 或 base 指现成 Instruct checkpoint，不是原始预训练权重。

## 2. Phase 1：从协议到冻结的零训练证据

### 2.1 数据和评测构成

Phase 1 从 OpenHands WebArena、GUI-Odyssey 和 GUI-Xplore 等已下载材料构造数据。OpenHands 和 GUI-Odyssey提供有任务的真实轨迹；GUI-Xplore 没有可靠任务指令，只用于布局/结构分析，不能把探索者的未来点击解释成任务预测标签。

冻结评测包含 111 个 transition，其中 web 80、mobile 31；layout pair 为 web 120、mobile 120，共 240 对。预测使用 8×8 归一化网格，主要报告前 4/8/16 个 cell。功能链首次返回 8 格，最多补看 8 个新格，累计面积上限为 25%。下一动作框只作为 action-target proxy，也就是“记录动作落在哪里”的位置弱标签：框被覆盖不等于任务证据充分，框未被覆盖也不自动证明必须 revisit。完整目标屏 next-click 是离线回放诊断，因为轨迹动作不一定唯一正确，短历史也可能丢失任务状态。

原始 P2 SFT 原型有 111 个 transition、333 条三分支对话。经 32B layout 接纳后为 101 个 transition、303 条，其中 web 94、mobile 7；两模型一致接纳为 98 个 transition、294 条。它们当时的意义是格式和银标 bootstrap，不是已训练能力或人类 gold。

主推理产出 1,980 条，canvas probe 48 条，native-focus probe 96 条。主输出 exact ID、重复、状态、错误、模型和 request SHA 审计通过；本地测试为 46 passed。这些检查说明结果集完整，不说明 scorer 或标签天然正确。

### 2.2 8B 与 32B 的离线结果

下表保留全部请求为分母。最后四项都是离线代理，不是在线 CU/BU 成功率。

| 测量 | 8B | 32B | 可以说明什么 |
|---|---:|---:|---|
| 完整截图加明确控件 query，预测点落入目标框 | 73/97，75.3% | 79/97，81.4% | 基础视觉定位和坐标协议可用 |
| 下一屏不可见，warm 前 8 格命中目标框中心 | 19/111，17.1% | 16/111，14.4% | 零训练网格预测较弱 |
| 下一屏不可见，current-only 前 8 格命中 | 21/111，18.9% | 19/111，17.1% | 这批条件与指标下未见额外旧历史净收益 |
| 完整目标屏加原任务/短历史，下一点击框一致 | 26/111，23.4% | 46/111，41.4% | 32B 的全图任务/grounding 代理更强，但远非任务上界 |
| 最多补看一次后产生可执行 act | 27/111 | 4/111 | 协议能跑通，零训练 check 行为不稳定 |
| 最终 act 落入记录的下一动作框 | 2/111 | 1/111 | 当前离线协议下的完整链路不可靠 |

明确控件 query 的 97 例由 76 个 web 和 21 个 mobile 样本组成。相对 111 个 source transition，4 个 web 样本只有未命名 `button`，10 个 mobile 样本的指令过泛、语义不一致或无法在单图中唯一识别，因此被排除；构造器没有读取目标框或原任务来补写 query。表中的“可执行 act”只表示控制器成功解析出 `decision=act` 和有效归一化点，可交给执行器，不表示动作正确，也不表示它已经在线执行成功。

额外旧历史没有带来净提升。全 111 例中，8B 的 warm 相对 current-only 新增命中 6 例、丢失 8 例；32B 新增 6 例、丢失 9 例。在预先标记为较早 reference 已进入 prompt 的同一 73 个 transition 上，格式失败仍按未命中保留在分母中：8B 两臂都是 13 例命中，32B 为 11 对 12。图 1/2 还要求相关 arm 都能评分，因此 8B 图中保留 73 例，32B 只剩 63 例。这个结果只否定“当前提示和数据下，额外旧历史已有稳定边际收益”，没有否定 current screen 的布局复用，也没有否定训练后的行为可能性。

![四组 8×8 热图，比较 older history、current-only、二者差值及目标频率；多组预测呈明显横向整行偏好。](../reports/phase1_20260923/selection_heatmaps.png)

图 1：较早 reference 可见、相关 arm 都能评分的匹配子集，其中 8B 为 mobile 31 加 web 42，共 73 例；32B 为 mobile 23 加 web 40，共 63 例。颜色表示模型生成某个 cell 的选择频率或两臂频率差，不是模型校准概率，也不是 attention 权重。主表的 111 分母保留了格式失败，不能和图中子集直接换算。8B warm 在全 111 例中有 48 次把整行 0 到 7 放在前八，32B 也有类似整行输出，说明口述网格协议混入了格式偏好。

![四个平台和模型分组的预算曲线，横轴为选择 4、8、16 个 cell，纵轴分别为目标中心命中与目标框覆盖；older history 没有一致领先 current-only。](../reports/phase1_20260923/prediction_budget_curves.png)

图 2：和图 1 相同的匹配子集。上排是目标框中心命中，下排是目标框面积覆盖；主表 111 仍不是这里的分母。均匀抽取 k 格时，`k/64` 既是单点命中概率，也是面积覆盖的线性期望，所以两排都可画这条随机虚线；它不等于“大框与任一选中格相交”的概率。增加预算会提高命中，但 warm 没有跨模型、跨平台的一致优势。

### 2.3 Layout judge 能用于召回，不能当人工准确率

相对原 silver 标签，8B 一致 195/240，32B 一致 186/240。拆开看，8B 为 web 94/120、mobile 101/120；32B 为 web 87/120、mobile 99/120。8B 的总一致数更高，不代表它比 32B 更准确，因为 web 的“不同 URL 模板”负例和 mobile 的几何正例本身有噪声。

真实 mobile reference-target 候选中，8B 接纳 7/31，32B 接纳 12/31。独立 assistant 视觉审查发现了键盘输入页到结果页、普通表单到日期 modal 等误配，也发现 8B 拒绝而 32B 保留的不同酒店详情实例。有限审查中，16 个明确布局案例与两模型分别一致 16/16、15/16。审查者是独立 assistant，不是人类标注者；这个有意抽取的小样本只能支持具体纠错，不能外推整体 accuracy，更不能称 human gold。

后续 judge 应分别输出 `same_template`、`spatial_reusable` 和 `changed_regions/state_changes`。模板相同、坐标能否直接迁移、下一动作是否合理，是三个不同问题。

### 2.4 原生坐标、crop/canvas 与成本

原生焦点对照用来检查网格协议是否遮蔽基座的空间输出能力。对两模型都完成初次 check 输入的交集，按平台和 sample ID 哈希固定抽出同一批 24 例；它属于可执行预测子集，不能外推全部 111 例。控制器把一个 0 到 1000 的原生焦点按整数平方距离映射到最近的 8 个网格中心，等距时用 cell ID 固定破平，观察面积仍为 12.5%。

| 8-cell 中心命中，同 24 例 | 8B | 32B |
|---|---:|---:|
| 网格加较早历史 | 4/24 | 2/24 |
| 原生焦点加较早历史 | 4/24 | 9/24 |
| 原生焦点加 current-only | 5/24 | 9/24 |
| 固定中心 `(500,500)` | 5/24 | 5/24 |
| 复制当前操作点 | 10/24 | 10/24 |

复制当前操作点只有 17/24 例存在有效空间点，其余按未命中计入 24 的分母。32B 的原生坐标提升值得继续验证，但同批简单基线更高，warm 与 current-only 又完全相同。该 probe 同时改变输出表达和控制器映射，不能据此声称模型使用了更早历史。

同 24 例还比较了两种观察表达：8 个独立 crop，以及把相同像素放回原位置、其余区域置灰的 full-size canvas。8B 的记录框一致从 0/24 变为 2/24，32B 仍为 0/24；canvas 平均多约 107 个视觉 token，没有形成稳定修复。

![左侧为八个独立 crop，右侧为同像素保持原位置的灰底 canvas；该例中决策从 revisit 变为 act，但记录框一致仍为 false。](../reports/phase1_canvas_probe/cases/qwen3vl8b_decision_disagreement_01e37e006bb7.png)

图 3：一个受控表达差异例。它说明位置保留会改变模型决策，但单例变化和 2/24 的总体记录框一致不足以证明 canvas 已解决问题。

当前 HF 实现没有跨请求复用 KV。完整 `predict + check + 可能的 revisit` 平均账本如下：

| 平均每个样本 | 8B | 32B |
|---|---:|---:|
| 调用数 | 2.95 | 2.82 |
| 输入 token | 12,006 | 11,420 |
| 视觉 token，含重复编码前缀 | 6,680 | 6,361 |
| 调用耗时之和 | 13.23 秒 | 30.63 秒 |
| 一次完整目标屏 next-click 耗时 | 2.23 秒 | 3.86 秒 |

扣除重复前缀后，局部链路新增目标视觉 token 平均约 688/635，而完整目标图约 481。独立 crop 有最小分辨率、坐标文字和多次调用开销，所以“观察 12.5% 面积”不能直接换算成 token 节省。这里测到的是当前实现，不是带 KV 复用、区域合并或稀疏视觉编码后的性能上限。

## 3. Phase 1b：扩容后的语义标签缺口

### 3.1 三份新任务来源

Phase 1b 新增 AgentNet、AndroidControl 和 WebLINX，先做有限下载和真实轨迹适配，再统一检查。WebLINX 经版本化的时序与空间门后只认 v2 的 38 条；AgentNet 为 90 条，AndroidControl 为 80 条，共 208 条机械有效候选。独立审查指出的 3 条仍在池中的 review/reject 被隔离后，最终候选为 205 条：AgentNet 89、AndroidControl 78、WebLINX 38；split 为 train 169、calibration 8、test 28。

这 205 条中有位置标签的为 137 条，train 中为 121 条。本文所称 perception candidate，是任务前缀、时序和空间弱标签足以支持明确命名的观察目标，但没有批准 check 语义；trajectory candidate 则只有真实任务、动作和前后屏可用，缺少可用空间标签。质量视图包含 8 条已审 perception candidate、3 条已审 trajectory candidate 和 194 条未审记录；另有 3 条隔离记录不在 205 内。因此 169 条 train 的主体仍是未审候选，不能写成 169 条 SFT-ready 样本。

对最初冻结来源做的独立视觉审查只覆盖 18 条、16 个 session，结果为 9 条 perception、3 条 trajectory、3 条 review、3 条 reject。把这些 ID join 到 v2 时，4 条已被 WebLINX 自动门排除，其中包括 1 条视觉上合理但被保守过滤的样本；3 条仍在 208 池中的 review/reject 被隔离；剩余 11 条已审候选，加上 194 条未审候选，组成最终 205 条。它发现 WebLINX 的 DOM bbox 与成功解码的截图仍可能不同步；AndroidControl 有语言方向、路线方向和空白点问题；AgentNet 需保留 drag、double-click 等动作类型，不能统一压成 click。该审查是 source-balanced 的稳定抽样，不是 precision 估计；WebLINX v2 后增样本也没有继承旧抽样的支持结论。

![WebLINX Investopedia transition 的 current 与 withheld target 几乎相同，红色 source bbox 落在导航文字而非记录所称输入框，展示 DOM 与截图状态错位。](../reports/phase1b_data_review/web/0fa432fed19832f4ace8.jpg)

图 4：新来源不能只通过“图片可解码、坐标在范围内”的机械门。该例属于 `dom_screenshot_state_desync`，应从任务条件空间监督中拒绝。

来源许可也要随行保留。WebLINX 快照是 CC-BY-NC-SA-4.0，AndroidControl 是 Apache-2.0，AgentNet 快照标为 MIT。来源是人类演示，不等于每个动作是任务最优解；有 point/bbox 也不等于它覆盖了全部决策证据。

### 3.2 真实 search A→B 专项

专项从已下载 OpenHands WebArena 和 GUI-Odyssey 中挖到 83 条真实 query B 提交后转移，覆盖 63 个 session、54 个不同 query pair：

| 来源 | 候选 | sessions | 不同 query pair | 与旧 Phase 1 转移重叠 |
|---|---:|---:|---:|---:|
| OpenHands WebArena | 43 | 25 | 43 | 8 |
| GUI-Odyssey | 40 | 38 | 11 | 0 |
| 合计 | 83 | 63 | 54 | 8 |

扣除 8 条重叠后，新增转移为 75 条；83 条总量也不代表 83 种任务。GUI-Odyssey 的 40 行有大量 cookie ingredient query pair 重复；54 行 diverse view 只控制字符串 pair 重复，不是质量批准集。OpenHands 43 条主要来自地图和 GitLab，干净的 Magento storefront 双 query 为 0，不能宣传成电商搜索扩容。

83 条里有 28 条 current-as-reference、55 条 older-reference。这一分层借助 target 离线确认，只能放在 `labels_only.offline_confirmation`。v2 的 `prediction_input` 只保留原任务、完整已见截图/动作前缀、current 和 issued action；旧 `in_session/` v1 含 target-informed reference hint，且导出图片 SHA 语义有误，不得再作为 predictor 输入。

83 条全部通过统一机械检查，但都没有 next action、point 或 bbox，只能作为 layout/后续 evidence-region 标注候选。按旧冻结评测保护、whole-session 和跨 split 精确像素门做保守隔离后，70 条原 train 中有 45 条留在 strict training trajectory candidate 视图；这里的 strict 只表示通过这些机械隔离门，仍不代表语义批准或可直接 SFT。

独立查看 6 例后，4 例被确认是非空 A 到非空 B 的 changed-instance 正例，分别覆盖酒店到超市、TikTok 到 Instagram、香草精到巧克力豆、TikTok 到 Triller；另 2 例是 empty→nonempty 和 empty→empty 诊断控制。导出物将 4 条正例、2 条控制和 77 条未审记录分开。6 例全部没有 next action 或 check 监督，且审查来自 assistant，比例不能外推 83 条。

OpenHands 轨迹数据在本地快照中没有可核验 license，不能拿代码仓库的 MIT license 代替。正式训练或再分发前需单独确认。

### 3.3 旧 SFT 的独立语义审查

机械审计复算了 333 条原型对话中的 1,776 个 crop，111 个 visible act 点都落在记录框内，预测分支未发现非法未来整图输入。71 个 target 与历史中已看过的像素状态相同，属于合法重访，不是泄漏。

问题出在 loss 边界和语义标签。每个 transition 有 predict、visible-check、missing-revisit 三条分支；后两支的 assistant predict 是为了构造反事实而放入上下文，missing 分支甚至故意避开目标。若使用 generic all-assistant loss，训练器会同时监督互相矛盾、包括故意错误的 predict。Phase 1b 已导出显式 prompt/completion 版本与 101 条 predict-only 版本，但只完成了记录层的边界修复，实际 token mask、多模态 causal mask、packing 隔离仍未跑通验证。

独立 reviewer 在不先看旧逐例审查和 Qwen 理由的条件下，分层抽取 24 个 web transition，并查看全部 7 个 approved mobile transition。31 例逐条看了真实截图、模型可见 messages、action bbox 和 visible/missing crops：

| 分支级监督 | 支持 | 不确定 | 不支持 |
|---|---:|---:|---:|
| predict | 12 | 6 | 13 |
| visible → act | 12 | 6 | 13 |
| missing → revisit | 4 | 0 | 27 |

主要拒绝原因包括任务完成后的重复点击、会撤销正确状态的动作、正文词片段 bbox、跨 app 状态被 last-three 截断，以及控件位置已经从 history/current 得知却仍被强制 revisit。这次审查中，确认弹窗、删除后列表重排和新搜索结果等动态状态支持了少量 missing→revisit 标签。

逐分支导出最终得到 28 条 assistant-supported completion：12 条 predict、12 条 visible-check、4 条 missing-revisit。其余为 53 条不支持、12 条不确定和 210 条未审。28 条不是 28 个完整三分支 transition，也不是 human gold；31 例是刻意分层审查，不能按其支持率推算剩余样本。

## 4. 已建立的证据与仍未建立的结论

| 已有证据 | 仍不能声称 |
|---|---|
| 严格的 pre-observation 数据通道可以构造、审计和复现 | 模型已学会预测未来所需观察 |
| 两个 starting checkpoint 能在明确 query 下做 75.3%/81.4% 的框内定位 | 下一屏预测已经可靠，或 32B 的一般任务能力可由该数代表 |
| Layout judge 能召回有用候选，也能暴露模型分歧 | 195/240 或 186/240 是 human accuracy |
| 32B 原生焦点在同 24 例上优于口述网格 | 更早历史产生了增益，或原生点已超过简单位置复制 |
| 少量局部观测样本能产出 act/revisit | 已有在线任务成功、速度收益或 token 节省 |
| 新来源有 205 条候选，真实 A→B 有 83 条 | 它们已经语义批准、都有空间监督、可直接训练 |
| 28 条分支 completion 经 assistant 审查支持 | 旧 303 条整体可用，或 completion-only mask 已经实现正确 |

低 next-click 一致率也不能被解释成模型的一般任务能力上限。记录动作可能不是唯一正确动作；full-target 分支只有原任务和最近三帧，可能丢失客户、商品或跨 app 累计状态；bbox 只标一个动作目标，不一定标到标题、价格或结果身份等决策证据。当前证据更适合定位数据和接口问题，不适合做 no-go 结论。

反过来，基础定位较强也不能自动推到完整链路。Phase 1 的主要失败集中在预观测区域表达、语义证据标签、部分观测后的 check 决策，以及多次调用成本。这些正是可通过数据和训练改变的环节，所以第一阶段给出的判断是“继续，但先把训练对象做对”。

## 5. 下一阶段的执行顺序

1. **先定义可训练的 evidence region。** 以 4 条已审 changed-instance A→B 为高优先级种子，标标题、价格、结果身份、Install/Open、modal 状态等任务证据。action target 与 decision evidence 分字段保存；空结果和恢复状态单列。每条保留标注者、复核者、证据框和拒绝理由。
2. **用独立复核支持小规模 smoke。** 现阶段可继续采用 assistant 标注加独立 reviewer，保留 `assistant-reviewed` 和 `unreviewed` 状态，不因等待真人而停住工程 smoke。若要对外报告 accuracy、自动扩容或把规则推广到大池，再对 exact revisit、changed-instance、current-as-reference、modal/state-change 和新三源动作类型做分层双人人审与分歧仲裁。
3. **验证训练边界。** 在正式 SFT 前逐 token 导出并检查 loss mask：prompt 为零 loss，仅 completion 参与监督；同时给出多图 placeholder 因果顺序、样本 packing 不串图，以及 missing 分支反事实 predict 不被监督的可复查测试。这个门不过，不启动规模训练。
4. **先做小规模行为 SFT。** 以 8B 验证协议和 loss，再用 32B 做容量复核；3B 暂不下沉。输出优先使用原生点、ROI 或固定 anchor，网格作为兼容基线。smoke 报告至少同时给训练 loss 边界检查、held-out 格式率、局部观测行动和完整任务回归，不能只报训练 loss。
5. **用完整功能链评测。** 同时报告预测格式率、point/region 命中、局部观测行动、revisit 恢复、实际视觉 token 和时延。current-only、older-history、current-position-copy 与 full-frame 都保留；在线任务成功与离线 replay agreement 分开。
6. **再进入 Stage 2。** 只有小规模 SFT 证明行为可学且任务回归可控后，才把预测机制带入真实 CU/BU 训练，恢复和保持原有能力，再考虑 RL、稀疏视觉实现与扩容。

Phase 1b 没有新增 NPU 推理，也没有进行 SFT 或 RL。原 Phase 1 worker 后续已进入 killed 状态；恢复工作由主代理另行推进，本报告不把任何恢复状态写成已经完成的阶段成果。

## 6. 产物与复核入口

本报告已经包含理解结论所需的信息；以下链接只用于逐项深查。

- 研究契约：[phase1_protocol.md](phase1_protocol.md)；研究与文献边界：[phase1_research_review.md](phase1_research_review.md)
- Phase 1 冻结结论：[PHASE1_RESULTS_20260923.md](PHASE1_RESULTS_20260923.md)
- 主机器指标：[metrics.json](../reports/phase1_20260923/metrics.json)；完整性审计：[completion_audit.json](../reports/phase1_20260923/completion_audit.json)
- 逐例回放：[gallery.html](../reports/phase1_20260923/gallery.html)；成本账本：[functional_chain.md](../reports/phase1_20260923/functional_chain.md)
- 原生坐标诊断：[phase1_native_focus_probe/summary.md](../reports/phase1_native_focus_probe/summary.md)；canvas 对照：[phase1_canvas_probe/summary.md](../reports/phase1_canvas_probe/summary.md)
- Phase 1b 权威状态：[phase1b_data_expansion.md](phase1b_data_expansion.md)
- 旧 SFT 语义审查：[phase1b_semantic_audit.md](phase1b_semantic_audit.md)；新来源视觉审查：[phase1b_new_source_visual_review.md](phase1b_new_source_visual_review.md)
- A→B 挖掘与审查：[phase1b_in_session_mining.md](phase1b_in_session_mining.md)、[phase1b_mined_visual_review.md](phase1b_mined_visual_review.md)

数据版本边界：Phase 1 冻结请求和结果保持不变；Phase 1b 新三源以 `$data/cu_model/phase1b/quality_routed_v2/` 为候选 authority，真实 A→B 只认 `$data/cu_model/phase1b/in_session_v2/`，审查分流只认 `in_session_reviewed_v2/`，旧 `in_session/` v1 不得作为 predictor 输入。旧 SFT 的 28 条分支级支持样本位于 `supervision_semantic/`。所有新审查仍是非 human-gold，且候选、银标、已审支持和训练完成四种状态必须分开表述。
