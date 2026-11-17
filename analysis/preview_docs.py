"""Render PDF pages to PNG so they can be eyeballed.

    python analysis/preview_docs.py                          # both reports, pages 1-3
    python analysis/preview_docs.py docs/X.pdf --pages 1-7
    python analysis/preview_docs.py --dpi 140 --out preview

Images land in `preview/<document>_pNN.png` (git-ignored scratch space).
"""
import argparse
from pathlib import Path

import fitz

from swift.db import ROOT

DOCS = ROOT / "docs"
DEFAULT = ["Swift_Dataset_Anatomy_and_Generation_Rules.pdf",
           "Swift_Dashboard_Specification.pdf"]


def page_range(text, count):
    """'1-3' or '2,5' or 'all' -> list of 1-based page numbers that exist."""
    if text == "all":
        return list(range(1, count + 1))
    pages = set()
    for part in text.split(","):
        if "-" in part:
            first, last = (int(x) for x in part.split("-", 1))
            pages.update(range(first, last + 1))
        else:
            pages.add(int(part))
    return sorted(p for p in pages if 1 <= p <= count)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", nargs="*", help="PDFs to render (default: both reports)")
    parser.add_argument("--pages", default="1-3", help="e.g. 1-3, 2,5 or all")
    parser.add_argument("--dpi", type=int, default=110)
    parser.add_argument("--out", default="preview", help="output folder")
    args = parser.parse_args()

    targets = [Path(p) for p in args.pdf] or [DOCS / name for name in DEFAULT]
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    for path in targets:
        doc = fitz.open(path)
        pages = page_range(args.pages, doc.page_count)
        for page in pages:
            image = out / f"{path.stem}_p{page}.png"
            doc[page - 1].get_pixmap(dpi=args.dpi).save(image)
        print(f"{path.name}: {len(pages)} page(s) of {doc.page_count} -> {out}")


if __name__ == "__main__":
    main()
