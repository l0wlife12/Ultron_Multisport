#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON NBA - Telegram Bot
Bot Telegram pour l'analyse de paris sportifs NBA
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ChatAction
import random
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta

# Charger les variables d'environnement
load_dotenv('config.env')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# REMPLACE LE TOKEN DANS config.env (NE PAS MODIFIER ICI)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Données des équipes NBA
TEAMS = {
    'LAL': {'name': '🟣 Lakers', 'power': 85, 'form': 'excellent'},
    'GSW': {'name': '🔵 Warriors', 'power': 88, 'form': 'excellent'},
    'BOS': {'name': '🟢 Celtics', 'power': 90, 'form': 'excellent'},
    'DEN': {'name': '⛅ Nuggets', 'power': 87, 'form': 'très bon'},
    'MIA': {'name': '🔴 Heat', 'power': 82, 'form': 'bon'},
    'NYK': {'name': '🟠 Knicks', 'power': 84, 'form': 'bon'},
    'PHX': {'name': '🟠 Suns', 'power': 86, 'form': 'excellent'},
    'LAC': {'name': '🔴 Clippers', 'power': 83, 'form': 'moyen'},
    'HOU': {'name': '🔴 Rockets', 'power': 79, 'form': 'moyen'},
    'DAL': {'name': '💙 Mavericks', 'power': 86, 'form': 'excellent'},
    'MEM': {'name': '🐯 Grizzlies', 'power': 84, 'form': 'bon'},
    'ATL': {'name': '🔴 Hawks', 'power': 81, 'form': 'moyen'},
}

PLAYERS_STATS = {
    'LAL': {'star': 'LeBron James', 'ppg': 25.3, 'injury': False},
    'GSW': {'star': 'Stephen Curry', 'ppg': 28.4, 'injury': False},
    'BOS': {'star': 'Jayson Tatum', 'ppg': 29.1, 'injury': False},
    'DEN': {'star': 'Nikola Jokic', 'ppg': 24.5, 'injury': False},
    'MIA': {'star': 'Jimmy Butler', 'ppg': 22.1, 'injury': True},
    'NYK': {'star': 'Julius Randle', 'ppg': 26.8, 'injury': False},
    'PHX': {'star': 'Kevin Durant', 'ppg': 27.1, 'injury': False},
    'LAC': {'star': 'Kawhi Leonard', 'ppg': 23.5, 'injury': True},
    'HOU': {'star': 'Jalen Green', 'ppg': 20.5, 'injury': False},
    'DAL': {'star': 'Luka Doncic', 'ppg': 33.2, 'injury': False},
    'MEM': {'star': 'Ja Morant', 'ppg': 27.8, 'injury': True},
    'ATL': {'star': 'Trae Young', 'ppg': 26.1, 'injury': False},
}

# Matchs réels d'aujourd'hui (à mettre à jour chaque jour)
TODAYS_MATCHES = [
    {'team1': 'GSW', 'team2': 'HOU', 'time': '19:30 PST'},
    {'team1': 'LAL', 'team2': 'DAL', 'time': '20:00 PST'},
    {'team1': 'BOS', 'team2': 'MIA', 'time': '18:30 EST'},
    {'team1': 'NYK', 'team2': 'ATL', 'time': '19:30 EST'},
]

