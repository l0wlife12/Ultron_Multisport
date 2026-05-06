#!/usr/bin/env python3
import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

print("🔧 Nettoyage du webhook Telegram...")
print("=" * 60)

# Supprimer le webhook
url_delete = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
response = requests.post(url_delete)
print(f"✅ Webhook supprimé: {response.status_code}")

time.sleep(1)

# Vérifier l'état
url_info = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
response = requests.get(url_info)
info = response.json()
if 'result' in info:
    print(f"✅ Info webhook: {info['result']}")
    print(f"   - URL: '{info['result'].get('url', '')}'")
    print(f"   - Pending updates: {info['result'].get('pending_update_count', 0)}")
else:
    print(f"⚠️  Impossible de récupérer les infos: {info}")

time.sleep(2)

# Lancer le bot
print("\n🤖 Démarrage du bot...")
print("=" * 60)
import subprocess
subprocess.Popen(['python', 'ultron_simple.py'])
print("✅ Bot démarré en arrière-plan")
