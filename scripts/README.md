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
| [156_from_xiaoke_all_passed_en.json](../evidence/156_from_xiaoke_all_passed_en.json) | 对原来缺日期的记录完成核验后的日期证据 |
| [liberation-sans/](../assets/fonts/liberation-sans/) | 固定版本的字体、来源说明、许可与校验值 |

分类用的 CSV 是此前发布的 v0.10.0 爬取文件的随仓库副本；**决定总体范围的是 v0.11.0 的冻结 census**。
不能把较早的分类证据文件误当成总体，也不能改用实时网站数据替换这些输入。
文件哈希保存在生成的分类摘要和日期补充清单中。

### 日期证据的形成

历史记录从 [reviewed_from_xiaoke.json](../evidence/reviewed_from_xiaoke.json)
筛选为 [284_from_xiaoke.json](../evidence/284_from_xiaoke.json)，经日期核验后分为：

- [156_from_xiaoke_all_passed_en.json](../evidence/156_from_xiaoke_all_passed_en.json)：已通过核验，进入补充流程。
- [128_from_xiaoke_failed_next_fail.json](../evidence/128_from_xiaoke_failed_next_fail.json)：未通过核验，不用于补日期。

这些核验结果是已保存的审查输入。绘图代码复现日期提取、合并、统计和绘制，**不会重新搜索网络或重新判定证据是否可信**。
需要修订某个日期时，应先完成对该 benchmark／版本的证据核验，再更新通过核验的输入。

## 3. 制作流程与中间产物

```text
冻结 census + 来源分类证据 + taxonomy.py
    │
    └─ classify_benchmarks.py
         └─ benchmark-taxonomy.jsonl（原始日期保持不变）
              │
              ├─ 156_from_xiaoke_all_passed_en.json
              │
              └─ supplement_taxonomy_dates.py
                   ├─ taxonomy-release-date-supplements.json（证据与哈希）
                   └─ benchmark-taxonomy-dated.jsonl（完整绘图数据）
                        │
                        ├─ taxonomy_trends.py
                        │    ├─ benchmark-taxonomy-trends.json
                        │    └─ taxonomy-trend-data.tex
                        │
                        └─ plot_taxonomy.py（同时读取趋势统计）
                             ├─ taxonomy-sankey.pdf
                             └─ taxonomy-trends.pdf
```

| 顺序 | 脚本 | 输出 |
| --- | --- | --- |
| 1 | [classify_benchmarks.py](classify_benchmarks.py) | `evidence/benchmark-taxonomy.jsonl`、`evidence/benchmark-taxonomy-summary.json`、`taxonomy-data.tex` |
| 2 | [supplement_taxonomy_dates.py](supplement_taxonomy_dates.py) | `evidence/benchmark-taxonomy-dated.jsonl`、`evidence/taxonomy-release-date-supplements.json` |
| 3 | [taxonomy_trends.py](taxonomy_trends.py) | `evidence/benchmark-taxonomy-trends.json`、`taxonomy-trend-data.tex` |
| 4 | [plot_taxonomy.py](plot_taxonomy.py) | `figures/taxonomy-sankey.pdf`、`figures/taxonomy-trends.pdf` |

需要定位某一步的问题时，可以按顺序分别执行：

```bash
build/figure-venv/bin/python scripts/classify_benchmarks.py
build/figure-venv/bin/python scripts/supplement_taxonomy_dates.py
build/figure-venv/bin/python scripts/taxonomy_trends.py
build/figure-venv/bin/python scripts/plot_taxonomy.py
```

### 第一步：分类

分类器根据来源字段及文本证据，结合 `taxonomy.py` 的规则，为每条记录选择一个主类别 `l1` 和一个子类别 `l2`。
`interaction`、`modality`、`operational` 是独立的属性（facets），可以重叠。
`evidence`、`label_basis`、`needs_review` 等字段保留分类依据和待复核原因。
证据不足的记录保留为 `other`，不会从总体删除。

### 第二步：补充日期

按以下规则提取有效日期：

