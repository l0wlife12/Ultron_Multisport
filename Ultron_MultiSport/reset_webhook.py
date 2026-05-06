#!/usr/bin/env python3
"""Reset Telegram webhook"""
import os
import requests
from dotenv import load_dotenv

load_dotenv('config.env')
token = os.getenv('TELEGRAM_TOKEN')

if token:
    # Delete webhook
    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    r = requests.get(url)
    print(f"✅ Webhook supprimé: {r.status_code}")
    
    # Get webhook info
    url2 = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    r2 = requests.get(url2)
    print(f"✅ Info webhook: {r2.json()}")
else:
    print("❌ Token manquant")
