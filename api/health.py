"""
Health Check Endpoint for Vercel
"""
import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    """Health check handler"""
    
    def do_GET(self):
        """Return health status"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'service': 'Minervini Stock Screener Bot',
            'version': '2.0',
            'endpoints': [
                '/api/webhook - Telegram webhook',
                '/api/scan - Trigger scan',
                '/api/health - Health check'
            ]
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
