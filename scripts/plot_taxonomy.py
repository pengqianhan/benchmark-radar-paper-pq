#!/usr/bin/env python3
r"""Draw the taxonomy figures from the classified census.

Two figures, both from `evidence/benchmark-taxonomy-dated.jsonl`:

  taxonomy-sankey    Level 1 -> Level 2 for all 1,283 source records. Every
                     record is one unit of ribbon height, so both columns are
                     equal in total and a reader can check coverage by eye.
                     Source composition is stated in the caption.
  taxonomy-trends    Panel A buckets the census by release period from
                     2023-01-01, the first full period after ChatGPT's release,
                     so the expansion this corpus is about is read in steps
                     rather than compressed into three annual bars. The step is
                     `PANEL_A_PERIOD`: quarter, half or year. Panel B keeps the
                     release-year shares the evidence supports.

Nothing is imputed and no record is dropped: the dated records released before
the window and those that still carry no release date at all cannot take a
half-year bucket, so each group keeps a column of its own on Panel A with its
count printed there.

Both are written as vector PDFs, which is what \includegraphics takes. The Sankey
reserves space for its rendered labels before export, so font metrics cannot
clip long class names at the page edge.

Usage:
    python3 scripts/plot_taxonomy.py                    # write figures/taxonomy-sankey.pdf and -trends.pdf
    python3 scripts/plot_taxonomy.py --period quarter   # same, with Panel A bucketed by quarter
"""

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
from matplotlib.patches import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from taxonomy import L1 as L1_LABEL  # noqa: E402
from supplement_taxonomy_dates import ROWS, sha256, check as check_dates  # noqa: E402
# The period model lives with the analysis that computes the shares, so both
# panels run on one clock and a switch cannot desynchronise them.
from taxonomy_trends import (  # noqa: E402
    PERIODS, TREND_PERIOD, WINDOW_START_YEAR, period_key,
)

PAPER = Path(__file__).resolve().parents[1]

# matplotlib stamps /CreationDate into every PDF, so two builds of the same data
# differ by a timestamp and cannot be checked against each other. Pinning it to
# the corpus's own discovery cutoff makes the figures byte-reproducible and
# dates them by the data rather than by the build. tests/test_taxonomy.py holds
# this equal to catalog-findings.json's discovery_cutoff, so it cannot drift.
DISCOVERY_CUTOFF = "2026-09-07"

# The manuscript is single-column article 11pt on letterpaper with 0.9in
# margins, so \textwidth is 484.2pt. Authoring at exactly that width means
# \includegraphics[width=\textwidth] scales by 1.0 and a label set in 7pt here
# prints as 7pt. Drawn wider, the same figure is scaled down and its labels fall
# below the ~6pt that stays legible in print.
FIG_WIDTH_IN = 484.20988 / 72
# Titles and provenance notes live in the LaTeX caption, not inside the figure,
# so nothing is said twice and the drawing keeps the height.
FS_L1, FS_L2, FS_HEAD = 8.5, 6.2, 9.0
FS_TICK, FS_AXIS, FS_PANEL, FS_LEGEND = 7.0, 8.0, 8.5, 7.0

TRENDS = PAPER / "evidence" / "benchmark-taxonomy-trends.json"
FIGURES = PAPER / "figures"

SOURCE_LABEL = {
    "llm_stats": "LLM Stats",
    "opencompass_hub": "OpenCompass Hub",
    "model_reports": "Model reports",
    "artificial_analysis": "Artificial Analysis",
}

# One hue per L1, kept consistent across both figures.
L1_COLOR = {
    "multimodal_perception": "#4C72B0",
    "coding_se": "#DD8452",
    "language_communication": "#55A868",
    "math_logic": "#C44E52",
    "agentic_tool_use": "#8172B3",
    "applied_verticals": "#937860",
    "knowledge_factuality": "#DA8BC3",
    "science_research": "#64B5CD",
    "safety_security": "#CCB974",
    "general_composite": "#8C8C8C",
    "other": "#BFBFBF",
}

