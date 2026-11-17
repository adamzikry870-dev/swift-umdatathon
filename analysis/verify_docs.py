"""Check the shipped documents: right length, nothing missing, no raw Markdown.

For each report the Markdown source is the contract: every heading and every
table header must appear in both the PDF and the DOCX, and no `**`, backticks or
pipe-table syntax may leak through.  The dashboard pack is checked page by page.

    python analysis/verify_docs.py
"""
import fitz
from docx import Document

from swift.db import ROOT
import mdconvert

DOCS = ROOT / "docs"
REPORTS = [
    # markdown source, document stem, documented page count, documented paragraphs
    ("FINDINGS_01_dataset_overview.md", "Swift_Dataset_Anatomy_and_Generation_Rules", 6, 81),
    ("FINDINGS_02_dashboard_spec.md", "Swift_Dashboard_Specification", 7, 108),
]
PACK = ("Swift_Dashboard_Pack", 11)
LEAKS = ("**", "```", " | ")


def norm(text):
    return " ".join(text.split())


def pdf_text(path):
    return norm("".join(page.get_text() for page in fitz.open(path)))


def docx_text(path):
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return norm(" ".join(parts))


def expected_strings(markdown):
    """Every heading and every table header cell in the source, markup stripped."""
    headings, cells = [], []
    for block in mdconvert.parse(markdown):
        if block[0] == "h":
            headings.append(mdconvert._plain(block[2]))
        elif block[0] == "table":
            cells.extend(mdconvert._plain(c) for c in block[1])
    return headings, cells


def main():
    checks = []

    def check(label, ok, detail=""):
        checks.append((label, ok, detail))

    for source, stem, pages_expected, paras_expected in REPORTS:
        markdown = (ROOT / "analysis" / source).read_text(encoding="utf-8")
        pdf, docx = DOCS / f"{stem}.pdf", DOCS / f"{stem}.docx"
        check(f"{stem}: pdf + docx exist", pdf.exists() and docx.exists())

        pages = fitz.open(pdf).page_count
        check(f"{stem}: page count", pages == pages_expected, f"{pages} vs {pages_expected}")

        paragraphs = len(Document(docx).paragraphs)
        check(f"{stem}: docx paragraph count", paragraphs == paras_expected,
              f"{paragraphs} vs {paras_expected}")

        headings, cells = expected_strings(markdown)
        for kind, text, target in [("pdf", pdf_text(pdf), pdf), ("docx", docx_text(docx), docx)]:
            missing = [h for h in headings if norm(mdconvert._plain(h)) not in text]
            check(f"{stem}: {kind} has all {len(headings)} headings", not missing,
                  ", ".join(missing[:3]))
            lost = [c for c in cells if len(c) > 1 and norm(c) not in text]
            check(f"{stem}: {kind} has all {len(cells)} table headers", not lost,
                  ", ".join(lost[:3]))
            leaked = [mark for mark in LEAKS if mark in text]
            check(f"{stem}: {kind} has no raw Markdown", not leaked, " ".join(leaked))

    pack = DOCS / f"{PACK[0]}.pdf"
    check(f"{PACK[0]}: exists", pack.exists())
    if pack.exists():
        doc = fitz.open(pack)
        check(f"{PACK[0]}: page count", doc.page_count == PACK[1],
              f"{doc.page_count} vs {PACK[1]}")
        blank = [p.number + 1 for p in doc if len(p.get_images()) != 1]
        check(f"{PACK[0]}: one panel image per page", not blank, str(blank))
        wide = [p.number + 1 for p in doc
                if abs(p.rect.width / p.rect.height - 16 / 9) > 0.01]
        check(f"{PACK[0]}: 16:9 pages", not wide, str(wide))

    width = max(len(label) for label, _ok, _d in checks)
    failed = 0
    for label, ok, detail in checks:
        suffix = f"  {detail}" if detail and not ok else ""
        print(f"{label:<{width}}  {'ok' if ok else 'FAIL'}{suffix}")
        failed += 0 if ok else 1
    print(f"\n{len(checks) - failed}/{len(checks)} document checks passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
