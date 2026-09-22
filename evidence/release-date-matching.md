# 原始 668 条缺日期记录的合并统计（2026-09-23）

本轮按用户确认，将原来采用的 437 条 Library 日期与旧核验文件中精确匹配的 16 条日期合并。按来源记录 key 去重，两个补全集合没有重叠；原有 437 个日期值保持不变。

| 原始 668 条的处理结果 | 数量 | 占原始缺日期记录 |
| --- | ---: | ---: |
| Library 日期 | 437 | 65.4% |
| 本轮新增的旧核验日期 | 16 | 2.4% |
| 合计已补全 | **453** | **67.8%** |
| 仍无日期 | **215** | **32.2%** |

完整冻结总体为 **615 条原有日期 + 453 条补充日期 + 215 条无日期 = 1,283 条**。绘图数据中 **1,068 条有日期**。453 条补充日期中，437 条为日精度，16 条为月精度。

## 各来源统计

| 来源 | 原始缺日期 | Library 补全 | 本轮新增 | 合计补全 | 仍缺日期 |
| --- | ---: | ---: | ---: | ---: | ---: |
| LLM Stats | 645 | 423 | 14 | 437 | 208 |
| Artificial Analysis | 8 | 6 | 1 | 7 | 1 |
| Model reports | 11 | 8 | 1 | 9 | 2 |
| OpenCompass Hub | 4 | 0 | 0 | 0 | 4 |
| 合计 | 668 | 437 | 16 | 453 | 215 |

剩余 215 条中：187 条候选日期仍未建立目标记录的发布／介绍事件，1 条身份未确定（LLM Stats 的 AIR-Bench），27 条未匹配到日期证据。Artificial Analysis 的 τ³-Banking 仍保留未知；未自动迁移同名 LLM Stats 记录的日期。

## 新增 16 条的日期字段

匹配字段统一为 `verification.catalogKey`；日期字段统一为 `nextVerification.releaseDate`，要求 `nextVerification.status == "passed"`，保留对应的 `precision`、`event`、`reason` 和 `sources`。不读取顶层 `date`，不将月精度扩展到某一天。

| 来源记录 key | 本轮日期 | 事件 |
| --- | --- | --- |
| `llm-stats:frontier-bench-v0.1` | 2026-07-23 | `version_release` |
| `llm-stats:global-mmlu-lite` | 2024-12 | `dataset_v1_release` |
| `llm-stats:groundui-1k` | 2024-10-02 | `named_subset_introduction_in_v2` |
| `llm-stats:mathverse-mini` | 2024-03-22 | `testmini_dataset_release` |
| `llm-stats:mega-mlqa` | 2023-03-22 | `mega_task_protocol_introduction` |
| `llm-stats:mega-tydi-qa` | 2023-03-22 | `mega_task_protocol_introduction` |
| `llm-stats:mega-udpos` | 2023-05-19 | `mega_task_added_in_v3` |
| `llm-stats:mega-xcopa` | 2023-03-22 | `mega_task_protocol_introduction` |
| `llm-stats:mega-xstorycloze` | 2023-05-19 | `mega_task_added_in_v3` |
| `llm-stats:surds` | 2025-05-27 | `surds_version_introduction_in_v3` |
| `llm-stats:swe-atlas` | 2026-03-04 | `suite_initial_launch` |
| `llm-stats:t2-bench` | 2025-06-09 | `benchmark_introduction` |
| `llm-stats:usamo-2026` | 2026-03-28 | `matharena_usamo_2026_adaptation_introduction` |
| `llm-stats:usamo25` | 2025-03-27 | `usamo_2025_llm_evaluation_introduction` |
| `artificial-analysis:apex-agents-aa` | 2026-04-08 | `aa_implementation_launch` |
| `model-reports:harbor_index` | 2026-07-07 | `harbor_index_1_0_launch` |

这些日期描述各条核验记录注明的初次发布、论文版本介绍、评测适配或别名介绍事件，不承诺所有后续模型分数使用同一协议。例如 Harbor-Index 保留 1.0 初次发布事件；Global-MMLU-Lite 只确认到 2024-12。

## 证据与复现

- [最终 668 条 CSV](release-date-matches.csv) / [JSON](release-date-matches.json)：包含最终日期、实际取值字段、日期来源、Library 阶段决定及候选日期。
- [明确采用的 16 条 key](release-date-legacy-selection.json)：绑定旧核验文件、Library 匹配审计和冻结 census 的 SHA-256。
- [旧核验原文件](156_from_xiaoke_all_passed_en.json)：保持原样，原始核验说明及来源 URL 均保留。
- [Library 阶段审计](library-date-matches.json)：仍为 437 条采用，不把旧核验日期误标为 Library 日期。
- [绘图日期清单](taxonomy-release-date-supplements.json)：记录全部 453 条补充日期与证据；完整绘图输入仍含全部 1,283 条来源记录。
- [Library 第一阶段报告](library-date-matching.md) 和 [第一阶段验证记录](library-date-validation.json) 描述提交 `4fdcaa9` 时的历史结果；本轮最终结果以本报告为准。
- [本轮验证记录](release-date-validation.json) 保存当前产物哈希、测试、构建及 PDF 检查结果。

软件提交仍为 `8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`，发现截止日仍为 2026-09-07。沿用已通过六步干净 checkout 审计的相同软件输入，并再次执行 `audit_catalog.py --check` 和 `audit_findings.py --check`；本轮不修改冻结人口、原始日期、分数或分类。

```bash
python scripts/match_library_dates.py --check
python scripts/supplement_taxonomy_dates.py --check
make reproduce-taxonomy PYTHON=/path/to/figure-python
make check-taxonomy PYTHON=/path/to/figure-python
/path/to/figure-python -m pytest -q tests
make PYTHON=/path/to/figure-python
```

## Figure 6

Panel A 无日期列为 215，全部记录仍计入各分类。Panel B 按原有数量和来源构成阈值重新计算：合格时段为 2023 H2–2025 H2，314 条有日期记录位于这些时段之外，仍保留在 Panel A。来源重加权的 agentic 占比敏感性为 6.6 个百分点。图例中的趋势与终点数值均从更新数据计算，没有手动恢复旧曲线。
