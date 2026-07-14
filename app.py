import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
from PIL import Image
from analyzer import extract_portfolio_from_image, normalize_stock_name
from research import ResearchManager
from advisory import PortfolioAdvisoryEngine
from report_generator import generate_pdf_report, generate_report_charts
from market_intelligence import MarketIntelligenceManager
from market_data import YahooFinanceProvider, MockProvider

# Configure page settings
st.set_page_config(
    page_title="AI Portfolio Analyzer MVP",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        
    return f"{'-' if is_negative else ''}₹{res}.{dec}"

# Factor Breakdown Formatting Helper
def format_factors_breakdown(factors) -> str:
    if not factors or not isinstance(factors, dict):
        return "N/A"
        
    labels = {
        "analyst_sentiment": "Analyst Sentiment",
        "target_upside": "Target Upside",
        "revenue_growth": "Revenue Growth",
        "profitability_outlook": "Profitability Outlook",
        "balance_sheet_strength": "Balance Sheet",
        "sector_outlook": "Sector Outlook",
        "risk_factors": "Risk Factors",
        "valuation_concerns": "Valuation Concerns"
    }
    
    lines = []
    for key, label in labels.items():
        val = str(factors.get(key, "neutral")).strip().lower()
        if key in ["risk_factors", "valuation_concerns"]:
            if "low" in val:
                symbol = "✓"
            elif "high" in val:
                symbol = "✗"
            else:
                symbol = "○"
        else:
            if "positive" in val:
                symbol = "✓"
            elif "negative" in val:
                symbol = "✗"
            else:
                symbol = "○"
        lines.append(f"{symbol} {label}: {val.capitalize()}")
        
    return "\n".join(lines)



# Custom CSS for a premium look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6C5CE7, #a29bfe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #A0AEC0;
        margin-bottom: 2rem;
    }
    
    .card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        margin-bottom: 1.5rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 0.25rem;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #6C5CE7, #5849D6);
        color: white;
        border: none;
        padding: 0.6rem 1.8rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(108, 92, 231, 0.4);
    }
    
    /* Center columns vertically */
    .valign-center {
        display: flex;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# Ensure outputs directory exists
OUTPUTS_DIR = "outputs"
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# App Title & Description
st.markdown("<h1 class='main-header'>AI Portfolio Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Upload screenshots of your investment portfolio to automatically extract and normalize stock holdings.</p>", unsafe_allow_html=True)

# Sidebar configuration
st.sidebar.image("https://img.icons8.com/fluent/96/000000/portfolio.png", width=80)
st.sidebar.markdown("### Configuration")

# Load API Key from environment
from dotenv import load_dotenv
load_dotenv()
active_api_key = os.getenv("GEMINI_API_KEY", "")
openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
research_provider = os.getenv("RESEARCH_PROVIDER", "openrouter").lower()
openrouter_model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct:free")

# Developer Mode Toggle
developer_mode = st.sidebar.checkbox("Developer Mode (Debug & API status)", value=False)

# Provider status indicator UI
if developer_mode:
    st.sidebar.markdown("#### ⚙️ Active AI Providers")
    
    # Gemini Vision Status
    if active_api_key:
        st.sidebar.success("🟢 **Gemini Vision**\nOCR & Image Understanding\n*(Configured)*")
    else:
        st.sidebar.error("🔴 **Gemini Vision**\nOCR & Image Understanding\n*(Key Missing)*")
    
    # Research Provider Status
    if research_provider == "gemini":
        if active_api_key:
            st.sidebar.success("🟢 **Gemini Research**\nText Analysis & Grounding\n*(Active)*")
        else:
            st.sidebar.error("🔴 **Gemini Research**\nText Analysis & Grounding\n*(Key Missing)*")
    else:
        # OpenRouter provider status
        if openrouter_api_key and "your_actual" not in openrouter_api_key:
            st.sidebar.success(f"🟢 **OpenRouter Research**\nSummaries & Recommendations\n*Model: {openrouter_model}*")
        else:
            st.sidebar.warning(f"🟡 **OpenRouter Research**\nSummaries & Recommendations\n*Model: {openrouter_model}*\n*(Key Missing)*")
    
    # Nirmal Bang Grounding Status
    st.sidebar.info("🟢 **Nirmal Bang Research**\nWeb Scraper Grounding\n*(Integrated)*")

# Risk Profile Selection
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Risk Profile Selector")
selected_risk_profile = st.sidebar.selectbox(
    "Choose Risk Profile",
    options=["Balanced", "Conservative", "Aggressive"],
    index=0,
    help="Determines the target concentration limits, sector weighting biases, and advisory rebalancing recommendations."
)

# Cache Control
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Cache Control")
force_refresh_cache = st.sidebar.checkbox(
    "Force Refresh Research", 
    value=False,
    help="Bypasses the 24-hour cache and forces a live web search & analysis for all portfolio stocks."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### MVP Capabilities")
st.sidebar.markdown("- 📸 Extract stocks from multiple screenshots")
st.sidebar.markdown("- 🔍 Standardize stock names/tickers")
st.sidebar.markdown("- 📁 Export data to JSON for research")

# Main Content Area
if not active_api_key:
    st.error(
        "### 🔴 System Configuration Error\n\n"
        "The **`GEMINI_API_KEY`** environment variable is not configured. "
        "Please set this variable in the system environment or a `.env` file in the project directory, "
        "then restart the server. Contact the system administrator if this issue persists."
    )
    st.stop()

col_upload, col_preview = st.columns([1.2, 0.8])

uploaded_files = []
with col_upload:
    st.markdown("### 1. Upload Portfolio Screenshots")
    uploaded_files = st.file_uploader(
        "Choose one or more portfolio screenshot images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

with col_preview:
    if uploaded_files:
        st.markdown("### Upload Previews")
        # Create a horizontal thumbnail display for uploaded images
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, file in enumerate(uploaded_files):
            col_idx = idx % 4
            with cols[col_idx]:
                image = Image.open(file)
                st.image(image, use_container_width=True, caption=file.name)

# Trigger analysis button
if uploaded_files:
    st.markdown("---")
    analyze_button = st.button("Analyze Portfolio Screenshots")
    
    if analyze_button:
        all_extracted_positions = []
        
        # We will create a temporary directory to save uploaded images for analysis
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        success_count = 0
        total_files = len(uploaded_files)
        
        for idx, file in enumerate(uploaded_files):
            status_text.markdown(f"**Analyzing {file.name}...** (File {idx+1}/{total_files})")
            
            # Save file to temp location
            temp_path = os.path.join(temp_dir, file.name)
            with open(temp_path, "wb") as f:
                f.write(file.getvalue())
            
            try:
                # Call Gemini vision parser
                portfolio_data = extract_portfolio_from_image(temp_path, api_key=active_api_key)
                
                # Normalize and collect positions
                overall_portfolio_value = getattr(portfolio_data, "overall_portfolio_value", None)
                positions_list = getattr(portfolio_data, "positions", [])
                for pos in positions_list:
                    normalized = normalize_stock_name(pos.ticker_or_name)
                    
                    # Extract attributes safely using getattr
                    quantity = getattr(pos, "quantity", 0.0)
                    average_price = getattr(pos, "average_price", 0.0)
                    pos_current_price = getattr(pos, "current_price", None)
                    pos_current_value = getattr(pos, "current_value", None)
                    pos_todays_pnl = getattr(pos, "todays_pnl", None)
                    
                    # Calculate screenshot-derived values
                    invested_value = quantity * average_price
                    
                    # Current price: use extracted current_price, fallback to average_price
                    current_price = pos_current_price if pos_current_price is not None else average_price
                    
                    # Current value: use extracted current_value, fallback to quantity * current_price
                    current_value = pos_current_value if pos_current_value is not None else (quantity * current_price)
                    
                    todays_pnl = pos_todays_pnl if pos_todays_pnl is not None else 0.0
                    
                    all_extracted_positions.append({
                        "original_name": getattr(pos, "ticker_or_name", "UNKNOWN"),
                        "normalized_ticker": normalized,
                        "quantity": quantity,
                        "average_price": average_price,
                        "invested_value": invested_value,
                        "current_price": current_price,
                        "current_value": current_value,
                        "todays_pnl": todays_pnl,
                        "overall_portfolio_value": overall_portfolio_value,
                        
                        # RAW EXTRACTIONS (Phase 2 Debugging)
                        "raw_name": getattr(pos, "ticker_or_name", "UNKNOWN"),
                        "raw_quantity": getattr(pos, "quantity", None),
                        "raw_average_price": getattr(pos, "average_price", None),
                        "raw_current_price": getattr(pos, "current_price", None),
                        "raw_current_value": getattr(pos, "current_value", None),
                        "raw_todays_pnl": getattr(pos, "todays_pnl", None),
                        
                        "source_file": file.name
                    })
                success_count += 1
            except Exception as e:
                st.error(f"Failed to analyze {file.name}: {str(e)}")
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            progress_bar.progress(int((idx + 1) / total_files * 100))
            
        # Clean up temp folder
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass
                
        status_text.markdown(f"**Analysis complete!** Successfully processed {success_count} of {total_files} files.")
        
        if all_extracted_positions:
            # Convert to DataFrame
            df = pd.DataFrame(all_extracted_positions)
            
            # Group by normalized ticker to combine holdings across multiple screenshots
            df_grouped = df.groupby("normalized_ticker").agg({
                "quantity": "sum",
                # Weighted average price
                "average_price": lambda x: (x * df.loc[x.index, "quantity"]).sum() / df.loc[x.index, "quantity"].sum() if df.loc[x.index, "quantity"].sum() > 0 else 0,
                "invested_value": "sum",
                # Weighted average current price
                "current_price": lambda x: (x * df.loc[x.index, "quantity"]).sum() / df.loc[x.index, "quantity"].sum() if df.loc[x.index, "quantity"].sum() > 0 else 0,
                "current_value": "sum",
                "todays_pnl": "sum",
                "original_name": lambda x: ", ".join(set(x)),
                "source_file": lambda x: ", ".join(set(x))
            }).reset_index()
            
            # Calculate Unrealized P&L and P&L % for consolidated holdings
            df_grouped["unrealized_pnl"] = df_grouped["current_value"] - df_grouped["invested_value"]
            df_grouped["pnl_pct"] = df_grouped.apply(
                lambda r: (r["unrealized_pnl"] / r["invested_value"] * 100) if r["invested_value"] > 0 else 0.0,
                axis=1
            )
            
            # Retrieve Research Reports for the stocks (Phase 3)
            status_text.markdown("**Retrieving broker research reports...**")
            unique_stocks = df_grouped["normalized_ticker"].tolist()
            try:
                openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
                manager = ResearchManager(
                    api_key=active_api_key,
                    openrouter_key=openrouter_api_key
                )
                research_results = manager.get_portfolio_research(
                    unique_stocks,
                    force_refresh=force_refresh_cache
                )
                research_data = [report.model_dump() for report in research_results]
            except Exception as re_err:
                st.warning(f"Research retrieval failed: {str(re_err)}")
                research_data = []
            
            # Calculate Portfolio Health Metrics & Advisory Suggestions (Phase 5)
            status_text.markdown("**Evaluating portfolio health score & risk profile...**")
            try:
                from health import PortfolioHealthEngine
                from advisory import PortfolioAdvisoryEngine
                
                health_engine = PortfolioHealthEngine()
                advisory_engine = PortfolioAdvisoryEngine()
                
                # Evaluate health with selected risk profile
                health_data = health_engine.evaluate_portfolio(
                    df_grouped.to_dict(orient="records"),
                    research_data,
                    selected_risk_profile
                )
                
                # Generate rebalancing recommendations
                rebalancing_data = advisory_engine.generate_allocation_recommendations(
                    df_grouped.to_dict(orient="records"),
                    research_data,
                    selected_risk_profile
                )
                
                # Generate intelligence summary
                intel_summary = advisory_engine.generate_intelligence_summary(
                    health_data,
                    rebalancing_data,
                    df_grouped.to_dict(orient="records")
                )
            except Exception as health_err:
                st.warning(f"Portfolio health evaluation/advisory failed: {str(health_err)}")
                health_data = {
                    "health_score": 0,
                    "risk_level": "Unknown",
                    "strengths": ["Evaluation error"],
                    "weaknesses": ["Evaluation error"],
                    "risk_flags": [f"Error: {str(health_err)}"]
                }
                rebalancing_data = []
                intel_summary = {}
                
            # Generate Market Intelligence Analysis (Phase 8)
            try:
                status_text.markdown("**Analyzing market intelligence (Technical, Derivatives, Liquidity)...**")
                provider = YahooFinanceProvider(fallback_provider=MockProvider())
                market_intel_manager = MarketIntelligenceManager(provider)
                tickers = [pos["normalized_ticker"] for pos in df_grouped.to_dict(orient="records")]
                market_intel_data = market_intel_manager.evaluate_market_intelligence(tickers)
            except Exception as intel_err:
                st.warning(f"Market intelligence analysis failed: {str(intel_err)}")
                market_intel_data = {
                    "overall_score": 50,
                    "technical_score": 50,
                    "derivatives_score": 50,
                    "liquidity_score": 50,
                    "market_breadth_score": 50,
                    "summaries": {
                        "overall": f"Market intelligence calculation failed: {str(intel_err)}",
                        "technical": "Data unavailable.",
                        "derivatives": "Data unavailable.",
                        "liquidity": "Data unavailable.",
                        "breadth": "Data unavailable."
                    },
                    "stock_details": {}
                }
            
            # Save final data to JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"portfolio_extraction_{timestamp}.json"
            output_filepath = os.path.join(OUTPUTS_DIR, output_filename)
            
            json_payload = {
                "timestamp": datetime.now().isoformat(),
                "selected_risk_profile": selected_risk_profile,
                "extracted_positions": all_extracted_positions,
                "consolidated_positions": df_grouped.to_dict(orient="records"),
                "research_reports": research_data,
                "portfolio_health": health_data,
                "rebalancing_recommendations": rebalancing_data,
                "portfolio_intelligence_summary": intel_summary,
                "market_intelligence": market_intel_data
            }
            
            with open(output_filepath, "w") as f:
                json.dump(json_payload, f, indent=4)
                
            # Pre-generate PDF report
            pdf_filepath = output_filepath.replace(".json", ".pdf")
            try:
                generate_pdf_report(json_payload, pdf_filepath)
            except Exception as pdf_err:
                st.warning(f"PDF generation failed: {pdf_err}")
                pdf_filepath = None
                
            st.session_state["last_analysis_results"] = {
                "df_grouped": df_grouped,
                "df_individual": df,
                "json_path": output_filepath,
                "json_data": json_payload,
                "pdf_path": pdf_filepath
            }
            
            st.success(f"Analysis saved to outputs/{output_filename}")
        else:
            st.error("No positions could be extracted from the uploaded files. Please verify that the screenshots are clear, readable, and contain a portfolio holdings table.")

# Display Analysis Results if available in session state
if "last_analysis_results" in st.session_state:
    results = st.session_state["last_analysis_results"]
    df_grouped = results["df_grouped"]
    df_individual = results["df_individual"]
    json_path = results["json_path"]
    json_data = results["json_data"]
    
    # Ensure Market Intelligence is present in the loaded JSON (for older saves)
    if "market_intelligence" not in json_data:
        try:
            provider = YahooFinanceProvider(fallback_provider=MockProvider())
            market_intel_manager = MarketIntelligenceManager(provider)
            tickers = [pos["normalized_ticker"] for pos in df_grouped.to_dict(orient="records")]
            market_intel_data = market_intel_manager.evaluate_market_intelligence(tickers)
            json_data["market_intelligence"] = market_intel_data
            
            with open(json_path, "w") as f:
                json.dump(json_data, f, indent=4)
                
            results["json_data"] = json_data
            st.session_state["last_analysis_results"] = results
        except Exception as intel_err:
            pass
            
    # Ensure PDF exists or generate on the fly
    pdf_path = results.get("pdf_path") or json_path.replace(".json", ".pdf")
    if not os.path.exists(pdf_path):
        try:
            generate_pdf_report(json_data, pdf_path)
            results["pdf_path"] = pdf_path
            st.session_state["last_analysis_results"] = results
        except Exception as pdf_err:
            st.warning(f"PDF auto-generation on load failed: {pdf_err}")
    
    # Recalculate health & advisory on the fly if the risk profile changed
    current_saved_profile = json_data.get("selected_risk_profile", "Balanced")
    if current_saved_profile != selected_risk_profile:
        try:
            from health import PortfolioHealthEngine
            from advisory import PortfolioAdvisoryEngine
            
            health_engine = PortfolioHealthEngine()
            advisory_engine = PortfolioAdvisoryEngine()
            
            research_data = json_data.get("research_reports", [])
            positions_list = json_data.get("consolidated_positions", [])
            
            # Re-evaluate health
            health_data = health_engine.evaluate_portfolio(
                positions_list,
                research_data,
                selected_risk_profile
            )
            
            # Re-evaluate rebalancing
            rebalancing_data = advisory_engine.generate_allocation_recommendations(
                positions_list,
                research_data,
                selected_risk_profile
            )
            
            # Re-evaluate intelligence summary
            intel_summary = advisory_engine.generate_intelligence_summary(
                health_data,
                rebalancing_data,
                positions_list
            )
            
            # Update json_data
            json_data["selected_risk_profile"] = selected_risk_profile
            json_data["portfolio_health"] = health_data
            json_data["rebalancing_recommendations"] = rebalancing_data
            json_data["portfolio_intelligence_summary"] = intel_summary
            
            # Re-save file
            with open(json_path, "w") as f:
                json.dump(json_data, f, indent=4)
                
            # Regenerate PDF report on recalculation
            try:
                generate_pdf_report(json_data, pdf_path)
                results["pdf_path"] = pdf_path
            except Exception as pdf_err:
                st.warning(f"PDF regeneration failed: {pdf_err}")
                
            # Update session state
            results["json_data"] = json_data
            st.session_state["last_analysis_results"] = results
        except Exception as e:
            st.error(f"Failed to dynamically recalculate portfolio advice: {e}")
    
    st.markdown("---")
    st.markdown("### Portfolio Analysis Dashboard")
    
    # Raw Gemini Extraction Expander (Debugging Section)
    if developer_mode:
        with st.expander("🛠️ Raw Gemini Extraction (Debugging)", expanded=False):
            st.markdown("This table displays the exact, raw data extracted by the Gemini Vision API before any stock name normalization, portfolio consolidation, or price calculations are applied. Use this to verify accuracy against your screenshots.")
            
            df_raw = df_individual.copy()
            raw_cols = {
                "raw_name": "Stock Name",
                "raw_quantity": "Quantity",
                "raw_average_price": "Average Buy Price (₹)",
                "raw_current_price": "Current Price (₹)",
                "raw_current_value": "Current Value (₹)",
                "source_file": "Source File"
            }
            
            # Fallback to standard columns if raw columns are not in df (for older saves)
            for raw_key, label in raw_cols.items():
                if raw_key not in df_raw.columns:
                    if raw_key == "raw_name":
                        df_raw["raw_name"] = df_raw["original_name"] if "original_name" in df_raw.columns else "N/A"
                    elif raw_key == "raw_quantity":
                        df_raw["raw_quantity"] = df_raw["quantity"]
                    elif raw_key == "raw_average_price":
                        df_raw["raw_average_price"] = df_raw["average_price"]
                    elif raw_key == "raw_current_price":
                        df_raw["raw_current_price"] = df_raw.get("current_price", None)
                    elif raw_key == "raw_current_value":
                        df_raw["raw_current_value"] = df_raw.get("current_value", None)
                        
            df_raw_display = df_raw.rename(columns=raw_cols)
            cols_to_show_raw = ["Stock Name", "Quantity", "Average Buy Price (₹)", "Current Price (₹)", "Current Value (₹)", "Source File"]
            cols_to_show_raw = [col for col in cols_to_show_raw if col in df_raw_display.columns]
            df_raw_display = df_raw_display[cols_to_show_raw]
            
            st.dataframe(
                df_raw_display.style.format({
                    "Quantity": lambda x: f"{x:,.2f}" if pd.notnull(x) and isinstance(x, (int, float)) else str(x) if pd.notnull(x) else "N/A",
                    "Average Buy Price (₹)": format_inr,
                    "Current Price (₹)": format_inr,
                    "Current Value (₹)": format_inr
                }),
                use_container_width=True,
                hide_index=True
            )
    
    # Key Summary Cards
    # Calculate financial metrics
    total_invested_cost = df_grouped["invested_value"].sum() if "invested_value" in df_grouped.columns else df_grouped["total_value"].sum()
    total_current_value = df_grouped["current_value"].sum() if "current_value" in df_grouped.columns else df_grouped["total_value"].sum()
    
    total_unrealized_pnl = total_current_value - total_invested_cost
    total_pnl_pct = (total_unrealized_pnl / total_invested_cost * 100) if total_invested_cost > 0 else 0.0
    
    pnl_color = "#10B981" if total_unrealized_pnl >= 0 else "#EF4444"
    pnl_symbol = "+" if total_unrealized_pnl >= 0 else ""
    
    # Executive Summary Card Section
    st.markdown("### 📊 Executive Summary")
    
    col_exec1, col_exec2, col_exec3 = st.columns(3)
    
    health_data = json_data.get("portfolio_health", {})
    health_score = health_data.get("health_score", 0)
    risk_level = health_data.get("risk_level", "Unknown")
    market_intel_score = json_data.get("market_intelligence", {}).get("overall_score", 50)
    research_reports = json_data.get("research_reports", [])
    
    buy_count = sum(1 for r in research_reports if "buy" in r.get("recommendation", "").lower() or "accumulate" in r.get("recommendation", "").lower())
    hold_count = sum(1 for r in research_reports if "hold" in r.get("recommendation", "").lower() or "neutral" in r.get("recommendation", "").lower())
    sell_count = sum(1 for r in research_reports if "sell" in r.get("recommendation", "").lower() or "reduce" in r.get("recommendation", "").lower())
    
    if buy_count > hold_count and buy_count > sell_count:
        consensus_label = "🟢 Bullish (Buy)"
    elif sell_count > buy_count and sell_count > hold_count:
        consensus_label = "🔴 Bearish (Sell)"
    else:
        consensus_label = "🟡 Neutral (Hold)"
        
    with col_exec1:
        st.markdown(f"""
        <div class='card' style='border-left: 4px solid #6C5CE7;'>
            <div class='metric-label'>Overall Portfolio Score</div>
            <div class='metric-value' style='color: #a29bfe;'>{health_score}/100</div>
            <div class='metric-sub'>Risk Profile: <b>{risk_level}</b></div>
        </div>
        """, unsafe_allow_html=True)
    with col_exec2:
        st.markdown(f"""
        <div class='card' style='border-left: 4px solid #3B82F6;'>
            <div class='metric-label'>Market Intelligence Score</div>
            <div class='metric-value' style='color: #60A5FA;'>{market_intel_score}/100</div>
            <div class='metric-sub'>Quantitative Outlook</div>
        </div>
        """, unsafe_allow_html=True)
    with col_exec3:
        st.markdown(f"""
        <div class='card' style='border-left: 4px solid #10B981;'>
            <div class='metric-label'>Research Consensus</div>
            <div class='metric-value' style='color: #34D399;'>{consensus_label}</div>
            <div class='metric-sub'>Analyst Ratings ({buy_count} Buy / {hold_count} Hold / {sell_count} Sell)</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("##### 🔍 Key Insights & Suggested Actions")
    col_ins1, col_ins2, col_ins3 = st.columns(3)
    
    intel_summary = json_data.get("portfolio_intelligence_summary", {})
    opps = intel_summary.get("top_opportunities", [])
    risks = intel_summary.get("key_risks", [])
    rebal_actions = intel_summary.get("rebalancing_actions_summary", [])
    
    with col_ins1:
        opp_val = opps[0] if opps else "No clear buying opportunity identified."
        st.info(f"**Top Opportunity:**\n{opp_val}")
    with col_ins2:
        risk_val = risks[0] if risks else "No major concentration or exposure risks detected."
        st.warning(f"**Largest Risk:**\n{risk_val}")
    with col_ins3:
        act_val = rebal_actions[0] if rebal_actions else "Maintain current allocations."
        st.success(f"**Suggested Action:**\n{act_val}")
        
    st.markdown("---")
    st.markdown("### 📈 Financial Metrics & Performance")
    
    col_card1, col_card2, col_card3, col_card4 = st.columns(4)
    with col_card1:
        st.markdown(f"""
        <div class='card'>
            <div class='metric-label'>Total Investment</div>
            <div class='metric-value'>{format_inr(total_invested_cost)}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_card2:
        st.markdown(f"""
        <div class='card'>
            <div class='metric-label'>Current Value</div>
            <div class='metric-value'>{format_inr(total_current_value)}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_card3:
        st.markdown(f"""
        <div class='card' style='border-left: 4px solid {pnl_color};'>
            <div class='metric-label'>Unrealized P&L</div>
            <div class='metric-value' style='color: {pnl_color};'>{pnl_symbol}{format_inr(total_unrealized_pnl)}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_card4:
        st.markdown(f"""
        <div class='card' style='border-left: 4px solid {pnl_color};'>
            <div class='metric-label'>P&L Percentage</div>
            <div class='metric-value' style='color: {pnl_color};'>{pnl_symbol}{total_pnl_pct:,.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Tab Layout for Consolidated vs Detailed view
    tab_cons, tab_research, tab_market_intel, tab_rebal, tab_health, tab_visuals, tab_report, tab_det, tab_raw = st.tabs([
        "Portfolio Holdings", 
        "Research Consensus", 
        "Market Intelligence",
        "Portfolio Optimization", 
        "Portfolio Health",
        "Portfolio Visualizations",
        "Report Center",
        "Individual Extractions", 
        "Exported JSON"
    ])
    
    with tab_cons:
        st.markdown("#### Consolidated Stock Holdings")
        st.markdown("Stock holdings merged and normalized across all uploaded screenshots.")
        
        # Display pretty dataframe
        display_df = df_grouped.copy()
        
        # Add missing columns if loading older saves
        if "invested_value" not in display_df.columns and "total_value" in display_df.columns:
            display_df["invested_value"] = display_df["total_value"]
            display_df["current_price"] = display_df["average_price"]
            display_df["current_value"] = display_df["total_value"]
            display_df["unrealized_pnl"] = 0.0
            display_df["pnl_pct"] = 0.0
            
        display_df = display_df.rename(columns={
            "normalized_ticker": "Normalized Ticker",
            "quantity": "Total Quantity",
            "average_price": "Avg Buy Price (₹)",
            "invested_value": "Total Investment (₹)",
            "current_price": "Current Price (₹)",
            "current_value": "Current Value (₹)",
            "unrealized_pnl": "Unrealized P&L (₹)",
            "pnl_pct": "P&L %",
            "original_name": "Extracted Names",
            "source_file": "Source Screenshots"
        })
        
        # Select columns to display in a clean order
        columns_to_show = [
            "Normalized Ticker", "Total Quantity", "Avg Buy Price (₹)", "Total Investment (₹)",
            "Current Price (₹)", "Current Value (₹)", "Unrealized P&L (₹)", "P&L %",
            "Extracted Names", "Source Screenshots"
        ]
        
        # Only select columns that actually exist
        columns_to_show = [col for col in columns_to_show if col in display_df.columns]
        display_df = display_df[columns_to_show]
        
        # Format currency/decimal columns
        st.dataframe(
            display_df.style.format({
                "Total Quantity": "{:,.2f}",
                "Avg Buy Price (₹)": format_inr,
                "Total Investment (₹)": format_inr,
                "Current Price (₹)": format_inr,
                "Current Value (₹)": format_inr,
                "Unrealized P&L (₹)": format_inr,
                "P&L %": "{:,.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
        
    with tab_research:
        st.markdown("#### Research Consensus")
        st.markdown("Consolidated analyst opinions, factor breakdowns, and overall confidence scores.")
        
        research_rows = []
        positions_list = json_data.get("consolidated_positions", [])
        research_reports = json_data.get("research_reports", [])
        market_intel = json_data.get("market_intelligence", {})
        health_details = json_data.get("portfolio_health", {})
        
        total_val = sum(pos.get("current_value", pos.get("quantity", 0.0) * pos.get("average_price", 0.0)) for pos in positions_list)
        if total_val == 0:
            total_val = 1.0
            
        reports_map = {r["stock"]: r for r in research_reports}
        
        for pos in positions_list:
            ticker = pos.get("normalized_ticker", "")
            qty = pos.get("quantity", 0.0)
            price = pos.get("current_price", pos.get("average_price", 0.0))
            curr_val = pos.get("current_value", qty * price)
            weight = (curr_val / total_val) * 100.0
            
            report = reports_map.get(ticker, {})
            rec = report.get("recommendation", "No Coverage")
            conf = report.get("confidence_score")
            conf_str = f"{conf:.0f}%" if conf is not None else "N/A"
            
            # Map source
            source = report.get("research_source", "No Coverage")
            rec_type = report.get("recommendation_type", "Web Research")
            if rec == "Research Not Available" or source == "System Error":
                display_source = "No Coverage"
                rec = "No Coverage"
            elif "Nirmal Bang" in source and "Motilal Oswal" in source:
                display_source = "Nirmal Bang + Motilal Oswal"
            elif "Nirmal Bang" in source:
                display_source = "Nirmal Bang"
            elif "Motilal Oswal" in source:
                display_source = "Motilal Oswal"
            elif "Web Research" in rec_type or "Web" in source:
                display_source = "Web Consensus"
            else:
                display_source = "Web Consensus"
                
            # Market Intelligence Overall Score (individual stock overall score)
            stock_details = market_intel.get("stock_details", {}).get(ticker, {})
            mi_score = stock_details.get("overall_score", 50)
            
            # Health Contribution
            is_concentrated = False
            for weak in health_details.get("weaknesses", []):
                if ticker in weak and "concentration" in weak.lower():
                    is_concentrated = True
                    break
            
            if rec == "Sell" or rec == "Reduce":
                health_contrib = "🔴 Negative"
            elif is_concentrated:
                health_contrib = "🔴 Negative (Overweight)"
            elif rec == "Buy" or rec == "Accumulate":
                health_contrib = "🟢 Positive"
            else:
                health_contrib = "🟡 Neutral"
                
            factors = report.get("factors_breakdown", {})
            
            def map_sentiment(val):
                val_str = str(val).lower()
                if "positive" in val_str: return "🟢 Positive"
                if "neutral" in val_str: return "🟡 Neutral"
                if "negative" in val_str: return "🔴 Negative"
                return "🟡 Neutral"
                
            def map_risk(val):
                val_str = str(val).lower()
                if "low" in val_str: return "🟢 Low"
                if "moderate" in val_str: return "🟡 Moderate"
                if "high" in val_str: return "🔴 High"
                return "🟡 Moderate"
                
            def map_valuation(val):
                val_str = str(val).lower()
                if "low" in val_str: return "🟢 Low"
                if "moderate" in val_str: return "🟡 Moderate"
                if "high" in val_str: return "🔴 High"
                return "🟡 Moderate"
                
            analyst_sent = map_sentiment(factors.get("analyst_sentiment", "neutral"))
            upside = map_sentiment(factors.get("target_upside", "neutral"))
            revenue = map_sentiment(factors.get("revenue_growth", "neutral"))
            profitability = map_sentiment(factors.get("profitability_outlook", "neutral"))
            balance_sheet = map_sentiment(factors.get("balance_sheet_strength", "neutral"))
            sector_out = map_sentiment(factors.get("sector_outlook", "neutral"))
            risk = map_risk(factors.get("risk_factors", "moderate"))
            valuation = map_valuation(factors.get("valuation_concerns", "moderate"))
            
            # Concise summary (instead of repeating factor text)
            if rec == "No Coverage":
                summary = "No analyst coverage or research available."
            else:
                summary_parts = []
                if "positive" in factors.get("balance_sheet_strength", "").lower():
                    bs_part = "Strong balance sheet"
                else:
                    bs_part = "Stable balance sheet"
                if "positive" in factors.get("profitability_outlook", "").lower():
                    prof_part = "positive profitability"
                else:
                    prof_part = "flat profitability"
                summary_parts.append(f"{bs_part} with {prof_part}.")
                
                val_str = factors.get("valuation_concerns", "moderate").lower()
                summary_parts.append(f"{val_str.capitalize()} valuation concern.")
                
                risk_str = factors.get("risk_factors", "moderate").lower()
                summary_parts.append(f"{risk_str.capitalize()} risk profile.")
                summary = " ".join(summary_parts)
                
            research_rows.append({
                "Stock": ticker,
                "Current Value": curr_val,
                "Portfolio Weight": f"{weight:.1f}%",
                "Research Source": display_source,
                "Recommendation": rec,
                "Overall Confidence": conf_str,
                "Market Intelligence Score": f"{mi_score}/100",
                "Portfolio Health Contribution": health_contrib,
                "Analyst Sentiment": analyst_sent,
                "Target Upside": upside,
                "Revenue": revenue,
                "Profitability": profitability,
                "Balance Sheet": balance_sheet,
                "Sector": report.get("sector", "Other"),
                "Risk": risk,
                "Valuation": valuation,
                "Summary": summary
            })
            
        df_research_grid = pd.DataFrame(research_rows)
        # Select columns in requested exact layout
        cols_to_show_research = [
            "Stock", "Current Value", "Portfolio Weight", "Research Source", "Recommendation",
            "Overall Confidence", "Market Intelligence Score", "Portfolio Health Contribution",
            "Analyst Sentiment", "Target Upside", "Revenue", "Profitability", "Balance Sheet",
            "Sector", "Risk", "Valuation", "Summary"
        ]
        cols_to_show_research = [col for col in cols_to_show_research if col in df_research_grid.columns]
        df_research_grid = df_research_grid[cols_to_show_research]
        
        st.dataframe(
            df_research_grid.style.format({
                "Current Value": format_inr
            }),
            use_container_width=True,
            hide_index=True
        )
        
    with tab_rebal:
        st.markdown("#### Portfolio Optimization & Rebalancing")
        st.markdown("Target allocations and action steps dynamically calculated to optimize diversification and concentration profiles.")
        
        rebal_list = json_data.get("rebalancing_recommendations", [])
        if rebal_list:
            df_rebal = pd.DataFrame(rebal_list)
            df_rebal_display = df_rebal.rename(columns={
                "ticker": "Ticker",
                "current_allocation_pct": "Current Alloc %",
                "recommended_allocation_pct": "Target Alloc %",
                "allocation_change_pct": "Alloc Change %",
                "action": "Advisory Action",
                "recommendation": "Consensus Rating",
                "confidence_score": "Confidence",
                "sector": "Sector"
            })
            
            cols_to_show_rebal = [
                "Ticker", "Current Alloc %", "Target Alloc %", "Alloc Change %", 
                "Advisory Action", "Consensus Rating", "Confidence", "Sector"
            ]
            cols_to_show_rebal = [col for col in cols_to_show_rebal if col in df_rebal_display.columns]
            df_rebal_display = df_rebal_display[cols_to_show_rebal]
            
            st.dataframe(
                df_rebal_display.style.format({
                    "Current Alloc %": "{:,.1f}%",
                    "Target Alloc %": "{:,.1f}%",
                    "Alloc Change %": lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%",
                    "Confidence": lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No rebalancing recommendations available.")
            
    with tab_health:
        st.markdown("#### Portfolio Health & Sizing Diagnostics")
        st.markdown("Diversification analysis, stock and sector concentration limits, and rating quality metrics.")
        
        health_data = json_data.get("portfolio_health", {})
        if health_data:
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown("**Core Strengths:**")
                for strength in health_data.get("strengths", []):
                    st.markdown(f"- {strength}")
                    
                st.markdown("**Areas for Improvement:**")
                for weakness in health_data.get("weaknesses", []):
                    st.markdown(f"- {weakness}")
            with col_h2:
                flags = health_data.get("risk_flags", [])
                if flags:
                    st.markdown("**Risk Exposure Flags:**")
                    for flag in flags:
                        st.markdown(f"⚠️ {flag}")
                else:
                    st.success("No active concentration or sizing exposure alerts.")
            
    with tab_visuals:
        st.markdown("#### Portfolio Analytics & Visualizations")
        st.markdown("Visual breakdown of current vs. recommended allocations, sector exposures, and analyst sentiment.")
        
        # Generate the charts on the fly
        temp_dash_dir = "temp_dash_charts"
        try:
            chart_paths = generate_report_charts(json_data, temp_dash_dir)
            
            # Show in 2 columns
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                if "current_allocation" in chart_paths and os.path.exists(chart_paths["current_allocation"]):
                    st.image(chart_paths["current_allocation"], use_container_width=True)
                if "sector_exposure" in chart_paths and os.path.exists(chart_paths["sector_exposure"]):
                    st.image(chart_paths["sector_exposure"], use_container_width=True)
                    
            with col_chart2:
                if "recommended_allocation" in chart_paths and os.path.exists(chart_paths["recommended_allocation"]):
                    st.image(chart_paths["recommended_allocation"], use_container_width=True)
                if "recommendation_distribution" in chart_paths and os.path.exists(chart_paths["recommendation_distribution"]):
                    st.image(chart_paths["recommendation_distribution"], use_container_width=True)
                    
            # Clean up temp charts
            for path in chart_paths.values():
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            if os.path.exists(temp_dash_dir):
                try:
                    os.rmdir(temp_dash_dir)
                except Exception:
                    pass
        except Exception as chart_err:
            st.error(f"Failed to generate dashboard charts: {chart_err}")
            
    with tab_market_intel:
        st.markdown("#### 📈 Market Intelligence Engine")
        st.markdown("Institutional-grade technical indicators, derivatives positioning, and liquidity metrics.")
        
        market_intel = json_data.get("market_intelligence")
        if market_intel:
            # 1. Overall Score Cards
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.markdown(f"""
                <div class='card' style='border-left: 4px solid #6C5CE7;'>
                    <div class='metric-label'>Overall Market Intelligence</div>
                    <div class='metric-value' style='color: #a29bfe;'>{market_intel.get("overall_score", 50)}/100</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"""
                <div class='card' style='border-left: 4px solid #3B82F6;'>
                    <div class='metric-label'>Technical Score</div>
                    <div class='metric-value' style='color: #60A5FA;'>{market_intel.get("technical_score", 50)}/100</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m3:
                st.markdown(f"""
                <div class='card' style='border-left: 4px solid #10B981;'>
                    <div class='metric-label'>Derivatives Score</div>
                    <div class='metric-value' style='color: #34D399;'>{market_intel.get("derivatives_score", 50)}/100</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m4:
                st.markdown(f"""
                <div class='card' style='border-left: 4px solid #F59E0B;'>
                    <div class='metric-label'>Liquidity Score</div>
                    <div class='metric-value' style='color: #FBBF24;'>{market_intel.get("liquidity_score", 50)}/100</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Summary callout
            st.info(market_intel.get("summaries", {}).get("overall", ""))
            
            # 2. Detailed Engines
            st.markdown("---")
            st.markdown("### 📊 Technical & Indicators Grid")
            
            tech_rows = []
            liq_rows = []
            derivs_rows = []
            
            for ticker, details in market_intel.get("stock_details", {}).items():
                t_data = details.get("technical", {})
                tech_rows.append({
                    "Ticker": ticker,
                    "Last Price": format_inr(t_data.get("close", 0)),
                    "Trend Score": f"{t_data.get('trend_score', 50)}/100",
                    "Momentum Score": f"{t_data.get('momentum_score', 50)}/100",
                    "Volatility Score": f"{t_data.get('volatility_score', 50)}/100",
                    "RSI (14)": f"{t_data.get('rsi', 50):.1f}",
                    "ADX (14)": f"{t_data.get('adx', 25):.1f}",
                    "Technical Summary": t_data.get("summary", "")
                })
                
                l_data = details.get("liquidity", {})
                liq_rows.append({
                    "Ticker": ticker,
                    "20d Avg Volume": f"{l_data.get('avg_volume_20d', 0):,.0f}",
                    "Volume Breakout": f"{l_data.get('volume_breakout_ratio', 1.0):.2f}x",
                    "Delivery %": f"{l_data.get('delivery_pct', 0.0):.1f}%",
                    "Liquidity Score": f"{l_data.get('liquidity_score', 50)}/100",
                    "Liquidity Summary": l_data.get("summary", "")
                })
                
                d_data = details.get("derivatives", {})
                derivs_rows.append({
                    "Ticker": ticker,
                    "Open Interest": f"{d_data.get('open_interest', 0):,}",
                    "OI Change %": f"{d_data.get('oi_change_pct', 0.0):+.1f}%" if d_data.get('oi_change_pct', 0.0) != 0 else "0.0%",
                    "Put-Call Ratio (PCR)": f"{d_data.get('put_call_ratio', 1.0):.2f}",
                    "Implied Volatility (IV)": f"{d_data.get('implied_volatility', 0.0):.1f}%",
                    "IV Percentile": f"{d_data.get('iv_percentile', 0.0):.1f}%",
                    "Max Pain": format_inr(d_data.get('max_pain', 0)),
                    "Buildup Position": d_data.get('buildup_type', "N/A"),
                    "Derivatives Score": f"{d_data.get('score', 50)}/100"
                })
                
            # Render tables
            st.dataframe(pd.DataFrame(tech_rows), use_container_width=True, hide_index=True)
            
            st.markdown("### 🔄 Derivatives Positioning Grid")
            st.dataframe(pd.DataFrame(derivs_rows), use_container_width=True, hide_index=True)
            st.caption("*Note: Institutional Derivatives positioning and build-ups are derived from open interest and PCR metrics.*")
            
            st.markdown("### 💧 Liquidity & Volume Profile Grid")
            st.dataframe(pd.DataFrame(liq_rows), use_container_width=True, hide_index=True)
            
            # Market Breadth Index details
            st.markdown("---")
            st.markdown("### 🌎 Market Breadth Index")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.write(f"**Portfolio Stocks Above 50 SMA:** {market_intel.get('market_breadth_score', 50)}%")
                st.write(f"**Market Breadth Index Summary:** {market_intel.get('summaries', {}).get('breadth', '')}")
            with col_b2:
                # Add a simple horizontal bar chart showing all engine scores
                st.markdown("**Core Intelligence Score Breakdown**")
                scores_df = pd.DataFrame({
                    "Engine": ["Technical", "Derivatives", "Liquidity", "Market Breadth", "Overall"],
                    "Score": [
                        market_intel.get("technical_score", 50),
                        market_intel.get("derivatives_score", 50),
                        market_intel.get("liquidity_score", 50),
                        market_intel.get("market_breadth_score", 50),
                        market_intel.get("overall_score", 50)
                    ]
                })
                st.bar_chart(scores_df.set_index("Engine"))
        else:
            st.info("Market intelligence data not available for this run. Run a new analysis to generate.")
            
    with tab_report:
        st.markdown("#### 📁 Client Report & Export Center")
        st.markdown("Download professional PDF advisory reports and export portfolio data in standard formats.")
        
        # Load PDF path
        pdf_path = results.get("pdf_path") or json_path.replace(".json", ".pdf")
        
        col_pdf, col_csv_holdings, col_csv_rebal, col_json = st.columns(4)
        
        with col_pdf:
            st.markdown("##### 📄 Professional PDF Report")
            st.write("Download client-ready PDF report including visualizations, executive summary, holdings, and rebalancing recommendations.")
            if os.path.exists(pdf_path):
                try:
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=f.read(),
                            file_name=f"portfolio_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                except Exception as read_err:
                    st.error(f"Error reading PDF file: {read_err}")
            else:
                st.error("PDF report is not available. Please try running analysis again.")
                
        with col_csv_holdings:
            st.markdown("##### 📊 Export Current Holdings")
            st.write("Download consolidated portfolio holdings as a CSV file for spreadsheets and custom import tools.")
            
            csv_holdings_df = df_grouped.copy()
            # Clean columns for CSV download
            if "invested_value" not in csv_holdings_df.columns and "total_value" in csv_holdings_df.columns:
                csv_holdings_df["invested_value"] = csv_holdings_df["total_value"]
            
            csv_holdings_data = csv_holdings_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Export Holdings (CSV)",
                data=csv_holdings_data,
                file_name=f"portfolio_holdings_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_csv_rebal:
            st.markdown("##### 🔄 Export Rebalancing Recommendations")
            st.write("Download target allocations, sector exposure weights, and recommended actions as a CSV file.")
            
            rebal_list = json_data.get("rebalancing_recommendations", [])
            if rebal_list:
                csv_rebal_df = pd.DataFrame(rebal_list)
                csv_rebal_data = csv_rebal_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Export Rebalancing (CSV)",
                    data=csv_rebal_data,
                    file_name=f"portfolio_rebalancing_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.write("*(Rebalancing data not available)*")
                
        with col_json:
            st.markdown("##### 💾 Export Consolidated JSON")
            st.write("Download the complete consolidated payload containing OCR extractions, research reports, and health metrics.")
            
            json_str = json.dumps(json_data, indent=2)
            st.download_button(
                label="⬇️ Export Portfolio Data (JSON)",
                data=json_str,
                file_name=os.path.basename(json_path),
                mime="application/json",
                use_container_width=True
            )
        
    with tab_det:
        st.markdown("#### Individual Extracted Entries")
        st.markdown("Raw extracted data from each screenshot before consolidation and merging.")
        
        detail_display_df = df_individual.copy()
        
        if "invested_value" not in detail_display_df.columns and "total_value" in detail_display_df.columns:
            detail_display_df["invested_value"] = detail_display_df["total_value"]
            detail_display_df["current_price"] = detail_display_df["average_price"]
            detail_display_df["current_value"] = detail_display_df["total_value"]
            detail_display_df["todays_pnl"] = 0.0
            
        detail_display_df = detail_display_df.rename(columns={
            "original_name": "Original Name",
            "normalized_ticker": "Normalized Ticker",
            "quantity": "Quantity",
            "average_price": "Avg Buy Price (₹)",
            "invested_value": "Total Investment (₹)",
            "current_price": "Current Price (₹)",
            "current_value": "Current Value (₹)",
            "todays_pnl": "Today's P&L (₹)",
            "source_file": "Source File"
        })
        
        columns_to_show_det = [
            "Original Name", "Normalized Ticker", "Quantity", "Avg Buy Price (₹)", 
            "Total Investment (₹)", "Current Price (₹)", "Current Value (₹)", "Today's P&L (₹)", "Source File"
        ]
        columns_to_show_det = [col for col in columns_to_show_det if col in detail_display_df.columns]
        detail_display_df = detail_display_df[columns_to_show_det]
        
        st.dataframe(
            detail_display_df.style.format({
                "Quantity": "{:,.2f}",
                "Avg Buy Price (₹)": format_inr,
                "Total Investment (₹)": format_inr,
                "Current Price (₹)": format_inr,
                "Current Value (₹)": format_inr,
                "Today's P&L (₹)": format_inr
            }),
            use_container_width=True,
            hide_index=True
        )
        
    with tab_raw:
        st.markdown("#### Saved JSON Output")
        st.markdown(f"Saved location: `outputs/{os.path.basename(json_path)}`")
        
        # Pretty print JSON
        st.code(json.dumps(json_data, indent=2), language="json")
        


# Display previously saved runs
st.markdown("---")
st.markdown("### Previously Analyzed Portfolios")

saved_files = sorted(
    [f for f in os.listdir(OUTPUTS_DIR) if f.startswith("portfolio_extraction_") and f.endswith(".json")],
    reverse=True
)

if saved_files:
    for filename in saved_files[:5]: # Show top 5
        filepath = os.path.join(OUTPUTS_DIR, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            dt_str = datetime.strptime(filename.replace("portfolio_extraction_", "").replace(".json", ""), "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            
            col_time, col_stats, col_load = st.columns([1.5, 3.5, 1.0])
            with col_time:
                st.write(f"⏱️ {dt_str}")
            with col_stats:
                total_val = sum(item.get("current_value", item.get("total_value", 0)) for item in data.get("extracted_positions", []))
                stocks_count = len(data.get("consolidated_positions", []))
                st.write(f"Contains **{stocks_count}** stocks | Current Value: **{format_inr(total_val)}**")
            with col_load:
                if st.button("Reload", key=f"reload_{filename}"):
                    # Parse consolidation positions into dataframe
                    df_grouped = pd.DataFrame(data["consolidated_positions"])
                    df_individual = pd.DataFrame(data["extracted_positions"])
                    
                    st.session_state["last_analysis_results"] = {
                        "df_grouped": df_grouped,
                        "df_individual": df_individual,
                        "json_path": filepath,
                        "json_data": data
                    }
                    st.rerun()
        except Exception as e:
            pass
else:
    st.info("No prior portfolio runs found in the outputs/ directory. Run an analysis above to save results.")
