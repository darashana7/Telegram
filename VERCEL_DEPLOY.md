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
REDIS_URL = redis://... (from Vercel KV or Upstash)
```

**Note:** For reliable scanning, create a Vercel KV (Redis) database and link it to your project. This is required for `scanall`.

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

### Full Scan Configuration (Cron Job)

To enable **Scan All**, you must set up a Cron Job to keep the scanner running in the background.

1. Create a `vercel.json` with cron config (already included).
2. Or use an external cron service (like cron-job.org) to ping this URL every minute (for Free tier) or 10 minutes:
   `https://your-project.vercel.app/api/cron-scan`

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/webhook` | POST | Telegram webhook receiver |
| `/api/health` | GET | Health check |
| `/api/cron-scan` | GET | Background scanner (loops through stocks) |
| `/api/scan?symbols=RELIANCE` | GET | Quick scan stocks |
| `/api/set_webhook?action=set` | GET | Auto-set webhook |

### Bot Commands (via Telegram)

- `/start` - Welcome message
- `/check SYMBOL` - Check a stock (e.g., `/check RELIANCE`)
- `/scanall` - **Start full background scan (~40 mins)**
- `/list` - View results of last scan
- `/scan` - Quick scan info
- `/nse` - NSE stock info

### Important Notes

⚠️ **Vercel Limitations & Solutions:**
- **Timeouts:** Vercel functions timeout after 10s (Free) or 60s (Pro).
- **Solution:** The bot now splits the 2000+ stock scan into small batches locally. You MUST keep the `/api/cron-scan` endpoint active via Vercel Cron or external ping.
- **Persistence:** Scan progress is saved in Redis. Ensure `REDIS_URL` is set.

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
├── 📁 public/                 # Frontend Dashboard (NEW!)
│   ├── index.html            # Main dashboard page
│   ├── styles.css            # Premium dark theme styling
│   └── app.js                # Interactive JavaScript
├── vercel.json               # Vercel configuration
├── bot.py                    # Local polling bot (unchanged)
├── main.py                   # Local scheduler (unchanged)
└── ...
```

---

## 🎨 Frontend Dashboard

The project now includes a stunning **frontend dashboard** with:

### Features
- **Live Health Monitoring** - Real-time API status indicator
- **Quick Stock Scanner** - Scan up to 10 stocks instantly
- **Preset Stock Lists** - One-click presets for Nifty 50, Bank Nifty, IT, Pharma, Auto
- **Beautiful Stock Cards** - Visual pass/fail indicators with metrics
- **API Testing Panel** - Test endpoints directly from the dashboard
- **Responsive Design** - Works on desktop, tablet, and mobile

### Design
- 🌙 **Dark Mode** - Premium dark theme with purple/violet accents
- ✨ **Glassmorphism** - Modern glass-card effects
- 🎭 **Micro-Animations** - Smooth transitions and hover effects
- 📱 **Mobile-First** - Fully responsive layout

### Access
After deployment, visit your Vercel URL to see the dashboard:
```
https://your-project.vercel.app/
```

