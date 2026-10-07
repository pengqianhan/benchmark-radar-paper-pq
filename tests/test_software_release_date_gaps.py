"""The software-gap record must list exactly the paper-only dates in the figure input."""

import json
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
from audit_software_release_dates import (  # noqa: E402
    CENSUS,
    OUT_JSON,
    ROWS,
    SUPPLEMENTS,
    sha256,
)


def test_gap_record_matches_current_paper_inputs():
    report = json.loads(OUT_JSON.read_text())
    for name, digest in report["paper_input_sha256"].items():
        assert sha256(PAPER / name) == digest, name
    assert report["population"] == len(json.loads(CENSUS.read_text())["records"])
    assert report["comparison"]["different_date"] == 0
    assert report["comparison"]["software_dated_figure_undated"] == 0
    assert sum(report["comparison"].values()) == report["population"]


def test_gap_records_are_exactly_the_supplemented_dates():
    report = json.loads(OUT_JSON.read_text())
    rows = {r["key"]: r for r in map(json.loads, ROWS.read_text().splitlines())}
    supplements = {r["catalogKey"]: r for r in json.loads(SUPPLEMENTS.read_text())["records"]}
    records = report["records"]
    assert [r["catalogKey"] for r in records] == [k for k in rows if k in supplements]
    assert len(records) == report["comparison"]["figure_dated_software_undated"]
    for r in records:
        assert r["release_date"] == rows[r["catalogKey"]]["release_date"]
        assert r["release_date"] == supplements[r["catalogKey"]]["release_date"]
        assert r["software"]["released"] is None
        assert r["event"] and r["precision"] and r["source_urls"] and r["reason"]
