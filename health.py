import os
import json
import requests
from typing import List, Dict, Any, Optional

# Static sector mappings to ensure consistency in diversification scoring
SECTOR_MAPPINGS = {
    # Indian Tickers
    "HDFCBANK": "Financial Services",
    "ICICIBANK": "Financial Services",
    "RELIANCE": "Energy & Conglomerate",
    "TCS": "Technology",
    "INFY": "Technology",
    "SBIN": "Financial Services",
    "HDFC": "Financial Services",
    "BHARTIARTL": "Telecommunications",
    "ITC": "FMCG",
    "LICI": "Financial Services",
    "HINDUNILVR": "FMCG",
    "LT": "Construction & Engineering",
    "AXISBANK": "Financial Services",
    "KOTAKBANK": "Financial Services",
    "ADANIENT": "Conglomerate",
    
    # US Tickers
    "AAPL": "Technology",
    "MSFT": "Technology",
    "AMZN": "Consumer Cyclical",
    "NVDA": "Technology",
    "GOOGL": "Technology",
    "META": "Technology",
    "TSLA": "Automobile",
    "BRK.A": "Financial Services",
    "BRK.B": "Financial Services",
    "LLY": "Healthcare",
    "V": "Financial Services",
}

# Memory cache to prevent redundant API queries
RESOLVED_SECTORS_CACHE = {}

def get_yahoo_metadata_sector(ticker: str) -> Optional[str]:
    """
    Attempts to fetch the sector of a given ticker using Yahoo Finance Search API.
    Supports both US and Indian tickers (appends .NS or .BO suffix if needed).
    """
    if not ticker:
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    ticker_options = [ticker]
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        ticker_options = [f"{ticker}.NS", f"{ticker}.BO", ticker]
        
    for option in ticker_options:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={option}"
        try:
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                quotes = data.get("quotes", [])
                for q in quotes:
                    if q.get("quoteType") == "EQUITY":
                        sector = q.get("sector") or q.get("sectorDisp")
                        if sector:
                            return sector.strip()
        except Exception:
            pass
            
    return None

def resolve_sector(ticker: str, report_sector: Optional[str]) -> str:
    """
    Resolves the sector using the preferred hierarchy:
    1. Static Mapping Table
    2. Dynamic Metadata Lookup (Yahoo Finance Search API)
    3. LLM Fallback (extracted value in report)
    4. Default Fallback ("Other")
    """
    # 1. Existing sector mapping table (check first)
    if ticker in SECTOR_MAPPINGS:
        return SECTOR_MAPPINGS[ticker]
        
    # Check memory cache
    if ticker in RESOLVED_SECTORS_CACHE:
        return RESOLVED_SECTORS_CACHE[ticker]
        
    # 2. Metadata lookup / structured source
    sector = get_yahoo_metadata_sector(ticker)
    if sector:
        RESOLVED_SECTORS_CACHE[ticker] = sector
        return sector
        
    # 3. LLM fallback only when sector information cannot be determined
    if report_sector and report_sector.strip().lower() not in ["null", "none", "", "unknown"]:
        resolved = report_sector.strip()
        RESOLVED_SECTORS_CACHE[ticker] = resolved
        return resolved
        
    # 4. Default fallback
    return "Other"

