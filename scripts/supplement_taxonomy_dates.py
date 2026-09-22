#!/usr/bin/env python3
"""Combine accepted Library dates and explicitly selected passed legacy reviews."""

import argparse
import calendar
import csv
import io
import json
from collections import Counter
from datetime import date
from pathlib import Path

from match_library_dates import AUDIT, LEGACY, SNAPSHOT, sha256
from match_library_dates import build as build_matches
from match_library_dates import check as check_matches

PAPER = Path(__file__).resolve().parents[1]
BASE = PAPER / "evidence/benchmark-taxonomy.jsonl"
CENSUS = PAPER / "evidence/catalog-findings.json"
ROWS = PAPER / "evidence/benchmark-taxonomy-dated.jsonl"
SUPPLEMENTS = PAPER / "evidence/taxonomy-release-date-supplements.json"
SELECTION = PAPER / "evidence/release-date-legacy-selection.json"
COMBINED = PAPER / "evidence/release-date-matches.json"
COMBINED_CSV = PAPER / "evidence/release-date-matches.csv"


def validate_legacy_date(record, cutoff):
    """Read only the explicitly authorized field, retaining its event and precision."""
    verification = record.get("nextVerification") or {}
    value = verification.get("releaseDate", "")
    precision = verification.get("precision")
    if verification.get("status") != "passed":
        raise ValueError("Selected nextVerification must have passed")
    if (precision, len(value)) not in {("day", 10), ("month", 7)}:
        raise ValueError("Invalid legacy release date/precision")
    parsed = date.fromisoformat(value + "-01" if precision == "month" else value)
    if parsed.year == 1 or parsed.isoformat()[:len(value)] != value:
        raise ValueError("Placeholder or noncanonical legacy date")
    last_possible = (date(parsed.year, parsed.month, calendar.monthrange(parsed.year, parsed.month)[1])
                     if precision == "month" else parsed)
    if last_possible > date.fromisoformat(cutoff):
        raise ValueError("Legacy date is after or straddles the cutoff")
    if not verification.get("event") or not verification.get("reason") or not (
            verification.get("sources") and all(s.get("url") for s in verification["sources"])):
        raise ValueError("Legacy date requires a release/introduction event and source evidence")
    return verification


