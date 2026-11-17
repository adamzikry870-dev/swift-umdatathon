"""One Markdown reader, two writers: DOCX (python-docx) and PDF (reportlab).

The analysis notes are written once in Markdown and shipped in both formats.
This module parses the Markdown into a small block list and then renders that
list twice, so the two files can never drift apart.

    python analysis/mdconvert.py analysis/FINDINGS_02_dashboard_spec.md \
        docs/Swift_Dashboard_Specification.docx "Dashboard Specification"
    python analysis/mdconvert.py analysis/FINDINGS_02_dashboard_spec.md \
        docs/Swift_Dashboard_Specification.pdf  "Dashboard Specification"

The writer is chosen from the output suffix.  Supported Markdown: headings,
paragraphs (with `meta` blocks of **Key:** value lines), bullet and numbered
lists, pipe tables, horizontal rules, blockquotes, fenced code, and inline
`code`, **bold** and *italic*.
"""
import re
import sys
from pathlib import Path

# ============================================================ 1. Markdown -> blocks

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
NUMBER = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
TABLE_RULE = re.compile(r"^:?-{2,}:?$")
META_LINE = re.compile(r"^\*\*[^*]+:\*\*")

BLOCK_START = ("#", "|", ">", "```")


def _starts_block(line):
    """Does this line open a block, i.e. should a paragraph stop before it?"""
    s = line.strip()
    return (not s or s.startswith(BLOCK_START) or bool(RULE.fullmatch(s))
            or bool(BULLET.match(line)) or bool(NUMBER.match(line)))


def parse(md):
    """Markdown text -> list of blocks.

    ("h", level, text)         ("p", [lines], is_meta)
    ("ul", [(indent, text)])   ("ol", [(indent, text)])
    ("table", header, rows)    ("code", [lines])
    ("rule",)                  ("quote", text)
    """
    lines = md.splitlines()
    blocks, i, n = [], 0, len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            body = []
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", body))
            continue

        m = HEADING.match(s)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue

        if RULE.fullmatch(s):
            blocks.append(("rule",))
            i += 1
            continue

        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(TABLE_RULE.fullmatch(c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows[0], rows[1:]))
            continue

        if s.startswith(">"):
            blocks.append(("quote", s.lstrip(">").strip()))
            i += 1
            continue

        for kind, pattern in (("ul", BULLET), ("ol", NUMBER)):
            m = pattern.match(raw)
            if not m:
                continue
            items = []
            while i < n:
                item = pattern.match(lines[i])
                if not item:
                    break
                indent = len(item.group(1)) // 2
                text = item.group(item.lastindex).strip()
                items.append((indent, text))
                i += 1
            blocks.append((kind, items))
            break
        else:
            para = [s]
            i += 1
            while i < n and not _starts_block(lines[i]):
                para.append(lines[i].strip())
                i += 1
            blocks.append(("p", para, all(META_LINE.match(x) for x in para)))

    return blocks


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# characters Calibri lacks -> readable fallbacks (applied in both writers)
GLYPH_FIX = {"\u27fa": "\u2194", "\u27f9": "\u2192", "\u226b": "\u00bb", "\u226a": "\u00ab"}


def _fold(text):
    for missing, fallback in GLYPH_FIX.items():
        text = text.replace(missing, fallback)
    return text


def _plain(text):
    """Strip inline markup, for places that cannot render it."""
    return _fold(re.sub(r"(\*\*|`|\*)", "", text))


