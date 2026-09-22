# Benchmark Radar paper

[Read the paper](main.pdf) · [Edit the LaTeX](main.tex) · [Benchmark Radar](https://github.com/ktwu01/benchmark-radar)

**Benchmark RADAR: Living Search Engine for Retrieval and Discovery of AI Benchmark Research** describes how researchers can discover evaluations, retrieve candidates, and inspect their task materials and reported scores. Its document, score, and date analyses each retain the complete frozen benchmark catalog.

This repository contains the manuscript, bibliography, dated figure inputs, and all images needed to build the paper independently. The software repository pins a reviewed commit here as its `docs/technical-report/latex` submodule.

## Data cutoff rule: v0.11.0

**All data used in this paper is cut off at the
[Benchmark Radar v0.11.0 release](https://github.com/ktwu01/benchmark-radar/releases/tag/v0.11.0)**,
which pins software commit
[`8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`](https://github.com/ktwu01/benchmark-radar/commit/8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0).
The discovery cutoff remains **2026-09-07**; registry snapshots retain their
recorded collection dates.

This rule covers discovery snapshots, registry inputs, model reports, scores,
tables, and figures. Routine paper edits must preserve the released inputs and
the hashes in `figure-data.tex`. Do not refresh from later data, current `main`,
or the live website. Changing the cutoff requires an explicitly agreed new
paper version.

The release preserves the inputs already audited for this paper. Publishing
those unchanged inputs does not require repeating the audit. A correction that
changes inputs or quantitative claims requires verification of the affected
claims. Rebuild and inspect the PDF after manuscript or figure edits.

The release includes
[`benchmark-radar-paper-data-v0.11.0.zip`](https://github.com/ktwu01/benchmark-radar/releases/download/v0.11.0/benchmark-radar-paper-data-v0.11.0.zip),
containing the catalog index, detail shards, model registry, discovery JSON, and
dated snapshots used by the audit. `SHA256SUMS` verifies the release assets;
`release-data.json` inside the archive records the commit and individual input
hashes. These fixed assets, rather than the rolling `cli-data` release, are the
paper's data reference.

```text
site/data/radar.json SHA-256: 029dc413770f39cad1fcd1c3ec2abeeea214544e3c909e2772b1fe2d9c52c4b9
site/data/benchmark-index.json SHA-256: b8d10892e25fe0fe63856f31e1645b41ee7d0f277fedaf308bd8f707852dbff2
```

## Write together in Overleaf

The project owner links their GitHub account in Overleaf account settings, then
chooses **New project → GitHub repo → ktwu01/benchmark-radar-paper**. Set
`main.tex` as the main document and use pdfLaTeX. Invite coauthors through Share.
UT Austin's eligible institutional premium accounts include GitHub integration.

Use **Integrations → GitHub** to pull accepted GitHub changes before a writing
session and push completed revisions afterward. This is manual synchronization;
saving in Overleaf does not push to GitHub. GitHub sync uses the default branch,
so review the manuscript in Overleaf before pushing. It does not open a PR.

Finish active comment and tracked-change review before pulling GitHub edits:
Git synchronization can displace those annotations. Overleaf may bundle several
authors' changes into a commit under the connected account; retain contribution
statements and review records for author credit.

After syncing, rebuild and inspect `main.pdf`, then commit and push it here.
Keep paper-only work in this repository by default. Update Benchmark Radar's
submodule pointer through a separate PR only when the user explicitly requests
it. A paper push alone does not change the version pinned by the software repository.

See [Overleaf's GitHub sync documentation](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/github-synchronization).

## Build locally

Install a TeX distribution with `latexmk`, pdfLaTeX, TikZ, and the manuscript's
LaTeX packages (TeX Live or TinyTeX), plus Python 3, Poppler (`pdftotext` and
`pdftoppm`), and Tesseract OCR. From this repository's root:

```bash
make
make arxiv
```

`make` builds the native TikZ figures and `main.pdf`. Commit the rebuilt PDF with
manuscript edits. Inspect the cover, changed pages, figures, and references before
committing. Overleaf compiles the manuscript using the checked-in figure PDFs;
after editing a figure's `.tex` source, rebuild it locally and sync its PDF too.

Every `make` or `make arxiv` scans the rendered PDF text and page images. Each
detected number below 100 prints:

```text
less than 100 is abnormal, ref to https://github.com/ktwu01/benchmark-radar/blob/main/principle.md
```

Warnings include the page, value, extraction method, and surrounding text.
Page numbers, citations, dates, percentages, model versions, and individual
source counts are included. Warnings do not rewrite evidence or fail the build;
missing tools and unreadable PDFs do. OCR can misread or miss small image text,
so inspect the flagged pages as part of visual review. The full warning report
is written to `build/small-number-warnings.json` and uploaded by CI. Run
`python scripts/check_small_numbers.py main.pdf --text-only` only for an explicit
partial scan; it warns that image coverage is incomplete.

`make arxiv` writes `arxiv.tar.gz`, including `main.bbl` and all figure inputs.
Unpack and compile that archive independently before submitting it. The archive
is a submission package, not evidence of an arXiv publication.

CI builds the manuscript and submission package and uploads them as artifacts.
Those artifacts do not update the checked-in `main.pdf` automatically.

## Reproduce the taxonomy figures

For the detailed production and maintenance workflow, including data provenance,
date verification rules, plotting parameters and validation, see
[scripts/README.md](scripts/README.md) (Chinese).

The complete pipeline runs locally from committed evidence; no live website,
software checkout, or manual PDF editing is required. With Python 3.11:

```bash
python3 -m venv build/figure-venv
build/figure-venv/bin/python -m pip install -r requirements-figures.txt
make reproduce-taxonomy PYTHON=build/figure-venv/bin/python
make check-taxonomy PYTHON=build/figure-venv/bin/python
```

`make reproduce-taxonomy` regenerates both taxonomy PDFs and their intermediate
evidence, even when the PDFs already exist. The stages are:

1. `scripts/classify_benchmarks.py` classifies every frozen source record using
   `evidence/catalog-findings.json` and the vendored `evidence/taxonomy-inputs/`.
2. `scripts/match_library_dates.py` matches the **original 668 undated records**
   against the fixed **1,107-record** `evidence/library-reviewed-dates.json`.
   It writes a complete JSON/CSV audit, using exact source IDs or explicit
   identity reviews and checking whether each date applies to the named version.
3. `scripts/supplement_taxonomy_dates.py` keeps the accepted Library matches and
   adds the 16 explicitly selected, passed `nextVerification.releaseDate` values
   from the earlier verification file. It writes the combined 668-record
   `evidence/release-date-matches.json` / `.csv` audit, the full drawing input
   `evidence/benchmark-taxonomy-dated.jsonl`, and the source-linked manifest
   `evidence/taxonomy-release-date-supplements.json`.
4. `scripts/taxonomy_trends.py` recomputes eligible periods and selected series in
   `evidence/benchmark-taxonomy-trends.json`, and exports `taxonomy-trend-data.tex`.
5. `scripts/plot_taxonomy.py` draws both taxonomy PDFs from that complete population.

The reviewed snapshot is extracted from the supplied local `library_index.json`
(SHA-256 `e95cb671b15d3bd89d9abe44cb0ebd42c278a6609288d0eae6904ca1e219c99d`).
It contains all records with `releaseEvidence`, preserving their complete date
evidence, identity fields, input positions and original record hashes. Builds
use this committed snapshot, require no live Library access, and never import
new records from it. The contributor's date verification is distinguished from
this paper's subsequent identity and event-scope review.

**453 dates are adopted: 437 from Library evidence + 16 from passed legacy
reviews. The full population has 615 originally dated + 453 = 1,068 dated,
leaving 215 undated.** Of those remaining, 187 have candidate dates that do not
establish the target's release/introduction, 1 has unresolved identity/version
issues, and 27 have no match in the reviewed snapshot. Source IDs alone are insufficient
when evidence only dates a parent dataset or a later result disclosure.
Explicit component-introduction evidence can support a component's date without
counting it as an independent benchmark-family release.

The first-stage Library matching remains unchanged and auditable separately.
It supplies dates for 140 records in the previous 156-record annotation and
297 additional records. The second stage uses the explicit allowlist in
`evidence/release-date-legacy-selection.json` for the other 16 records, joined by
`verification.catalogKey`. All 16 require `nextVerification.status: passed`,
and use only `nextVerification.releaseDate`, preserving its precision, event and
sources. No accepted Library date is overwritten; the top-level legacy `date`
is never a fallback. The selection binds the donor, Library audit and census
hashes. See the [combined report](evidence/release-date-matching.md) and
[complete current audit table](evidence/release-date-matches.csv).

This is a retrospective annotation of the existing v0.11.0 population with the
same 2026-09-07 discovery cutoff. All 1,283 source records, the original census
(615 dated / 668 undated), classifications, scores and released hashes remain
unchanged. Review dates can follow the cutoff; accepted benchmark dates cannot.

Figure 6 Panel A focuses on dates from 2023: it shows 936 dated records and
215 undated records, with legend counts covering those 1,151 shown records.
The 132 earlier dated records are omitted from this view because historical
coverage is incomplete; they remain in the census, input data and audit.
The trends JSON records this display scope in `panel_a`. Panel B's data,
denominators, source-composition reference and selection rules are unchanged.

`make check-taxonomy` runs two fresh, isolated builds with different hash seeds,
time zones and caller timestamps. All thirteen artifacts must be byte-identical
between runs; generated JSON/JSONL/CSV/TeX must also match the checked-in files.
It records hashes and environment versions in
`build/taxonomy-reproduction-check.json`. PDF metadata use the discovery cutoff
as a deterministic timestamp (not the annotation or build date), and the figures
use the vendored Liberation Sans regular/italic fonts in
`assets/fonts/liberation-sans/`, matching the paper's Helvetica-style figures
without depending on system fonts. Labels and titles use normal weight. PDF
bytes may differ across library versions/platforms; repeat the byte comparison within one environment. The
statistics and input hashes remain directly checkable across environments.
After rebuilding figures, run `make PYTHON=build/figure-venv/bin/python` to update
and scan `main.pdf`.

## Reproduce the paper's numbers

`figure-data.tex` is generated by the **Benchmark Radar software repository**.
Reproduction is optional; normal paper builds use the committed TeX inputs.
To reproduce from source, use a separate clean software checkout at the release
commit above and run the six-step CI sequence in its
[repository instructions](https://github.com/ktwu01/benchmark-radar/blob/v0.11.0/AGENTS.md#before-opening-a-pull-request).
Then run these commands from that software checkout's root:

```bash
git submodule update --init --recursive
git -C docs/technical-report/latex switch -c paper/reproduce-v0.11.0
python scripts/export_report_figure_data.py
python scripts/export_report_figure_data.py --check
```

The exporter reads `site/data/benchmark-index.json` and `site/data/radar.json`
and writes this repository's `figure-data.tex` through the submodule. Its header
records the input SHA-256 hashes; `--check` verifies the complete export against
those local inputs. Do not edit the numbers or hashes by hand.

The paper's full-catalog census uses those same rebuilt records. After copying
the software-generated `figure-data.tex` into this paper checkout, run from the
paper root:

```bash
python scripts/audit_catalog.py /path/to/benchmark-radar
python scripts/audit_catalog.py /path/to/benchmark-radar --check
python scripts/audit_findings.py /path/to/benchmark-radar
python scripts/audit_findings.py /path/to/benchmark-radar --check
make arxiv
```

The script reads the complete index, all its detail shards, the shared model
and document registries, and discovery snapshots. It writes `catalog-data.tex`
and `evidence/catalog-audit.json`, with one audit row per source record and
SHA-256 hashes of its inputs. It checks record IDs, observation uniqueness,
model and document counts, and scored/unscored reconciliation. Missing or
malformed artifacts fail visibly. It preserves source identities and applies
the same measurement rules across sources.

`figures/corpus-evidence-body.tex` draws one linked mark per census record.
The manuscript includes that TikZ source directly so the PDF keeps the links;
`figures/corpus-evidence.pdf` provides a standalone figure. Normal paper builds
use the committed data and require no software checkout.

The v0.11.0 audit uses software commit
[`8f46bbf`](https://github.com/ktwu01/benchmark-radar/commit/8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0)
and a **2026-09-07** discovery cutoff. Registry snapshots retain their August
collection dates. The census has 1,283 source records, including 790 scored and
493 unscored records, with 12,916 numeric observations. Of the unscored records,
464 provide artifact links. These counts preserve separate source records for
related benchmarks; they do not count distinct underlying tests.

Keep the release cutoff fixed and review the prose, figures, and rendered PDF
together. Commit the analysis outputs, figure sources and PDFs, and `main.pdf`
together. Push the reviewed paper commit. Update the parent pointer only when
the user explicitly requests it, using the workflow below. The full-corpus rules in
[principle.md](https://github.com/ktwu01/benchmark-radar/blob/main/principle.md)
apply to paper tables and figures as well as the website.

## Full-catalog findings

`scripts/audit_findings.py` verifies the rebuilt inputs against the frozen census, then exports `findings-data.tex`, `evidence/catalog-findings.json`, and `evidence/catalog-findings.csv`. The JSON and CSV each contain all 1,283 source records. Documentation, reported scores, and dates use the same record IDs across all four sources. Numeric maxima, every tied observation and its settings, document identities, model counts, units, and date evidence stay attached to their source record. Missing measurements remain unknown.

The previous reporting tables restricted the main findings to a report-document subset and eight percentage-headroom examples. The percentage-unit requirement removed 708 scored records from the displayed score analysis. Recomputing that exporter reproduced the small tables without fixing their coverage. The replacement retains all 790 scored records and 493 unscored records, with native score maxima in the complete CSV and JSON. Percentage headroom is an optional field, not an inclusion rule. Document counts never substitute for benchmark-record counts, and source labels never substitute for unknown organization identities.

The cutoff and released input hashes are unchanged. Paper CI checks generated findings against the checksummed v0.11.0 archive before compiling the manuscript. Run `python -m pytest -q tests` for population, missing-evidence, and numeric-warning regression cases. The obsolete `example-data.tex`, its `audit_examples.py` generator, and `evidence/restored-examples.json` have been removed; Git history preserves that earlier subset.

The paper's opening illustration is schematic: its bars and connections are illustrative, ordinal labels have been removed, and its count uses the frozen release. The Results section uses the supplied Humanity’s Last Exam interface snapshot, linked to its interactive view. The full linked census appears in the appendix. A restoration review is recorded in [RESTORATION.md](RESTORATION.md).

## Updating the paper used by Benchmark Radar

Run this workflow only when the user explicitly requests an update to the parent
Benchmark Radar repository or its pinned paper revision. Push the reviewed paper
commit to this repository first. From a clean Benchmark Radar checkout, on a new
branch:

```bash
git submodule update --init --recursive
git -C docs/technical-report/latex fetch origin
git -C docs/technical-report/latex checkout <reviewed-paper-commit>
git add docs/technical-report/latex
git commit -m "Update reviewed paper version"
```

Run Benchmark Radar's required clean-checkout CI sequence before opening the PR.
Merge PRs with a merge commit, never squash. New clones should use
`git clone --recurse-submodules`; existing clones use
`git submodule update --init --recursive` after pulling.

## Evidence and publication

The published [v0.9.0 Zenodo deposit](https://doi.org/10.5281/zenodo.22167102)
remains frozen in the software repository. A new deposit requires a separately
reviewed version; this migration does not change that deposit or its metadata.

## History and license

The LaTeX directory's commit history was extracted from Benchmark Radar at
`7e8ed74`; extraction preserves authors, dates, and messages but changes commit
IDs. The original history remains in the software repository. Use-case images
were copied unchanged from its `assets/use-case-492/` directory.

The paper and original editorial content use [CC BY-NC 4.0](LICENSE-CONTENT.md).
Third-party material retains its original terms.

The image `figures/hle-score-history.png` is the supplied screenshot, preserved byte-for-byte. Its provenance and comparison with the frozen HLE record are recorded in `evidence/hle-score-history.json`. Its 577 scores and displayed maximum of 55.47 agree with the frozen release. The horizontal axis uses model announcement dates, not evaluation dates; the chart does not establish matched protocols or percentage-scale eligibility. The interactive link may show later updates.

The additional supplied `figures/leaderboard-frontier.png` and `figures/discovery-trends.png` snapshots appear in the main Results section and link to their respective interactive pages. `evidence/interface-snapshots.json` preserves both image hashes, scope notes, and the frozen September 7 category counts used to verify the Trends cards. Both original images are kept without cropping or retouching.
