#!/usr/bin/env python3
"""
generate_pdf.py — Convert HANDOVER_GUIDE.md → professional PDF.
Usage : python generate_pdf.py
Output: HANDOVER_GUIDE.pdf  (overwrites existing)
Deps  : reportlab  (already in venv)
"""

import re
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ── Brand colours ─────────────────────────────────────────────────────────────

GREEN       = HexColor('#407E3C')
GREEN_DARK  = HexColor('#2D5C29')
GREEN_LIGHT = HexColor('#E8F5E9')
GRAY_LIGHT  = HexColor('#F3F4F6')
GRAY_BORDER = HexColor('#D1D5DB')
GRAY_TEXT   = HexColor('#6B7280')
CODE_BG     = HexColor('#F8F8F8')
CODE_FG     = '#c7254e'

NOTE_BG, NOTE_BD  = HexColor('#DBEAFE'), HexColor('#3B82F6')
TIP_BG,  TIP_BD   = HexColor('#DCFCE7'), HexColor('#22C55E')
WARN_BG, WARN_BD  = HexColor('#FEF3C7'), HexColor('#F59E0B')
IMP_BG,  IMP_BD   = HexColor('#FFE4E6'), HexColor('#EF4444')

CALLOUT_MAP = {
    'NOTE':      (NOTE_BG, NOTE_BD, 'NOTE'),
    'TIP':       (TIP_BG,  TIP_BD,  'TIP'),
    'WARNING':   (WARN_BG, WARN_BD, 'WARNING'),
    'IMPORTANT': (IMP_BG,  IMP_BD,  'IMPORTANT'),
}

PAGE_W, PAGE_H = A4
MARGIN     = 2.2 * cm
CONTENT_W  = PAGE_W - 2 * MARGIN

# ── Paragraph styles ──────────────────────────────────────────────────────────

def _s(name, **kw):
    return ParagraphStyle(name, **kw)

S_H1 = _s('RMMHeading1', fontName='Helvetica-Bold', fontSize=19, leading=25,
           textColor=GREEN_DARK, spaceBefore=16, spaceAfter=5, keepWithNext=1)
S_H2 = _s('RMMHeading2', fontName='Helvetica-Bold', fontSize=14, leading=19,
           textColor=GREEN, spaceBefore=12, spaceAfter=4, keepWithNext=1)
S_H3 = _s('RMMHeading3', fontName='Helvetica-Bold', fontSize=11, leading=15,
           textColor=HexColor('#1F2937'), spaceBefore=9, spaceAfter=3, keepWithNext=1)
S_H4 = _s('RMMHeading4', fontName='Helvetica-Bold', fontSize=10, leading=14,
           textColor=HexColor('#374151'), spaceBefore=6, spaceAfter=2, keepWithNext=1)

S_BODY = _s('RMMBody', fontName='Helvetica', fontSize=10, leading=15,
            textColor=HexColor('#111827'), spaceBefore=3, spaceAfter=3,
            alignment=TA_JUSTIFY)
S_BULLET  = _s('RMMBullet',  fontName='Helvetica', fontSize=10, leading=14,
               textColor=HexColor('#111827'), leftIndent=18, firstLineIndent=-12,
               spaceBefore=1, spaceAfter=1)
S_BULLET2 = _s('RMMBullet2', fontName='Helvetica', fontSize=10, leading=14,
               textColor=HexColor('#111827'), leftIndent=34, firstLineIndent=-12,
               spaceBefore=1, spaceAfter=1)
S_NUMBERED = _s('RMMNumbered', fontName='Helvetica', fontSize=10, leading=14,
                textColor=HexColor('#111827'), leftIndent=22, firstLineIndent=-16,
                spaceBefore=1, spaceAfter=1)

S_CODE = _s('RMMCode', fontName='Courier', fontSize=8, leading=11,
            textColor=HexColor('#1F2937'))

S_TH = _s('RMMTableH', fontName='Helvetica-Bold', fontSize=9, leading=12,
           textColor=white)
S_TD = _s('RMMTableD', fontName='Helvetica', fontSize=9, leading=12,
           textColor=HexColor('#111827'))
S_CALLOUT       = _s('RMMCallout',  fontName='Helvetica', fontSize=9.5, leading=14,
                     textColor=HexColor('#1F2937'), leftIndent=4)
S_CALLOUT_LABEL = _s('RMMCalloutL', fontName='Helvetica-Bold', fontSize=9.5, leading=14,
                     textColor=HexColor('#1F2937'), leftIndent=4)

# TOC styles
S_TOC1 = _s('RMMTOC1', fontName='Helvetica-Bold', fontSize=12, leading=16,
             textColor=GREEN_DARK, spaceBefore=6)
