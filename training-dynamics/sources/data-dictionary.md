# 数据说明

本包收录 OLMo-3-7B RL-Zero 三条训练赛道的权重几何、外推 checkpoint 的功能评测、推理隐状态几何以及两条密集续训的监测数据。根目录下 `data/` 放数据，`code/` 放分析、评测与统计代码，`figures/` 放图与绘图脚本。每个文件的相对路径、字节数与 SHA-256 见包根的 `MANIFEST.tsv`；`SHA256SUMS` 可直接用于校验，macOS 上运行 `shasum -a 256 -c SHA256SUMS`，Linux 上运行 `sha256sum -c SHA256SUMS`，结果应全部为 OK。

包内不含生成全文、SVD 因子和模型权重。cell 聚合文件里的 `ckpt` 与 `samples_file` 字段记录了权重目录和生成全文在 DolphinFS 或 HDFS 上的位置，需要文本级复核时按这两个字段取用。以 `$CHECKPOINT_STORAGE/` 开头的路径是容器内的 HDFS 挂载路径，在 codelab 上对应 `$CHECKPOINT_STORAGE/`。

## 1. 通用约定

### 1.1 赛道与 checkpoint

| 赛道 | 有效训练步 | checkpoint 数 | 末步 label |
|---|---|---:|---|
| Math | 100 至 2000，每 100 步 | 20 | `allenai__Olmo-3-7B-RL-Zero-Math`（step 2000） |
| Code | 400 至 3000，每 100 步 | 27 | `allenai__Olmo-3-7B-RL-Zero-Code`（step 3000） |
| Mix | 50 至 1000，每 50 步 | 20 | `allenai__Olmo-3-7B-RL-Zero-Mix`（step 1000） |

Code 赛道的官方 step100、step200、step300 目录装的是 step1000、step2000、step3000 的权重，不是有效训练步。`data/weight_geometry/K4096/` 的逐步表里包含这三步的行，统计前需要排除；相邻差分表中 Code step400 的行以 step300 目录为前驱，同样排除。排除后累计矩阵有 15,008 个有效行，相邻配对有 14,336 个有效行。

外推使用的前缀按有效 checkpoint 个数取：p20、p50、p80 分别用前 20%、50%、80% 的有效 checkpoint 外推到该赛道真实末步；Code 的前缀末端是 step800、step1700、step2500。p100 用整段轨迹外推到末步的 1.25 倍，这个目标步没有真实 checkpoint。

### 1.2 label 命名

| label 形式 | 含义 |
|---|---|
| `allenai__Olmo-3-7B-RL-Zero-<赛道>-step_<n>` | 官方 checkpoint，训练步 n；不带 `-step_<n>` 的是该赛道末步 |
| `ours__<方法>__<赛道>_p<前缀>__` | 外推 checkpoint，方法为 lin_elem、qh_elem、qh_maglin、relex_r1、relex_r2 |
| `ours__qh_hybrid_k<K>__<赛道>_p<前缀>` | 冻结 H 的前 K 个谱方向、其余部分外推，K 为 96、1024、2048、4096；幅度配方见 `data/functional/aime_grid/tables/expbde_master.tsv` 的 `magnitude` 列 |
| `ours__<方法>__<赛道>_p<前缀>__freeze<step>` | 方向替换：保留该方法的幅度配方，更新方向取自官方 step 的 checkpoint；step 超出前缀时用到了前缀之外的信息 |
| `ours__relex_freeze_r2__Mix_p80__freeze500` | relex_r2 的方向替换构造，方向取自 Mix step500 |
| `pcaq_signfix_403a6893__qh_extrapQ__<赛道>_p<前缀>` | qh_extrapQ（PCA-Q 外推）checkpoint，Math/Mix×p20/p50/p80 共 6 个；403a6893 是生成这批权重的 `code/olmo_analysis/extrapolate_ckpt.py` 的 SHA-256 前缀 |
| `pcaq_baseline__qh_elem__<赛道>_p<前缀>` | 与上一行逐条件配对的同前缀 qh_elem checkpoint，权重与 `ours__qh_elem__<赛道>_p<前缀>__` 相同 |

方法的构造如下。

