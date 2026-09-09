#!/usr/bin/env python3
"""Year series for the benchmark taxonomy, over every dated record.

No time window. Every record in `benchmark-taxonomy.jsonl` that carries a
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

PAPER = Path(__file__).resolve().parents[1]
ROWS = PAPER / "evidence" / "benchmark-taxonomy.jsonl"
OUT = PAPER / "evidence" / "benchmark-taxonomy-trends.json"
# Manuscript macros for the eligibility rule Section 4.2 states in prose.
OUT_MACROS = PAPER / "taxonomy-trend-data.tex"

# A year needs this many dated records before a percentage is worth reading.
MIN_RELIABLE = 30
# It also needs a source mix close to the corpus's. A count threshold cannot see
# that the OpenCompass crawl stops at the discovery cutoff, so the final year is
# drawn mostly from model reports and its share measures the change of catalogue
# rather than a change in the field. Total variation distance from the pooled
# mix; 2023-2025 sit at 0.03-0.07 and the truncated final year at 0.62, so the
# threshold separates them without being fitted to either.
MAX_MIX_DEVIATION = 0.25

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


def release_year(row):
    value = row.get("release_date")
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def build():
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
    # discovery cutoff and its 2026 entries have not been indexed yet, so 2026
    # is mostly model reports. An overall share therefore mixes a real change in
    # the field with a change in which catalogue supplied that year's records.
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
        "schema_version": 1,
        "definitions": {
            "population": "Every row in benchmark-taxonomy.jsonl, dated and undated.",
            "dated": "Rows carrying a benchmark release date in the frozen census. No proxy, no crawl date.",
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

    # The largest gap between a reported year's crude share and the same share
    # reweighted to a common source mix, which is what lets the prose claim the
    # rise is not a composition effect.
    pooled = {s: d["share_of_year"][data["reportable_years"][1]]
              for s, d in data["stratified"].items()}
    worst = 0.0
    for year in data["reportable_years"]:
        crude = data["facets"]["interaction:agentic"]["share"][year]
        num = den = 0.0
        for source, series_ in data["stratified"].items():
            if series_["base"][year]:
                num += pooled[source] * series_["agentic_share"][year]
                den += pooled[source]
        worst = max(worst, abs(num / den - crude) * 100)
    excluded = sum(v for y, v in data["per_year"].items() if y not in data["reportable_years"])
    macros = "\n".join([
        "% Generated by scripts/taxonomy_trends.py. Do not edit by hand.",
        f"\\newcommand{{\\TaxonomyMinYearRecords}}{{{MIN_RELIABLE}}}",
        f"\\newcommand{{\\TaxonomyExcludedFromShares}}{{{excluded}}}",
        f"\\newcommand{{\\TaxonomyMixAdjustment}}{{{worst:.1f}}}",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
