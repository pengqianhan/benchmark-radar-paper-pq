#!/usr/bin/env python3
"""Add reviewed release/introduction dates without changing the frozen census.

Only missing dates are filled, by source-specific catalogKey. The original
classification and all non-date measurements are retained. No network requests
or run-time timestamps enter these deterministic outputs.
"""

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
BASE = PAPER / "evidence/benchmark-taxonomy.jsonl"
REVIEWED = PAPER / "evidence/156_from_xiaoke_all_passed_en.json"
CENSUS = PAPER / "evidence/catalog-findings.json"
ROWS = PAPER / "evidence/benchmark-taxonomy-dated.jsonl"
SUPPLEMENTS = PAPER / "evidence/taxonomy-release-date-supplements.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enrich(rows, reviewed, cutoff):
    """Return new rows and normalized evidence; reject ambiguous or unsafe joins."""
    by_key = {row["key"]: row for row in rows}
    if len(by_key) != len(rows):
        raise ValueError("Duplicate catalog keys in the frozen classification")
    supplements = {}
    for position, record in enumerate(reviewed, 1):
        key = record["verification"]["catalogKey"]
        if key not in by_key or key in supplements:
            raise ValueError(f"Unknown or duplicate reviewed catalogKey: {key}")
        if by_key[key].get("release_date") is not None:
            raise ValueError(f"Refusing to overwrite a frozen release date: {key}")
        field = "nextVerification" if record.get("nextVerification") else "verification"
        verification = record[field]
        if verification["status"] != "passed":
            raise ValueError(f"Latest verification did not pass: {key}")
        value = verification.get("releaseDate") or verification.get("verifiedDate")
        precision = verification["precision"]
        if (precision, len(value or "")) not in {("day", 10), ("month", 7)}:
            raise ValueError(f"Invalid release date/precision: {key}: {value}, {precision}")
        parsed = date.fromisoformat(value + "-01" if precision == "month" else value)
        canonical = parsed.isoformat()[:7] if precision == "month" else parsed.isoformat()
        if value != canonical or parsed > date.fromisoformat(cutoff):
            raise ValueError(f"Invalid date or date after discovery cutoff: {key}: {value}")
        sources = verification.get("sources") or verification.get("sourceChecks")
        if not verification.get("event") or not sources or not all(s.get("url") for s in sources):
            raise ValueError(f"Missing release event or source evidence: {key}")
        supplements[key] = {
            "catalogKey": key,
            "name": record["name"],
            "release_date": value,
            "precision": precision,
            "event": verification["event"],
            "reason": verification["reason"],
            "sources": sources,
            "limitation": verification.get("limitation"),
            "checkedAt": verification["checkedAt"],
            "verificationField": field,
            "inputRecordIndex": position,
            "originalDate": record.get("date"),
        }
    enriched = []
    for row in rows:
        result = dict(row)
        if row["key"] in supplements:
            evidence = supplements[row["key"]]
            result["release_date"] = evidence["release_date"]
            result["release_date_evidence"] = {
                "file": str(SUPPLEMENTS.relative_to(PAPER)),
                "catalogKey": row["key"],
                "precision": evidence["precision"],
                "event": evidence["event"],
            }
        enriched.append(result)
    return enriched, [supplements[key] for key in sorted(supplements)]


def build():
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in BASE.read_text(encoding="utf-8").splitlines() if line]
    reviewed = json.loads(REVIEWED.read_text(encoding="utf-8"))
    enriched, records = enrich(rows, reviewed, census["discovery_cutoff"])
    baseline_dated = sum(row.get("release_date") is not None for row in rows)
    manifest = {
        "schema_version": 1,
        "software_commit": census["software_commit"],
        "discovery_cutoff": census["discovery_cutoff"],
        "definition": "Retrospective verification of release or first introduction events for existing frozen source records. Event scope is retained; these are not uniformly dataset-download dates. The original census and its date coverage remain unchanged.",
        "selection": "Use nextVerification when present, otherwise verification; require passed; use releaseDate or verifiedDate. Join only by verification.catalogKey, never by name or legacy id. Fill only missing dates. Preserve month/day precision.",
        "input_sha256": {str(path.relative_to(PAPER)): sha256(path)
                         for path in (CENSUS, BASE, REVIEWED)},
        "population": len(rows),
        "baseline_dated": baseline_dated,
        "baseline_undated": len(rows) - baseline_dated,
        "supplemented": len(records),
        "dated": baseline_dated + len(records),
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
             if not path.exists() or path.read_text(encoding="utf-8") != text]
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
            path.write_text(text, encoding="utf-8")
    manifest = json.loads(SUPPLEMENTS.read_text(encoding="utf-8"))
    print(f"population {manifest['population']}  supplemented {manifest['supplemented']}  "
          f"dated {manifest['dated']}  undated {manifest['undated']}")


if __name__ == "__main__":
    main()
