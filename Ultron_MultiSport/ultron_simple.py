#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON SIMPLE - Bot de test basique
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# NBA Teams
NBA_TEAMS = {
    'LAL': {'name': '🟣 Lakers', 'power': 85},
    'GSW': {'name': '🔵 Warriors', 'power': 88},
    'BOS': {'name': '🟢 Celtics', 'power': 90},
    'DEN': {'name': '⛅ Nuggets', 'power': 87},
    'MIA': {'name': '🔴 Heat', 'power': 82},
    'NYK': {'name': '🟠 Knicks', 'power': 84},
    'PHX': {'name': '🟠 Suns', 'power': 86},
    'LAC': {'name': '🔴 Clippers', 'power': 83},
    'HOU': {'name': '🔴 Rockets', 'power': 79},
    'DAL': {'name': '💙 Mavericks', 'power': 86},
    'MEM': {'name': '🐯 Grizzlies', 'power': 84},
    'ATL': {'name': '🔴 Hawks', 'power': 81},
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande start"""
    await update.message.reply_text(
        "🤖 ULTRON est actif!\n\n"
        "Commandes:\n"
        "/nba - Matchs NBA\n"
        "/test - Test simple\n"
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test simple"""
    await update.message.reply_text(
        "✅ Bot fonctionne!\n\n"
        "Test: Voici un message simple\n"
        "Heure: " + datetime.now().strftime("%H:%M:%S")
    )

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche les matchs NBA"""
    try:
        # Récupérer les matchs via API
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.balldontlie.io/v1/games?dates[]={today}"
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            matches = []
            
            for game in data.get('data', []):
                if game['status'] not in ['Final', 'Final/OT']:
                    team1_code = game['home_team']['abbreviation'].upper()
                    team2_code = game['visitor_team']['abbreviation'].upper()
                    
                    if team1_code in NBA_TEAMS and team2_code in NBA_TEAMS:
                        matches.append(f"{NBA_TEAMS[team1_code]['name']} vs {NBA_TEAMS[team2_code]['name']}")
            
            if matches:
                msg = "🏀 MATCHS NBA D'AUJOURD'HUI:\n\n"
                for i, match in enumerate(matches, 1):
                    msg += f"{i}. {match}\n"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("Aucun match NBA trouvé aujourd'hui.")
        else:
            await update.message.reply_text("⚠️ Erreur API. Voici les matchs par défaut:\n\n"
                                          "1. 🟠 Knicks vs 🔴 Hawks\n"
                                          "2. 🟣 Lakers vs 💙 Mavericks\n"
                                          "3. 🟢 Celtics vs ⛅ Nuggets")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur: {str(e)}\n\nMatchs par défaut:\n"
                                      "1. 🟠 Knicks vs 🔴 Hawks\n"
                                      "2. 🟣 Lakers vs 💙 Mavericks")

def main() -> None:
    """Start the bot"""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ Token Telegram manquant!")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("nba", nba))
    
    print("="*60)
    print("ULTRON SIMPLE - Demarrage")
    print("="*60)
    print("Bot actif!")
    print("="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
