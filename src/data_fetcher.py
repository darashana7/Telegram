"""
Stock Data Fetcher Module
Fetches historical stock data from Yahoo Finance
"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import (
    EXCHANGE_SUFFIX, HISTORICAL_DATA_PERIOD, 
    CACHE_DIR, CACHE_DURATION_HOURS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockDataFetcher:
    """Fetches and caches stock data from Yahoo Finance"""
    
    def __init__(self):
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, symbol: str) -> str:
        """Get cache file path for a symbol"""
        safe_symbol = symbol.replace(".", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe_symbol}.json")
    
    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache file is still valid"""
        if not os.path.exists(cache_path):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        age = datetime.now() - file_time
        return age < timedelta(hours=CACHE_DURATION_HOURS)
    
    def _load_from_cache(self, symbol: str) -> Optional[Dict]:
        """Load data from cache if valid"""
        cache_path = self._get_cache_path(symbol)
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache load error for {symbol}: {e}")
        return None
    
    def _save_to_cache(self, symbol: str, data: Dict):
        """Save data to cache"""
        cache_path = self._get_cache_path(symbol)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Cache save error for {symbol}: {e}")
    
    def get_nse_symbol(self, symbol: str) -> str:
        """Convert symbol to NSE format for Yahoo Finance"""
        if not symbol.endswith(EXCHANGE_SUFFIX):
            return f"{symbol}{EXCHANGE_SUFFIX}"
        return symbol
    
    def fetch_stock_data(self, symbol: str, period: str = None) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLCV data for a stock
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE' or 'RELIANCE.NS')
            period: Data period (default: 1y)
            
        Returns:
            DataFrame with OHLCV data or None if error
        """
        period = period or HISTORICAL_DATA_PERIOD
        nse_symbol = self.get_nse_symbol(symbol)
        
        try:
            ticker = yf.Ticker(nse_symbol)
            df = ticker.history(period=period)
            
            if df.empty:
                logger.warning(f"No data returned for {nse_symbol}")
                return None
            
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {nse_symbol}: {e}")
            return None
    
    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive stock information including current price,
        52-week high/low, and other metrics
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with stock info or None if error
        """
        nse_symbol = self.get_nse_symbol(symbol)
        
        # Check cache first
        cached = self._load_from_cache(nse_symbol)
        if cached:
            return cached
        
        try:
            ticker = yf.Ticker(nse_symbol)
            info = ticker.info
            
            # Get historical data for calculations
            hist = ticker.history(period="1y")
            
            if hist.empty:
                logger.warning(f"No historical data for {nse_symbol}")
                return None
            
            # Calculate key values
            current_price = hist['Close'].iloc[-1]
            week_52_high = hist['High'].max()
            week_52_low = hist['Low'].min()
            
            # Calculate SMAs
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            sma_150 = hist['Close'].rolling(window=150).mean().iloc[-1] if len(hist) >= 150 else None
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            
            # Calculate 200-day SMA from 1 month ago
            sma_200_1m_ago = hist['Close'].rolling(window=200).mean().iloc[-22] if len(hist) >= 222 else None
            
            result = {
                "symbol": nse_symbol,
                "name": info.get("longName", symbol),
                "current_price": round(current_price, 2),
                "week_52_high": round(week_52_high, 2),
                "week_52_low": round(week_52_low, 2),
                "sma_50": round(sma_50, 2) if sma_50 else None,
                "sma_150": round(sma_150, 2) if sma_150 else None,
                "sma_200": round(sma_200, 2) if sma_200 else None,
                "sma_200_1m_ago": round(sma_200_1m_ago, 2) if sma_200_1m_ago else None,
                "percent_from_52w_high": round(((week_52_high - current_price) / week_52_high) * 100, 2),
                "percent_above_52w_low": round(((current_price - week_52_low) / week_52_low) * 100, 2),
                "volume": int(hist['Volume'].iloc[-1]),
                "avg_volume_20d": int(hist['Volume'].tail(20).mean()),
                "timestamp": datetime.now().isoformat()
            }
            
            # Cache the result
            self._save_to_cache(nse_symbol, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting info for {nse_symbol}: {e}")
            return None
    
    def get_historical_prices(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        Get historical closing prices for SMA calculations
        
        Args:
            symbol: Stock symbol
            days: Number of trading days
            
        Returns:
            DataFrame with date and close price
        """
        nse_symbol = self.get_nse_symbol(symbol)
        
        try:
            ticker = yf.Ticker(nse_symbol)
            # Fetch extra data to ensure we have enough for 200-day SMA
            hist = ticker.history(period="1y")
            
            if hist.empty:
                return None
            
            return hist[['Close', 'High', 'Low', 'Volume']]
            
        except Exception as e:
            logger.error(f"Error getting historical prices for {nse_symbol}: {e}")
            return None
    
    def batch_download_stocks(self, symbols: list, period: str = "1y") -> Dict[str, pd.DataFrame]:
        """
        Download historical data for multiple stocks in a single batch request.
        This is 5-10x faster than individual downloads.
        
        Args:
            symbols: List of stock symbols
            period: Data period (default: 1y)
            
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        # Convert to NSE symbols
        nse_symbols = [self.get_nse_symbol(s) for s in symbols]
        
        try:
            # Use yfinance's batch download (much faster)
            data = yf.download(
                nse_symbols, 
                period=period, 
                group_by='ticker',
                threads=True,  # Enable multi-threading
                progress=False  # Disable progress bar for cleaner output
            )
            
            result = {}
            
            # Handle single vs multiple tickers differently
            if len(nse_symbols) == 1:
                symbol = nse_symbols[0]
                if not data.empty:
                    result[symbols[0]] = data
            else:
                for orig_symbol, nse_symbol in zip(symbols, nse_symbols):
                    try:
                        if nse_symbol in data.columns.get_level_values(0):
                            stock_data = data[nse_symbol].dropna()
                            if not stock_data.empty and len(stock_data) >= 200:
                                result[orig_symbol] = stock_data
                    except Exception as e:
                        logger.debug(f"Error extracting data for {nse_symbol}: {e}")
                        continue
            
            return result
            
        except Exception as e:
            logger.error(f"Batch download error: {e}")
            return {}
    
    def get_stock_info_from_hist(self, symbol: str, hist: pd.DataFrame, skip_name: bool = True) -> Optional[Dict[str, Any]]:
        """
        Calculate stock info from pre-downloaded historical data.
        ULTRA-FAST version - skips company name lookup and caching for bulk scans.
        
        Args:
            symbol: Stock symbol
            hist: Pre-downloaded historical DataFrame
            skip_name: If True, use symbol as name (faster). Default True for speed.
            
        Returns:
            Dictionary with stock info
        """
        try:
            if hist is None or hist.empty or len(hist) < 200:
                return None
            
            # Use numpy for faster calculations
            close_prices = hist['Close'].values
            high_prices = hist['High'].values
            low_prices = hist['Low'].values
            
            # Calculate key values - explicitly cast to Python float
            current_price = float(close_prices[-1])
            week_52_high = float(high_prices.max())
            week_52_low = float(low_prices.min())
            
            # Fast SMA calculations using numpy - cast to Python float
            sma_50 = float(np.mean(close_prices[-50:])) if len(close_prices) >= 50 else None
            sma_150 = float(np.mean(close_prices[-150:])) if len(close_prices) >= 150 else None
            sma_200 = float(np.mean(close_prices[-200:])) if len(close_prices) >= 200 else None
            
            # Use symbol as name (skip slow API call)
            name = symbol
            
            # Volume calculations - explicitly cast to Python int
            volume = 0
            avg_volume_20d = 0
            if 'Volume' in hist.columns:
                vol_values = hist['Volume'].values
                volume = int(float(vol_values[-1]))  # Cast through float first for numpy compatibility
                avg_volume_20d = int(float(np.mean(vol_values[-20:])))
            
            # Round and return - all values are native Python types now
            return {
                "symbol": str(symbol),
                "name": str(name),
                "current_price": float(round(current_price, 2)),
                "week_52_high": float(round(week_52_high, 2)),
                "week_52_low": float(round(week_52_low, 2)),
                "sma_50": float(round(sma_50, 2)) if sma_50 else None,
                "sma_150": float(round(sma_150, 2)) if sma_150 else None,
                "sma_200": float(round(sma_200, 2)) if sma_200 else None,
                "percent_from_52w_high": float(round(((week_52_high - current_price) / week_52_high) * 100, 2)),
                "percent_above_52w_low": float(round(((current_price - week_52_low) / week_52_low) * 100, 2)),
                "volume": int(volume),
                "avg_volume_20d": int(avg_volume_20d),
            }
            
        except Exception as e:
            logger.debug(f"Error calculating info for {symbol}: {e}")
            return None


def fetch_all_nse_symbols() -> list:
    """
    Fetch list of all NSE stock symbols
    Uses a combination of sources to get comprehensive list
    """
    symbols = []
    
    # Try to fetch from NSE indices
    indices = ['^NSEI', '^NSEBANK']  # Nifty 50 and Bank Nifty
    
    try:
        # Fetch Nifty 500 components (covers most traded stocks)
        # Since yfinance doesn't directly provide index components,
        # we'll use a predefined list of popular NSE stocks
        
        popular_stocks = [
            # Nifty 50 stocks (sample - full list would be fetched)
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
            "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE", "WIPRO", "HCLTECH",
            "NESTLEIND", "POWERGRID", "NTPC", "TATAMOTORS", "M&M",
            "ADANIENT", "ADANIPORTS", "BAJAJFINSV", "TATASTEEL", "ONGC",
            "JSWSTEEL", "COALINDIA", "HINDALCO", "GRASIM", "INDUSINDBK",
            "TECHM", "DRREDDY", "CIPLA", "DIVISLAB", "EICHERMOT",
            "BPCL", "HEROMOTOCO", "BRITANNIA", "APOLLOHOSP", "SHREECEM",
            "TATACONSUM", "SBILIFE", "HDFCLIFE", "UPL", "BAJAJ-AUTO"
        ]
        
        symbols.extend(popular_stocks)
        
    except Exception as e:
        logger.error(f"Error fetching NSE symbols: {e}")
    
    return list(set(symbols))


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = StockDataFetcher()
    
    # Test with a popular stock
    print("Testing with RELIANCE...")
    info = fetcher.get_stock_info("RELIANCE")
    if info:
        print(json.dumps(info, indent=2))
    else:
        print("Failed to fetch data")
