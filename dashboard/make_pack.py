"""Assemble the ten panel PNGs into one PDF pack, with a cover page.

    python dashboard/make_pack.py   ->  docs/Swift_Dashboard_Pack.pdf
"""
import sys
from pathlib import Path

import fitz
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import style as S  # noqa: E402

PNG = HERE / "png"
OUT = HERE.parent / "docs" / "Swift_Dashboard_Pack.pdf"
PAGE_W, PAGE_H = 13.33 * 72, 7.5 * 72      # points, 16:9

# number, short name, one-line claim (shortened from the panel title for the cover)
PANELS = [
    ("01", "Currency", "Currency is chosen by the sender, not by the corridor"),
    ("02", "Amounts", "Who pays whom sets the amount: a 49x gap between B-B and C-C"),
    ("03", "Routing", "Every extra bank in the chain is a 37% coin flip"),
    ("04", "Continuity", "Truncation is exactly 1 - 0.95^(n-1)"),
    ("05", "FX", "Conversions follow the country chain, not chance"),
    ("06", "Duration", "Latency is bought by hand-offs, not by conversions"),
    ("07", "Time", "One global business-hours curve, rotated by timezone"),
    ("08", "Anomalies", "Labels are injected by typology and by destination"),
    ("09", "Geography", "A handful of banks carry the network"),
    ("10", "Party text", "The sender's address is domestic; the beneficiary's is anywhere"),
]


def cover(path):
    """Cover page: title block plus the ten claims as a two-column index."""
    S.setup()
    fig = plt.figure(figsize=(13.33, 7.5))
    fig.patches.append(plt.Rectangle((0, 0), 0.022, 1, transform=fig.transFigure,
                                     facecolor=S.NAVY, edgecolor="none", zorder=0))
    fig.text(0.07, 0.90, "SWIFT UMDAC DATATHON 2026  ·  PRELIMINARY ROUND",
             fontsize=10, color=S.TEAL, fontweight="bold")
    fig.text(0.07, 0.815, "Anatomy of a synthetic\npayment network",
             fontsize=34, color=S.NAVY, fontweight="bold", va="top", linespacing=1.15)
    fig.text(0.07, 0.655,
             "Ten exhibits on how 10 million SWIFT-shaped payments are constructed, from the currency\n"
             "on the wire to the addresses in the free-text fields.",
             fontsize=12.5, color="#374151", va="top", linespacing=1.5)
    fig.patches.append(plt.Rectangle((0.07, 0.575), 0.18, 0.0035, transform=fig.transFigure,
                                     facecolor=S.GOLD, edgecolor="none"))

    for i, (number, short, claim) in enumerate(PANELS):
        x = 0.07 + (i // 5) * 0.455
        y = 0.495 - (i % 5) * 0.082
        fig.text(x, y, number, fontsize=15, color=S.GOLD, fontweight="bold", va="top")
        fig.text(x + 0.038, y - 0.004, short.upper(), fontsize=8.2, color=S.TEAL,
                 fontweight="bold", va="top")
        fig.text(x + 0.038, y - 0.028, claim, fontsize=9.6, color="#1F2937", va="top")

    fig.text(0.07, 0.075, "Every figure is generated directly from 10,000,000 payment records "
                          "(analysis/payments.parquet); no external data is used.",
             fontsize=9, color=S.GREY)
    fig.text(0.07, 0.043, "Fictitious data  ·  prepared for the Universiti Malaya UMDAC Datathon 2026",
             fontsize=8, color=S.GREY)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    cov = PNG / "00_cover.png"
    cover(cov)
    panels = sorted(p for p in PNG.glob("[0-9][0-9]_*.png") if p.name != cov.name)

    doc = fitz.open()
    for image in [cov, *panels]:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_image(fitz.Rect(0, 0, PAGE_W, PAGE_H), filename=str(image))
    doc.set_metadata({"title": "Anatomy of a synthetic payment network - dashboard pack",
                      "author": "UMDAC Datathon 2026 analysis",
                      "subject": "Swift synthetic payment data: ten structural exhibits"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT), deflate=True, garbage=4)
    doc.close()
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB, {len(panels) + 1} pages)")


if __name__ == "__main__":
    main()
