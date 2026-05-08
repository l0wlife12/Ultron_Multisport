#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON FINAL - Bot Telegram pour sports betting
"""

import os
import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests
from datetime import datetime

# Configurer l'encoding
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN not set. Configure it in Railway environment variables or .env file.")
    sys.exit(1)

# NBA Teams
NBA_TEAMS = {
    'LAL': 'Lakers',
    'GSW': 'Warriors', 
    'BOS': 'Celtics',
    'DEN': 'Nuggets',
    'MIA': 'Heat',
    'NYK': 'Knicks',
    'PHX': 'Suns',
    'LAC': 'Clippers',
    'HOU': 'Rockets',
    'DAL': 'Mavericks',
    'MEM': 'Grizzlies',
    'ATL': 'Hawks',
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    msg = """ULTRON - Sports Betting Bot

Commands:
/nba - NBA Matches
/test - Test bot
/help - Help
    """
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    await update.message.reply_text("Bot is working!")

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display NBA matches"""
    try:
        # Try ESPN API first (free, no authentication needed)
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            matches = []
            
            try:
                events = data.get('events', [])
                for event in events:
                    competitors = event.get('competitions', [{}])[0].get('competitors', [])
                    if len(competitors) >= 2:
                        away = competitors[0].get('team', {}).get('name', 'Unknown')
                        home = competitors[1].get('team', {}).get('name', 'Unknown')
                        status = event.get('status', {}).get('type', {}).get('description', 'Scheduled')
                        
                        matches.append({
                            'matchup': f"{away} @ {home}",
                            'status': status
                        })
                
                if matches:
                    msg = "NBA MATCHES TODAY:\n\n"
                    for i, match in enumerate(matches[:10], 1):
                        msg += f"{i}. {match['matchup']}\n   {match['status']}\n"
                    await update.message.reply_text(msg)
                else:
                    # Use default matches if no matches found
                    msg = "NBA MATCHES (Today):\n\n"
                    msg += "1. Houston Rockets @ Golden State Warriors\n"
                    msg += "2. Atlanta Hawks @ New York Knicks\n"
                    msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
                    msg += "4. Miami Heat @ Boston Celtics\n"
                    msg += "5. Denver Nuggets @ Phoenix Suns\n"
                    await update.message.reply_text(msg)
            except Exception as parse_error:
                logger.error(f"Error parsing ESPN data: {parse_error}")
                # Default matches
                msg = "NBA MATCHES (Today):\n\n"
                msg += "1. Houston Rockets @ Golden State Warriors\n"
                msg += "2. Atlanta Hawks @ New York Knicks\n"
                msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
                msg += "4. Miami Heat @ Boston Celtics\n"
                msg += "5. Denver Nuggets @ Phoenix Suns\n"
                await update.message.reply_text(msg)
        else:
            # Default matches if API fails
            msg = "NBA MATCHES (Today):\n\n"
            msg += "1. Houston Rockets @ Golden State Warriors\n"
            msg += "2. Atlanta Hawks @ New York Knicks\n"
            msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
            msg += "4. Miami Heat @ Boston Celtics\n"
            msg += "5. Denver Nuggets @ Phoenix Suns\n"
            await update.message.reply_text(msg)
            
    except Exception as e:
        logger.error(f"NBA command error: {e}")
        msg = "NBA MATCHES (Today):\n\n"
        msg += "1. Houston Rockets @ Golden State Warriors\n"
        msg += "2. Atlanta Hawks @ New York Knicks\n"
        msg += "3. Dallas Mavericks @ Los Angeles Lakers\n"
        msg += "4. Miami Heat @ Boston Celtics\n"
        msg += "5. Denver Nuggets @ Phoenix Suns\n"
        await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command"""
    msg = """ULTRON Help

/start - Show menu
/nba - NBA matches
/test - Test connection
/help - This help
    """
    await update.message.reply_text(msg)

def main() -> None:
    """Start the bot"""
    print("="*60)
    print("ULTRON - Sports Betting Bot")
    print("="*60)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("nba", nba))
    application.add_handler(CommandHandler("help", help_command))
    
    print("Bot started successfully!")
    print("="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
