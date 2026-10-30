import os
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from services.billing import number_to_indian_words
from config import Config

# Brand Colors matching reference
COLOR_GOLD = colors.HexColor("#ffd60a")
COLOR_GOLD_DARK = colors.HexColor("#d9890b")
COLOR_GOLD_BG = colors.HexColor("#fef3c7")
COLOR_INK = colors.HexColor("#14161c")
COLOR_NAVY = colors.HexColor("#1b2547")
COLOR_LINE = colors.HexColor("#a9b3c6")
COLOR_LIGHT_GRAY = colors.HexColor("#f3f4f6")
COLOR_TEXT_MUTED = colors.HexColor("#4b5563")

class NumberedCanvas(canvas.Canvas):
    """Canvas that adds header/footer decorations and page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        w, h = A4
        
        # Bottom decorative footer bar
        self.setFillColor(COLOR_INK)
        self.rect(0, 0, w, 14, fill=1, stroke=0)
        self.setFillColor(COLOR_GOLD)
        p = self.beginPath()
        p.moveTo(0, 0)
        p.lineTo(35, 0)
        p.lineTo(18, 14)
        p.lineTo(0, 14)
        p.close()
        self.drawPath(p, fill=1, stroke=0)
        
        # Page number (if multiple pages)
        if total_pages > 1:
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.white)
            self.drawRightString(w - 20, 4, f"Page {self._pageNumber} of {total_pages}")
            
        self.restoreState()


def generate_invoice_pdf(invoice_dict, output_path=None):
    """
    Generates a professional A4 PDF invoice inspired by the Moraya Electric design.
    Returns either bytes (io.BytesIO) or writes to output_path.
    """
    buffer = io.BytesIO() if output_path is None else open(output_path, "wb")
    
    # Page setup: A4 with tight 20pt side margins for maximum printable area
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=20,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=22,
        textColor=COLOR_INK,
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=COLOR_INK,
        alignment=1
    )
    small_tag_style = ParagraphStyle(
        'DocTag',
        fontName='Helvetica',
        fontSize=7,
        leading=8.5,
        textColor=COLOR_INK
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=COLOR_INK
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=COLOR_INK
    )
    table_header_style = ParagraphStyle(
        'TableHead',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=COLOR_INK,
        alignment=1
    )
    words_style = ParagraphStyle(
        'WordsStyle',
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        textColor=COLOR_INK
    )

    story = []
    
    # Width available: 595.27 - 48 = 547.27 pt
    CONTENT_WIDTH = 547.27

    # 1. Header with Logo & Business Information
    logo_path = os.path.join(os.path.dirname(__file__), "..", "static", "images", "moraya_logo.jpg")
    if not os.path.exists(logo_path):
        # Fallback to brain copy
        logo_path = r"C:/Users/iNDIA/.gemini/antigravity/brain/2800909f-8f6f-4664-9174-0cce4623e992/.user_uploaded/media_1793377086456_dab566c1.jpg"
    
    logo_img = None
    if os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=70, height=70)
        except Exception as e:
            print(f"[PDF] Logo load error: {e}")

    # Header text box
    header_text_html = """
    <para align="center">
        <b><font size="21" color="#14161c">MORAYA ELECTRIC</font></b><br/>
        <b><font size="9" color="#14161c">ELECTRICAL &amp; ELECTRONICS SOLUTIONS</font></b><br/>
        <font size="8" color="#1b2547"><b>Call / WhatsApp:</b> 7083155192, 8625914505</font>
    </para>
    """
    header_p = Paragraph(header_text_html, styles['Normal'])

    # Header services list
    services_html = """
    <para>
        <font size="7" color="#333333">
        • Electrical Fitting &amp; Wiring<br/>
        • New Home / Old Home Fitting<br/>
        • Maintenance &amp; Repairing<br/>
        • Lighting Solutions<br/>
        • Single &amp; Three Phase Service
        </font>
    </para>
    """
    services_p = Paragraph(services_html, styles['Normal'])

    if logo_img:
        hdr_data = [[logo_img, header_p, services_p]]
        hdr_cols = [75, 330, 142.27]
    else:
        hdr_data = [[header_p, services_p]]
        hdr_cols = [400, 147.27]

    hdr_table = Table(hdr_data, colWidths=hdr_cols)
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fffdf0")),
        ('BOX', (0, 0), (-1, -1), 1.5, COLOR_GOLD),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 6))

    # 2. INVOICE Title Badge
    inv_title_table = Table([
        [Paragraph('<b><font size="12" color="#ffffff">&nbsp;INVOICE&nbsp;</font></b>', styles['Normal'])]
    ], colWidths=[130])
    inv_title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_INK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(inv_title_table)
    story.append(Spacer(1, 4))

    # 3. Customer and Invoice Meta Details (2-column layout)
    cust_name = invoice_dict.get("customer_name") or "Valued Customer"
    cust_phone = invoice_dict.get("customer_phone") or "—"
    cust_addr = invoice_dict.get("customer_address") or "—"
    inv_num = invoice_dict.get("invoice_number", "ME-DRAFT")
    
    # Format date nicely
    raw_date = invoice_dict.get("invoice_date", "")
    try:
        inv_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        inv_date = str(raw_date)[:10]

    pay_type = invoice_dict.get("payment_type", "Cash")
    pay_status = invoice_dict.get("payment_status", "Unpaid")

    meta_data = [
        [
            Paragraph(f"<b>Customer Name:</b> {cust_name}", table_cell_style),
            Paragraph(f"<b>Invoice No:</b> {inv_num}", table_cell_bold)
        ],
        [
            Paragraph(f"<b>Mobile Number:</b> {cust_phone}", table_cell_style),
            Paragraph(f"<b>Date:</b> {inv_date}", table_cell_style)
        ],
        [
            Paragraph(f"<b>Address:</b> {cust_addr}", table_cell_style),
            Paragraph(f"<b>Payment Mode:</b> {pay_type} ({pay_status})", table_cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[330, 217.27])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # 4. Products / Services Line Items Table
    # Columns: Sr.No. (35), Description (272.27), Qty (60), Rate (80), Amount (100)
    col_widths = [35, 272.27, 60, 80, 100]
    
    items_table_data = [
        [
            Paragraph("<b>Sr.No.</b>", table_header_style),
            Paragraph("<b>Description of Goods / Services</b>", table_header_style),
            Paragraph("<b>Qty</b>", table_header_style),
            Paragraph("<b>Rate (₹)</b>", table_header_style),
            Paragraph("<b>Amount (₹)</b>", table_header_style)
        ]
    ]

    items = invoice_dict.get("items") or []
    for idx, it in enumerate(items, 1):
        desc = it.get("description", "")
        qty = float(it.get("quantity", 1.0))
        rate = float(it.get("rate", 0.0))
        amt = float(it.get("amount", qty * rate))
        
        items_table_data.append([
            Paragraph(str(idx), table_cell_style),
            Paragraph(desc, table_cell_style),
            Paragraph(f"{qty:g}", ParagraphStyle('R', parent=table_cell_style, alignment=1)),
            Paragraph(f"{rate:,.2f}", ParagraphStyle('R', parent=table_cell_style, alignment=2)),
            Paragraph(f"{amt:,.2f}", ParagraphStyle('R', parent=table_cell_bold, alignment=2))
        ])

    # If few items, add empty visual rows so the invoice matches the printed receipt format
    min_rows = max(4, len(items))
    while len(items_table_data) <= min_rows:
        items_table_data.append([
            Paragraph(str(len(items_table_data)), table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph("", table_cell_style)
        ])

    items_table = Table(items_table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_GOLD),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_INK),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.5, COLOR_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 8))

    # 5. Bottom Financial Summary: 3 Sections
    # Box A: Advance Breakdown | Box B: Pending Balance | Box C: Totals
    subtotal = float(invoice_dict.get("subtotal", 0.0))
    discount = float(invoice_dict.get("discount_amount", 0.0))
    tax_amt = float(invoice_dict.get("tax_amount", 0.0))
    net_amt = float(invoice_dict.get("net_amount", subtotal - discount + tax_amt))
    cash_adv = float(invoice_dict.get("cash_advance", 0.0))
    upi_adv = float(invoice_dict.get("upi_advance", 0.0))
    bank_adv = float(invoice_dict.get("bank_advance", 0.0))
    tot_adv = float(invoice_dict.get("total_advance", cash_adv + upi_adv + bank_adv))
    balance_due = float(invoice_dict.get("balance_due", max(0.0, net_amt - tot_adv)))

    # Table A: Advance Paid
    adv_data = [
        [Paragraph("<b>Advance Paid</b>", table_header_style), Paragraph("", table_header_style)],
        [Paragraph("Cash", table_cell_style), Paragraph(f"₹ {cash_adv:,.2f}" if cash_adv else "—", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("UPI", table_cell_style), Paragraph(f"₹ {upi_adv:,.2f}" if upi_adv else "—", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("Bank Transfer", table_cell_style), Paragraph(f"₹ {bank_adv:,.2f}" if bank_adv else "—", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("<b>Total Advance</b>", table_cell_bold), Paragraph(f"<b>₹ {tot_adv:,.2f}</b>", ParagraphStyle('R', parent=table_cell_bold, alignment=2))]
    ]
    adv_table = Table(adv_data, colWidths=[90, 80])
    adv_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), COLOR_GOLD),
        ('BACKGROUND', (0, 4), (1, 4), COLOR_GOLD_BG),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))

    # Table B: Pending Amount
    pend_data = [
        [Paragraph("<b>Pending Amount</b>", table_header_style), Paragraph("", table_header_style)],
        [Paragraph("Net Amount", table_cell_style), Paragraph(f"₹ {net_amt:,.2f}", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("Advance Paid", table_cell_style), Paragraph(f"₹ {tot_adv:,.2f}", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("<b>Balance Due</b>", table_cell_bold), Paragraph(f"<b>₹ {balance_due:,.2f}</b>", ParagraphStyle('R', parent=table_cell_bold, alignment=2, textColor=colors.HexColor("#b91c1c") if balance_due > 0 else colors.HexColor("#15803d")))]
    ]
    pend_table = Table(pend_data, colWidths=[95, 80])
    pend_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), COLOR_GOLD),
        ('BACKGROUND', (0, 3), (1, 3), COLOR_GOLD_BG),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))

    # Table C: Summary
    sum_data = [
        [Paragraph("Total Amount", table_cell_style), Paragraph(f"₹ {subtotal:,.2f}", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("Discount", table_cell_style), Paragraph(f"- ₹ {discount:,.2f}" if discount else "₹ 0.00", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("Tax", table_cell_style), Paragraph(f"+ ₹ {tax_amt:,.2f}" if tax_amt else "₹ 0.00", ParagraphStyle('R', parent=table_cell_style, alignment=2))],
        [Paragraph("<b>Net Amount</b>", ParagraphStyle('N', parent=table_cell_bold, fontSize=11)), Paragraph(f"<b>₹ {net_amt:,.2f}</b>", ParagraphStyle('N', parent=table_cell_bold, fontSize=11, alignment=2, textColor=COLOR_NAVY))]
    ]
    sum_table = Table(sum_data, colWidths=[90, 97.27])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 3), (1, 3), COLOR_GOLD),
        ('BOX', (0, 0), (-1, -1), 1.5, COLOR_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    bottom_cols = Table([
        [adv_table, pend_table, sum_table]
    ], colWidths=[175, 180, 192.27])
    bottom_cols.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bottom_cols)
    story.append(Spacer(1, 10))

    # 6. Amount in Words
    words = invoice_dict.get("amount_in_words") or number_to_indian_words(net_amt)
    words_data = [
        [Paragraph("<b>Amount in Words:</b>", table_cell_bold), Paragraph(words, words_style)]
    ]
    words_table = Table(words_data, colWidths=[110, 437.27])
    words_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(words_table)
    story.append(Spacer(1, 15))

    # 7. Signature & Thank You Section
    sig_data = [
        [
            Paragraph("<i>Thank You for Your Business...</i>", ParagraphStyle('Thx', fontName='Helvetica-Oblique', fontSize=12, textColor=COLOR_NAVY)),
            Paragraph("<b>For MORAYA ELECTRIC</b><br/><br/><br/>Authorised Signature", ParagraphStyle('Sig', fontName='Helvetica', fontSize=9, alignment=1))
        ]
    ]
    sig_table = Table(sig_data, colWidths=[330, 217.27])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    story.append(sig_table)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)

    if output_path is None:
        buffer.seek(0)
        return buffer.getvalue()
    else:
        buffer.close()
        return output_path