| 方法 | 构造 |
|---|---|
| lin_elem | 对累积更新的每个元素做线性回归 |
| relex_r1、relex_r2 | 从前缀学习 1 或 2 个时间 PCA 方向，外推其系数 |
| qh_elem | 固定前缀末端的 Q，在该基中逐元素拟合 H |
| qh_maglin | 固定更新方向，只线性外推幅度 |
| qh_hybrid_k | 冻结部分 H 谱方向，对其余部分外推 |
| qh_extrapQ | 用 Q 的时间 PCA 模态预测旋转，在预测的 Q 基中重新拟合 H |

文件名就是 label。PCA-Q 配对中的 qh_elem 臂是与 qh_extrapQ 臂同协议、同批生成的一组 rollout，它与 `aime_grid`、`grid_8bench` 里同名方法的 cell 不是同一次生成，跨目录比较时按各自目录读。

### 1.3 没有保存权重的 label

relex_r1 与 relex_r2 两族的全部 label（各赛道、各前缀）与 `ours__relex_freeze_r2__Mix_p80__freeze500` 只有本包中的输出表，没有保存权重，不能重新前向或重新生成。其余 label 的权重在 DolphinFS 与 HDFS 的 `models/` 下：官方 checkpoint 在 `allenai/`，lin_elem、qh_elem、qh_maglin 各 12 格（3 个赛道×4 个前缀）与 qh_hybrid_k96/1024/2048/4096 各 8 格在 `ours/`（方向替换构造是对应格下的 `freeze<step>` 子目录），PCA-Q 外推臂的 6 格在 `experiments/` 下的 `qh_extrapQ/` 子目录，完整路径见 `data/functional/pcaq_aime/qh_extrapQ/` 中聚合文件的 `ckpt` 字段。

### 1.4 生成协议

功能评测的采样参数为 temperature 0.6、top_p 0.95，记录在逐题文件的 `_meta` 行或同名 `.json` 中；seed 只在 Code AIME 与 PCA-Q AIME 的 `_meta` 中有记录，为 0；其余评测的输出没有记录 seed，评测脚本的默认值也是 0。Math 赛道使用 dapo 模板，Mix 与 Code 赛道使用 thinking 模板。`code_aime/relex_r2_p80_p100.json` 中的两个 cell 没有记录 seed、模板与存储上限。生成引擎为 vLLM 0.22.0（CUDA）与 vllm-ascend 0.22.1，二者都按 `config.layer_types` 对 sliding-attention 层施加 4,096-token 滑窗。

| benchmark | 题数 | 每题样本 | 生成上限（tokens） | 所在目录 |
|---|---:|---:|---|---|
| AIME90 | 90 | 32 | 32,768 | aime_grid、code_aime、pcaq_aime |
| MATH-500 | 500 | 8 | 6,144 | grid_8bench、code16_8bench、pcaq_clean3 |
| GSM8K | 1,319 | 8 | 5,120 | grid_8bench、code16_8bench、pcaq_clean3 |
| HumanEval | 164 | 8 | 2,048；code16_8bench 为 4,096 | grid_8bench、code16_8bench、pcaq_clean3 |
| MBPP（附测试用例） | 257 | 8 | 6,144 | code16_8bench、mbpp_standard |
| GPQA-main | 448 | 8 | 3,072 | grid_8bench、code16_8bench |
| GPQA-diamond | 198 | 8 | 3,072 | grid_8bench、code16_8bench |
| BBH | 6,507 | 8 | 1,224 | grid_8bench、code16_8bench |
| MMLU（57 个学科，每学科至多 150 题） | 7,687 | 8 | 3,072 | code16_8bench、mmlu_true_pass1 |
| first50 预算对照 | 50 | 8 | 8,192 | budget_8192 |

MMLU-Math 指 Math 赛道 label 在上表 MMLU 题集上的 true pass@1 评测（`mmlu_true_pass1/`），不是 MMLU 的数学学科子集；Code 赛道在同一题集上的评测在 `code16_8bench/mmlu/`。

AIME 的 pass@16 是逐题无偏估计 1−C(32−c,16)/C(32,16) 的 90 题均值，c 是该题 32 个样本中的正确数；8 样本任务的 pass@8 是 8 个样本至少一次正确的题目比例；pass@1 是全部样本的正确率。

### 1.5 逐题文件与 cell 聚合

功能评测的每个 cell（label×benchmark）有两份文件。多任务目录按 `<benchmark>/<label>.results.jsonl` 与 `<benchmark>/<label>.json` 存放；AIME 类目录没有 benchmark 子目录，文件直接放在目录下。