L2_LABEL = {
    "image_understanding_vqa": "Image understanding / VQA",
    "video_understanding": "Video understanding",
    "audio_speech": "Audio & speech",
    "ocr_document": "OCR & document",
    "chart_diagram": "Chart & diagram",
    "visual_generation_editing": "Visual generation & editing",
    "spatial_3d": "Spatial & 3D",
    "embodied_perception": "Embodied perception",
    "cross_modal_reasoning": "Cross-modal reasoning",
    "multimodal_general": "Multimodal (general)",
    "code_generation": "Code generation",
    "swe_repo_issue": "Repo & issue resolution",
    "competitive_programming": "Competitive programming",
    "code_reasoning_execution": "Code reasoning & execution",
    "frontend_ui": "Frontend & UI",
    "data_sql": "Data & SQL",
    "code_security": "Code security",
    "hardware_eda": "Hardware & EDA",
    "code_general": "Code (general)",
    "reading_comprehension": "Reading comprehension",
    "multilingual_translation": "Multilingual & translation",
    "instruction_following": "Instruction following",
    "creative_writing": "Creative writing",
    "summarization": "Summarization",
    "dialogue_roleplay": "Dialogue & roleplay",
    "human_preference_chat": "Human preference / chat",
    "long_context_text": "Long context (text)",
    "language_general": "Language (general)",
    "competition_math": "Competition math",
    "math_word_problems": "Math word problems",
    "formal_theorem_proving": "Formal theorem proving",
    "logical_puzzle_reasoning": "Logic & puzzles",
    "abstract_reasoning": "Abstract reasoning",
    "math_general": "Math (general)",
    "tool_function_calling": "Tool & function calling",
    "computer_gui_use": "Computer & GUI use",
    "web_browsing_deep_research": "Browsing & deep research",
    "os_terminal": "OS & terminal",
    "workflow_task_execution": "Workflow & task execution",
    "multi_agent_collaboration": "Multi-agent collaboration",
    "embodied_agent": "Embodied agent",
    "agent_general": "Agent (general)",
    "healthcare_medical": "Healthcare & medical",
    "legal": "Legal",
    "finance_economics": "Finance & economics",
    "business_productivity": "Business & productivity",
    "education": "Education",
    "vertical_general": "Vertical (general)",
    "world_knowledge_qa": "World knowledge QA",
    "exam_academic": "Academic exams",
    "factuality_hallucination": "Factuality & hallucination",
    "commonsense": "Commonsense",
    "knowledge_general": "Knowledge (general)",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology_life_science": "Biology & life science",
    "general_science_qa": "General science QA",
    "research_engineering_ml": "Research & ML engineering",
    "scientific_reasoning": "Scientific reasoning",
    "science_general": "Science (general)",
    "harmfulness_alignment": "Harmfulness & alignment",
    "jailbreak_robustness": "Jailbreak & robustness",
    "cybersecurity_offensive": "Cybersecurity",
    "privacy": "Privacy",
    "bias_fairness": "Bias & fairness",
    "safety_general": "Safety (general)",
    "aggregate_index": "Aggregate index",
    "general_capability": "General capability",
    "arena_elo": "Arena / Elo",
    "robustness_consistency": "Robustness & consistency",
    "unclassified": "Unclassified",
}

SOURCE_COLOR = {
    "opencompass_hub": "#1B5E20",
    "model_reports": "#E65100",
    "llm_stats": "#0D47A1",
    "artificial_analysis": "#4A148C",
}

