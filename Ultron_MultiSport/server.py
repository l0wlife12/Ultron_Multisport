#!/usr/bin/env python3
import http.server
import socketserver
import os
from pathlib import Path

# Configuration
PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        # Format personnalisé des logs
        print(f"[{self.log_date_time_string()}] {format % args}")
    
    def do_GET(self):
        # Redirection racine vers crypto_exchange.html
        if self.path == '/':
            self.path = '/crypto_exchange.html'
        return super().do_GET()

# Démarrer le serveur
if __name__ == '__main__':
    os.chdir(DIRECTORY)
    
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print("=" * 60)
        print("🚀 SERVEUR CRYPTO EXCHANGE DÉMARRÉ")
        print("=" * 60)
        print(f"📍 Adresse: http://localhost:{PORT}")
        print(f"📁 Répertoire: {DIRECTORY}")
        print("=" * 60)
        print("Appuyez sur Ctrl+C pour arrêter le serveur")
        print("=" * 60)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n⛔ Serveur arrêté.")
            httpd.server_close()
