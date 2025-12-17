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


# Simple KV operations using Redis
def kv_get(key: str):
    """Get value from Redis"""
    r = get_redis()
    if not r:
        print("Redis not available")
        return None
    try:
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
    r = get_redis()
    if not r:
        print("Redis not available for SET")
        return False
    try:
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
    # Try to load from validated stocks file first
    try:
        data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'valid_nse_stocks.json')
        with open(data_path, 'r') as f:
            data = json.load(f)
            return data.get('valid_stocks', [])
    except:
        pass
    
    # Fallback to top 500 stocks
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from src.stock_list import get_nse_stock_list
        return get_nse_stock_list()
    except:
        pass
    
    # Final fallback - top stocks
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
        ticker = yf.Ticker(f"{symbol}.NS")
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
        
        if score >= 9:  # Only return perfect matches
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
    """Run a batch scan of stocks"""
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
    
    # Check if we're starting a new scan
    if offset == 0:
        current_results = []
    
    # Get batch
    batch = all_stocks[offset:offset + BATCH_SIZE]
    
    if not batch:
        # Scan complete - reset
        kv_set("scan_offset", 0)
        kv_set("last_scan_complete", datetime.now().isoformat())
        return {
            "status": "scan_complete",
            "total_stocks": total,
            "qualifying_stocks": len(current_results),
            "results": current_results
        }
    
    # Scan batch
    new_results = []
    scanned = 0
    for symbol in batch:
        result = check_stock_quick(symbol)
        if result:
            new_results.append(result)
        scanned += 1
    
    # Merge results
    all_results = current_results + new_results
    
    # Update offset
    new_offset = offset + BATCH_SIZE
    is_complete = new_offset >= total
    
    if is_complete:
        new_offset = 0
        kv_set("last_scan_complete", datetime.now().isoformat())
        
        # Send Telegram notification if we found stocks
        if all_results:
            msg = f"🎯 <b>Scan Complete!</b>\n\n"
            msg += f"📊 Scanned: {total} stocks\n"
            msg += f"✅ Found: {len(all_results)} qualifying stocks\n\n"
            for r in all_results[:10]:
                msg += f"• <b>{r['symbol']}</b> ₹{r['price']:,.2f}\n"
            if len(all_results) > 10:
                msg += f"\n...and {len(all_results) - 10} more"
            send_telegram(msg)
    
    # Save state
    kv_set("scan_offset", new_offset)
    kv_set("scan_results", all_results)
    
    return {
        "status": "batch_complete" if not is_complete else "scan_complete",
        "batch": f"{offset+1}-{min(offset+BATCH_SIZE, total)}/{total}",
        "scanned": scanned,
        "found_in_batch": len(new_results),
        "total_found": len(all_results),
        "next_offset": new_offset,
        "is_complete": is_complete
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