# Every tracked facet needs a label and a hue, because Panel B's series are
# chosen by a rule rather than named here: any of them can reach the chart.
FACET_LABEL = {
    "interaction:agentic": "agentic (facet)",
    "modality:multimodal": "multimodal (facet)",
    "modality:image": "image (facet)",
    "modality:video": "video (facet)",
    "modality:audio": "audio (facet)",
    "modality:embodied": "embodied (facet)",
    "modality:gui": "GUI (facet)",
    "operational:reasoning": "reasoning (facet)",
    "operational:tool_calling": "tool calling (facet)",
    "operational:long_context": "long context (facet)",
    "operational:retrieval_rag": "retrieval & RAG (facet)",
    "operational:safety_probe": "safety probe (facet)",
    "operational:spatial": "spatial (facet)",
    "operational:multilingual": "multilingual (facet)",
    "operational:examination": "examination (facet)",
    "operational:instruction_following": "instruction following (facet)",
}

FACET_COLOR = {
    "interaction:agentic": "#8172B3",
    "modality:multimodal": "#00838F",
    "modality:image": "#1565C0",
    "modality:video": "#6A1B9A",
    "modality:audio": "#AD1457",
    "modality:embodied": "#2E7D32",
    "modality:gui": "#EF6C00",
    "operational:reasoning": "#5D4037",
    "operational:tool_calling": "#C2185B",
    "operational:long_context": "#00695C",
    "operational:retrieval_rag": "#827717",
    "operational:safety_probe": "#B71C1C",
    "operational:spatial": "#455A64",
    "operational:multilingual": "#0277BD",
    "operational:examination": "#7B1FA2",
    "operational:instruction_following": "#4527A0",
}


def display_order(rows):
    """Stacking order for both figures: largest class first, `other` last.

    Derived from the census rather than hard-coded, so the two figures cannot
    disagree with each other or drift as the classification changes. This is a
    presentation order; `taxonomy.L1_PRIORITY` is the tie-break rule and means
    something different.
    """
    counts = Counter(row["l1"] for row in rows)
    return sorted(counts, key=lambda l1: (l1 == "other", -counts[l1], l1))


def load_rows():
    return [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]


# --- Sankey -------------------------------------------------------------


def spread_labels(mids, gap):
    """Label positions: as close to their nodes as a minimum spacing allows.

    Pushing labels apart in one direction only can never compress a gap that is
    already wide, so the block grows past the drawing and the end labels fall
    off. This instead solves the least-squares problem directly: minimise the
    total squared displacement from each node subject to
    ``y[i+1] - y[i] >= gap``. Substituting ``v[i] = y[i] - i*gap`` turns that
    into isotonic regression on ``v``, which pool-adjacent-violators solves
    exactly. The result is bounded by the span of the nodes themselves, so a
    label can never be pushed outside the figure.
    """
    shifted = [m - index * gap for index, m in enumerate(mids)]
    values, weights = [], []
    for value in shifted:
        values.append(value)
        weights.append(1)
        while len(values) > 1 and values[-2] > values[-1]:
            v2, w2 = values.pop(), weights.pop()
            v1, w1 = values.pop(), weights.pop()
            values.append((v1 * w1 + v2 * w2) / (w1 + w2))
            weights.append(w1 + w2)
    flat = [value for value, weight in zip(values, weights) for _ in range(weight)]
    return [value + index * gap for index, value in enumerate(flat)]


def stack(items, gap):
    """Lay out (key, size) pairs bottom-up, returning {key: (y0, y1)}."""
    spans, cursor = {}, 0.0
    for key, size in items:
        spans[key] = (cursor, cursor + size)
        cursor += size + gap
    return spans, cursor - gap if items else 0.0


def ribbon(ax, x0, x1, y0a, y0b, y1a, y1b, color, alpha):
    """A flow from [y0a, y0b] at x0 to [y1a, y1b] at x1, with Bezier edges."""
    curve = (x1 - x0) * 0.42
    verts = [
        (x0, y0a),
        (x0 + curve, y0a), (x1 - curve, y1a), (x1, y1a),
        (x1, y1b),
        (x1 - curve, y1b), (x0 + curve, y0b), (x0, y0b),
        (x0, y0a),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none",
                           alpha=alpha, zorder=1))


