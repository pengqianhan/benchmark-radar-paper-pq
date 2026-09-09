#!/usr/bin/env python3
r"""Draw the taxonomy figures from the classified census.

Two figures, both from `evidence/benchmark-taxonomy.jsonl`:

  taxonomy-sankey    Level 1 -> Level 2 for all 1,283 source records. Every
                     record is one unit of ribbon height, so both columns are
                     equal in total and a reader can check coverage by eye.
                     Source composition is stated in the caption.
  taxonomy-trends    Release-year series over the 615 records that carry a
                     benchmark release date, with the 668 undated records
                     stated on the figure rather than left out silently.

Nothing is imputed and no record is dropped: a benchmark with no release date
is absent from the year panels by necessity, and the count is printed there.

Both are written as vector PDFs, which is what \includegraphics takes.

Usage:
    python3 scripts/plot_taxonomy.py     # write figures/taxonomy-sankey.pdf and -trends.pdf
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

ROWS = PAPER / "evidence" / "benchmark-taxonomy.jsonl"
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

FACET_LABEL = {
    "interaction:agentic": "agentic (facet)",
    "modality:multimodal": "multimodal (facet)",
    "modality:embodied": "embodied (facet)",
    "operational:tool_calling": "tool calling (facet)",
    "operational:long_context": "long context (facet)",
    "operational:examination": "examination (facet)",
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
    fig.savefig(path_stem.with_suffix(".pdf"))
    plt.close(fig)
    return {"nodes_l2": len(l2s), "total": total}


# --- Trends -------------------------------------------------------------

TREND_SERIES = [
    ("facets", "interaction:agentic", "#8172B3", 2.6),
    ("l1", "coding_se", L1_COLOR["coding_se"], 1.8),
    ("l1", "multimodal_perception", L1_COLOR["multimodal_perception"], 1.8),
    ("l1", "knowledge_factuality", L1_COLOR["knowledge_factuality"], 1.8),
    ("l1", "applied_verticals", L1_COLOR["applied_verticals"], 1.8),
    ("facets", "modality:embodied", "#2E7D32", 1.6),
    ("facets", "operational:tool_calling", "#C2185B", 1.6),
]


def draw_trends(trends, path_stem, order):
    years = [int(y) for y in trends["years"]]
    per_year = {int(k): v for k, v in trends["per_year"].items()}
    reportable = [int(y) for y in trends["reportable_years"]]
    # A real year axis. A categorical one would place 2010 next to 2015 and
    # read as a single step, which is not what the dates say.
    axis = list(range(min(years), max(years) + 1))
    excluded_total = sum(per_year[y] for y in years if y not in reportable)
    # The undated records cannot take a year, so they get their own column. It
    # holds 668 records against a largest year of 279, so a shared y-axis would
    # flatten every year bar; the column keeps its own scale, said on the axis.
    fig = plt.figure(figsize=(FIG_WIDTH_IN, 5.7))
    # Explicit margins: tight_layout cannot handle a hand-built gridspec whose
    # two columns carry different scales, and warns rather than laying it out.
    grid = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.0], width_ratios=[11, 1.5],
                            hspace=1.00, wspace=0.06,
                            left=0.085, right=0.965, top=0.955, bottom=0.175)
    ax_top = fig.add_subplot(grid[0, 0])
    ax_undated = fig.add_subplot(grid[0, 1])
    ax_mid = fig.add_subplot(grid[1, :])

    # Panel A: every record. Dated ones on the year axis, undated in their own
    # labelled column, both stacked by Level 1.
    bottom = {year: 0.0 for year in axis}
    undated_bottom = 0.0
    for l1 in order:
        series = trends["l1"].get(l1)
        values = [series["counts"].get(str(y), 0) for y in axis] if series else [0] * len(axis)
        ax_top.bar(axis, values, bottom=[bottom[y] for y in axis], color=L1_COLOR[l1],
                   width=0.74, label=f"{L1_LABEL[l1]} ({(series or {}).get('total', 0)})",
                   edgecolor="white", linewidth=0.4)
        for year, value in zip(axis, values):
            bottom[year] += value
        share = trends["undated_by_l1"].get(l1, 0)
        ax_undated.bar([0], [share], bottom=[undated_bottom], color=L1_COLOR[l1],
                       width=0.72, edgecolor="white", linewidth=0.4, hatch="//")
        undated_bottom += share
    peak = max(bottom.values())
    for year in axis:
        if per_year.get(year):
            ax_top.text(year, bottom[year] + peak * 0.02, str(per_year[year]),
                        ha="center", va="bottom", fontsize=6.0, color="#333333")
    ax_undated.text(0, undated_bottom * 1.02, str(trends["undated"]), ha="center", va="bottom",
                    fontsize=7.5, color="#333333", fontweight="bold")
    ax_undated.set_xticks([0])
    ax_undated.set_xticklabels(["no release\ndate"], fontsize=FS_TICK)
    ax_undated.set_xlim(-0.62, 0.62)
    ax_undated.set_ylim(0, undated_bottom * 1.12)
    ax_undated.yaxis.tick_right()
    ax_undated.tick_params(axis="y", labelsize=6.0)
    ax_undated.yaxis.set_label_position("right")
    ax_undated.set_ylabel("own scale", fontsize=6.5, color="#B71C1C", style="italic", labelpad=2)
    ax_undated.spines[["top", "left"]].set_visible(False)
    ax_undated.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_undated.set_axisbelow(True)
    ax_top.set_xticks(axis)
    ax_top.set_xticklabels([str(y) for y in axis], fontsize=FS_TICK, rotation=45)
    ax_top.set_xlim(min(axis) - 0.7, max(axis) + 0.7)
    ax_top.set_ylim(0, peak * 1.10)
    ax_top.set_ylabel("Benchmarks", fontsize=FS_AXIS)
    ax_top.set_title(
        f"A \u00b7 Release year of all {trends['population']:,} records, by Level 1",
        fontsize=FS_PANEL, fontweight="bold", loc="left", pad=6,
    )
    ax_top.spines[["top", "right"]].set_visible(False)
    ax_top.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_top.set_axisbelow(True)

    # Panel B: shares only where the base supports them. Drawing 2010-2022 here
    # would turn a single 2010 record into a 100% spike.
    for kind, key, color, width in TREND_SERIES:
        series = trends[kind][key]
        values = [series["share"][str(y)] for y in reportable]
        label = FACET_LABEL.get(key, L1_LABEL.get(key, key))
        ax_mid.plot(reportable, values, color=color, linewidth=width * 0.65, marker="o",
                    markersize=3.5, label=label, zorder=3, alpha=0.95)
        ax_mid.annotate(f"{values[-1] * 100:.0f}%", xy=(reportable[-1], values[-1]),
                        xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=6.5, color=color, fontweight="bold")
    ax_mid.set_xticks(reportable)
    ax_mid.set_xticklabels([f"{y}\nn={per_year[y]}" for y in reportable], fontsize=FS_TICK)
    ax_mid.set_xlim(reportable[0] - 0.35, reportable[-1] + 0.55)
    ax_mid.set_ylim(0, 0.35)
    ax_mid.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax_mid.set_ylabel("Share of dated records", fontsize=FS_AXIS)
    ax_mid.set_title(
        "B \u00b7 Selected classes and facets, over the years whose share the evidence supports",
        fontsize=FS_PANEL, fontweight="bold", loc="left", pad=6,
    )

    ax_mid.spines[["top", "right"]].set_visible(False)
    ax_mid.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_mid.set_axisbelow(True)

    ax_top.legend(loc="upper center", bbox_to_anchor=(0.5, -0.34), ncol=3,
                  fontsize=6.2, frameon=False, columnspacing=1.2, handlelength=1.2)
    ax_mid.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3,
                  fontsize=6.2, frameon=False, columnspacing=1.2, handlelength=1.2)

    # No in-figure note: Figure~\ref{fig:taxonomy-trends}'s caption carries the
    # date provenance, the omitted low-base years and the per-source undated split.
    fig.savefig(path_stem.with_suffix(".pdf"))
    plt.close(fig)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    os.environ.setdefault("SOURCE_DATE_EPOCH", str(int(
        datetime.fromisoformat(DISCOVERY_CUTOFF).replace(tzinfo=timezone.utc).timestamp()
    )))

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "pdf.fonttype": 42,
    })
    FIGURES.mkdir(exist_ok=True)

    rows = load_rows()
    trends = json.loads(TRENDS.read_text(encoding="utf-8"))
    assert len(rows) == trends["population"] == 1283, "figures must draw the whole census"

    order = display_order(rows)
    info = draw_sankey(rows, FIGURES / "taxonomy-sankey", order)
    draw_trends(trends, FIGURES / "taxonomy-trends", order)

    print(f"taxonomy-sankey  : {info['total']:,} records from "
          f"{len({r['source'] for r in rows})} sources, "
          f"{len({r['l1'] for r in rows})} L1 -> {info['nodes_l2']} L2 nodes")
    print(f"taxonomy-trends  : {trends['dated']} dated over "
          f"{trends['years'][0]}-{trends['years'][-1]}, {trends['undated']} undated stated on the figure")
    for name in ("taxonomy-sankey", "taxonomy-trends"):
        written = FIGURES / f"{name}.pdf"
        print(f"    {written.relative_to(PAPER)}  {written.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