| 文件 | 内容 |
|---|---|
| `<label>.results.jsonl` | 逐题一行。8 样本任务的字段为 `uid`、`idx`、`subset`、`n`、`k`、`correct`（正确样本数）、`correct_vec`（逐样本对错）、`pass@8`、`n_samples`、`sum_tokens`、`cap_hits`（撞生成上限的样本数）、`extracted`（逐样本抽取到的答案或代码执行结果，BBH 为截取的文本片段）；Code AIME 与 PCA-Q AIME 的字段为 `uid`、`problem_idx`、`gold_answer`、`n`、`k`、`correct`、`correct_vec`、`pass@16`、`n_samples`、`sum_tokens`、`cap_hits`、`extracted`；`aime_grid` 的逐题行为 `problem_idx`、`n`、`k`、`correct`、`pass@16`、`n_samples`、`sum_tokens`、`cap_hits`，没有 `uid`、`correct_vec` 与 `extracted`。各行另有 `run_id` 与 `ts`，是生成记录的标识与时间戳，分析不使用 |
| `<label>.json` | cell 聚合：模型路径、采样参数、`pass@1`（`aime_grid` 无此字段，可由逐题 `correct` 求出）、`pass@k`、`mean_tokens`（或 `mean_len`）、`cap_rate`（或 `max_tokens_hit_rate`）、按子任务的 `per_subset`，AIME 另有逐题的 `per_problem` |

`aime_grid` 以外的逐题文件开头有一行或多行 `_meta`，记录 benchmark、label、采样数、温度、top_p、生成上限与模板；`grid_8bench` 以外的目录还记录 `sample_chars`（生成文本的存储上限，按字符计），`code_aime` 与 `pcaq_aime` 另记录 seed。`grid_8bench` 中有 4 个逐题文件含无法解析的行（BBH 3 个文件共 592 行，GSM8K 1 个文件 1 行）；`grid_8bench` 的 3 个文件与 `aime_grid` 的 1 个文件含重复的题键。读取时跳过 `_meta` 行和无法解析的行，再按 `uid`（`aime_grid` 按 `problem_idx`）去重并保留最后一条，这样每题都有一条记录，算出的 pass@1、pass@k 与同名 `.json` 一致。

达到 `sample_chars` 存储上限的样本在登记分数中按错计，相应 cell 的分数是保守下界：Code AIME 有 5 个 label 共 15 个这样的样本，清单见 `data/functional/code_aime/storage_cap_hits.csv`；PCA-Q AIME 的 `pcaq_baseline__qh_elem__Math_p50` 有 3 个，清单见 `data/functional/pcaq_paired/storage_cap_hits.csv`。标准 MBPP 的 `ours__relex_r2__Math_p50__` 有 2 条样本超出 65,536 字符的存储上限，该 checkpoint 不进入标准 MBPP 的几何与分数联合分析。token 撞上限（`finish_reason=length`，即生成达到上表的上限）与存储上限是两件事。

## 2. data/inputs

| 路径 | 内容 |
|---|---|
| `benchmarks/<benchmark>.jsonl` | 8 个多任务 benchmark 的评测输入（题面、参考答案、MBPP 的测试用例）。`mmlu.jsonl` 有 57 个学科共 14,015 题，MMLU 评测使用其中每个学科至多 150 题，共 7,687 题 |
| `aime/test.jsonl`、`aime/train.jsonl` | AIME 题集，两部分合计 90 题 |

## 3. data/weight_geometry

权重几何的对象是累积更新 ΔW_t=W_t−W_base 与相邻增量 δW_t=W_t−W_(t−1)，每个 checkpoint 覆盖 32 层×7 类投影（q、k、v、o、gate、up、down）共 224 个矩阵，三条赛道合计 672 个“赛道×层×投影”配置。SVD 为全秩（K=4096），基座因子以 FP32 保存，checkpoint 的 U/V 为 FP16、奇异值为 FP32。