class PortfolioHealthEngine:
    def __init__(self):
        pass

    def evaluate_portfolio(self, consolidated_positions: List[dict], research_reports: List[dict], risk_profile: str = "Balanced") -> dict:
        """
        Evaluates the portfolio and generates Portfolio Health Score, Risk Level,
        Strengths, Weaknesses, and Key Risk Flags.
        """
        # Map stock ticker to research report details
        reports_map = {r["stock"]: r for r in research_reports}
        
        # Define profile limits
        profile_lower = risk_profile.lower()
        if "conservative" in profile_lower:
            stock_limit = 15.0
            sector_limit = 30.0
        elif "aggressive" in profile_lower:
            stock_limit = 35.0
            sector_limit = 60.0
        else: # Balanced
            stock_limit = 25.0
            sector_limit = 45.0
            
        total_value = 0.0
        positions_eval = []
        
        for pos in consolidated_positions:
            ticker = pos.get("normalized_ticker", "")
            qty = pos.get("quantity", 0.0)
            avg_p = pos.get("average_price", 0.0)
            curr_v = pos.get("current_value", None)
            
            # Fallback to average buy value if current_value is missing
            val = curr_v if curr_v is not None else (qty * avg_p)
            total_value += val
            
            report = reports_map.get(ticker, {})
            recommendation = report.get("recommendation", "Research Not Available")
            confidence = report.get("confidence_score", 0.0)
            if confidence is None:
                confidence = 0.0
                
            # Sector Resolution Order:
            # 1. Existing sector mapping table (checked inside resolve_sector)
            # 2. Metadata lookup (checked inside resolve_sector)
            # 3. LLM fallback (checked inside resolve_sector)
            # 4. Default fallback ("Other")
            sector = resolve_sector(ticker, report.get("sector"))
                
            positions_eval.append({
                "ticker": ticker,
                "value": val,
                "recommendation": recommendation,
                "confidence": confidence,
                "sector": sector
            })
            
        if total_value <= 0:
            return {
                "health_score": 0,
                "risk_level": "Low",
                "strengths": ["Empty portfolio holds no active risk"],
                "weaknesses": ["Empty portfolio has no allocation"],
                "risk_flags": ["Portfolio is empty"],
                "metrics": {
                    "buy_allocation_pct": 0.0,
                    "hold_allocation_pct": 0.0,
                    "sell_allocation_pct": 0.0,
                    "max_stock_allocation_pct": 0.0,
                    "max_sector_allocation_pct": 0.0,
                    "unique_sectors_count": 0,
                    "weighted_confidence_pct": 0.0
                }
            }
            
        # Calculate weight allocations
        for pe in positions_eval:
            pe["weight"] = (pe["value"] / total_value) * 100.0
            
        # 1. Recommendation Quality score (Max 40 points)
        buy_weight = 0.0
        hold_weight = 0.0
        sell_weight = 0.0
        na_weight = 0.0
        
        for pe in positions_eval:
            rec = pe["recommendation"].lower()
            w = pe["weight"]
            if "buy" in rec or "accumulate" in rec:
                buy_weight += w
            elif "hold" in rec or "neutral" in rec or "reduce" not in rec and "sell" not in rec and "research not available" not in rec:
                # Fallback to hold for general consensus that is non-negative
                hold_weight += w
            elif "sell" in rec or "reduce" in rec:
                sell_weight += w
            else:
                na_weight += w
                
        rating_score = 40.0 * (buy_weight / 100.0) + 20.0 * (hold_weight / 100.0)
        
        # 2. Confidence Exposure score (Max 20 points)
        weighted_confidence = 0.0
        for pe in positions_eval:
            weighted_confidence += pe["weight"] * (pe["confidence"] / 100.0)
        confidence_score = 20.0 * (weighted_confidence / 100.0)
        
        # 3. Concentration Risk score (Max 20 points) - Risk-profile aware
        max_pos_weight = max(pe["weight"] for pe in positions_eval) if positions_eval else 0.0
        if max_pos_weight <= stock_limit:
            concentration_score = 20.0
        elif max_pos_weight <= stock_limit + 10.0:
            concentration_score = 15.0
        elif max_pos_weight <= stock_limit + 20.0:
            concentration_score = 10.0
        else:
            concentration_score = 5.0
            
        # 4. Sector Diversification score (Max 20 points)
        sectors_weights = {}
        for pe in positions_eval:
            sec = pe["sector"]
            sectors_weights[sec] = sectors_weights.get(sec, 0.0) + pe["weight"]
            
        # Count sectors excluding "Other"
        unique_sectors = len([s for s in sectors_weights if s != "Other"])
        if unique_sectors == 0 and "Other" in sectors_weights:
            unique_sectors = 1  # If everything is other, count as 1 sector
            
        max_sector_weight = max(sectors_weights.values()) if sectors_weights else 0.0
        
        # Sector Concentration score (Max 10) - Risk-profile aware
        if max_sector_weight <= sector_limit:
            sec_conc_score = 10.0
        elif max_sector_weight <= sector_limit + 15.0:
            sec_conc_score = 7.0
        elif max_sector_weight <= sector_limit + 30.0:
            sec_conc_score = 4.0
        else:
            sec_conc_score = 1.0
            
        # Unique Sectors count score (Max 10)
        if unique_sectors >= 4:
            sec_count_score = 10.0
        elif unique_sectors == 3:
            sec_count_score = 7.0
        elif unique_sectors == 2:
            sec_count_score = 4.0
        else:
            sec_count_score = 1.0
            
        sector_score = sec_conc_score + sec_count_score
        
        # Total Health Score calculation
        health_score = int(round(rating_score + confidence_score + concentration_score + sector_score))
        health_score = max(0, min(100, health_score))
        
        # Programmatically evaluate Strengths
        strengths = []
        if buy_weight > 50.0:
            strengths.append(f"✓ Strong allocation to Buy-rated stocks ({buy_weight:.1f}% allocation)")
        if unique_sectors >= 3:
            strengths.append(f"✓ Good diversification across {unique_sectors} industry sectors")
        if max_pos_weight <= stock_limit:
            strengths.append(f"✓ Balanced position sizing (largest stock allocation is {max_pos_weight:.1f}%, within the {risk_profile} limit of {stock_limit}%)")
        if weighted_confidence >= 75.0:
            strengths.append(f"✓ High rating confidence (weighted rating confidence is {weighted_confidence:.1f}%)")
        if not strengths:
            strengths.append("✓ Balanced asset allocation profile")
            
        # Programmatically evaluate Weaknesses
        weaknesses = []
        if sell_weight > 10.0:
            weaknesses.append(f"✗ Elevated exposure to Sell-rated assets ({sell_weight:.1f}% allocation)")
        if max_pos_weight > stock_limit:
            weaknesses.append(f"✗ High single stock concentration risk (largest position {max_pos_weight:.1f}% exceeds {risk_profile} limit of {stock_limit}%)")
        if max_sector_weight > sector_limit:
            largest_sec = max(sectors_weights, key=sectors_weights.get)
            weaknesses.append(f"✗ High sector concentration in {largest_sec} ({max_sector_weight:.1f}% exceeds {risk_profile} limit of {sector_limit}%)")
        if unique_sectors <= 2:
            weaknesses.append(f"✗ Limited sector diversification (only {unique_sectors} sector(s) with active coverage)")
        if weighted_confidence < 60.0:
            weaknesses.append(f"✗ High exposure to low-confidence consensus recommendations")
            
        # Evaluate Risk Flags
        risk_flags = []
        if max_pos_weight > stock_limit + 10.0:
            risk_flags.append(f"⚠️ CONCENTRATION ALERT: Single stock position exceeds the {risk_profile} limit by more than 10% ({max_pos_weight:.1f}% vs {stock_limit}% limit).")
        if max_sector_weight > sector_limit + 15.0:
            largest_sec = max(sectors_weights, key=sectors_weights.get)
            risk_flags.append(f"⚠️ SECTOR CONCENTRATION ALERT: Exposure to {largest_sec} sector exceeds the {risk_profile} limit by more than 15% ({max_sector_weight:.1f}% vs {sector_limit}% limit).")
        if sell_weight > 15.0:
            risk_flags.append(f"⚠️ SELL RATINGS RISK: Excessive allocation to underperforming assets with Sell/Reduce consensus.")
        if weighted_confidence < 50.0:
            risk_flags.append(f"⚠️ LOW RATINGS CONFIDENCE: High exposure to low-confidence analyst ratings.")
            
        # Determine overall Risk Level (Low/Moderate/High)
        if health_score >= 75 and len(risk_flags) == 0:
            risk_level = "Low"
        elif health_score >= 50 and len(risk_flags) <= 1:
            risk_level = "Moderate"
        else:
            risk_level = "High"
            
        return {
            "health_score": health_score,
            "risk_level": risk_level,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "risk_flags": risk_flags,
            "metrics": {
                "buy_allocation_pct": buy_weight,
                "hold_allocation_pct": hold_weight,
                "sell_allocation_pct": sell_weight,
                "max_stock_allocation_pct": max_pos_weight,
                "max_sector_allocation_pct": max_sector_weight,
                "unique_sectors_count": unique_sectors,
                "weighted_confidence_pct": weighted_confidence
            }
        }