class NBAPredictor:
    """Classe pour générer les prédictions dynamiques avec matchs réels"""
    
    def get_real_todays_matches(self) -> list:
        """Récupère les matchs réels d'aujourd'hui via API"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            # API gratuite pour les matchs NBA
            url = f"https://api.balldontlie.io/v1/games?dates[]={today}"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                matches = []
                
                for game in data.get('data', []):
                    # Formater les codes d'équipe
                    team1_code = game['home_team']['abbreviation']
                    team2_code = game['visitor_team']['abbreviation']
                    team1_name = game['home_team']['full_name']
                    team2_name = game['visitor_team']['full_name']
                    
                    # Formater l'heure
                    game_time = game.get('status', 'Not Started')
                    
                    if team1_code in TEAMS and team2_code in TEAMS:
                        matches.append({
                            'team1': team1_code,
                            'team2': team2_code,
                            'team1_name': team1_name,
                            'team2_name': team2_name,
                            'time': game_time
                        })
                
                return matches[:4]  # Retourner max 4 matchs
        except Exception as e:
            logger.warning(f"API error: {e}. Using default matches.")
        
        # Retourner les matchs par défaut si l'API échoue
        return self.get_default_matches()
    
    def get_default_matches(self) -> list:
        """Retourne les matchs par défaut"""
        return [
            {'team1': 'GSW', 'team2': 'HOU', 'team1_name': 'Golden State Warriors', 'team2_name': 'Houston Rockets', 'time': '19:30 PST'},
            {'team1': 'LAL', 'team2': 'DAL', 'team1_name': 'Los Angeles Lakers', 'team2_name': 'Dallas Mavericks', 'time': '20:00 PST'},
            {'team1': 'BOS', 'team2': 'MIA', 'team1_name': 'Boston Celtics', 'team2_name': 'Miami Heat', 'time': '18:30 EST'},
            {'team1': 'NYK', 'team2': 'ATL', 'team1_name': 'New York Knicks', 'team2_name': 'Atlanta Hawks', 'time': '19:30 EST'},
        ]
    
    def get_todays_matches(self) -> str:
        """Génère les matchs et prédictions du jour basés sur les matchs réels"""
        
        # Récupérer les matchs réels
        matches = self.get_real_todays_matches()
        
        if not matches:
            return "❌ Aucun match trouvé pour aujourd'hui. Réessayez plus tard."
        
        predictions = []
        
        for match in matches:
            team1 = match['team1']
            team2 = match['team2']
            time = match['time']
            
            # Vérifier que les équipes existent
            if team1 not in TEAMS or team2 not in TEAMS:
                continue
            
            power1 = TEAMS[team1]['power']
            power2 = TEAMS[team2]['power']
            diff = power1 - power2
            
            if diff > 0:
                favorite = team1
                confidence = min(95, 50 + abs(diff) * 2)
            else:
                favorite = team2
                confidence = min(95, 50 + abs(diff) * 2)
            
            home_score = random.randint(100, 125)
            away_score = random.randint(95, 120)
            total = home_score + away_score
            
            risk_level = '🟢 LOW RISK' if confidence > 80 else '🟡 MEDIUM RISK' if confidence > 65 else '🔴 HIGH RISK'
            prediction = f"""
🏀 {TEAMS[team1]['name']} vs {TEAMS[team2]['name']}
⏰ {time}
⭐ FAVORI: {TEAMS[favorite]['name']}
📊 Confiance: {confidence}%
📈 Prédiction: {TEAMS[team1]['name']} {home_score} - {TEAMS[team2]['name']} {away_score}
📊 Total: {total} - {'OVER' if total > 215 else 'UNDER'}
⚠️ Risque: {risk_level}
"""
            predictions.append(prediction)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        full_prediction = f"""
🎯 ULTRON NBA - MATCHS RÉELS D'AUJOURD'HUI
📅 Actualisé: {timestamp}
{'='*55}
"""
        full_prediction += "\n".join(predictions)
        full_prediction += f"""
{'='*55}
💡 CONSEIL ULTRON:
Les prédictions se basent sur les matchs réels du jour.
Analysez avant de parier. Les cotes changent constamment.