| 路径 | 内容 | 粒度 |
|---|---|---|
| `K4096/` | Pass1 至 Pass9 的逐配置原始表 | 赛道×层×投影×训练步，或再细分到谱带、窗口、帧 |
| `K4096/bf16/` | bf16 往返后改变的坐标：掩码摘要、与几何掩码的重叠、行列集中度、跨赛道 Jaccard（相对阈值 η=10⁻³，全部有效步） | 赛道×层×投影×步 |
| `K4096/pass7_sensitivity/` | Pass7 谱带漂移在 ktop=48、192 与 k_traj=256、1024 下的敏感性表 | 同 Pass7 主表 |
| `derived/` | 由 `K4096/` 与 SVD 因子派生的汇总与重构结果，见下表 | 各表不同 |
| `bf16_eta/` | bf16 相对阈值 η 的全扫描（η=10⁻⁴、10⁻³、3.8×10⁻³、4×10⁻³、10⁻²）：`bf16_eta_summary.csv` 146,720 行、`bf16_eta_overlap.csv` 300,160 行、`bf16_eta_rowcol.csv` 6,720 行、`bf16_eta_jaccard.csv` 3,360 行，`RESULTS_SUMMARY.json` 与 `figure_data.csv` 为汇总 | 矩阵×步×η |
| `oft_null/` | OFT 式参数化的 matched-null 面板：18 个配置（3 赛道×L0/L16/L31×q_proj/down_proj）×3 个更新帧，Gaussian-X 与 permuted-spectrum 两种 null 各 32 次抽样（`anchor_draws.csv`），累计生成元稳定性对匹配随机游走的 32 次抽样（`rw_draws.csv`），以及 frame-cell 与配置级汇总、heart 带非退化判定 | 配置×帧×抽样 |

`K4096/` 的文件按前缀归类如下。

| 文件前缀 | 内容 |
|---|---|
| `coord_metrics`、`coord_accel_*` | Pass1：坐标掩码与主子空间、低幅值坐标的重叠与 lift |
| `per_step_metrics*`、`trajectory_metrics*`、`layer_module_summary*`、`pass2_low_quadrant_traj_*` | Pass2：逐步谱指标、四块（PP/PO/OP/OO）能量、时间 Gram 的 EVR、RELEX 拟合；后缀 `kmain256`、`tr256/512/1024` 为截断秩变体 |
| `low_principal_*`、`pass3_interval_shortcut` | Pass3：后部谱方向捕获与区间 lift |
| `pass4_*` | Pass4：cross-Gram、稳健拟合、留一与时间残差 |
| `pass5_*` | Pass5：top-1024 核内的谱带组成、稳定子空间与 k 扫描 |
| `pass6_*` | Pass6：右极分解 ΔW=QH 的逐步量、谱带旋转、能量捕获、非正规性与随机基线 |
| `pass7_*` | Pass7：谱带漂移、谱带四块轨迹、模块分层与行为代理 |
| `pass8_*` | Pass8：生长子空间漂移（`pass8_growth_dir_drift.csv`，约 366 MB）、子空间交换率、与 RELEX 的关联 |
| `pass9_*` | Pass9：OFT 拟合的 λ 扫描、lag 洗牌稳定性、δ 扫描与 Q_inf 谱带结构 |
| `p6_*`、`rotation_bands`、`decay_law_*`、`rot_decay_mechanism_results` | 幅度标度指数与谱带旋转衰减的经验拟合 |
| `gate_*`、`holdout_r2_stats` | PC1 系数的门控信号与前 10 点预测末 5 点的留出 R² |
| `md3_*`、`verify_heart_band_energy`、`layer_bin_sensitivity`、`mc_random_baseline` | 模块动力学、后半谱带能量核对、层分组敏感性与随机基线 |

`gate_*` 与 `holdout_r2_stats` 先用整条轨迹求 PC1，再在该方向上预测系数，方向含未来 checkpoint 的信息，属于回顾性诊断。Pass7 中 `top_0_96` 带的对齐为 1 由构造决定。后半谱带 [2048:4096] 的能量占比有投影内与全矩阵两种分母，数值见 `derived/energy_coordinates_summary.json`。`low_principal_metrics.csv` 的 `LSRR_ratio_norm96` 列有 17.39% 的行被谱隙下限写成 0、最大值约 9,455，不作为指标使用。

`derived/` 的内容如下。

