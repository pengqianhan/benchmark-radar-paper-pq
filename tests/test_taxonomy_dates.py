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
from supplement_taxonomy_dates import (  # noqa: E402
    BASE,
    LEGACY,
    SELECTION,
    build,
    check,
    combine_matches,
    enrich,
    validate_legacy_date,
)


def test_enrichment_preserves_full_population_and_all_non_date_fields():
    baseline = [json.loads(line) for line in BASE.read_text().splitlines()]
    enriched, manifest = build()
    assert [row["key"] for row in enriched] == [row["key"] for row in baseline]
    assert (manifest["population"], manifest["baseline_dated"], manifest["baseline_undated"],
            manifest["supplemented"], manifest["dated"], manifest["undated"]) == (
                1283, 615, 668, 453, 1068, 215)
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
    assert changed == 453
    check()


def test_combination_adds_exactly_selected_16_and_preserves_all_437_library_dates():
    _, manifest = build()
    combined = {r["catalogKey"]: r for r in manifest["matching_records"]}
    library = {r["catalogKey"]: r for r in build_matches()["records"]}
    legacy = {r["verification"]["catalogKey"]: r for r in json.loads(LEGACY.read_text())}
    selected = set(json.loads(SELECTION.read_text())["catalog_keys"])
    assert set(combined) == set(library)
    assert len(selected) == 16
    assert manifest["date_source_counts"] == {"library": 437, "legacy_next_verification": 16}
    assert manifest["matching_decisions"] == {
        "accepted": 453, "scope_not_release": 187, "identity_unresolved": 1, "unmatched": 27}
    assert manifest["precision_counts"] == {"day": 437, "month": 16}
    for key, row in combined.items():
        if key in selected:
            review = legacy[key]["nextVerification"]
            assert row["release_date"] == review["releaseDate"]
            assert row["nextVerification"] == review
            assert row["date_field"] == "nextVerification.releaseDate"
            assert row["sources"] == review["sources"]
            assert library[key]["decision"] != "accepted"
        else:
            assert row["release_date"] == library[key]["release_date"]
            assert row["decision"] == library[key]["decision"]
    assert combined["llm-stats:global-mmlu-lite"]["release_date"] == "2024-12"
    assert combined["llm-stats:groundui-1k"]["release_date"] == "2024-10-02"
    assert combined["model-reports:harbor_index"]["event"] == "harbor_index_1_0_launch"
    assert combined["artificial-analysis:tau3-banking"]["release_date"] is None


def legacy_fixture():
    return {"date": "2000-01-01", "verification": {"catalogKey": "llm-stats:a"},
            "nextVerification": {"status": "passed", "releaseDate": "2025-02",
                                 "precision": "month", "event": "version_release",
                                 "reason": "Version release history establishes the month.",
                                 "sources": [{"url": "https://example.org/releases"}]}}


@pytest.mark.parametrize("problem", ["failed", "missing_field", "placeholder", "invalid_day",
                                    "precision_mismatch", "after_cutoff", "straddling_month",
                                    "missing_event", "missing_source"])
def test_legacy_review_must_have_valid_passed_event_and_exact_date_field(problem):
    donor = legacy_fixture()
    v = donor["nextVerification"]
    if problem == "failed":
        v["status"] = "failed"
    elif problem == "missing_field":
        v.pop("releaseDate")
        v["verifiedDate"] = "2025-02"  # Neither this nor top-level date is a fallback.
    elif problem == "placeholder":
        v.update(releaseDate="0001-01-01", precision="day")
    elif problem == "invalid_day":
        v.update(releaseDate="2025-02-30", precision="day")
    elif problem == "precision_mismatch":
        v["precision"] = "day"
    elif problem == "after_cutoff":
        v.update(releaseDate="2026-09-08", precision="day")
    elif problem == "straddling_month":
        v["releaseDate"] = "2026-09"
    elif problem == "missing_event":
        v.pop("event")
    elif problem == "missing_source":
        v["sources"] = []
    with pytest.raises(ValueError):
        validate_legacy_date(donor, "2026-09-07")


def test_legacy_join_requires_exact_selected_keys_and_cannot_overwrite_library():
    census, snapshot, reviews = fixtures()
    matches = match(census, snapshot, reviews, [])
    donor = legacy_fixture()
    key = "llm-stats:a"
    with pytest.raises(ValueError, match="must not replace"):
        combine_matches(matches, [donor], [key], census["discovery_cutoff"])
    matches[0].update(decision="scope_not_release", release_date=None)
    for donors, selected in [([donor], [key, key]), ([donor, donor], [key]),
                             ([donor], ["other:a"])]:
        with pytest.raises(ValueError):
            combine_matches(matches, donors, selected, census["discovery_cutoff"])
    assert combine_matches(matches, [donor], [], census["discovery_cutoff"])[0]["release_date"] is None
    result = combine_matches(matches, [donor], [key], census["discovery_cutoff"])
    assert result[0]["release_date"] == "2025-02"
    assert result[0]["library_candidate_date"] == "2025-01-15"
    tampered = copy.deepcopy(result)
    tampered[0]["release_date"] = donor["date"]
    with pytest.raises(ValueError, match="selected evidence field"):
        enrich(census["records"], tampered)


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
