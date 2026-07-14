import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import matplotlib
matplotlib.use('Agg')  # Headless mode for matplotlib
import matplotlib.pyplot as plt
import numpy as np

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from health import SECTOR_MAPPINGS

# Define growth and stable sectors
GROWTH_SECTORS = ["Technology", "Conglomerate", "Energy", "Automobile", "Consumer Cyclical"]
STABLE_SECTORS = ["Financial Services", "FMCG", "Consumer Defensive", "Healthcare", "Utilities", "Telecommunications", "Construction & Engineering"]

# Custom NumberedCanvas for professional header, footer, and page numbers
class NumberedCanvas(canvas.Canvas):
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

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # First page is cover page - skip header/footer
            return
            
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header
        self.drawString(54, 750, "PORTFOLIO INTELLIGENCE & ADVISORY REPORT")
        self.setFont("Helvetica", 8)
        self.drawRightString(558, 750, datetime.now().strftime("%B %Y"))
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)
        
        # Footer
        self.line(54, 50, 558, 50)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 38, page_str)
        self.drawString(54, 38, "Confidential - Financial Advisory Services")
        self.restoreState()

# Indian Rupee Formatting Helper Function
def format_inr(val) -> str:
    if val is None or val == "" or str(val).strip().lower() in ["none", "n/a", "null", "nan", ""]:
        return "N/A"
        
    try:
        numeric_val = float(val)
    except (ValueError, TypeError):
        return str(val)
        
    s = f"{numeric_val:.2f}"
    parts = s.split('.')
    num = parts[0]
    dec = parts[1] if len(parts) > 1 else "00"
    
    is_negative = num.startswith('-')
    if is_negative:
        num = num[1:]
        
    if len(num) <= 3:
        res = num
    else:
        last_three = num[-3:]
        remaining = num[:-3]
        groups = []
        while len(remaining) > 0:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        res = ",".join(groups) + "," + last_three
        
    return f"{'-' if is_negative else ''}Rs. {res}.{dec}"

