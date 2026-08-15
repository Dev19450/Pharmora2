import os
import io
import pandas as pd
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def generate_csv_report(df: pd.DataFrame) -> str:
    """Generates CSV format report buffer content."""
    return df.to_csv(index=False)

def generate_excel_report(df: pd.DataFrame, stock_info: dict, forecast_info: dict, prod_info: dict = None) -> bytes:
    """Generates multi-tab Excel workbook with Dashboard, Stock, Profit, Dead Stock & AI Forecast."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sales Data", index=False)
        
        if prod_info:
            highest_profit_df = pd.DataFrame(prod_info.get("highest_profit", []))
            if not highest_profit_df.empty:
                highest_profit_df.to_excel(writer, sheet_name="Highest Profit Meds", index=False)

            fast_moving_df = pd.DataFrame(prod_info.get("fast_moving", []))
            if not fast_moving_df.empty:
                fast_moving_df.to_excel(writer, sheet_name="Fast Moving Products", index=False)

            dead_stock_df = pd.DataFrame(prod_info.get("dead_stock", []))
            if not dead_stock_df.empty:
                dead_stock_df.to_excel(writer, sheet_name="Dead Stock Analyzer", index=False)

        low_stock_df = pd.DataFrame(stock_info.get("low_stock", []))
        if not low_stock_df.empty:
            low_stock_df.to_excel(writer, sheet_name="Low Stock Alert", index=False)
            
        red_alert_df = pd.DataFrame(stock_info.get("red_alert", []))
        if not red_alert_df.empty:
            red_alert_df.to_excel(writer, sheet_name="Expiry Red Alert", index=False)
            
        forecast_df = pd.DataFrame(forecast_info.get("demand_forecast", []))
        if not forecast_df.empty:
            forecast_df.to_excel(writer, sheet_name="AI Demand Forecast", index=False)
            
        reorder_df = pd.DataFrame(forecast_info.get("reorder_suggestions", []))
        if not reorder_df.empty:
            reorder_df.to_excel(writer, sheet_name="Auto Reorder", index=False)

    return output.getvalue()

def generate_pdf_report(df: pd.DataFrame, kpis: dict, stock_info: dict, forecast_info: dict, prod_info: dict = None) -> bytes:
    """Generates an executive PDF report with styling using ReportLab."""
    output = io.BytesIO()
    
    if not REPORTLAB_AVAILABLE:
        text_content = f"Pharmora Executive Analytics Report\nGenerated: {datetime.now()}\nTotal Sales: Rs.{kpis.get('total_sales')}\nTotal Profit: Rs.{kpis.get('total_profit')}\nTotal Orders: {kpis.get('total_orders')}\n"
        return text_content.encode('utf-8')

    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=8
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=15
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6
    )

    elements = []

    elements.append(Paragraph("Pharmora - Executive Analytics & AI Inventory Report", title_style))
    elements.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Smart Pharmacy Intelligence", subtitle_style))
    elements.append(Spacer(1, 8))

    kpi_data = [
        ["Total Sales", "Total Profit", "Total Orders", "Avg Margin", "Stock Value"],
        [
            f"Rs. {kpis.get('total_sales', 0):,.2f}",
            f"Rs. {kpis.get('total_profit', 0):,.2f}",
            f"{kpis.get('total_orders', 0):,}",
            f"{kpis.get('avg_margin', 0):.1f}%",
            f"Rs. {kpis.get('total_stock_value', 0):,.2f}"
        ]
    ]
    t_kpis = Table(kpi_data, colWidths=[100, 100, 90, 90, 110])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#202020")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#5DD62C")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#141414")),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#F8F8F8")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#337418")),
    ]))
    elements.append(t_kpis)
    elements.append(Spacer(1, 12))

    # Highest Profit Medicines Table
    if prod_info and prod_info.get("highest_profit"):
        elements.append(Paragraph("1. Highest Profit Medicines (Gross Margin Drivers)", section_heading))
        profit_data = [["Medicine", "Category", "Sales", "Net Profit", "Margin %", "Tag"]]
        for p in prod_info.get("highest_profit", [])[:6]:
            profit_data.append([
                p.get("medicine", ""),
                p.get("category", ""),
                f"Rs. {p.get('sales', 0):,.2f}",
                f"Rs. {p.get('profit', 0):,.2f}",
                f"{p.get('margin', 0):.1f}%",
                p.get("tag", "Leader")
            ])
        t_profit = Table(profit_data, colWidths=[120, 90, 90, 90, 60, 90])
        t_profit.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#202020")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#5DD62C")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#337418")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_profit)
        elements.append(Spacer(1, 12))

    # Fast Moving Medicines Table
    if prod_info and prod_info.get("fast_moving"):
        elements.append(Paragraph("2. Fast-Moving High Turnover Products", section_heading))
        fast_data = [["Medicine", "Category", "Qty Sold", "Sales (Rs.)", "Stock Left", "Status"]]
        for f_item in prod_info.get("fast_moving", [])[:6]:
            fast_data.append([
                f_item.get("medicine", ""),
                f_item.get("category", ""),
                f"{f_item.get('qty_sold', 0):,} units",
                f"Rs. {f_item.get('sales', 0):,.2f}",
                f"{f_item.get('stock', 0)} units",
                f_item.get("status", "Fast Mover")
            ])
        t_fast = Table(fast_data, colWidths=[120, 90, 80, 90, 70, 90])
        t_fast.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#93c5fd")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_fast)
        elements.append(Spacer(1, 12))

    # Dead Stock & Idle Capital Section
    if prod_info and prod_info.get("dead_stock"):
        elements.append(Paragraph("3. Dead Stock & Idle Working Capital Risk", section_heading))
        dead_data = [["Medicine", "Stock", "Cost Price", "Locked Capital", "Days Idle", "Action Advice"]]
        for d_item in prod_info.get("dead_stock", [])[:6]:
            dead_data.append([
                d_item.get("medicine", ""),
                f"{d_item.get('stock', 0)} units",
                f"Rs. {d_item.get('buy_price', 0):,.2f}",
                f"Rs. {d_item.get('locked_capital', 0):,.2f}",
                f"{d_item.get('days_idle', 0)} d",
                d_item.get("action", "Clearance")
            ])
        t_dead = Table(dead_data, colWidths=[120, 70, 75, 95, 60, 120])
        t_dead.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dc2626")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_dead)
        elements.append(Spacer(1, 12))

    # Critical Expiry Red Alerts
    elements.append(Paragraph("4. Critical Expiry Red Alerts", section_heading))
    red_alerts = stock_info.get("red_alert", [])[:5]
    if red_alerts:
        alert_data = [["Medicine", "Current Stock", "Days to Expiry", "Daily Burn Rate", "Risk Status"]]
        for item in red_alerts:
            alert_data.append([
                item.get("medicine", ""),
                str(item.get("stock", 0)),
                f"{item.get('days_to_expiry', 0)} Days",
                f"{item.get('daily_rate', 0)} / day",
                "EXPIRES BEFORE SOLD OUT"
            ])
        t_alert = Table(alert_data, colWidths=[120, 80, 90, 90, 140])
        t_alert.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#991b1b")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
        ]))
        elements.append(t_alert)
    else:
        elements.append(Paragraph("No critical expiry red alerts detected.", styles['Normal']))

    doc.build(elements)
    return output.getvalue()

def generate_customer_invoice_pdf(invoice: dict) -> bytes:
    """Generates official customer sales invoice receipt PDF with proper ReportLab styling."""
    output = io.BytesIO()

    if not REPORTLAB_AVAILABLE:
        text = f"TAX INVOICE #{invoice.get('invoice_no')}\nCustomer: {invoice.get('customer_name')}\nTotal: Rs. {invoice.get('grand_total')}"
        return text.encode('utf-8')

    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'InvHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor("#202020"),
        spaceAfter=4
    )
    meta_style = ParagraphStyle(
        'InvMeta',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#15803d")
    )
    cell_style = ParagraphStyle(
        'InvCell',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#202020"),
        leading=12
    )

    elements = []

    # Store Banner & Invoice Number
    store_name = invoice.get('store_name') or 'HealthCare Central Pharmacy'
    elements.append(Paragraph(f"<b>{store_name}</b>", header_style))
    elements.append(Paragraph("Official Tax Invoice | License No: PHARM-2026-REG | GSTIN: 27AAAAA0000A1Z5", meta_style))
    elements.append(Spacer(1, 10))

    # Invoice Details Table (using Paragraphs so <b> tags render properly)
    info_data = [
        [
            Paragraph(f"<b>Invoice No:</b> {invoice.get('invoice_no', 'N/A')}", cell_style),
            Paragraph(f"<b>Date:</b> {invoice.get('date', 'N/A')}", cell_style)
        ],
        [
            Paragraph(f"<b>Customer Name:</b> {invoice.get('customer_name', 'Walk-in Customer')}", cell_style),
            Paragraph(f"<b>Contact:</b> {invoice.get('customer_phone', 'N/A')}", cell_style)
        ],
        [
            Paragraph(f"<b>Billed By:</b> {invoice.get('billed_by', 'Pharma Staff')}", cell_style),
            Paragraph(f"<b>Payment Mode:</b> {invoice.get('payment_mode', 'Cash / UPI')}", cell_style)
        ]
    ]
    t_info = Table(info_data, colWidths=[260, 240])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8f8f8")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#337418")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 15))

    # Itemized Table
    items_data = [["Item Description", "Category", "Batch", "Qty", "Unit Price", "Remaining Stock", "Total (Rs.)"]]
    for item in invoice.get("items", []):
        items_data.append([
            item.get("medicine", ""),
            item.get("category", ""),
            item.get("batch", ""),
            f"{item.get('qty', 0)} strips",
            f"Rs. {item.get('unit_price', 0):,.2f}",
            f"{item.get('remaining_stock', 0)} left",
            f"Rs. {item.get('line_total', 0):,.2f}"
        ])

    t_items = Table(items_data, colWidths=[120, 75, 60, 55, 65, 75, 70])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#202020")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#5DD62C")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#337418")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 15))

    # Grand Totals Box (using clean plain text with Helvetica-Bold for final row)
    totals_data = [
        ["Subtotal Amount:", f"Rs. {invoice.get('subtotal', 0):,.2f}"],
        [f"Discount ({invoice.get('discount_pct', 0)}%):", f"- Rs. {invoice.get('discount_amount', 0):,.2f}"],
        ["GST Tax (12%):", f"+ Rs. {invoice.get('tax_amount', 0):,.2f}"],
        ["Grand Total Payable:", f"Rs. {invoice.get('grand_total', 0):,.2f}"]
    ]
    t_totals = Table(totals_data, colWidths=[360, 140])
    t_totals.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-2), 'Helvetica'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9.5),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#5DD62C")),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#0F0F0F")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#337418")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_totals)

    elements.append(Spacer(1, 20))
    thanks_style = ParagraphStyle(
        'Thanks',
        parent=styles['Normal'],
        alignment=1,
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor("#15803d")
    )
    elements.append(Paragraph("Thank you for choosing Pharmora Pharmacy! Get well soon.", thanks_style))

    doc.build(elements)
    return output.getvalue()
