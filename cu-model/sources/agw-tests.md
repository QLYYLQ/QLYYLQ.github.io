# AGW 数据扩展与 AutoGUIWorld 合成方法：验证状态和下一次任务测试

日期：2026-10-06。本文是下一次实验的任务清单，不是新的 NPU 运行结果或 HOPE 提交授权。既有 AGW 冻结报告及原始回执见 [AGW-35B 评估](AGW_35B_REVIEW_20261003.md) 和 [执行账本](../reports/agw_20261003/STATUS.md)。

## 两个想法分别到了哪一步

| 想法 | 已验证 | 尚未验证 |
|---|---|---|
| 让 AGW 参加由真实环境观察驱动的数据扩展 | 模型制品校验通过；H910C 上 HF eager 两 NPU 单图、七图解码通过；离线冻结请求跑完。当前屏显式目标 97 条中，原生完整动作调用 25/97，落入来源动作框 15/97。另有事后语法容错得到 95/97 可读坐标、62/97 来源框命中，只能作诊断。 | 自主提出任务下一动作、在真实环境执行并获得下一观察、独立验收候选数据、同基座 A/B、真实 Chrome 任务和完整 predict/check/revisit。现有输出不支持 AGW 已可担任主要 teacher 或 judge。 |
| 借用 AGW 训练数据的合成方法 | [论文](https://arxiv.org/html/2610.01215)和[公开仓库](https://github.com/ImYangC7/AutoGUIWorld)的流程已核对：结构化 GUI seed → 与 seed 相容的任务 → Meta Planner 原子动作与预期变化 → Voyager 生成渲染提示 → Image2 编辑下一屏 → 动作定位与逐步 QC。AGW-35B 是用 AutoGUIWorld 产生的 79,266 条 step 样本训练的动作模型。 | 本项目没有运行同款图像生成后端、完整合成轨迹、独立 QC 或合成数据训练增益对照。公开仓库要求另接文本/视觉/图像 adapter；作者的数据、同款后端和成本未在本项目复现。合成动作点位于动作前截图，不等于本项目动作后下一屏的 evidence ROI。 |

本地 pre-observation 零样本诊断为：14 case × warm/current-only = 28 条 direct，严格点格式 0/28；23 个有框字段 × 两臂 = 46 个几何单位，严格命中 0/46。事后去步号头后 27/28 可解析、1/46 命中，不替代主结果。28 条 plan 输出中，盲审四项核心内容同时齐备 0/28。没有受限观察后完整链或真实任务成功结果。论文报告的 Chrome 分域反而下降：OSWorld 46 项任务 39.0%→26.0%，WAA 17 项任务 11.2%→0.0%；这是作者的结果，尚未在本项目同协议复测。

## 新 NPU 作业要补的任务测试

前置条件：2026-10-06 对 `62628822` 的 `hope status --runid=62628822 --nocache --json` 返回 `STOPPED`，`hopex jobs` 在其配置的队列视图中没有列出本人的在跑/排队作业；这不声称其他队列全局空闲。按 `AGENTS.md`，原 worker 结束后不得自行重提。以下只定义后续获授权时的测试，不触碰现有作业或其他项目的资源。

### T1：真实轨迹观察上的自主动作候选

输入优先用冻结的 14 个 Phase 1c case（6 web、6 mobile、2 desktop；源文件为 `$data/cu_model/phase1c/data/evidence_samples.jsonl`，SHA-256 `32ca544c9edce18eef1b8b39f73fcd931faca77b7ed6a48fdf466548ba1ea8b9`）做工程 pilot。给 AGW 原任务和当前真实截图，比较 current-only 与合法历史两臂，要求它按原生 `Action:` + `computer_use` 接口提出**当前下一动作**。历史臂固定最近 5 个含当前步的截图及此前 5 步 action-only 描述；更早历史不入输入，`max_model_len=8192`，超过预算的请求留在固定分母并记为输入失败，不临时改变截断规则。构造时只从 `prediction_input` 白名单提取 task、current 和过去 history，完全不把 `issued_action` 或原始 `action_history` 放进请求，当前帧的 `action_after` 也必须删除。审计仍须按 web 的 `pre_observation_step`、mobile 的 `action_step`、desktop 的 `step` 检查原 `action_history`，确保只引用 `< current_step` 的过去动作，且当前步动作的重复副本没有进入消息；过去同样的点击可以合法出现。下一屏像素、DOM、URL、答案和目标派生提示也不得进入输入。原动作只留在离线标签侧。逐请求核验时间索引、图像 SHA、输入键白名单和图像数。不能直接把现有 pre-observation `prediction_input` 整体送入此测试，因为它含刚发出的动作。

两臂各报告 14/14 固定分母下的正常解码、原生动作 schema 合法率、动作类型与坐标可执行率、任务语义合理性及来源动作的一致/不同/无法判定；同 case 配对报告历史臂变化。来源动作只是一条示范，动作一致率不是任务成功率。事后语法修复单列，不能把修复文本当成原生可执行调用。按 web/mobile/desktop 和动作类型分层，保存原始输出及逐例复核。此 pilot 只回答能否充当**候选提议器**；样本规模和来源不足以给出总体能力结论。

T1 的 CPU 端请求已冻结：[构造器](../scripts/agw/build_task_proposal_requests.py)和[manifest](../reports/agw_20261006/requests/task_proposal_manifest.json)记录 14 条 current-only、14 条 history、独立的 14 条离线动作标签，源图像及请求中 79 次 SHA 检查通过。manifest 明确标注这只是工程 pilot，过去动作以文本转录，尚未运行目标 processor 的 8192-token 预算门，也没有 AGW 新输出。标签文件不得送入模型请求。

### T2：下一观测完整链

沿用冻结的 14 case、warm/current-only 两臂，分别保存原始 strict 接口和明确标注的探索性 adapter 分支。固定预测输入的未来信息禁入门；实际按模型选区渲染下一屏受限像素；继续同一对话执行 `<check>`、必要时一次 `<revisit>` 和下一动作或弃答。四条件各 14 个 case，总分母 56 条最终分支；每条保留图像授权 mask、image SHA、processor 视觉 token、调用次数、总耗时和分支 lineage。和 oracle 连续 ROI、当前动作位置复制、固定中心及完整屏比较。报告 OK/L1/L2/L3/B、证据覆盖、语义支持、补看收益与成本，不把几何代理提升为能力。14/14 case 的 `labels_only.action_supervision_status` 都是 `unavailable_no_next_action_label`；因此这里的下一动作只能检查格式或供独立复核，不能评分动作正确率或真实任务成功，后者交给 T3。

### T3：真实环境数据飞轮门

T1/T2 通过接口和审查门之后，另接**可重置的真实 CU/BU executor**：AGW 提议动作 → executor 执行 → 保存真实下一截图和最终环境状态 → 独立 QC → 合格候选入库。先冻结任务、site/session、初始状态、最长步数、停止条件和人工/程序验收规则；Chrome 单列，并与同基座 Qwen3.5-35B-A3B 在同 harness、prompt、processor、decode、executor 下配对。可先做 12 项工程 smoke（Chrome 6、Ubuntu 6，覆盖 click、text、scroll、drag），只检查执行链；这个数量尚未选定任务，不够估计总体能力。逐任务报告分母、双方结果、差值、失败动作、候选保留率、新增任务/状态覆盖和每条合格数据的 NPU/人工成本。合格数据再以相同初始化、随机种子、训练 token/样本预算、去重规则和清洁 held-out 集，与不加 AGW 候选的真实数据基线比较下游 CU/BU 效果，才能判断数据扩展是否有效。当前仓库没有这条 AGW 在线 executor 的验收回执，也尚未确认可用的本地同基座权重；仅靠 NPU 上的离线 replay 无法关闭此门。

### T4：AutoGUIWorld 合成数据门

单独连接经确认可用的图像编辑和文本/视觉 adapter，在可复核的小批次中保存 seed、task、before、action、after、renderer 提示、provider revision、成本和每一步 QC。公开[仓库 README 的 CLI 示例](https://github.com/ImYangC7/AutoGUIWorld/blob/7d3a063f3538cb4a6216c7da9dbae320b010ca2d/README.md)从结构化世界采样 synthetic seed；若要从真实截图扩充，须先核验是否存在可用导入接口，否则实现并审核桥接。工程首批可冻结 24 个真实 before/action/after 配对转移（Chrome、Ubuntu × click、text、scroll、drag × 每类 3 条），用真实 before+action 生成 synthetic after，再与真实 after 盲审；单步过门后再测 4 条五步链的误差累积。这些数量是拟议的 pilot，尚未选定或运行。把精确文本/数值、滚动、输入、drag、无关内容保持和 Chrome 动态状态列为必审项。新增动作后 evidence ROI 与可接受 ROI bundle 的离线标注，绝不放入预测输入。用真实环境观察和同任务真实转移作校准；按 site/session/task-family 隔离训练与测试。训练对照应区分真实数据、真实数据加 AGW 候选、真实数据加通过 QC 的合成数据以及混合条件，固定初始化、随机种子、样本/token 配额、去重规则和 held-out 集。只有完成独立复核及下游同协议增益对照，才能把这支线叫做本项目有效的数据扩展方法。AGW 权重不能替代 Image2。

## 执行顺序与资源边界

1. 在开发机冻结 T1/T2 的请求、泄漏审计、评分器、输入图像 SHA、输出目录和 manifest；用 CPU 校验 schema。新实验使用独立 run ID，不覆盖 `reports/agw_20261003/` 或旧共享输出。
2. 如获一次新作业授权，复制已核实的 `jobs/agw/agw35b_20261003_vllm030_r3.hope` 中的显式字段：1 worker、16 H910C die、同一队列；优先级需另据平台规则和旧提交回执核对，不能猜测或扩张资源。身份门通过后再核 worker 镜像、设备、共享目录可写、模型 revision 和代码 SHA。旧镜像的 vLLM 必需 Triton 核失败，首次任务测试应按已实测可用的 HF eager 路线运行，并继续把 vLLM 状态单列。
3. 原生接口不过门时不自动执行动作。探索性 adapter 输出只进入隔离的候选诊断。T3 要有独立真实环境 executor 与 evaluator；T4 要有实际图像编辑后端。这两项依赖不能用 NPU smoke 冒充。

新作业的输出应包含每个固定 cohort 的全量 request/response、错误也计入分母、worker/模型/运行时/图像 SHA、终态回执、逐例复核及费用/时延。任何后续训练仍须独立验证 CU 与 BU 能力保持。
