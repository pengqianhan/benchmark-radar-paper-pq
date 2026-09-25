# Paper repository instructions

- Keep paper-only edits and PRs in this repository by default. Update the parent
  Benchmark Radar repository, including its submodule pointer, only when the user
  explicitly requests it.
- Keep work on the task branch. Update local or remote `main`, or merge a pull
  request, only when the user explicitly requests it. Creating or updating a PR
  does not authorize a merge.
- Follow the README's v0.11.0 data cutoff rule: software commit
  `8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`, discovery through 2026-09-07,
  and the recorded input hashes. Preserve these released inputs during routine
  edits. Publishing unchanged audited inputs does not require a new audit; a
  changed cutoff requires an explicitly agreed new paper version.
- Edit `main.tex` directly; it is the single source of manuscript prose.
- Keep `references.bib`, all required images, native figure sources, and dated
  `figure-data.tex` in this repository so it builds without the software checkout.
- Run `make` after manuscript or figure changes. Visually inspect the resulting
  PDF and commit `main.pdf` plus any rebuilt figure PDFs. Keep the full figure
  sources on `benchmark_class`; upstream Figure 6 PRs follow the minimal-file
  submission rules below.
- Run `make arxiv` and compile the extracted archive before a submission.
- Do not infer current corpus counts from the paper. Before changing quantitative
  claims, run and audit the software repository's six-step clean-checkout CI
  sequence as described in its AGENTS.md and report README. Missing measurements
  must not remove benchmark records; investigate any unexplained loss below the
  full-corpus baseline of 1,259+ records across 4+ sources.
- Refresh `figure-data.tex` only through the software repository's exporter after
  that audit. Cite the software commit, input evidence, and cutoff for new claims.
- The v0.9.0 Zenodo deposit remains frozen in the software repository.
- Preserve author contribution statements, final approval, and accountability.
  Overleaf's Git commit author does not represent all coauthors' contributions.
- Read the README for Overleaf sync and submodule updates. When a parent pointer
  update is requested, push the paper commit before advancing that pointer.
  Do not add submodules or symlinks here: this repository must be importable by
  Overleaf.
- Merge pull requests with a merge commit; never squash-merge.

## Minimal Figure 6 submissions

- Keep the complete work for `figures/taxonomy-trends.pdf` in
  `pengqianhan/benchmark-radar-paper-pq` on `benchmark_class`: plotting code,
  evidence, generated data, audits, fonts, dependencies, tests, and documentation.
  This development branch is not the branch to submit wholesale to upstream.
- Before every upstream submission, including each update to an existing PR,
  pull the latest upstream `main` state with `git fetch upstream main`, where
  `upstream` is `https://github.com/ktwu01/benchmark-radar-paper.git`. Prepare or
  refresh a separate submission branch from that latest `upstream/main`, then
  apply only the necessary Figure 6 changes. If upstream advances before the
  next submission, refresh the base and rebuild again. Do not use a stale local
  `main` or the full `benchmark_class` history as the submission base.
- Choose the submission scope by comparing the new figure with the manuscript
  on the latest upstream `main`:
  1. **Figure presentation only; no prose change needed:** leave `main.tex`
     byte-for-byte unchanged. Submit exactly `figures/taxonomy-trends.pdf` and
     the newly compiled `main.pdf`.
  2. **The new figure requires corresponding prose changes:** make only the
     necessary edits to its explanation, caption, or directly affected claims
     in `main.tex`. Submit exactly `main.tex`, `main.pdf`, and
     `figures/taxonomy-trends.pdf`.
- Minimize the diff. Preserve all unrelated prose, author information,
  contributions, references, figures, formatting, and build configuration.
  Do not include plotting scripts, evidence, generated TeX/data files, fonts,
  dependencies, tests, documentation, or this `AGENTS.md` in the upstream
  Figure 6 PR. These remain on the fork's `benchmark_class` branch.
- Compile `main.pdf` from the actual submission branch with the new figure and
  its own `main.tex`; do not copy a manuscript PDF built from the development
  branch's older manuscript. The submission must build with upstream's existing
  assets and only the two or three submitted files, without depending on
  additional files from `benchmark_class`.
- Complete the required frozen-data checks, regression tests, `make`, visual
  review, and submission-package checks described in this file before pushing.
  The minimal file scope does not waive evidence verification or change the
  frozen cutoff.
- Before committing and pushing, inspect the **entire PR diff against the latest
  upstream `main`**, not just the last commit. It must contain exactly the two
  or three files for the selected case. Verify the same file list on GitHub
  after pushing, and keep the PR description consistent with that scope.

## Full-catalog findings

- Read the software repository's `principle.md` before revising benchmark claims.
  Start from every source record in a cleanly rebuilt shared catalog.
- Use `scripts/audit_catalog.py` to refresh `catalog-data.tex` and
  `evidence/catalog-audit.json`; its `--check` mode must pass against that rebuild.
  Refresh `figure-data.tex` only with the software exporter as described above.
- A statistic may require a score, scale, date, or protocol. State its eligible
  coverage and keep records with missing measurements in the population census.
  Do not substitute a model-report-only audit for the paper's main findings.
- Distinct scored models, numeric observations, and cited documents are different
  units. Preserve source-record identities; do not sum similarly named records.
- Keep one mark per source record in the corpus overview and preserve its detail
  link when building the manuscript. Check the links against the census IDs.
- Main document, score, and date analyses use `scripts/audit_findings.py` and
  `findings-data.tex`. Each retains the exact full frozen catalog ID set; a
  measurement eligibility filter must not become a population filter.
- Run `audit_findings.py /path/to/frozen-software --check` and the paper's
  regression tests before building. Never reinstate model-report-only main
  findings or substitute document counts for benchmark-record coverage.
- Every number below 100 appearing in the rendered paper must produce this
  warning: `less than 100 is abnormal, ref to https://github.com/ktwu01/benchmark-radar/blob/main/principle.md`.
  Apply it without exemptions for page numbers, citations, dates, model versions,
  percentages, or source-specific counts. `make` and `make arxiv` run the check
  on PDF text and OCR of rendered pages. Review the page/context warnings;
  do not change frozen evidence merely to silence them.
- Do not restore `example-data.tex`, `scripts/audit_examples.py`, or
  `evidence/restored-examples.json`. Git history preserves the removed subset;
  `findings-data.tex` and the full-catalog exports are the current analysis.