S_TOC2 = _s('RMMTOC2', fontName='Helvetica', fontSize=10, leading=14,
             textColor=HexColor('#374151'), leftIndent=16, spaceBefore=1)
S_TOC3 = _s('RMMTOC3', fontName='Helvetica', fontSize=9, leading=12,
             textColor=HexColor('#6B7280'), leftIndent=32)

# Cover styles (white text on green background)
S_COV_TITLE = _s('CovTitle', fontName='Helvetica-Bold', fontSize=32, leading=40,
                 textColor=white, alignment=TA_CENTER)
S_COV_SUB   = _s('CovSub',   fontName='Helvetica',      fontSize=15, leading=21,
                 textColor=HexColor('#A7F3D0'), alignment=TA_CENTER)
S_COV_META  = _s('CovMeta',  fontName='Helvetica',      fontSize=10, leading=16,
                 textColor=HexColor('#D1FAE5'), alignment=TA_CENTER)

# ── Inline markdown → ReportLab XML ──────────────────────────────────────────

def _inline(text: str) -> str:
    """Convert inline markdown formatting to reportlab paragraph XML."""
    # 1. Protect inline code from XML escaping
    codes: dict[str, str] = {}

    def _protect(m):
        key = f'\x00C{len(codes)}\x00'
        raw = (m.group(1)
               .replace('&', '&amp;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))
        codes[key] = f'<font name="Courier" size="8" color="{CODE_FG}">{raw}</font>'
        return key

    text = re.sub(r'`([^`\n]+)`', _protect, text)

    # 2. Escape remaining XML special chars
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 3. Bold+italic, bold, italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*',     r'<b>\1</b>',        text)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)

    # 4. Hyperlinks
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: f'<link href="{m.group(2)}" color="#407E3C"><u>{m.group(1)}</u></link>',
        text,
    )

    # 5. Restore code spans
    for k, v in codes.items():
        text = text.replace(k, v)

    return text


def _plain(text: str) -> str:
    """Strip all markdown formatting to plain text."""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


_seen_anchors: dict[str, int] = {}

def _anchor(plain: str) -> str:
    key = re.sub(r'[^\w-]', '', plain.lower().replace(' ', '-'))[:50] or 'sec'
    n = _seen_anchors.get(key, 0)
    _seen_anchors[key] = n + 1
    return key if n == 0 else f'{key}-{n}'


# ── Document template with TOC support ───────────────────────────────────────

class RMMDoc(BaseDocTemplate):

    def __init__(self, path: str):
        BaseDocTemplate.__init__(
            self, path, pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN,  bottomMargin=MARGIN,
        )
        # Cover: full-page frame (background drawn by onPage callback)
        f_cover = Frame(0, 0, PAGE_W, PAGE_H, id='cover', showBoundary=0)
        # Normal content frame with room for header bar + footer
        f_main  = Frame(
            MARGIN, MARGIN + 0.9 * cm,
            CONTENT_W, PAGE_H - 2 * MARGIN - 1.8 * cm,
            id='main', showBoundary=0,
        )
        self.addPageTemplates([
            PageTemplate('Cover',  frames=[f_cover], onPage=_draw_cover),
            PageTemplate('Normal', frames=[f_main],  onPage=_draw_normal),
        ])

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        level = {'RMMHeading1': 0, 'RMMHeading2': 1, 'RMMHeading3': 2}.get(
            flowable.style.name)
        if level is None:
            return
        key  = getattr(flowable, '_toc_key',  '')
        text = getattr(flowable, '_toc_text', '')
        if key:
            self.canv.bookmarkPage(key)
            self.notify('TOCEntry', (level, text, self.page, key))


def _draw_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Accent stripe
    canvas.setFillColor(GREEN)
    canvas.rect(0, PAGE_H * 0.38, PAGE_W, 5, fill=1, stroke=0)
    # Logo box
    bw = 80
    bx = (PAGE_W - bw) / 2
    by = PAGE_H * 0.65
    canvas.setFillColor(HexColor('#4ADE80'))
    canvas.roundRect(bx, by, bw, bw, 12, fill=1, stroke=0)
    canvas.setFont('Helvetica-Bold', 22)
    canvas.setFillColor(GREEN_DARK)
    canvas.drawCentredString(PAGE_W / 2, by + bw / 2 - 8, 'RMM')
    canvas.restoreState()


def _draw_normal(canvas, doc):
    canvas.saveState()
    # Top green bar
    canvas.setFillColor(GREEN)
    canvas.rect(MARGIN, PAGE_H - MARGIN - 3 * mm, CONTENT_W, 3 * mm, fill=1, stroke=0)
    # Footer rule
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, MARGIN + 7 * mm, PAGE_W - MARGIN, MARGIN + 7 * mm)
    # Footer text
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawString(MARGIN, MARGIN + 2.5 * mm, 'RMM System — Complete Handbook')
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN + 2.5 * mm, f'Page {doc.page}')
    canvas.restoreState()


