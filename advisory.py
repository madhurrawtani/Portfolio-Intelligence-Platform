import os
from typing import List, Dict, Any, Optional
from health import SECTOR_MAPPINGS

# Define growth and stable sectors for profile adjustments
GROWTH_SECTORS = ["Technology", "Conglomerate", "Energy", "Automobile", "Consumer Cyclical"]
STABLE_SECTORS = ["Financial Services", "FMCG", "Consumer Defensive", "Healthcare", "Utilities", "Telecommunications", "Construction & Engineering"]

class PortfolioAdvisoryEngine:
    def __init__(self):
        pass

    def generate_allocation_recommendations(
        self, 
        consolidated_positions: List[dict], 
        research_reports: List[dict], 
        risk_profile: str = "Balanced"
    ) -> List[dict]:
        """
        Generates recommended allocations and rebalancing actions based on current holdings,
        research ratings, confidence, and chosen risk profile.
        """
        # Map stock ticker to research report details
        reports_map = {r["stock"]: r for r in research_reports}
        
        # Calculate total current portfolio value
        total_current_value = sum(
            pos.get("current_value", pos.get("quantity", 0.0) * pos.get("average_price", 0.0))
            for pos in consolidated_positions
        )
        
        # Risk profile configuration
        profile_lower = risk_profile.lower()
        if "conservative" in profile_lower:
            stock_cap = 15.0
        elif "aggressive" in profile_lower:
            stock_cap = 35.0
        else: # Balanced
            stock_cap = 25.0
            
        base_weights = {}
        
        # Step 1 & 2: Exclude Sells and compute base weights based on ratings & confidence
        for pos in consolidated_positions:
            ticker = pos.get("normalized_ticker", "")
            report = reports_map.get(ticker, {})
            recommendation = report.get("recommendation", "Research Not Available")
            confidence = report.get("confidence_score", 0.0) or 0.0
            
            rec_lower = recommendation.lower()
            
            # Exclude Sells and Reduces completely
            if "sell" in rec_lower or "reduce" in rec_lower or "research not available" in rec_lower:
                base_weights[ticker] = 0.0
                continue
                
            # Base weight by recommendation
            if "buy" in rec_lower or "accumulate" in rec_lower:
                if confidence >= 80.0:
                    weight = 3.0
                elif confidence >= 50.0:
                    weight = 2.0
                else:
                    weight = 1.0
            elif "hold" in rec_lower or "neutral" in rec_lower:
                if confidence >= 80.0:
                    weight = 1.5
                elif confidence >= 50.0:
                    weight = 1.0
                else:
                    weight = 0.5
            else:
                # Fallback for unrecognized non-negative recommendations
                weight = 1.0
                
            # Step 3: Apply Risk Profile Adjustments
            # Determine sector
            sector = "Other"
            if ticker in SECTOR_MAPPINGS:
                sector = SECTOR_MAPPINGS[ticker]
            elif report.get("sector") and report.get("sector").strip().lower() not in ["null", "none", "", "unknown"]:
                sector = report.get("sector").strip()
                
            if "conservative" in profile_lower:
                # Conservative: Preference for stable sectors, penalty on growth and low-confidence
                if sector in GROWTH_SECTORS or sector == "Other":
                    weight *= 0.5
                elif sector in STABLE_SECTORS:
                    weight *= 1.3
                    
                if confidence < 60.0:
                    weight *= 0.5
                elif confidence >= 80.0:
                    weight *= 1.3
                    
            elif "aggressive" in profile_lower:
                # Aggressive: Preference for growth/high-upside sectors, discount hold ratings
                if sector in GROWTH_SECTORS:
                    weight *= 1.3
                if "hold" in rec_lower or "neutral" in rec_lower:
                    weight *= 0.8
                if confidence >= 80.0:
                    weight *= 1.1
                    
            base_weights[ticker] = weight
            
        # Step 4: Normalize weights to sum to 100%
        total_base = sum(base_weights.values())
        normalized_weights = {}
        for ticker, w in base_weights.items():
            if total_base > 0:
                normalized_weights[ticker] = (w / total_base) * 100.0
            else:
                normalized_weights[ticker] = 0.0
                
        # Step 5: Apply single-stock concentration caps iteratively and redistribute
        active_keys = [k for k, w in normalized_weights.items() if w > 0]
        if active_keys:
            # If the number of active assets * stock_cap is <= 100%, they will all just hit the cap
            if len(active_keys) * stock_cap <= 100.0:
                for k in active_keys:
                    normalized_weights[k] = stock_cap
            else:
                capped_keys = set()
                for _ in range(20):
                    excess = 0.0
                    newly_capped = False
                    
                    for k in active_keys:
                        if k not in capped_keys and normalized_weights[k] > stock_cap:
                            excess += normalized_weights[k] - stock_cap
                            normalized_weights[k] = stock_cap
                            capped_keys.add(k)
                            newly_capped = True
                            
                    if excess <= 1e-5 and not newly_capped:
                        break
                        
                    uncapped_keys = [k for k in active_keys if k not in capped_keys]
                    if not uncapped_keys:
                        break
                        
                    uncapped_sum = sum(normalized_weights[k] for k in uncapped_keys)
                    if uncapped_sum <= 0:
                        # Distribute excess evenly among uncapped keys
                        for k in uncapped_keys:
                            normalized_weights[k] += excess / len(uncapped_keys)
                    else:
                        for k in uncapped_keys:
                            normalized_weights[k] += excess * (normalized_weights[k] / uncapped_sum)
                    
        # Step 6: Compute Current vs Recommended allocation comparisons and actions
        recommendations = []
        for pos in consolidated_positions:
            ticker = pos.get("normalized_ticker", "")
            report = reports_map.get(ticker, {})
            
            qty = pos.get("quantity", 0.0)
            avg_p = pos.get("average_price", 0.0)
            curr_v = pos.get("current_value", None)
            val = curr_v if curr_v is not None else (qty * avg_p)
            
            curr_alloc_pct = (val / total_current_value * 100.0) if total_current_value > 0 else 0.0
            rec_alloc_pct = normalized_weights.get(ticker, 0.0)
            change_pct = rec_alloc_pct - curr_alloc_pct
            
            # Action logic
            if rec_alloc_pct == 0.0 and curr_alloc_pct > 0.0:
                action = "Reduce Exposure" # Exit Sell-rated or uncovered completely
            elif change_pct > 2.0:
                action = "Increase Exposure"
            elif change_pct < -2.0:
                action = "Reduce Exposure"
            else:
                action = "Maintain Exposure"
                
            recommendations.append({
                "ticker": ticker,
                "current_value": val,
                "current_allocation_pct": curr_alloc_pct,
                "recommended_allocation_pct": rec_alloc_pct,
                "allocation_change_pct": change_pct,
                "action": action,
                "recommendation": report.get("recommendation", "Research Not Available"),
                "confidence_score": report.get("confidence_score", 0.0),
                "sector": report.get("sector", "Other")
            })
            
        return recommendations

    def generate_intelligence_summary(
        self, 
        health_data: dict, 
        rebalancing_data: List[dict], 
        consolidated_positions: List[dict]
    ) -> dict:
        """
        Compiles the primary client-facing summary showing Opportunities, Risks, and Rebalancing.
        """
        # 1. Opportunities (High confidence Buy ratings)
        opportunities = []
        for item in rebalancing_data:
            rec = item.get("recommendation", "").lower()
            conf = item.get("confidence_score", 0.0) or 0.0
            if ("buy" in rec or "accumulate" in rec) and conf >= 70.0:
                opportunities.append(
                    f"Boost exposure to {item['ticker']} ({item['recommendation']}, confidence: {conf:.1f}%)"
                )
        if not opportunities:
            opportunities.append("No immediate high-confidence buying opportunities identified.")

        # 2. Key Risks (Sells, Concentration flags, high exposure to low confidence holds)
        key_risks = []
        # Exclude using risk flags from health
        health_flags = health_data.get("risk_flags", [])
        for flag in health_flags:
            key_risks.append(flag)
            
        # Check for Sell recommendations in rebalancing
        sells = [item["ticker"] for item in rebalancing_data if "sell" in item["recommendation"].lower() or "reduce" in item["recommendation"].lower()]
        if sells:
            key_risks.append(f"⚠️ SELL RATINGS: Active Sell/Reduce rating coverage on {', '.join(sells)}. Rebalancing suggests exiting exposure.")
            
        if not key_risks:
            key_risks.append("No critical risk warnings identified for current positions.")

        # 3. Rebalancing Summary
        rebal_increase = [item["ticker"] for item in rebalancing_data if item["action"] == "Increase Exposure"]
        rebal_reduce = [item["ticker"] for item in rebalancing_data if item["action"] == "Reduce Exposure"]
        
        actions_summary = []
        if rebal_increase:
            actions_summary.append(f"Increase exposure to: {', '.join(rebal_increase)}")
        if rebal_reduce:
            actions_summary.append(f"Reduce exposure to: {', '.join(rebal_reduce)}")
        if not actions_summary:
            actions_summary.append("All positions currently align with target allocations. Maintain current exposure.")
            
        return {
            "top_opportunities": opportunities,
            "key_risks": key_risks,
            "rebalancing_actions_summary": actions_summary
        }