# Safe float conversion helper
def safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# Matplotlib chart generator
def generate_report_charts(json_data: dict, temp_dir: str) -> Dict[str, str]:
    os.makedirs(temp_dir, exist_ok=True)
    chart_paths = {}
    
    positions = json_data.get("consolidated_positions", [])
    rebal_data = json_data.get("rebalancing_recommendations", [])
    
    if not positions:
        return chart_paths
        
    # Styles
    plt.style.use('ggplot')
    colors_list = ['#6C5CE7', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#a29bfe', '#60A5FA', '#34D399', '#94A3B8']
    
    # 1. Current Allocation Pie Chart
    tickers = [p["normalized_ticker"] for p in positions]
    current_values = []
    for p in positions:
        val = p.get("current_value")
        if val is None:
            val = safe_float(p.get("quantity")) * safe_float(p.get("average_price"))
        else:
            val = safe_float(val)
        current_values.append(val)
    total_val = sum(current_values)
    current_shares = [v / total_val * 100 for v in current_values] if total_val > 0 else [0]*len(positions)
    
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    wedges, texts, autotexts = ax.pie(current_shares, labels=tickers, autopct='%1.1f%%', startangle=140, colors=colors_list[:len(tickers)])
    plt.setp(autotexts, size=7, weight="bold", color="white")
    plt.setp(texts, size=7)
    ax.set_title("Current Allocation", fontsize=9, weight="bold", pad=8)
    plt.tight_layout()
    curr_chart_path = os.path.join(temp_dir, "current_allocation.png")
    plt.savefig(curr_chart_path, dpi=150)
    plt.close()
    chart_paths["current_allocation"] = curr_chart_path
    
    # 2. Recommended Allocation Pie Chart
    rebal_map = {item["ticker"]: item["recommended_allocation_pct"] for item in rebal_data}
    rec_weights = [rebal_map.get(t, 0.0) for t in tickers]
    
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    rec_tickers_filtered = [t for t, w in zip(tickers, rec_weights) if w > 0]
    rec_weights_filtered = [w for w in rec_weights if w > 0]
    
    if rec_weights_filtered:
        wedges, texts, autotexts = ax.pie(rec_weights_filtered, labels=rec_tickers_filtered, autopct='%1.1f%%', startangle=140, colors=colors_list[:len(rec_tickers_filtered)])
        plt.setp(autotexts, size=7, weight="bold", color="white")
        plt.setp(texts, size=7)
    else:
        ax.text(0.5, 0.5, "No Allocation (All Sells/Unresolved)", horizontalalignment='center', verticalalignment='center')
    ax.set_title("Recommended Allocation", fontsize=9, weight="bold", pad=8)
    plt.tight_layout()
    rec_chart_path = os.path.join(temp_dir, "recommended_allocation.png")
    plt.savefig(rec_chart_path, dpi=150)
    plt.close()
    chart_paths["recommended_allocation"] = rec_chart_path
    
    # 3. Sector Exposure Horizontal Bar Chart
    sectors_weights = {}
    for pos in positions:
        ticker = pos["normalized_ticker"]
        sec = "Other"
        for item in rebal_data:
            if item["ticker"] == ticker:
                sec = item.get("sector", "Other")
                break
        val = pos.get("current_value")
        if val is None:
            val = safe_float(pos.get("quantity")) * safe_float(pos.get("average_price"))
        else:
            val = safe_float(val)
        sectors_weights[sec] = sectors_weights.get(sec, 0.0) + val
        
    total_sec_val = sum(sectors_weights.values())
    sector_names = list(sectors_weights.keys())
    sector_pcts = [v / total_sec_val * 100 for v in sectors_weights.values()] if total_sec_val > 0 else [0]*len(sector_names)
    
    sorted_idx = np.argsort(sector_pcts)
    sector_names = [sector_names[i] for i in sorted_idx]
    sector_pcts = [sector_pcts[i] for i in sorted_idx]
    
    fig, ax = plt.subplots(figsize=(5, 2.5))
    bars = ax.barh(sector_names, sector_pcts, color='#3B82F6')
    ax.set_xlabel("Exposure (%)", fontsize=7)
    ax.set_title("Sector Exposure Distribution", fontsize=9, weight="bold", pad=8)
    plt.setp(ax.get_yticklabels(), fontsize=7)
    plt.setp(ax.get_xticklabels(), fontsize=7)
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{width:.1f}%', 
                va='center', ha='left', fontsize=7, color='#475569')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    sector_chart_path = os.path.join(temp_dir, "sector_exposure.png")
    plt.savefig(sector_chart_path, dpi=150)
    plt.close()
    chart_paths["sector_exposure"] = sector_chart_path
    
    # 4. Recommendation Distribution
    rec_counts = {"Buy/Accumulate": 0.0, "Hold/Neutral": 0.0, "Sell/Reduce": 0.0, "No Coverage": 0.0}
    for item in rebal_data:
        rec = item.get("recommendation", "").lower()
        val = safe_float(item.get("current_value"))
        if "buy" in rec or "accumulate" in rec:
            rec_counts["Buy/Accumulate"] += val
        elif "hold" in rec or "neutral" in rec:
            rec_counts["Hold/Neutral"] += val
        elif "sell" in rec or "reduce" in rec:
            rec_counts["Sell/Reduce"] += val
        else:
            rec_counts["No Coverage"] += val
            
    total_rec_val = sum(rec_counts.values())
    rec_labels = list(rec_counts.keys())
    rec_vals = [v / total_rec_val * 100 for v in rec_counts.values()] if total_rec_val > 0 else [0]*len(rec_labels)
    
    rec_labels_filtered = [l for l, v in zip(rec_labels, rec_vals) if v > 0]
    rec_vals_filtered = [v for v in rec_vals if v > 0]
    
    fig, ax = plt.subplots(figsize=(5, 2.5))
    if rec_vals_filtered:
        bars = ax.bar(rec_labels_filtered, rec_vals_filtered, color=['#10B981', '#F59E0B', '#EF4444', '#94A3B8'][:len(rec_vals_filtered)])
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f'{yval:.1f}%', 
                    va='bottom', ha='center', fontsize=7, color='#475569')
    else:
        ax.text(0.5, 0.5, "No Ratings Data", horizontalalignment='center', verticalalignment='center')
    ax.set_ylabel("Exposure (%)", fontsize=7)
    ax.set_title("Analyst Recommendation Distribution (Value-Weighted)", fontsize=9, weight="bold", pad=8)
    plt.setp(ax.get_xticklabels(), fontsize=7)
    plt.setp(ax.get_yticklabels(), fontsize=7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    rec_dist_path = os.path.join(temp_dir, "recommendation_distribution.png")
    plt.savefig(rec_dist_path, dpi=150)
    plt.close()
    chart_paths["recommendation_distribution"] = rec_dist_path
    
    return chart_paths

# Executive Summary Generator
def generate_exec_summary(health_data: dict, rebalancing_data: List[dict]) -> str:
    health_score = health_data.get("health_score", 0)
    
    if health_score >= 80:
        quality_str = "excellent structural health, characterized by high rating consensus, strong analyst coverage, and well-managed risk exposures."
    elif health_score >= 60:
        quality_str = "moderate structural health. While there are sound core allocations, there are several key concentrations or rating misalignments that should be addressed to optimize risk-adjusted returns."
    else:
        quality_str = "elevated risk and weak structural health. There is critical exposure to Sell-rated assets, low rating confidence, or excessive concentration, requiring immediate rebalancing."
        
    strengths = health_data.get("strengths", [])
    weaknesses = health_data.get("weaknesses", [])
    
    strengths_bullets = "\n".join([f"• {s.replace('✓ ', '')}" for s in strengths]) if strengths else "• No major structural strengths identified."
    weaknesses_bullets = "\n".join([f"• {w.replace('✗ ', '')}" for w in weaknesses]) if weaknesses else "• No critical structural weaknesses identified."
    
    increase_actions = [item["ticker"] for item in rebalancing_data if item["action"] == "Increase Exposure"]
    reduce_actions = [item["ticker"] for item in rebalancing_data if item["action"] == "Reduce Exposure"]
    
    action_bullets = []
    if increase_actions:
        action_bullets.append(f"• Increase allocation to high-conviction assets: {', '.join(increase_actions)}.")
    if reduce_actions:
        action_bullets.append(f"• Exit or reduce exposure to Sell-rated or highly concentrated assets: {', '.join(reduce_actions)}.")
    if not action_bullets:
        action_bullets.append("• Maintain current allocations as they align with the target risk profile.")
    actions_str = "\n".join(action_bullets)
    
    summary_text = (
        f"<b>Overall Portfolio Quality:</b><br/>"
        f"The portfolio is currently evaluated at a Portfolio Health Score of {health_score}/100, indicating {quality_str}<br/><br/>"
        f"<b>Primary Strengths:</b><br/>"
        f"{strengths_bullets.replace('\n', '<br/>')}<br/><br/>"
        f"<b>Primary Weaknesses & Risks:</b><br/>"
        f"{weaknesses_bullets.replace('\n', '<br/>')}<br/><br/>"
        f"<b>Most Important Recommended Actions:</b><br/>"
        f"{actions_str.replace('\n', '<br/>')}"
    )
    return summary_text

# PDF Report Generation function
def generate_pdf_report(json_data: dict, output_pdf_path: str):
    # Setup temporary directory for charts
    temp_dir = "temp_report_charts"
    chart_paths = generate_report_charts(json_data, temp_dir)
    
    # Extract data fields
    timestamp_str = json_data.get("timestamp", datetime.now().isoformat())
    date_formatted = datetime.fromisoformat(timestamp_str).strftime("%B %d, %Y")
    
    risk_profile = json_data.get("selected_risk_profile", "Balanced")
    health_data = json_data.get("portfolio_health", {})
    health_score = health_data.get("health_score", 0)
    risk_level = health_data.get("risk_level", "Unknown")
    rebal_data = json_data.get("rebalancing_recommendations", [])
    intel_summary = json_data.get("portfolio_intelligence_summary", {})
    research_reports = json_data.get("research_reports", [])
    positions = json_data.get("consolidated_positions", [])
    
    # Calculate portfolio values
    total_cost = 0.0
    total_val = 0.0
    for p in positions:
        cost = p.get("invested_value")
        if cost is None:
            cost = safe_float(p.get("quantity")) * safe_float(p.get("average_price"))
        else:
            cost = safe_float(cost)
        total_cost += cost
        
        val = p.get("current_value")
        if val is None:
            val = safe_float(p.get("quantity")) * safe_float(p.get("average_price"))
        else:
            val = safe_float(val)
        total_val += val
        
    unrealized_pnl = total_val - total_cost
    pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0
    
    # Initialize Document Template
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )
    
    # Base Styles
    base_styles = getSampleStyleSheet()
    
    # Custom Styles for Premium Advisory Look
    primary_color = colors.HexColor("#6C5CE7")  # Deep Purple
    secondary_color = colors.HexColor("#3B82F6")  # Premium Blue
    dark_slate = colors.HexColor("#1E293B")
    muted_slate = colors.HexColor("#475569")
    light_bg = colors.HexColor("#F8FAFC")
    
    style_cover_title = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        textColor=primary_color,
        spaceAfter=15,
        alignment=1  # Centered
    )
    style_cover_sub = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=14,
        leading=18,
        textColor=secondary_color,
        spaceAfter=150,
        alignment=1  # Centered
    )
    style_cover_meta = ParagraphStyle(
        "CoverMeta",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=muted_slate,
        alignment=1  # Centered
    )
    style_h1 = ParagraphStyle(
        "AdvisoryH1",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )
    style_h2 = ParagraphStyle(
        "AdvisoryH2",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=secondary_color,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    style_body = ParagraphStyle(
        "AdvisoryBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=dark_slate,
        spaceAfter=10
    )
    style_body_bold = ParagraphStyle(
        "AdvisoryBodyBold",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=dark_slate,
        spaceAfter=10
    )
    style_table_header = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=dark_slate
    )
    style_table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=dark_slate
    )
    
    story = []
    
    # ------------------ COVER PAGE ------------------
    story.append(Spacer(1, 150))
    story.append(Paragraph("PORTFOLIO ADVISORY & INTELLIGENCE REPORT", style_cover_title))
    story.append(Paragraph(f"Structural Diagnostics, Exposure Optimization & Rebalancing Summary", style_cover_sub))
    story.append(Paragraph(f"<b>Prepared For:</b> Investment Advisory Client<br/>"
                           f"<b>Selected Risk Profile:</b> {risk_profile}<br/>"
                           f"<b>Analysis Date:</b> {date_formatted}<br/>"
                           f"<b>Status:</b> Completed", style_cover_meta))
    story.append(PageBreak())
    
    # ------------------ SECTION 1: EXECUTIVE SUMMARY ------------------
    story.append(Paragraph("Executive Summary", style_h1))
    exec_summary_text = generate_exec_summary(health_data, rebal_data)
    story.append(Paragraph(exec_summary_text, style_body))
    
    # Diagnostic assessment summary text
    conclusion_text = (
        "<b>Overall Assessment:</b> The portfolio displays a cohesive structure with a primary health score of "
        f"{health_score}/100 and a <b>{risk_level}</b> risk profile. Recommended rebalancing actions "
        f"have been calculated dynamically to align your asset allocations with the target <b>{risk_profile}</b> profile limits. "
        "Exiting Sell-rated assets and trimming overweight positions will significantly reduce single-stock concentration risks."
    )
    story.append(Paragraph(conclusion_text, style_body))
    story.append(Spacer(1, 15))
    
    # ------------------ SECTION 2: PORTFOLIO METRICS & CHARTS ------------------
    story.append(Paragraph("Portfolio Diagnostics & Metrics", style_h1))
    
    # Metrics Table
    metrics_table_data = [
        [Paragraph("<b>Metric Name</b>", style_table_cell_bold), Paragraph("<b>Value</b>", style_table_cell_bold)],
        ["Portfolio Health Score", f"{health_score}/100"],
        ["Portfolio Risk Level", risk_level],
        ["Advisory Risk Profile", risk_profile],
        ["Total Investment Cost", format_inr(total_cost)],
        ["Total Portfolio Current Value", format_inr(total_val)],
        ["Unrealized Profit & Loss", f"{format_inr(unrealized_pnl)} ({'+' if unrealized_pnl >= 0 else ''}{pnl_pct:.2f}%)"]
    ]
    t_metrics = Table(metrics_table_data, colWidths=[250, 254])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_metrics)
    story.append(Spacer(1, 20))
    
    # Add Pie Charts side by side
    if ("current_allocation" in chart_paths and "recommended_allocation" in chart_paths and 
            os.path.exists(chart_paths["current_allocation"]) and os.path.exists(chart_paths["recommended_allocation"])):
        chart_table_data = [
            [Image(chart_paths["current_allocation"], width=230, height=164), 
             Image(chart_paths["recommended_allocation"], width=230, height=164)]
        ]
        t_charts = Table(chart_table_data, colWidths=[252, 252])
        t_charts.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_charts)
        
    story.append(PageBreak())
    
    # ------------------ SECTION 3: CURRENT HOLDINGS & RESEARCH INSIGHTS ------------------
    story.append(Paragraph("Current Holdings & Research Insights", style_h1))
    
    # Holdings table header
    holdings_headers = ["Ticker", "Quantity", "Avg Buy Price", "Current Price", "Current Value", "Alloc %", "Rating", "Confidence"]
    holdings_table_rows = [[Paragraph(h, style_table_header) for h in holdings_headers]]
    
    # Map ticker to research rating and confidence
    reports_map = {r["stock"]: r for r in research_reports}
    
    for pos in positions:
        ticker = pos.get("normalized_ticker", "")
        qty = pos.get("quantity", 0.0)
        avg_price = pos.get("average_price", 0.0)
        curr_price = pos.get("current_price", avg_price)
        curr_value = pos.get("current_value", qty * curr_price)
        alloc_pct = (curr_value / total_val * 100.0) if total_val > 0 else 0.0
        
        report = reports_map.get(ticker, {})
        rating = report.get("recommendation", "N/A")
        confidence = report.get("confidence_score", 0.0)
        conf_str = f"{confidence:.1f}%" if confidence else "N/A"
        
        holdings_table_rows.append([
            Paragraph(ticker, style_table_cell_bold),
            Paragraph(f"{qty:,.2f}", style_table_cell),
            Paragraph(format_inr(avg_price), style_table_cell),
            Paragraph(format_inr(curr_price), style_table_cell),
            Paragraph(format_inr(curr_value), style_table_cell),
            Paragraph(f"{alloc_pct:.1f}%", style_table_cell),
            Paragraph(rating, style_table_cell),
            Paragraph(conf_str, style_table_cell)
        ])
        
    t_holdings = Table(holdings_table_rows, colWidths=[55, 45, 65, 65, 75, 55, 75, 70])
    t_holdings.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_holdings)
    story.append(Spacer(1, 15))
    
    # Add Sector & Ratings bar charts side by side
    if ("sector_exposure" in chart_paths and "recommendation_distribution" in chart_paths and 
            os.path.exists(chart_paths["sector_exposure"]) and os.path.exists(chart_paths["recommendation_distribution"])):
        bar_chart_table = [
            [Image(chart_paths["sector_exposure"], width=245, height=122), 
             Image(chart_paths["recommendation_distribution"], width=245, height=122)]
        ]
        t_bar_charts = Table(bar_chart_table, colWidths=[252, 252])
        t_bar_charts.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_bar_charts)
        
    story.append(PageBreak())
    
    # ------------------ SECTION 4: REBALANCING & ALLOCATION RECOMMENDATIONS ------------------
    story.append(Paragraph("Allocation Recommendations & Rebalancing", style_h1))
    
    rebal_headers = ["Ticker", "Current Alloc", "Target Alloc", "Alloc Change", "Advisory Action", "Recommendation", "Sector"]
    rebal_table_rows = [[Paragraph(rh, style_table_header) for rh in rebal_headers]]
    
    for item in rebal_data:
        ticker = item.get("ticker", "")
        curr_alloc = item.get("current_allocation_pct", 0.0)
        rec_alloc = item.get("recommended_allocation_pct", 0.0)
        change_alloc = item.get("allocation_change_pct", 0.0)
        action = item.get("action", "")
        rec = item.get("recommendation", "")
        sec = item.get("sector", "")
        
        # Color coding for Action cell
        action_color = "#475569"
        if action == "Increase Exposure":
            action_color = "#10B981"
        elif action == "Reduce Exposure":
            action_color = "#EF4444"
            
        action_paragraph = Paragraph(f"<font color='{action_color}'><b>{action}</b></font>", style_table_cell)
        
        rebal_table_rows.append([
            Paragraph(ticker, style_table_cell_bold),
            Paragraph(f"{curr_alloc:.1f}%", style_table_cell),
            Paragraph(f"{rec_alloc:.1f}%", style_table_cell),
            Paragraph(f"{'+' if change_alloc > 0 else ''}{change_alloc:.1f}%", style_table_cell),
            action_paragraph,
            Paragraph(rec, style_table_cell),
            Paragraph(sec, style_table_cell)
        ])
        
    t_rebal = Table(rebal_table_rows, colWidths=[55, 65, 65, 65, 95, 80, 79])
    t_rebal.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), secondary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_rebal)
    story.append(Spacer(1, 20))
    
    # ------------------ SECTION 5: MARKET INTELLIGENCE ------------------
    market_intel = json_data.get("market_intelligence")
    if market_intel:
        story.append(Paragraph("Market Intelligence & Technical Diagnostics", style_h1))
        
        overall_score = market_intel.get("overall_score", 50)
        tech_score = market_intel.get("technical_score", 50)
        deriv_score = market_intel.get("derivatives_score", 50)
        liq_score = market_intel.get("liquidity_score", 50)
        breadth_score = market_intel.get("market_breadth_score", 50)
        
        summaries = market_intel.get("summaries", {})
        overall_sum = summaries.get("overall", "Overall market intelligence diagnostics completed.")
        tech_sum = summaries.get("technical", "Technical trend analysis and momentum tracking.")
        deriv_sum = summaries.get("derivatives", "Institutional positioning and open interest build-ups.")
        liq_sum = summaries.get("liquidity", "Liquidity depth and volume breakout metrics.")
        breadth_sum = summaries.get("breadth", "Market breadth and relative strength vs. index.")
        
        story.append(Paragraph(f"<b>Overall Market Intelligence Score:</b> {overall_score}/100", style_body_bold))
        story.append(Paragraph(overall_sum, style_body))
        
        intel_table_data = [
            [Paragraph("<b>Intelligence Engine</b>", style_table_cell_bold), Paragraph("<b>Score</b>", style_table_cell_bold), Paragraph("<b>Executive Summary</b>", style_table_cell_bold)],
            ["Technical Analysis", f"{tech_score}/100", Paragraph(tech_sum, style_table_cell)],
            ["Derivatives Positioning", f"{deriv_score}/100", Paragraph(deriv_sum, style_table_cell)],
            ["Liquidity Profile", f"{liq_score}/100", Paragraph(liq_sum, style_table_cell)],
            ["Market Breadth Index", f"{breadth_score}/100", Paragraph(breadth_sum, style_table_cell)]
        ]
        t_intel = Table(intel_table_data, colWidths=[130, 50, 324])
        t_intel.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_intel)
        story.append(Spacer(1, 15))
        story.append(PageBreak())
        
    # ------------------ SECTION 6: FINAL ASSESSMENT ------------------
    story.append(Paragraph("Final Portfolio Assessment & Disclaimers", style_h1))
    
    disclaimer_text = (
        "<b>Advisory Note:</b> The recommendations generated in this report are structured, rule-based allocations "
        "derived from independent broker research and quantitative risk indicators matching your selected risk profile. "
        "These target weights do not constitute direct trading orders or guaranteed financial outcomes. "
        "Please consult a certified financial advisor before executing large rebalancing actions.<br/><br/>"
        "<i>Report generated automatically by the AI Portfolio Analyzer Client Advisory Engine.</i>"
    )
    story.append(Paragraph(disclaimer_text, style_body))
    
    # Build PDF Document
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Cleanup temp charts
    for path in chart_paths.values():
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass
