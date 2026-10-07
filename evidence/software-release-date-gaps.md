# 论文补充日期与最新软件数据的差异

对照软件提交 `375c41c5da28bd112115c75efd9a59a03ef3b537`（2026-10-07），从干净 checkout 依次运行 `benchmark-radar normalize-catalog`、`benchmark-radar classify`、`benchmark-radar build-data-release` 后得到 3,217 条记录。逐条比较 Figure 6 的 1,283 条冻结来源记录的发布日期：

| 比较结果 | 数量 |
| --- | ---: |
| 日期相同 | 615 |
| 两边均无日期 | 215 |
| **论文有日期、软件无日期** | **453** |
| 两边日期不同 | 0 |
| 软件有日期、论文无日期 | 0 |

两边都有日期时全部一致，软件数据仍是其已有日期的依据。本文件记录其余 453 条：它们的日期只来自论文仓库已审核的补充层，软件仓库的来源爬取、`data/catalog/benchmark_dates.yml` 与 `data/model_cards.yml` 都没有这些日期。

## 日期如何得到

| 来源 | 数量 | 输入与字段 | 方法 |
| --- | ---: | --- | --- |
| Library | 437 | `library-reviewed-dates.json` 的 `releaseEvidence.date` | `match_library_dates.py` 按 catalog/sourceId 精确匹配，或依 `library-date-match-reviews.json` 的身份审查匹配；只采用正式介绍或发布事件 |
| 旧核验 | 16 | `156_from_xiaoke_all_passed_en.json` 的 `nextVerification.releaseDate` | `supplement_taxonomy_dates.py` 仅采用 `release-date-legacy-selection.json` 中精确 key 且状态为 passed 的记录 |

## 统计

| 来源记录 | 数量 |
| --- | ---: |
| artificial_analysis | 7 |
| llm_stats | 437 |
| model_reports | 9 |

| 日期精度 | 数量 |
| --- | ---: |
| day | 437 |
| month | 16 |

| Figure 6 时段 | 数量 |
| --- | ---: |
| 2023 H1 | 26 |
| 2023 H2 | 21 |
| 2024 H1 | 46 |
| 2024 H2 | 55 |
| 2025 H1 | 77 |
| 2025 H2 | 59 |
| 2026 H1 | 98 |
| 2026 H2 | 16 |
| before 2023 (not drawn) | 55 |

其中 9 条在软件中有 `first_score_reported_at`；那是模型成绩的报告日期，不是 benchmark 发布日期。

## 文件

- [software-release-date-gaps.json](software-release-date-gaps.json)：完整记录、证据、软件端字段与输入哈希。
- [software-release-date-gaps.csv](software-release-date-gaps.csv)：便于审核的逐条表格。

重新生成或检查（软件 checkout 须先完成上述构建）：

```bash
python scripts/audit_software_release_dates.py /path/to/benchmark-radar
python scripts/audit_software_release_dates.py /path/to/benchmark-radar --check
```