```python
verification = record.get("nextVerification") or record["verification"]
assert verification["status"] == "passed"
release_date = verification.get("releaseDate") or verification.get("verifiedDate")
precision = verification["precision"]
catalog_key = record["verification"]["catalogKey"]
```

注意以下约束：

- 顶层 `date` 可能是修正前的历史值，不能直接作为最终日期。
- 使用 `catalogKey` 匹配分类记录的 `key`，不能按名称或历史 `id` 合并。
- 只填补原来为 `null` 的日期，不覆盖冻结 census 已有日期。
- 月精度保持 `YYYY-MM`，日精度保持 `YYYY-MM-DD`，不人为补出具体日期。
- 重复键、找不到的键、覆盖已有日期、未通过核验、非法日期或超出截止日的日期会报错。
- 保留事件类型、来源 URL、核验说明、核验日期、输入位置和文件哈希；首次介绍、论文公开、特定版本发布不一律等于数据集可下载日期。

当前证据对应的数量关系为：

```text
原始 census：615 有日期 + 668 无日期 = 1,283
补充日期：156（143 条日精度 + 13 条月精度）
绘图输入：771 有日期 + 512 无日期 = 1,283
```

这是对截止日前已有记录的事后证据补充，不扩大发现截止日。
原始 `catalog-findings.json` 和 `benchmark-taxonomy.jsonl` 的日期保持不变。

### 第三、四步：两张图如何生成

**Sankey 图**使用全部 1,283 条记录的主分类。
每条记录贡献一个单位的流带高度，左右两列的总量一致。
日期是否缺失不影响这张图的分类计数；facets 不作为 Sankey 的分类列。

**Trends 图 Panel A**也保留全部记录：

- 从 2023 H1 开始按半年分桶，最后一个桶只到发现截止日。
- 2023 年之前的有日期记录合并在左侧一列。
- 无日期记录放在右侧独立刻度的一列，仍按主分类堆叠。
- 图例计数包含有日期和无日期记录。

**Panel B**只对满足条件的时间段计算和展示占比。当前规则在 `taxonomy_trends.py` 中：

| 参数 | 当前值 | 含义 |
| --- | --- | --- |
| `TREND_PERIOD` | `"half"` | 默认半年；同时控制统计与绘图 |
| `WINDOW_START_YEAR` | `2023` | Panel A 分时段轴的起点；更早记录仍保留 |
| `MIN_RELIABLE` | `30` | 一个时间段至少有 30 条有日期记录 |
| `MAX_MIX_DEVIATION` | `0.25` | 该时段与全部有日期记录的来源构成，总变差距离不超过 0.25 |
| `SHARE_SERIES_MIN_RECORDS` | `20` | 候选类别／facet 在合格时段至少包含 20 条记录 |
| `SHARE_SERIES_DRAWN` | `6` | 最多绘制 6 条曲线 |
| `SHARE_SERIES_MAX_CONTAINMENT` | `0.8` | 与已选曲线的交集占两者较小集合超过 80% 时跳过 |

曲线按合格时段前半与后半的**合并计数占比之差的绝对值**排序，时段数量为奇数时不把中间时段计入这两个比较组。
这不是首尾两个点直接相减。每个候选项的统计、选择结果及原因都写入趋势 JSON。
Facets 与主类别可以重叠，因此 Panel B 的曲线占比不要求相加为 100%。
当前合格时段是 2023 H2–2025 H1；该范围由代码计算，不能在图中手动固定。

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
build/figure-venv/bin/python scripts/supplement_taxonomy_dates.py --check
build/figure-venv/bin/python scripts/taxonomy_trends.py --check
```

完整复现检查由 [check_taxonomy_reproduction.py](check_taxonomy_reproduction.py) 执行：

```bash
make check-taxonomy PYTHON=build/figure-venv/bin/python
```

它在两个临时目录中从原始输入分别构建，改变哈希种子、时区和调用者时间戳，要求 **9 个生成产物逐字节一致**。
其中 JSON、JSONL、TeX 还必须与当前工作区文件一致。
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
