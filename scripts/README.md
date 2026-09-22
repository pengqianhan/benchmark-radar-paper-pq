# Taxonomy 图制作与维护流程

本文记录以下两张图从证据数据、分类、日期补充、统计到 PDF 导出的完整流程，供后续维护与复现使用：

- [taxonomy-sankey.pdf](../figures/taxonomy-sankey.pdf)：全部来源记录的 Level 1 → Level 2 分类关系。
- [taxonomy-trends.pdf](../figures/taxonomy-trends.pdf)：分类随发布或首次介绍时间的分布，以及符合条件的类别占比变化。

**以下命令均在仓库根目录执行，不是在 `scripts/` 目录执行。**
两张图由同一套流水线生成；修改时以脚本和证据为源，不直接编辑 PDF。

## 1. 快速复现

使用 Python 3.11，首次准备环境：

```bash
python3 -m venv build/figure-venv
build/figure-venv/bin/python -m pip install -r requirements-figures.txt
```

生成两张图及全部中间产物，然后检查复现一致性：

```bash
make reproduce-taxonomy PYTHON=build/figure-venv/bin/python
make check-taxonomy PYTHON=build/figure-venv/bin/python
```

生成过程不访问网络，也不要求另有 Benchmark Radar 软件仓库。
`make reproduce-taxonomy` 即使看到已有 PDF，也会从输入重新运行全部步骤。
`make clean` 会删除 `build/`，包括上面创建的虚拟环境；清理后需重新准备环境。

## 2. 输入与数据范围

人口总体以 [catalog-findings.json](../evidence/catalog-findings.json) 为准：
v0.11.0、软件提交 `8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`、发现截止日 **2026-09-07**。
全部 **1,283 条来源记录**均保留；相同 benchmark 在不同来源中的记录分别计数，不能按名称去重。

| 输入 | 用途 |
| --- | --- |
| [catalog-findings.json](../evidence/catalog-findings.json) | 冻结的记录集合、来源、原始发布日期及其他测量字段 |
| [taxonomy-inputs/](../evidence/taxonomy-inputs/) | 随仓库保存的来源分类证据：OpenCompass Hub、LLM Stats、Artificial Analysis 的 CSV，以及 `model_cards.yml` |
| [taxonomy.py](taxonomy.py) | 分类名称、标签映射、字段权重、排除词、文本模式和类别选择规则 |
| [library-reviewed-dates.json](../evidence/library-reviewed-dates.json) | 全部 1,107 条带核验日期证据的 Library 输入快照 |
| [library-date-match-reviews.json](../evidence/library-date-match-reviews.json) | 身份消歧、跨来源映射及事件适用性审查 |
| [156_from_xiaoke_all_passed_en.json](../evidence/156_from_xiaoke_all_passed_en.json) | 历史对照、身份佐证及明确选定的 16 条核验日期 |
| [release-date-legacy-selection.json](../evidence/release-date-legacy-selection.json) | 第二阶段采用的 16 个精确来源记录 key，绑定全部输入哈希 |
| [liberation-sans/](../assets/fonts/liberation-sans/) | 固定版本的字体、来源说明、许可与校验值 |

分类用的 CSV 是此前发布的 v0.10.0 爬取文件的随仓库副本；**决定总体范围的是 v0.11.0 的冻结 census**。
不能把较早的分类证据文件误当成总体，也不能改用实时网站数据替换这些输入。
文件哈希保存在生成的分类摘要和日期补充清单中。

### 日期证据与匹配范围

当前日期来源为 [library-reviewed-dates.json](../evidence/library-reviewed-dates.json)，
从用户提供的本地 `library_index.json` 中提取全部 1,107 条带 `releaseEvidence` 的记录。
快照保留完整日期证据、身份字段、源记录位置、源文件及记录哈希。
原文件有 3,010 条，但这些记录不加入论文的 1,283 条冻结总体。
“人工核验”是提供者对日期来源的说明；本流程另行核对论文记录的身份及日期事件适用性。

