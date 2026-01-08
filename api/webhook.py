"""
Telegram Webhook Handler for Vercel Serverless
Handles incoming Telegram bot updates via webhooks
Implements full Minervini 9-criteria screening
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# Environment variables with fallback
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '') or '8550797252:AAG_P9X-9RxOQyIz-N2LAHiGJhnBKzAF5W8'
CHAT_IDS = os.environ.get('TELEGRAM_CHAT_IDS', '').split(',')

# Telegram API base
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Minervini criteria thresholds
MIN_PERCENT_ABOVE_52W_LOW = 30
MAX_PERCENT_FROM_52W_HIGH = 25
MIN_200_SMA_UPTREND_DAYS = 22


def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to a Telegram chat"""
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            },
            timeout=30
        )
        return response.json().get('ok', False)
    except Exception as e:
        print(f"Error sending message: {e}")
        return False


def handle_start(chat_id: str) -> str:
    """Handle /start command"""
    return """
🎯 <b>Minervini Stock Screener Bot</b>

Welcome! I can help you find stocks that meet Mark Minervini's Trend Template criteria.

<b>Available Commands:</b>

📊 /scan - Quick scan (top 50 stocks)
📋 /list - Show eligible stocks (full list)
🔍 /check SYMBOL - Check a specific stock
📈 /fullscan - Nifty 500 scan (~500 stocks)
🌐 /scanall - ALL NSE stocks (~2000 stocks)
🏛️ /nse - Show all available stocks
ℹ️ /help - Show this help message

<b>Minervini's 9 Criteria:</b>
1️⃣ Price > 150-day SMA
2️⃣ Price > 200-day SMA  
3️⃣ 150-day SMA > 200-day SMA
4️⃣ 200-day SMA trending up (1 month)
5️⃣ 50-day SMA > 150-day SMA
6️⃣ 50-day SMA > 200-day SMA
7️⃣ Price > 50-day SMA
8️⃣ Price ≥30% above 52-week low
9️⃣ Price within 25% of 52-week high

Type a command to get started!
    """.strip()


