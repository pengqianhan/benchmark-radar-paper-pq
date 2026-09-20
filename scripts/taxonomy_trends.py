#!/usr/bin/env python3
"""Year series for the benchmark taxonomy, over every dated record.

No time window. Every record in `benchmark-taxonomy-dated.jsonl` that carries a
benchmark release date enters its release year, from the earliest year present
to the discovery cutoff. Records with no release date are counted and named
rather than dropped silently: they cannot be placed on a year axis at all, and
a share computed without saying so would misstate the corpus.

Each year's shares are taken over that year's dated records, so a year with a
handful of records reports a share built on a handful. `min_reliable` marks the
years whose base is large enough to read as a trend rather than as noise.

Usage:
    python3 scripts/taxonomy_trends.py            # write evidence/benchmark-taxonomy-trends.json
    python3 scripts/taxonomy_trends.py --check    # verify the committed file
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from supplement_taxonomy_dates import ROWS, SUPPLEMENTS, check as check_dates, sha256

PAPER = Path(__file__).resolve().parents[1]
OUT = PAPER / "evidence" / "benchmark-taxonomy-trends.json"
# Manuscript macros for the eligibility rule Section 4.2 states in prose.
OUT_MACROS = PAPER / "taxonomy-trend-data.tex"

# A year needs this many dated records before a percentage is worth reading.
MIN_RELIABLE = 30
# It also needs a source mix close to the corpus's. A count threshold cannot see
# that the OpenCompass crawl stops at the discovery cutoff, so the final year is
# dominated by LLM Stats and model reports. Its share also reflects which
# catalogues supplied the records. Use total variation distance from the
# pooled mix; the threshold is held fixed when date evidence is supplemented.
MAX_MIX_DEVIATION = 0.25

# --- Panel B: the periods whose share may be read, and the series drawn -----

# The trend granularity, shared with the figure so both panels run on one clock.
# The window opens on 2023-01-01, the first full period after ChatGPT's release.
TREND_PERIOD = "half"
WINDOW_START_YEAR = 2023
PERIODS = {
    "quarter": {"months": 3, "mark": "Q", "noun": "quarter"},
    "half": {"months": 6, "mark": "H", "noun": "half-year"},
    "year": {"months": 12, "mark": "", "noun": "year"},
}

# Which series Panel B draws is a rule, not a list. A hand-picked list cannot be
# checked against the data it claims to summarise, and the one this replaced had
# gone stale: it drew two classes whose share moved under a point while leaving
# the examination facet, which moved ten, off the chart.
#
# A series enters the ranking only with this many dated records inside the
# reported periods. At twenty, one record cannot move its share by more than
# about five points in the thinnest reported period.
SHARE_SERIES_MIN_RECORDS = 20
# Lines on the panel. Six fills the legend's three columns twice over.
SHARE_SERIES_DRAWN = 6
# Movement is ranked on pooled counts, not on a first-to-last difference: with
# the earliest reported period an order of magnitude thinner than the latest, an
# endpoint rule promoted two series whose whole movement was four records in
# that thin period. The earliest half of the reported periods is pooled against
# the latest half, and the middle one is dropped when there is an odd number.
#
# A series more than this contained in one already drawn is skipped. The
# Multimodal Perception & Generation class and the multimodal facet share every
# record the class holds, so the second line spends a slot without adding a
# dimension; the facet still reaches the chart when the class does not.
SHARE_SERIES_MAX_CONTAINMENT = 0.8

# Facets worth a series of their own. The interaction axis carries the finding
# the flat five-way chart cannot show, so it leads.
TRACKED_FACETS = [
    ("interaction", "agentic"),
    ("modality", "multimodal"), ("modality", "image"), ("modality", "video"),
    ("modality", "audio"), ("modality", "embodied"), ("modality", "gui"),
    ("operational", "reasoning"), ("operational", "tool_calling"),
    ("operational", "long_context"), ("operational", "retrieval_rag"),
    ("operational", "safety_probe"), ("operational", "spatial"),
    ("operational", "multilingual"), ("operational", "examination"),
    ("operational", "instruction_following"),
]


def tex_period(label):
    """`2023H2` as `2023~H2`, the spelling the manuscript uses."""
    head, mark = label[:4], label[4:]
    return f"{head}~{mark}" if mark else head


def period_key(date, months):
    """(year, period index) for an ISO release date, or None when there is none.

    The index is one-based inside its year, so `half` gives H1/H2 and `quarter`
    Q1-Q4. Comparing the tuples orders the axis.
    """
    if not isinstance(date, str) or len(date) < 7 or not date[:4].isdigit():
        return None
    return int(date[:4]), (int(date[5:7]) - 1) // months + 1


def period_label(key, period=TREND_PERIOD):
    """`(2023, 2)` as `2023H2`: one token, sortable, and the figure's tick."""
    year, index = key
    mark = PERIODS[period]["mark"]
    return f"{year}{mark}{index}" if mark else str(year)


