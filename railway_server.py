"""
Railway Backend Server
Runs the Telegram bot + HTTP API for Vercel frontend
"""
import os
import sys
import json
import asyncio
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.minervini_screener import MinerviniScreener
from src.stock_list import get_nse_stock_list

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for Vercel frontend

# Initialize screener
screener = MinerviniScreener()

# Store for scan results
scan_state = {
    "status": "idle",
    "progress": 0,
    "total": 0,
    "results": [],
    "last_scan": None,
    "is_scanning": False
}


@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        "service": "Minervini Stock Screener API",
        "version": "2.0",
        "status": "running",
        "endpoints": {
            "/api/health": "Health check",
            "/api/scan": "Quick scan stocks",
            "/api/status": "Get scan status",
            "/api/results": "Get scan results",
            "/api/scanall": "Start full scan"
        }
    })


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Minervini Stock Screener (Railway)",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    })


def to_python_type(val):
    """Convert numpy types to native Python types for JSON serialization"""
    import numpy as np
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    elif isinstance(val, np.bool_):
        return bool(val)
    return val


@app.route('/api/scan')
def scan():
    """Quick scan specific stocks"""
    symbols_param = request.args.get('symbols', 'RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK')
    symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()][:10]
    
    results = []
    passing = []
    
    for symbol in symbols:
        try:
            result = screener.check_trend_template(symbol)
            if result:
                stock_data = {
                    'symbol': str(result.symbol),
                    'price': float(round(to_python_type(result.current_price), 2)),
                    'score': int(to_python_type(result.score)),
                    'passes': bool(result.passes_all),
                    'sma_50': float(round(to_python_type(result.metrics.get('sma_50', 0)), 2)),
                    'sma_150': float(round(to_python_type(result.metrics.get('sma_150', 0)), 2)),
                    'sma_200': float(round(to_python_type(result.metrics.get('sma_200', 0)), 2)),
                    'pct_from_high': float(round(to_python_type(result.metrics.get('pct_from_high', 0)), 1)),
                    'pct_above_low': float(round(to_python_type(result.metrics.get('pct_above_low', 0)), 1))
                }
                results.append(stock_data)
                if result.passes_all:
                    passing.append(stock_data)
        except Exception as e:
            results.append({'symbol': symbol, 'error': str(e)})
    
    return jsonify({
        'success': True,
        'scanned': len(results),
        'passing': len(passing),
        'results': results
    })


@app.route('/api/status')
def status():
    """Get current scan status"""
    return jsonify(scan_state)


@app.route('/api/results')
def results():
    """Get last scan results"""
    return jsonify({
        'results': scan_state['results'],
        'count': len(scan_state['results']),
        'last_scan': scan_state['last_scan']
    })


@app.route('/api/scanall', methods=['POST', 'GET'])
def scanall():
    """Start a full scan of all stocks"""
    if scan_state['is_scanning']:
        return jsonify({
            'status': 'already_running',
            'progress': scan_state['progress'],
            'total': scan_state['total']
        })
    
    # Start scan in background thread
    thread = threading.Thread(target=run_full_scan)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'started',
        'message': 'Full scan started in background'
    })


def run_full_scan():
    """Run full scan in background"""
    global scan_state
    
    try:
        scan_state['is_scanning'] = True
        scan_state['status'] = 'scanning'
        scan_state['results'] = []
        
        # Get all stocks
        stocks = get_nse_stock_list()
        scan_state['total'] = len(stocks)
        scan_state['progress'] = 0
        
        results = []
        
        for i, symbol in enumerate(stocks):
            scan_state['progress'] = i + 1
            
            try:
                result = screener.check_trend_template(symbol)
                if result and result.passes_all:
                    results.append({
                        'symbol': result.symbol,
                        'price': round(result.current_price, 2),
                        'score': result.score
                    })
            except:
                pass
        
        scan_state['results'] = results
        scan_state['status'] = 'complete'
        scan_state['last_scan'] = datetime.now().isoformat()
        
    finally:
        scan_state['is_scanning'] = False


def run_telegram_bot():
    """Run Telegram bot in separate thread"""
    try:
        from bot import main as bot_main
        bot_main()
    except Exception as e:
        print(f"Telegram bot error: {e}")


if __name__ == '__main__':
    # Start Telegram bot in background thread
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Get port from environment (Railway sets this)
    port = int(os.environ.get('PORT', 8000))
    
    print(f"🚀 Starting Minervini API server on port {port}")
    print(f"📱 Telegram bot running in background")
    
    # Run Flask server
    app.run(host='0.0.0.0', port=port, debug=False)