def combine_matches(matches, legacy, selected_keys, cutoff):
    """Keep Library dates; add only selected exact-key reviews to missing rows."""
    by_key = {row["catalogKey"]: row for row in matches}
    donors = {row["verification"]["catalogKey"]: (i, row) for i, row in enumerate(legacy)}
    if len(by_key) != len(matches) or len(donors) != len(legacy):
        raise ValueError("Duplicate source-record keys in date inputs")
    if len(set(selected_keys)) != len(selected_keys):
        raise ValueError("Duplicate selected legacy keys")
    for key in selected_keys:
        if key not in by_key or key not in donors:
            raise ValueError("Selected legacy key missing from original missing-date audit or donor file")
        if by_key[key]["decision"] == "accepted":
            raise ValueError("Legacy date must not replace an accepted Library date")
    result = []
    for entry in matches:
        accepted = entry["decision"] == "accepted"
        row = {key: entry[key] for key in (
            "catalogKey", "name", "source", "libraryId", "decision", "release_date",
            "precision", "event", "reason", "match_method", "identity_review", "date_scope",
            "releaseEvidence")}
        row.update(library_decision=entry["decision"],
                   library_candidate_date=entry["candidate_date"],
                   evidence_source="library" if accepted else None,
                   input_file=str(SNAPSHOT.relative_to(PAPER)) if accepted else None,
                   date_field="releaseEvidence.date" if accepted else None,
                   sources=[{"url": entry["releaseEvidence"]["sourceUrl"]}] if accepted else [])
        if entry["catalogKey"] in selected_keys:
            index, donor = donors[entry["catalogKey"]]
            verification = validate_legacy_date(donor, cutoff)
            row.update(decision="accepted", evidence_source="legacy_next_verification",
                       input_file=str(LEGACY.relative_to(PAPER)), date_field="nextVerification.releaseDate",
                       release_date=verification["releaseDate"], precision=verification["precision"],
                       event=verification["event"], reason=verification["reason"],
                       sources=verification["sources"], nextVerification=verification,
                       legacy_record_index=index, legacy_top_level_date=donor.get("date"),
                       match_method="exact_verification_catalogKey",
                       library_identity_review=entry["identity_review"], identity_review=None,
                       library_releaseEvidence=entry["releaseEvidence"], releaseEvidence=None,
                       date_scope=verification["event"])
        result.append(row)
    return result


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
        source = entry.get("evidence_source", "library")
        if source == "library":
            expected_date = entry["releaseEvidence"]["date"]
            sources = [{"url": entry["releaseEvidence"]["sourceUrl"]}]
        elif source == "legacy_next_verification":
            expected_date = entry["nextVerification"]["releaseDate"]
            sources = entry["nextVerification"]["sources"]
            if entry["nextVerification"]["status"] != "passed":
                raise ValueError("Accepted legacy verification must have passed")
        else:
            raise ValueError("Unknown date evidence source")
        if not entry["release_date"] or entry["release_date"] != expected_date:
            raise ValueError("Accepted date must come unchanged from its selected evidence field")
        key = entry["catalogKey"]
        supplements[key] = {
            "catalogKey": key, "name": entry["name"],
            "libraryId": entry["libraryId"], "match_method": entry["match_method"],
            "release_date": entry["release_date"], "precision": entry["precision"],
            "event": entry["event"], "original_scope": entry["date_scope"],
            "reason": entry["reason"], "releaseEvidence": entry["releaseEvidence"],
            "sources": sources, "evidence_source": source,
            "input_file": entry.get("input_file", str(SNAPSHOT.relative_to(PAPER))),
            "date_field": entry.get("date_field", "releaseEvidence.date"),
            "identity_review": entry["identity_review"],
        }
        if source == "legacy_next_verification":
            supplements[key].update(nextVerification=entry["nextVerification"],
                                    legacy_record_index=entry["legacy_record_index"],
                                    legacy_top_level_date=entry["legacy_top_level_date"])
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
                "evidence_source": evidence["evidence_source"],
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
    selection = json.loads(SELECTION.read_text())
    if selection["date_field"] != "nextVerification.releaseDate" or selection["input_sha256"] != {
            str(path.relative_to(PAPER)): sha256(path) for path in (LEGACY, AUDIT, CENSUS)}:
        raise ValueError("Legacy selection refers to changed inputs or an unauthorized date field")
    combined = combine_matches(audit["records"], json.loads(LEGACY.read_text()),
                               selection["catalog_keys"], census["discovery_cutoff"])
    enriched, records = enrich(rows, combined)
    baseline_dated = sum(row["release_date"] is not None for row in rows)
    manifest = {
        "schema_version": 3,
        "software_commit": census["software_commit"],
        "discovery_cutoff": census["discovery_cutoff"],
        "definition": "Retrospective release/introduction annotations for existing frozen source records. Library dates are retained unchanged; explicitly selected passed legacy reviews fill additional missing dates. These are not uniformly dataset-download dates or independent benchmark releases. Original census dates remain unchanged.",
        "selection": "Library releaseEvidence.date first, followed only by selected exact verification.catalogKey matches with passed nextVerification.releaseDate. Never use top-level legacy date, names alone, placeholder dates, model dates, or unselected legacy donors. Preserve event scope and month/day precision.",
        "input_sha256": {str(path.relative_to(PAPER)): sha256(path)
                         for path in (CENSUS, BASE, SNAPSHOT, AUDIT, LEGACY, SELECTION)},
        "library_reviewed_records": audit["library_reviewed_records"],
        "library_source_sha256": audit["library_source_sha256"],
        "library_matching_decisions": audit["decisions"],
        "matching_decisions": dict(sorted(Counter(r["decision"] for r in combined).items())),
        "date_source_counts": dict(sorted(Counter(r["evidence_source"] for r in records).items())),
        "per_source": {source: dict(sorted(Counter(r["decision"] for r in combined
                                                  if r["source"] == source).items()))
                       for source in sorted({r["source"] for r in combined})},
        "population": len(rows), "baseline_dated": baseline_dated,
        "baseline_undated": len(rows) - baseline_dated,
        "supplemented": len(records), "dated": baseline_dated + len(records),
        "undated": len(rows) - baseline_dated - len(records),
        "precision_counts": dict(sorted(Counter(r["precision"] for r in records).items())),
        "records": records,
        "matching_records": combined,
    }
    return enriched, manifest


def outputs():
    rows, manifest = build()
    combined = manifest.pop("matching_records")
    audit = {key: value for key, value in manifest.items() if key != "records"}
    audit["records"] = combined
    buffer = io.StringIO(newline="")
    fields = ["catalogKey", "name", "source", "decision", "evidence_source", "input_file",
              "date_field", "release_date", "precision", "event", "source_urls",
              "library_decision", "library_candidate_date", "reason"]
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for entry in combined:
        item = {key: entry.get(key) for key in fields}
        item["source_urls"] = ";".join(source["url"] for source in entry["sources"])
        writer.writerow(item)
    return {
        ROWS: "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        SUPPLEMENTS: json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        COMBINED: json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        COMBINED_CSV: buffer.getvalue(),
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
