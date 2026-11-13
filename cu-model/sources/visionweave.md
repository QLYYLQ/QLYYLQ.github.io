# 视觉细节按内容分配：VisionWeave 解读与 CUA SFT 造数管线增补

整理日期：2026-10-13。本文是《CUA SFT 数据管线与扩展调研》（2026-10-10，下称“原报告”）的增补，原报告没有改动。论文是 *VisionWeave: Weaving Elastic Visual Representations as a Native Capability of MLLMs*（arXiv 2610.07987v1，2026-10-06，预印本，下称 VW）。

*阅读约定沿用原报告：标「**论文报告**」的段落只写论文或作者代码仓里能核对的事实；「**推断**」「**建议**」是针对本项目的判断；「**项目数据**」是从项目已有文件里重新算出的数；其他外部资料在文中注明出处。论文数字的核验方式见第 9 节，原报告的术语（predict、check、`labels_only` 等）见文末附录。*

## 结论先行

VW 要模型学会的行为是：**看到一张图后，按内容决定每一块用多细的表示。** 信息密的地方保留原生细节，背景和大块空白用粗表示，但每个区域都留在输入里；训练目标是让回答和看全细节时一致。它不需要任何“哪里重要”的人工标注，监督全部来自同一个模型在全细节输入下的输出，也就是自蒸馏。在 Qwen3.8-27B 上，8 个 benchmark 平均省 43.0% 的视觉 token，平均保留 98.9% 的原生分数。27B 上省得最多、也最怕粗细放错位置的是 GUI grounding：ScreenSpotV2 省 55.1%，分数从 94.42 降到 91.43；粗块数不变、位置随机打乱时只剩 59.28；同等节省下，FastV† 和 VisionZip 只剩 43.79 和 45.68。4B 的情况不同，ScreenSpotV2 只省 24.1%，低于 4B 的平均节省 35.8%。

对 Cyrus 下一步的 SFT 造数管线，结论有五条：

1. **VW 模型本身给不了 `<predict>` 标签。** 它的 router 只处理已经到手的帧，没法在下一屏到达之前选区。它能改的是 O_t、历史帧，以及 check/revisit 时看到的观测怎样编码。
2. **最值得借的是它的“保真度”尺子。** 以同一个模型看全细节时的输出为基准，衡量某种省下来的表示（粗化、裁剪、降采样）还够不够用。在下一屏到达后离线计算，它能给 check 行、`acceptable_bundles` 和 predict 候选增加一种不靠人工的 silver 标签（6.2 节）。
3. **最值得试的是改观测合同。** 把“只返回授权 crop”换成“全屏粗看，选中区域细看”。学生始终看得到全局，和全观察 teacher 之间的信息差小得多，蒸馏更好做；原生实现下，多块 crop 各自被放大到最小像素的浪费也没有了。代价是每次观测的 token 更多，粗算是现在 3 块 crop 的 1.6 到 2.2 倍（6.4 节）。这一条要先做对照实验再定（第 7 节）。
4. **原生弹性编码器是一次基座改造，不能和第 1 轮 LoRA SFT 放在同一轮。** 它要训练 pooler 和 router，Stage 3 还要更新 LLM。论文权重没有公开，代码只开放了 dense Qwen3.5 的推理和 SGLang 服务。移植到 Qwen3-VL 要自己实现，还要处理 Qwen3-VL 的 DeepStack 多层特征。
5. **论文的 GUI 证据偏窄，要先在本项目的数据上测。** GUI 只有 ScreenSpotV2 一个 benchmark，表格只给了每图 512 token 的分数；小目标（ScreenSpot-Pro）、OSWorld-G 和多步 agent 都没测。在 27B 的 ScreenSpotV2 上，直接降采样到一半 token 也有 91.04，和 VW 的 91.43 很接近。

最先能做、又不用改模型结构的，是第 7 节的三个小实验。

## 1. 论文要模型学会的行为

**论文报告**：VW 让模型自己学“视觉粒度”，落到五条可观察的行为上。

- **按块选粒度。** 画面按 4×4 个 ViT patch 分块。每块要么用原生的 4 个细 token（每个覆盖 2×2 patch），要么用 1 个粗 token，后者省掉这一块 3/4 的 token。router 逐块给出“用粗”的概率 p，p 超过阈值 t（默认 0.5）就用粗（§2.2）。
- **不丢区域。** 每块至少留一个粗 token，整张图始终都在序列里，只是有的地方糊一些。剪枝方法做不到这一点：论文的 GUI 示例里，FastV† 把网页上星标按钮的 token 剪掉了，VW 的每个区域都还在（§4.2、附录 B.1）。
- **粗细混排时位置不乱。** 粗 token 放在它覆盖的 4 个细 token 的几何中心，MRoPE 坐标是 (τ, 2I+½, 2J+½)，τ 是时间位置，(I, J) 是块的行列号；粗细 token 共用一个坐标系（§2.2.1）。LLM 要专门训练才读得好这种混合序列：不做 Stage 3 时，27B 的 ScreenSpotV2 只有 66.59，做完是 91.43（附录 E.1）。
- **回答保真。** 学生（粗或混合表示）在 teacher 回答上的逐 token 分布要贴近 teacher（全细表示）。loss 只比较两者的分布，不用标准答案（§2.3）。
- **节省量跟着内容走，推理时可调。** 同一阈值下，27B 在 InfoVQA 只省 16.5%，DocVQA 省 27.3%，三个视频 benchmark 省 49.6% 到 54.2%，ScreenSpotV2 省 55.1%。Figure 9 的文档示例里，一张密集数字表格的 468 个 token 一个都没省。阈值调低可以多省：t=0.25 时，27B 在 Video-MME 上的节省从 54.2% 升到 66.0%，论文称分数约低 0.37 分（按上下文是和默认阈值比）；t=1 时退回全细（§3.5）。

