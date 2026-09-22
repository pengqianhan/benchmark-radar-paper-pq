#!/usr/bin/env python3
"""Match reviewed Library date evidence to the frozen paper's undated records.

The Library snapshot is an annotation source, never a replacement population.
Only explicit source IDs or recorded identity reviews authorize a join. Names
retrieve candidates but never authorize a date transfer. All missing records,
including rejected and unmatched candidates, appear in the audit.
"""

import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
CENSUS = PAPER / "evidence/catalog-findings.json"
SNAPSHOT = PAPER / "evidence/library-reviewed-dates.json"
REVIEWS = PAPER / "evidence/library-date-match-reviews.json"
LEGACY = PAPER / "evidence/156_from_xiaoke_all_passed_en.json"
AUDIT = PAPER / "evidence/library-date-matches.json"
CSV = PAPER / "evidence/library-date-matches.csv"
SNAPSHOT_FIELDS = (
    "id", "name", "aliases", "description", "links", "catalogSources",
    "sourceAttribution", "source", "releasedAt", "releaseDatePrecision",
    "firstRelease", "releaseEvidence", "evaluationRole", "benchmarkParentId",
    "variantOf", "variantOfExternal", "mergedIds", "mergedRecordLinks",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def freeze(source):
    document = json.loads(source.read_text())
    selected = []
    for index, record in enumerate(document["records"]):
        if not record.get("releaseEvidence"):
            continue
        item = {key: record[key] for key in SNAPSHOT_FIELDS if key in record}
        item["input_record_index"] = index
        item["input_record_sha256"] = canonical_hash(record)
        selected.append(item)
    return {
        "schema_version": 1,
        "source_file": source.name,
        "source_sha256": sha256(source),
        "source_data_as_of": document["manifest"]["dataAsOf"],
        "source_record_count": len(document["records"]),
        "selection": "All and only records with nonempty releaseEvidence; preserve identity fields and complete date evidence. Human verification is supplied by the contributor, not independently re-performed by this extractor.",
        "selected_count": len(selected),
        "records": selected,
    }


def normalized_name(value):
    value = unicodedata.normalize("NFKC", value).casefold().replace("τ", "tau")
    # Preserve '+' and digits: base and Plus editions are different identities.
    return re.sub(r"[^\w+]", "", value, flags=re.UNICODE).replace("_", "")


def validate_evidence(record, cutoff):
    evidence = record["releaseEvidence"]
    value = evidence.get("date", "")
    precision = evidence.get("precision")
    if evidence.get("id") != record["id"]:
        raise ValueError(f"Evidence ID mismatch: {record['id']}")
    if (precision, len(value)) not in {("day", 10), ("month", 7)}:
        raise ValueError(f"Invalid date precision: {record['id']}")
    parsed = date.fromisoformat(value + "-01" if precision == "month" else value)
    if parsed.year == 1 or parsed.isoformat()[:len(value)] != value:
        raise ValueError(f"Placeholder or noncanonical date: {record['id']}")
    if not evidence.get("sourceUrl") or evidence.get("basis") not in {
            "paper-v1", "official-announcement"}:
        raise ValueError(f"Missing source or unsupported date basis: {record['id']}")
    # A month straddling the cutoff cannot establish pre-cutoff publication.
    last_possible = (date(parsed.year, parsed.month, calendar.monthrange(parsed.year, parsed.month)[1])
                     if precision == "month" else parsed)
    return last_possible <= date.fromisoformat(cutoff)


def legacy_index(records):
    result = {}
    for record in records:
        verification = record.get("nextVerification") or record["verification"]
        key = record["verification"]["catalogKey"]
        result[key] = {
            "date": verification.get("releaseDate") or verification["verifiedDate"],
            "precision": verification["precision"],
            "event": verification["event"],
            "sources": verification.get("sources") or verification.get("sourceChecks"),
        }
    return result


def match(census, snapshot, reviews, legacy):
    records = snapshot["records"]
    by_id = {record["id"]: record for record in records}
    if len(by_id) != len(records) or snapshot["selected_count"] != len(records):
        raise ValueError("Duplicate Library IDs or incorrect selected count")
    baseline = census["records"]
    by_key = {row["key"]: row for row in baseline}
    if len(by_key) != len(baseline):
        raise ValueError("Duplicate frozen source-record keys")
    missing = {key for key, row in by_key.items() if row["release_date"] is None}
    overrides = {row["catalogKey"]: row for row in reviews["records"]}
    if len(overrides) != len(reviews["records"]) or set(overrides) - missing:
        raise ValueError("Duplicate review or review outside original missing population")
    if reviews["snapshot_sha256"] != canonical_hash(snapshot):
        raise ValueError("Identity/date-scope reviews refer to a different snapshot")
    if reviews["census_sha256"] != canonical_hash(census):
        raise ValueError("Identity/date-scope reviews refer to a different frozen census")
    source_ids, names = defaultdict(set), defaultdict(set)
    before_cutoff = {}
    for record in records:
        before_cutoff[record["id"]] = validate_evidence(record, census["discovery_cutoff"])
        for source in record.get("catalogSources", []):
            source_ids[f"{source['catalog']}:{source['sourceId']}"].add(record["id"])
        for name in [record["name"], *record.get("aliases", [])]:
            names[normalized_name(name)].add(record["id"])
    old = legacy_index(legacy)
    rows = []
    for target in baseline:
        key = target["key"]
        if key not in missing:
            continue
        exact = sorted(source_ids[key])
        name_candidates = sorted(names[normalized_name(target["name"])])
        review = overrides.get(key)
        chosen = exact[0] if len(exact) == 1 else None
        method = "exact_source_id" if chosen else None
        decision = "unmatched" if not exact and not name_candidates else "identity_unresolved"
        reason = "No reviewed Library identity found." if decision == "unmatched" else (
            "Candidate names or multiple source-ID matches do not establish an unambiguous identity.")
        if review:
            chosen = review.get("libraryId")
            if chosen not in by_id or not review.get("reason") or not review.get("identityEvidence"):
                raise ValueError(f"Incomplete identity/date-scope review: {key}")
            method = "reviewed_identity" if chosen not in exact or len(exact) != 1 else method
            decision = review["decision"]
            reason = review["reason"]
            if decision not in {"accepted", "scope_not_release", "identity_unresolved"}:
                raise ValueError(f"Invalid reviewed decision: {key}")
        elif chosen:
            evidence = by_id[chosen]["releaseEvidence"]
            scope = evidence.get("dateScope")
            if scope in {"underlying-dataset", "public-disclosure"}:
                decision = "scope_not_release"
                reason = ("Evidence dates the underlying dataset or a public disclosure; "
                          "release/first introduction of this exact record is not established.")
            elif scope is not None:
                raise ValueError(f"Unrecognized evidence scope: {key}: {scope}")
            else:
                decision = "accepted"
                reason = ("Unique exact catalog/sourceId match; supplied reviewed evidence "
                          "identifies the named benchmark's paper or official introduction/release.")
        selected = by_id.get(chosen)
        evidence = selected["releaseEvidence"] if selected else None
        if chosen and not before_cutoff[chosen]:
            decision = "after_cutoff"
            reason = "The reviewed date is after the frozen discovery cutoff."
        row = {
            "catalogKey": key, "name": target["name"], "source": target["source"],
            "original_date": target["release_date"],
            "exact_source_id_candidates": exact, "name_candidates": name_candidates,
            "libraryId": chosen, "libraryName": selected["name"] if selected else None,
            "match_method": method, "decision": decision, "reason": reason,
            "candidate_date": evidence["date"] if evidence else None,
            "precision": evidence["precision"] if evidence else None,
            "date_scope": evidence.get("dateScope", "benchmark_introduction_or_release") if evidence else None,
            "event": (review.get("event") if review else None) or (
                "paper_introduction" if evidence and evidence["basis"] == "paper-v1"
                else "official_introduction_or_release" if evidence else None),
            "release_date": evidence["date"] if decision == "accepted" else None,
            "releaseEvidence": evidence,
            "identity_review": review,
            "legacy": old.get(key),
        }
        if key in old:
            old_date = old[key]["date"]
            new_date = row["candidate_date"]
            row["legacy_comparison"] = (
                "no_candidate" if new_date is None else "same_date" if new_date == old_date
                else "overlapping_precision" if new_date.startswith(old_date) or old_date.startswith(new_date)
                else "different_date")
        else:
            row["legacy_comparison"] = "not_in_legacy"
        rows.append(row)
    return rows


def build():
    census = json.loads(CENSUS.read_text())
    snapshot = json.loads(SNAPSHOT.read_text())
    reviews = json.loads(REVIEWS.read_text())
    rows = match(census, snapshot, reviews, json.loads(LEGACY.read_text()))
    sources = sorted({row["source"] for row in rows})
    return {
        "schema_version": 1,
        "software_commit": census["software_commit"],
        "discovery_cutoff": census["discovery_cutoff"],
        "definition": "Retrospective annotation of the original frozen missing-date population. Accepted dates come exclusively from the supplied reviewed Library snapshot. Legacy dates are comparison evidence only. Counts are source records, not independent benchmark releases.",
        "input_sha256": {str(path.relative_to(PAPER)): sha256(path)
                         for path in (CENSUS, SNAPSHOT, REVIEWS, LEGACY)},
        "library_source_sha256": snapshot["source_sha256"],
        "library_reviewed_records": snapshot["selected_count"],
        "population": len(census["records"]),
        "baseline_undated": len(rows),
        "source_id_matching": {
            "unique": sum(len(row["exact_source_id_candidates"]) == 1 for row in rows),
            "multiple": sum(len(row["exact_source_id_candidates"]) > 1 for row in rows),
            "none": sum(not row["exact_source_id_candidates"] for row in rows),
        },
        "decisions": dict(sorted(Counter(row["decision"] for row in rows).items())),
        "per_source": {source: dict(sorted(Counter(row["decision"] for row in rows
                                                  if row["source"] == source).items()))
                       for source in sources},
        "legacy_comparison": dict(sorted(Counter(row["legacy_comparison"] for row in rows).items())),
        "records": rows,
    }


def outputs():
    audit = build()
    buffer = io.StringIO(newline="")
    fields = ["catalogKey", "name", "source", "decision", "libraryId", "libraryName",
              "match_method", "candidate_date", "release_date", "precision", "date_scope",
              "event", "sourceUrl", "reason", "exact_source_id_candidates", "name_candidates",
              "legacy_date", "legacy_comparison"]
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in audit["records"]:
        item = {key: row.get(key) for key in fields}
        for key in ("exact_source_id_candidates", "name_candidates"):
            item[key] = ";".join(row[key])
        item["sourceUrl"] = (row["releaseEvidence"] or {}).get("sourceUrl")
        item["legacy_date"] = (row["legacy"] or {}).get("date")
        writer.writerow(item)
    return {AUDIT: json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            CSV: buffer.getvalue()}


def check():
    stale = [str(path.relative_to(PAPER)) for path, content in outputs().items()
             if not path.exists() or path.read_text() != content]
    if stale:
        raise ValueError("Stale Library matching outputs: " + ", ".join(stale))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-source", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.freeze_source:
        SNAPSHOT.write_text(json.dumps(freeze(args.freeze_source), ensure_ascii=False,
                                       sort_keys=True, indent=2) + "\n")
    elif args.check:
        check()
    else:
        for path, content in outputs().items():
            path.write_text(content)
        print(json.dumps(build()["decisions"], sort_keys=True))


if __name__ == "__main__":
    main()
