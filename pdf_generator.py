"""
VendorBridge — pdf_generator.py
Server-side dynamic PDF generation using ReportLab.

Generates professional, publication-quality A4 documents:
1. Invoice PDF (Tax/Commercial Invoice submitted by vendor)
2. Purchase Order PDF (Official PO issued by admin)
3. Payment Receipt PDF (Settlement receipt after payment is recorded)

Follows VendorBridge brand guidelines:
- Palette: #1E3A34 (Deep Forest), #285C55 (Primary Teal), #C47D63 (Terracotta), #64748B (Slate Muted)
- Typography: Helvetica / Helvetica-Bold
- Two-pass NumberedCanvas for dynamic "Page X of Y" and corporate footer.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ─────────────────────────────────────────────────────────────────────────────
# Brand Colors & Theme Palette
# ─────────────────────────────────────────────────────────────────────────────
COLOR_PRIMARY_DARK = colors.HexColor("#1A3C38")
COLOR_PRIMARY = colors.HexColor("#285C55")
COLOR_PRIMARY_LIGHT = colors.HexColor("#EAF2F0")
COLOR_ACCENT = colors.HexColor("#C47D63")
COLOR_ACCENT_LIGHT = colors.HexColor("#FDF5F2")
COLOR_TEXT_MAIN = colors.HexColor("#1E293B")
COLOR_TEXT_MUTED = colors.HexColor("#64748B")
COLOR_BORDER = colors.HexColor("#CBD5E1")
COLOR_BORDER_LIGHT = colors.HexColor("#E2E8F0")
COLOR_BG_LIGHT = colors.HexColor("#F8FAFC")
COLOR_SUCCESS = colors.HexColor("#0D9488")
COLOR_SUCCESS_BG = colors.HexColor("#F0FDF4")
COLOR_WARNING = colors.HexColor("#D97706")
COLOR_WARNING_BG = colors.HexColor("#FFFBEB")
COLOR_DANGER = colors.HexColor("#DC2626")
COLOR_WHITE = colors.white


# ─────────────────────────────────────────────────────────────────────────────
# Numbered Canvas for Two-Pass Page Numbering & Footers
# ─────────────────────────────────────────────────────────────────────────────
class NumberedCanvas(Canvas):
    """
    Two-pass canvas that dynamically calculates and renders
    'Page X of Y' alongside official corporate footer notes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            Canvas.showPage(self)
        Canvas.save(self)

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        # Footer dividing line
        self.setStrokeColor(COLOR_BORDER_LIGHT)
        self.setLineWidth(0.75)
        self.line(36, 42, 559, 42)

        # Footer Left: System identity and electronic authenticity note
        self.setFont("Helvetica", 7.5)
        self.setFillColor(COLOR_TEXT_MUTED)
        self.drawString(
            36,
            30,
            "VendorBridge Procurement Management System • Digitally Authorized Record • Confidential",
        )
        self.drawString(
            36,
            20,
            f"Generated on {datetime.now().strftime('%d %b %Y at %H:%M UTC')} • Verify at vendorbridge.local",
        )

        # Footer Right: Page X of Y
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(559, 30, page_str)
        self.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# Typography & Styles Builder