**论文报告**：按论文的描述，有三件事 VW 不做。router 的输入只有视觉塔第 0、L/2、L 层的特征和块位置（L 是视觉塔层数，第 0 层指 patch embedding），没有文本问题（§2.2.2），附录 A 的未来工作也没提按问题决定粒度。它在帧到达之后才做决定，不预测未来帧。粒度只有粗、细两档，多档留作未来工作（附录 A）。

**推断**：放到 CUA 上，VW 直接能做的是读屏时把细节留给文字、图标和小控件，以及把历史帧粗看。按需把某个局部升级成细看，它做不到：router 不看问题、每帧只决定一次，这一步要靠 predict 和 revisit 触发。两者的分工是：VW 回答“这一帧哪里有字、有控件”，原报告的 predict 回答“这个任务下一步要读哪里”，后者取决于任务和 session 历史。

## 2. 方法：结构与三阶段自蒸馏

**论文报告**：结构上新增两个部件，gated spatial pooler 和 router，另外给粗 token 定了位置编码。

| 部件 | 做法 | 设定 |
|---|---|---|
| 细 token | 原生 merger：2×2 patch 特征拼接后过 MLP | Qwen 原生，不改 |
| 粗 token（gated spatial pooler） | 先把 2×2 个 patch 特征加权合成 1 个，再过同一个 merger，所以一个粗 token 覆盖 4×4 patch | 每个特征先过 LayerNorm；逐通道 softmax 门控，加值网络残差；末层零初始化，起点就是均值池化。4B 在 Stage 1 后、省 75% 时，8 个 benchmark 全部优于 pixel-unshuffle（Figure 7） |
| 位置 | 粗 token 放在块中心 | SGLang 里把坐标乘 2、旋转频率减半，用整数位置表示半整数，复用原有 kernel（§2.5） |
| router | 每块一个可学 query，依次在视觉塔第 0、L/2、L 层做局部（本块 4×4 patch）和全局（整帧）cross-attention，共 6 层；线性头输出“用粗”的概率 | 27B 取第 0、13、27 层，16 头，打分头用 FP32（§2.4） |

训练分三阶段。teacher 都是冻结的原生模型（全细 token）；loss 是在 teacher 回答上逐 token 的前向 KL，在 teacher 的 top-512 词表上重新归一化，温度 1，off-policy（§2.3、§2.4）。下表是 27B 的设定。

| | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| 训练对象 | pooler | router | pooler + LLM（ViT、merger、router 冻结） |
| 学生看到 | 全粗，25% token | soft mixing：方向和模长分开插值，100% token | 硬路由，与推理一致 |
| loss | KL | KL + 0.02·L_bal；L_bal 按样本计算，把粗块比例往 ρ=0.8 推（折合省 60% token） | KL；router 头的标量偏置先离线校准到约 50% 节省，训练和推理中都固定 |
| 峰值 / 最低学习率 | 1e-4 / 5e-6 | 1e-5 / 0 | 3e-6 / 0 |
| global batch | 32（packed 序列） | 64（packed 序列） | 512（样本） |
| 步数 | 5,257 | 2,500 | 1,000 |
| 学生最大长度 | 16,384 | 24,576 | 24,576（不 packing） |

Stage 3 的标量偏置在 router 的打分头上，直接改变 p；推理时的阈值 t 再作用在 p 上，两者一起决定实际省多少。偏置是在训练子集上校准到约 50% 节省的，评测时的实际节省随 benchmark 变化，27B 平均 43.0%，4B 平均 35.8%。Stage 1 按回答长度的平方根加权，这在 Stage 2 里引起不稳定，所以 Stage 2、3 改成对所有回答 token 取全局平均。Stage 2 中 router 越训越果断：平均熵从 0.658 降到 0.427 nats，p 落在 [0.4, 0.6) 的块从 64.8% 降到 14.6%，p≥0.9 的块升到 28.3%。

## 3. 数据是怎么造的

**论文报告**：

- 提示：三份公开数据，约 77.7 万条（packing 前），三个阶段用同一份混合。LLaVA-OneVision 约 24.6 万条（图像理解），LLaVA-Video-178K 约 28.1 万条（视频理解），UGround 约 25 万条（GUI grounding）。按条数算 GUI 约占 32%，这个比例是本文算的；论文只给了条数，没给按 token 的比例，也没说用了 UGround 的哪个子集。
- 回答：由原生模型（teacher）生成，学生和 teacher 在同一个回答上逐 token 对齐分布。论文没写解码方式和最大长度，也没提任何按正确率或长度的过滤。
- 监督：粒度上没有任何“哪里重要”的标注。粒度分配只受两样东西约束：粗化之后输出分布变了多少，以及 Stage 2 平衡项和 Stage 3 偏置给出的目标节省量。
- 分辨率：训练时每张图最多 4,096 个原生视觉 token；视频每帧 512，最多 64 帧。按字面算，64 帧就是 32,768 个视觉 token，超过 Stage 2、3 的学生最大长度 24,576，论文没说超长样本怎么处理。评测时原生基线是每图 512 token。
- on-policy 还是 off-policy：在 4B 的 Stage 3 上试过 on-policy（学生自己 rollout），8 项平均 72.21，off-policy 是 72.59，两者各赢 4 项，没有一致收益，所以全程用 off-policy（附录 E.2）。
- 规模：先在 Qwen3.5-4B 验证，再扩到 Qwen3.8-27B；论文称扩到 27B 用了超过 3 万 A100 GPU 小时。

