"""Regression cases for the benchmark taxonomy.

The first duty of this classifier is coverage: every source record in the frozen
census keeps exactly one row, including records whose crawl carried no evidence.
The second is that a label can be traced to a named source field.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
from classify_benchmarks import build, summarise  # noqa: E402
from taxonomy import GENERIC_L2, L1, L2, NOISE  # noqa: E402

# Landmark benchmarks whose primary domain is not in dispute. Cases where two
# L1 classes are both defensible are listed in DOCUMENTED_AMBIGUITY instead of
# being asserted here, so this set measures the classifier rather than taste.
GOLD_L1 = {
    "MMLU": "knowledge_factuality",
    "MMLU-Pro": "knowledge_factuality",
    "MMLU-Redux": "knowledge_factuality",
    "SuperGPQA": "knowledge_factuality",
    "AGIEval": "knowledge_factuality",
    "C-Eval": "knowledge_factuality",
    "CMMLU": "knowledge_factuality",
    "TriviaQA": "knowledge_factuality",
    "CommonSenseQA": "knowledge_factuality",
    "SimpleQA": "knowledge_factuality",
    "AIME": "math_logic",
    "HMMT": "math_logic",
    "MATH-500": "math_logic",
    "GSM8K": "math_logic",
    "ARC-AGI": "math_logic",
    "ARC-AGI-2": "math_logic",
    "HorizonMath": "math_logic",
    "HumanEval": "coding_se",
    "MBPP": "coding_se",
    "SWE-bench Verified": "coding_se",
    "SWE-bench Pro": "coding_se",
    "SWE-bench Science": "coding_se",
    "LiveCodeBench": "coding_se",
    "Codeforces": "coding_se",
    "Aider Polyglot": "coding_se",
    "Terminal-Bench": "agentic_tool_use",
    "OSWorld": "agentic_tool_use",
    "tau-bench": "agentic_tool_use",
    "tau2-bench": "agentic_tool_use",
    "BFCL": "agentic_tool_use",
    "BrowseComp": "agentic_tool_use",
    "WideSearch": "agentic_tool_use",
    "MCPMark": "agentic_tool_use",
    "Toolathlon Verified": "agentic_tool_use",
    "Vending Bench": "agentic_tool_use",
    "MMMU": "multimodal_perception",
    "MMMU-Pro": "multimodal_perception",
    "MathVista": "multimodal_perception",
    "MathVision": "multimodal_perception",
    "ChartQA": "multimodal_perception",
    "DocVQA": "multimodal_perception",
    "Video-MME": "multimodal_perception",
    "MMVU": "multimodal_perception",
    "OmniDocBench": "multimodal_perception",
    "CharXiv Reasoning": "multimodal_perception",
    "GPQA Diamond": "science_research",
    "CritPt": "science_research",
    "BioMysteryBench": "science_research",
    "SUPERChem": "science_research",
    "HealthBench": "applied_verticals",
    "GDPval": "applied_verticals",
    "JobBench": "applied_verticals",
    "Legal Agent Benchmark": "applied_verticals",
    "CVE-Bench": "safety_security",
    "CyberGym": "safety_security",
    "RealToxicityPrompts": "safety_security",
    "SafetyBench": "safety_security",
    "IFEval": "language_communication",
    "IFBench": "language_communication",
    "MultiChallenge": "language_communication",
    "LongBench": "language_communication",
    "MRCR": "language_communication",
    "Chatbot Arena": "language_communication",
    "Arena-Hard": "language_communication",
    "Creative Writing v3": "language_communication",
    "MMMLU": "language_communication",
    "LiveBench": "general_composite",
}

# Records where two L1 classes are each defensible. Recorded, not asserted: the
# point is that a reader knows which way the classifier went and why.
DOCUMENTED_AMBIGUITY = {
    "FinQA": ("math_logic", "applied_verticals"),
    "DROP": ("math_logic", "language_communication"),
    "SciCode": ("science_research", "coding_se"),
    "MLE-bench": ("science_research", "coding_se"),
    "ExploitBench": ("safety_security", "coding_se"),
    "LSAT": ("applied_verticals", "knowledge_factuality"),
    "BoolQ": ("knowledge_factuality", "language_communication"),
    "OfficeQA Pro": ("multimodal_perception", "applied_verticals"),
    "MMLU-ProX": ("applied_verticals", "knowledge_factuality"),
}


@pytest.fixture(scope="module")
def classified():
    census, rows = build()
    return census, rows, {r["name"]: r for r in rows}, summarise(census, rows)


def test_every_census_record_keeps_a_row(classified):
    census, rows, _, _ = classified
    assert [r["key"] for r in rows] == [r["key"] for r in census]
    assert len(rows) == len(census) >= 1259
    assert len({r["source"] for r in census}) >= 4


def test_no_record_is_dropped_for_missing_evidence(classified):
    """A crawl row with no tags and no description stays in, labelled `other`."""
    _, rows, _, _ = classified
    blank = [r for r in rows if r["unclassified_reason"] == "no_source_evidence"]
    assert blank, "the four empty LLM Stats community rows must still be present"
    for row in blank:
        assert row["l1"] == "other" and row["confidence"] == 0.0
        assert row["evidence"] == []


def test_counts_reconcile_to_the_population(classified):
    census, _, _, summary = classified
    assert sum(summary["by_l1"].values()) == len(census)
    assert sum(summary["by_l2"].values()) == len(census)
    for source, counts in summary["by_source_l1"].items():
        assert sum(counts.values()) == sum(1 for r in census if r["source"] == source)


def test_labels_are_well_formed(classified):
    _, rows, _, _ = classified
    for row in rows:
        assert row["l1"] in L1
        assert row["l2"] in L2[row["l1"]]
        for axis in ("modality", "interaction", "operational"):
            assert isinstance(row[axis], list)
        assert row["interaction"], "interaction always states static or agentic"


def test_non_topical_tokens_never_become_labels(classified):
    """`Unsupported`, `Open-Source`, `LLM`, `VLM` and venues are not topics."""
    _, rows, _, _ = classified
    for row in rows:
        for item in row["evidence"]:
            if item.get("token", "").strip().lower() in NOISE:
                assert "l1" not in item, f"{row['key']}: {item['token']} became a label"


def test_every_source_token_is_mapped(classified):
    _, _, _, summary = classified
    assert summary["unmapped_tokens"] == {}, "extend TOKEN_MAP or NOISE"


def test_gold_landmark_benchmarks(classified):
    _, _, by_name, _ = classified
    missing = [name for name in GOLD_L1 if name not in by_name]
    assert not missing, f"gold names absent from the census: {missing}"
    wrong = {
        name: (by_name[name]["l1"], expected)
        for name, expected in GOLD_L1.items()
        if by_name[name]["l1"] != expected
    }
    assert not wrong, f"L1 mismatches (got, expected): {wrong}"


def test_documented_ambiguity_stays_within_its_two_readings(classified):
    _, _, by_name, _ = classified
    for name, options in DOCUMENTED_AMBIGUITY.items():
        if name in by_name:
            assert by_name[name]["l1"] in options, f"{name} left both documented readings"


def test_generic_l2_only_when_nothing_specific_matched(classified):
    _, rows, _, _ = classified
    for row in rows:
        if row["l2"] in GENERIC_L2 and row["l1"] != "other":
            specific = [l2 for l2 in row["l2_all"] if l2 in L2[row["l1"]] and l2 not in GENERIC_L2]
            assert not specific, f"{row['key']}: {specific} was available over {row['l2']}"


def test_agentic_coding_keeps_both_signals(classified):
    """The defect this taxonomy exists to fix: an agentic coding benchmark must
    stay under `coding_se` without losing its agentic reading."""
    _, _, by_name, _ = classified
    swe = by_name["SWE-bench Verified"]
    assert swe["l1"] == "coding_se"
    assert "agentic" in swe["interaction"], "the agentic reading survives as a facet"

    # And where both readings scored, the subject-over-layer rule is recorded.
    overridden = [
        r for r in by_name.values()
        if any(item.get("rule") == "subject_over_layer" for item in r["evidence"])
    ]
    assert overridden, "no record exercised the subject-over-layer rule"
    for row in overridden:
        assert row["l1"] not in ("agentic_tool_use", "multimodal_perception",
                                 "knowledge_factuality", "language_communication")


def test_facet_counts_exceed_their_l1(classified):
    """Agentic is a facet first: more records interact agentically than are
    primarily about the agent loop."""
    _, rows, _, summary = classified
    agentic_facet = summary["facets"]["interaction"].get("agentic", 0)
    assert agentic_facet > summary["by_l1"]["agentic_tool_use"]
    assert agentic_facet + summary["facets"]["interaction"]["static"] == len(rows)


def test_outputs_match_a_rebuild():
    """`--check` must pass against the committed JSONL and summary."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(PAPER / "scripts" / "classify_benchmarks.py"), "--check"],
        capture_output=True, text=True, cwd=PAPER,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_review_queue_is_bounded(classified):
    """Flagged rows are a review queue, not the bulk of the corpus."""
    _, rows, _, _ = classified
    flagged = [r for r in rows if r["needs_review"]]
    assert len(flagged) / len(rows) < 0.35
    assert Counter(r["l1"] for r in flagged)["other"] == 4


