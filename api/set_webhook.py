"""
Utility to set Telegram webhook
Run this once after deployment to register the webhook URL
"""
import json
import os
from http.server import BaseHTTPRequestHandler
import requests


BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')


def set_webhook(webhook_url: str) -> dict:
    """Set the Telegram webhook URL"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url},
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def get_webhook_info() -> dict:
    """Get current webhook info"""
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo",
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def delete_webhook() -> dict:
    """Delete the current webhook"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


class handler(BaseHTTPRequestHandler):
    """Webhook setup handler"""
    
    def do_GET(self):
        """Get current webhook info or set new webhook"""
        from urllib.parse import parse_qs, urlparse
        
        query = parse_qs(urlparse(self.path).query)
        action = query.get('action', ['info'])[0]
        
        if action == 'set':
            # Set webhook - derive from host
            host = self.headers.get('Host', '')
            webhook_url = f"https://{host}/api/webhook"
            result = set_webhook(webhook_url)
            result['webhook_url'] = webhook_url
        elif action == 'delete':
            result = delete_webhook()
        else:
            result = get_webhook_info()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())
    
    def do_POST(self):
        """Set webhook from POST body"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            webhook_url = body.get('url', '')
            
            if webhook_url:
                result = set_webhook(webhook_url)
            else:
                result = {'ok': False, 'error': 'Missing url parameter'}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