**推断**：这套数据的标签全部来自模型自己。只要有提示和一个冻结的全细节 teacher，数据就能一直扩，不需要人工，也不需要 judge。代价是学生最多学到 teacher 的水平，teacher 的错误也会照学，所以在同一输入下，这类数据只能教“省”，教不了“更准”。固定 token 预算时情况不同：省下的 token 可以换成更多帧或更高分辨率，LongVideoBench 上帧数上限 256 的 VW 就比 128 帧的原生模型高 1.20 分，实验 B 要测的也是这件事。按上表粗算，Stage 1、2 学生端最多分别处理约 27.6 亿和 39.3 亿 token（packing 长度 × batch × 步数，是上限）；Stage 3 是 512 × 1,000，约 51.2 万条样本，不到整份混合的一轮。每条样本还要在全细节输入上跑一遍 teacher，拿到目标分布。

## 4. 主要数字

**论文报告**：下表取自论文 Table 4，只列和 CUA 最相关的行。8 个 benchmark 是 RealWorldQA、DocVQA、InfoVQA、ScreenSpotV2、HallusionBench、VideoOCR、Video-MME 和 LongVideoBench，分数满分 100。括号里是相对原生的变化；“8 项平均”一行括号里的数，是 8 项相对变化的平均，不是两个平均分之比（27B 按平均分相除是 −1.18%）。“VW 节省”是 VW 的自适应节省；降采样、FastV†、VisionZip 都固定省 50%。FastV† 是作者改过的版本，在视觉编码器之后选 token，这样才能在 SGLang 里跑。

| 模型 | Benchmark | 原生（512 token/图） | 降采样 | FastV† | VisionZip | VW | VW 节省 |
|---|---|---:|---:|---:|---:|---:|---:|
| 4B | ScreenSpotV2 | 89.86 | 80.42 | 72.56 | 70.44 | 89.47（−0.43%） | 24.1% |
| 4B | DocVQA | 91.92 | 82.71 | 78.69 | 76.57 | 91.03（−0.97%） | 16.0% |
| 4B | 8 项平均 | 73.25 | 67.87 | 66.86 | 65.97 | 72.59（−0.90%） | 35.8% |
| 27B | ScreenSpotV2 | 94.42 | 91.04 | 49.53 | 49.21 | 91.43（−3.17%） | 55.1% |
| 27B | DocVQA | 92.47 | 83.19 | 77.05 | 76.01 | 91.33（−1.23%） | 27.3% |
| 27B | InfoVQA | 74.13 | 58.48 | 55.49 | 53.96 | 71.61（−3.40%） | 16.5% |
| 27B | 8 项平均 | 77.65 | 72.52 | 67.32 | 66.81 | 76.73（−1.08%） | 43.0% |

本文核算：摘要里的“保留 98.9%”等于 100% 减去这个 1.08%。论文同时给出 FastV† 保留 88.2%、VisionZip 保留 87.5%，这两个是固定省 50% 时的数，而 VW 平均只省 43.0%，所以不是等节省对比。按 VW 的节省量对齐后（附录 E.3），27B 上两者的平均分分别是原生的 90.3% 和 90.6%（按平均分相除）。

和 GUI 有关的消融放在一起看：

| 设置 | 4B ScreenSpotV2 | 27B ScreenSpotV2 | 27B 8 项平均 | 出处 |
|---|---:|---:|---:|---|
| VW 默认 | 89.47 | 91.43 | 76.73 | Table 4 |
| 打乱路由（每图粗块数不变，位置随机） | 80.03 | 59.28 | 71.37 | Table 6 |
| 不做 Stage 3（LLM 没适配混合序列） | 未报告 | 66.59 | 73.15 | 附录 E.1 |
| 节省量和 VW 相同时的 FastV† / VisionZip | 87.34 / 86.08 | 43.79 / 45.68 | 70.10 / 70.33 | 附录 E.3 |
| Stage 1 全粗（省 75%）：gated pooler / pixel-unshuffle | 69.42 / 67.53 | 未报告 | 未报告 | Figure 7 |

**推断**：两张表合起来看，有三点。第一，VW 相对剪枝的优势大部分来自 GUI grounding。27B 的等节省对比去掉 ScreenSpotV2 后，其余 7 项的平均只剩 74.63 对 73.86 和 73.85；打乱路由的 8 项平均降幅是 5.36，去掉 ScreenSpotV2 后只剩 1.53。第二，随机混排粗细对 GUI 伤害很大：粗块数不变、只打乱位置，27B 的 ScreenSpotV2 掉 32 分，4B 掉 9.4 分，4B 打乱后的 80.03 甚至低于省 50% 的均匀降采样（80.42）。这里面可能有一部分是分布偏移，因为 Stage 3 的 LLM 适配的是 VW 自己的路由分布。学到的分配和均匀降采样相比，在 27B 的 ScreenSpotV2 上只高 0.39 分，同时多省约 5 个百分点。第三，全粗表示对 GUI 伤得很重（4B 全粗 69.42，原生 89.86），细 token 要留够、留对，LLM 也要在同样的混合序列上训过，才读得准坐标。

**论文报告**：serving、截图示例和分辨率扫描的数字如下。

- serving（Table 5，与作者 GitHub README 一致）：27B 在 SGLang 上跑 LongVideoBench（2×A100-80GB，TP=2，每帧 1024 token、最多 256 帧）。吞吐从 0.90 升到 2.07 req/min（2.30 倍）；平均 TTFT 从 169.90 s 降到 77.54 s（−54.4%）；平均 TPOT 从 355.64 ms 降到 140.29 ms（−60.6%）；P95 TTFT 和 P95 TPOT 分别降 57.1% 和 59.6%。这一组只报了吞吐和时延，没报节省率；GUI 会话没有测。
- 截图示例（Figure 9，27B，512 token 预算）：三张 GUI 截图里，桌面从 480 个 token 降到 183 个，平板从 468 降到 261，网页从 480 降到 207，分别省 61.9%、44.2%、56.9%；两张文档里，表单从 484 降到 265，密集数字表格的 468 个一个没省。FastV† 在每张图上都省一半。
- 分辨率与帧数（Figure 5、6）：Figure 5 在两个模型、8 个 benchmark（含 ScreenSpotV2）上扫了每图约 128 到 1024 token，论文称 VW 在所有任务和分辨率上都优于降采样。Figure 6 里，LongVideoBench 上帧数上限 256 的 VW 比帧数上限 128 的原生模型高 1.20 分，用的 token 还更少。曲线上的具体数值论文没有给。