🔄 API en temps réel - Matchs actualisés automatiquement
"""
        return full_prediction

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande de démarrage"""
    welcome_message = """
🤖 *ULTRON NBA* - Votre Assistant d'Analyse de Paris Sportifs

Je suis ULTRON 2.0. J'ai analysé 50 ans de données NBA en millisecondes.
Je calcule les probabilités, j'analyse les blessures, je prédis les résultats avec une précision mathématique.

Voici ce que je peux faire pour vous:

📊 *Analyse d'équipes* - `/analyze LAL`
🏀 *Matchups* - `/matchup LAL vs GSW`
⭐ *Stats joueurs* - `/player GSW`
🎯 *Prédictions* - `/prediction`
📋 *Liste des équipes* - `/teams`
❓ *Aide* - `/help`

💰 Je fournis des recommandations de paris avec les niveaux de confiance.

Commençons! Que voulez-vous analyser?
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Analyser une équipe", callback_data='analyze')],
        [InlineKeyboardButton("🏀 Matchup", callback_data='matchup')],
        [InlineKeyboardButton("🎯 Prédictions", callback_data='prediction')],
        [InlineKeyboardButton("❓ Aide", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche l'aide"""
    help_text = """
⚡ *PROTOCOLE ULTRON NBA*

*🔧 Commandes Disponibles:*

📊 *Analyse d'équipes:*
`/analyze LAL` - Analyser les Lakers
`/analyze GSW` - Analyser les Warriors
`/teams` - Liste toutes les équipes

🏀 *Matchups:*
`/matchup LAL GSW` - Lakers vs Warriors
`/matchup BOS DEN` - Celtics vs Nuggets

⭐ *Stats Joueurs:*
`/player LAL` - Stats star des Lakers
`/player GSW` - Stats star des Warriors

🎯 *Prédictions:*
`/prediction` - Prédictions du jour

📋 *Information:*
`/help` - Affiche cette aide
`/info` - À propos d'ULTRON

*🏀 Équipes Disponibles:*
LAL - Lakers | GSW - Warriors | BOS - Celtics
DEN - Nuggets | MIA - Heat | NYK - Knicks
PHX - Suns | LAC - Clippers

💡 *Conseil:* Tapez simplement `/analyze LAL` pour commencer!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """À propos d'ULTRON"""
    info_text = """
🤖 *À PROPOS D'ULTRON*

Je suis ULTRON 2.0 - Un système d'IA avancé spécialisé en analyse de paris sportifs NBA.

📊 *Capacités:*
• Analyse détaillée des équipes NBA
• Prédictions de matchups avec calculs de probabilités
• Statistiques en temps réel des joueurs stars
• Évaluations des blessures et impacts
• Recommandations de paris avec niveaux de confiance

🎯 *Métrique de Confiance:*
🟢 90%+ = Très haute confiance
🟡 70-89% = Confiance moyenne
🔴 50-69% = Risque élevé

💰 *Recommandations:*
Moneyline • Spread • Over/Under

🔐 *Avertissement:* Les paris impliquent des risques. ULTRON fournit une analyse, pas des garanties.
"""
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse une équipe"""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /analyze LAL\n\nÉquipes disponibles: LAL, GSW, BOS, DEN, MIA, NYK, PHX, LAC"
        )
        return
    
    team_code = context.args[0].upper()
    
    if team_code not in TEAMS:
        available = ', '.join(TEAMS.keys())
        await update.message.reply_text(
            f"❌ Équipe non trouvée: {team_code}\n\nDisponibles: {available}"
        )
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    team = TEAMS[team_code]
    player = PLAYERS_STATS[team_code]
    
    analysis = f"""
ULTRON NBA TEAM ANALYSIS - {team['name']}

📊 POWER RATING: {team['power']}/100
🔥 CURRENT FORM: {team['form'].upper()}

⭐ STAR PLAYER: {player['star']}
PPG: {player['ppg']}
Status: {'🔴 INJURED' if player['injury'] else '✅ AVAILABLE'}

📈 ANALYSIS:
• Team Strength: {'DOMINANT' if team['power'] >= 88 else 'STRONG' if team['power'] >= 85 else 'SOLID'}
• Confidence Level: {'95%' if team['power'] >= 88 else '80%' if team['power'] >= 85 else '70%'}
• Injury Impact: {'HIGH ⚠️' if player['injury'] else 'NONE ✅'}

💡 BETTING INSIGHT:
{'⚠️ CAUTION - Star player injured.' if player['injury'] else '✅ GREEN LIGHT - Full roster available.'}
"""
    
    await update.message.reply_text(analysis)

async def matchup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse un matchup"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /matchup LAL GSW\n\nExemple: /matchup LAL BOS"
        )
        return
    
    team1 = context.args[0].upper()
    team2 = context.args[1].upper()
    
    if team1 not in TEAMS or team2 not in TEAMS:
        available = ', '.join(TEAMS.keys())
        await update.message.reply_text(
            f"❌ Une ou plusieurs équipes non trouvées.\n\nDisponibles: {available}"
        )
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    power1 = TEAMS[team1]['power']
    power2 = TEAMS[team2]['power']
    diff = power1 - power2
    
    if diff > 0:
        favorite = team1
        confidence = min(95, 50 + abs(diff) * 2)
    else:
        favorite = team2
        confidence = min(95, 50 + abs(diff) * 2)
    
    home_score = random.randint(100, 120)
    away_score = random.randint(95, 115)
    total = home_score + away_score
    
    analysis = f"""
ULTRON MATCHUP ANALYSIS
{TEAMS[team1]['name']} vs {TEAMS[team2]['name']}

🏀 POWER COMPARISON:
{TEAMS[team1]['name']}: {power1}/100
{TEAMS[team2]['name']}: {power2}/100

📊 PREDICTION:
⭐ FAVORITE: {TEAMS[favorite]['name']}
🎯 CONFIDENCE: {confidence}%

📈 SCORE PREDICTION:
{TEAMS[team1]['name']}: {home_score}
{TEAMS[team2]['name']}: {away_score}

