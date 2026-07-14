import sys
import os

# Ensure we can import from the workspace
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from health import PortfolioHealthEngine
from advisory import PortfolioAdvisoryEngine

def test_allocation_exclusion_rules():
    print("Testing Exclusion of Sell-rated Assets...")
    advisory = PortfolioAdvisoryEngine()
    
    positions = [
        {"normalized_ticker": "RELIANCE", "quantity": 10, "average_price": 2500.0, "current_value": 25000.0},
        {"normalized_ticker": "HDFCBANK", "quantity": 20, "average_price": 1500.0, "current_value": 30000.0},
        {"normalized_ticker": "AAPL", "quantity": 5, "average_price": 150.0, "current_value": 75000.0}
    ]
    
    reports = [
        {"stock": "RELIANCE", "recommendation": "Buy", "confidence_score": 80.0, "sector": "Energy"},
        {"stock": "HDFCBANK", "recommendation": "Sell", "confidence_score": 90.0, "sector": "Financial Services"},
        {"stock": "AAPL", "recommendation": "Reduce", "confidence_score": 70.0, "sector": "Technology"}
    ]
    
    # Run advisory rebalancing
    rebal_data = advisory.generate_allocation_recommendations(positions, reports, "Balanced")
    
    # Map recommendations by ticker
    rebal_map = {item["ticker"]: item for item in rebal_data}
    
    # Reliance is Buy, HDFCBANK is Sell, AAPL is Reduce.
    # Therefore, recommended allocation for HDFCBANK and AAPL must be exactly 0%.
    # Reliance should receive 100% since it's the only Buy asset.
    assert rebal_map["HDFCBANK"]["recommended_allocation_pct"] == 0.0
    assert rebal_map["AAPL"]["recommended_allocation_pct"] == 0.0
    assert rebal_map["RELIANCE"]["recommended_allocation_pct"] == 25.0
    assert rebal_map["HDFCBANK"]["action"] == "Reduce Exposure"
    assert rebal_map["AAPL"]["action"] == "Reduce Exposure"
    
    print("OK: Exclusion of Sell/Reduce rated assets verified.")

def test_risk_profile_allocations():
    print("Testing Risk Profile Capping and Sector Biases...")
    advisory = PortfolioAdvisoryEngine()
    
    # 8 positions that are all Buy-rated
    positions = [
        {"normalized_ticker": "RELIANCE", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0}, # Energy (Growth)
        {"normalized_ticker": "HDFCBANK", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0}, # Fin Serv (Stable)
        {"normalized_ticker": "AAPL", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0},     # Tech (Growth)
        {"normalized_ticker": "ITC", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0},        # FMCG (Stable)
        {"normalized_ticker": "INFY", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0},       # Tech (Growth)
        {"normalized_ticker": "HINDUNILVR", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0}, # FMCG (Stable)
        {"normalized_ticker": "MSFT", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0},       # Tech (Growth)
        {"normalized_ticker": "SBIN", "quantity": 10, "average_price": 2000.0, "current_value": 20000.0}        # Fin Serv (Stable)
    ]
    
    reports = [
        {"stock": "RELIANCE", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Energy"},
        {"stock": "HDFCBANK", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Financial Services"},
        {"stock": "AAPL", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Technology"},
        {"stock": "ITC", "recommendation": "Buy", "confidence_score": 85.0, "sector": "FMCG"},
        {"stock": "INFY", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Technology"},
        {"stock": "HINDUNILVR", "recommendation": "Buy", "confidence_score": 85.0, "sector": "FMCG"},
        {"stock": "MSFT", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Technology"},
        {"stock": "SBIN", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Financial Services"}
    ]
    
    # 1. Test Conservative Profile (Cap = 15%)
    rebal_con = advisory.generate_allocation_recommendations(positions, reports, "Conservative")
    for item in rebal_con:
        # Verify cap is strictly respected (maximum allocation <= 15%)
        assert item["recommended_allocation_pct"] <= 15.01
        
    con_map = {item["ticker"]: item for item in rebal_con}
    # Stable sector assets (HDFCBANK, ITC) should have higher recommended weight than growth sector assets (RELIANCE, AAPL)
    assert con_map["HDFCBANK"]["recommended_allocation_pct"] > con_map["AAPL"]["recommended_allocation_pct"]
    print("OK: Conservative weight limits and sector preference verified.")
    
    # 2. Test Balanced Profile (Cap = 25%)
    rebal_bal = advisory.generate_allocation_recommendations(positions, reports, "Balanced")
    for item in rebal_bal:
        assert item["recommended_allocation_pct"] <= 25.01
    print("OK: Balanced weight limits verified.")
    
    # 3. Test Aggressive Profile (Cap = 35%)
    rebal_agg = advisory.generate_allocation_recommendations(positions, reports, "Aggressive")
    for item in rebal_agg:
        assert item["recommended_allocation_pct"] <= 35.01
        
    agg_map = {item["ticker"]: item for item in rebal_agg}
    # Growth sector assets should have higher weight than stable sector assets under Aggressive
    assert agg_map["AAPL"]["recommended_allocation_pct"] > agg_map["HDFCBANK"]["recommended_allocation_pct"]
    print("OK: Aggressive weight limits and sector preference verified.")

def test_intelligence_summary_output():
    print("Testing Portfolio Intelligence Summary compilation...")
    health = PortfolioHealthEngine()
    advisory = PortfolioAdvisoryEngine()
    
    positions = [
        {"normalized_ticker": "RELIANCE", "quantity": 10, "average_price": 2500.0, "current_value": 25000.0},
        {"normalized_ticker": "HDFCBANK", "quantity": 20, "average_price": 1500.0, "current_value": 30000.0}
    ]
    reports = [
        {"stock": "RELIANCE", "recommendation": "Buy", "confidence_score": 85.0, "sector": "Energy"},
        {"stock": "HDFCBANK", "recommendation": "Hold", "confidence_score": 50.0, "sector": "Financial Services"}
    ]
    
    health_data = health.evaluate_portfolio(positions, reports, "Balanced")
    rebal_data = advisory.generate_allocation_recommendations(positions, reports, "Balanced")
    
    intel_summary = advisory.generate_intelligence_summary(health_data, rebal_data, positions)
    
    assert "top_opportunities" in intel_summary
    assert "key_risks" in intel_summary
    assert "rebalancing_actions_summary" in intel_summary
    
    print("Opportunities:", [o.encode('ascii', 'ignore').decode('ascii') for o in intel_summary["top_opportunities"]])
    print("Risks:", [r.encode('ascii', 'ignore').decode('ascii') for r in intel_summary["key_risks"]])
    print("Rebalancing Actions:", [a.encode('ascii', 'ignore').decode('ascii') for a in intel_summary["rebalancing_actions_summary"]])
    print("OK: Intelligence summary output verified.")

if __name__ == "__main__":
    print("==========================================")
    print("PORTFOLIO ADVISORY ENGINE TEST SUITE")
    print("==========================================\n")
    try:
        test_allocation_exclusion_rules()
        test_risk_profile_allocations()
        test_intelligence_summary_output()
        print("\nALL ADVISORY TESTS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print("\nTEST ASSERTION FAILED!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print("\nTEST RUN ENCOUNTERED ERROR!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