## 5. 可信度：哪些能直接用，哪些不能外推

**推断**：这是一篇预印本，权重和训练代码都没公开，也没有第三方复现；§2.3.2 以后的内容（Table 2 到 Table 6、附录）只来自 alphaxiv 的全文转写，Table 4 的平均值和摘要对得上，表内数字也自洽，但没和 PDF 原件逐项对过。在这个前提下，下面几条在论文内部有一致的证据。

- “按块学粒度 + 自蒸馏”这条路线，在两个模型尺度、八个 benchmark 上都成立；有打乱路由、去掉 Stage 3、换 pooler、on/off-policy 四组消融，还有等节省对比和端到端 serving 实测。
- 在 GUI 上，丢 token 的剪枝在节省到一半左右时就会崩。4B 在 24.1% 的同等节省下，FastV† 和 VisionZip 只比 VW 低 2.1 和 3.4 分（87.34、86.08 对 89.47）；固定省 50% 时降到 72.56 和 70.44；27B 在 55.1% 的同等节省下只剩 43.79 和 45.68。原报告 notes 记的 FocusUI 结果方向相同：3B 基座保留 30% token 时，Fast-V 只有 4.8，VisionZip 18.9，FocusUI 40.6。notes 没写这组数用的 benchmark 和全 token 基线（同段其他结果都是 ScreenSpot-Pro），FocusUI 里的 Fast-V 也是原版，不是 VW 改过的 FastV†。
- 保留每个区域、只降细节，比丢 token 稳得多：27B 的 ScreenSpotV2 上，降采样省 50% 还有 91.04，VW 省 55.1% 有 91.43，两种剪枝只剩 49 左右。但粗细不能随机混排，打乱路由后只剩 59.28。所以 CUA 省 token 应该先降细节，丢区域要慎重。

下面几条不能直接外推。

- GUI 只有 ScreenSpotV2。原报告 notes 引过 ScreenSpot-Pro 论文的统计：ScreenSpot 的目标平均约占截图面积的 2.01%，ScreenSpot-Pro 只有约 0.07%。粗化最容易在后者上出错，论文没测；OSWorld-G 和多步 agent 也没测。
- 起点分辨率不同。表格里只有每图 512 token 这一档；Figure 5 的曲线覆盖每图约 128 到 1024 token（含 ScreenSpotV2），但没有数值。本项目小面板每图只有约 180 token（第 6 节），高分辨率桌面截图又常要上千 token。
- 在 27B 的 GUI 上，VW 相对降采样的优势不大：降采样省 50% 得 91.04，VW 省 55.1% 得 91.43。4B 上差距大（80.42 对 89.47），但 VW 只省了 24.1%，节省量不对等。附录的等节省对比没有降采样这一列，“稳定优于降采样”的证据主要在 Figure 5 的曲线里。
- 模型大小会改变 GUI 上的表现：27B 的 ScreenSpotV2 省 55.1%，高于 27B 的平均；4B 只省 24.1%，低于 4B 的平均。本项目的 8B/32B 落在哪一边要实测。
- 底座和工程栈不同。论文用 Qwen3.5/3.8；本项目用 Qwen3-VL-8B/32B，在 NPU（H910C）上跑 HF eager。VW 的服务实现基于 CUDA 上的 SGLang。
- serving 收益测在长视频上，GUI 会话没有服务端数据。

## 6. 和现有管线的衔接与冲突

**项目数据**：先看本项目现在的视觉 token 账本。

- 每张图很小。小面板 40 行（20 个请求，8B、32B 各跑一遍）的 outputs 文件（`evidence/qwen3vl8b_outputs.jsonl`、`qwen3vl32b_outputs.jsonl`，字段 `token_counts` 和 `image_grid_thw`）里，每张图约 720 个 patch（网格如 40×18、20×36），合并后约 180 个视觉 token（最少 180、最多 187），约合 18 万像素。
- 源图被缩得很厉害。按 sha256 去重共 123 张源截图，在 0.90 到 4.49 MP 之间（中位数 4.02 MP），送进模型时面积缩小了 4.9 到 24.4 倍（中位数 21.4 倍）。最常见的是 1344×2992 和 1440×3120 两种手机截图，共 55 张。
- 图占了输入的大头。每个请求 5 到 33 张图，视觉 token 900 到 5,940 个，占输入 token 的 37% 到 70%（中位数 59%）。AGW T2 受限链的 14 个 case 上（本地 `cu_model/docs/AGW_DATA_SCALING_RESULTS_20261006.md` 第 9 节），direct 路线全链累计的 prompt token 在 current-only 下是 49,918，加上历史（warm）后是 104,236，翻了一倍多。

Qwen3-VL-8B 的公开配置（Hugging Face 上的 `config.json`）：视觉塔 27 层、hidden 1152、patch 16、merge 2，DeepStack 用下标 8、16、24 三层的特征。论文 27B 的 router 取第 0、13、27 层，视觉塔层数和这里相同。

**推断**：也就是说，本项目的屏幕是在很低的分辨率下被看的，输入 token 里一半以上花在图上，加上历史帧后总量还要翻倍。VW 省下的 token 可以拿去提高当前屏的分辨率，也可以直接压缩历史帧，两件事都用得上。逐项对照如下：