| 路径 | 内容 |
|---|---|
| `pass1_5_summary.json` | Pass1 至 Pass5 在有效行上的汇总数值：坐标 lift、四块绝对能量、累计矩阵参与秩、轨迹 EVR、Pass5 同分母组成比 1.064614 等 |
| `energy_coordinates_summary.json` | 能量分母、四块份额与 lift、bf16 末步坐标、Pass5 组成比与 Pass7 漂移端点 |
| `pass3_sss_sensitivity.csv` | 综合分 SSS 在四种 C2 处理下的逐配置探索性结果 |
| `fixedq/` | 已知目标 H 时冻结前缀 Q 的 oracle 重构（rank-512，672 配置、7,392 个目标步）：逐步、逐配置与分组汇总，`blocks/` 为按块分解，`lowdim/` 为用含目标的完整 Q 轨迹学习少数 PCA 模态后的低维 Q 重构（63 条轨迹，3 与 5 个模态），`ktraj256/`、`ktraj1024/` 为 k_traj 敏感性，`summary_tables/` 为图用汇总 |
| `tau/` | 相邻 Q 相似度的指数与线性时标拟合（`pass8_tau_refit_all.csv`，672 配置×2 谱带=1,344 行）、共用 H 下有限目标 Q 预测与冻结 Q 的比较（`pass9_q_gapint_all.csv` 189 行，`pass9_q_gapint_prefix_all.csv` 63 行）、晚期相邻 Q 相似度的特征、相关与分层回归 |
| `geometry/` | Pass8 漂移的池化汇总、能量分母核对、后半谱带 Q 持久性描述、幅度标度中位数、RELEX 与漂移关联、精确 SVD 下谱带旋转端点 |
| `scaling/` | PC1 系数、总范数与旋转率的幂指数及留出 R² 按赛道、层、投影的汇总 |

## 4. data/extrapolation

| 路径 | 内容 |
|---|---|
| `recon/recon_<赛道>_p<前缀>.csv` | 外推权重相对真实末步的逐层逐投影重构 cosine 与相对误差，p20、p50、p80。Code 与 Mix 含 lin_elem、qh_elem、qh_maglin、relex_r1、relex_r2；Math 含 qh_elem、qh_maglin、relex_r2 |
| `pcaq_weight_delta.csv` | qh_extrapQ（PCA-Q 外推）与同前缀 qh_elem 权重在 L0、L16、L31 七类投影上的相对 Frobenius 差与最大绝对差，6 个前缀条件共 126 行；`shape_class` 区分 4096×4096 方阵与矩形 MLP 投影 |

## 5. data/functional