[156_from_xiaoke_all_passed_en.json](../evidence/156_from_xiaoke_all_passed_en.json)
用于历史对照和具名组件身份佐证，并在第二阶段为明确选定的 16 条记录提供
`nextVerification.releaseDate`。不采用顶层 `date`，也不覆盖第一阶段已接受的日期。
本轮从 main 原始 **668 条无日期记录**开始，并非从旧补全后的 512 条开始。

## 3. 制作流程与中间产物

```text
冻结 census + 来源分类证据 + taxonomy.py
    └─ classify_benchmarks.py → benchmark-taxonomy.jsonl（原始日期）

冻结 census + Library 1107 条快照 + 身份/事件审查 + 旧结果对照
    └─ match_library_dates.py → library-date-matches.json / .csv（全部 668 条）
         └─ supplement_taxonomy_dates.py
              ├─ + 16 条明确选定且 passed 的 nextVerification.releaseDate
              ├─ release-date-matches.json / .csv（合并后全部 668 条）
              ├─ taxonomy-release-date-supplements.json（采用的日期与证据）
              └─ benchmark-taxonomy-dated.jsonl（全部 1283 条）
                   ├─ taxonomy_trends.py → 趋势 JSON + taxonomy-trend-data.tex
                   └─ plot_taxonomy.py → taxonomy-trends.pdf / taxonomy-sankey.pdf
```

可以按以下顺序单独执行；`make reproduce-taxonomy` 自动执行全部步骤：

```bash
build/figure-venv/bin/python scripts/classify_benchmarks.py
build/figure-venv/bin/python scripts/match_library_dates.py
build/figure-venv/bin/python scripts/supplement_taxonomy_dates.py
build/figure-venv/bin/python scripts/taxonomy_trends.py
build/figure-venv/bin/python scripts/plot_taxonomy.py
```

分类标签、facets、全部源记录身份和非日期测量字段保持不变。

### 身份匹配与日期适用性

1. 首先按 Library `catalogSources.catalog + sourceId` 对应冻结 `key`，得到
   619 条唯一候选、2 条多候选、47 条无此类匹配。
2. 名称规范化只检索候选，保留 `+` 和版本数字；不能单独授权补全。
   跨来源映射、多候选消歧和事件范围例外写入
   [library-date-match-reviews.json](../evidence/library-date-match-reviews.json)。
   审查绑定 census 和 Library 快照哈希，输入变化必须重新审查。
3. 采用 `releaseEvidence.date` 与其 `precision`，不用 `firstSeenAt`、
   模型日期或补成具体日期的顶层 `releasedAt`。
   `0001-01-01` 无效。月精度保持 `YYYY-MM`，跨越截止日的月份不能作为已证实的截止日前日期。
4. 底层数据集日期和结果披露日期默认不作为目标版本的发布日期。
   只有明确证明原始发布已经包含具名组件、子集或别名时，才记录例外；
   不因此合并来源记录或声称这些组件是独立 benchmark 发布。
5. 日期值不同不一定是错误：例如原始介绍、论文公开、任务数据开放可能发生在不同日期。
   `event` 与旧结果对照保存这些差异。父版本早于目标版本的日期仍被拒绝。
6. 第二阶段仅对 allowlist 中的 16 个 `verification.catalogKey` 采用旧核验文件的
   `nextVerification.releaseDate`，要求 `status` 为 `passed` 且事件、日期精度和来源齐全。
   保持第一阶段 437 个日期值不变。保留 Library 候选与决定供对照；最终结果和实际日期字段
   写入 `release-date-matches.json/.csv`。跨来源同名候选不自动加入。

审计 JSON/CSV 包含全部 668 条目标记录的候选、来源身份、日期、精度、来源 URL、
决定、理由及旧结果对照。无法采用的候选保留证据；无匹配、日期范围不适用、
身份或版本未确定的记录仍进入图中无日期列。

```text
原始 census：615 有日期 + 668 无日期 = 1,283
第一阶段：437 Library 日期 + 231 无日期 = 668
第二阶段：437 Library 日期 + 16 旧核验日期 + 215 无日期 = 668
剩余：187 事件范围不适用 + 1 身份/版本未确定 + 27 无匹配 = 215
绘图输入：1,068 有日期 + 215 无日期 = 1,283
旧结果对照：140 条使用 Library 日期、16 条使用旧核验日期，另补充 297 条
```

