"""
Cron Scan Handler for Vercel
Scans stocks in batches to avoid timeout
Stores results in Vercel KV (or JSON fallback)
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# Try to import yfinance
try:
    import yfinance as yf
except ImportError:
    yf = None

# Environment variables
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_IDS = os.environ.get('TELEGRAM_CHAT_IDS', '').split(',')
REDIS_URL = os.environ.get('REDIS_URL', '')

# Telegram API
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Scan settings
BATCH_SIZE = 30  # Stocks per invocation (safe for 10s timeout)
MIN_PERCENT_ABOVE_52W_LOW = 30
MAX_PERCENT_FROM_52W_HIGH = 25

# Redis client (lazy initialization)
_redis_client = None

def get_redis():
    """Get Redis client"""
    global _redis_client
    if _redis_client is None and REDIS_URL:
        try:
            import redis
            _redis_client = redis.from_url(REDIS_URL)
        except Exception as e:
            print(f"Redis init error: {e}")
    return _redis_client


def send_telegram(message: str) -> bool:
    """Send message to all Telegram users"""
    success = False
    for chat_id in CHAT_IDS:
        if chat_id.strip():
            try:
                response = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id.strip(),
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    },
                    timeout=10
                )
                if response.json().get('ok'):
                    success = True
            except:
                pass
    return success


# Robust KV operations
def kv_get(key: str):
    """Get value from Redis"""
    REDIS_URL = os.environ.get('REDIS_URL', '')
    if not REDIS_URL:
        return None
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        value = r.get(key)
        if value:
            try:
                return json.loads(value.decode('utf-8'))
            except:
                return value.decode('utf-8')
        return None
    except Exception as e:
        print(f"Redis GET error: {e}")
        return None


def kv_set(key: str, value, ex: int = None):
    """Set value in Redis"""
    REDIS_URL = os.environ.get('REDIS_URL', '')
    if not REDIS_URL:
        return False
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        if ex:
            r.setex(key, ex, value_str)
        else:
            r.set(key, value_str)
        return True
    except Exception as e:
        print(f"Redis SET error: {e}")
        return False



def get_all_stocks() -> list:
    """Get list of all NSE stocks to scan"""
    # 1. Try to get full list from CSV (Best source ~2000 stocks)
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from src.all_nse_stocks import get_all_nse_stocks
        stocks = get_all_nse_stocks()
        if stocks and len(stocks) > 1000:
            return stocks
    except Exception as e:
        print(f"Error loading full list: {e}")

    # 2. Fallback to Nifty 500 list
    try:
        from src.stock_list import get_nse_stock_list
        return get_nse_stock_list()
    except:
        pass
    
    # 3. Final fallback - top stocks
    return [
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", 
        "ITC", "SBIN", "LT", "AXISBANK", "MARUTI", "TITAN", "SUNPHARMA",
        "BAJFINANCE", "KOTAKBANK", "WIPRO", "HCLTECH", "TATAMOTORS", "M&M",
        "ADANIENT", "ASIANPAINT", "BAJAJFINSV", "ULTRACEMCO", "NESTLEIND",
        "TATASTEEL", "POWERGRID", "TECHM", "JSWSTEEL", "NTPC", "ONGC"
    ]


def check_stock_quick(symbol: str) -> dict:
    """Quick check if stock passes Minervini criteria"""
    try:
        # Append .NS if missing
        if not symbol.endswith('.NS'):
            ticker_symbol = f"{symbol}.NS"
        else:
            ticker_symbol = symbol
            
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1y")
        
        if hist.empty or len(hist) < 200:
            return None
        
        current_price = hist['Close'].iloc[-1]
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
        sma_150 = hist['Close'].rolling(window=150).mean().iloc[-1]
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        
        # Check 200 SMA trend
        sma_200_series = hist['Close'].rolling(window=200).mean()
        sma_200_trending = bool(sma_200_series.iloc[-1] > sma_200_series.iloc[-23])
        
        # Calculate all 9 criteria
        pct_above_low = ((current_price - low_52w) / low_52w) * 100
        pct_from_high = ((high_52w - current_price) / high_52w) * 100
        
        criteria = {
            '1': bool(current_price > sma_150),
            '2': bool(current_price > sma_200),
            '3': bool(sma_150 > sma_200),
            '4': sma_200_trending,
            '5': bool(sma_50 > sma_150),
            '6': bool(sma_50 > sma_200),
            '7': bool(current_price > sma_50),
            '8': bool(pct_above_low >= MIN_PERCENT_ABOVE_52W_LOW),
            '9': bool(pct_from_high <= MAX_PERCENT_FROM_52W_HIGH)
        }
        
        score = sum(1 for v in criteria.values() if v)
        
        # Return result if score is high enough (e.g. 9/9)
        if score >= 9:
            return {
                'symbol': symbol,
                'price': round(float(current_price), 2),
                'score': score,
                'sma_50': round(float(sma_50), 2),
                'sma_150': round(float(sma_150), 2),
                'sma_200': round(float(sma_200), 2),
                'pct_from_high': round(float(pct_from_high), 1),
                'pct_above_low': round(float(pct_above_low), 1)
            }
        return None
        
    except Exception as e:
        return None


def run_batch_scan():
    """Run a batch scan of stocks with time limit"""
    start_time = time.time()
    MAX_DURATION = 9  # Seconds (safe for Free tier 10s limit)
    
    if not yf:
        return {"error": "yfinance not available"}
    
    # Get current offset
    offset = kv_get("scan_offset") or 0
    if isinstance(offset, str):
        offset = int(offset)
    
    all_stocks = get_all_stocks()
    total = len(all_stocks)
    
    # Get current results
    current_results = kv_get("scan_results") or []
    if not isinstance(current_results, list):
        current_results = []
    
    # Check if we should start a new scan
    if offset == 0:
        # Check last scan time to prevent spamming
        last_complete = kv_get("last_scan_complete")
        if last_complete:
            try:
                last_dt = datetime.fromisoformat(last_complete)
                hours_diff = (datetime.now() - last_dt).total_seconds() / 3600
                if hours_diff < 4:  # Wait at least 4 hours between full scans
                    return {
                        "status": "waiting",
                        "message": f"Last scan was {hours_diff:.1f} hours ago. Waiting for 4h cooldown."
                    }
            except:
                pass
        
        # Start new scan
        current_results = []
    
    scanned_count = 0
    new_results = []
    
    # Process stocks until timeout
    while time.time() - start_time < MAX_DURATION and offset < total:
        symbol = all_stocks[offset]
        
        # Skip if symbol is bad
        if symbol:
            result = check_stock_quick(symbol)
            if result:
                new_results.append(result)
        
        offset += 1
        scanned_count += 1
    
    # Merge results
    all_results = current_results + new_results
    
    # Check completion
    is_complete = offset >= total
    
    if is_complete:
        offset = 0 # Reset for next cycle
        kv_set("last_scan_complete", datetime.now().isoformat())
        
        # Format and send results using telegram
        if all_results:
            msg = f"🎯 <b>Scan Complete!</b>\n\n"
            msg += f"📊 Scanned: {total} stocks\n"
            msg += f"✅ Found: {len(all_results)} qualifying stocks\n\n"
            
            # Show top 15 results
            for r in all_results[:15]:
                price = r.get('price', 0)
                msg += f"• <b>{r['symbol']}</b> ₹{price:,.2f}\n"
            
            if len(all_results) > 15:
                msg += f"\n...and {len(all_results) - 15} more. Use /list to see all."
                
            send_telegram(msg)
        else:
            send_telegram(f"🎯 <b>Scan Complete!</b>\nScanned {total} stocks. No matches found.")
            
    # Save state
    kv_set("scan_offset", offset)
    kv_set("scan_results", all_results)
    
    return {
        "status": "partial_complete" if not is_complete else "scan_complete",
        "processed": scanned_count,
        "offset": offset,
        "total": total,
        "found_total": len(all_results),
        "found_in_batch": len(new_results),
        "next_offset": offset
    }


class handler(BaseHTTPRequestHandler):
    """Cron scan handler"""
    
    def do_GET(self):
        """Handle cron trigger"""
        from urllib.parse import parse_qs, urlparse
        
        try:
            # Parse query parameters
            query = parse_qs(urlparse(self.path).query)
            
            # Allow manual offset override via query param
            manual_offset = query.get('offset', [None])[0]
            if manual_offset is not None:
                kv_set("scan_offset", int(manual_offset))
            
            # Check if this is a reset request
            if 'reset' in query:
                kv_set("scan_offset", 0)
                kv_set("scan_results", [])
            
            result = run_batch_scan()
            
            # Add qualifying stocks to response if any were found
            if result.get('total_found', 0) > 0:
                found_stocks = kv_get("scan_results") or []
                result['qualifying_stocks'] = found_stocks[:50]  # Limit to 50 for response size
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        except Exception as e:
            import traceback
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_detail = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "kv_url_set": bool(KV_REST_API_URL),
                "kv_token_set": bool(KV_REST_API_TOKEN)
            }
            self.wfile.write(json.dumps(error_detail).encode())
    
    def do_POST(self):
        """Also handle POST for flexibility"""
        self.do_GET()