| 路径 | 内容 | 规模 |
|---|---|---|
| `aime_grid/` | Math 与 Mix 赛道 AIME90 的外推网格：官方 checkpoint、五种外推方法×4 个前缀、qh_hybrid K 轴与方向替换构造 | 64 个 label |
| `aime_grid/tables/` | Math、Mix 主表（pass@1/16/32、撞上限率、失败类别占比、与起点及末步之差），Exp A 方向滞后度 S、Exp B/D/E 方向来源与幅度函数、Exp C 解题重叠，失败类别与文本形态统计，前缀与末步对照点、方向×幅度六格 | 每 label 一行或每配置一行 |
| `grid_8bench/` | 多任务网格的六个 benchmark（MATH-500、GSM8K、HumanEval、GPQA-main、GPQA-diamond、BBH）；`cells.csv` 为 label×benchmark 汇总（pass@1、pass@8、平均长度、撞上限率）；`behavior_probe_p80.csv` 为 p80 前缀条件下各外推构造的文本行为指标（前段 “Wait” 比例、开头 “Wait” 密度、撞上限率、短输出比例）及其相对起点与末步的变化 | 89 个 label×6 个 benchmark |
| `code16_8bench/` | Code 赛道 16 个 checkpoint（官方 step800、1700、2500、3000，qh_elem、qh_maglin、relex_r2 各 p20/p50/p80/p100）在 8 个 benchmark 上的评测 | 128 个 cell |
| `mbpp_standard/` | 标准 MBPP（附测试用例，6,144 tokens） | 89 个 label |
| `mmlu_true_pass1/` | MMLU-Math 的逐题结果（`mmlu/`，45 个 label），`cells.csv` 为这 45 个 label 的 true pass@1、置信区间、pass@8、撞上限率、结束方式计数、不同答案抽取下的分数差，以及 `T_fixed=m_sub=448` 的 D_stim、V、V×D、H_health 与底物比例；`geometry_correlations.csv`、`derived_correlations.csv` 为几何量、撞上限率与 true pass@1 的秩相关 | 45 个 label，2,767,320 个样本 |
| `code_aime/` | Code 赛道 AIME90：14 个 label 的逐题文件；`relex_r2_p80_p100.json` 为 `ours__relex_r2__Code_p80__`、`ours__relex_r2__Code_p100__` 两个 cell 的逐题结果，用与其余 label 相同的 thinking-first boxed-integer 答案抽取评分，没有记录 seed、模板与存储上限；`metrics.csv` 为 16 个 label 在保守口径与删除存储上限样本两种处理下的 pass@1、pass@16，以及存储上限样本数与 token 撞上限率 | 16 个 label |
| `pcaq_aime/qh_extrapQ/`、`pcaq_aime/qh_elem/` | PCA-Q 配对 AIME90 的两臂 | 各 6 个 label |
| `pcaq_clean3/qh_extrapQ/`、`pcaq_clean3/qh_elem/` | PCA-Q 配对在 MATH-500、GSM8K、HumanEval 上的两臂 | 各 6 个 label×3 个 benchmark |
| `pcaq_paired/` | `paired_cells.csv`（AIME 6 格与 clean3 18 格的两臂分数、token 撞上限率与差值，登记 primary 口径），`registered_scorers.csv`（全部登记评分口径），`clean3_paired_cells.csv`（逐格配对差与按题 bootstrap 区间，10,000 次），`clean3_paired_summary.csv`（按赛道、前缀的汇总），`storage_cap_hits.csv` | 24 个配对条件 |
| `budget_8192/` | first50 预算对照：`code/` 为 Code 的 6 个 checkpoint（4 个官方、qh_elem p20 与 p50）×4 个 benchmark 在 8,192 tokens 下的结果，`mbpp_standard/` 为 Math 线 8 个 checkpoint（4 个官方、4 个 lin_elem）；参考预算一侧取自 `code16_8bench/` 与 `mbpp_standard/` 的同题结果；`budget_effects.csv`、`budget_group_effects.csv`、`paired_question_effects.csv` 为逐 cell、逐组与逐题的配对差及 bootstrap 区间 | 32 个配对 cell |
| `scoring/` | Code16 在同一批保存文本上的三种评分口径：`gsm8k/`（16 个 cell）、`math500_bbh/`（32 个 cell）、`multiple_choice/`（MMLU 与两个 GPQA，48 个 cell） | 逐样本 |

`scoring/` 的逐样本表 `cells/.../sample_rescore.csv` 中，前缀 `old_` 的列是 production 评分器的抽取与判分，`new_`（MATH-500、BBH）或 `conservative_`（GSM8K）的列是 suite 口径；`value_conflict` 或 `marker_value_conflict` 为真的样本在 conflict-excluded 口径下剔除。`multiple_choice/per_cell.csv` 中 `base_` 与 `adapter_` 两组列分别对应不使用和使用 Markdown 答案标题适配器的抽取。HumanEval 与 MBPP 用单元测试判分，三种口径相同。`data/runtime_geometry/code_mbpp_join/` 中名称以 `production`、`suite`、`conflict_excluded` 开头的列或取值分别对应这三种口径。Code 与 MBPP 的自动评分没有人工语义裁决，三种口径并列，没有一种被指定为语义金标准。

`grid_8bench/`、`code16_8bench/`、`mbpp_standard/` 中 `cap_hits` 与 `cap_rate` 统计的是撞生成上限的样本。`mmlu_true_pass1/cells.csv` 的 `in_domain_030` 标记底物比例至少 0.30 的 43 个 label，`geometry_forward` 记录几何前向的 RoPE 设置。

## 6. data/runtime_geometry

运行时几何复用已保存的 completion，对 prompt 与指定 completion 前缀做一次前向，取最后一层逐 token 隐状态，在固定窗口内计算四个指标。前向使用 BF16 参数与 FP32 RoPE buffer，按层设置 RoPE：sliding-attention 层用未缩放 RoPE（θ=500,000），full-attention 层用 YaRN（factor 8）。所核查的 17 个 Transformers 发行版中，5.0.0 至 5.12.1 的 14 个对 OLMo3 的所有层使用 YaRN，复现时需按层设置，实现见 `code/geometry/olmo3_per_layer_rope.py`。