| 环节 | 现有做法 | VW 带来的变化 | 关系与处理 |
|---|---|---|---|
| `<predict>` | 下一屏到达前只读合法 prefix；O_{t+1} 只进 `labels_only` | router 在帧到达后才决定 | **错位**。predict 主线不变；VW 模型本身产不出 predict 标签，保真度方法可以离线补一种 silver 来源（6.2） |
| check/revisit 时的观测 | 只返回授权 crop，其余记 unknown；每块 crop 被放大到 min_pixels，3 块至少约 147 token（原报告） | 全屏粗、局部细 | **互补，但改变 check 语义**。作为观测合同 v2 做对照（6.4、实验 C） |
| sufficient/insufficient 标签 | crop-only 回放 K 次，加 full-target 对照；“低分辨率够用”借 VisionThink 的整图两档规则（原报告） | 以全细 teacher 的输出为基准，可以细到块级 | **互补**。新增保真度指标，与 K 次回放并列 |
| 特权蒸馏 | GHD 门控；PI-Distill：teacher 比学生多看到的越多，蒸馏越难（原报告） | 学生每块都看得到，VW 用纯 KL、不门控 | **连接**。crop-only 合同下蒸馏必须门控；粗细合同下信息差小得多，但证据落在粗块里时仍要门控（6.3） |
| 分辨率 | 16 次位置错误可能有相当一部分来自分辨率；第 0 轮扫约 200k/800k/1.6M px（原报告） | 省下的 token 可以换成更高分辨率 | **互补**。扫描里加“粗看整图 + 细看局部”一臂（实验 B） |
| 历史帧 | 每请求 5 到 33 张，32B 两次 OOM | 27B 在三个视频 benchmark 上省 49.6% 到 54.2%，分数变化在 −0.30% 到 +0.21% 之间 | **互补**。历史帧可以粗编码；比较 warm 和 current-only 时，两边当前帧的编码要一致 |
| token 账本 | 按 `image_grid_thw` 算 T·H·W/merge²，不按面积估（原报告 notes） | router 之后的 token 数不再等于网格数 | **冲突**。账本加 router 之后的粗/细 token 数，以及 encoder、router 时延 |
| renderer 冻结 | processor/renderer 哈希写进 `run_meta`，训练推理逐字节一致 | router 本身就是 renderer 的一部分 | **冲突**。router 权重、阈值 t、偏置一起冻结并写哈希；router 一变，所有依赖模型的标签都要重算 |
| 训练计划 | 第 1 轮用 LoRA、冻结视觉塔，一次只改一处 | 要训 pooler、router，Stage 3 还要更新 LLM | **冲突**。弹性编码器作为独立的基座分支，第 0 轮之后另起，过门后才给第 2 轮用（6.5） |
| 回归门 | 全观察回归集，含小元素 grounding | “相对全细节的保留率”这套口径 | **连接**。所有省 token 的变体都按保留率报告，并补 ScreenSpot-Pro 和 OSWorld-G |
| serving | 账本记 prefill/decode/encoder ms；vLLM 时延拆分没调研，SGLang 没提（原报告 notes） | SGLang 上的半整数 RoPE；编码器分离部署时随特征传递粗细布局 | **缺口**。效率结论要在真实服务栈上测过才算；NPU 上能不能用要另查 |

### 6.1 采集：多存三样东西

**建议**：

1. **原始分辨率帧。** 历史帧、O_t、O_{t+1} 都保存未缩放的原图和 SHA，不只存送进模型的那一版。粗细表示、降采样和 crop 都要从原图重新渲染，而现在送进模型时面积已经缩了 5 到 24 倍。
2. **全细节 teacher 的输出。** 对每条训练行（四类行，以及通用 grounding 和动作行），用冻结的模型在全细节设置下生成回答，存下回答、teacher checkpoint 和 processor 哈希。“全细节”指同一渲染分辨率下不做任何粗化或裁剪，分辨率取第 0 轮扫描选定的那一档，不必是原图。历史帧沿用低分辨率，免得 32B 在多图请求上 OOM：比如当前屏用 4 倍像素档（约 720 token），历史帧保持约 180 token，33 张图的请求约 6,500 个视觉 token，和现在最多的 5,940 是一个量级。存储允许的话，再存每个回答位置的 top-k 概率（论文用 k=512；按 int32 id 加 fp16 概率算，每个位置约 3 KB），否则训练时在线重算。predict 行的 teacher 和学生过同一份输入白名单，只看 prefix；check/revisit 行的 teacher 可以看完整的 O_{t+1}，它的输出只用来造标签，存进 `labels_only`。
3. **粒度账本。** router 算 renderer 的一部分，所以 router 版本哈希、阈值 t 和偏置跟 processor 哈希一起写进 `run_meta`。每张图的原生网格、router 后 token 数、粗/细块数、细块掩码（RLE），以及每次调用的 encoder、router、prefill、decode 时延，和 `image_grid_thw`、token 数一起写进 `branch` 区。弹性编码器就绪之前，router 相关字段留空。

### 6.2 标注：新增“保真度探针”标签

**建议**：对一个观测和它的 teacher 回答，构造几种省下来的表示 V′：全粗、全粗加某个 bundle 细、只给 crop、整体降采样。对每个 V′ 算两项：

- **分布保真**：逐 token 的 KL(teacher 全细 ‖ 模型在 V′ 下)，按论文的做法在 top-512 上归一化，再对回答 token 取平均，另记最大值。每种表示要一次 teacher-forcing 前向。
- **结果保真**：V′ 下 greedy 解码的动作、坐标或字段是否与全细节时一致。grounding 看是否命中；动作要求类型和参数相同，坐标落在同一个目标元素里。每种表示要一次 greedy 解码。

两项都在阈值内，才算“V′ 够用”。阈值和原报告的 r*/u*/p*/g* 一样，在 calibration 集上冻结。思路类似原报告借来的 VisionThink 规则（高低两档分辨率都 8/8 正确才算“低分辨率够”），区别是粒度细到块级，而且只和 teacher 比一次，不要求 8 次全对。用处有三个（哪一轮进训练见 6.5）：

