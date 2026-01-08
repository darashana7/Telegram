"""
Manual Scan Trigger Endpoint for Vercel
Allows triggering stock scans via HTTP requests
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_IDS = os.environ.get('TELEGRAM_CHAT_IDS', '').split(',')
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to Telegram"""
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
        print(f"Error: {e}")
        return False


def quick_check_stock(symbol: str) -> dict:
    """Check a single stock with full 9-point Minervini Trend Template"""
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="1y")
        
        if hist.empty:
            return {'symbol': symbol, 'error': 'No data'}
        
        # Current Metrics
        current_price = hist['Close'].iloc[-1]
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        
        # Moving Averages
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
        sma_150 = hist['Close'].rolling(window=150).mean().iloc[-1] if len(hist) >= 150 else None
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
        
        # 200 SMA Trend (22 days/1 month ago)
        sma_200_1m = hist['Close'].rolling(window=200).mean().iloc[-22] if len(hist) >= 222 else None
        
        pct_above_low = ((current_price - low_52w) / low_52w) * 100
        pct_from_high = ((high_52w - current_price) / high_52w) * 100
        
        # 9 Criteria Check
        criteria = {
            "1": sma_150 and current_price > sma_150,
            "2": sma_200 and current_price > sma_200,
            "3": sma_150 and sma_200 and sma_150 > sma_200,
            "4": sma_200 and sma_200_1m and sma_200 > sma_200_1m,
            "5": sma_50 and sma_150 and sma_50 > sma_150,
            "6": sma_50 and sma_200 and sma_50 > sma_200,
            "7": sma_50 and current_price > sma_50,
            "8": pct_above_low >= 30,
            "9": pct_from_high <= 25
        }
        
        score = sum(1 for v in criteria.values() if v)
        passes = score == 9
        
        return {
            'symbol': symbol,
            'price': round(float(current_price), 2),
            'score': score,
            'passes': passes,
            'sma_50': round(float(sma_50), 2) if sma_50 else None,
            'sma_150': round(float(sma_150), 2) if sma_150 else None,
            'sma_200': round(float(sma_200), 2) if sma_200 else None,
            'high_52w': round(float(high_52w), 2),
            'low_52w': round(float(low_52w), 2),
            'pct_above_low': round(float(pct_above_low), 1),
            'pct_from_high': round(float(pct_from_high), 1)
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}


class handler(BaseHTTPRequestHandler):
    """Scan endpoint handler"""
    
    def do_GET(self):
        """Handle scan requests"""
        try:
            # Parse query parameters
            query = parse_qs(urlparse(self.path).query)
            symbols = query.get('symbols', ['RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK'])[0].split(',')
            notify = query.get('notify', ['false'])[0].lower() == 'true'
            
            # Limit to 10 stocks for serverless timeout
            symbols = symbols[:10]
            
            results = []
            passing = []
            
            for symbol in symbols:
                symbol = symbol.strip().upper()
                if symbol:
                    result = quick_check_stock(symbol)
                    results.append(result)
                    if result.get('passes'):
                        passing.append(result)
            
            # Notify via Telegram if requested
            if notify and passing:
                message = f"🎯 <b>Scan Results</b>\n\n"
                message += f"Scanned: {len(results)} stocks\n"
                message += f"Passing: {len(passing)} stocks\n\n"
                
                for r in passing:
                    message += f"✅ <b>{r['symbol']}</b> | ₹{r['price']} | Score: {r['score']}/6\n"
                
                for chat_id in CHAT_IDS:
                    if chat_id.strip():
                        send_message(chat_id.strip(), message)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'success': True,
                'scanned': len(results),
                'passing': len(passing),
                'results': results
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def do_POST(self):
        """Handle POST scan requests with body"""
        self.do_GET()
