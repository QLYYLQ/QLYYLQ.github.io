# C7 单独补充包

状态：COMPLETE_VALIDATED_C7。90 道题、2,880 个样本全部通过严格验收。
验收时间：2026-10-27T06:45:21.794556+08:00。HOPE 64985603 / [运行节点] 已 SUCCEEDED。
全部 15 格的原始总包已 COMPLETE_VALIDATED，本补充包只包含 C7。

模型为 allenai/Olmo-3-7B-RL-Zero-Code 末步，原生 thinking 模板；
T=1.0、top_p=1.0、seed=1、每题 32 样本、max_tokens=32,768、
max_model_len=49,152。prompt 三方 token 核对全部通过，模型小文件
SHA256、镜像、引擎版本与评分函数均见 run_records.json。

实测 pass@1：22.395833%；逐题无偏 pass@16 的平均值：
53.402237%；撞上限率：2.638889%；
平均生成 token 数：8527.893。
本报告不对种子间差异作显著性判断。

followup_cells_aime.csv 只有 C7 的 90 行，run_records.json 只有 C7 的一条记录。
逐题表由冻结的 aggregate_results.py --cells C7 独立生成，重新校验原始
results、samples、final 的 SHA256，并与最终总表中的 C7 行逐字段一致。
evidence/ 包含单格验收、聚合验收、原生 worker 回执和全任务完成证据。
code/evaluator/ 是原样冻结代码和配置；其中注册表覆盖全任务，供核对来源。

样本全文、prompt token ID 和生成 token ID 留在集群，不进入本 ZIP。
本包解压到 training_dynamics/followup_20261025_C7/，不会覆盖此前必做包。
读取必做包与本包的表时按行拼接；如果使用全量最终包，则不再追加本包，以免重复 C7。
MANIFEST.tsv 和 SHA256SUMS 可校验交付文件；未声称已直接写入 Mac。
