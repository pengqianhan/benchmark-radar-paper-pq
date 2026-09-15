#!/usr/bin/env python3
"""Restore the clipped left edge of the committed vector Sankey PDF.

Requires pypdf. Run from any directory:
    python3 scripts/fix_taxonomy_sankey_margin.py

The original Matplotlib export places the longest label at x=-1.513 pt,
outside its page. Extend the page to x=-8 pt to expose the complete label
with a small margin. The existing PDF is the vector source: its drawing,
fonts, labels, and frozen counts are preserved without reclassification.
This repair is idempotent and also applies to the original export.
"""

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject


FIGURE = Path(__file__).resolve().parents[1] / "figures/taxonomy-sankey.pdf"
ORIGINAL_BOX = (0.0, 0.0, 484.20988, 619.2)
PADDED_BOX = (-8.0, 0.0, 484.20988, 619.2)


def main():
    reader = PdfReader(FIGURE)
    if len(reader.pages) != 1:
        raise ValueError("Expected the single-page taxonomy Sankey export")
    page = reader.pages[0]
    box = tuple(float(value) for value in page.mediabox)
    if box == PADDED_BOX and tuple(page.cropbox) == PADDED_BOX:
        print("Taxonomy Sankey already has the corrected left margin.")
        return
    if box != ORIGINAL_BOX or tuple(page.cropbox) != ORIGINAL_BOX or page.rotation:
        raise ValueError("Unexpected page bounds; inspect the export before changing it")

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.pages[0].mediabox = RectangleObject(PADDED_BOX)
    writer.pages[0].cropbox = RectangleObject(PADDED_BOX)
    temporary = FIGURE.with_suffix(".tmp.pdf")
    try:
        writer.write(temporary)
        repaired = PdfReader(temporary).pages[0]
        if repaired.get_contents().get_data() != page.get_contents().get_data():
            raise ValueError("The repair must preserve the vector drawing unchanged")
        temporary.replace(FIGURE)
    finally:
        temporary.unlink(missing_ok=True)
    print("Restored the complete Multimodal label with an 8 pt left extension.")


if __name__ == "__main__":
    main()