- **check 行**：给“授权表示够不够”加一个不靠人工的 silver 标签。它和 crop-only K 次回放的结论一致时自动收录，不一致时进 Undetermined。
- **`acceptable_bundles`**：对 DOM/AX、EFR 差分框、WMA 匹配产出的候选 bundle，逐个测“全粗加该 bundle 细”是否保真，删掉多余成员；不保真时，用下面的敏感度图找出缺的块补上。这一步用到 O_{t+1}，结果只存进 `labels_only`。`label_source` 记一个新值 `fidelity_probe`，`prefix_predictability` 照旧单独判，进 predict 正例前仍要过可达性门。`label_source` 的取值现在有两套写法：训练决策文档是 `{oracle, prefix_sampled_validated}`，pipelines notes 是 `{oracle, validated_sample, teacher_corrected}`，加新值之前先统一。
- **块级敏感度图**：把屏幕分块，逐块粗化，记 KL 增量，得到“这一屏对这个回答，哪里不能糊”。每块一次前向，块多时用分层二分减少次数。它可以当任务条件化 router 的监督；在 O_{t+1} 上算出的敏感块也可以当 predict 的 silver 候选，同样只进 `labels_only`，也要过可达性门。

在还没有学出来的 pooler 之前，“粗化”可以先在像素空间近似：把该块按边长缩小一半（每 2×2 像素并成 1 个），再放大回原尺寸。这样不省 token，只用来测敏感度；它只是 VW 粗 token 的近似，结果要标 `proxy=pixel_blur`。

### 6.3 过滤与门控

**建议**：

1. 蒸馏数据和四类训练行分开过滤。论文没提任何过滤；训练弹性编码器用的蒸馏数据，这里建议也不按对错过滤，因为目标是保真；有 GT 的样本记录 teacher 是否正确，分开统计。本项目的四类训练行照旧用原报告的验收规则（K 次回放、judge 一致、可达性门等）。
2. crop-only 合同下的蒸馏必须门控。全观察 teacher 看得到 crop 外的证据，学生看不到，直接 KL 会教学生“看不到也照答”。照 GHD 的思路改写，只在 crop 里确有证据、且学生失败时才蒸馏。粗细合同下信息差小得多，但没有消失：证据如果落在粗块里看不清（例如只占 0.07% 面积的小目标），直接 KL 一样会教学生照答。所以先用敏感度图确认 teacher 依赖的块在学生那边是细的，再直接 KL；否则同样门控，或把这条标成 insufficient。粗细合同下纯 KL 是否够用还只是假设，等到真正用 KL 蒸馏的那一步（第 2 轮起，或弹性基座分支），再拿纯 KL 和门控 KL 各训一版，比较 false-sufficient。
3. 小目标分层常驻。训练混合和回归门都保留目标面积小于 0.1% 的 grounding 样本（ScreenSpot-Pro 式），单独报告，粗化最可能在这里出错。
4. 监控路由塌缩。每轮报告各页面族的细块比例和节省率分布。论文 Stage 2 的目标粗块比例 0.8（折合省 60% token）、Stage 3 校准的约 50% 节省，都是为它自己的混合数据定的，CUA 数据要在自己的 calibration 集上重定。
5. 因果审计不放松。任何用到 O_{t+1} 的保真度计算只进 `labels_only`；predict 行的 teacher 输入白名单与学生相同。

### 6.4 观测合同 v2：全屏粗看，选中区域细看

**建议（待实验 C 验证）**：现在的合同是“只返回授权 crop，其余记 unknown”。v2 改成：O_{t+1} 整屏以粗表示返回，predict 选中的块（以及 revisit 追加的块）用细表示；check 判断“细节够不够”，revisit 就是“把这些块升级成细”。历史帧在 v2 下全部粗看。

按 VW 的结构，原生有 N 个细 token、细块占比为 f 时，总 token 数是 N/4 + 3fN/4。f=10% 时是 0.325N，f=20% 时是 0.4N。代入本项目：现在一张约 18 万像素的整图约 180 token。如果 O_{t+1} 改用 4 倍像素（约 74 万像素，原生 N=720 个 token）渲染，全粗正好也是 180 token，和现在的整图一样多；再细看 10% 的块，共 234 token。现在 3 块 crop 的 bundle 至少约 147 token，v2 每次观测大约贵六成。弹性编码器到位之前，可以用“缩略整图加高分辨率 crop”来近似（3 块 crop 时共 4 张图），现成的 Qwen3-VL 就能跑；缩略图就用现在约 180 token 的整图的话，加上 3 块 crop 共约 327 token 起，是 crop-only 的 2.2 倍左右。

v2 下全局一直在，位置偏了也能在粗图上发现并发起 revisit；学生和全观察 teacher 的信息差只剩分辨率这一项，蒸馏更好做，粗块里看不清的证据仍按 6.3 门控。原生实现里整屏只编码一次，也不再有多块 crop 各自被放大到最小像素；近似方案里 crop 仍会被放大。除了 token，代价还有三处：check 的状态集要加一个 `seen_coarse`，因为粗区域是“看到了但模糊”，`visibly_absent` 在粗区域上可能误判；“预算”从像素面积变成 token 数；VW 的 LLM 是在 router 选出的粗细分布上适配的，v2 的细块由 predict 决定，分布不同，LLM 要在 v2 自己的分布上训过。

### 6.5 放进哪一轮

**建议**，对应原报告的三轮（大致对应训练决策文档的 S0、S1、S2）：