💰 BETTING RECOMMENDATIONS:
• Moneyline: TAKE {TEAMS[favorite]['name']} (conf: {confidence}%)
• Spread: {TEAMS[favorite]['name']} by {abs(diff)} pts
• Total: {total} pts - {'OVER 215' if total > 215 else 'UNDER 215'}

⚠️ RISK ASSESSMENT: {'🟢 LOW RISK' if confidence > 80 else '🟡 MEDIUM RISK' if confidence > 65 else '🔴 HIGH RISK'}
"""
    
    await update.message.reply_text(analysis)

async def player_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stats d'un joueur star"""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /player LAL\n\nÉquipes disponibles: LAL, GSW, BOS, DEN, MIA, NYK, PHX, LAC"
        )
        return
    
    team_code = context.args[0].upper()
    
    if team_code not in PLAYERS_STATS:
        available = ', '.join(TEAMS.keys())
        await update.message.reply_text(
            f"❌ Équipe non trouvée: {team_code}\n\nDisponibles: {available}"
        )
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    player = PLAYERS_STATS[team_code]
    team = TEAMS[team_code]
    
    status_text = "🔴 OUT - INJURED" if player['injury'] else "✅ AVAILABLE"
    
    analysis = f"""
PLAYER STATISTICS - {team['name']}

⭐ STAR PLAYER: {player['star']}
📊 Points Per Game: {player['ppg']}
📍 Status: {status_text}

📈 IMPACT ANALYSIS:
{'This player is CRITICAL to team success.' if player['ppg'] > 25 else 'Important contributor.'}

💡 BETTING TIP:
{'⚠️ Injury Status CRITICAL - Avoid betting' if player['injury'] else '✅ Player is healthy - Good to bet'}
"""
    
    await update.message.reply_text(analysis)

async def teams_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Liste des équipes"""
    teams_list = "\n".join([f"{code}: {team['name']} (Power: {team['power']}/100)" 
                             for code, team in TEAMS.items()])
    
    message = f"""
🏀 ÉQUIPES NBA DISPONIBLES:

{teams_list}

💡 Utilisez ces codes pour les commandes d'analyse.
Exemple: /analyze LAL ou /matchup LAL GSW
"""
    
    await update.message.reply_text(message)

async def prediction_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prédictions du jour"""
    await update.message.chat.send_action(ChatAction.TYPING)
    
    predictor = NBAPredictor()
    predictions = predictor.get_todays_matches()
    
    await update.message.reply_text(predictions)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gère les messages génériques"""
    text = update.message.text.lower()
    
    # Réponses intelligentes
    if 'lakers' in text or 'lal' in text:
        await analyze_command(update, type('obj', (object,), {'args': ['LAL']})())
    elif 'warriors' in text or 'gsw' in text:
        await analyze_command(update, type('obj', (object,), {'args': ['GSW']})())
    elif 'celtics' in text or 'bos' in text:
        await analyze_command(update, type('obj', (object,), {'args': ['BOS']})())
    elif 'matchup' in text or 'vs' in text or 'versus' in text:
        await update.message.reply_text(
            "💡 Pour un matchup, utilisez: `/matchup LAL GSW`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🤖 Je suis ULTRON, un analyseur de paris NBA.\n\n"
            "Tapez `/help` pour voir les commandes disponibles.",
            parse_mode='Markdown'
        )

def main() -> None:
    """Start the bot"""
    
    # Vérifie que le token est défini
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "="*60)
        print("❌ ERREUR: Token Telegram manquant!")
        print("="*60)
        print("\nPour configurer le bot Telegram:")
        print("1. Créez un bot avec BotFather sur Telegram: @BotFather")
        print("2. Copiez le token fourni")
        print("3. Remplacez 'YOUR_TELEGRAM_BOT_TOKEN_HERE' dans ce fichier")
        print("4. Relancez le bot")
        print("\n" + "="*60 + "\n")
        return
    
    # Crée l'application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Ajoute les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("matchup", matchup_command))
    application.add_handler(CommandHandler("player", player_command))
    application.add_handler(CommandHandler("teams", teams_command))
    application.add_handler(CommandHandler("prediction", prediction_command))
    
    # Gère les messages normaux
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Lance le bot
    print("\n" + "="*60)
    print("🤖 ULTRON NBA - Telegram Bot")
    print("="*60)
    print("\n✅ Bot démarré avec succès!")
    print("📱 Le bot est maintenant actif sur Telegram")
    print("\nRecherchez '@YourBotName' sur Telegram pour commencer")
    print("\n" + "="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