def handle_check(chat_id: str, symbol: str) -> str:
    """Handle /check command - check a specific stock with all 9 criteria"""
    try:
        import yfinance as yf
        import pandas as pd
        
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="1y")
        info = ticker.info
        
        if hist.empty:
            return f"❌ Could not fetch data for {symbol}. Please check the symbol."
        
        days_available = len(hist)
        
        if days_available < 50:
            return f"❌ Only {days_available} days of data available for {symbol}. Need at least 50 days."
        
        # Calculate all metrics
        current_price = hist['Close'].iloc[-1]
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        
        # Calculate SMAs
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if days_available >= 50 else None
        sma_150 = hist['Close'].rolling(window=150).mean().iloc[-1] if days_available >= 150 else None
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if days_available >= 200 else None
        
        # Calculate 200-day SMA trend (compare current vs 22 days ago)
        sma_200_trending_up = False
        if days_available >= 222:
            sma_200_series = hist['Close'].rolling(window=200).mean()
            current_sma_200 = sma_200_series.iloc[-1]
            past_sma_200 = sma_200_series.iloc[-23]  # ~1 month ago
            sma_200_trending_up = current_sma_200 > past_sma_200
        
        # Calculate percentages
        pct_above_low = ((current_price - low_52w) / low_52w) * 100
        pct_from_high = ((high_52w - current_price) / high_52w) * 100
        
        # Check ALL 9 criteria
        criteria = {}
        score = 0
        
        # Criteria 1: Price > 150-day SMA
        if sma_150:
            criteria['1_price_above_150sma'] = current_price > sma_150
        else:
            criteria['1_price_above_150sma'] = None  # Not enough data
        
        # Criteria 2: Price > 200-day SMA
        if sma_200:
            criteria['2_price_above_200sma'] = current_price > sma_200
        else:
            criteria['2_price_above_200sma'] = None
        
        # Criteria 3: 150-day SMA > 200-day SMA
        if sma_150 and sma_200:
            criteria['3_150sma_above_200sma'] = sma_150 > sma_200
        else:
            criteria['3_150sma_above_200sma'] = None
        
        # Criteria 4: 200-day SMA trending up
        if days_available >= 222:
            criteria['4_200sma_trending_up'] = sma_200_trending_up
        else:
            criteria['4_200sma_trending_up'] = None
        
        # Criteria 5: 50-day SMA > 150-day SMA
        if sma_50 and sma_150:
            criteria['5_50sma_above_150sma'] = sma_50 > sma_150
        else:
            criteria['5_50sma_above_150sma'] = None
        
        # Criteria 6: 50-day SMA > 200-day SMA
        if sma_50 and sma_200:
            criteria['6_50sma_above_200sma'] = sma_50 > sma_200
        else:
            criteria['6_50sma_above_200sma'] = None
        
        # Criteria 7: Price > 50-day SMA
        if sma_50:
            criteria['7_price_above_50sma'] = current_price > sma_50
        else:
            criteria['7_price_above_50sma'] = None
        
        # Criteria 8: Price >= 30% above 52-week low
        criteria['8_price_30pct_above_52w_low'] = pct_above_low >= MIN_PERCENT_ABOVE_52W_LOW
        
        # Criteria 9: Price within 25% of 52-week high
        criteria['9_price_within_25pct_of_52w_high'] = pct_from_high <= MAX_PERCENT_FROM_52W_HIGH
        
        # Count score - properly handle numpy booleans by converting to Python bool
        score = 0
        for key, value in criteria.items():
            if value is not None and bool(value) == True:
                score += 1
        
        total_criteria = sum(1 for v in criteria.values() if v is not None)
        passes_all = score == 9 and total_criteria == 9
        
        status = "✅ PASSES ALL 9!" if passes_all else f"❌ FAILS ({score}/{total_criteria})"
        
        # Build message
        message = f"""
📊 <b>{symbol}</b> - {info.get('shortName', symbol)}

<b>Score: {score}/9 {status}</b>

💰 <b>Current Price:</b> ₹{current_price:,.2f}

📊 <b>Moving Averages:</b>
• 50-day SMA: {f"₹{sma_50:,.2f}" if sma_50 else "N/A (need 50+ days)"}
• 150-day SMA: {f"₹{sma_150:,.2f}" if sma_150 else "N/A (need 150+ days)"}
• 200-day SMA: {f"₹{sma_200:,.2f}" if sma_200 else "N/A (need 200+ days)"}

📈 <b>52-Week Range:</b>
• High: ₹{high_52w:,.2f} ({pct_from_high:.1f}% away)
• Low: ₹{low_52w:,.2f} ({pct_above_low:.1f}% above)

<b>Minervini 9 Criteria:</b>
"""
        
        criteria_labels = {
            '1_price_above_150sma': 'Price > 150 SMA',
            '2_price_above_200sma': 'Price > 200 SMA',
            '3_150sma_above_200sma': '150 SMA > 200 SMA',
            '4_200sma_trending_up': '200 SMA Uptrend',
            '5_50sma_above_150sma': '50 SMA > 150 SMA',
            '6_50sma_above_200sma': '50 SMA > 200 SMA',
            '7_price_above_50sma': 'Price > 50 SMA',
            '8_price_30pct_above_52w_low': '≥30% above 52W Low',
            '9_price_within_25pct_of_52w_high': 'Within 25% of 52W High'
        }
        
        for key, value in criteria.items():
            label = criteria_labels.get(key, key)
            if value is None:
                icon = "⚠️"
                message += f"{icon} {label} (need more data)\n"
            elif value:
                icon = "✅"
                message += f"{icon} {label}\n"
            else:
                icon = "❌"
                message += f"{icon} {label}\n"
        
        if days_available < 200:
            message += f"\n⚠️ <i>Only {days_available} days of data. Full analysis needs 200+ days.</i>"
        
        return message.strip()
        
    except Exception as e:
        return f"❌ Error checking {symbol}: {str(e)}"


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
    except:
        return None


def handle_list(chat_id: str) -> str:
    """Handle /list command - show cached scan results from file"""
    # Try to load scan results from JSON file
    results = None
    last_scan = None
    
    try:
        scan_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'scan_results.json')
        with open(scan_file, 'r') as f:
            data = json.load(f)
            results = data.get('results', [])
            last_scan = data.get('timestamp', '')
    except Exception as e:
        print(f"Error loading scan results: {e}")
    
    # Also try fullscan/scanall results if available
    if not results:
        try:
            scan_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'scan_results.json')
            with open(scan_file, 'r') as f:
                data = json.load(f)
                # Check for scanall or fullscan
                if 'scanall' in data:
                    results = data['scanall'].get('results', [])
                    last_scan = data['scanall'].get('timestamp', '')
                elif 'fullscan' in data:
                    results = data['fullscan'].get('results', [])
                    last_scan = data['fullscan'].get('timestamp', '')
        except:
            pass
    
    if not results:
        return """
📋 <b>No Scan Results Available</b>

Scans run automatically twice daily (10 AM & 3:30 PM IST).

💡 While waiting, you can:
• /check SYMBOL - Check individual stocks
• Just type a symbol like <code>RELIANCE</code>

<b>Popular stocks to check:</b>
RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK
        """.strip()
    
    # Format timestamp
    time_str = ""
    if last_scan:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(last_scan.replace('Z', '+00:00'))
            time_str = dt.strftime("%d-%b-%Y %H:%M")
        except:
            time_str = last_scan[:16]
    
    # Format results
    message = f"📋 <b>Qualifying Stocks (9/9 Criteria)</b>\n\n"
    if time_str:
        message += f"🕐 Last scan: {time_str}\n"
    message += f"✅ Found: {len(results)} stocks\n\n"
    
    for i, r in enumerate(results[:25], 1):
        symbol = r.get('symbol', 'N/A')
        price = r.get('price', r.get('current_price', 0))
        pct_from_high = r.get('pct_from_high', 0)
        message += f"{i}. <b>{symbol}</b> ₹{price:,.2f}"
        if pct_from_high:
            message += f" ({pct_from_high:.1f}% from high)"
        message += "\n"
    
    if len(results) > 25:
        message += f"\n...and {len(results) - 25} more stocks"
    
    message += "\n\n💡 Use /check SYMBOL for detailed analysis"
    
    return message.strip()