# ─────────────────────────────────────────────────────────────────────────────
def get_pdf_styles():
    base = getSampleStyleSheet()

    styles = {
        "BrandTitle": ParagraphStyle(
            "BrandTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=COLOR_PRIMARY_DARK,
        ),
        "BrandSub": ParagraphStyle(
            "BrandSub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=COLOR_TEXT_MUTED,
        ),
        "DocTitle": ParagraphStyle(
            "DocTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_RIGHT,
            textColor=COLOR_PRIMARY,
        ),
        "DocMetaRight": ParagraphStyle(
            "DocMetaRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            alignment=TA_RIGHT,
            textColor=COLOR_TEXT_MAIN,
        ),
        "DocMetaRightBold": ParagraphStyle(
            "DocMetaRightBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=COLOR_PRIMARY_DARK,
        ),
        "CardHeader": ParagraphStyle(
            "CardHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=COLOR_PRIMARY,
            spaceAfter=4,
        ),
        "CardTitle": ParagraphStyle(
            "CardTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=COLOR_TEXT_MAIN,
        ),
        "CardBody": ParagraphStyle(
            "CardBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=COLOR_TEXT_MAIN,
        ),
        "CardMuted": ParagraphStyle(
            "CardMuted",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=COLOR_TEXT_MUTED,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=COLOR_WHITE,
            alignment=TA_LEFT,
        ),
        "TableHeaderRight": ParagraphStyle(
            "TableHeaderRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=COLOR_WHITE,
            alignment=TA_RIGHT,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_LEFT,
        ),
        "TableCellBold": ParagraphStyle(
            "TableCellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_LEFT,
        ),
        "TableCellRight": ParagraphStyle(
            "TableCellRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_RIGHT,
        ),
        "TableCellRightBold": ParagraphStyle(
            "TableCellRightBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_RIGHT,
        ),
        "TotalLabel": ParagraphStyle(
            "TotalLabel",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=COLOR_TEXT_MUTED,
        ),
        "TotalValue": ParagraphStyle(
            "TotalValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            alignment=TA_RIGHT,
            textColor=COLOR_TEXT_MAIN,
        ),
        "GrandTotalLabel": ParagraphStyle(
            "GrandTotalLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_RIGHT,
            textColor=COLOR_PRIMARY_DARK,
        ),
        "GrandTotalValue": ParagraphStyle(
            "GrandTotalValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=TA_RIGHT,
            textColor=COLOR_PRIMARY,
        ),
        "NotesHeading": ParagraphStyle(
            "NotesHeading",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=COLOR_PRIMARY_DARK,
            spaceAfter=3,
        ),
        "NotesBody": ParagraphStyle(
            "NotesBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=COLOR_TEXT_MAIN,
        ),
        "BadgeText": ParagraphStyle(
            "BadgeText",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ),
    }
    return styles


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Format Currency & Strings
# ─────────────────────────────────────────────────────────────────────────────
def format_inr(paise: Optional[int]) -> str:
    if paise is None:
        return "₹0.00"
    rupees = float(paise) / 100.0
    return f"₹{rupees:,.2f}"


def build_status_badge(status: str, styles: Dict[str, ParagraphStyle]) -> Table:
    st = (status or "submitted").upper()
    bg = COLOR_PRIMARY_LIGHT
    fg = COLOR_PRIMARY

    if st in ("PAID", "APPROVED", "CONFIRMED", "VERIFIED"):
        bg = COLOR_SUCCESS_BG
        fg = COLOR_SUCCESS
    elif st in ("SUBMITTED", "PENDING", "UNDER_REVIEW", "ISSUED"):
        bg = COLOR_WARNING_BG
        fg = COLOR_WARNING
    elif st in ("REJECTED", "CANCELLED"):
        bg = colors.HexColor("#FEF2F2")
        fg = COLOR_DANGER

    badge_style = ParagraphStyle(
        "BStyle",
        parent=styles["BadgeText"],
        textColor=fg,
    )

    t = Table([[Paragraph(f"STATUS: {st}", badge_style)]], colWidths=[130])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 0.75, fg),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return t


