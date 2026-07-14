import os
import shutil
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from market_data import (
    BaseMarketDataProvider,
    YahooFinanceProvider,
    CSVProvider,
    MockProvider,
    validate_and_repair_data
)
from market_intelligence import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_adx,
    TechnicalAnalysisEngine,
    LiquidityEngine,
    MarketBreadthEngine,
    MarketIntelligenceManager
)

def run_tests():
    print("=========================================================================")
    print(" RUNNING PHASE 8: MARKET DATA ENGINE & VALIDATION SUITE")
    print("=========================================================================")

    # Setup temp testing directory for historical data
    test_data_dir = "data/test_historical"
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)
    os.makedirs(test_data_dir, exist_ok=True)

    try:
        # ---------------------------------------------------------------------
        # TEST 1: DATA VALIDATION & REPAIR
        # ---------------------------------------------------------------------
        print("\n[TEST 1] Testing Data Validation and Repair Utility...")
        
        # Create a raw messy DataFrame
        dates = ["2026-07-03", "2026-07-01", "2026-07-02", "2026-07-02"] # unsorted & duplicate
        df_messy = pd.DataFrame({
            "Date": dates,
            "Open": [100.0, np.nan, 102.0, 102.0],
            "High": [105.0, 103.0, 104.0, 104.0],
            "Low": [98.0, 97.0, -5.0, 99.0], # negative Low
            "Close": [104.0, 101.0, 103.0, 103.0],
            "Volume": [10000, 12000, 11000, 11000]
        })
        
        df_clean, issues = validate_and_repair_data(df_messy)
        
        # Assertions
        assert len(df_clean) == 3, f"Expected 3 rows after duplicate removal, got {len(df_clean)}"
        assert df_clean["Date"].is_monotonic_increasing, "Date column should be sorted chronologically"
        assert not df_clean.isna().any().any(), "DataFrame should not contain NaN values after repair"
        assert (df_clean["Low"] > 0).all(), "Negative value should have been repaired"
        assert len(issues) > 0, "Expected validation issues to be reported"
        
        print("-> Messy data issues detected and repaired successfully:")
        for issue in issues:
            print(f"   * {issue}")
        print("[OK] TEST 1 PASSED!")

        # ---------------------------------------------------------------------
        # TEST 2: TECHNICAL INDICATORS MATH
        # ---------------------------------------------------------------------
        print("\n[TEST 2] Testing Technical Indicators Math...")
        mock_provider = MockProvider()
        df_tech = mock_provider.get_historical_data("TEST_STOCK", days=100)
        
        close_series = df_tech["Close"]
        rsi = calculate_rsi(close_series, 14)
        macd, macd_sig, macd_hist = calculate_macd(close_series)
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close_series)
        atr = calculate_atr(df_tech, 14)
        adx = calculate_adx(df_tech, 14)
        
        # Assertions
        assert len(rsi) == 100, "RSI length mismatch"
        assert rsi.dropna().min() >= 0 and rsi.dropna().max() <= 100, "RSI out of bounds"
        assert len(macd) == 100 and len(macd_sig) == 100 and len(macd_hist) == 100, "MACD length mismatch"
        assert (bb_upper.dropna() >= bb_mid.dropna()).all() and (bb_mid.dropna() >= bb_lower.dropna()).all(), "Bollinger Bands boundary violation"
        assert len(atr) == 100, "ATR length mismatch"
        assert len(adx) == 100, "ADX length mismatch"
        
        print("[OK] Technical indicator mathematical engines calculated without bounds failures.")
        print("[OK] TEST 2 PASSED!")

        # ---------------------------------------------------------------------
        # TEST 3: PROVIDER SWITCHING & MOCK ENGINE
        # ---------------------------------------------------------------------
        print("\n[TEST 3] Testing Provider Abstraction and Switching...")
        
        # We can switch providers at runtime since all inherit from BaseMarketDataProvider
        providers = [
            MockProvider(),
            CSVProvider(data_dir=test_data_dir, fallback_provider=MockProvider()),
            YahooFinanceProvider(data_dir=test_data_dir, fallback_provider=MockProvider())
        ]
        
        for p in providers:
            # All must support historical query
            df = p.get_historical_data("TCS", days=50)
            assert not df.empty, f"Provider {p.__class__.__name__} failed to fetch historical data"
            assert "Open" in df.columns and "Close" in df.columns, f"Provider {p.__class__.__name__} returned missing columns"
            
            # All must support benchmark
            df_b = p.get_benchmark_data(days=50)
            assert not df_b.empty, f"Provider {p.__class__.__name__} failed to fetch benchmark data"
            
            # All must support derivatives details
            deriv = p.get_derivatives_data("TCS")
            assert isinstance(deriv, dict), f"Provider {p.__class__.__name__} failed to return derivatives dictionary"
            assert "open_interest" in deriv, "Derivatives details missing 'open_interest'"
            
        print("[OK] All provider modules adhere correctly to BaseMarketDataProvider abstract interface.")
        print("[OK] TEST 3 PASSED!")

        # ---------------------------------------------------------------------
        # TEST 4: DOCKING LOCAL HISTORICAL CACHE & INCREMENTAL UPDATES
        # ---------------------------------------------------------------------
        print("\n[TEST 4] Testing Cache Creation and Incremental Updates...")
        
        # We use the YahooFinanceProvider with mock fallback to test directory caching
        # MockProvider is used as fallback to avoid rate limits / network queries during test execution
        m_fallback = MockProvider()
        yf_provider = YahooFinanceProvider(data_dir=test_data_dir, fallback_provider=m_fallback)
        
        # 1. Test cache creation (initial save)
        ticker_test = "INFY"
        csv_filepath = os.path.join(test_data_dir, f"{ticker_test}.csv")
        assert not os.path.exists(csv_filepath), "Test file should not exist initially"
        
        df_first = yf_provider.get_historical_data(ticker_test, days=100)
        assert os.path.exists(csv_filepath), "YahooFinanceProvider did not write cache file to disk"
        
        # 2. Test cache hit (re-read without downloading)
        # We modify the written CSV on disk to check if it gets reused
        df_disk = pd.read_csv(csv_filepath)
        sentinel_price = 9999.0
        df_disk.loc[df_disk.index[-1], "Close"] = sentinel_price
        df_disk.to_csv(csv_filepath, index=False)
        
        # Query again. It should read from file directly without pulling new mock data since last date matches today.
        df_second = yf_provider.get_historical_data(ticker_test, days=100)
        assert df_second["Close"].iloc[-1] == sentinel_price, "Intelligent update did not hit local cache"
        print("[OK] Cached local historical CSV retrieved successfully on subsequent request.")
        
        # 3. Test incremental update (pulling new data)
        # We modify the CSV to make the last date look 10 days older, so it triggers incremental update
        df_stale = pd.read_csv(csv_filepath)
        df_stale["Date"] = pd.to_datetime(df_stale["Date"])
        last_date = df_stale["Date"].max()
        stale_offset = 10
        df_stale["Date"] = df_stale["Date"] - timedelta(days=stale_offset)
        df_stale["Date"] = df_stale["Date"].dt.strftime("%Y-%m-%d")
        df_stale.to_csv(csv_filepath, index=False)
        
        # Now query again. Since last date in cache is 10 days ago, it will download and append the missing days.
        df_updated = yf_provider.get_historical_data(ticker_test, days=100)
        
        # The updated df should have rows with the current dates restored
        last_date_updated = pd.to_datetime(df_updated["Date"]).max().date()
        assert last_date_updated == datetime.now().date(), f"Incremental update failed to restore current date, got {last_date_updated}"
        
        print("[OK] Cache stale check correctly triggered incremental downloader and appended new records.")
        print("[OK] TEST 4 PASSED!")

        # ---------------------------------------------------------------------
        # TEST 5: CONSOLIDATED MARKET INTELLIGENCE SCORE RUN
        # ---------------------------------------------------------------------
        print("\n[TEST 5] Testing Integrated Market Intelligence Engine...")
        
        manager = MarketIntelligenceManager(yf_provider)
        tickers = ["RELIANCE", "TCS", "INFY"]
        intel_payload = manager.evaluate_market_intelligence(tickers)
        
        assert "overall_score" in intel_payload, "Missing overall score"
        assert "technical_score" in intel_payload, "Missing technical score"
        assert "derivatives_score" in intel_payload, "Missing derivatives score"
        assert "liquidity_score" in intel_payload, "Missing liquidity score"
        assert "market_breadth_score" in intel_payload, "Missing market breadth score"
        assert len(intel_payload["stock_details"]) == 3, "Missing detail nodes for stocks"
        
        print(f"-> Combined Overall Intelligence Score: {intel_payload['overall_score']}/100")
        print(f"-> Tech Score: {intel_payload['technical_score']}, Derivatives Score: {intel_payload['derivatives_score']}")
        print(f"-> Breadth: {intel_payload['summaries']['breadth']}")
        print("[OK] TEST 5 PASSED!")

        print("\n=========================================================================")
        print(" ALL PHASE 8 MARKET DATA ENGINE TESTS PASSED SUCCESSFULLY!")
        print("=========================================================================")
        return True

    except Exception as test_err:
        print(f"\n[FAIL] TEST FAILED: {str(test_err)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup test directory
        if os.path.exists(test_data_dir):
            shutil.rmtree(test_data_dir)

if __name__ == "__main__":
    run_tests()