def test_trends_cover_every_dated_record():
    """The year series must account for every dated row and name the rest."""
    sys.path.insert(0, str(PAPER / "scripts"))
    from taxonomy_trends import build as build_trends

    data = build_trends()
    assert data["dated"] + data["undated"] == data["population"] == 1283
    assert sum(data["per_year"].values()) == data["dated"]
    assert sum(data["undated_by_source"].values()) == data["undated"]
    for year in data["years"]:
        l1_total = sum(series["counts"][year] for series in data["l1"].values())
        assert l1_total == data["per_year"][year], f"{year} L1 counts do not close"
        l2_total = sum(series["counts"][year] for series in data["l2"].values())
        assert l2_total == data["per_year"][year], f"{year} L2 counts do not close"


def test_trends_use_every_year_no_window():
    """The user asked for all dated records; no year may be silently dropped."""
    from taxonomy_trends import build as build_trends, release_year

    data = build_trends()
    rows = [json.loads(line) for line in
            (PAPER / "evidence" / "benchmark-taxonomy.jsonl").read_text().splitlines() if line]
    present = {str(release_year(r)) for r in rows if release_year(r) is not None}
    assert set(data["years"]) == present, "a release year present in the data has no series"


def test_trends_output_matches_a_rebuild():
    import subprocess

    result = subprocess.run(
        [sys.executable, str(PAPER / "scripts" / "taxonomy_trends.py"), "--check"],
        capture_output=True, text=True, cwd=PAPER,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_sankey_columns_carry_the_whole_census(classified):
    """Both Sankey columns must total the population, or the figure hides records.

    The source breakdown is checked too: the figure no longer draws a source
    column, but its caption still reports the per-source composition.
    """
    from collections import defaultdict

    _, rows, _, _ = classified
    source_l1 = defaultdict(Counter)
    l1_l2 = defaultdict(Counter)
    for row in rows:
        source_l1[row["source"]][row["l1"]] += 1
        l1_l2[row["l1"]][row["l2"]] += 1

    assert sum(sum(c.values()) for c in source_l1.values()) == len(rows)
    assert sum(sum(c.values()) for c in l1_l2.values()) == len(rows)
    # Every unit leaving an L1 node must have entered it.
    for l1, into in Counter(r["l1"] for r in rows).items():
        out = sum(l1_l2[l1].values())
        assert out == into, f"{l1}: {out} leaving vs {into} entering"


def test_pdf_timestamp_is_pinned_to_the_corpus_cutoff():
    """The figures must not carry a build timestamp.

    matplotlib writes /CreationDate into every PDF, which would make two builds
    of identical data differ. The date is pinned to the census's own discovery
    cutoff; this keeps that constant equal to the census rather than to whatever
    was typed once.
    """
    import plot_taxonomy

    census = json.loads((PAPER / "evidence" / "catalog-findings.json").read_text())
    assert plot_taxonomy.DISCOVERY_CUTOFF == census["discovery_cutoff"]


def test_figures_are_byte_reproducible():
    """Rebuilding the figures must not change a single byte."""
    import hashlib
    import subprocess

    figures = [PAPER / "figures" / f"taxonomy-{n}.pdf" for n in ("sankey", "trends")]
    before = [hashlib.sha256(f.read_bytes()).hexdigest() for f in figures]
    result = subprocess.run(
        [sys.executable, str(PAPER / "scripts" / "plot_taxonomy.py")],
        capture_output=True, text=True, cwd=PAPER,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    after = [hashlib.sha256(f.read_bytes()).hexdigest() for f in figures]
    assert before == after, "a rebuild changed the figures without the data changing"


def test_figures_render_and_are_current():
    """The committed figures must come from the committed classification."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(PAPER / "scripts" / "plot_taxonomy.py")],
        capture_output=True, text=True, cwd=PAPER,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    produced = {"taxonomy-sankey.pdf", "taxonomy-trends.pdf"}
    for name in produced:
        figure = PAPER / "figures" / name
        assert figure.exists() and figure.stat().st_size > 10_000, figure
    # Only these two files may exist. A dropped variant or a leftover raster
    # copy must not linger and be mistaken for the figure the manuscript cites.
    stale = sorted(
        path.name for path in (PAPER / "figures").glob("taxonomy-*")
        if path.name not in produced
    )
    assert not stale, f"stale taxonomy figures on disk: {stale}"


def test_figure_labels_are_the_canonical_class_names():
    """A figure must not rename a class.

    The plotting module carried its own label map and six of eleven names had
    drifted from the taxonomy -- `Coding & Software Eng.` for `Coding & Software
    Engineering`, `Safety & Security` for `Safety, Security & Alignment`, and so
    on -- so a reader could not match a figure to the data file. The map is now
    the taxonomy's own, and this keeps it that way.
    """
    import plot_taxonomy
    from taxonomy import L1 as canonical

    assert plot_taxonomy.L1_LABEL is canonical
    for key, label in canonical.items():
        assert not label.endswith("."), f"{key}: {label!r} is abbreviated"
    assert set(plot_taxonomy.L1_COLOR) == set(canonical), "every class needs a colour"


def test_figure_display_order_covers_every_class():
    """The stacking order both figures share must hold all classes, `other` last."""
    import plot_taxonomy

    rows = [json.loads(line) for line in
            (PAPER / "evidence" / "benchmark-taxonomy.jsonl").read_text().splitlines() if line]
    order = plot_taxonomy.display_order(rows)
    assert set(order) == {r["l1"] for r in rows}
    assert order[-1] == "other"
    counts = Counter(r["l1"] for r in rows)
    ranked = [counts[l1] for l1 in order[:-1]]
    assert ranked == sorted(ranked, reverse=True), "largest class first"


# Counter-examples found by adversarial review. A text pattern must not read a
# data source, an application domain, or the benchmark's own title as evidence
# that the benchmark is run as an agent.
NOT_AGENTIC = {
    "opencompass:2348": "named Shell; measures implicit risk in vertical domains",
    "llm-stats:cbnsl": "uses networks from the bnlearn repository",
    "opencompass:1274": "offers a modular codebase",
    "llm-stats:nuscene": "nuScenes autonomous driving domain",
    "llm-stats:surds": "autonomous-driving scenes",
    "llm-stats:vladbench": "vision-language autonomous-driving benchmark",
    "llm-stats:repobench": "repository-level code auto-completion",
    "llm-stats:repoqa": "long-context code understanding over repositories",
    "llm-stats:longbench-v2": "long-context multiple-choice questions",
    "llm-stats:bigcodebench": "function calls from 139 libraries, not an agent loop",
    "opencompass:1253": "same benchmark from the OpenCompass crawl",
    "llm-stats:humanity's-last-exam-(no-tools,-text-only)": "the variant that states no tools",
}

STILL_AGENTIC = {
    "model-reports:swe_bench_verified", "model-reports:osworld", "model-reports:tau_bench",
    "model-reports:terminal_bench", "model-reports:legal_agent_benchmark",
    "llm-stats:swe-bench-multilingual", "llm-stats:android-control-low-em",
    "llm-stats:cc-bench-v2-backend", "llm-stats:vision2web",
    "llm-stats:humanity's-last-exam-(with-tools,-text-only)",
}


def test_agentic_facet_rejects_non_interaction_evidence(classified):
    _, rows, _, _ = classified
    by_key = {row["key"]: row for row in rows}
    missing = [key for key in NOT_AGENTIC if key not in by_key]
    assert not missing, f"counter-example keys absent from the census: {missing}"
    wrong = {
        key: reason for key, reason in NOT_AGENTIC.items()
        if "agentic" in by_key[key]["interaction"]
    }
    assert not wrong, f"agentic asserted without interaction evidence: {wrong}"


def test_agentic_facet_survives_where_the_evidence_is_real(classified):
    _, rows, _, _ = classified
    by_key = {row["key"]: row for row in rows}
    lost = [key for key in STILL_AGENTIC if "agentic" not in by_key[key]["interaction"]]
    assert not lost, f"tightening the patterns dropped real agentic records: {lost}"


def test_tool_variants_of_one_benchmark_differ(classified):
    """The `(no tools)` and `(with tools)` HLE rows must not share a facet."""
    _, rows, _, _ = classified
    by_key = {row["key"]: row for row in rows}
    no_tools = by_key["llm-stats:humanity's-last-exam-(no-tools,-text-only)"]
    with_tools = by_key["llm-stats:humanity's-last-exam-(with-tools,-text-only)"]
    assert "tool_calling" not in no_tools["operational"]
    assert "tool_calling" in with_tools["operational"]
    assert no_tools["interaction"] == ["static"]
    assert "agentic" in with_tools["interaction"]


def test_undated_records_keep_their_classification():
    """Panel A draws the undated records, so their L1 split must be published."""
    from taxonomy_trends import build as build_trends, release_year

    data = build_trends()
    rows = [json.loads(line) for line in
            (PAPER / "evidence" / "benchmark-taxonomy.jsonl").read_text().splitlines() if line]
    undated = [r for r in rows if release_year(r) is None]
    assert sum(data["undated_by_l1"].values()) == len(undated) == data["undated"]
    assert data["undated_by_l1"] == dict(Counter(r["l1"] for r in undated).most_common())
    # The four evidence-free rows are undated too; they must not vanish here.
    assert data["undated_by_l1"].get("other") == 4


def test_stratified_series_expose_the_changing_source_mix():
    """Panel C holds the source constant, so per-source bases must reconcile."""
    from taxonomy_trends import build as build_trends

    data = build_trends()
    for year in data["years"]:
        mix = sum(s["share_of_year"][year] for s in data["stratified"].values())
        assert abs(mix - 1.0) < 1e-3, f"{year}: source shares sum to {mix}"
        base = sum(s["base"][year] for s in data["stratified"].values())
        assert base == data["per_year"][year]
    for source, series in data["stratified"].items():
        for year in data["years"]:
            assert series["agentic"][year] <= series["base"][year]
    # The finding that motivated this panel: 2026 is not the same cohort.
    oc = data["stratified"]["opencompass_hub"]["share_of_year"]
    assert oc["2025"] > 0.6 and oc["2026"] < 0.3, "the 2026 source break should be visible"


def test_year_shares_need_a_stable_source_mix_not_just_a_count():
    """A sufficient record count does not make a year's share readable.

    The OpenCompass crawl stops at the discovery cutoff, so the truncated final
    year clears the count threshold while being drawn from a different mix of
    catalogues. Reporting its share would measure the change of catalogue.
    """
    from taxonomy_trends import MAX_MIX_DEVIATION, MIN_RELIABLE
    from taxonomy_trends import build as build_trends

    data = build_trends()
    final = data["years"][-1]
    assert data["per_year"][final] >= MIN_RELIABLE, "the case only bites when the count passes"
    assert data["mix_deviation"][final] > MAX_MIX_DEVIATION
    assert final in data["unstable_mix_years"] and final not in data["reportable_years"]
    for year in data["reportable_years"]:
        assert data["per_year"][year] >= MIN_RELIABLE
        assert data["mix_deviation"][year] <= MAX_MIX_DEVIATION
    # Every dated record is either in a reported year or accounted for as excluded.
    excluded = sum(v for y, v in data["per_year"].items() if y not in data["reportable_years"])
    reported = sum(data["per_year"][y] for y in data["reportable_years"])
    assert excluded + reported == data["dated"]


def test_composition_adjustment_backs_the_prose_claim():
    """Section 4.2 claims reweighting moves the agentic share by at most 1.1
    points. That number is generated, and must stay small enough to support the
    sentence it appears in."""
    macros = (PAPER / "taxonomy-trend-data.tex").read_text()
    value = float(macros.split("TaxonomyMixAdjustment}}{")[1].split("}")[0]
                  if "TaxonomyMixAdjustment}}{" in macros
                  else macros.split("\\TaxonomyMixAdjustment}{")[1].split("}")[0])
    assert value <= 3.0, f"composition adjustment is {value} points; the claim no longer holds"
