# Build the manuscript and native TikZ figures from dated TeX inputs.
LATEXMK ?= latexmk
PYTHON ?= python3
FIGURE_NAMES := corpus-evidence cover-metrics pipeline-evaluation search-surface source-composition
FIGURE_PDFS := $(addprefix figures/,$(addsuffix .pdf,$(FIGURE_NAMES)))
FIGURE_SOURCES := $(addprefix figures/,$(addsuffix .tex,$(FIGURE_NAMES)))
# Drawn by matplotlib from the frozen classification, not by latexmk.
TAXONOMY_FIGURES := figures/taxonomy-sankey.pdf figures/taxonomy-trends.pdf
TAXONOMY_INPUTS := scripts/taxonomy.py scripts/classify_benchmarks.py \
	scripts/match_library_dates.py evidence/library-reviewed-dates.json \
	evidence/library-date-match-reviews.json \
	evidence/release-date-legacy-selection.json \
	scripts/supplement_taxonomy_dates.py scripts/taxonomy_trends.py scripts/plot_taxonomy.py \
	evidence/156_from_xiaoke_all_passed_en.json \
	evidence/catalog-findings.json $(wildcard evidence/taxonomy-inputs/*) \
	$(wildcard assets/fonts/liberation-sans/*)
TAXONOMY_OUTPUTS := $(TAXONOMY_FIGURES) taxonomy-data.tex taxonomy-trend-data.tex \
	evidence/benchmark-taxonomy.jsonl evidence/benchmark-taxonomy-summary.json \
	evidence/benchmark-taxonomy-dated.jsonl evidence/taxonomy-release-date-supplements.json \
	evidence/library-date-matches.json evidence/library-date-matches.csv \
	evidence/release-date-matches.json evidence/release-date-matches.csv \
	evidence/benchmark-taxonomy-trends.json

.PHONY: all figures taxonomy-figures reproduce-taxonomy check-taxonomy arxiv check-small-numbers clean

all: check-small-numbers

figures: $(FIGURE_PDFS) $(TAXONOMY_FIGURES)

# One shared phony recipe also works with parallel make and missing outputs.
# Always rebuild from evidence, including when checked-in PDFs already exist.
taxonomy-figures: $(TAXONOMY_INPUTS)
	$(PYTHON) scripts/classify_benchmarks.py
	$(PYTHON) scripts/match_library_dates.py
	$(PYTHON) scripts/supplement_taxonomy_dates.py
	$(PYTHON) scripts/taxonomy_trends.py
	$(PYTHON) scripts/plot_taxonomy.py

reproduce-taxonomy: taxonomy-figures

check-taxonomy:
	$(PYTHON) scripts/check_taxonomy_reproduction.py

$(TAXONOMY_OUTPUTS): taxonomy-figures
	@test -f $@

figures/%.pdf: figures/%.tex figures/figure-style.tex figure-data.tex catalog-data.tex Makefile
	cd figures && $(LATEXMK) -g -pdf -interaction=nonstopmode -halt-on-error $*.tex

figures/corpus-evidence.pdf: figures/corpus-evidence-body.tex

main.pdf: main.tex references.bib figure-data.tex catalog-data.tex findings-data.tex taxonomy-data.tex taxonomy-trend-data.tex figures/corpus-evidence-body.tex $(FIGURE_PDFS) $(TAXONOMY_FIGURES) $(wildcard figures/*.png) Makefile
	$(LATEXMK) -g -pdf -interaction=nonstopmode -halt-on-error main.tex

# Scan rendered text and raster figures on every normal build, even if the PDF
# is up to date. Small numbers warn; unreadable inputs or missing tools fail.
check-small-numbers: main.pdf
	mkdir -p build
	$(PYTHON) scripts/check_small_numbers.py main.pdf --json-output build/small-number-warnings.json

# arXiv runs no BibTeX pass. Ship main.bbl, the dated numbers, native drawings,
# and finished figures. All paper assets live in this repository.
arxiv: check-small-numbers
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error main.tex
	rm -rf build/arxiv
	mkdir -p build/arxiv/figures
	cp main.tex main.bbl figure-data.tex catalog-data.tex findings-data.tex taxonomy-data.tex taxonomy-trend-data.tex build/arxiv/
	cp $(FIGURE_PDFS) $(TAXONOMY_FIGURES) $(FIGURE_SOURCES) figures/figure-style.tex figures/corpus-evidence-body.tex figures/*.png build/arxiv/figures/
	tar -czf arxiv.tar.gz -C build/arxiv .

# Keep tracked PDFs; remove only intermediates and the upload staging area.
clean:
	$(LATEXMK) -c main.tex
	cd figures && $(LATEXMK) -c $(addsuffix .tex,$(FIGURE_NAMES))
	rm -rf build arxiv.tar.gz