# ── Cover & TOC flowables ────────────────────────────────────────────────────

def _cover_story():
    return [
        Spacer(1, PAGE_H * 0.30),
        Paragraph('RMM System', S_COV_TITLE),
        Spacer(1, 0.4 * cm),
        Paragraph('Complete Handbook', S_COV_SUB),
        Spacer(1, 0.7 * cm),
        HRFlowable(width=7 * cm, thickness=1,
                   color=HexColor('#4ADE80'), hAlign='CENTER'),
        Spacer(1, 0.7 * cm),
        Paragraph('Remote Monitoring &amp; Management Platform', S_COV_META),
        Paragraph('Version 1.0&nbsp;&nbsp;·&nbsp;&nbsp;NinjaOne-style, built in-house', S_COV_META),
        Spacer(1, 2 * cm),
        Paragraph('All staff: technicians · administrators · managers · developers', S_COV_META),
    ]


def _toc_story():
    toc = TableOfContents()
    toc.levelStyles  = [S_TOC1, S_TOC2, S_TOC3]
    toc.dotsMinLevel = 0
    return [
        Paragraph('Table of Contents', S_H1),
        Spacer(1, 0.3 * cm),
        toc,
        PageBreak(),
    ]


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _mk_heading(level: int, raw: str, had_h1: list) -> list:
    """Return a heading Paragraph, with PageBreak before H1 (after first)."""
    style = (S_H1, S_H2, S_H3, S_H4)[min(level - 1, 3)]
    plain = _plain(raw)
    key   = _anchor(plain)
    para  = Paragraph(f'<a name="{key}"/>{_inline(raw)}', style)
    para._toc_key  = key
    para._toc_text = plain
    out = []
    if level == 1:
        if had_h1[0]:
            out.append(PageBreak())
        had_h1[0] = True
    return out + [para]


def _mk_code(lines: list) -> list:
    text = ('\n'.join(lines)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('\n', '<br/>'))
    cell  = Paragraph(text, S_CODE)
    tbl   = Table([[cell]], colWidths=[CONTENT_W - 1 * cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CODE_BG),
        ('BOX',           (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
    ]))
    return [Spacer(1, 3), tbl, Spacer(1, 3)]


def _mk_table(rows: list) -> list:
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        parsed.append(cells)
    # Remove separator rows (e.g. |---|---|)
    data_rows = [r for r in parsed
                 if not all(re.match(r'^[-:\s]+$', c) for c in r)]
    if not data_rows:
        return []
    ncols  = max(len(r) for r in data_rows)
    col_w  = CONTENT_W / ncols
    data   = []
    for idx, row in enumerate(data_rows):
        cells = (row + [''] * ncols)[:ncols]
        sty   = S_TH if idx == 0 else S_TD
        data.append([Paragraph(_inline(c), sty) for c in cells])
    tbl = Table(data, colWidths=[col_w] * ncols, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  0), GREEN),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [white, GREEN_LIGHT]),
        ('GRID',          (0, 0), (-1, -1), 0.4, GRAY_BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
    ]))
    return [Spacer(1, 4), tbl, Spacer(1, 4)]


def _mk_callout(lines: list, ctype: str) -> list:
    bg, bd, label = CALLOUT_MAP.get(ctype, (GRAY_LIGHT, GRAY_BORDER, ctype))
    text = ' '.join(lines)
    text = re.sub(rf'^\*\*{ctype}:\*\*\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(rf'^{ctype}:\s*',          '', text, flags=re.IGNORECASE)
    rows = [
        [Paragraph(f'<b>{label}</b>', S_CALLOUT_LABEL)],
        [Paragraph(_inline(text),    S_CALLOUT)],
    ]
    tbl = Table(rows, colWidths=[CONTENT_W - 0.6 * cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg),
        ('LINEBEFORE',    (0, 0), (-1, -1), 4, bd),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (0,  0),  6),
        ('BOTTOMPADDING', (0, 0), (0,  0),  2),
        ('TOPPADDING',    (0, 1), (0, -1),  2),
        ('BOTTOMPADDING', (0, 1), (0, -1),  7),
    ]))
    return [Spacer(1, 4), tbl, Spacer(1, 4)]


# ── Markdown parser ───────────────────────────────────────────────────────────

