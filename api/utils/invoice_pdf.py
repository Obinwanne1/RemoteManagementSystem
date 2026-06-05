"""
ReportLab PDF generator for professional invoices.
Returns bytes that can be streamed directly as application/pdf.
"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage,
)

# ── Brand colours ──────────────────────────────────────────────────────────────
GREEN       = colors.HexColor("#407E3C")
GREEN_LIGHT = colors.HexColor("#EEF7ED")
DARK        = colors.HexColor("#1A2B1A")
MID         = colors.HexColor("#4A5A4A")
MUTED       = colors.HexColor("#6B7B6B")
WHITE       = colors.white
PAGE_BG     = colors.HexColor("#F8FAF8")

W, H = A4  # 210mm × 297mm

_MARGIN = 18 * mm


def _styles():
    base = getSampleStyleSheet()
    return {
        "company_name": ParagraphStyle(
            "company_name",
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=DARK,
            leading=18,
        ),
        "company_sub": ParagraphStyle(
            "company_sub",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=MUTED,
            leading=12,
        ),
        "invoice_title": ParagraphStyle(
            "invoice_title",
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=GREEN,
            leading=30,
            alignment=TA_RIGHT,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "meta_value": ParagraphStyle(
            "meta_value",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=DARK,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "section_label": ParagraphStyle(
            "section_label",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=MUTED,
            leading=10,
            spaceAfter=3,
        ),
        "bill_name": ParagraphStyle(
            "bill_name",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=DARK,
            leading=14,
        ),
        "bill_detail": ParagraphStyle(
            "bill_detail",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=MID,
            leading=12,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=WHITE,
            leading=10,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=DARK,
            leading=12,
        ),
        "table_cell_right": ParagraphStyle(
            "table_cell_right",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=DARK,
            leading=12,
            alignment=TA_RIGHT,
        ),
        "total_label": ParagraphStyle(
            "total_label",
            fontName="Helvetica",
            fontSize=9,
            textColor=MID,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "total_value": ParagraphStyle(
            "total_value",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "grand_label": ParagraphStyle(
            "grand_label",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=WHITE,
            leading=14,
            alignment=TA_RIGHT,
        ),
        "grand_value": ParagraphStyle(
            "grand_value",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=WHITE,
            leading=14,
            alignment=TA_RIGHT,
        ),
        "footer_heading": ParagraphStyle(
            "footer_heading",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=DARK,
            leading=11,
        ),
        "footer_body": ParagraphStyle(
            "footer_body",
            fontName="Helvetica",
            fontSize=8,
            textColor=MID,
            leading=12,
        ),
        "status_badge": ParagraphStyle(
            "status_badge",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=WHITE,
            leading=10,
            alignment=TA_RIGHT,
        ),
    }


def _fmt_date(dt_val):
    if not dt_val:
        return "—"
    if isinstance(dt_val, str):
        try:
            dt_val = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except Exception:
            return dt_val[:10]
    return dt_val.strftime("%d %B %Y")


def _fmt_money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


STATUS_COLORS = {
    "paid":    colors.HexColor("#22C55E"),
    "sent":    colors.HexColor("#3B82F6"),
    "overdue": colors.HexColor("#EF4444"),
    "draft":   colors.HexColor("#9CA3AF"),
}


def generate_invoice_pdf(invoice, customer, org) -> bytes:
    """
    Generate a professional A4 PDF invoice.

    Args:
        invoice: Invoice model instance (or dict with to_dict() fields)
        customer: Customer model instance (or dict)
        org: OrgSettings model instance (or dict)

    Returns:
        bytes — raw PDF content
    """
    # Normalise to dicts
    inv = invoice.to_dict() if hasattr(invoice, "to_dict") else invoice
    cust = customer.to_dict() if hasattr(customer, "to_dict") else customer
    org_d = org.to_dict() if hasattr(org, "to_dict") else org
    logo_bytes = org.logo_bytes() if hasattr(org, "logo_bytes") else None

    S = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=f"Invoice {inv.get('invoice_number', '')}",
        author=org_d.get("company_name", "RMM System"),
    )

    content_width = W - 2 * _MARGIN
    story = []

    # ─────────────────────────────────────────────────────────────────────────
    # HEADER — company (left) + INVOICE title (right)
    # ─────────────────────────────────────────────────────────────────────────
    col_left = content_width * 0.55
    col_right = content_width * 0.45

    # Company logo / name cell
    company_name = org_d.get("company_name") or "Your Company"
    company_addr = org_d.get("company_address") or ""
    company_email = org_d.get("company_email") or ""
    company_phone = org_d.get("company_phone") or ""

    left_items = []
    if logo_bytes:
        try:
            logo_img = RLImage(io.BytesIO(logo_bytes), width=40*mm, height=14*mm)
            logo_img.hAlign = "LEFT"
            left_items.append(logo_img)
            left_items.append(Spacer(1, 4))
        except Exception:
            pass

    left_items.append(Paragraph(company_name, S["company_name"]))
    detail_parts = [p for p in [company_addr, company_email, company_phone] if p]
    if detail_parts:
        left_items.append(Paragraph("<br/>".join(detail_parts), S["company_sub"]))

    # Invoice meta cell
    inv_num = inv.get("invoice_number") or inv.get("id", "")[:8].upper()
    inv_status = (inv.get("status") or "draft").upper()
    status_color = STATUS_COLORS.get(inv.get("status", "draft"), colors.HexColor("#9CA3AF"))

    right_items = [
        Paragraph("INVOICE", S["invoice_title"]),
        Spacer(1, 3),
        Paragraph(f"#{inv_num}", ParagraphStyle("inv_num", fontName="Helvetica-Bold",
            fontSize=12, textColor=DARK, leading=15, alignment=TA_RIGHT)),
        Spacer(1, 8),
        Paragraph("ISSUE DATE", S["meta_label"]),
        Paragraph(_fmt_date(inv.get("created_at")), S["meta_value"]),
        Spacer(1, 4),
        Paragraph("DUE DATE", S["meta_label"]),
        Paragraph(_fmt_date(inv.get("due_date")), S["meta_value"]),
        Spacer(1, 4),
        Paragraph("STATUS", S["meta_label"]),
        Paragraph(f'<font color="{status_color.hexval()}">{inv_status}</font>',
                  S["meta_value"]),
    ]

    header_table = Table(
        [[left_items, right_items]],
        colWidths=[col_left, col_right],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=6*mm))

    # ─────────────────────────────────────────────────────────────────────────
    # BILL TO + PERIOD
    # ─────────────────────────────────────────────────────────────────────────
    bill_col = content_width * 0.55
    period_col = content_width * 0.45

    cust_name = cust.get("name") or "—"
    cust_email = cust.get("email") or ""
    cust_phone = cust.get("phone") or ""
    cust_addr = cust.get("address") or ""

    bill_items = [
        Paragraph("BILL TO", S["section_label"]),
        Paragraph(cust_name, S["bill_name"]),
    ]
    bill_detail_parts = [p for p in [cust_addr, cust_email, cust_phone] if p]
    if bill_detail_parts:
        bill_items.append(Paragraph("<br/>".join(bill_detail_parts), S["bill_detail"]))

    period_start = _fmt_date(inv.get("period_start"))
    period_end   = _fmt_date(inv.get("period_end"))
    payment_terms = org_d.get("payment_terms") or "Net 30"

    period_items = [
        Paragraph("SERVICE PERIOD", S["section_label"]),
        Paragraph(f"{period_start} – {period_end}", ParagraphStyle(
            "period", fontName="Helvetica-Bold", fontSize=9.5,
            textColor=DARK, leading=13)),
        Spacer(1, 5),
        Paragraph("PAYMENT TERMS", S["section_label"]),
        Paragraph(payment_terms, ParagraphStyle(
            "terms", fontName="Helvetica", fontSize=9,
            textColor=MID, leading=12)),
    ]

    bill_table = Table(
        [[bill_items, period_items]],
        colWidths=[bill_col, period_col],
    )
    bill_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 6*mm))

    # ─────────────────────────────────────────────────────────────────────────
    # LINE ITEMS TABLE
    # ─────────────────────────────────────────────────────────────────────────
    desc_w  = content_width * 0.46
    qty_w   = content_width * 0.12
    rate_w  = content_width * 0.18
    amount_w = content_width * 0.24

    def _hdr(text):
        return Paragraph(text, S["table_header"])

    def _cell(text, right=False):
        return Paragraph(str(text), S["table_cell_right"] if right else S["table_cell"])

    headers = [_hdr("DESCRIPTION"), _hdr("QTY"), _hdr("UNIT RATE"), _hdr("AMOUNT")]

    line_items = inv.get("line_items") or []
    if not line_items:
        device_count = inv.get("device_count") or 0
        rate = inv.get("per_device_rate") or 0
        subtotal = inv.get("subtotal") or 0
        line_items = [{"description": f"Managed Devices — Service Period", "amount": subtotal}]

    rows = [headers]
    for i, item in enumerate(line_items):
        desc = item.get("description", "Service")
        qty = item.get("quantity") or inv.get("device_count") or 1
        rate = item.get("rate") or inv.get("per_device_rate") or (
            float(item.get("amount", 0)) / float(qty) if float(qty) > 0 else 0
        )
        amount = item.get("amount", 0)
        rows.append([
            _cell(desc),
            _cell(str(qty), right=True),
            _cell(_fmt_money(rate), right=True),
            _cell(_fmt_money(amount), right=True),
        ])

    # Alternating row colours
    items_table = Table(rows, colWidths=[desc_w, qty_w, rate_w, amount_w])
    row_count = len(rows)
    table_style = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDE8DD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]
    # Alternate data rows
    for r in range(1, row_count):
        if r % 2 == 0:
            table_style.append(("BACKGROUND", (0, r), (-1, r), GREEN_LIGHT))
    items_table.setStyle(TableStyle(table_style))
    story.append(items_table)
    story.append(Spacer(1, 4*mm))

    # ─────────────────────────────────────────────────────────────────────────
    # TOTALS BLOCK
    # ─────────────────────────────────────────────────────────────────────────
    subtotal_val = float(inv.get("subtotal") or 0)
    tax_val      = float(inv.get("tax") or 0)
    tax_rate_pct = float(inv.get("tax_rate") or 0) * 100
    total_val    = float(inv.get("total") or 0)

    totals_left_w = content_width * 0.6
    totals_right_w = content_width * 0.4

    subtotal_rows = [
        [Paragraph("Subtotal", S["total_label"]),
         Paragraph(_fmt_money(subtotal_val), S["total_value"])],
        [Paragraph(f"Tax ({tax_rate_pct:.1f}%)", S["total_label"]),
         Paragraph(_fmt_money(tax_val), S["total_value"])],
    ]

    sub_table = Table(subtotal_rows, colWidths=[totals_right_w * 0.55, totals_right_w * 0.45])
    sub_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#DDE8DD")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))

    grand_table = Table(
        [[Paragraph("TOTAL DUE", S["grand_label"]),
          Paragraph(_fmt_money(total_val), S["grand_value"])]],
        colWidths=[totals_right_w * 0.55, totals_right_w * 0.45],
    )
    grand_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))

    totals_outer = Table(
        [["", sub_table], ["", grand_table]],
        colWidths=[totals_left_w, totals_right_w],
    )
    totals_outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(totals_outer)
    story.append(Spacer(1, 8*mm))

    # ─────────────────────────────────────────────────────────────────────────
    # FOOTER — payment instructions + notes
    # ─────────────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDE8DD"),
                             spaceBefore=2*mm, spaceAfter=4*mm))

    footer_col_w = content_width / 2 - 4*mm
    footer_left = []
    footer_right = []

    bank_details = org_d.get("bank_details") or ""
    if bank_details:
        footer_left.append(Paragraph("PAYMENT DETAILS", S["section_label"]))
        footer_left.append(Paragraph(bank_details.replace("\n", "<br/>"), S["footer_body"]))
        footer_left.append(Spacer(1, 4))

    notes = inv.get("notes") or ""
    if notes:
        footer_left.append(Paragraph("NOTES", S["section_label"]))
        footer_left.append(Paragraph(notes.replace("\n", "<br/>"), S["footer_body"]))

    footer_msg = org_d.get("footer_notes") or "Thank you for your business!"
    footer_right.append(Spacer(1, 4))
    footer_right.append(Paragraph(footer_msg, ParagraphStyle(
        "footer_msg",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=GREEN,
        leading=13,
        alignment=TA_RIGHT,
    )))

    company_contact = org_d.get("company_email") or ""
    if company_contact:
        footer_right.append(Spacer(1, 4))
        footer_right.append(Paragraph(company_contact, ParagraphStyle(
            "footer_contact",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=11,
            alignment=TA_RIGHT,
        )))

    footer_table = Table(
        [[footer_left, footer_right]],
        colWidths=[footer_col_w + 4*mm, footer_col_w],
    )
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(footer_table)

    doc.build(story)
    return buf.getvalue()
