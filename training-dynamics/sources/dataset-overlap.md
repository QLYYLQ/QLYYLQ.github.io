# 第 9 项与旧 Code T=0.6 逐题结果交付

## 结论

`dolci_overlap.csv` 有 90 个数据行，覆盖 `problem_idx=0..89` 和
`uid=aime-000..aime-089`。其中 19 题与 Dolci-RL-Zero-Math-7B 的训练集题面
逐字相同，另外 71 题没有逐字相同的训练题。19 题的 `problem_idx` 为：

`2, 3, 11, 14, 15, 20, 25, 28, 29, 32, 48, 49, 56, 58, 60, 68, 70, 77, 83`

这与最终报告使用的 19/71 分层和已有注册映射完全一致。

## 匹配与编号规则

- AIME 顺序是 `test.jsonl` 的 20 行在前、`train.jsonl` 的 70 行在后，按物理行序组成
  `problem_idx=0..89`；`uid` 是对应的 `aime-000..aime-089`。
- 重合判据沿用报告注册口径：AIME 的完整 `problem` 字符串与 Dolci train parquet
  中单条 user prompt 的完整 `content` 做 Python 字符串完全相等比较。不去首尾空白，
  不做任何归一化、模糊匹配或改写匹配。
- `dolci_row_id` 是 Dolci train parquet 的零起始物理行号；19 个命中各自都只有一条
  匹配行。未命中行留空。

## 19 个命中

| problem_idx | uid | dolci_row_id |
|---:|---|---:|
| 2 | aime-002 | 5075 |
| 3 | aime-003 | 5052 |
| 11 | aime-011 | 5081 |
| 14 | aime-014 | 5077 |
| 15 | aime-015 | 5071 |
| 20 | aime-020 | 5085 |
| 25 | aime-025 | 5041 |
| 28 | aime-028 | 5064 |
| 29 | aime-029 | 5076 |
| 32 | aime-032 | 5069 |
| 48 | aime-048 | 5067 |
| 49 | aime-049 | 5087 |
| 56 | aime-056 | 5083 |
| 58 | aime-058 | 5042 |
| 60 | aime-060 | 5062 |
| 68 | aime-068 | 5068 |
| 70 | aime-070 | 5043 |
| 77 | aime-077 | 5058 |
| 83 | aime-083 | 5054 |

## Gold 与来源核验

- 回放 `statistics/problem_metrics.csv` 有 32 个 label × 90 题 = 2,880 行；每个
  `problem_idx` 的 `uid` 和 `gold_answer` 在 32 个 label 间一致。
- AIME 原始 90 个答案与回放逐题表的 `gold_answer` 全部按整数相等。
- 19 个题面命中的 Dolci `ground_truth` 与对应 AIME 答案也全部按整数相等。
- 其中 5 个 AIME 原始答案保留三位数前导零：`049`、`081`、`033`、`012`、
  `072`；Dolci 和回放表存成 `49`、`81`、`33`、`12`、`72`。这是字符串表示差异，
  整数答案相同。题面重合标记不使用答案字段。
- 当前 AIME 的 90 组题面/原始答案哈希与 2026-09-27 注册映射逐行一致；本次独立重算
  的 90 个重合标记和 Dolci 行号也与注册映射逐行一致。

关键输入 SHA256：

- AIME test：`c9d73d754416d619b4aa926fdb34975709c298eaead84507c02ad3eb9b378bfe`
- AIME train：`76edecd54e39fdd88a3bf90d38115d8c3ab608a6d0bf14f8aea74df678dbc8da`
- Dolci train parquet：`1e15f56845e70dad480fb5e6833bffea974ecf6c4341ea4530586694b7a1675c`
- 回放 problem_metrics：`31e3516387b56d6ee4dd3233681ead134766034ec21751f6cc3d253c65740d90`
- 已注册 overlap map：`67b2c58eea0095a27b903a8886819438fc197cf7e4f3708b326f297aa28078ec`

输出 `dolci_overlap.csv` SHA256：
`5b369724b9c29e50edea5a6534c5c9e66ab6db55bdc445534dc5dae43780eba4`。
完整逐行证据见 `evidence/dolci_validation.json`，重算代码见
`build_dolci_overlap.py`。

重算命令（开发机的 pyarrow 需要使用虚拟环境自带的新版 `libgcc_s`）：

```bash
LD_LIBRARY_PATH=$REMOTE_HOME/.venv/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} \
  $REMOTE_HOME/.venv/bin/python \
  local_results/followup_20261025/dolci_oldcode/build_dolci_overlap.py
```

## 旧 Code T=0.6 逐题结果

`old_code_t06/` 保存了 C5、C6 配对所需的两份旧结果，均从指定源目录逐字节复制，
每份都是 1 条协议 meta + 90 条逐题记录：

| label | bytes | SHA256 | 汇总 correct samples | 汇总 cap hits |
|---|---:|---|---:|---:|
| allenai__Olmo-3-7B-RL-Zero-Code-step_2500 | 58,580 | `3b4bad995569c709d77703bcbb7cf93f86f6e02799393019a0f6401e0e1226c7` | 803 | 334 |
| allenai__Olmo-3-7B-RL-Zero-Code | 58,407 | `bfec4125ae1513e2a8eb9345a19ac2af68642c61542410a93acb26b1c34664ab` | 862 | 252 |

两份 meta 均确认 `temperature=0.6`、`top_p=0.95`、`seed=0`、`n=32`、
`k=16`、`max_tokens=32768`、`max_model_len=49152` 和 `thinking` 模板。
源/副本 `cmp`、大小及 SHA256 全相同；题号、UID、每题样本数组长度和
`correct == sum(correct_vec)` 全部通过。详见 `old_code_t06/manifest.json` 与
`old_code_t06/validation_evidence.json`。