- **第 0 轮（冻结与审计）**：加上 6.1 的三类采集字段；统一 `label_source` 词表；在账本里给 router 字段留好位置；跑实验 A、B、C。
- **第 1 轮（首次 SFT）**：主线不变，仍是 LoRA、冻结视觉塔、text-ROI。实验 C 显示 v2 更好时，check/revisit 行按 v2（缩略整图加 crop）渲染，训练和推理保持一致；这一步会连带给 check 状态集加 `seen_coarse`，预算也改按 token 计，除此之外第 1 轮不再加别的改动。`fidelity_probe` 在这一轮只记录（check 行的 silver 标签和 bundle 的 silver 来源都算），和 K 次回放及其他来源对照，不进训练。
- **弹性基座分支（与第 1 轮并行，但不混在一起）**：在 Qwen3-VL-8B 上复现 VW，先做只训 pooler 和 router 的 Stage 1、2，再做更新 LLM 的 Stage 3。数据用 CUA 化的混合：UGround 式 grounding、本项目四类行的提示、用多帧 session 代替视频，再加小目标分层；teacher 是全细节设置下的 Qwen3-VL-8B。移植时要处理 DeepStack：按 transformers 的实现，config 里的下标 8、16、24 从 0 起算，即视觉塔第 9、17、25 层的输出，各自过一个 merger 后加到 LLM 前 3 层输出的视觉位置上；VW 的层号里第 0 层是 patch embedding，两边差一位。粗 token 位置上这 3 路特征怎么给，论文没有涉及。过门条件：按每个评测集的平均视觉 token 数对齐后，小目标分层、OSWorld-G 和全观察回归都不低于“直接降采样到同样 token 数”的对照，容差和其他阈值一起在 calibration 集上冻结；小面板样本太小，只用来查有没有明显退化。同时在实际服务栈上测端到端时延，确认省下的 token 换成了时延收益。过门之后，以它为基座重跑第 1 轮的 text-ROI SFT，再进入第 2 轮。
- **第 2 轮起**：实验 A 显示敏感块和已复核的 evidence box 重合度够高、第 1 轮记录的探针标签和 K 次回放一致率也够高时，`fidelity_probe` 作为 check 行和 `acceptable_bundles` 的 silver 来源进训练。rejection-SFT 里“同预算”的比较一律按 token 数，不再用像素面积。弹性基座过门只说明 router 自己选细块时没问题；要把 revisit 实现成“块升级”，还要再验证由 predict 指定细块时的效果。

## 7. 先做的三个小实验（都不改模型结构）

**建议**：

- **实验 A：像素空间敏感度探针。** 在小面板的 10 个 seed 和 T2 的 14 个 case 上做。基准是同一分辨率下不做任何粗化时 8B/32B 的输出；先在现在的渲染（约 18 万像素）上做，再在 v2 设想的 4 倍像素上做一遍。块按 VW 的大小切（每块 4×4 patch，即渲染图上 64×64 像素），块多时先分层二分；逐块按 6.2 的像素近似粗化，测 KL 增量和输出是否改变。再把单独粗化后都没影响的块一起粗化，复测一次，用来估计按内容能省多少。另一个问题是敏感块和已复核的 evidence box、acceptable bundle 重合多少：重合高，`fidelity_probe` 才适合当 bundle 的 silver 来源；重合低，就只留作诊断。
- **实验 B：分辨率 × 表示。** 并进第 0 轮的三档 O_t 扫描（约 200k/800k/1.6M px），每档分别用“整图”和“缩略整图加高分辨率 crop”两种表示。warm 和 current-only 两种设置下 O_t 的渲染完全相同，历史帧固定用现在的低分辨率。报告有用选区、位置误差、真实 processor token 和时延，按实测 token 数画出成本和效果的曲线来比较，不强行对齐 token。目的是量出 16 次位置错误里由分辨率造成的那部分，同时看两种表示谁的曲线更好。
- **实验 C：观测合同对照。** 在 T2 受限链的 14 个 case 上，check/revisit 分别在“只给 crop”和“缩略整图加 crop”两种合同下各跑一遍，比较 false-sufficient、无益 revisit、补看后恢复、总 token 和时延，并报告保真度标签和 K 次回放标签的一致率。

三个实验的阈值都先在 calibration 集上冻结，再看结果。B 和 C 用的是没在这种输入上训练过的现成模型，结果可能低估 v2。样本小，结果只用来决定第 1 轮用哪个合同，以及 `fidelity_probe` 从第 2 轮起能不能当 silver 来源，不能当方法结论。

## 8. 还没回答的问题

- 任务条件化：VW 的 router 不看任务，而 CUA 里“哪里该细”取决于任务和历史。一个自然的组合是把 predict 的输出当 router 的先验或强制细块，但这在论文范围之外，需要自己验证。
- 时间冗余：相邻截图大面积不变，VW 没有利用跨帧冗余。session 内“没变的区域粗看或复用”需要另外设计；原报告 notes 里的 GUI-KV、GUIPruner 是相关工作。
- 坐标读出：块中心是半整数位置，Qwen3-VL 的 [0,1000] 坐标输出会不会漂，需要实测。
- 训练成本：论文扩到 27B 用了超过 3 万 A100 GPU 小时，8B 的成本要按自己的数据量估；NPU 上能不能用 SGLang，也要另查。

## 9. 来源与核验