| 指标 | 定义 |
|---|---|
| `D_world` | 固定词表嵌入子样本的局部本征维度，checkpoint 级 |
| `D_stim` | 去均值轨迹点云的 TLE 局部维度估计，近邻数 k=20 |
| `V` | ½Σlog(1+dσ_i²/T)，σ_i 为去均值轨迹矩阵的奇异值，d=4096 |
| `H` | H_health=log(D_world)×V/exp(0.1·D_stim)，由 cell 平均 D_stim、V 与 D_world 代入 |

`t_fixed` 是截取的 completion token 窗口，`m_sub` 是取样点数，本包的主比较都满足 `t_fixed=m_sub`。`n_used` 是达到窗口要求且成功计算的样本数，`n_dropped` 是不足窗口或不在固定 cohort 中的样本数，底物比例为 n_used/(n_used+n_dropped)；正式解释只用底物比例至少 0.30 的 cell。cell 级 D_stim、V 是 used 样本的算术均值。逐样本表的 `n_avail` 是该样本可用的隐状态点数，`correct`、`n_tokens`、`finish_reason` 来自对应的功能评测。

| 路径 | 内容 | 规模 |
|---|---|---|
| `grid_m448/` | 89×8 网格的 89 个 label×7 个 benchmark（MATH-500、GSM8K、HumanEval、GPQA-main、GPQA-diamond、BBH、MMLU）的 cohort，`T_fixed=m_sub=448`：`grid_m448_cells.csv`（cell 级）与 `grid_m448_persample.csv`（逐样本） | 623 个 cell，606 个有几何值，474 个底物至少 0.30；927,941 个逐样本行 |
| `grid_m448/official/` | official checkpoint 的 D_stim/V 与分数相关（各筛选切片、逐 benchmark 4 点），以及外推损伤按文本出口方向（变长、变短）分组的组内相关与范围汇总 | 7 个 benchmark×2 条赛道，共 14 组 |
| `aime_m2048/` | AIME 的 64 个 Math/Mix checkpoint，`T_fixed=m_sub=2048`，每题取第 0 个样本：cell 级与逐样本 | 64 行；5,670 个逐样本行 |
| `mgrid/` | 固定样本窗口网格：16 个 Math/Mix label×7 个 benchmark（与 `grid_m448/` 相同）×7 个窗口（m=64、96、128、192、256、320、448），每个 cell 固定使用达到 448 tokens 的样本；`analysis/` 为 cell 表、组内跨窗口秩相关、V∝m^α 指数、受限分数敏感性与各窗口秩相关汇总 | 784 个 cell；1,321,418 个样本×窗口行；m448 下 96/112 个单元在域内 |
| `short128/` | 89 个 label×5 个 benchmark（MMLU、GPQA-main、HumanEval、GPQA-diamond、BBH），`T_fixed=m_sub=128`，候选样本只要求达到 128 tokens；`analysis/` 为 cell 表、分组统计、行为对照（短且自停对长且撞预算）与推断统计 | 445 个 cell，428 个有几何值；724,118 个逐样本行 |
| `code16/` | Code16×8 的匹配几何，m128 与 m448 两窗使用同一批 `n_avail≥448` 样本：cell 级、底物与域内判定、逐样本 | 256 个 cell（每窗 128 个，全部在域内）；539,738 个样本×窗口行 |
| `mbpp_standard/` | 标准 MBPP 89 个 checkpoint 的匹配几何，设计同上 | 178 个 cell，128 个在域内（64 个 checkpoint）；256,936 个样本×窗口行 |
| `code_mbpp_join/` | Code16 与标准 MBPP 的几何、三种评分口径与结束方式的 cell 级合表，同窗 D/V–分数相关（全部、按 benchmark、按赛道），结束方式对照（同一 cell 内自停组减撞预算组的 D 与准确率差），Code 外推 checkpoint 相关符号的 benchmark 计数，以及图数据 | 每窗 128 个 Code cell、89 个 MBPP checkpoint |
| `t1/` | 时间自相关与层深控制，固定 6 个 label（Math、Mix 末步，Math p80 的 lin_elem、qh_elem、qh_maglin、relex_r2）×30 题：`block_control.csv` 3,600 行、`cross_within.csv` 186 行、`eligibility.csv` 180 行、`layer_depth_matched.csv` 5,940 行；`inputs/` 为前向用的登记 completion 与题目清单，`summary/` 为按 label 的汇总 | 层深表含 5,610 个测量行与 330 个显式 NA |