def build_shares(rows, period=TREND_PERIOD):
    """Panel B: the periods whose share may be read, and the series to draw.

    Eligibility is the year rule applied to periods, unchanged: enough dated
    records, and a source mix close to the pooled one. Selection is
    `SHARE_SERIES_*` and nothing else -- no series is named in this module, so
    the panel follows the census instead of an author's memory of it. Every
    candidate is published with its movement and the reason it was or was not
    drawn, so a reader can check the choice rather than take it.
    """
    months = PERIODS[period]["months"]
    buckets = [(period_key(row["release_date"], months), row) for row in rows]
    periods = sorted({key for key, _ in buckets})

    per_period = Counter(key for key, _ in buckets)
    sources = defaultdict(Counter)
    agentic = Counter()
    agentic_by_source = defaultdict(Counter)
    counts = defaultdict(Counter)
    members = defaultdict(dict)
    kinds = {}
    for key, row in buckets:
        sources[key][row["source"]] += 1
        if "agentic" in row["interaction"]:
            agentic[key] += 1
            agentic_by_source[row["source"]][key] += 1
        entries = [("l1", row["l1"])]
        entries += [("facet", f"{axis}:{value}") for axis, value in TRACKED_FACETS
                    if value in row[axis]]
        for kind, name in entries:
            counts[name][key] += 1
            members[name][row["key"]] = key
            kinds[name] = kind

    pooled = Counter(row["source"] for row in rows)
    pooled = {source: count / len(rows) for source, count in pooled.items()}
    deviation = {
        key: round(0.5 * sum(abs(sources[key].get(source, 0) / per_period[key] - share)
                             for source, share in pooled.items()), 4)
        for key in periods
    }
    reported = [key for key in periods
                if per_period[key] >= MIN_RELIABLE and deviation[key] <= MAX_MIX_DEVIATION]
    if not reported:
        raise ValueError(f"no {period} period is reportable; inspect the thresholds")

    # Pooled halves. `//` on both ends drops the middle period of an odd run
    # rather than letting it count twice.
    span = len(reported) // 2
    early, late = reported[:span], reported[-span:]
    base_early = sum(per_period[key] for key in early)
    base_late = sum(per_period[key] for key in late)

    candidates = []
    for name, per_key in counts.items():
        total = sum(per_key.get(key, 0) for key in reported)
        movement = (sum(per_key.get(key, 0) for key in late) / base_late
                    - sum(per_key.get(key, 0) for key in early) / base_early)
        candidates.append({
            "key": name,
            "kind": kinds[name],
            "records": total,
            "movement": round(movement, 4),
            "counts": {period_label(key, period): per_key.get(key, 0) for key in reported},
            "share": {period_label(key, period): round(per_key.get(key, 0) / per_period[key], 4)
                      for key in reported},
        })
    candidates.sort(key=lambda entry: (-abs(entry["movement"]), -entry["records"], entry["key"]))

    reported_set = set(reported)
    selected, drawn = [], []
    for entry in candidates:
        held = {row_key for row_key, key in members[entry["key"]].items() if key in reported_set}
        # `rule` is the machine-readable half of `reason`: which clause decided.
        if entry["records"] < SHARE_SERIES_MIN_RECORDS:
            entry["rule"] = "base"
            entry["reason"] = f"fewer than {SHARE_SERIES_MIN_RECORDS} records in the reported periods"
        elif len(selected) == SHARE_SERIES_DRAWN:
            entry["rule"] = "rank"
            entry["reason"] = f"outside the {SHARE_SERIES_DRAWN} largest movements"
        else:
            covering = [(len(held & other) / min(len(held), len(other)), name)
                        for name, other in drawn]
            worst, by = max(covering, default=(0.0, None))
            if worst > SHARE_SERIES_MAX_CONTAINMENT:
                entry["rule"] = "containment"
                entry["reason"] = f"{worst:.0%} of its records are already drawn as {by}"
            else:
                entry["rule"] = "drawn"
                entry["reason"] = f"movement rank {len(selected) + 1}"
                selected.append(entry["key"])
                drawn.append((entry["key"], held))
        entry["drawn"] = entry["key"] in selected

    # The same reweighting the year series reports, over the periods drawn here:
    # each reported period's agentic share recomputed at the pooled source mix of
    # those periods, which is what lets the prose say the rise is not a change of
    # catalogue. Reported in percentage points.
    reference = {
        source: sum(sources[key].get(source, 0) for key in reported) / base_reported
        for source, base_reported in
        [(source, sum(per_period[key] for key in reported)) for source in pooled]
    }
    adjustment = 0.0
    for key in reported:
        crude = agentic[key] / per_period[key]
        numerator = denominator = 0.0
        for source, weight in reference.items():
            base = sources[key].get(source, 0)
            if base:
                numerator += weight * (agentic_by_source[source].get(key, 0) / base)
                denominator += weight
        adjustment = max(adjustment, abs(numerator / denominator - crude) * 100)

    return {
        "period": period,
        "noun": PERIODS[period]["noun"],
        "window_start_year": WINDOW_START_YEAR,
        "periods": [period_label(key, period) for key in periods],
        "per_period": {period_label(key, period): per_period[key] for key in periods},
        "mix_deviation": {period_label(key, period): deviation[key] for key in periods},
        "reported": [period_label(key, period) for key in reported],
        "movement_halves": {
            "early": [period_label(key, period) for key in early],
            "late": [period_label(key, period) for key in late],
        },
        "excluded_records": len(rows) - sum(per_period[key] for key in reported),
        "min_records": SHARE_SERIES_MIN_RECORDS,
        "drawn": SHARE_SERIES_DRAWN,
        "max_containment": SHARE_SERIES_MAX_CONTAINMENT,
        "mix_adjustment": round(adjustment, 1),
        "selected": selected,
        "series": {entry["key"]: entry for entry in candidates},
    }


