"""The upstream Figure 6 submission must use only frozen v0.11.0 release dates."""

import json
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
from plot_taxonomy_frozen import (  # noqa: E402
    FROZEN_DATED, FROZEN_UNDATED, OUT, UPSTREAM_MACROS, load_rows, year_series,
)


def test_frozen_figure_uses_the_census_dates_only():
    rows = load_rows()
    trends = year_series(rows)
    census = json.loads((PAPER / "evidence/catalog-findings.json").read_text())["records"]
    assert trends["population"] == len(census) == 1283
    assert (trends["dated"], trends["undated"]) == (FROZEN_DATED, FROZEN_UNDATED)
    catalog = (PAPER / "catalog-data.tex").read_text()
    assert f"\\newcommand{{\\CensusReleaseKnown}}{{{FROZEN_DATED}}}" in catalog
    assert sum(trends["per_year"].values()) == trends["dated"]
    assert sum(trends["undated_by_l1"].values()) == trends["undated"]


def test_frozen_figure_keeps_the_upstream_macros():
    assert year_series(load_rows())["macros"] == UPSTREAM_MACROS


def test_frozen_figure_rebuilds_and_matches_the_committed_one(tmp_path):
    builds = []
    for name in ("first.pdf", "second.pdf"):
        out = tmp_path / name
        subprocess.run([sys.executable, str(PAPER / "scripts/plot_taxonomy_frozen.py"),
                        "--check", "--out", str(out)], check=True, cwd=PAPER, capture_output=True)
        builds.append(out)
    # Deterministic in one environment; font subsetting may differ across them,
    # so the committed file is held to the rebuild by its drawn text.
    assert builds[0].read_bytes() == builds[1].read_bytes()
    from pypdf import PdfReader

    def text(path):
        return "\n".join(page.extract_text() for page in PdfReader(path).pages)

    committed = text(OUT)
    assert committed == text(builds[0])
    assert "668" in committed and "no release" in committed and "own scale" not in committed
