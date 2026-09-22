# Library 日期匹配审计（2026-09-22）

本轮使用提供者已核验的 Library 日期证据，重新匹配 main 冻结总体中原始 668 条无日期来源记录。全部 1,283 条记录、原有 615 条日期、分类、分数及来源身份保持不变。

## 结果

| 处理结论 | 记录数 |
| --- | ---: |
| 采用适用于目标记录的日期 | 437 |
| 候选日期未建立目标版本的发布／介绍事件 | 202 |
| 身份或版本无法确定 | 2 |
| 在 1,107 条证据中无匹配 | 27 |
| 原始无日期目标记录 | 668 |

绘图输入为 **1,052 条有日期 + 231 条无日期 = 1,283 条**。437 条补充中，422 条为日精度，15 条为月精度。所有采用的日期值均来自快照中的 `releaseEvidence.date`，没有从旧 156 条结果兜底。

| 来源 | 原始无日期 | 本轮补全 | 剩余无日期 |
| --- | ---: | ---: | ---: |
| artificial_analysis | 8 | 6 | 2 |
| llm_stats | 645 | 423 | 222 |
| model_reports | 11 | 8 | 3 |
| opencompass_hub | 4 | 0 | 4 |

## 输入与身份规则

- 冻结软件提交：`8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`；发现截止日：2026-09-07。
- 原始 Library 文件：本地 3,010 条版本，SHA-256 `e95cb671b15d3bd89d9abe44cb0ebd42c278a6609288d0eae6904ca1e219c99d`。该版本不同于作者消息中的 2,992 条版本；本轮不读取滚动的 GitHub main。
- [Library 快照](library-reviewed-dates.json) 提取全部 1,107 条非空 `releaseEvidence` 记录，保留完整日期证据、身份字段、原始记录位置及哈希。源文件其余记录不成为日期来源，也不加入论文总体。
- “人工核验”来自提供者的说明。本轮进行身份、版本与事件适用性审查，不声称重新人工核验了所有原始网页。
- 初始来源 ID 匹配为 619 条唯一候选、2 条多候选、47 条无此类匹配；名称仅用于检索候选，不自动授权日期迁移。
- [明确的身份／事件审查](library-date-match-reviews.json) 绑定输入快照和 census 的哈希，保存跨来源映射、Plus 版本消歧及适用性例外。
- `0001-01-01` 是未知占位值。月精度不会补为某一天；任何可能跨越截止日的月份都不能作为已证实的截止日前日期。
- 日期的事件包括论文介绍、具名组件介绍、实际任务数据开放等；不把底层数据集年龄、模型发布时间或某次结果披露自动作为当前版本发布日期。组件来源记录继续各自计数，不代表独立 benchmark-family 发布次数。

## 旧 156 条结果对照

旧集合中，140 条在本轮仍得到支持，16 条保留未知；另有 297 条是旧集合之外的新补全。共有 18 条旧集合记录的候选日期值不同（包括 3 条日期精度范围重叠）；这是日期值对照，不代表全部都能采用。

| 来源记录 | 旧日期 | 本轮候选日期 | 本轮结论 |
| --- | --- | --- | --- |
| `llm-stats:beyond-aime` | 2025-04-14 | 2025-06-17 | accepted |
| `llm-stats:global-mmlu-lite` | 2024-12 | 2024-12-04 | scope_not_release |
| `llm-stats:groundui-1k` | 2024-10-02 | 2024-03-26 | scope_not_release |
| `llm-stats:imagemining` | 2026-04-29 | 2026-04-28 | accepted |
| `llm-stats:mathverse-mini` | 2024-03-22 | 2024-03-21 | scope_not_release |
| `llm-stats:mega-mlqa` | 2023-03-22 | 2019-10-16 | scope_not_release |
| `llm-stats:mega-tydi-qa` | 2023-03-22 | 2020-03-10 | scope_not_release |
| `llm-stats:mega-udpos` | 2023-05-19 | 2020-03-24 | scope_not_release |
| `llm-stats:mega-xcopa` | 2023-03-22 | 2020-05-01 | scope_not_release |
| `llm-stats:mega-xstorycloze` | 2023-05-19 | 2021-12-20 | scope_not_release |
| `llm-stats:mle-bench-lite` | 2024-10-09 | 2024-10-08 | accepted |
| `llm-stats:mm-mt-bench` | 2024-09-17 | 2024-10-09 | accepted |
| `llm-stats:surds` | 2025-05-27 | 2024-11-20 | scope_not_release |
| `llm-stats:swe-atlas` | 2026-03-04 | 2026-05-08 | scope_not_release |
| `llm-stats:usamo-2026` | 2026-03-28 | 2026-03 | scope_not_release |
| `llm-stats:usamo25` | 2025-03-27 | 2025-03 | scope_not_release |
| `artificial-analysis:apex-agents-aa` | 2026-04-08 | 2026-01-21 | scope_not_release |
| `model-reports:harbor_index` | 2026-07-07 | 2026-07-28 | identity_unresolved |

具体处理理由和原始 URL 见 [全部 668 条匹配表](library-date-matches.csv) 与 [完整 JSON 审计](library-date-matches.json)。例如：HumanEval+／MBPP+ 使用 Plus 版本日期；SURDS、GroundUI-1K 及 MEGA 组件不继承父版本日期；BeyondAIME 和 MM-MT-Bench 分别保留本轮证据指向的数据开放或论文／数据事件，并显示更早的历史介绍日期。旧证据只用于身份佐证及冲突发现，所有输出日期值仍取自本轮快照。

## Figure 6 与敏感性

Panel A 保留全部 1,283 条记录，其中 132 条日期早于 2023，920 条位于 2023 H1 至截止日，231 条仍放在无日期列。Panel B 使用原有样本量和来源构成规则重新计算，合格半年度为 2023 H1–2025 H2。没有为了恢复旧曲线改变筛选阈值或分类。

重加权使 agentic 占比最多变化 6.5 个百分点，正文因此改为报告敏感性，而不再声称来源构成影响很小或已被排除。这些曲线描述已收集且有日期的来源记录，不估计全领域的独立 benchmark 发布率。

## 复现与验证

```bash
python scripts/match_library_dates.py --check
python scripts/supplement_taxonomy_dates.py --check
make reproduce-taxonomy PYTHON=/path/to/figure-python
make check-taxonomy PYTHON=/path/to/figure-python
/path/to/figure-python -m pytest -q tests
make PYTHON=/path/to/figure-python
```

软件审计从上述冻结提交的独立干净 checkout 开始，初始化其论文子模块，依次执行 ruff check、ruff format --check、normalize-catalog、classify、build-data-release、pytest。已重建 1,283 条记录，并通过 `audit_catalog.py --check` 和 `audit_findings.py --check`。软件测试共 1,314 项通过；首次在受限沙箱中运行时，4 项本机 HTTP 端口测试受限，允许本机临时端口后完整测试通过。最终论文测试、构建及产物哈希见 [验证记录](library-date-validation.json)。
