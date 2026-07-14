import sys
import os
import json
from dotenv import load_dotenv

# Set path to import from workspace
sys.path.append(r"C:\Users\HP1\.gemini\antigravity\scratch\portfolio-analyzer")

from research import ResearchManager

def main():
    load_dotenv()
    print("Loading active credentials from .env...")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    provider = os.getenv("RESEARCH_PROVIDER", "openrouter")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"OpenRouter Key: {'LOADED' if openrouter_key else 'MISSING'}")
    
    if not openrouter_key or "your_actual" in openrouter_key:
        print("Error: Live OpenRouter key is missing or is still a placeholder.")
        return
        
    print("\nInitializing ResearchManager...")
    manager = ResearchManager(api_key=gemini_key, openrouter_key=openrouter_key)
    
    test_stocks = ["RELIANCE", "HDFCBANK", "ICICIBANK"]
    print(f"Running batch analysis on {test_stocks} with force_refresh=True...")
    
    try:
        reports = manager.get_portfolio_research(test_stocks, force_refresh=True)
        print(f"\nSuccessfully generated {len(reports)} reports!")
        
        for idx, report in enumerate(reports):
            print(f"\n==========================================")
            print(f"Report {idx+1}: {report.stock}")
            print(f"==========================================")
            print(f"Research Available: {report.research_available}")
            print(f"Recommendation: {report.recommendation}")
            print(f"Confidence Pct: {report.confidence_score}%")
            print(f"Raw Score: {report.raw_score}/{report.max_score}")
            print(f"Target Price: {report.target_price}")
            print(f"Source(s) Used: {report.research_source}")
            print(f"Recommendation Type: {report.recommendation_type}")
            print(f"Report Date: {report.research_date}")
            print(f"Factors Breakdown: {json.dumps(report.factors_breakdown, indent=2)}")
            print(f"Key Reasons: {report.key_reasons}")
            print(f"Key Takeaway: {report.key_takeaway}")
            print(f"AI Provider Used: {report.ai_provider_used}")
            
            # Assertions to verify correctness
            assert report.stock in test_stocks
            assert report.raw_score is not None, "Raw score was not calculated"
            assert report.max_score == 10, f"Expected Max Score 10, got {report.max_score}"
            assert report.confidence_score == (report.raw_score / report.max_score) * 100, "Confidence calculation mismatch"
            assert isinstance(report.factors_breakdown, dict) and len(report.factors_breakdown) > 0, "Factors breakdown is missing or empty"
            assert report.research_date is not None, "Report date is missing"
            
        print("\nPASS: All live intelligence assertions verify successfully!")
    except Exception as e:
        print(f"\nFAIL: Intelligence validation encountered error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
