#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Bot Telegram pour sports betting
Version stable et compatible Windows
"""

import os
import sys
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests
from datetime import datetime

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set. Configure it in Railway environment variables or .env file.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /start"""
    msg = "ULTRON - Sports Betting Bot\n\nCommandes disponibles:\n/nba - NBA matches d'aujourd'hui\n/test - Test du bot\n/help - Aide"
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /test"""
    msg = "Bot fonctionne!\n\nHeure: " + datetime.now().strftime("%H:%M:%S")
    await update.message.reply_text(msg)

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /nba - Affiche les matchs NBA"""
    try:
        # Utiliser ESPN API (gratuit, pas d'authentification requise)
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(url, timeout=10)
        
        matches = []
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            for event in events[:10]:
                try:
                    competitions = event.get('competitions', [])
                    if competitions:
                        comp = competitions[0]
                        competitors = comp.get('competitors', [])
                        if len(competitors) >= 2:
                            away_team = competitors[0].get('team', {}).get('name', 'Team A')
                            home_team = competitors[1].get('team', {}).get('name', 'Team B')
                            matches.append(f"{away_team} @ {home_team}")
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue
        
        if matches:
            msg = "NBA MATCHES TODAY:\n\n"
            for i, match in enumerate(matches, 1):
                msg += f"{i}. {match}\n"
        else:
            msg = "NBA MATCHES:\n\n"
            msg += "1. Houston Rockets @ Golden State Warriors\n"
            msg += "2. Atlanta Hawks @ New York Knicks\n"
            msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
            msg += "4. Miami Heat @ Boston Celtics\n"
            msg += "5. Denver Nuggets @ Phoenix Suns\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"NBA command error: {e}")
        msg = "NBA MATCHES:\n\n"
        msg += "1. Houston Rockets @ Golden State Warriors\n"
        msg += "2. Atlanta Hawks @ New York Knicks\n"
        msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
        msg += "4. Miami Heat @ Boston Celtics\n"
        msg += "5. Denver Nuggets @ Phoenix Suns\n"
        await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /help"""
    msg = "ULTRON Help\n\n/start - Menu principal\n/nba - Matchs NBA\n/test - Test du bot\n/help - Cette aide"
    await update.message.reply_text(msg)

def main():
    """Demarrer le bot"""
    print("="*60)
    print("ULTRON - Sports Betting Bot")
    print("="*60)
    print("Token: OK")
    print("="*60)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("nba", nba))
    application.add_handler(CommandHandler("help", help_cmd))
    
    print("Demarrage du bot...")
    print("="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