# ─────────────────────────────────────────────────────────────────────────────
# 1. Invoice PDF Generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_invoice_pdf(data: Dict[str, Any]) -> bytes:
    """
    Generates a formal commercial Tax Invoice PDF matching VendorBridge specifications.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54,
    )
    styles = get_pdf_styles()
    story: List[Any] = []

    # ── Header Section ──
    header_left = [
        Paragraph("VendorBridge", styles["BrandTitle"]),
        Paragraph("Procurement Management System", styles["BrandSub"]),
        Paragraph("Commercial Tax Invoice • Accounts Payable", styles["CardMuted"]),
    ]

    header_right = [
        Paragraph("TAX INVOICE", styles["DocTitle"]),
        Spacer(1, 4),
        build_status_badge(data.get("status", "submitted"), styles),
        Spacer(1, 4),
        Paragraph(
            f"<b>Invoice #:</b> {data.get('invoice_number', '—')}",
            styles["DocMetaRight"],
        ),
        Paragraph(
            f"<b>Invoice Date:</b> {data.get('invoice_date', '—')}",
            styles["DocMetaRight"],
        ),
        Paragraph(
            f"<b>Payment Due:</b> {data.get('due_date', '—')}",
            styles["DocMetaRight"],
        ),
    ]

    header_table = Table([[header_left, header_right]], colWidths=[280, 243])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Colored branding bar
    story.append(
        HRFlowable(
            width="100%",
            thickness=2.5,
            color=COLOR_PRIMARY,
            spaceBefore=0,
            spaceAfter=12,
        )
    )

    # ── Two-Column Information Box (Vendor / Bill To) ──
    vendor_lines = [
        Paragraph("ISSUED BY / VENDOR", styles["CardHeader"]),
        Paragraph(data.get("company_name", "Vendor Organization"), styles["CardTitle"]),
    ]
    if data.get("registration_number"):
        vendor_lines.append(
            Paragraph(f"<b>Reg / GSTIN:</b> {data['registration_number']}", styles["CardBody"])
        )
    if data.get("contact_phone"):
        vendor_lines.append(
            Paragraph(f"<b>Phone:</b> {data['contact_phone']}", styles["CardBody"])
        )
    if data.get("vendor_email"):
        vendor_lines.append(
            Paragraph(f"<b>Email:</b> {data['vendor_email']}", styles["CardBody"])
        )
    if data.get("address"):
        vendor_lines.append(
            Paragraph(f"<b>Address:</b> {data['address']}", styles["CardBody"])
        )

    buyer_lines = [
        Paragraph("BILL TO / PURCHASER", styles["CardHeader"]),
        Paragraph("VendorBridge Procurement Corp.", styles["CardTitle"]),
        Paragraph("Central Supply Chain & Finance Division", styles["CardBody"]),
        Paragraph("<b>Address:</b> Tower 4, Tech Horizon Park, Bengaluru, KA 560100", styles["CardBody"]),
        Paragraph("<b>Email:</b> finance@vendorbridge.local", styles["CardBody"]),
        Paragraph(f"<b>Authorized PO Ref:</b> {data.get('po_number', '—')}", styles["CardBody"]),
    ]

    entity_table = Table([[vendor_lines, buyer_lines]], colWidths=[255, 255])
    entity_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(entity_table)
    story.append(Spacer(1, 10))

    # ── Procurement Context Strip ──
    context_data = [
        [
            Paragraph(f"<b>Purchase Order:</b> {data.get('po_number', '—')}", styles["CardBody"]),
            Paragraph(f"<b>Tender RFQ:</b> {data.get('rfq_number', '—')} — {data.get('rfq_title', 'Tender')[:28]}", styles["CardBody"]),
            Paragraph(f"<b>Quotation Ref:</b> {data.get('quotation_number', '—')}", styles["CardBody"]),
        ]
    ]
    context_table = Table(context_data, colWidths=[160, 230, 133])
    context_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARY_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_PRIMARY),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(context_table)
    story.append(Spacer(1, 14))

    # ── Line Items Table ──
    table_headers = [
        Paragraph("#", styles["TableHeader"]),
        Paragraph("Item Description & Specifications", styles["TableHeader"]),
        Paragraph("Quantity", styles["TableHeaderRight"]),
        Paragraph("Unit Price (₹)", styles["TableHeaderRight"]),
        Paragraph("Total (₹)", styles["TableHeaderRight"]),
    ]

    item_name = data.get("item_name") or data.get("rfq_title") or "Procurement Deliverables"
    specs = data.get("specifications") or "Delivered according to technical specifications agreed in quotation."
    quantity = float(data.get("quantity") or 1.0)
    unit = data.get("unit") or "Units"
    unit_price_paise = data.get("unit_price_paise") or 0
    invoice_amount_paise = data.get("amount_paise") or 0

    desc_content = [
        Paragraph(f"<b>{item_name}</b>", styles["TableCellBold"]),
        Paragraph(f"<font color='#64748B'>{specs}</font>", styles["CardMuted"]),
    ]

    rows = [
        table_headers,
        [
            Paragraph("1", styles["TableCell"]),
            desc_content,
            Paragraph(f"{quantity:g} {unit}", styles["TableCellRight"]),
            Paragraph(format_inr(unit_price_paise), styles["TableCellRight"]),
            Paragraph(format_inr(invoice_amount_paise), styles["TableCellRightBold"]),
        ],
    ]

    line_items_table = Table(rows, colWidths=[24, 250, 75, 85, 89])
    line_items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(line_items_table)
    story.append(Spacer(1, 8))

    # ── Summary & Totals Block ──
    summary_data = [
        [
            "",
            "",
            Paragraph("Subtotal Amount:", styles["TotalLabel"]),
            Paragraph(format_inr(invoice_amount_paise), styles["TotalValue"]),
        ],
        [
            "",
            "",
            Paragraph("Applicable Tax (Included / Exempt):", styles["TotalLabel"]),
            Paragraph("₹0.00", styles["TotalValue"]),
        ],
        [
            "",
            "",
            Paragraph("Net Payable Total:", styles["GrandTotalLabel"]),
            Paragraph(format_inr(invoice_amount_paise), styles["GrandTotalValue"]),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[150, 120, 140, 113])
    summary_table.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (2, 1), (3, 1), 0.75, COLOR_BORDER),
                ("TOPPADDING", (2, 2), (3, 2), 6),
                ("BOTTOMPADDING", (2, 2), (3, 2), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ── Verification & Payment Lifecycle Box ──
    v_status = data.get("status", "submitted")
    status_notes = []

    if v_status in ("verified", "paid"):
        verified_by = data.get("verified_by_name") or "Authorized Finance Officer"
        verified_at = data.get("verified_at") or "System Verified"
        status_notes.append(
            Paragraph(
                f"<b>✓ VERIFIED AGAINST PURCHASE ORDER:</b> Verified by {verified_by} on {verified_at}.",
                styles["NotesBody"],
            )
        )
    else:
        status_notes.append(
            Paragraph(
                "<b>⏳ AWAITING VERIFICATION:</b> Under review by internal Accounts Payable against authorized PO.",
                styles["NotesBody"],
            )
        )

    if v_status == "paid":
        paid_at = data.get("paid_at") or "Settled"
        pay_ref = data.get("payment_reference") or "Electronic Transfer"
        status_notes.append(
            Paragraph(
                f"<b>✓ PAYMENT SETTLED IN FULL:</b> Payment Ref <b>{pay_ref}</b> recorded on {paid_at}.",
                styles["NotesBody"],
            )
        )

    if status_notes:
        stat_box = Table([[status_notes]], colWidths=[523])
        stat_bg = COLOR_SUCCESS_BG if v_status == "paid" else (COLOR_PRIMARY_LIGHT if v_status == "verified" else COLOR_WARNING_BG)
        stat_border = COLOR_SUCCESS if v_status == "paid" else (COLOR_PRIMARY if v_status == "verified" else COLOR_WARNING)
        stat_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), stat_bg),
                    ("BOX", (0, 0), (-1, -1), 0.75, stat_border),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(stat_box)
        story.append(Spacer(1, 12))

    # ── Terms & Notes ──
    notes_content = [
        Paragraph("TERMS, PARTICULAR CONDITIONS & DECLARATIONS", styles["NotesHeading"]),
        Paragraph(
            "1. This invoice is issued electronically under the terms and commercial conditions of the referenced Purchase Order.<br/>"
            "2. All deliverables are subject to standard inspection, three-way matching, and quality validation by VendorBridge.<br/>"
            "3. Payment will be disbursed into the verified vendor banking account on file according to net commercial terms.",
            styles["NotesBody"],
        ),
    ]
    if data.get("notes"):
        notes_content.append(Spacer(1, 4))
        notes_content.append(Paragraph(f"<b>Vendor Remarks:</b> {data['notes']}", styles["NotesBody"]))

    notes_table = Table([[notes_content]], colWidths=[523])
    notes_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(notes_table)
    story.append(Spacer(1, 16))

    # ── Sign-off & Stamp Section ──
    sign_data = [
        [
            [
                Paragraph("<b>Authorized Vendor Signatory</b>", styles["CardHeader"]),
                Spacer(1, 20),
                Paragraph(f"{data.get('company_name', 'Vendor Partner')}", styles["CardTitle"]),
                Paragraph("Authorized Electronic Signature", styles["CardMuted"]),
            ],
            [
                Paragraph("<b>VendorBridge Accounts Payable</b>", styles["CardHeader"]),
                Spacer(1, 20),
                Paragraph("Three-Way Matching & Internal Audit", styles["CardTitle"]),
                Paragraph("Certified Electronic Record", styles["CardMuted"]),
            ],
        ]
    ]
    sign_table = Table(sign_data, colWidths=[260, 263])
    sign_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (0, 0), 0.5, COLOR_BORDER),
                ("LINEABOVE", (1, 0), (1, 0), 0.5, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(KeepTogether(sign_table))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Purchase Order PDF Generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_po_pdf(data: Dict[str, Any]) -> bytes:
    """
    Generates an official Purchase Order PDF matching VendorBridge specifications.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54,
    )
    styles = get_pdf_styles()
    story: List[Any] = []

    # ── Header Section ──
    header_left = [
        Paragraph("VendorBridge", styles["BrandTitle"]),
        Paragraph("Procurement Management System", styles["BrandSub"]),
        Paragraph("Central Purchasing & Supply Chain Operations", styles["CardMuted"]),
    ]

    header_right = [
        Paragraph("PURCHASE ORDER", styles["DocTitle"]),
        Spacer(1, 4),
        build_status_badge(data.get("status", "issued"), styles),
        Spacer(1, 4),
        Paragraph(
            f"<b>PO Number:</b> {data.get('po_number', '—')}",
            styles["DocMetaRight"],
        ),
        Paragraph(
            f"<b>Issue Date:</b> {data.get('issued_at', data.get('created_at', '—'))[:10]}",
            styles["DocMetaRight"],
        ),
        Paragraph(
            f"<b>RFQ Reference:</b> {data.get('rfq_number', '—')}",
            styles["DocMetaRight"],
        ),
    ]

    header_table = Table([[header_left, header_right]], colWidths=[280, 243])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Colored branding bar
    story.append(
        HRFlowable(
            width="100%",
            thickness=2.5,
            color=COLOR_PRIMARY,
            spaceBefore=0,
            spaceAfter=12,
        )
    )

    # ── Two-Column Information Box (Purchaser / Awarded Vendor) ──
    buyer_lines = [
        Paragraph("PURCHASING ORGANIZATION / BUYER", styles["CardHeader"]),
        Paragraph("VendorBridge Procurement Corp.", styles["CardTitle"]),
        Paragraph("Headquarters & Central Operations", styles["CardBody"]),
        Paragraph("Tower 4, Horizon Tech Park, Bengaluru, KA 560100", styles["CardBody"]),
        Paragraph("<b>Authorized Officer:</b> " + (data.get("approved_by_name") or data.get("created_by_name") or "Procurement Director"), styles["CardBody"]),
        Paragraph("<b>Official Contact:</b> procurement@vendorbridge.local", styles["CardBody"]),
    ]

    vendor_lines = [
        Paragraph("AWARDED VENDOR / SUPPLIER", styles["CardHeader"]),
        Paragraph(data.get("company_name", "Vendor Organization"), styles["CardTitle"]),
    ]
    if data.get("registration_number"):
        vendor_lines.append(
            Paragraph(f"<b>Registration / GSTIN:</b> {data['registration_number']}", styles["CardBody"])
        )
    if data.get("contact_phone"):
        vendor_lines.append(
            Paragraph(f"<b>Contact Phone:</b> {data['contact_phone']}", styles["CardBody"])
        )
    if data.get("vendor_email"):
        vendor_lines.append(
            Paragraph(f"<b>Email:</b> {data['vendor_email']}", styles["CardBody"])
        )
    if data.get("address"):
        vendor_lines.append(
            Paragraph(f"<b>Address:</b> {data['address']}", styles["CardBody"])
        )

    entity_table = Table([[buyer_lines, vendor_lines]], colWidths=[255, 255])
    entity_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(entity_table)
    story.append(Spacer(1, 10))

    # ── Procurement Proposal Strip ──
    context_data = [
        [
            Paragraph(f"<b>Awarded RFQ:</b> {data.get('rfq_number', '—')} — {data.get('rfq_title', 'Tender')[:25]}", styles["CardBody"]),
            Paragraph(f"<b>Quotation Bid Ref:</b> {data.get('quotation_number', '—')}", styles["CardBody"]),
            Paragraph(f"<b>Delivery Commitment:</b> {data.get('delivery_days', 14)} calendar days", styles["CardBody"]),
        ]
    ]
    context_table = Table(context_data, colWidths=[220, 160, 143])
    context_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARY_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_PRIMARY),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(context_table)
    story.append(Spacer(1, 14))

    # ── Line Items Table ──
    table_headers = [
        Paragraph("#", styles["TableHeader"]),
        Paragraph("Item Description & Technical Scope", styles["TableHeader"]),
        Paragraph("Quantity", styles["TableHeaderRight"]),
        Paragraph("Agreed Unit Rate (₹)", styles["TableHeaderRight"]),
        Paragraph("Authorized Total (₹)", styles["TableHeaderRight"]),
    ]

    item_name = data.get("item_name") or data.get("rfq_title") or "Procurement Requirement"
    specs = data.get("specifications") or data.get("rfq_description") or "Delivered according to standard OEM enterprise criteria."
    quantity = float(data.get("quantity") or 1.0)
    unit = data.get("unit") or "Units"
    unit_price_paise = data.get("unit_price_paise") or 0
    total_amount_paise = data.get("total_amount_paise") or 0

    desc_content = [
        Paragraph(f"<b>{item_name}</b>", styles["TableCellBold"]),
        Paragraph(f"<font color='#64748B'>{specs}</font>", styles["CardMuted"]),
    ]

    rows = [
        table_headers,
        [
            Paragraph("1", styles["TableCell"]),
            desc_content,
            Paragraph(f"{quantity:g} {unit}", styles["TableCellRight"]),
            Paragraph(format_inr(unit_price_paise), styles["TableCellRight"]),
            Paragraph(format_inr(total_amount_paise), styles["TableCellRightBold"]),
        ],
    ]

    line_items_table = Table(rows, colWidths=[24, 250, 75, 85, 89])
    line_items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(line_items_table)
    story.append(Spacer(1, 8))

    # ── Summary & Totals Block ──
    summary_data = [
        [
            "",
            "",
            Paragraph("Subtotal PO Value:", styles["TotalLabel"]),
            Paragraph(format_inr(total_amount_paise), styles["TotalValue"]),
        ],
        [
            "",
            "",
            Paragraph("Tax Assessment:", styles["TotalLabel"]),
            Paragraph("Inclusive per Bid", styles["TotalValue"]),
        ],
        [
            "",
            "",
            Paragraph("Authorized PO Total:", styles["GrandTotalLabel"]),
            Paragraph(format_inr(total_amount_paise), styles["GrandTotalValue"]),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[150, 120, 140, 113])
    summary_table.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (2, 1), (3, 1), 0.75, COLOR_BORDER),
                ("TOPPADDING", (2, 2), (3, 2), 6),
                ("BOTTOMPADDING", (2, 2), (3, 2), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ── Instructions for Invoicing ──
    instr_content = [
        Paragraph("INVOICING & FULFILLMENT INSTRUCTIONS FOR VENDOR", styles["NotesHeading"]),
        Paragraph(
            f"1. <b>Invoice Submission:</b> Please log in to your VendorBridge portal and click <b>Submit Invoice</b> for <b>{data.get('po_number', 'this PO')}</b>.<br/>"
            "2. <b>Three-Way Matching:</b> Invoices must match this Purchase Order quantity and total value to ensure rapid verification and payment.<br/>"
            "3. <b>Delivery Confirmation:</b> Goods/services must be delivered with a physical or electronic delivery receipt matching the tender specification.",
            styles["NotesBody"],
        ),
    ]
    if data.get("quotation_terms") or data.get("quotation_notes"):
        terms_text = data.get("quotation_terms") or data.get("quotation_notes")
        instr_content.append(Spacer(1, 4))
        instr_content.append(Paragraph(f"<b>Agreed Quotation Terms:</b> {terms_text}", styles["NotesBody"]))

    instr_table = Table([[instr_content]], colWidths=[523])
    instr_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(instr_table)
    story.append(Spacer(1, 16))

    # ── Sign-off & Stamp Section ──
    approver = data.get("approved_by_name") or data.get("created_by_name") or "Procurement Authority"
    sign_data = [
        [
            [
                Paragraph("<b>Authorized Purchasing Authority</b>", styles["CardHeader"]),
                Spacer(1, 20),
                Paragraph(approver, styles["CardTitle"]),
                Paragraph("VendorBridge Central Procurement Division", styles["CardMuted"]),
            ],
            [
                Paragraph("<b>Vendor Acknowledgment & Acceptance</b>", styles["CardHeader"]),
                Spacer(1, 20),
                Paragraph(data.get("company_name", "Awarded Vendor Partner"), styles["CardTitle"]),
                Paragraph("Authorized Supplier Representative", styles["CardMuted"]),
            ],
        ]
    ]
    sign_table = Table(sign_data, colWidths=[260, 263])
    sign_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (0, 0), 0.5, COLOR_BORDER),
                ("LINEABOVE", (1, 0), (1, 0), 0.5, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(KeepTogether(sign_table))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Payment Receipt PDF Generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_payment_receipt_pdf(data: Dict[str, Any]) -> bytes:
    """
    Generates a formal Payment Receipt & Settlement Confirmation PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54,
    )
    styles = get_pdf_styles()
    story: List[Any] = []

    # ── Header Section ──
    header_left = [
        Paragraph("VendorBridge", styles["BrandTitle"]),
        Paragraph("Procurement Management System", styles["BrandSub"]),
        Paragraph("Corporate Accounts Payable & Treasury Division", styles["CardMuted"]),
    ]

    header_right = [
        Paragraph("PAYMENT RECEIPT", styles["DocTitle"]),
        Spacer(1, 4),
        build_status_badge("PAID", styles),
        Spacer(1, 4),
        Paragraph(
            f"<b>Payment Ref:</b> {data.get('payment_reference', '—')}",
            styles["DocMetaRightBold"],
        ),
        Paragraph(
            f"<b>Payment Date:</b> {data.get('paid_at', '—')[:10] if data.get('paid_at') else datetime.now().strftime('%Y-%m-%d')}",
            styles["DocMetaRight"],
        ),
        Paragraph(
            f"<b>Invoice Ref:</b> {data.get('invoice_number', '—')}",
            styles["DocMetaRight"],
        ),
    ]

    header_table = Table([[header_left, header_right]], colWidths=[280, 243])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Colored branding bar
    story.append(
        HRFlowable(
            width="100%",
            thickness=2.5,
            color=COLOR_SUCCESS,
            spaceBefore=0,
            spaceAfter=14,
        )
    )

    # ── Big Paid Amount Banner ──
    amount_paise = data.get("amount_paise") or 0
    formatted_amount = format_inr(amount_paise)

    amount_banner_data = [
        [
            Paragraph("SETTLEMENT CONFIRMATION • ACCOUNTS PAYABLE RECORD", styles["CardHeader"]),
        ],
        [
            Paragraph(f"<font color='#0D9488' size='22'><b>{formatted_amount}</b></font>", styles["BadgeText"]),
        ],
        [
            Paragraph("Amount Recorded &amp; Settled in Full Against Vendor Invoice", styles["CardMuted"]),
        ],
    ]
    amount_banner = Table(amount_banner_data, colWidths=[523])
    amount_banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_SUCCESS_BG),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_SUCCESS),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(amount_banner)
    story.append(Spacer(1, 14))

    # ── Beneficiary & Disbursing Entity Cards ──
    payer_lines = [
        Paragraph("DISBURSED BY / PAYER", styles["CardHeader"]),
        Paragraph("VendorBridge Procurement Corp.", styles["CardTitle"]),
        Paragraph("Treasury & Accounts Payable Operations", styles["CardBody"]),
        Paragraph("Tower 4, Horizon Tech Park, Bengaluru, KA 560100", styles["CardBody"]),
        Paragraph("<b>Finance Contact:</b> accounts@vendorbridge.local", styles["CardBody"]),
    ]

    payee_lines = [
        Paragraph("BENEFICIARY / PAID TO", styles["CardHeader"]),
        Paragraph(data.get("company_name", "Vendor Organization"), styles["CardTitle"]),
    ]
    if data.get("registration_number"):
        payee_lines.append(
            Paragraph(f"<b>Registration / GSTIN:</b> {data['registration_number']}", styles["CardBody"])
        )
    if data.get("contact_phone"):
        payee_lines.append(
            Paragraph(f"<b>Contact Phone:</b> {data['contact_phone']}", styles["CardBody"])
        )
    if data.get("vendor_email"):
        payee_lines.append(
            Paragraph(f"<b>Vendor Email:</b> {data['vendor_email']}", styles["CardBody"])
        )
    if data.get("address"):
        payee_lines.append(
            Paragraph(f"<b>Address:</b> {data['address']}", styles["CardBody"])
        )

    entity_table = Table([[payer_lines, payee_lines]], colWidths=[255, 255])
    entity_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(entity_table)
    story.append(Spacer(1, 14))

    # ── Settlement Details Grid ──
    grid_rows = [
        [
            Paragraph("<b>Transaction Parameter</b>", styles["TableHeader"]),
            Paragraph("<b>Settlement Details</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("Payment Reference / Receipt ID", styles["TableCellBold"]),
            Paragraph(str(data.get("payment_reference") or "PAY-REF-ELECTRONIC"), styles["TableCell"]),
        ],
        [
            Paragraph("Settled Commercial Invoice", styles["TableCellBold"]),
            Paragraph(f"{data.get('invoice_number', '—')} (Date: {data.get('invoice_date', '—')})", styles["TableCell"]),
        ],
        [
            Paragraph("Associated Purchase Order", styles["TableCellBold"]),
            Paragraph(str(data.get("po_number") or "—"), styles["TableCell"]),
        ],
        [
            Paragraph("Tender / RFQ Reference", styles["TableCellBold"]),
            Paragraph(f"{data.get('rfq_number', '—')} — {data.get('rfq_title', 'Tender')}", styles["TableCell"]),
        ],
        [
            Paragraph("Payment Method / Mode", styles["TableCellBold"]),
            Paragraph("Electronic Fund Transfer / Corporate Banking", styles["TableCell"]),
        ],
        [
            Paragraph("Settlement Date & Time", styles["TableCellBold"]),
            Paragraph(str(data.get("paid_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")), styles["TableCell"]),
        ],
        [
            Paragraph("Total Amount Paid", styles["TableCellBold"]),
            Paragraph(f"<b>{formatted_amount}</b>", styles["TableCellBold"]),
        ],
        [
            Paragraph("Outstanding Balance", styles["TableCellBold"]),
            Paragraph("<b>₹0.00 (Settled in Full)</b>", styles["TableCellBold"]),
        ],
    ]

    settlement_table = Table(grid_rows, colWidths=[200, 323])
    settlement_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(settlement_table)
    story.append(Spacer(1, 14))

    # ── Audit Trail & Electronic Validation Seal ──
    verifier_name = data.get("verified_by_name") or "Internal Accounts Payable"
    audit_content = [
        Paragraph("AUDIT TRAIL & SYSTEM AUTHENTICATION CERTIFICATE", styles["NotesHeading"]),
        Paragraph(
            f"This payment settlement was approved and recorded in the VendorBridge ledger by <b>{verifier_name}</b>. "
            "The corresponding purchase order, supplier quotation, and invoice have completed three-way matching "
            "and are permanently recorded in the immutable audit log.",
            styles["NotesBody"],
        ),
    ]

    audit_table = Table([[audit_content]], colWidths=[523])
    audit_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(audit_table)
    story.append(Spacer(1, 16))

    # ── Sign-off & Stamp Section ──
    sign_data = [
        [
            [
                Paragraph("<b>Disbursing Finance Officer</b>", styles["CardHeader"]),
                Spacer(1, 18),
                Paragraph("VendorBridge Treasury Department", styles["CardTitle"]),
                Paragraph("Authorized Electronic Payment Record", styles["CardMuted"]),
            ],
            [
                Paragraph("<b>Audit & Compliance Seal</b>", styles["CardHeader"]),
                Spacer(1, 18),
                Paragraph("Three-Way Matching Verified", styles["CardTitle"]),
                Paragraph("Official Ledger Confirmation", styles["CardMuted"]),
            ],
        ]
    ]
    sign_table = Table(sign_data, colWidths=[260, 263])
    sign_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (0, 0), 0.5, COLOR_BORDER),
                ("LINEABOVE", (1, 0), (1, 0), 0.5, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(KeepTogether(sign_table))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
