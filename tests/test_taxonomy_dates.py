"""Date joins must preserve identities, event scope, precision and the census."""

import copy
import json
import sys
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
from match_library_dates import (  # noqa: E402
    CENSUS,
    SNAPSHOT,
    canonical_hash,
    match,
    normalized_name,
    validate_evidence,
)
from match_library_dates import (  # noqa: E402
    build as build_matches,
)
from supplement_taxonomy_dates import BASE, build, check, enrich  # noqa: E402


def test_enrichment_preserves_full_population_and_all_non_date_fields():
    baseline = [json.loads(line) for line in BASE.read_text().splitlines()]
    enriched, manifest = build()
    assert [row["key"] for row in enriched] == [row["key"] for row in baseline]
    assert (manifest["population"], manifest["baseline_dated"], manifest["baseline_undated"],
            manifest["supplemented"], manifest["dated"], manifest["undated"]) == (
                1283, 615, 668, 437, 1052, 231)
    changed = 0
    for original, result in zip(baseline, enriched):
        if result == original:
            continue
        changed += 1
        assert original["release_date"] is None
        restored = dict(result)
        restored.pop("release_date_evidence")
        restored["release_date"] = None
        assert restored == original
    assert changed == 437
    check()


def test_audit_has_all_668_original_missing_records_and_reconciles_every_source():
    census = json.loads(CENSUS.read_text())
    audit = build_matches()
    assert {row["catalogKey"] for row in audit["records"]} == {
        row["key"] for row in census["records"] if row["release_date"] is None}
    assert audit["source_id_matching"] == {"unique": 619, "multiple": 2, "none": 47}
    assert audit["decisions"] == {
        "accepted": 437, "scope_not_release": 202, "identity_unresolved": 2, "unmatched": 27}
    for source, summary in audit["per_source"].items():
        assert sum(summary.values()) == sum(r["source"] == source for r in audit["records"])
    snapshot = json.loads(SNAPSHOT.read_text())
    assert len(snapshot["records"]) == snapshot["selected_count"] == 1107
    donors = {r["id"]: r for r in snapshot["records"]}
    for row in audit["records"]:
        if row["decision"] == "accepted":
            assert row["release_date"] == donors[row["libraryId"]]["releaseEvidence"]["date"]
        else:
            assert row["release_date"] is None


def test_known_identity_and_event_conflicts_are_not_silent_date_transfers():
    entries = {r["catalogKey"]: r for r in build_matches()["records"]}
    assert entries["llm-stats:humaneval+"]["release_date"] == "2023-05-02"
    assert entries["llm-stats:mbpp+"]["release_date"] == "2023-11-24"
    assert normalized_name("HumanEval+") != normalized_name("HumanEval")
    assert entries["llm-stats:air-bench"]["release_date"] is None
    assert entries["llm-stats:surds"]["release_date"] is None
    assert entries["llm-stats:mega-mlqa"]["release_date"] is None
    assert entries["llm-stats:global-mmlu-lite"]["release_date"] is None
    assert entries["llm-stats:aime"]["libraryName"] == "AIME 2024"
    assert entries["llm-stats:aime"]["release_date"] is None
    assert entries["model-reports:harbor_index"]["release_date"] is None
    assert entries["llm-stats:beyond-aime"]["release_date"] == "2025-06-17"
    assert entries["llm-stats:beyond-aime"]["legacy"]["date"] == "2025-04-14"
    assert entries["llm-stats:beyond-aime"]["event"] == "dataset_release"
    assert entries["llm-stats:swe-atlas-codebase-qna"]["decision"] == "accepted"
    assert entries["llm-stats:mm-clawbench"]["event"] == "private_benchmark_public_introduction"
    # Linked entities do not collapse the paper's separate source records.
    assert entries["llm-stats:arxivmath"]["libraryId"] == entries["model-reports:arxivmath"]["libraryId"]
    month = entries["llm-stats:frontier-swe-impl"]
    assert month["precision"] == "month" and month["release_date"] == "2026-04"


def fixtures():
    donor = {"id": "lib_a", "name": "A", "aliases": [],
             "catalogSources": [{"catalog": "llm-stats", "sourceId": "a"}],
             "releaseEvidence": {"id": "lib_a", "date": "2025-01-15", "precision": "day",
                                 "sourceUrl": "https://example.org/a", "basis": "paper-v1"}}
    census = {"records": [{"key": "llm-stats:a", "name": "A", "source": "llm_stats",
                            "release_date": None}], "discovery_cutoff": "2026-09-07"}
    snapshot = {"records": [donor], "selected_count": 1}
    reviews = {"records": [], "snapshot_sha256": canonical_hash(snapshot),
               "census_sha256": canonical_hash(census)}
    return census, snapshot, reviews