见 [合并匹配报告](../evidence/release-date-matching.md)。第一阶段结果保留在
[Library 匹配报告](../evidence/library-date-matching.md)。重建不访问网络。
需要重新提取用户提供的同一文件时：

```bash
python scripts/match_library_dates.py --freeze-source evidence/library_index.json
```

此命令只提取快照；新的快照若改变哈希，既有身份/事件审查会失败，不能自动沿用。

### 趋势统计与绘图

**Sankey 图**使用全部 1,283 条记录的主分类。
每条记录贡献一个单位的流带高度，左右两列的总量一致。
日期是否缺失不影响这张图的分类计数；facets 不作为 Sankey 的分类列。

**Trends 图 Panel A**从完整总体出发，展示近期日期与未知日期：

- 从 2023 H1 开始按半年分桶，最后一个桶只到发现截止日。
- 不绘制原来的 2010–2022 汇总列：该时期的收集不完整，图中聚焦近期趋势。
- 132 条早期记录仍保留在完整 census、日期输入和统计审计中，不从数据集中删除。
- 无日期记录放在右侧独立刻度的一列，仍按主分类堆叠。
- 图例只计入实际展示的记录：936 条 2023 年起的有日期记录 + 215 条无日期记录 = 1,151 条。
- `benchmark-taxonomy-trends.json` 的 `panel_a` 保存展示范围、排除数量及各类图例计数。

**Panel B**只对满足条件的时间段计算和展示占比。当前规则在 `taxonomy_trends.py` 中：

| 参数 | 当前值 | 含义 |
| --- | --- | --- |
| `TREND_PERIOD` | `"half"` | 默认半年；同时控制统计与绘图 |
| `WINDOW_START_YEAR` | `2023` | Panel A 分时段轴的起点；更早记录保留在数据中但不绘制 |
| `MIN_RELIABLE` | `30` | 一个时间段至少有 30 条有日期记录 |
| `MAX_MIX_DEVIATION` | `0.25` | 该时段与全部有日期记录的来源构成，总变差距离不超过 0.25 |
| `SHARE_SERIES_MIN_RECORDS` | `20` | 候选类别／facet 在合格时段至少包含 20 条记录 |
| `SHARE_SERIES_DRAWN` | `6` | 最多绘制 6 条曲线 |
| `SHARE_SERIES_MAX_CONTAINMENT` | `0.8` | 与已选曲线的交集占两者较小集合超过 80% 时跳过 |

曲线按合格时段前半与后半的**合并计数占比之差的绝对值**排序，时段数量为奇数时不把中间时段计入这两个比较组。
这不是首尾两个点直接相减。每个候选项的统计、选择结果及原因都写入趋势 JSON。
Facets 与主类别可以重叠，因此 Panel B 的曲线占比不要求相加为 100%。
当前合格时段是 2023 H2–2025 H2；该范围由代码计算，不能在图中手动固定。
移除 Panel A 早期汇总列不会改变 Panel B 的输入、分母、来源构成基准或曲线选择。

## 4. 视觉样式与字体

样式集中在 [plot_taxonomy.py](plot_taxonomy.py)：

- `L1_COLOR`、`FACET_COLOR` 控制颜色；两张图的主类别颜色一致。
- `FS_L1`、`FS_L2`、`FS_HEAD`、`FS_TICK`、`FS_AXIS`、`FS_PANEL` 等控制字号。
- 标题、类别名和数值标签使用常规字重，与论文 Helvetica 风格相协调。
- 使用仓库内 Liberation Sans 2.1.5 Regular／Italic，并将字体嵌入矢量 PDF。
- `fit_label_width()` 为 Sankey 的长标签预留空间；修改字体或字号后仍需目视检查。
- PDF 创建时间固定到发现截止日，仅用于消除构建时间差异，不代表本次作图或日期核验时间。

