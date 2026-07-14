import sys
import os

# Ensure we can import from the workspace
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from health import PortfolioHealthEngine, SECTOR_MAPPINGS, RESOLVED_SECTORS_CACHE, get_yahoo_metadata_sector, resolve_sector

def test_sector_resolution():
    print("Running Sector Resolution Hierarchy Tests...")
    
    # Reset memory cache to ensure clean test runs
    RESOLVED_SECTORS_CACHE.clear()
    
    # 1. Existing Sector Mapping Table (SECTOR_MAPPINGS)
    # Ticker "RELIANCE" is in SECTOR_MAPPINGS. It should map to "Energy & Conglomerate"
    assert resolve_sector("RELIANCE", "Technology") == "Energy & Conglomerate"
    print("OK: Static mapping resolution verified (RELIANCE)")
    
    # 2. Metadata Lookup / Structured Source (Yahoo Finance Search API)
    # Ticker "ITC" is not in SECTOR_MAPPINGS, but is on Yahoo Finance.
    # It should dynamically fetch "Consumer Defensive" (or similar) from the API.
    # We pass a conflicting LLM sector ("Utilities") to ensure Yahoo Finance takes priority.
    itc_sector = resolve_sector("ITC", "Utilities")
    assert itc_sector is not None
    assert itc_sector != "Utilities"
    assert "Consumer" in itc_sector or "FMCG" in itc_sector or "Tobacco" in itc_sector or "Defensive" in itc_sector
    print(f"OK: Metadata lookup resolution verified (ITC -> {itc_sector})")
    
    # 3. LLM Fallback (when not in SECTOR_MAPPINGS and Yahoo API lookup yields None)
    # Using a fake ticker that won't exist on Yahoo Finance
    fake_ticker = "FAKE_MOCK_XYZ"
    llm_sector = "Specialty Finance"
    resolved_fake = resolve_sector(fake_ticker, llm_sector)
    assert resolved_fake == llm_sector
    print("OK: LLM fallback resolution verified (FAKE_MOCK_XYZ)")
    
    # 4. Default Fallback ("Other")
    # Using a fake ticker with no LLM sector
    unknown_ticker = "UNKNOWN_MOCK_XYZ"
    resolved_unknown = resolve_sector(unknown_ticker, None)
    assert resolved_unknown == "Other"
    print("OK: Default fallback resolution verified (UNKNOWN_MOCK_XYZ -> Other)")
    
    print("Sector Resolution Tests: ALL PASSED!\n")

def test_portfolio_health_scoring():
    print("Running Portfolio Health Scoring Tests...")
    engine = PortfolioHealthEngine()
    
    # Test Empty Portfolio
    empty_result = engine.evaluate_portfolio([], [])
    assert empty_result["health_score"] == 0
    assert empty_result["risk_level"] == "Low"  # Empty portfolio default
    assert "Portfolio is empty" in empty_result["risk_flags"]
    print("OK: Empty portfolio evaluation verified")
    
    # Mock Consolidated Positions
    consolidated_positions = [
        {"normalized_ticker": "RELIANCE", "quantity": 10, "average_price": 2500.0, "current_value": 25000.0},
        {"normalized_ticker": "HDFCBANK", "quantity": 20, "average_price": 1500.0, "current_value": 30000.0},
        {"normalized_ticker": "AAPL", "quantity": 5, "average_price": 150.0, "current_value": 75000.0},
        {"normalized_ticker": "MOCK_LLM_STOCK", "quantity": 100, "average_price": 100.0, "current_value": 10000.0}
    ]
    
    # Mock Research Reports
    research_reports = [
        {
            "stock": "RELIANCE",
            "research_available": "Yes",
            "recommendation": "Buy",
            "confidence_score": 80.0,
            "sector": "Energy"
        },
        {
            "stock": "HDFCBANK",
            "research_available": "Yes",
            "recommendation": "Buy",
            "confidence_score": 90.0,
            "sector": "Financial Services"
        },
        {
            "stock": "AAPL",
            "research_available": "Yes",
            "recommendation": "Hold",
            "confidence_score": 70.0,
            "sector": "Technology"
        },
        {
            "stock": "MOCK_LLM_STOCK",
            "research_available": "Yes",
            "recommendation": "Sell",
            "confidence_score": 40.0,
            "sector": "Utilities"
        }
    ]
    
    # Evaluate portfolio
    result = engine.evaluate_portfolio(consolidated_positions, research_reports)
    
    # Inspect output structure
    assert "health_score" in result
    assert "risk_level" in result
    assert "strengths" in result
    assert "weaknesses" in result
    assert "risk_flags" in result
    assert "metrics" in result
    
    score = result["health_score"]
    risk = result["risk_level"]
    metrics = result["metrics"]
    
    # Safely print lists by encoding to ASCII (ignores emojis and unicode symbols like checkmarks)
    safe_strengths = [s.encode('ascii', 'ignore').decode('ascii').strip() for s in result['strengths']]
    safe_weaknesses = [w.encode('ascii', 'ignore').decode('ascii').strip() for w in result['weaknesses']]
    safe_flags = [f.encode('ascii', 'ignore').decode('ascii').strip() for f in result['risk_flags']]
    
    print(f"Evaluated Score: {score}/100")
    print(f"Risk Level: {risk}")
    print(f"Strengths: {safe_strengths}")
    print(f"Weaknesses: {safe_weaknesses}")
    print(f"Risk Flags: {safe_flags}")
    print(f"Metrics: {metrics}")
    
    # Assert score is within boundaries
    assert 0 <= score <= 100
    
    # Assert risk level calculation is sound
    assert risk in ["Low", "Moderate", "High"]
    
    # Verify sector allocation counts (excluding "Other")
    # AAPL -> Technology (Static Mapping)
    # HDFCBANK -> Financial Services (Static Mapping)
    # RELIANCE -> Energy & Conglomerate (Static Mapping)
    # MOCK_LLM_STOCK -> Utilities (LLM Fallback)
    # Total unique sectors = 4
    assert metrics["unique_sectors_count"] == 4
    
    print("Portfolio Health Scoring Tests: ALL PASSED!\n")

if __name__ == "__main__":
    print("==========================================")
    print("PORTFOLIO HEALTH ENGINE TEST SUITE")
    print("==========================================\n")
    try:
        test_sector_resolution()
        test_portfolio_health_scoring()
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
    except AssertionError as e:
        print("TEST ASSERTION FAILED!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print("TEST RUN ENCOUNTERED ERROR!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
