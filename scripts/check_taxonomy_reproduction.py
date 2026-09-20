#!/usr/bin/env python3
"""Rebuild taxonomy artifacts twice in isolation and compare their SHA-256 hashes.

Machine-readable outputs must also match the checked-in evidence. PDF bytes
are compared between runs in the same environment: font/PDF library versions
can affect binary serialization across environments. Neither run uses existing
derived files, the network, or a software checkout.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
SCRIPTS = ("classify_benchmarks.py", "supplement_taxonomy_dates.py",
           "taxonomy_trends.py", "plot_taxonomy.py")
DATA_OUTPUTS = (
    "evidence/benchmark-taxonomy.jsonl", "evidence/benchmark-taxonomy-summary.json",
    "taxonomy-data.tex", "evidence/benchmark-taxonomy-dated.jsonl",
    "evidence/taxonomy-release-date-supplements.json",
    "evidence/benchmark-taxonomy-trends.json", "taxonomy-trend-data.tex",
)
OUTPUTS = (*DATA_OUTPUTS, "figures/taxonomy-sankey.pdf", "figures/taxonomy-trends.pdf")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(root, seed):
    (root / "scripts").mkdir(parents=True)
    (root / "evidence").mkdir()
    for name in (*SCRIPTS, "taxonomy.py"):
        shutil.copyfile(PAPER / "scripts" / name, root / "scripts" / name)
    for name in ("catalog-findings.json", "156_from_xiaoke_all_passed_en.json"):
        shutil.copyfile(PAPER / "evidence" / name, root / "evidence" / name)
    shutil.copytree(PAPER / "evidence/taxonomy-inputs", root / "evidence/taxonomy-inputs")
    shutil.copytree(PAPER / "assets/fonts", root / "assets/fonts")
    env = {**os.environ, "MPLCONFIGDIR": str(root / "mpl-cache"),
           "PYTHONHASHSEED": str(seed), "TZ": "UTC" if seed == 1 else "Pacific/Auckland",
           "SOURCE_DATE_EPOCH": str(seed)}
    for name in SCRIPTS:
        result = subprocess.run([sys.executable, str(root / "scripts" / name)],
                                cwd=root, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"{name}:\n{result.stdout}\n{result.stderr}")
    return {name: digest(root / name) for name in OUTPUTS}


def main():
    with tempfile.TemporaryDirectory(prefix="taxonomy-reproduction-") as directory:
        hashes = [rebuild(Path(directory) / str(seed), seed) for seed in (1, 2)]
    if hashes[0] != hashes[1]:
        raise SystemExit("Rebuilds differ: " + ", ".join(
            name for name in OUTPUTS if hashes[0][name] != hashes[1][name]))
    stale = [name for name in DATA_OUTPUTS
             if not (PAPER / name).exists() or digest(PAPER / name) != hashes[0][name]]
    if stale:
        raise SystemExit("Checked-in data are stale; run make reproduce-taxonomy: " + ", ".join(stale))
    report = {
        "result": "passed",
        "method": "Two fresh builds with different hash seeds, time zones and caller timestamps; all output bytes agree. Machine-readable outputs also match the working tree.",
        "python": sys.version,
        "packages": {name: version(name) for name in
                     ("matplotlib", "numpy", "pypdf", "PyYAML", "fonttools", "pillow")},
        "font_sha256": {str(path.relative_to(PAPER)): digest(path)
                        for path in sorted((PAPER / "assets/fonts").rglob("*.ttf"))},
        "output_sha256": hashes[0],
        "working_tree_pdf_matches": {name: (PAPER / name).exists() and
                                     digest(PAPER / name) == hashes[0][name]
                                     for name in OUTPUTS if name.endswith(".pdf")},
    }
    target = PAPER / "build/taxonomy-reproduction-check.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS: {len(OUTPUTS)} artifacts are byte-identical across two fresh builds.")
    print(f"Report: {target.relative_to(PAPER)}")


if __name__ == "__main__":
    main()