- 论文正文：arXiv 2610.07987v1（https://arxiv.org/abs/2610.07987）。PDF 原件没下载到：这次的云端环境和本机文件夹连接都不能直接访问 arxiv.org，网页抓取工具读 PDF 时又被限流。摘要到 §2.3.1 是用网页抓取工具读的 arXiv HTML 版（抓取在 §2.3.2 中断）；全文含附录 A 至 E 读的是 alphaxiv 提供的全文 markdown（https://www.alphaxiv.org/abs/2610.07987.md）。
- 交叉核对：摘要和引言里的数字（43.0%、98.9%、16.5% 到 55.1%、88.2%、87.5%、2.30 倍、−54.4%、−60.6%）和 Table 1 在两个版本中一致；Table 5 与作者 README 一致；Table 4、Table 6、附录 E.1 和 E.3 的平均值与相对变化，都按表内原始分数重算过，全部在四舍五入范围内一致。§2.3.2 以后的数字只有 alphaxiv 全文这一个来源。Figure 7、9 的数字来自图中标注的转写，可信度低一级。
- 代码：https://github.com/FFY0/VisionWeave 。README 写明权重因内部政策暂不可用，待合规审批；已开放的是 dense Qwen3.5 的推理和 SGLang 服务，页面上没有训练代码。
- Qwen3-VL：结构来自 Hugging Face 上 Qwen3-VL-8B 的 `config.json`；DeepStack 的层号起算和注入位置来自 transformers 5.19.0 的 `models/qwen3_vl/modeling_qwen3_vl.py`。
- 项目数据：token 账本和源截图尺寸来自项目共享文件夹 `/mnt/project-files/cu_model_project_refs_20261010/evidence/` 下的两份 outputs 文件（`request_runtime.images`）和 `requests.jsonl`；T2 的 token 数来自本地 `cu_model/docs/AGW_DATA_SCALING_RESULTS_20261006.md` 第 9 节。
- 原报告与 notes：管线各环节、FocusUI、ScreenSpot 与 ScreenSpot-Pro 的目标面积、crop 最小像素等，引自 `/mnt/project-files/research_reports/` 下的原报告和 `CUA SFT 数据管线与扩展调研_notes/`；文中的 pipelines notes 指其中的 `pipelines_flywheels.md`。训练决策文档指 `cu_model_project_refs_20261010/provenance/source_docs/SESSION_PREDICTION_TRAINING_DECISIONS_20260927.md`。

## 附录：原报告术语速查

定义摘自原报告、它的 notes 和训练决策文档，以原文为准。

| 术语 | 含义 |
|---|---|
| O_t、O_{t+1} | 动作前的当前屏；动作后的下一屏 |
| `<predict>`、predict 行 | 下一屏 O_{t+1} 到达前，只读合法 prefix（任务、截至 t 的截图和动作、O_t、已发出的动作），输出要看的区域，坐标是 [0,1000] 的 xyxy |
| 授权 crop | O_{t+1} 到达后，只把 predict 选中的区域按 crop 返回，其余记 unknown |
| 观测合同 | 规定 check/revisit 时模型能看到什么、以什么形式返回 |
| check、revisit | check 判断授权 crop 里的证据够不够（sufficient、insufficient、visibly_absent、unknown）；不够时 revisit 补看区域 |
| 四类训练行 | predict、sufficient-check 加动作、insufficient 加 revisit、post-revisit；都只监督末尾的 completion |
| `prediction_input`、`labels_only` | 前者是 predict 行允许进模型输入的字段；后者只用来造标签，永不原样进输入（完整 O_{t+1} 像素、目标 DOM/AX、URL、未来动作、teacher ROI 等）。check/revisit 行另外能看到授权 crop（v2 下是整屏粗表示加细块）。因果审计按每类行的输入清单检查，本文说的“白名单”就是这份清单 |
| `acceptable_bundles` | 可接受的区域组合，组内是 AND、组间是 OR，例如 `OR[AND(rA,rB),AND(rC)]` |
| `label_source`、`prefix_predictability` | 前者是 bundle 标签的来源；后者记该区域能否只凭 prefix 预见（`prefix_supported`、`target_state_dependent`、`unknown`） |
| silver、gold | silver 是自动产生、没经人工确认的标签；gold 是人工金标。silver 不会自动升为 gold |
| 可达性门 | prefix-only 的候选与 oracle 区域重叠，或 prefix 里有该位置的布局证据，才进 predict 正例；否则只当 revisit 目标或诊断 |
| DOM/AX、EFR、WMA | oracle 区域的三个来源：DOM/AX 节点框；EFR，前后两屏像素差分得到的变化框；WMA，前后两屏元素的匈牙利匹配 |
| K 次回放、full-target 对照 | 只给授权 crop 让模型作答 K 次；K 次全对、和给完整目标屏时结论相同、且动作落在 crop 内，才算 sufficient |
| false-sufficient | check 判了 sufficient，证据其实不够 |
| r*/u*/p*/g* | predict 验收四项（覆盖可接受 bundle、crop-only 回放效用、预算、精度）的阈值，在 calibration 集上冻结 |
| calibration 集 | 原报告按 session 加近重复簇切出 train、calibration、test 三份，calibration 那份专门用来定阈值，在看 held-out 结果之前冻结 |
| Undetermined | 异构 judge 意见不一致、不自动收录的样本 |
| GHD 门控 | 只在学生失败、且多看了下一屏的 teacher 能恢复示范动作时才蒸馏 |
| `run_meta`、`branch` | schema 里的两个区：`run_meta` 存 processor 配置哈希等整次 run 不变的信息；`branch` 存每条分支的 `image_grid_thw`、token 数、时延和 lineage |
| 第 0、1、2 轮 | 原报告的三轮：冻结与审计；首次 SFT（LoRA、冻结视觉塔、text-ROI）；rejection-SFT。大致对应训练决策文档的 S0、S1、S2，S3（可选 DPO）和 S4（可选 region head）本文没有涉及 |
| text-ROI | 区域以文本坐标输出，不加专门的 region head |
| 小面板、有用选区、16 次位置错误 | 小面板是 20 个请求（10 个 seed × direct/forced）在 8B、32B 上各跑一遍、共 40 行的 base 评估；有用选区要求位置和任务用途同时判对；40 行里位置判错的有 16 行 |
| direct、forced | 直接输出；先强制写出 reference 和布局分析再输出 |
| T2 受限链、14 个 case | AGW 在 2026-10-06 做的离线受限观察链实验；14 个 case 的 evidence box（回答所需证据在屏幕上的框）由 AI reviewer 复核，不是人工金标 |
| warm、current-only | 带历史帧；只给当前屏 |
| H910C、HF eager | 项目跑模型用的 NPU；Hugging Face transformers 的 eager 推理 |