def handle_scan_quick(chat_id: str) -> str:
    """Handle quick scan - returns cached results or triggers scan"""
    # Check if we have cached results
    results = kv_get("scan_results")
    
    if results:
        return handle_list(chat_id)
    
    return """
🔍 <b>Scan System</b>

Scans run automatically every hour during market hours (9 AM - 3 PM IST).

<b>Current commands:</b>
• /list - View last scan results
• /check SYMBOL - Check individual stock

<b>Popular stocks to check:</b>
RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK
BHARTIARTL, ITC, SBIN, LT, AXISBANK
    """.strip()


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


def handle_scan_all(chat_id: str) -> str:
    """Handle /scanall command - initiate background full scan"""
    # Reset scan state
    if kv_set("scan_offset", 0) and kv_set("scan_results", []):
        return """
🔍 <b>Full Scan Initiated</b>

I have queued a full scan of all ~2000 NSE stocks.
This will run in the background.

<b>Progress:</b>
• Stocks: All NSE (~2000)
• Time: ~20-40 mins (depending on queue)
• You will receive a full report when complete.

You can check progress occasionally with /status (coming soon) or just wait for the notification!
        """.strip()
    else:
        return "❌ Error initiating scan. Database connection failed."


def process_update(update: dict) -> None:
    """Process incoming Telegram update"""
    try:
        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '').strip()
        
        if not chat_id or not text:
            return
        
        # Handle commands
        if text.startswith('/start') or text.startswith('/help'):
            response = handle_start(chat_id)
        elif text.startswith('/check'):
            parts = text.split()
            if len(parts) >= 2:
                symbol = parts[1].upper()
                response = handle_check(chat_id, symbol)
            else:
                response = "❌ Please provide a stock symbol.\nExample: /check RELIANCE"
        elif text.startswith('/scanall'):
            response = handle_scan_all(chat_id)
        elif text.startswith('/scan') or text.startswith('/fullscan'):
            response = handle_scan_quick(chat_id)
        elif text.startswith('/nse'):
            response = """
🏛️ <b>NSE Stocks</b>

Use /check SYMBOL to check any stock with all 9 Minervini criteria.

<b>Popular stocks:</b>
• RELIANCE, TCS, INFY, HDFCBANK
• ICICIBANK, BHARTIARTL, ITC, SBIN
• LT, AXISBANK, MARUTI, TITAN
• SUNPHARMA, BAJFINANCE, KOTAKBANK

To scan all 2000+ stocks, use /scanall
            """.strip()
        elif text.startswith('/list'):
            response = handle_list(chat_id)
        elif text.replace('.', '').replace('-', '').isalnum() and len(text) <= 20 and not text.startswith('/'):
            # Treat as stock symbol
            response = handle_check(chat_id, text.upper())
        else:
            response = "💡 Send a stock symbol to check it, or use /help for commands."
        
        send_message(chat_id, response)
        
    except Exception as e:
        print(f"Error processing update: {e}")


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_POST(self):
        """Handle POST requests (webhook updates from Telegram)"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            update = json.loads(body.decode('utf-8'))
            
            # Process the update
            process_update(update)
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode())
            
        except Exception as e:
            print(f"Webhook error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'error': str(e)}).encode())
    
    def do_GET(self):
        """Handle GET requests (for health checks)"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            'status': 'ok',
            'message': 'Minervini Bot Webhook is running',
            'criteria': '9 Minervini Trend Template criteria'
        }).encode())
