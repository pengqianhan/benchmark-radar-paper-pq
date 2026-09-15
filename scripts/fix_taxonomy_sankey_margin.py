#!/usr/bin/env python3
"""Restore the clipped left edge of the committed vector Sankey PDF.

`scripts/plot_taxonomy.py` now applies this repair to every Sankey it writes, so
a normal rebuild needs nothing else. This entry point stays for the other case:
repairing an already-committed PDF without redrawing it, which keeps the export's
own embedded font subset instead of resubsetting against whatever fonts the
current machine has.

The repair itself lives in `plot_taxonomy.pad_left_margin`: it moves /MediaBox and
/CropBox only, leaves the vector drawing, labels and frozen counts untouched, and
is idempotent.

Requires pypdf. Run from any directory:
    python3 scripts/fix_taxonomy_sankey_margin.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_taxonomy import SANKEY_LEFT_PAD_PT, pad_left_margin  # noqa: E402

FIGURE = Path(__file__).resolve().parents[1] / "figures/taxonomy-sankey.pdf"


def main():
    if pad_left_margin(FIGURE):
        print(f"Extended the page {SANKEY_LEFT_PAD_PT:g}pt to the left; "
              "the complete Multimodal label is now on the page.")
    else:
        print("Taxonomy Sankey already has the corrected left margin.")


if __name__ == "__main__":
    main()
