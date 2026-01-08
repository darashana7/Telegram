# Railway Deployment Guide

## 🚀 Deploy to Railway

This project supports **hybrid deployment**:
- **Vercel** → Frontend dashboard (static files)
- **Railway** → Backend API + Telegram bot (long-running processes)

---

## Option 1: Railway Only (Full Stack)

Deploy everything to Railway - simpler setup.

### Steps:

1. **Create Railway Account** at [railway.app](https://railway.app)

2. **Connect GitHub Repository**
   - Go to Railway Dashboard
   - Click "New Project" → "Deploy from GitHub repo"
   - Select this repository

3. **Add Environment Variables**
   ```
   TELEGRAM_BOT_TOKEN = your-bot-token
   TELEGRAM_CHAT_IDS = chat-id-1,chat-id-2
   PORT = 8000
   ```

4. **Deploy**
   - Railway will auto-detect `Procfile` and deploy
   - Wait for build to complete

5. **Access Your App**
   ```
   https://your-app.railway.app/
   ```

---

## Option 2: Vercel + Railway (Hybrid)

Best performance: Vercel for frontend, Railway for backend.

### Step 1: Deploy Backend to Railway

1. Create Railway project as above
2. Add environment variables
3. Get your Railway URL: `https://your-app.railway.app`

### Step 2: Deploy Frontend to Vercel

1. Deploy to Vercel: `vercel --prod`

2. **Update frontend to use Railway backend:**
   
   Edit `public/app.js` line 9:
   ```javascript
   const RAILWAY_URL = 'https://your-app.railway.app';
   ```

3. Redeploy: `vercel --prod`

---

## API Endpoints (Railway)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/api/health` | GET | Health check |
| `/api/scan?symbols=TCS,INFY` | GET | Scan specific stocks |
| `/api/status` | GET | Get scan progress |
| `/api/results` | GET | Get last scan results |
| `/api/scanall` | POST | Start full scan |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Yes |
| `TELEGRAM_CHAT_IDS` | Comma-separated chat IDs | Yes |
| `PORT` | Server port (Railway sets this) | No |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Browser                          │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────▼─────────────┐
        │      Vercel (Frontend)     │
        │   - Static HTML/CSS/JS     │
        │   - Fast CDN delivery      │
        └─────────────┬─────────────┘
                      │ API Calls
        ┌─────────────▼─────────────┐
        │     Railway (Backend)      │
        │   - Flask API Server       │
        │   - Stock Screening        │
        │   - Telegram Bot           │
        │   - Background Scans       │
        └───────────────────────────┘
```

---

## Troubleshooting

### 502 Bad Gateway
- Check Railway logs: `railway logs`
- Ensure `PORT` environment variable is used
- Verify dependencies are installed

### CORS Errors
- Backend has CORS enabled for all origins
- Check browser console for specific errors

### Telegram Bot Not Responding
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check Railway logs for bot errors
- Try `/start` command to test

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run Railway server locally
python railway_server.py

# Server runs at http://localhost:8000
```