`mbpp_standard/` 的 `_domain_gate.csv` 用 1/0 表示 `in_domain`，`code16/` 用 True/False。`short128/analysis/` 与 `mgrid/analysis/` 中 MMLU 行的 `pass1`、`pass8` 使用与 `mmlu_true_pass1/` 不同的答案抽取，MMLU 分数以后者为准；`pass1c` 在 MMLU 与 GPQA 上只按完整保存的文本判分，是下界。

T1 的层深 D_stim 要求每个 label×题目单元至少有 96 个唯一 embedding 点。10 个单元不满足，它们都生成到 32,768 tokens 并高度重复，在 33 个层位置各记一行显式 NA（`layer_status=NA`），block 与 cross 指标仍覆盖全部 180 个单元。层深最后一个位置是 Transformers 5.5.4 的 `hidden_states[-1]`，即经过 final norm 的状态。

## 7. data/continuation

两条从官方 Math checkpoint 出发、每 2 个 update 存一次盘的续训。runA 从 step1600 出发、学习率 3×10⁻⁶，runB 从 step1000 出发、学习率 1×10⁻⁶，各计划 250 个 update，每个 update 采样 96 题×8 个回答，回答上限 16,384 tokens；存盘只有 BF16 HF 权重与数据加载状态，没有优化器状态。update 从各自起点开始计数，`global_step_<n>` 与 `u_<update>` 中的编号是 update 数，不是官方训练步数。本包收录 2026-10-10 18:22（北京时间）快照时的进度：runA 42 个 update、21 次存盘，runB 40 个 update、20 次存盘。续训的训练代码不在包内，在 `my_rl_job` 目录（codelab 上的 `$REMOTE_HOME/my_rl_job/`）。

| 路径 | 内容 |
|---|---|
| `protocol.json` | 起点、学习率、update 数、存盘频率、批大小、回答上限与资源设置；`checkpoint_root` 是训练容器内的 HDFS 挂载路径 |
| `<run>/monitor_snapshot.json` | 快照时点 `checked_at`（Unix 时间）、已完成的 update 数与运行状态 |
| `<run>/update_gates/u_<update>.json` | 每个 update 的 actor 与 rollout log-prob 一致性读数：mean\|Δlogp\|、超过 1 nat 的 token 比例（门限 0.2 nat 与 0.01），按上下文长度分桶 |
| `<run>/checkpoints/global_step_<n>.json` | 每次存盘的文件清单、字节数与 SHA-256 |
| `rollout_correctness.json` | 训练 rollout 对数据集答案的逐 update 正确数与总数 |
| `bf16_probe_adjacent.txt`、`bf16_probe_cumulative.txt` | 第 7 层 down_proj 单张量（45,088,768 个元素）上相邻存盘与自起点累计的 BF16 元素改变比例和相对 Frobenius 位移，并与官方 100 步间隔对照；相邻存盘取每臂最近两对（runA 为第 38→40、40→42 个 update，runB 为第 36→38、38→40 个 update） |

## 8. code

| 路径 | 内容 |
|---|---|
| `olmo_analysis/` | 权重几何 Pass1 至 Pass9、外推 checkpoint 构造（`extrapolate_ckpt.py`）、AIME 样本分析与绘图脚本；`inference_manifold/` 为运行时几何指标（`manifold_metrics.py`）、前向与 T1 控制；路径常量在 `olmo_utils.py` |
| `evaluation/` | 多任务生成评测与 production 评分器（`eval_pass8.py`）、AIME 分片评测（`eval_aime_sharded.py`）、多选题 Markdown 答案标题适配器、MATH-500/BBH 与 GSM8K 的替代评分器，`fixtures/` 为评分器测试夹具 |
| `geometry/olmo3_per_layer_rope.py` | 运行时几何前向的按层 RoPE 设置 |
| `continuation/` | 续训数据的统计脚本：逐 update 正确率、BF16 改变比例抽样；训练代码见第 7 节 |

代码中的绝对路径指向 codelab 与 DolphinFS 上的存储位置；在本包内运行时，需要把数据路径换成 `data/` 下对应的目录。

## 9. 规模

各文件的字节数与 SHA-256 以 `MANIFEST.tsv` 为准。包内最大的是 `data/functional/`（约 2.0 GB），其次是 `data/weight_geometry/`（约 0.7 GB）与 `data/runtime_geometry/`（约 0.5 GB）；全部数据、代码与图合计约 3 GB。
