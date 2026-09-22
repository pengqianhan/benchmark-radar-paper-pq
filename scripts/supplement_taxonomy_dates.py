#!/usr/bin/env python3
"""Apply accepted Library date matches without changing the frozen census."""

import argparse
import json
from collections import Counter
from pathlib import Path

from match_library_dates import AUDIT, SNAPSHOT, sha256
from match_library_dates import build as build_matches
from match_library_dates import check as check_matches

PAPER = Path(__file__).resolve().parents[1]
BASE = PAPER / "evidence/benchmark-taxonomy.jsonl"
CENSUS = PAPER / "evidence/catalog-findings.json"
ROWS = PAPER / "evidence/benchmark-taxonomy-dated.jsonl"
SUPPLEMENTS = PAPER / "evidence/taxonomy-release-date-supplements.json"


def enrich(rows, matches):
    by_key = {row["key"]: row for row in rows}
    if len(by_key) != len(rows):
        raise ValueError("Duplicate catalog keys in the frozen classification")
    expected = {row["key"] for row in rows if row["release_date"] is None}
    match_keys = [entry["catalogKey"] for entry in matches]
    if len(set(match_keys)) != len(match_keys) or set(match_keys) != expected:
        raise ValueError("Matching audit must contain each original missing record exactly once")
    supplements = {}
    for entry in matches:
        if entry["decision"] != "accepted":
            if entry["release_date"] is not None:
                raise ValueError("Unaccepted candidate cannot supply a release date")
            continue
        if not entry["release_date"] or entry["release_date"] != entry["releaseEvidence"]["date"]:
            raise ValueError("Accepted date must come unchanged from Library releaseEvidence")
        key = entry["catalogKey"]
        supplements[key] = {
            "catalogKey": key, "name": entry["name"],
            "libraryId": entry["libraryId"], "match_method": entry["match_method"],
            "release_date": entry["release_date"], "precision": entry["precision"],
            "event": entry["event"], "original_scope": entry["date_scope"],
            "reason": entry["reason"], "releaseEvidence": entry["releaseEvidence"],
            "sources": [{"url": entry["releaseEvidence"]["sourceUrl"]}],
            "identity_review": entry["identity_review"],
        }
    enriched = []
    for row in rows:
        result = dict(row)
        if row["key"] in supplements:
            evidence = supplements[row["key"]]
            result["release_date"] = evidence["release_date"]
            result["release_date_evidence"] = {
                "file": str(SUPPLEMENTS.relative_to(PAPER)),
                "catalogKey": row["key"], "libraryId": evidence["libraryId"],
                "precision": evidence["precision"], "event": evidence["event"],
            }
        enriched.append(result)
    return enriched, [supplements[key] for key in sorted(supplements)]


def build():
    check_matches()
    census = json.loads(CENSUS.read_text())
    rows = [json.loads(line) for line in BASE.read_text().splitlines() if line]
    frozen = {row["key"]: row for row in census["records"]}
    if {row["key"] for row in rows} != set(frozen) or any(
            row["release_date"] != frozen[row["key"]]["release_date"] for row in rows):
        raise ValueError("Classification population/dates differ from frozen census")
    audit = build_matches()
    enriched, records = enrich(rows, audit["records"])
    baseline_dated = sum(row["release_date"] is not None for row in rows)
    manifest = {
        "schema_version": 2,
        "software_commit": census["software_commit"],
        "discovery_cutoff": census["discovery_cutoff"],
        "definition": "Retrospective release/introduction annotations for existing frozen source records. All supplemental dates come from the supplied 1107-record Library evidence snapshot; identity and event scope are checked separately. These are not uniformly dataset-download dates or counts of independent benchmark releases. Original census dates remain unchanged.",
        "selection": "Use accepted rows from the complete original-missing-date matching audit; exact source IDs or explicit identity reviews, plus applicable event scope. Never use names alone, placeholder dates, model dates or legacy dates as fallback donors. Preserve month/day precision.",
        "input_sha256": {str(path.relative_to(PAPER)): sha256(path)
                         for path in (CENSUS, BASE, SNAPSHOT, AUDIT)},
        "library_reviewed_records": audit["library_reviewed_records"],
        "library_source_sha256": audit["library_source_sha256"],
        "matching_decisions": audit["decisions"],
        "per_source": audit["per_source"],
        "population": len(rows), "baseline_dated": baseline_dated,
        "baseline_undated": len(rows) - baseline_dated,
        "supplemented": len(records), "dated": baseline_dated + len(records),
        "undated": len(rows) - baseline_dated - len(records),
        "precision_counts": dict(sorted(Counter(r["precision"] for r in records).items())),
        "records": records,
    }
    return enriched, manifest


def outputs():
    rows, manifest = build()
    return {
        ROWS: "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        SUPPLEMENTS: json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    }


def check():
    stale = [str(path.relative_to(PAPER)) for path, text in outputs().items()
             if not path.exists() or path.read_text() != text]
    if stale:
        raise ValueError("Stale date supplement outputs: " + ", ".join(stale))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        for path, text in outputs().items():
            path.write_text(text)
    manifest = json.loads(SUPPLEMENTS.read_text())
    print(f"population {manifest['population']}  supplemented {manifest['supplemented']}  "
          f"dated {manifest['dated']}  undated {manifest['undated']}")


if __name__ == "__main__":
    main()
