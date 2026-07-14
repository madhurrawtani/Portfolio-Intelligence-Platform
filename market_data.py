import os
import json
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# =========================================================================
# PROVIDER ABSTRACTION LAYER FOR MARKET DATA ENGINE
# =========================================================================

class BaseMarketDataProvider:
    """
    Abstract Base Class for market data providers.
    All data providers must implement these methods.
    """
    def get_historical_data(self, ticker: str, days: int = 150) -> pd.DataFrame:
        raise NotImplementedError

    def get_benchmark_data(self, days: int = 150) -> pd.DataFrame:
        raise NotImplementedError

    def get_derivatives_data(self, ticker: str) -> dict:
        raise NotImplementedError

    def get_market_breadth_data(self) -> dict:
        raise NotImplementedError


# =========================================================================
# DATA VALIDATION AND REPAIR UTILITY
# =========================================================================

def validate_and_repair_data(df: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
    """
    Automatically validates and repairs historical price datasets.
    Checks for duplicates, missing dates, missing OHLC, invalid negative values, and sorting.
    """
    issues = []
    if df.empty:
        return df, ["DataFrame is empty"]

    # 1. Date conversion & type formatting
    try:
        df["Date"] = pd.to_datetime(df["Date"])
    except Exception as e:
        issues.append(f"Date conversion error: {str(e)}")
        
    # 2. Date ordering and index sorting
    initial_order_sorted = df["Date"].is_monotonic_increasing
    if not initial_order_sorted:
        issues.append("Date column was out of chronological order. Sorting applied.")
        df = df.sort_values(by="Date").reset_index(drop=True)

    # 3. Duplicate dates checking
    initial_len = len(df)
    df = df.drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    if len(df) < initial_len:
        issues.append(f"Removed {initial_len - len(df)} duplicate date row(s).")

    # 4. Column existence check
    ohlc_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    for col in ohlc_cols:
        if col not in df.columns:
            if col == "Adj Close" and "Close" in df.columns:
                df["Adj Close"] = df["Close"]
                issues.append("Missing column 'Adj Close', copied values from 'Close'.")
            else:
                df[col] = np.nan
                issues.append(f"Missing column '{col}', created it with NaN.")

    # 5. Type cast values to float
    for col in ohlc_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 6. Repair missing values (NaN) via forward & backward fill
    nan_counts = df[ohlc_cols].isna().sum()
    for col, count in nan_counts.items():
        if count > 0:
            issues.append(f"Found {count} missing values in '{col}'. Repaired using ffill & bfill.")
            df[col] = df[col].ffill().bfill()

    # 7. Check for invalid prices (negative or zero)
    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        negative_mask = df[col] <= 0
        if negative_mask.any():
            count = negative_mask.sum()
            issues.append(f"Found {count} negative or zero values in '{col}'. Repaired via ffill.")
            df.loc[negative_mask, col] = np.nan
            df[col] = df[col].ffill().bfill()

    # Ensure Date column is back to string for consistent storage/serialization
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df, issues


# =========================================================================
# PROVIDER IMPLEMENTATIONS
# =========================================================================

class YahooFinanceProvider(BaseMarketDataProvider):
    """
    Default Market Data Provider.
    Pulls data dynamically from Yahoo Finance v8 chart endpoint.
    Maintains a local historical database in data/historical/ with intelligent incremental updates.
    """
    def __init__(self, fallback_provider: Optional[BaseMarketDataProvider] = None, data_dir: str = "data/historical"):
        self.fallback_provider = fallback_provider
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _normalize_ticker(self, ticker: str) -> str:
        ticker_suffix = ticker.upper().strip()
        # Normalization suffix handling for Indian tickers vs US tickers
        if not ticker_suffix.endswith(".NS") and not ticker_suffix.endswith(".BO") and len(ticker_suffix) <= 6 and ticker_suffix != "SPY" and ticker_suffix != "QQQ":
            # If short ticker and not a known US ETF, try Indian NSE standard (.NS)
            ticker_suffix = f"{ticker_suffix}.NS"
        return ticker_suffix

    def _fetch_yahoo_chart_api(self, ticker: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        normalized_ticker = self._normalize_ticker(ticker)
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{normalized_ticker}?period1={start_ts}&period2={end_ts}&interval=1d"
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("chart", {}).get("result", [])
                if not result:
                    return None
                    
                chart_data = result[0]
                timestamps = chart_data.get("timestamp", [])
                if not timestamps:
                    return None
                    
                indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                adj_close_list = chart_data.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
                
                df = pd.DataFrame({
                    "Date": [datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in timestamps],
                    "Open": indicators.get("open", []),
                    "High": indicators.get("high", []),
                    "Low": indicators.get("low", []),
                    "Close": indicators.get("close", []),
                    "Volume": indicators.get("volume", [])
                })
                
                if adj_close_list:
                    df["Adj Close"] = adj_close_list
                else:
                    df["Adj Close"] = df["Close"]
                    
                return df
        except Exception:
            pass
        return None

    def get_historical_data(self, ticker: str, days: int = 150) -> pd.DataFrame:
        clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "").strip()
        csv_path = os.path.join(self.data_dir, f"{clean_ticker}.csv")
        
        df_local = pd.DataFrame()
        if os.path.exists(csv_path):
            try:
                df_local = pd.read_csv(csv_path)
            except Exception:
                pass
                
        today_date = datetime.now().date()
        
        # 1. Cache hit and Intelligent update logic
        if not df_local.empty and "Date" in df_local.columns:
            # Check last date in cache
            df_local["Date"] = pd.to_datetime(df_local["Date"])
            last_date_in_cache = df_local["Date"].max().date()
            
            # If last date in cache is today (or Friday/weekend), consider it up-to-date
            days_diff = (today_date - last_date_in_cache).days
            
            # Weekend adjust: if today is Monday and cache has Friday (3 days diff), or Sunday/Saturday
            is_weekend = today_date.weekday() >= 5
            cache_is_fresh = False
            if days_diff == 0:
                cache_is_fresh = True
            elif is_weekend and last_date_in_cache.weekday() == 4 and (today_date - last_date_in_cache).days <= 3:
                cache_is_fresh = True
                
            if cache_is_fresh:
                # Cache is current, reuse it directly
                df_local["Date"] = df_local["Date"].dt.strftime("%Y-%m-%d")
                cutoff = datetime.now() - timedelta(days=days)
                df_filtered = df_local[pd.to_datetime(df_local["Date"]) >= cutoff].reset_index(drop=True)
                return df_filtered
            else:
                # Cache is stale. Download only missing days incrementally.
                start_fetch = datetime.combine(last_date_in_cache + timedelta(days=1), datetime.min.time())
                end_fetch = datetime.now() + timedelta(days=1)
                
                df_new = self._fetch_yahoo_chart_api(ticker, start_fetch, end_fetch)
                if df_new is not None and not df_new.empty:
                    df_local["Date"] = df_local["Date"].dt.strftime("%Y-%m-%d")
                    # Merge and clean
                    df_combined = pd.concat([df_local, df_new], ignore_index=True)
                    df_clean, issues = validate_and_repair_data(df_combined)
                    df_clean.to_csv(csv_path, index=False)
                    
                    cutoff = datetime.now() - timedelta(days=days)
                    df_filtered = df_clean[pd.to_datetime(df_clean["Date"]) >= cutoff].reset_index(drop=True)
                    return df_filtered
                else:
                    # If download fails, reuse local cache anyway
                    df_local["Date"] = df_local["Date"].dt.strftime("%Y-%m-%d")
                    cutoff = datetime.now() - timedelta(days=days)
                    df_filtered = df_local[pd.to_datetime(df_local["Date"]) >= cutoff].reset_index(drop=True)
                    return df_filtered
        else:
            # No cache exists. Download complete history (default last 2 years for technical indicators)
            start_fetch = datetime.now() - timedelta(days=730)
            end_fetch = datetime.now() + timedelta(days=1)
            
            df_new = self._fetch_yahoo_chart_api(ticker, start_fetch, end_fetch)
            if df_new is not None and not df_new.empty:
                df_clean, issues = validate_and_repair_data(df_new)
                df_clean.to_csv(csv_path, index=False)
                
                cutoff = datetime.now() - timedelta(days=days)
                df_filtered = df_clean[pd.to_datetime(df_clean["Date"]) >= cutoff].reset_index(drop=True)
                return df_filtered

        # 2. Fallback provider
        if self.fallback_provider:
            return self.fallback_provider.get_historical_data(ticker, days)
        raise ValueError(f"Failed to obtain historical data for {ticker} from Yahoo Finance.")

    def get_benchmark_data(self, days: int = 150) -> pd.DataFrame:
        try:
            return self.get_historical_data("^NSEI", days)
        except Exception:
            try:
                return self.get_historical_data("^GSPC", days)
            except Exception:
                if self.fallback_provider:
                    return self.fallback_provider.get_benchmark_data(days)
                raise ValueError("Failed to retrieve benchmark data.")

    def get_derivatives_data(self, ticker: str) -> dict:
        if self.fallback_provider:
            return self.fallback_provider.get_derivatives_data(ticker)
        return MockProvider().get_derivatives_data(ticker)

    def get_market_breadth_data(self) -> dict:
        if self.fallback_provider:
            return self.fallback_provider.get_market_breadth_data()
        return MockProvider().get_market_breadth_data()


class CSVProvider(BaseMarketDataProvider):
    """
    CSV Provider.
    Pulls data strictly from pre-existing local CSV files.
    """
    def __init__(self, data_dir: str = "data/historical", fallback_provider: Optional[BaseMarketDataProvider] = None):
        self.data_dir = data_dir
        self.fallback_provider = fallback_provider

    def get_historical_data(self, ticker: str, days: int = 150) -> pd.DataFrame:
        clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "").strip()
        csv_path = os.path.join(self.data_dir, f"{clean_ticker}.csv")
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df_clean, issues = validate_and_repair_data(df)
                cutoff = datetime.now() - timedelta(days=days)
                df_filtered = df_clean[pd.to_datetime(df_clean["Date"]) >= cutoff].reset_index(drop=True)
                return df_filtered
            except Exception as e:
                pass
                
        if self.fallback_provider:
            return self.fallback_provider.get_historical_data(ticker, days)
        raise ValueError(f"CSV for {ticker} does not exist at {csv_path}.")

    def get_benchmark_data(self, days: int = 150) -> pd.DataFrame:
        # Check standard NIFTY file
        for name in ["^NSEI", "NSEI", "BENCHMARK"]:
            csv_path = os.path.join(self.data_dir, f"{name}.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df_clean, _ = validate_and_repair_data(df)
                cutoff = datetime.now() - timedelta(days=days)
                return df_clean[pd.to_datetime(df_clean["Date"]) >= cutoff].reset_index(drop=True)
                
        if self.fallback_provider:
            return self.fallback_provider.get_benchmark_data(days)
        raise ValueError("Benchmark CSV not found.")

    def get_derivatives_data(self, ticker: str) -> dict:
        if self.fallback_provider:
            return self.fallback_provider.get_derivatives_data(ticker)
        return MockProvider().get_derivatives_data(ticker)

    def get_market_breadth_data(self) -> dict:
        if self.fallback_provider:
            return self.fallback_provider.get_market_breadth_data()
        return MockProvider().get_market_breadth_data()


class MockProvider(BaseMarketDataProvider):
    """
    Deterministic Mock Provider that generates realistic data for testing and fallback.
    Utilizes hashing of the stock symbol to ensure consistency.
    """
    def __init__(self, seed_modifier: int = 42):
        self.seed_modifier = seed_modifier

    def _get_ticker_seed(self, ticker: str) -> int:
        return sum(ord(c) for c in ticker) + self.seed_modifier

    def get_historical_data(self, ticker: str, days: int = 150) -> pd.DataFrame:
        seed = self._get_ticker_seed(ticker)
        np.random.seed(seed)
        
        date_today = datetime.now()
        dates = [date_today - timedelta(days=i) for i in range(days)]
        dates.reverse()
        
        start_price = 100.0 + (seed % 1500)
        volatility = 0.015 + ((seed % 10) * 0.003)
        drift = 0.0002 + ((seed % 5) * 0.0001) - 0.0002
        
        prices = [start_price]
        for _ in range(1, days):
            change = np.random.normal(drift, volatility)
            prices.append(prices[-1] * (1.0 + change))
            
        highs = [p * (1.0 + abs(np.random.normal(0, volatility*0.5))) for p in prices]
        lows = [p * (1.0 - abs(np.random.normal(0, volatility*0.5))) for p in prices]
        opens = [p * (1.0 + np.random.normal(0, volatility*0.2)) for p in prices]
        
        for i in range(days):
            highs[i] = max(highs[i], opens[i], prices[i])
            lows[i] = min(lows[i], opens[i], prices[i])
            
        volumes = [int(100000 + (seed % 900000) * np.random.uniform(0.5, 2.0)) for _ in range(days)]
        
        df = pd.DataFrame({
            "Date": [d.strftime("%Y-%m-%d") for d in dates],
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": prices,
            "Adj Close": prices,
            "Volume": volumes
        })
        return df

    def get_benchmark_data(self, days: int = 150) -> pd.DataFrame:
        return self.get_historical_data("BENCHMARK", days)

    def get_derivatives_data(self, ticker: str) -> dict:
        seed = self._get_ticker_seed(ticker)
        np.random.seed(seed)
        
        buildups = ["Long Build-up", "Short Build-up", "Long Unwinding", "Short Covering"]
        buildup_idx = seed % len(buildups)
        
        pcr = 0.6 + (seed % 10) * 0.1
        iv = 15.0 + (seed % 40)
        iv_percentile = float(seed % 100)
        max_pain = 100.0 + (seed % 20) * 50.0
        
        open_interest = int(500000 + (seed % 10) * 100000)
        oi_change = float(-15.0 + (seed % 30) * 1.2)
        premium = 0.5 + (seed % 5) * 0.5
        
        return {
            "ticker": ticker,
            "open_interest": open_interest,
            "oi_change_pct": oi_change,
            "put_call_ratio": pcr,
            "implied_volatility": iv,
            "iv_percentile": iv_percentile,
            "max_pain": max_pain,
            "futures_premium_pct": premium,
            "buildup_type": buildups[buildup_idx]
        }

    def get_market_breadth_data(self) -> dict:
        return {
            "advance_decline_ratio": 1.25,
            "nifty_above_50ma_pct": 68.0,
            "nifty_above_200ma_pct": 72.0
        }