def test_names_retrieve_candidates_but_never_authorize_a_join():
    census, snapshot, reviews = fixtures()
    snapshot["records"][0]["catalogSources"] = []
    reviews["snapshot_sha256"] = canonical_hash(snapshot)
    result = match(census, snapshot, reviews, [])
    assert result[0]["decision"] == "identity_unresolved"
    assert result[0]["release_date"] is None


@pytest.mark.parametrize("scope", ["underlying-dataset", "public-disclosure"])
def test_scoped_evidence_requires_explicit_applicability_review(scope):
    census, snapshot, reviews = fixtures()
    snapshot["records"][0]["releaseEvidence"]["dateScope"] = scope
    reviews["snapshot_sha256"] = canonical_hash(snapshot)
    assert match(census, snapshot, reviews, [])[0]["decision"] == "scope_not_release"


def test_ambiguous_exact_ids_require_explicit_identity_review():
    census, snapshot, reviews = fixtures()
    other = copy.deepcopy(snapshot["records"][0])
    other["id"] = other["releaseEvidence"]["id"] = "lib_b"
    snapshot["records"].append(other)
    snapshot["selected_count"] = 2
    reviews["snapshot_sha256"] = canonical_hash(snapshot)
    assert match(census, snapshot, reviews, [])[0]["decision"] == "identity_unresolved"


@pytest.mark.parametrize("value,precision", [("0001-01-01", "day"), ("2025-02-30", "day"),
                                            ("2025-02", "day"), ("2025-02-01", "month")])
def test_placeholder_or_malformed_date_cannot_pass(value, precision):
    _, snapshot, _ = fixtures()
    donor = snapshot["records"][0]
    donor["releaseEvidence"].update(date=value, precision=precision)
    with pytest.raises(ValueError):
        validate_evidence(donor, "2026-09-07")


@pytest.mark.parametrize("value,precision", [("2026-09-08", "day"), ("2026-09", "month")])
def test_post_cutoff_or_straddling_month_is_not_applied(value, precision):
    census, snapshot, reviews = fixtures()
    snapshot["records"][0]["releaseEvidence"].update(date=value, precision=precision)
    reviews["snapshot_sha256"] = canonical_hash(snapshot)
    result = match(census, snapshot, reviews, [])[0]
    assert result["decision"] == "after_cutoff" and result["release_date"] is None


@pytest.mark.parametrize("problem", ["duplicate_baseline", "duplicate_donor", "missing_source",
                                    "changed_snapshot", "changed_census", "review_of_dated_record"])
def test_invalid_or_stale_inputs_fail_visibly(problem):
    census, snapshot, reviews = fixtures()
    if problem == "duplicate_baseline":
        census["records"].append(copy.deepcopy(census["records"][0]))
    elif problem == "duplicate_donor":
        snapshot["records"].append(copy.deepcopy(snapshot["records"][0]))
        snapshot["selected_count"] = 2
    elif problem == "missing_source":
        snapshot["records"][0]["releaseEvidence"].pop("sourceUrl")
    elif problem == "changed_snapshot":
        snapshot["records"][0]["releaseEvidence"]["date"] = "2025-02-01"
    elif problem == "changed_census":
        census["records"][0]["name"] = "Different version"
    elif problem == "review_of_dated_record":
        census["records"][0]["release_date"] = "2020-01-01"
        reviews["records"] = [{"catalogKey": "llm-stats:a"}]
    if problem not in {"changed_snapshot", "changed_census"}:
        reviews.update(snapshot_sha256=canonical_hash(snapshot), census_sha256=canonical_hash(census))
    with pytest.raises(ValueError):
        match(census, snapshot, reviews, [])


@pytest.mark.parametrize("problem", ["missing_row", "duplicate_row", "known_date", "changed_donor_date",
                                    "date_on_rejected_row"])
def test_enrichment_cannot_drop_records_or_override_evidence(problem):
    census, snapshot, reviews = fixtures()
    matches = match(census, snapshot, reviews, [])
    rows = census["records"]
    if problem == "missing_row":
        matches = []
    elif problem == "duplicate_row":
        matches.append(copy.deepcopy(matches[0]))
    elif problem == "known_date":
        rows[0]["release_date"] = "2020-01-01"
    elif problem == "changed_donor_date":
        matches[0]["release_date"] = "2025-01-16"
    elif problem == "date_on_rejected_row":
        matches[0]["decision"] = "scope_not_release"
    with pytest.raises(ValueError):
        enrich(rows, matches)
