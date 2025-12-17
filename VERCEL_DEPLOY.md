# Minervini Stock Screener Bot - Vercel Deployment

## 🚀 Deploying to Vercel

This project has been configured for Vercel serverless deployment with webhook-based Telegram bot.

### Prerequisites

1. Vercel account
2. Vercel CLI installed: `npm i -g vercel`

### Setup Steps

#### 1. Add Environment Variables in Vercel

Go to your Vercel project settings and add:

```
TELEGRAM_BOT_TOKEN = your-bot-token
TELEGRAM_CHAT_IDS = chat-id-1,chat-id-2,chat-id-3
```

#### 2. Deploy to Vercel

```bash
# Login to Vercel
vercel login

# Deploy
vercel

# For production
vercel --prod
```

#### 3. Set Telegram Webhook

After deployment, visit this URL to set the webhook:

```
https://your-project.vercel.app/api/set_webhook?action=set
```

Or manually set it:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-project.vercel.app/api/webhook"}'
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/webhook` | POST | Telegram webhook receiver |
| `/api/health` | GET | Health check |
| `/api/scan?symbols=RELIANCE,TCS` | GET | Quick scan stocks |
| `/api/scan?symbols=RELIANCE&notify=true` | GET | Scan and notify via Telegram |
| `/api/set_webhook?action=info` | GET | Get current webhook info |
| `/api/set_webhook?action=set` | GET | Auto-set webhook |
| `/api/set_webhook?action=delete` | GET | Delete webhook |

### Bot Commands (via Telegram)

- `/start` - Welcome message
- `/help` - Help message
- `/check SYMBOL` - Check a stock (e.g., `/check RELIANCE`)
- `/scan` - Quick scan info
- `/nse` - NSE stock info
- Just send a symbol like `TCS` to check it

### Important Notes

⚠️ **Serverless Limitations:**
- Vercel functions have a 10-second timeout (free tier)
- Full stock scans (500+ stocks) cannot run on Vercel
- Use `/check SYMBOL` for individual stock checks
- For full scanning, run the local bot: `python bot.py`

### Local Development

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally
vercel dev
```

### Switching Between Local & Vercel

**For Vercel (webhook mode):**
```bash
vercel --prod
# Then set webhook via /api/set_webhook?action=set
```

**For Local (polling mode):**
```bash
# First delete webhook
curl "https://your-project.vercel.app/api/set_webhook?action=delete"

# Then run local bot
python bot.py
```

### File Structure

```
📁 Telegram/
├── 📁 api/                    # Vercel serverless functions
│   ├── webhook.py            # Main Telegram webhook handler
│   ├── health.py             # Health check endpoint
│   ├── scan.py               # Stock scan API
│   ├── set_webhook.py        # Webhook management
│   └── requirements.txt      # Python dependencies
├── vercel.json               # Vercel configuration
├── bot.py                    # Local polling bot (unchanged)
├── main.py                   # Local scheduler (unchanged)
└── ...
```
