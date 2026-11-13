# AIME follow-up required-cell report

**状态：REQUIRED_COMPLETE_OPTIONAL_C7_PENDING**

本包只交付已经 strict PASS 的 14 个必做 cell。可选 C7 在冻结快照时为
85/90 题，仍在运行，因此没有进入本包的聚合表、run_records 或 gate
集合。整项 15-cell campaign 尚未标记为 `COMPLETE_VALIDATED`，原有终态 observer
继续等待 C7、平台 `SUCCEEDED` 与最终总包。
冻结时续跑平台状态为 `RUNNING`，不是整体终态。

必做范围已从集群 raw 结果通过冻结的 `aggregate_results.py --cells mandatory`
重新聚合：AIME 900 行、Math500 2,000 行、run_records 14 条、共 44,800 个样本。
14 份 strict gate 收据随包交付。旧评测前缀和 25 个非评测保护对象均按既有
SHA256 核验，本次没有重跑随机游走或修改共享结果。

## B2 协议限定

B1、B2 都使用 tp2 base overlay 的实际 dapo `chat_template.jinja`。B1 的 user
消息是原题。B2 的 user 消息在原题后增加两个换行和
`Think through the problem step by step and put your final answer in \boxed{}.`。
现有回放代码没有单独的 thinking user 模板，因此该字符串是本轮的明确定义。
B2 不是 Code/Mix 原生 thinking chat template 的等价基线；跨赛道比较必须保留
这个限制。

## 数据边界

D1/D2 的 32k 列来自同一批完整生成的前 32,768 个原始生成 token 重新解码
判分。样本全文、prompt token ID 与生成 token ID 只保留在集群 `raw/`，没有
进入本 zip。`tp2_allwrong_tails.jsonl` 是用户明确要求的 1,500 字符尾部导出，
不是完整生成文本。

本包包含 compact 表格、代码、来源、报告和验证证据。`MANIFEST.tsv` 与
`SHA256SUMS` 覆盖包内交付文件；外部 `.validation.json` 记录 ZIP CRC 和逐文件
复核。当前环境没有已配置的 Mac 写入连接，因此提供本机与共享文件路径供下载，
不声称已经直接写入 Mac 文件系统。