# ============================================================ 2. DOCX writer
def write_docx(blocks, path, title, subtitle="Swift UMDAC Datathon 2026 — working note"):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    ACCENT = RGBColor(0x0B, 0x3D, 0x6B)
    ACCENT2 = RGBColor(0x1F, 0x6F, 0x8B)
    GREY = RGBColor(0x59, 0x59, 0x59)
    BODY_FONT, MONO_FONT = "Calibri", "Consolas"
    INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")

    def fix(text):
        return _fold(text)

    def element(name, **attrs):
        el = OxmlElement(name)
        for key, value in attrs.items():
            el.set(qn(f"w:{key}"), str(value))
        return el

    def shade_run(run, fill):
        run._element.get_or_add_rPr().append(element("w:shd", val="clear", fill=fill))

    def shade_cell(cell, fill):
        cell._tc.get_or_add_tcPr().append(
            element("w:shd", val="clear", color="auto", fill=fill))

    def borders(par, sides, color, size="4", space="4"):
        pPr = par._p.get_or_add_pPr()
        box = OxmlElement("w:pBdr")
        for side in sides:
            box.append(element(f"w:{side}", val="single", sz=size, space=space, color=color))
        pPr.append(box)

    def cell_margins(table):
        mar = OxmlElement("w:tblCellMar")
        for side in ("top", "bottom", "left", "right"):
            mar.append(element(f"w:{side}", w={"top": 60, "bottom": 60,
                                               "left": 90, "right": 90}[side], type="dxa"))
        table._tbl.tblPr.append(mar)

    def row_flags(row, header=False):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(element("w:tblHeader", val="true") if header
                   else element("w:cantSplit", val="true"))

    def emit(par, text, size, color=None, bold=False, italic=False):
        """Write text into a paragraph, with `code` spans as shaded mono runs."""
        for part in re.split(r"(`[^`]+`)", text):
            if not part:
                continue
            is_code = part.startswith("`") and part.endswith("`") and len(part) > 2
            run = par.add_run(part[1:-1] if is_code else part)
            run.font.size = Pt(size - 1 if is_code else size)
            run.font.name = MONO_FONT if is_code else BODY_FONT
            if is_code:
                run.font.color.rgb = RGBColor(0x8B, 0x1A, 0x1A)
                shade_run(run, "F2F2F2")
            elif color is not None:
                run.font.color.rgb = color
            run.bold = bold
            run.italic = italic

    def add_runs(par, text, size=10.5, color=None, bold=False, italic=False):
        for part in INLINE.split(fix(text)):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                emit(par, part[2:-2], size, color, bold=True, italic=italic)
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                emit(par, part[1:-1], size, color, bold=bold, italic=True)
            else:
                emit(par, part, size, color, bold=bold, italic=italic)

    def widths(table, header, rows, total_cm=16.6):
        """Fixed layout, columns sized by a damped function of their content."""
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        table._tbl.tblPr.append(layout)
        table._tbl.tblPr.append(element("w:tblW", w=int(total_cm / 2.54 * 1440), type="dxa"))

        weights = []
        for j in range(len(header)):
            lengths = [len(header[j].replace("`", ""))] + [
                len(r[j].replace("`", "").replace("**", "")) if j < len(r) else 0
                for r in rows]
            p90 = sorted(lengths)[int(len(lengths) * 0.9)] if lengths else 8
            weights.append(max(6, min(p90, 60)) ** 0.72)
        widths_cm = [total_cm * w / sum(weights) for w in weights]
        widths_cm = [max(w, 1.5) for w in widths_cm]
        widths_cm = [w * total_cm / sum(widths_cm) for w in widths_cm]
        for row in table.rows:
            row_flags(row)
            for j, cell in enumerate(row.cells):
                cell.width = Cm(widths_cm[j])

    def page_number(par, instruction):
        run = par.add_run()
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), instruction)
        run._element.addnext(field)

    def setup(doc):
        sec = doc.sections[0]
        sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.9)
        sec.left_margin, sec.right_margin = Cm(2.1), Cm(2.1)
        normal = doc.styles["Normal"]
        normal.font.name = BODY_FONT
        normal.font.size = Pt(10.5)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)

        header = sec.header.paragraphs[0]
        header.text = ""
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header.add_run(subtitle)
        run.font.size, run.font.name, run.font.color.rgb = Pt(8), BODY_FONT, GREY

        footer = sec.footer.paragraphs[0]
        footer.text = ""
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for text, instruction in [("Page ", "PAGE"), (" of ", "NUMPAGES")]:
            run = footer.add_run(text)
            run.font.size, run.font.color.rgb = Pt(8), GREY
            page_number(footer, instruction)

    doc = Document()
    setup(doc)
    first_title = True

    for block in blocks:
        kind = block[0]

        if kind == "h":
            _, level, text = block
            if level == 1 and first_title:
                first_title = False
                par = doc.add_paragraph()
                par.paragraph_format.space_before = Pt(0)
                par.paragraph_format.space_after = Pt(4)
                add_runs(par, text, size=24, color=ACCENT, bold=True)
                borders(par, ["bottom"], "0B3D6B", size="12", space="6")
            else:
                par = doc.add_heading(level=1 if level == 1 else min(level - 1, 4))
                par.text = ""
                size = {1: 17, 2: 13.5, 3: 11.8, 4: 11}.get(level, 10.5)
                add_runs(par, text, size=size,
                         color=ACCENT if level <= 2 else ACCENT2, bold=True)
                par.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
                par.paragraph_format.space_after = Pt(4)
                par.paragraph_format.keep_with_next = True

        elif kind == "p":
            _, lines, _meta = block
            par = doc.add_paragraph()
            par.paragraph_format.space_after = Pt(6)
            par.paragraph_format.line_spacing = 1.12
            add_runs(par, " ".join(lines))

        elif kind in ("ul", "ol"):
            style = "List Bullet" if kind == "ul" else "List Number"
            for indent, text in block[1]:
                par = doc.add_paragraph(style=style)
                par.paragraph_format.left_indent = Cm(0.63 + 0.5 * indent)
                par.paragraph_format.space_after = Pt(3)
                par.paragraph_format.line_spacing = 1.08
                add_runs(par, text)

        elif kind == "table":
            _, header, rows = block
            table = doc.add_table(rows=1, cols=len(header))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.LEFT
            table.autofit = True
            cell_margins(table)
            row_flags(table.rows[0], header=True)
            for j, text in enumerate(header):
                cell = table.rows[0].cells[j]
                cell.text = ""
                par = cell.paragraphs[0]
                par.paragraph_format.space_after = Pt(2)
                add_runs(par, text, size=9.5, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
                shade_cell(cell, "0B3D6B")
            for k, row in enumerate(rows):
                cells = table.add_row().cells
                for j, text in enumerate(row[:len(header)]):
                    cells[j].text = ""
                    par = cells[j].paragraphs[0]
                    par.paragraph_format.space_after = Pt(2)
                    add_runs(par, text, size=9.5)
                    if k % 2 == 1:
                        shade_cell(cells[j], "F3F6F9")
            widths(table, header, rows)
            doc.add_paragraph().paragraph_format.space_after = Pt(4)

        elif kind == "rule":
            par = doc.add_paragraph()
            par.paragraph_format.space_before = Pt(2)
            par.paragraph_format.space_after = Pt(8)
            borders(par, ["bottom"], "BFBFBF", size="6", space="1")

        elif kind == "quote":
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.6)
            par.paragraph_format.space_before = Pt(4)
            par.paragraph_format.space_after = Pt(8)
            borders(par, ["left"], "1F6F8B", size="18", space="8")
            add_runs(par, block[1], size=10, color=GREY, italic=True)

        elif kind == "code":
            par = doc.add_paragraph()
            fmt = par.paragraph_format
            fmt.left_indent = Cm(0.15)
            fmt.right_indent = Cm(0.15)
            fmt.space_before, fmt.space_after = Pt(8), Pt(10)
            fmt.line_spacing = 1.0
            fmt.keep_together = True
            borders(par, ["top", "left", "bottom", "right"], "D6DEE7")
            run = par.add_run(fix("\n".join(block[1])))
            run.font.name = MONO_FONT
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


