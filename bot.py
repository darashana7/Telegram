"""
Interactive Telegram Bot for Minervini Stock Screener
Users can send commands to get stock data
"""
import logging
import json
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

sys.path.append(os.path.dirname(__file__))
from src.minervini_screener import MinerviniScreener
from src.stock_list import get_nse_stock_list
from src.all_nse_stocks import get_all_nse_stocks, get_nse_stock_count

# Bot Token
BOT_TOKEN = "8550797252:AAG_P9X-9RxOQyIz-N2LAHiGJhnBKzAF5W8"

# Scan results storage
SCAN_RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'scan_results.json')


def save_scan_results(scan_type: str, results: list, total_scanned: int):
    """Save scan results to JSON file with metadata"""
    from datetime import datetime
    
    # Load existing data
    data = {}
    if os.path.exists(SCAN_RESULTS_FILE):
        try:
            with open(SCAN_RESULTS_FILE, 'r') as f:
                data = json.load(f)
        except:
            data = {}
    
    # Convert results to serializable format
    results_data = []
    for r in results:
        results_data.append({
            'symbol': r.symbol,
            'name': r.name if hasattr(r, 'name') else '',
            'current_price': float(r.current_price),
            'score': r.score,
            'passes_all': r.passes_all,
            'criteria': r.criteria,
            'metrics': {k: float(v) if isinstance(v, (int, float)) else v for k, v in r.metrics.items()}
        })
    
    # Update data for this scan type
    data[scan_type] = {
        'timestamp': datetime.now().isoformat(),
        'total_scanned': total_scanned,
        'qualifying_count': len(results),
        'results': results_data
    }
    
    # Save to file
    os.makedirs(os.path.dirname(SCAN_RESULTS_FILE), exist_ok=True)
    with open(SCAN_RESULTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    return True


def load_scan_results(scan_type: str = None):
    """Load cached scan results. If scan_type is None, return all data."""
    if not os.path.exists(SCAN_RESULTS_FILE):
        return None
    
    try:
        with open(SCAN_RESULTS_FILE, 'r') as f:
            data = json.load(f)
        
        if scan_type:
            return data.get(scan_type)
        return data
    except Exception as e:
        logging.error(f"Error loading scan results: {e}")
        return None


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize screener
screener = MinerviniScreener()

# Store for results
last_scan_results = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome = """
🎯 <b>Minervini Stock Screener Bot</b>

Welcome! I can help you find stocks that meet Mark Minervini's Trend Template criteria.

<b>Scan Commands:</b>
📊 /scan - Quick scan (top 50 stocks)
📈 /fullscan - Nifty 500 scan (~500 stocks)
🌐 /scanall - ALL NSE stocks (~2000 stocks)

<b>View Results:</b>
📋 /list - Show cached scan summary
📋 /listscanall - View ALL NSE scan results
📋 /listfullscan - View Nifty 500 results

<b>Other:</b>
🔍 /check SYMBOL - Check a specific stock
🏛️ /nse - Show all available stocks
ℹ️ /help - Show this help message

<b>Minervini's 9 Criteria:</b>
✅ Price > 50, 150, 200 SMA
✅ 50 SMA > 150 SMA > 200 SMA
✅ 200 SMA trending up
✅ ≥30% above 52-week low
✅ Within 25% of 52-week high

Type a command to get started!
    """
    await update.message.reply_text(welcome.strip(), parse_mode='HTML')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    await start(update, context)


async def nse_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total NSE stocks available"""
    all_stocks = get_all_nse_stocks()
    nifty500 = get_nse_stock_list()
    
    header = f"""📊 <b>NSE Stocks Available</b>

<b>Total stocks in database: {len(all_stocks)}</b>

<b>Categories:</b>
• Nifty 50: 50 stocks
• Nifty Next 50: 50 stocks  
• Nifty Midcap 150: ~150 stocks
• Nifty Smallcap 250: ~250 stocks
• Other NSE stocks: ~{len(all_stocks) - 500}+ stocks

<b>Scan Options:</b>
• /scan - Quick scan (top 50)
• /fullscan - Nifty 500 scan ({len(nifty500)} stocks)
• /scanall - ALL NSE stocks ({len(all_stocks)} stocks)

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    await update.message.reply_text(header, parse_mode='HTML')
    
    # Show first 100 stocks
    message = "<b>First 100 stocks:</b>\n"
    for i, symbol in enumerate(all_stocks[:100], 1):
        message += f"{i}. {symbol}\n"
        if i % 50 == 0:
            await update.message.reply_text(message, parse_mode='HTML')
            message = ""
    
    await update.message.reply_text(f"... and {len(all_stocks) - 100} more stocks!\n\nUse /scanall to scan all {len(all_stocks)} stocks!")


async def scan_all_nse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scan ALL NSE stocks (~2000)"""
    global last_scan_results
    
    all_stocks = get_all_nse_stocks()
    await update.message.reply_text(
        f"🔍 <b>Scanning ALL {len(all_stocks)} NSE stocks...</b>\n\n"
        f"⚠️ This will take 30-45 minutes!\n"
        f"Please wait patiently. I'll send results when done.",
        parse_mode='HTML'
    )
    
    try:
        results = screener.scan_stocks(all_stocks, min_score=9)
        last_scan_results = results
        
        # Save results to file
        save_scan_results('scanall', results, len(all_stocks))
        
        if not results:
            await update.message.reply_text("📊 No stocks currently meet all 9 criteria.")
            return
        
        # Header
        header = f"🎯 <b>Full NSE Scan Complete!</b>\n\n"
        header += f"📊 Scanned: {len(all_stocks)} stocks\n"
        header += f"✅ Found: {len(results)} qualifying stocks\n"
        header += f"💾 Results saved! Use /list to view anytime.\n"
        header += "━━━━━━━━━━━━━━━━━━━━━━━━"
        await update.message.reply_text(header, parse_mode='HTML')
        
        # Send all results in batches
        batch_size = 25
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]
            msg = ""
            for j, r in enumerate(batch, i+1):
                name = r.name[:20] if hasattr(r, 'name') else ''
                msg += f"{j}. <b>{r.symbol}</b> | {name} | ₹{r.current_price:,.2f}\n"
            await update.message.reply_text(msg, parse_mode='HTML')
        
        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Total: {len(results)} stocks pass 9/9 criteria</b>",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Scan all error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def check_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check a specific stock"""
    if not context.args:
        await update.message.reply_text("❌ Please provide a stock symbol.\nExample: /check RELIANCE")
        return
    
    symbol = context.args[0].upper()
    await update.message.reply_text(f"🔍 Checking {symbol}...")
    
    try:
        result = screener.check_trend_template(symbol)
        
        if not result:
            # Try to get basic info even if full analysis fails
            import yfinance as yf
            try:
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="1y")
                info = ticker.info
                
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    high_52w = hist['High'].max()
                    low_52w = hist['Low'].min()
                    days_data = len(hist)
                    
                    message = f"""📊 <b>{symbol}</b>
                    
<b>⚠️ Limited Data (New Stock)</b>
Only {days_data} days of data available.
Minervini analysis needs 200+ days.

💰 <b>Current Price:</b> ₹{current_price:,.2f}

📈 <b>52-Week Range:</b>
• High: ₹{high_52w:,.2f}
• Low: ₹{low_52w:,.2f}

Company: {info.get('shortName', symbol)}
Sector: {info.get('sector', 'N/A')}

<i>Wait for more trading history for full analysis.</i>"""
                    await update.message.reply_text(message, parse_mode='HTML')
                    return
            except:
                pass
            
            await update.message.reply_text(f"❌ Could not fetch data for {symbol}. Please check the symbol.")
            return
        
        # Format result
        status = "✅ PASSES" if result.passes_all else "❌ FAILS"
        
        message = f"""
📊 <b>{symbol}</b> - {result.name}

<b>Score: {result.score}/9 {status}</b>

💰 Price: ₹{result.current_price:,.2f}

📊 <b>Moving Averages:</b>
• 50-day SMA: ₹{result.metrics['sma_50']:,.2f}
• 150-day SMA: ₹{result.metrics['sma_150']:,.2f}
• 200-day SMA: ₹{result.metrics['sma_200']:,.2f}

📈 <b>52-Week Range:</b>
• High: ₹{result.metrics['week_52_high']:,.2f} ({result.metrics['pct_from_52w_high']:.1f}% away)
• Low: ₹{result.metrics['week_52_low']:,.2f} ({result.metrics['pct_above_52w_low']:.1f}% above)

<b>Criteria:</b>
"""
        criteria_labels = {
            "1_price_above_150sma": "Price > 150 SMA",
            "2_price_above_200sma": "Price > 200 SMA",
            "3_150sma_above_200sma": "150 SMA > 200 SMA",
            "4_200sma_trending_up": "200 SMA Uptrend",
            "5_50sma_above_150sma": "50 SMA > 150 SMA",
            "6_50sma_above_200sma": "50 SMA > 200 SMA",
            "7_price_above_50sma": "Price > 50 SMA",
            "8_price_30pct_above_52w_low": "≥30% above Low",
            "9_price_within_25pct_of_52w_high": "Within 25% of High"
        }
        
        for key, passed in result.criteria.items():
            icon = "✅" if passed else "❌"
            label = criteria_labels.get(key, key)
            message += f"{icon} {label}\n"
        
        await update.message.reply_text(message.strip(), parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error checking {symbol}: {e}")
        await update.message.reply_text(f"❌ Error checking {symbol}: {str(e)}")


async def quick_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run quick scan on top 50 stocks"""
    global last_scan_results
    
    await update.message.reply_text("🔍 Running quick scan on top 50 stocks...\nThis may take 2-3 minutes.")
    
    try:
        # Top 50 stocks
        stocks = get_nse_stock_list()[:50]
        results = screener.scan_stocks(stocks, min_score=9)
        last_scan_results = results
        
        if not results:
            await update.message.reply_text("📊 No stocks currently meet all 9 criteria.")
            return
        
        # Format results
        message = f"🎯 <b>Quick Scan Results</b>\n\n"
        message += f"📊 Found {len(results)} qualifying stocks:\n\n"
        
        for i, r in enumerate(results[:20], 1):
            message += f"{i}. <b>{r.symbol}</b> | ₹{r.current_price:,.2f}\n"
        
        if len(results) > 20:
            message += f"\n...and {len(results) - 20} more. Use /list to see all."
        
        message += "\n\n✅ All pass 9/9 Minervini criteria"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Scan error: {e}")
        await update.message.reply_text(f"❌ Scan error: {str(e)}")


async def full_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run full Nifty 500 scan"""
    global last_scan_results
    
    await update.message.reply_text("🔍 Running FULL Nifty 500 scan...\nThis will take 10-15 minutes. Please wait.")
    
    try:
        stocks = get_nse_stock_list()
        results = screener.scan_stocks(stocks, min_score=9)
        last_scan_results = results
        
        # Save results to file
        save_scan_results('fullscan', results, len(stocks))
        
        if not results:
            await update.message.reply_text("📊 No stocks currently meet all 9 criteria.")
            return
        
        # Send in batches
        message = f"🎯 <b>Full Scan Complete!</b>\n\n"
        message += f"📊 Scanned: {len(stocks)} stocks\n"
        message += f"✅ Found: {len(results)} qualifying stocks\n"
        message += f"💾 Results saved! Use /list to view anytime.\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        # Send list in batches
        batch_size = 20
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]
            batch_msg = ""
            for j, r in enumerate(batch, i+1):
                batch_msg += f"{j}. <b>{r.symbol}</b> | {r.name[:20]} | ₹{r.current_price:,.2f}\n"
            await update.message.reply_text(batch_msg, parse_mode='HTML')
        
        await update.message.reply_text("✅ Scan complete! All stocks pass 9/9 criteria.", parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Full scan error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def list_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show ALL eligible stocks from last scan"""
    global last_scan_results
    from datetime import datetime
    
    # First check if results are in memory
    if last_scan_results:
        # Show from memory
        header = f"📋 <b>Current Session Results</b>\n"
        header += f"📊 Total: {len(last_scan_results)} stocks\n"
        header += "━━━━━━━━━━━━━━━━━━━━━━━━"
        await update.message.reply_text(header, parse_mode='HTML')
        
        # Send ALL stocks in batches
        batch_size = 25
        for batch_num in range(0, len(last_scan_results), batch_size):
            batch = last_scan_results[batch_num:batch_num + batch_size]
            message = ""
            
            for i, r in enumerate(batch, batch_num + 1):
                name = r.name[:22] if hasattr(r, 'name') else ''
                message += f"{i}. <b>{r.symbol}</b> | {name} | ₹{r.current_price:,.2f}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        
        footer = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        footer += f"✅ <b>Total: {len(last_scan_results)} stocks</b>\n"
        footer += "All pass Minervini 9/9 criteria"
        await update.message.reply_text(footer, parse_mode='HTML')
        return
    
    # Try to load from saved scan results
    all_data = load_scan_results()
    
    if not all_data:
        await update.message.reply_text(
            "📋 <b>No cached scan results found.</b>\n\n"
            "Run one of these commands first:\n"
            "• /fullscan - Scan Nifty 500\n"
            "• /scanall - Scan ALL NSE stocks",
            parse_mode='HTML'
        )
        return
    
    # Show summary of available scans
    summary = "📋 <b>Cached Scan Results</b>\n"
    summary += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for scan_type in ['scanall', 'fullscan']:
        if scan_type in all_data:
            scan_data = all_data[scan_type]
            timestamp = datetime.fromisoformat(scan_data['timestamp'])
            time_str = timestamp.strftime("%d-%b-%Y %H:%M")
            
            scan_name = "All NSE Stocks" if scan_type == 'scanall' else "Nifty 500"
            summary += f"📊 <b>{scan_name}</b>\n"
            summary += f"   🕐 Scanned: {time_str}\n"
            summary += f"   📈 Stocks scanned: {scan_data['total_scanned']}\n"
            summary += f"   ✅ Qualifying: {scan_data['qualifying_count']}\n\n"
    
    summary += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    summary += "Use /listscanall or /listfullscan to view details"
    await update.message.reply_text(summary, parse_mode='HTML')


async def list_scanall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cached scanall results"""
    await _show_cached_results(update, 'scanall', 'All NSE Stocks')


async def list_fullscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cached fullscan results"""
    await _show_cached_results(update, 'fullscan', 'Nifty 500')


async def _show_cached_results(update: Update, scan_type: str, scan_name: str):
    """Helper to show cached results for a specific scan type"""
    from datetime import datetime
    
    scan_data = load_scan_results(scan_type)
    
    if not scan_data:
        await update.message.reply_text(
            f"📋 No cached {scan_name} results found.\n\n"
            f"Run /{scan_type} first!",
            parse_mode='HTML'
        )
        return
    
    # Format timestamp
    timestamp = datetime.fromisoformat(scan_data['timestamp'])
    time_str = timestamp.strftime("%d-%b-%Y %H:%M")
    
    results = scan_data['results']
    
    # Header
    header = f"📋 <b>{scan_name} Results</b>\n"
    header += f"🕐 Scanned: {time_str}\n"
    header += f"📊 Total scanned: {scan_data['total_scanned']}\n"
    header += f"✅ Qualifying: {len(results)} stocks\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(header, parse_mode='HTML')
    
    # Send ALL stocks in batches
    batch_size = 25
    for batch_num in range(0, len(results), batch_size):
        batch = results[batch_num:batch_num + batch_size]
        message = ""
        
        for i, r in enumerate(batch, batch_num + 1):
            name = r.get('name', '')[:22]
            price = r.get('current_price', 0)
            message += f"{i}. <b>{r['symbol']}</b> | {name} | ₹{price:,.2f}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    footer = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    footer += f"✅ <b>Total: {len(results)} stocks</b>\n"
    footer += "All pass Minervini 9/9 criteria"
    await update.message.reply_text(footer, parse_mode='HTML')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    text = update.message.text.upper()
    
    # Check if it's a stock symbol
    if text.isalpha() and len(text) <= 20:
        context.args = [text]
        await check_stock(update, context)
    else:
        await update.message.reply_text(
            "💡 Send a stock symbol to check it, or use:\n"
            "/scan - Quick scan\n"
            "/check SYMBOL - Check stock\n"
            "/help - All commands"
        )


def main():
    """Start the bot"""
    print("🚀 Starting Minervini Bot...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("nse", nse_stocks))
    app.add_handler(CommandHandler("check", check_stock))
    app.add_handler(CommandHandler("scan", quick_scan))
    app.add_handler(CommandHandler("fullscan", full_scan))
    app.add_handler(CommandHandler("scanall", scan_all_nse))
    app.add_handler(CommandHandler("list", list_results))
    app.add_handler(CommandHandler("listscanall", list_scanall))
    app.add_handler(CommandHandler("listfullscan", list_fullscan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is running! Send commands to @Minervini_1_bot")
    print("Press Ctrl+C to stop.")
    
    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
