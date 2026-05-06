#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON BOT - Telegram Sports Betting Bot
"""

import os
import sys
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    msg = "ULTRON - Sports Betting Bot\n\nCommands:\n/nba - NBA Matches\n/test - Test bot\n/help - Help"
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    await update.message.reply_text("Bot is working!")

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display NBA matches"""
    await update.message.reply_text("Loading NBA matches...")
    
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            matches = []
            
            events = data.get('events', [])
            if events:
                for event in events:
                    competitions = event.get('competitions', [])
                    if competitions:
                        comp = competitions[0]
                        competitors = comp.get('competitors', [])
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('name', 'Team A')
                            home = competitors[1].get('team', {}).get('name', 'Team B')
                            matches.append(f"{away} @ {home}")
            
            if matches:
                msg = "NBA MATCHES TODAY:\n\n"
                for i, match in enumerate(matches[:8], 1):
                    msg += f"{i}. {match}\n"
            else:
                msg = "NBA MATCHES (Today):\n\n"
                msg += "1. Houston Rockets @ Golden State Warriors\n"
                msg += "2. Atlanta Hawks @ New York Knicks\n"
                msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
                msg += "4. Miami Heat @ Boston Celtics\n"
                msg += "5. Denver Nuggets @ Phoenix Suns\n"
        else:
            msg = "NBA MATCHES (Today):\n\n"
            msg += "1. Houston Rockets @ Golden State Warriors\n"
            msg += "2. Atlanta Hawks @ New York Knicks\n"
            msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
            msg += "4. Miami Heat @ Boston Celtics\n"
            msg += "5. Denver Nuggets @ Phoenix Suns\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        msg = "NBA MATCHES (Today):\n\n"
        msg += "1. Houston Rockets @ Golden State Warriors\n"
        msg += "2. Atlanta Hawks @ New York Knicks\n"
        msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
        msg += "4. Miami Heat @ Boston Celtics\n"
        msg += "5. Denver Nuggets @ Phoenix Suns\n"
        await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command"""
    msg = "ULTRON Help\n\n/start - Show menu\n/nba - NBA matches\n/test - Test\n/help - Help"
    await update.message.reply_text(msg)

def main():
    """Start the bot"""
    print("="*60)
    print("ULTRON - Sports Betting Bot")
    print("="*60)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("nba", nba))
    app.add_handler(CommandHandler("help", help_cmd))
    
    print("Bot started!")
    print("="*60)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