# ============================================================ 3. PDF writer
def write_pdf(blocks, path, title, footer="Swift UMDAC Datathon 2026  ·  dashboard specification"):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                    Paragraph, Spacer, Table, TableStyle, XPreformatted)

    NAVY = colors.HexColor("#0B3D6B")
    TEAL = colors.HexColor("#1F6F8B")
    GOLD = colors.HexColor("#C9962B")
    GREY = colors.HexColor("#595959")
    LIGHT = colors.HexColor("#F2F5F9")
    RULE = colors.HexColor("#D9DEE5")
    INK = colors.HexColor("#1F2937")

    fonts = {
        "Calibri": r"C:\Windows\Fonts\calibri.ttf",
        "Calibri-Bold": r"C:\Windows\Fonts\calibrib.ttf",
        "Calibri-Italic": r"C:\Windows\Fonts\calibrii.ttf",
        "Calibri-BoldItalic": r"C:\Windows\Fonts\calibriz.ttf",
        "Consolas": r"C:\Windows\Fonts\consola.ttf",
    }
    for name, file in fonts.items():
        if Path(file).exists():
            pdfmetrics.registerFont(TTFont(name, file))
    pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold",
                                  italic="Calibri-Italic", boldItalic="Calibri-BoldItalic")

    BODY = ParagraphStyle("body", fontName="Calibri", fontSize=9.9, leading=14.4,
                          textColor=INK, spaceAfter=6, alignment=TA_LEFT)
    H1 = ParagraphStyle("h1", fontName="Calibri-Bold", fontSize=15.5, leading=19,
                        textColor=NAVY, spaceBefore=14, spaceAfter=7, keepWithNext=1)
    H2 = ParagraphStyle("h2", fontName="Calibri-Bold", fontSize=11.6, leading=15,
                        textColor=TEAL, spaceBefore=11, spaceAfter=4, keepWithNext=1)
    # variants for headings followed by a long table, which must be allowed to split
    H1_PLAIN = ParagraphStyle("h1-plain", parent=H1, keepWithNext=0)
    H2_PLAIN = ParagraphStyle("h2-plain", parent=H2, keepWithNext=0)
    BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=4,
                            spaceAfter=3)
    NUMBERED = ParagraphStyle("numbered", parent=BULLET)
    CODE = ParagraphStyle("code", fontName="Consolas", fontSize=8.3, leading=11,
                          textColor=colors.HexColor("#222222"))
    TCELL = ParagraphStyle("cell", fontName="Calibri", fontSize=8.5, leading=11, textColor=INK)
    THEAD = ParagraphStyle("thead", fontName="Calibri-Bold", fontSize=8.5, leading=11,
                           textColor=colors.white)
    QUOTE = ParagraphStyle("quote", parent=BODY, leftIndent=12, textColor=GREY,
                           fontName="Calibri-Italic")

    def inline(text):
        text = _escape(_fold(text))
        text = re.sub(r"`([^`]+)`",
                      r'<font name="Consolas" size="8.8" color="#0B3D6B">\1</font>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
        return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)

    def rule(width, thickness, colour):
        return Table([[""]], colWidths=[width], rowHeights=[thickness],
                     style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colour)]))

    def table_block(rows, width):
        ncol = len(rows[0])
        data = [[Paragraph(inline(c), THEAD) for c in rows[0]]]
        for row in rows[1:]:
            row = row + [""] * (ncol - len(row))
            data.append([Paragraph(inline(c), TCELL) for c in row[:ncol]])
        table = Table(data, colWidths=[width / ncol] * ncol, repeatRows=1, hAlign="LEFT")
        style = [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("TOPPADDING", (0, 0), (-1, -1), 4),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                 ("LEFTPADDING", (0, 0), (-1, -1), 5),
                 ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE)]
        style += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(data), 2)]
        table.setStyle(TableStyle(style))
        return table

    def code_block(lines, width):
        table = Table([[XPreformatted(_escape("\n".join(lines)), CODE)]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    width = A4[0] - 40 * mm
    story = []
    for block in blocks:
        kind = block[0]

        if kind == "h":
            _, level, text = block
            if level == 1:
                story.append(Paragraph(inline(text), ParagraphStyle(
                    "title", fontName="Calibri-Bold", fontSize=21, leading=26,
                    textColor=NAVY, spaceAfter=4)))
                story += [Spacer(1, 2), rule(width, 1.6, GOLD), Spacer(1, 8)]
            else:
                story.append(Paragraph(inline(text), H1 if level == 2 else H2))

        elif kind == "p":
            _, lines, meta = block
            text = "<br/>".join(inline(x) for x in lines) if meta else inline(" ".join(lines))
            story.append(Paragraph(text, BODY))

        elif kind == "ul":
            for _indent, text in block[1]:
                story.append(Paragraph(inline(text), BULLET, bulletText="•"))
            story.append(Spacer(1, 4))

        elif kind == "ol":
            for number, (_indent, text) in enumerate(block[1], start=1):
                story.append(Paragraph(inline(text), NUMBERED, bulletText=f"{number}."))
            story.append(Spacer(1, 4))

        elif kind == "table":
            _, header, rows = block
            table = table_block([header, *rows], width)
            heading = None
            if story and isinstance(story[-1], Paragraph) and \
                    story[-1].style.name in ("h1", "h2"):
                heading = story.pop()            # keep heading with its table
            head = [heading] if heading else []
            # short tables stay whole; long ones may break between rows (header repeats)
            if len(rows) <= 6:
                story.append(KeepTogether([*head, Spacer(1, 2), table, Spacer(1, 7)]))
            else:
                if heading is not None:          # so the heading must not hold it back
                    style = H1_PLAIN if heading.style.name == "h1" else H2_PLAIN
                    head = [Paragraph(heading.text, style)]
                story += [*head, Spacer(1, 2), table, Spacer(1, 7)]

        elif kind == "rule":
            story += [Spacer(1, 4), rule(width, 0.7, RULE), Spacer(1, 6)]

        elif kind == "quote":
            story.append(Paragraph(inline(block[1]), QUOTE))
            story.append(Spacer(1, 4))

        elif kind == "code":
            story.append(KeepTogether([Spacer(1, 2), code_block(block[1], width), Spacer(1, 7)]))

    class Doc(BaseDocTemplate):
        def __init__(self, target):
            super().__init__(str(target), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                             topMargin=18 * mm, bottomMargin=17 * mm, title=title)

        def afterPage(self):
            canvas = self.canv
            canvas.saveState()
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.6)
            canvas.line(20 * mm, 12 * mm, A4[0] - 20 * mm, 12 * mm)
            canvas.setFont("Calibri", 7.4)
            canvas.setFillColor(GREY)
            canvas.drawString(20 * mm, 8.6 * mm, footer)
            canvas.drawRightString(A4[0] - 20 * mm, 8.6 * mm, f"page {self.page}")
            canvas.restoreState()

    def masthead(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 7 * mm, A4[0], 7 * mm, stroke=0, fill=1)
        canvas.setFillColor(GOLD)
        canvas.rect(0, A4[1] - 7.9 * mm, A4[0], 0.9 * mm, stroke=0, fill=1)
        canvas.restoreState()

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc = Doc(path)
    frame = Frame(20 * mm, 17 * mm, width, A4[1] - 35 * mm, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=masthead)])
    doc.build(story)


# ============================================================ 4. CLI
def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    source, target = Path(argv[0]), Path(argv[1])
    title = argv[2] if len(argv) > 2 else source.stem.replace("_", " ")
    subtitle = argv[3] if len(argv) > 3 else "Swift UMDAC Datathon 2026 — working note"
    blocks = parse(source.read_text(encoding="utf-8"))

    if target.suffix.lower() == ".docx":
        write_docx(blocks, target, title, subtitle)
    elif target.suffix.lower() == ".pdf":
        write_pdf(blocks, target, title, footer=subtitle)
    else:
        raise SystemExit(f"unsupported output type: {target.suffix}")
    print(f"wrote {target} ({target.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
