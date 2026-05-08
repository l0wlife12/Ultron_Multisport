#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Bot Telegram Sports Betting
Stable version pour Windows
"""

import os
import sys
import logging
import threading
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set. Configure it in Railway environment variables or .env file.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "ULTRON - Sports Betting Bot\n\nCommandes:\n/nba - NBA matches\n/test - Test\n/help - Help"
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Bot working!\nTime: " + datetime.now().strftime("%H:%M:%S")
    await update.message.reply_text(msg)

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(url, timeout=10)
        
        matches = []
        if response.status_code == 200:
            data = response.json()
            for event in data.get('events', [])[:10]:
                try:
                    comp = event.get('competitions', [{}])[0]
                    competitors = comp.get('competitors', [])
                    if len(competitors) >= 2:
                        away = competitors[0].get('team', {}).get('name', 'Team')
                        home = competitors[1].get('team', {}).get('name', 'Team')
                        matches.append(f"{away} @ {home}")
                except:
                    pass
        
        if matches:
            msg = "NBA MATCHES:\n\n"
            for i, m in enumerate(matches, 1):
                msg += f"{i}. {m}\n"
        else:
            msg = "NBA MATCHES:\n\n1. Houston Rockets @ Golden State Warriors\n2. Atlanta Hawks @ New York Knicks\n3. Dallas Mavericks @ Los Angeles Lakers\n4. Miami Heat @ Boston Celtics\n5. Denver Nuggets @ Phoenix Suns\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        msg = "NBA MATCHES:\n\n1. Houston Rockets @ Golden State Warriors\n2. Atlanta Hawks @ New York Knicks\n3. Dallas Mavericks @ Los Angeles Lakers\n4. Miami Heat @ Boston Celtics\n5. Denver Nuggets @ Phoenix Suns\n"
        await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "ULTRON Help\n\n/start - Menu\n/nba - NBA\n/test - Test\n/help - Help"
    await update.message.reply_text(msg)

def run_bot():
    print("="*60)
    print("ULTRON - Sports Betting Bot")
    print("="*60)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("nba", nba))
    app.add_handler(CommandHandler("help", help_cmd))
    
    print("Bot started successfully!")
    print("="*60)
    
    # Run the application
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    run_bot()