def release_year(row):
    value = row.get("release_date")
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def build():
    check_dates()
    supplement = json.loads(SUPPLEMENTS.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]
    dated = [(release_year(r), r) for r in rows]
    undated = [r for year, r in dated if year is None]
    dated = [(year, r) for year, r in dated if year is not None]

    per_year = Counter(year for year, _ in dated)
    years = sorted(per_year)

    l1 = defaultdict(Counter)
    l2 = defaultdict(Counter)
    facets = defaultdict(Counter)
    sources = defaultdict(Counter)
    source_agentic = defaultdict(Counter)
    for year, row in dated:
        l1[row["l1"]][year] += 1
        l2[f"{row['l1']}/{row['l2']}"][year] += 1
        sources[row["source"]][year] += 1
        if "agentic" in row["interaction"]:
            source_agentic[row["source"]][year] += 1
        for axis, value in TRACKED_FACETS:
            if value in row[axis]:
                facets[f"{axis}:{value}"][year] += 1

    def series(counter):
        return {
            "counts": {str(y): counter.get(y, 0) for y in years},
            "share": {
                str(y): round(counter.get(y, 0) / per_year[y], 4) if per_year[y] else None
                for y in years
            },
            "total": sum(counter.values()),
        }

    # A year's source mix is not constant: the OpenCompass crawl stops at the
    # discovery cutoff and has limited coverage of 2026 entries. An overall
    # share can mix a change in the field with a change in which catalogue
    # supplied that year's records.
    # These per-source series let a reader hold the source constant.
    stratified = {}
    for source, per_source_year in sources.items():
        stratified[source] = {
            "base": {str(y): per_source_year.get(y, 0) for y in years},
            "agentic": {str(y): source_agentic[source].get(y, 0) for y in years},
            "agentic_share": {
                str(y): (round(source_agentic[source].get(y, 0) / per_source_year[y], 4)
                         if per_source_year.get(y) else None)
                for y in years
            },
            "share_of_year": {
                str(y): round(per_source_year.get(y, 0) / per_year[y], 4) if per_year[y] else None
                for y in years
            },
        }

    pooled = {source: sum(per_source_year.values()) / len(dated)
              for source, per_source_year in sources.items()}
    mix_deviation = {
        str(y): round(0.5 * sum(abs(stratified[s]["share_of_year"][str(y)] - pooled[s])
                                for s in stratified), 4)
        for y in years
    }
    reportable = [str(y) for y in years
                  if per_year[y] >= MIN_RELIABLE and mix_deviation[str(y)] <= MAX_MIX_DEVIATION]

    return {
        "schema_version": 2,
        "input_sha256": {str(path.relative_to(PAPER)): sha256(path)
                         for path in (ROWS, SUPPLEMENTS)},
        "date_coverage": {key: supplement[key] for key in
                          ("baseline_dated", "baseline_undated", "supplemented")},
        "definitions": {
            "population": "Every row in benchmark-taxonomy-dated.jsonl, dated and undated.",
            "dated": "Frozen census dates plus reviewed release or first introduction dates for previously undated records. Retrospective evidence does not extend the discovery cutoff.",
            "undated": "Rows with no release date. They cannot enter any year and are excluded from every share below.",
            "year": "The benchmark's own release year. Not a model release, not a crawl day.",
            "share": "That year's count over that year's dated records, not over the whole corpus.",
            "min_reliable": f"Years with fewer than {MIN_RELIABLE} dated records; read their shares as noise.",
            "mix_deviation": "Total variation distance between that year's source mix and the pooled mix.",
            "reportable_years": "Years whose share may be read: enough dated records and a source mix close to the corpus.",
            "l1": "Primary capability domain, one per record, so a year's L1 counts sum to that year's dated total.",
            "facets": "Orthogonal properties. A record can appear in several, so these do not sum to the year total.",
            "undated_by_l1": "Level 1 composition of the records that carry no release date, so they stay visible on the figure.",
            "stratified": "Per-source year series. `share_of_year` exposes the changing source mix; `agentic_share` holds the source constant.",
            "shares": ("Panel B: the same eligibility rule applied to "
                       f"{PERIODS[TREND_PERIOD]['noun']} periods, plus the ranking that picks "
                       "the series drawn. `series` holds every candidate with its movement and "
                       "the reason it was or was not drawn."),
        },
        "population": len(rows),
        "dated": len(dated),
        "undated": len(undated),
        "undated_by_source": dict(Counter(r["source"] for r in undated).most_common()),
        "undated_by_l1": dict(Counter(r["l1"] for r in undated).most_common()),
        "years": [str(y) for y in years],
        "per_year": {str(y): per_year[y] for y in years},
        "min_reliable": MIN_RELIABLE,
        "low_base_years": [str(y) for y in years if per_year[y] < MIN_RELIABLE],
        "max_mix_deviation": MAX_MIX_DEVIATION,
        "mix_deviation": mix_deviation,
        "unstable_mix_years": [str(y) for y in years
                               if per_year[y] >= MIN_RELIABLE
                               and mix_deviation[str(y)] > MAX_MIX_DEVIATION],
        "reportable_years": reportable,
        "l1": {k: series(v) for k, v in sorted(l1.items())},
        "l2": {k: series(v) for k, v in sorted(l2.items())},
        "facets": {k: series(v) for k, v in sorted(facets.items())},
        "sources": {k: series(v) for k, v in sorted(sources.items())},
        "stratified": dict(sorted(stratified.items())),
        "shares": build_shares([row for _, row in dated]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    # The year totals must account for every dated record, and the dated and
    # undated halves must account for the whole population.
    assert sum(data["per_year"].values()) == data["dated"]
    assert data["dated"] + data["undated"] == data["population"]
    assert sum(data["undated_by_l1"].values()) == data["undated"]
    assert sum(data["undated_by_source"].values()) == data["undated"]
    for source, series_ in data["stratified"].items():
        assert sum(series_["base"].values()) == sum(data["sources"][source]["counts"].values())
    for year in data["years"]:
        got = sum(s["counts"][year] for s in data["l1"].values())
        assert got == data["per_year"][year], f"{year}: L1 counts {got} != {data['per_year'][year]}"

    # Panel B's own numbers, so the caption states the rule the figure ran and
    # not the one an author remembers. Every period series closes on its base,
    # and the selection is a subset of the candidates it was ranked against.
    shares = data["shares"]
    for period in shares["reported"]:
        got = sum(entry["counts"][period] for entry in shares["series"].values()
                  if entry["kind"] == "l1")
        assert got == shares["per_period"][period], f"{period}: L1 counts do not close"
    assert set(shares["selected"]) <= set(shares["series"])
    assert len(shares["selected"]) <= SHARE_SERIES_DRAWN
    reported = shares["reported"]
    macros = "\n".join([
        "% Generated by scripts/taxonomy_trends.py. Do not edit by hand.",
        f"\\newcommand{{\\TaxonomyTrendDated}}{{{data['dated']}}}",
        f"\\newcommand{{\\TaxonomyTrendUndated}}{{{data['undated']}}}",
        f"\\newcommand{{\\TaxonomySupplementedDates}}{{{data['date_coverage']['supplemented']}}}",
        f"\\newcommand{{\\TaxonomySharePeriod}}{{{shares['noun']}}}",
        f"\\newcommand{{\\TaxonomyReportedPeriods}}{{{tex_period(reported[0])}--"
        f"{tex_period(reported[-1])}}}",
        f"\\newcommand{{\\TaxonomyWindowFirst}}"
        f"{{{tex_period(period_label((WINDOW_START_YEAR, 1)))}}}",
        f"\\newcommand{{\\TaxonomyMinPeriodRecords}}{{{MIN_RELIABLE}}}",
        f"\\newcommand{{\\TaxonomyExcludedFromShares}}{{{shares['excluded_records']}}}",
        f"\\newcommand{{\\TaxonomyMixAdjustment}}{{{shares['mix_adjustment']:.1f}}}",
        f"\\newcommand{{\\TaxonomySeriesDrawn}}{{{len(shares['selected'])}}}",
        f"\\newcommand{{\\TaxonomySeriesMinRecords}}{{{SHARE_SERIES_MIN_RECORDS}}}",
        f"\\newcommand{{\\TaxonomySeriesMaxContainment}}"
        f"{{{SHARE_SERIES_MAX_CONTAINMENT:.0%}}}".replace("%", "\\%"),
    ]) + "\n"

    if args.check:
        if not OUT_MACROS.exists() or OUT_MACROS.read_text(encoding="utf-8") != macros:
            print(f"{OUT_MACROS.relative_to(PAPER)} does not match a rebuild")
            return 1
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(PAPER)} does not match a rebuild")
            return 1
    else:
        OUT.write_text(text, encoding="utf-8")
        OUT_MACROS.write_text(macros, encoding="utf-8")

    print(f"population {data['population']}  dated {data['dated']}  undated {data['undated']}")
    print(f"years {data['years'][0]}-{data['years'][-1]}; reportable shares: "
          f"{', '.join(data['reportable_years'])}")
    print(f"excluded: low base {', '.join(data['low_base_years'])}; "
          f"unstable source mix {', '.join(data['unstable_mix_years']) or 'none'}")
    print(f"panel B  : {shares['noun']} shares over {', '.join(reported)}; "
          f"{shares['excluded_records']} dated records outside them")
    for rank, key in enumerate(shares["selected"], 1):
        entry = shares["series"][key]
        print(f"    {rank}. {key:<34} {entry['movement'] * 100:>+6.1f}pp  "
              f"n={entry['records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
