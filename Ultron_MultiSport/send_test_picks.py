#!/usr/bin/env python3
"""
Test script to send a sample enriched picks message to VIP channel
Tests the display format for NBA Spread, NHL Puckline, and MLB Runline enrichments
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
if os.path.exists('config.env'):
    load_dotenv('config.env')

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_VIP = os.environ.get("TELEGRAM_CHAT_ID_VIP", "")

def send_test_picks():
    """Send sample enriched picks to VIP channel"""
    
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_VIP:
        print("❌ Missing Telegram credentials")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    heure_qc = datetime.now().strftime("%H:%M")
    
    # Test message with all 3 sports enriched
    msg = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎  U L T R O N  V I P  (TEST)
     3 PICK(S)  •  {heure_qc}  •  🔬 Enriched Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🥇  🏀 Celtics @ Heat  🟢
🕐  20:00  |  💼 DraftKings
🟢 ML: Celtics -200
🟢 SPREAD: Celtics -3.5 @ -110 | 74/100 (ATS 8/10 | Net +5.2)
🟢 Total Points O/U: Under 210.5 @ -110

🥈  🏒 Hurricanes @ Rangers  🟢
🕐  22:00  |  💼 BetMGM
🟢 ML: Hurricanes -110
🟢 PUCK LINE: Hurricanes -1.5 @ -110 | 72/100 (ATS 7/10 | 🥅 Anderson 0.918)
🟢 Total Goals O/U: Under 5.5 @ -110

🏅  ⚾ Dodgers @ Padres  🟢
🕐  21:10  |  💼 FanDuel
🟢 ML: Dodgers -140
🟢 RUNLINE: Dodgers -1.5 @ -115 | 70/100 (ATS 6/10 | ERA 3.24)
🟡 Total Runs O/U: Over 7.5 @ +100

═══════════════════════════════════════════
📊  ENRICHMENT DETAILS
═══════════════════════════════════════════

🏀 NBA SPREAD (Celtics):
   • ATS 8/10 (80%) on last 10 games
   • Net Rating: +5.2 (excellent defense)
   • No back-to-back ✅

🏒 NHL PUCK LINE (Hurricanes):
   • ATS 7/10 (70%) covering ±1.5
   • Goalie: Anderson SV% 0.918 (elite)
   • GAA: 2.61 (very good)
   • No road trip penalty ✅

⚾ MLB RUNLINE (Dodgers):
   • ATS 6/10 (60%) against -1.5
   • Pitcher: Clayton Kershaw ERA 3.24
   • Sharp money: YES (aligned with pick)
   • No key injuries ✅

═══════════════════════════════════════════
✨ Modifications Appliquées:
   ✅ Affichage enrichis pour les 3 sports
   ✅ Format ATS records L10
   ✅ Stats avancées (Net rating, Goalie SV%, ERA)
   ✅ Détection back-to-back NBA
   ✅ Détection road trip NHL
   ✅ Confiance enrichie 68-74/100
""".strip()
    
    payload = {
        "chat_id": TELEGRAM_CHAT_VIP,
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"✅ Test message sent to VIP channel!")
            print(f"\n📱 Preview:\n{msg}")
        else:
            print(f"❌ Telegram error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_test_picks()