不要依赖本机 Helvetica／Arial 的自动回退，否则不同机器可能画出不同的字体和布局。
字体来源、许可证和 SHA-256 见 [字体说明](../assets/fonts/liberation-sans/README.md)。

修改时间粒度时，正式版本应修改 `taxonomy_trends.py` 中的 `TREND_PERIOD` 后完整重建。
`plot_taxonomy.py --period quarter` 等命令只临时覆盖 Panel A，并会覆盖现有 PDF；探索结束后运行 `make reproduce-taxonomy` 恢复正式配置。

## 5. 检查与论文更新

检查中间数据是否与当前输入一致，不重写文件：

```bash
build/figure-venv/bin/python scripts/classify_benchmarks.py --check
build/figure-venv/bin/python scripts/match_library_dates.py --check
build/figure-venv/bin/python scripts/supplement_taxonomy_dates.py --check
build/figure-venv/bin/python scripts/taxonomy_trends.py --check
```

完整复现检查由 [check_taxonomy_reproduction.py](check_taxonomy_reproduction.py) 执行：

```bash
make check-taxonomy PYTHON=build/figure-venv/bin/python
```

它在两个临时目录中从原始输入分别构建，改变哈希种子、时区和调用者时间戳，要求 **13 个生成产物逐字节一致**。
其中 JSON、JSONL、CSV、TeX 还必须与当前工作区文件一致。
结果写入 `build/taxonomy-reproduction-check.json`，包含包版本、字体哈希、产物哈希及 `working_tree_pdf_matches`。
后者应单独查看：它记录当前 PDF 是否与本次构建相同；不同平台／依赖版本的 PDF 字节可能不同，该字段为 `false` 本身不会使检查失败。

修改后运行已有回归测试：

```bash
build/figure-venv/bin/python -m pip install pytest
build/figure-venv/bin/python -m pytest -q tests
```

更新论文中的图，需要另外安装 TeX、`latexmk`、Poppler 和 Tesseract，然后运行：

```bash
make PYTHON=build/figure-venv/bin/python
```

该命令重建 `main.pdf`，并按仓库规定执行 PDF 文本与 OCR 的小于 100 数值告警检查。
检查报告在 `build/small-number-warnings.json`；不要为了消除告警修改证据。
目视检查两张独立 PDF 及论文中的对应页面，确认长标签不裁切、图例不重叠、字体一致、图注与统计一致。

## 6. 后续维护与归档

| 想修改的内容 | 应修改的位置 |
| --- | --- |
| 分类定义、标签映射或证据权重 | `taxonomy.py`，必要时调整 `classify_benchmarks.py` |
| 已核验的补充日期及其依据 | 通过核验的日期输入；若更换文件名，同时更新脚本常量、复现检查、Makefile、测试及文档中的引用 |
| 时间粒度、占比条件、曲线选择规则 | `taxonomy_trends.py` |
| 字体、字号、颜色、图例和布局 | `plot_taxonomy.py` 及随仓库保存的字体 |
| 论文图注和解释 | `main.tex`；数量宏由脚本生成，不手改生成的 TeX |

通常顺序是：修改源文件 → 完整重建 → 检查复现和测试 → `make` → 目视检查 → 提交相关源码、证据、生成的 JSON／TeX、两张图及更新后的 `main.pdf`。
`build/` 是临时目录，不能作为唯一的长期证据来源；需长期保存的输入和字体应随仓库提交。

改变总体、冻结来源或发现截止日时，遵循 [AGENTS.md](../AGENTS.md) 和 [根目录 README](../README.md) 的软件审计与版本规则。
普通作图维护不直接更新软件仓库、其论文子模块指针或 `main` 分支。

### 已记录的实现节点

| 提交 | 制作流程变化 |
| --- | --- |
| `41b7164` | 将 156 条已核验日期作为独立补充层；建立完整绘图数据、自动重建和两次独立复现检查 |
| `fa7fb10` | 恢复常规字重的 Helvetica 风格；随仓库保存 Liberation Sans 字体及许可证 |

后续改变数据口径、统计规则或视觉配置时，可在此补充相应提交及原因。