def parse_markdown(md: str) -> list:
    lines   = md.splitlines()
    story   = []
    had_h1  = [False]
    n       = len(lines)
    i       = 0

    def _is_list_break(ln):
        return (not ln.strip()
                or ln.strip().startswith('```')
                or re.match(r'^#{1,4}\s', ln)
                or re.match(r'^---+\s*$', ln)
                or ln.startswith('|')
                or ln.startswith('>'))

    while i < n:
        line = lines[i]

        # ── Fenced code block ─────────────────────────────────────────────
        if line.strip().startswith('```'):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1
            story.extend(_mk_code(code_lines))
            continue

        # ── Heading ───────────────────────────────────────────────────────
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            story.extend(_mk_heading(len(m.group(1)), m.group(2), had_h1))
            i += 1
            continue

        # ── Horizontal rule ───────────────────────────────────────────────
        if re.match(r'^---+\s*$', line):
            story.append(HRFlowable(width='100%', thickness=0.5,
                                    color=GRAY_BORDER, spaceBefore=4, spaceAfter=4))
            i += 1
            continue

        # ── Table ─────────────────────────────────────────────────────────
        if line.startswith('|'):
            tbl_lines = []
            while i < n and lines[i].startswith('|'):
                tbl_lines.append(lines[i])
                i += 1
            story.extend(_mk_table(tbl_lines))
            continue

        # ── Blockquote / callout ──────────────────────────────────────────
        if line.startswith('>'):
            bq = []
            while i < n and lines[i].startswith('>'):
                bq.append(lines[i][1:].strip())
                i += 1
            full = ' '.join(bq)
            ctype = 'NOTE'
            for ct in ('NOTE', 'TIP', 'WARNING', 'IMPORTANT'):
                if re.match(rf'\*\*{ct}:\*\*|{ct}:', full, re.IGNORECASE):
                    ctype = ct
                    break
            story.extend(_mk_callout(bq, ctype))
            continue

        # ── Bullet list ───────────────────────────────────────────────────
        mb = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if mb:
            indent = len(mb.group(1))
            sty    = S_BULLET2 if indent >= 4 else S_BULLET
            txt    = _inline(mb.group(2))
            i += 1
            # Collect soft-wrapped continuation lines
            while i < n:
                nx = lines[i]
                if (_is_list_break(nx)
                        or re.match(r'^\s*[-*]\s+', nx)
                        or re.match(r'^\s*\d+\.\s+', nx)):
                    break
                txt += ' ' + _inline(nx.strip())
                i += 1
            story.append(Paragraph(f'&#x2022;&nbsp;{txt}', sty))
            continue

        # ── Numbered list ─────────────────────────────────────────────────
        mn = re.match(r'^\s*(\d+)\.\s+(.*)', line)
        if mn:
            num = mn.group(1)
            txt = _inline(mn.group(2))
            i += 1
            while i < n:
                nx = lines[i]
                if (_is_list_break(nx)
                        or re.match(r'^\s*\d+\.\s+', nx)
                        or re.match(r'^\s*[-*]\s+', nx)):
                    break
                txt += ' ' + _inline(nx.strip())
                i += 1
            story.append(Paragraph(f'<b>{num}.</b>&nbsp;{txt}', S_NUMBERED))
            continue

        # ── Blank line ────────────────────────────────────────────────────
        if not line.strip():
            story.append(Spacer(1, 2))
            i += 1
            continue

        # ── Normal paragraph ──────────────────────────────────────────────
        para_lines = [line]
        i += 1
        while i < n:
            nx = lines[i]
            if (_is_list_break(nx)
                    or re.match(r'^#{1,4}\s', nx)
                    or re.match(r'^\s*[-*]\s+', nx)
                    or re.match(r'^\s*\d+\.\s+', nx)):
                break
            para_lines.append(nx)
            i += 1
        text = ' '.join(l.strip() for l in para_lines).strip()
        if text:
            story.append(Paragraph(_inline(text), S_BODY))

    return story


# ── Build ─────────────────────────────────────────────────────────────────────

def build(md_path: Path, pdf_path: Path):
    _seen_anchors.clear()

    md_text = md_path.read_text(encoding='utf-8')

    story: list = []

    # 1 — Cover page (Cover template, drawn green by onPage callback)
    story.extend(_cover_story())
    story.append(NextPageTemplate('Normal'))
    story.append(PageBreak())

    # 2 — TOC page (auto-generated, clickable)
    story.extend(_toc_story())

    # 3 — Content (all chapters from markdown)
    story.extend(parse_markdown(md_text))

    doc = RMMDoc(str(pdf_path))
    doc.multiBuild(story)

    size_kb = pdf_path.stat().st_size // 1024
    print(f'Done: {pdf_path}  ({size_kb} KB)')


if __name__ == '__main__':
    root = Path(__file__).parent
    build(root / 'HANDOVER_GUIDE.md', root / 'HANDOVER_GUIDE.pdf')
