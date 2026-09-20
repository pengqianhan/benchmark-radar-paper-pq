"""Date enrichment must preserve source identities, evidence and the census."""

import copy
import json
import sys
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
from supplement_taxonomy_dates import BASE, REVIEWED, build, check, enrich  # noqa: E402


def test_enrichment_changes_only_missing_dates_and_preserves_every_record():
    baseline = [json.loads(line) for line in BASE.read_text().splitlines()]
    enriched, manifest = build()
    assert [row["key"] for row in enriched] == [row["key"] for row in baseline]
    assert (manifest["population"], manifest["baseline_dated"], manifest["baseline_undated"],
            manifest["supplemented"], manifest["dated"], manifest["undated"]) == (
                1283, 615, 668, 156, 771, 512)
    changed = 0
    for original, result in zip(baseline, enriched):
        if result == original:
            continue
        changed += 1
        assert original["release_date"] is None
        assert result["release_date"]
        restored = dict(result)
        restored.pop("release_date_evidence")
        restored["release_date"] = None
        assert restored == original
    assert changed == 156
    assert manifest["precision_counts"] == {"day": 143, "month": 13}
    check()


def test_latest_verified_date_wins_and_cross_source_records_survive():
    reviewed = json.loads(REVIEWED.read_text())
    _, manifest = build()
    entries = {row["catalogKey"]: row for row in manifest["records"]}
    changed_from_original = 0
    for row in reviewed:
        field = "nextVerification" if row.get("nextVerification") else "verification"
        latest = row[field]
        actual = entries[row["verification"]["catalogKey"]]
        assert actual["release_date"] == (latest.get("releaseDate") or latest["verifiedDate"])
        assert actual["event"] == latest["event"]
        assert actual["precision"] == latest["precision"]
        assert actual["verificationField"] == field
        changed_from_original += actual["release_date"] != row["date"]
    assert changed_from_original > 0, "Exercise corrections, not only unchanged dates"
    assert len({row["id"] for row in reviewed}) == 154
    assert len(entries) == 156
    assert {"llm-stats:arxivmath", "model-reports:arxivmath"} <= entries.keys()


def test_month_precision_is_not_invented_as_a_day():
    reviewed = json.loads(REVIEWED.read_text())
    item = next(row for row in reviewed
                if (row.get("nextVerification") or row["verification"])["precision"] == "month")
    rows, _ = enrich([{"key": item["verification"]["catalogKey"], "release_date": None}],
                     [item], "2026-09-07")
    assert len(rows[0]["release_date"]) == 7
    assert rows[0]["release_date_evidence"]["precision"] == "month"


@pytest.mark.parametrize("problem", ["unknown_key", "duplicate_review", "duplicate_baseline",
                                    "existing_date", "failed_latest", "after_cutoff",
                                    "invalid_date", "precision_mismatch", "missing_source"])
def test_invalid_supplements_fail_instead_of_silently_dropping_records(problem):
    item = copy.deepcopy(json.loads(REVIEWED.read_text())[0])
    rows = [{"key": item["verification"]["catalogKey"], "release_date": None}]
    reviewed = [item]
    if problem == "unknown_key":
        item["verification"]["catalogKey"] = "missing:record"
    elif problem == "duplicate_review":
        reviewed.append(copy.deepcopy(item))
    elif problem == "duplicate_baseline":
        rows.append(copy.deepcopy(rows[0]))
    elif problem == "existing_date":
        rows[0]["release_date"] = "2020-01-01"
    elif problem == "failed_latest":
        item["nextVerification"] = {"status": "failed"}
    elif problem == "after_cutoff":
        item["verification"]["verifiedDate"] = "2026-09-08"
    elif problem == "invalid_date":
        item["verification"]["verifiedDate"] = "2025-02-30"
    elif problem == "precision_mismatch":
        item["verification"]["precision"] = "month"
    elif problem == "missing_source":
        item["verification"]["sourceChecks"] = []
    with pytest.raises(ValueError):
        enrich(rows, reviewed, "2026-09-07")