def draw_sankey(rows, path_stem, order):
    """Level 1 -> Level 2 for every record in the census.

    Source provenance is reported in the caption rather than as a third column:
    a source-to-L1 column is a near-complete 4x11 bipartite graph whose crossings
    sit on top of the L1 -> L2 flows this figure exists to show.
    """
    total = len(rows)
    l1_l2 = defaultdict(Counter)
    for row in rows:
        l1_l2[row["l1"]][row["l2"]] += 1

    source_totals = Counter(row["source"] for row in rows)
    l1_totals = Counter(row["l1"] for row in rows)
    l2_totals = Counter((row["l1"], row["l2"]) for row in rows)

    sources = [s for s, _ in source_totals.most_common()]
    l1s = [k for k in order if l1_totals[k]]
    l2s = [
        (l1, l2)
        for l1 in l1s
        for l2, _ in sorted(l1_l2[l1].items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    # Column gaps are set so both columns end at the same height.
    gap_l1 = total * 0.014
    gap_l2 = total * 0.0042
    span_l1, h_l1 = stack([(k, l1_totals[k]) for k in l1s], gap_l1)
    span_l2, h_l2 = stack([(k, l2_totals[k]) for k in l2s], gap_l2)
    height = max(h_l1, h_l2)
    for spans, own in ((span_l1, h_l1), (span_l2, h_l2)):
        shift = (height - own) / 2
        for key, (a, b) in spans.items():
            spans[key] = (a + shift, b + shift)

    # The top of the stack holds many one-record sub-domains, so their labels
    # must spread past the nodes however tall the canvas is. Rather than force
    # them back and clip the ends, solve the labels first and let the axis cover
    # whatever range they need. A short fixed-point pass settles the two, because
    # widening the view makes one label worth slightly more data units.
    label_pitch_in = FS_L2 * 1.30 / 72
    mids = [sum(span_l2[k]) / 2 for k in l2s]
    fig_w, fig_h = FIG_WIDTH_IN, 8.6
    view_lo, view_hi = -height * 0.012, height * 1.05
    for _ in range(8):
        gap = label_pitch_in * (view_hi - view_lo) / (fig_h * 0.99)
        label_y = spread_labels(mids, gap)
        view_lo = min(-height * 0.012, label_y[0] - gap)
        view_hi = max(height * 1.05, label_y[-1] + gap * 2.6)
    assert all(b - a >= gap - 1e-6 for a, b in zip(label_y, label_y[1:]))
    assert view_lo <= label_y[0] and label_y[-1] <= view_hi

    x_l1, x_l2 = 0.30, 0.72
    node_w = 0.022
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)

    out_cursor = {k: span_l1[k][0] for k in l1s}
    for l1, l2 in l2s:
        n = l2_totals[(l1, l2)]
        y0 = out_cursor[l1]
        y1a, y1b = span_l2[(l1, l2)]
        ribbon(ax, x_l1 + node_w, x_l2, y0, y0 + n, y1a, y1b, L1_COLOR[l1], 0.44)
        out_cursor[l1] += n

    def node(x, y0, y1, color, label, side, size, weight="normal", label_y=None):
        ax.add_patch(Rectangle((x, y0), node_w, y1 - y0, facecolor=color,
                               edgecolor="white", linewidth=0.4, zorder=3))
        mid = (y0 + y1) / 2
        at = mid if label_y is None else label_y
        if side == "left":
            ax.text(x - 0.012, at, label, ha="right", va="center",
                    fontsize=size, fontweight=weight, zorder=4)
        else:
            if abs(at - mid) > gap * 0.35:  # a displaced label needs a leader
                ax.plot([x + node_w, x + node_w + 0.008], [mid, at],
                        color="#999999", linewidth=0.4, zorder=2)
            ax.text(x + node_w + 0.010, at, label, ha="left", va="center",
                    fontsize=size, fontweight=weight, zorder=4)

    for l1 in l1s:
        y0, y1 = span_l1[l1]
        share = l1_totals[l1] / total * 100
        node(x_l1, y0, y1, L1_COLOR[l1],
             f"{L1_LABEL[l1]}  \u00b7  {l1_totals[l1]}  ({share:.1f}%)", "left", FS_L1, "bold")

    for key, at in zip(l2s, label_y):
        y0, y1 = span_l2[key]
        node(x_l2, y0, y1, L1_COLOR[key[0]],
             f"{L2_LABEL.get(key[1], key[1])}  \u00b7  {l2_totals[key]}", "right", FS_L2, label_y=at)

    # Headings sit over the text they name. Centring them on the nodes collides,
    # because a Level 1 label runs left of its node while a Level 2 label runs
    # right of its own.
    for x, align, title in (
        (x_l1 - 0.012, "right", "Level 1 \u2014 capability domain"),
        (x_l2 + node_w + 0.010, "left", "Level 2 \u2014 sub-domain"),
    ):
        ax.text(x, view_hi - gap * 1.2, title, ha=align, va="bottom",
                fontsize=FS_HEAD, fontweight="bold")

    ax.set_xlim(-0.25, 1.08)
    ax.set_ylim(view_lo, view_hi)
    ax.axis("off")
    # No suptitle and no in-figure note: Figure~\ref{fig:taxonomy-sankey}'s
    # caption carries the population, the provenance and the facet counts.
    fit_label_width(fig, ax)
    written = path_stem.with_suffix(".pdf")
    fig.savefig(written)
    plt.close(fig)
    return {"nodes_l2": len(l2s), "total": total}


def fit_label_width(fig, ax):
    """Fit text inside the authored page width without reducing font sizes."""
    for _ in range(60):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        extents = [text.get_window_extent(renderer) for text in ax.texts]
        left = min(box.x0 for box in extents)
        right = max(box.x1 for box in extents)
        # Leave a small safety margin for PDF versus raster font metrics.
        margin = fig.bbox.width * 0.012
        if left >= margin and right <= fig.bbox.width - margin:
            return
        inverse = ax.transData.inverted()
        lo, hi = ax.get_xlim()
        required_lo = inverse.transform((left - margin, 0))[0]
        required_hi = inverse.transform((right + margin, 0))[0]
        ax.set_xlim(min(lo, required_lo), max(hi, required_hi))
    raise ValueError("Sankey labels do not fit the page at the authored font size")


# --- Trends -------------------------------------------------------------

# Panel A starts at 2023-01-01, the first full period after ChatGPT's release.
# Earlier dated records keep an aggregate column; undated records keep another.
# The period axis therefore focuses on the recent expansion without dropping
# either group from the population.
#
# The step is a reading choice, not a data one: all three run off the same
# release dates. It follows `taxonomy_trends.TREND_PERIOD`, which is also the
# granularity Panel B's shares are computed at, so one edit moves both panels.
# `--period` overrides Panel A for exploration; the reproducible manuscript
# build uses the default period shared by both panels.
PANEL_A_PERIOD = TREND_PERIOD


def period_axis(rows, months, end):
    """Bucket the census for Panel A. Every record lands somewhere.

    Returns the contiguous periods from the start of `WINDOW_START_YEAR` through
    `end`, the per-bucket Level 1 counts, and the two groups no period can hold:
    records dated before the window, and records with no date at all. The axis is
    stepped rather than taken from the keys present, so a period with no releases
    stays on it as a gap instead of closing up.
    """
    start = (WINDOW_START_YEAR, 1)
    per_year = 12 // months
    buckets, before, undated = defaultdict(Counter), Counter(), Counter()
    before_years = set()
    for row in rows:
        when = period_key(row.get("release_date"), months)
        if when is None:
            undated[row["l1"]] += 1
        elif when < start:
            before[row["l1"]] += 1
            before_years.add(when[0])
        else:
            buckets[when][row["l1"]] += 1

    last = max([end, *buckets])
    axis, cursor = [], start
    while cursor <= last:
        axis.append(cursor)
        year, index = cursor
        cursor = (year, index + 1) if index < per_year else (year + 1, 1)
    span = (min(before_years), max(before_years)) if before_years else None
    return axis, dict(buckets), before, undated, span


def draw_trends(rows, trends, path_stem, order, period=PANEL_A_PERIOD):
    months = PERIODS[period]["months"]
    cutoff = datetime.fromisoformat(DISCOVERY_CUTOFF)
    axis, buckets, before, undated, before_span = period_axis(
        rows, months, period_key(DISCOVERY_CUTOFF, months))
    # Panel A buckets the census rows itself, because the trends file is a year
    # series; these keep the two readings of the same evidence in agreement.
    assert sum(undated.values()) == trends["undated"]
    placed = sum(before.values()) + sum(sum(counts.values()) for counts in buckets.values())
    assert placed == trends["dated"]

    # Three columns across the top. The middle one is the period axis; the
    # two flanking columns hold the records no half-year can take. The left one
    # shares the main scale, because the pre-window years hold a comparable
    # number of records. The larger undated column uses its own scale so
    # the dated bars remain readable.
    fig = plt.figure(figsize=(FIG_WIDTH_IN, 5.7))
    # Explicit margins: tight_layout cannot handle a hand-built gridspec whose
    # columns carry different scales, and warns rather than laying it out.
    grid = fig.add_gridspec(2, 3, height_ratios=[1.2, 1.0], width_ratios=[1.5, 11, 1.5],
                            hspace=1.05, wspace=0.07,
                            left=0.095, right=0.955, top=0.945, bottom=0.175)
    ax_top = fig.add_subplot(grid[0, 1])
    ax_before = fig.add_subplot(grid[0, 0], sharey=ax_top)
    ax_undated = fig.add_subplot(grid[0, 2])
    ax_mid = fig.add_subplot(grid[1, :])

    # Panel A: every record. The dated ones from 2023 on their period, the
    # earlier dated ones and the undated ones in their columns, all stacked by
    # Level 1. The two aggregate columns are hatched so neither is mistaken for
    # a period bucket.
    xs = list(range(len(axis)))
    bottom = [0.0] * len(axis)
    before_bottom = undated_bottom = 0.0
    full_counts = Counter(row["l1"] for row in rows)
    for l1 in order:
        values = [buckets.get(key, {}).get(l1, 0) for key in axis]
        ax_top.bar(xs, values, bottom=bottom, color=L1_COLOR[l1], width=0.74,
                   label=f"{L1_LABEL[l1]} ({full_counts[l1]})",
                   edgecolor="white", linewidth=0.4)
        bottom = [b + v for b, v in zip(bottom, values)]
        for ax, counts, base in ((ax_before, before, before_bottom),
                                 (ax_undated, undated, undated_bottom)):
            ax.bar([0], [counts.get(l1, 0)], bottom=[base], color=L1_COLOR[l1],
                   width=0.72, edgecolor="white", linewidth=0.4, hatch="//")
        before_bottom += before.get(l1, 0)
        undated_bottom += undated.get(l1, 0)
    peak = max(bottom)
    for x, value in zip(xs, bottom):
        if value:
            ax_top.text(x, value + peak * 0.02, str(int(value)), ha="center", va="bottom",
                        fontsize=6.5, color="#333333")

    mark = PERIODS[period]["mark"]
    labels = [f"{year}\n{mark}{index}" if mark else str(year) for year, index in axis]
    # The last bucket stops at the discovery cutoff rather than at the end of its
    # own months, so it is short by construction. Saying so on the tick keeps a
    # reader from taking the fall for the field slowing down.
    if axis[-1] == period_key(DISCOVERY_CUTOFF, months):
        labels[-1] += f"\nto {cutoff.day} {cutoff:%b}"
    ax_top.set_xticks(xs)
    ax_top.set_xticklabels(labels, fontsize=FS_TICK)
    ax_top.set_xlim(-0.72, len(axis) - 0.28)
    ax_top.set_ylim(0, peak * 1.12)
    ax_top.tick_params(axis="y", labelleft=False, length=0)
    ax_top.spines[["top", "right"]].set_visible(False)
    ax_top.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_top.set_axisbelow(True)

    ax_before.text(0, before_bottom + peak * 0.02, str(int(before_bottom)), ha="center",
                   va="bottom", fontsize=7.5, color="#333333", fontweight="bold")
    early = f"{before_span[0]}\u2013{before_span[1]}" if before_span else "before"
    years_spanned = before_span[1] - before_span[0] + 1 if before_span else 0
    ax_before.set_xticks([0])
    ax_before.set_xticklabels([f"{early}\n({years_spanned} years)"], fontsize=FS_TICK)
    ax_before.set_xlim(-0.62, 0.62)
    ax_before.set_ylabel("Benchmarks", fontsize=FS_AXIS)
    ax_before.tick_params(axis="y", labelsize=6.0)
    ax_before.spines[["top", "right"]].set_visible(False)
    ax_before.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_before.set_axisbelow(True)
    ax_before.set_title(
        f"A \u00b7 Release {PERIODS[period]['noun']} of all {trends['population']:,} "
        f"records, by Level 1",
        fontsize=FS_PANEL, fontweight="bold", loc="left", pad=6,
    )

    ax_undated.text(0, undated_bottom * 1.02, str(trends["undated"]), ha="center", va="bottom",
                    fontsize=7.5, color="#333333", fontweight="bold")
    ax_undated.set_xticks([0])
    ax_undated.set_xticklabels(["no release\ndate"], fontsize=FS_TICK)
    ax_undated.set_xlim(-0.62, 0.62)
    ax_undated.set_ylim(0, undated_bottom * 1.12)
    ax_undated.yaxis.tick_right()
    ax_undated.tick_params(axis="y", labelsize=6.0)
    # Said above the column, not as a y-label: a right-side y-label lands between
    # the bar and its own tick labels and was clipped off the page entirely when
    # the column sat at the figure edge.
    ax_undated.set_title("own scale", fontsize=6.5, color="#B71C1C", style="italic", pad=3)
    ax_undated.spines[["top", "left"]].set_visible(False)
    ax_undated.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_undated.set_axisbelow(True)

    # Panel B: shares only over the periods whose base and source mix support
    # them, and only for the series the evidence file's rule picked. This module
    # names no class: `shares["selected"]` is that rule's output and
    # `shares["series"]` holds every candidate it was ranked against, each with
    # the reason it was or was not drawn. The x axis is positional, because the
    # reported periods are contiguous and equally wide.
    shares = trends["shares"]
    reported = shares["reported"]
    xs = list(range(len(reported)))
    peak = 0.0
    for rank, key in enumerate(shares["selected"]):
        entry = shares["series"][key]
        values = [entry["share"][label] for label in reported]
        peak = max(peak, max(values))
        facet = entry["kind"] == "facet"
        color = FACET_COLOR[key] if facet else L1_COLOR[key]
        name = FACET_LABEL[key] if facet else L1_LABEL[key]
        ax_mid.plot(xs, values, color=color, linewidth=1.70 if rank == 0 else 1.15,
                    marker="o", markersize=3.5, zorder=3, alpha=0.95,
                    label=f"{name}  {entry['movement'] * 100:+.0f}pp")
        ax_mid.annotate(f"{values[-1] * 100:.0f}%", xy=(xs[-1], values[-1]),
                        xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=6.5, color=color, fontweight="bold")
    ax_mid.set_xticks(xs)
    ax_mid.set_xticklabels(
        [f"{label[:4]} {label[4:]}".strip() + f"\nn={shares['per_period'][label]}"
         for label in reported], fontsize=FS_TICK)
    ax_mid.set_xlim(-0.35, len(reported) - 1 + 0.55)
    ax_mid.set_ylim(0, max(0.35, peak * 1.18))
    ax_mid.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax_mid.set_ylabel("Share of dated records", fontsize=FS_AXIS)
    ax_mid.set_title(
        f"B \u00b7 The {len(shares['selected'])} series whose share moved most across the "
        f"reported {shares['noun']}s",
        fontsize=FS_PANEL, fontweight="bold", loc="left", pad=6,
    )

    ax_mid.spines[["top", "right"]].set_visible(False)
    ax_mid.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_mid.set_axisbelow(True)

    ax_top.legend(loc="upper center", bbox_to_anchor=(0.5, -0.38), ncol=3,
                  fontsize=6.2, frameon=False, columnspacing=1.2, handlelength=1.2)
    ax_mid.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3,
                  fontsize=6.2, frameon=False, columnspacing=1.2, handlelength=1.2)

    # No in-figure note: Figure~\ref{fig:taxonomy-trends}'s caption carries the
    # date provenance, the omitted low-base years and the per-source undated split.
    fig.savefig(path_stem.with_suffix(".pdf"))
    plt.close(fig)
    return {"axis": axis, "period": period, "labels": labels,
            "in_window": int(sum(bottom)),
            "before": int(before_bottom), "before_span": before_span}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", choices=sorted(PERIODS), default=PANEL_A_PERIOD,
                        help="Panel A's bucket width (default: PANEL_A_PERIOD, "
                             f"currently {PANEL_A_PERIOD})")
    args = parser.parse_args()
    os.environ["SOURCE_DATE_EPOCH"] = str(int(
        datetime.fromisoformat(DISCOVERY_CUTOFF).replace(tzinfo=timezone.utc).timestamp()
    ))

    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "pdf.fonttype": 42,
    })
    FIGURES.mkdir(exist_ok=True)

    check_dates()
    rows = load_rows()
    trends = json.loads(TRENDS.read_text(encoding="utf-8"))
    for relative, digest in trends["input_sha256"].items():
        if sha256(PAPER / relative) != digest:
            raise ValueError("Stale trends: rerun make reproduce-taxonomy")
    assert len(rows) == trends["population"] == 1283, "figures must draw the whole census"

    order = display_order(rows)
    info = draw_sankey(rows, FIGURES / "taxonomy-sankey", order)
    window = draw_trends(rows, trends, FIGURES / "taxonomy-trends", order, args.period)

    print(f"taxonomy-sankey  : {info['total']:,} records from "
          f"{len({r['source'] for r in rows})} sources, "
          f"{len({r['l1'] for r in rows})} L1 -> {info['nodes_l2']} L2 nodes")
    first, last = (label.replace("\n", " ").split(" to ")[0] for label in
                   (window["labels"][0], window["labels"][-1]))
    print(f"taxonomy-trends  : {window['in_window']} records over {first}-{last} in "
          f"{len(window['axis'])} {PERIODS[window['period']]['noun']} buckets; "
          f"{window['before']} dated before the window and {trends['undated']} undated "
          f"stated on the figure")
    if window["period"] != PANEL_A_PERIOD:
        print(f"    note: the figure now holds the {window['period']} view. Set "
              f"PANEL_A_PERIOD = {window['period']!r} to keep it, or rerun without "
              f"--period to restore the committed one.")
    for name in ("taxonomy-sankey", "taxonomy-trends"):
        written = FIGURES / f"{name}.pdf"
        print(f"    {written.relative_to(PAPER)}  {written.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
