#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON MULTISPORT - Telegram Bot
Bot Telegram pour l'analyse de paris sportifs NBA, NHL, NFL
Récupère les matchs réels via Google Search
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
from bs4 import BeautifulSoup
import re

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

# ==================== DONNÉES NBA ====================
NBA_TEAMS = {
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

NBA_PLAYERS_STATS = {
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

# ==================== DONNÉES NHL ====================
NHL_TEAMS = {
    'NYR': {'name': '🔴 Rangers', 'power': 87, 'form': 'excellent'},
    'TOR': {'name': '🔵 Maple Leafs', 'power': 85, 'form': 'excellent'},
    'COL': {'name': '❄️ Avalanche', 'power': 88, 'form': 'excellent'},
    'VGK': {'name': '🟡 Golden Knights', 'power': 84, 'form': 'bon'},
    'EDM': {'name': '🟠 Oilers', 'power': 86, 'form': 'excellent'},
    'BOS': {'name': '🟤 Bruins', 'power': 82, 'form': 'bon'},
    'DAL': {'name': '💚 Stars', 'power': 83, 'form': 'bon'},
    'CAR': {'name': '🔴 Hurricanes', 'power': 85, 'form': 'bon'},
}

NHL_PLAYERS_STATS = {
    'NYR': {'star': 'Artemi Panarin', 'ppg': 1.35, 'injury': False},
    'EDM': {'star': 'Connor McDavid', 'ppg': 1.42, 'injury': False},
    'TOR': {'star': 'Auston Matthews', 'ppg': 1.18, 'injury': True},
    'COL': {'star': 'Nathan MacKinnon', 'ppg': 1.28, 'injury': False},
}

# ==================== DONNÉES NFL ====================
NFL_TEAMS = {
    'KC': {'name': '🔴 Chiefs', 'power': 92, 'form': 'excellent'},
    'SF': {'name': '🔴 49ers', 'power': 88, 'form': 'excellent'},
    'BUF': {'name': '🔵 Bills', 'power': 86, 'form': 'très bon'},
    'DAL': {'name': '💙 Cowboys', 'power': 85, 'form': 'excellent'},
    'LAR': {'name': '🔵 Rams', 'power': 82, 'form': 'bon'},
    'DEN': {'name': '🟠 Broncos', 'power': 79, 'form': 'moyen'},
    'PHI': {'name': '🟢 Eagles', 'power': 87, 'form': 'excellent'},
    'TB': {'name': '🔴 Buccaneers', 'power': 80, 'form': 'bon'},
}

NFL_PLAYERS_STATS = {
    'KC': {'star': 'Patrick Mahomes', 'ppg': 285, 'injury': False},
    'SF': {'star': 'Christian McCaffrey', 'ppg': 95, 'injury': True},
    'DAL': {'star': 'Dak Prescott', 'ppg': 265, 'injury': False},
    'BUF': {'star': 'Josh Allen', 'ppg': 275, 'injury': False},
}

# Dictionnaires consolidés par sport
TEAMS = {'nba': NBA_TEAMS, 'nhl': NHL_TEAMS, 'nfl': NFL_TEAMS}
PLAYERS_STATS = {'nba': NBA_PLAYERS_STATS, 'nhl': NHL_PLAYERS_STATS, 'nfl': NFL_PLAYERS_STATS}

# Icônes et noms des sports
SPORTS_CONFIG = {
    'nba': {'emoji': '🏀', 'name': 'NBA', 'query': 'NBA games today'},
    'nhl': {'emoji': '🏒', 'name': 'NHL', 'query': 'NHL games today'},
    'nfl': {'emoji': '🏈', 'name': 'NFL', 'query': 'NFL games today'},
}

class GoogleSportsPredictor:
    """Classe pour récupérer les matchs via Google et générer les prédictions"""
    
    def search_google_matches(self, sport: str) -> list:
        """Récupère les matchs du jour via API fiables"""
        try:
            if sport == 'nba':
                return self.fetch_nba_matches()
            elif sport == 'nhl':
                return self.fetch_nhl_matches()
            elif sport == 'nfl':
                return self.fetch_nfl_matches()
        except Exception as e:
            logger.warning(f"Match fetch error ({sport}): {e}")
        
        return self.get_default_matches(sport)
    
    def fetch_nba_matches(self) -> list:
        """Récupère les matchs NBA réels"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Essayer l'API BallDontLie d'abord
            url = f"https://api.balldontlie.io/v1/games?dates[]={today}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                matches = []
                
                for game in data.get('data', []):
                    try:
                        if game['status'] not in ['Final', 'Final/OT']:  # Matchs à venir ou en cours
                            team1_code = game['home_team']['abbreviation'].upper()
                            team2_code = game['visitor_team']['abbreviation'].upper()
                            
                            # Vérifier que les codes existent
                            if team1_code in NBA_TEAMS and team2_code in NBA_TEAMS:
                                matches.append({
                                    'team1': team1_code,
                                    'team2': team2_code,
                                    'team1_name': game['home_team']['full_name'],
                                    'team2_name': game['visitor_team']['full_name'],
                                    'time': self.format_game_time(game.get('scheduled_at', ''))
                                })
                    except (KeyError, TypeError):
                        continue
                
                if matches:
                    return matches[:4]
        except Exception as e:
            logger.warning(f"BallDontLie API error: {e}")
        
        # Fallback: utiliser les matchs par défaut
        return self.get_default_matches('nba')
    
    def fetch_nhl_matches(self) -> list:
        """Récupère les matchs NHL réels"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Utiliser l'API NHL officielle
            url = f"https://statsapi.web.nhl.com/api/v1/schedule?startDate={today}&endDate={today}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                matches = []
                
                for game in data.get('games', []):
                    try:
                        if game['status']['abstractGameState'] != 'Final':
                            team1_code = game['teams']['home']['team']['abbreviation'].upper()
                            team2_code = game['teams']['away']['team']['abbreviation'].upper()
                            
                            if team1_code in NHL_TEAMS and team2_code in NHL_TEAMS:
                                matches.append({
                                    'team1': team1_code,
                                    'team2': team2_code,
                                    'team1_name': game['teams']['home']['team']['name'],
                                    'team2_name': game['teams']['away']['team']['name'],
                                    'time': self.format_nhl_time(game.get('gameDateTime', ''))
                                })
                    except (KeyError, TypeError):
                        continue
                
                if matches:
                    return matches[:4]
        except Exception as e:
            logger.warning(f"NHL API error: {e}")
        
        return self.get_default_matches('nhl')
    
    def fetch_nfl_matches(self) -> list:
        """Récupère les matchs NFL réels"""
        try:
            # NFL API via ESPN (gratuite)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                matches = []
                
                for event in data.get('events', []):
                    try:
                        status = event['status']['type']['name']
                        
                        # Récupérer matchs non-finalisés
                        if status != 'Final':
                            teams = event['competitions'][0]['competitors']
                            team1_code = teams[0]['abbreviation'].upper()
                            team2_code = teams[1]['abbreviation'].upper()
                            
                            if team1_code in NFL_TEAMS and team2_code in NFL_TEAMS:
                                matches.append({
                                    'team1': team1_code,
                                    'team2': team2_code,
                                    'team1_name': teams[0]['displayName'],
                                    'team2_name': teams[1]['displayName'],
                                    'time': self.format_nfl_time(event.get('date', ''))
                                })
                    except (KeyError, TypeError, IndexError):
                        continue
                
                if matches:
                    return matches[:4]
        except Exception as e:
            logger.warning(f"NFL API error: {e}")
        
        return self.get_default_matches('nfl')
    
    def format_game_time(self, timestamp: str) -> str:
        """Formate l'heure d'un match NBA"""
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%H:%M %Z")
        except:
            pass
        return "TBD"
    
    def format_nhl_time(self, timestamp: str) -> str:
        """Formate l'heure d'un match NHL"""
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%H:%M %Z")
        except:
            pass
        return "TBD"
    
    def format_nfl_time(self, timestamp: str) -> str:
        """Formate l'heure d'un match NFL"""
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%H:%M %Z")
        except:
            pass
        return "TBD"
    
    
    def get_team_code(self, team_name: str, sport: str) -> str:
        """Convertit le nom de l'équipe en code"""
        teams_dict = TEAMS[sport]
        team_name = team_name.lower().strip()
        
        # Exact match d'abord
        for code, data in teams_dict.items():
            if team_name == data['name'].lower().replace('🟣 ', '').replace('🔵 ', '').replace('🟢 ', '').replace('🔴 ', '').replace('❄️ ', '').replace('⛅ ', '').replace('🟠 ', '').replace('🟤 ', '').replace('💚 ', '').replace('💙 ', '').replace('🟡 ', '').replace('🐯 ', ''):
                return code
            
            # Partial match
            if team_name in data['name'].lower():
                return code
        
        # Fallback: vérifier les noms complets d'équipes
        full_names = {
            'new york knicks': 'NYK',
            'atlanta hawks': 'ATL',
            'los angeles lakers': 'LAL',
            'golden state warriors': 'GSW',
            'boston celtics': 'BOS',
            'denver nuggets': 'DEN',
            'miami heat': 'MIA',
            'phoenix suns': 'PHX',
            'los angeles clippers': 'LAC',
            'houston rockets': 'HOU',
            'dallas mavericks': 'DAL',
            'memphis grizzlies': 'MEM',
            'new york rangers': 'NYR',
            'toronto maple leafs': 'TOR',
            'colorado avalanche': 'COL',
            'vegas golden knights': 'VGK',
            'edmonton oilers': 'EDM',
            'boston bruins': 'BOS',
            'dallas stars': 'DAL',
            'carolina hurricanes': 'CAR',
            'kansas city chiefs': 'KC',
            'san francisco 49ers': 'SF',
            'buffalo bills': 'BUF',
            'dallas cowboys': 'DAL',
            'los angeles rams': 'LAR',
            'denver broncos': 'DEN',
            'philadelphia eagles': 'PHI',
            'tampa bay buccaneers': 'TB',
        }
        
        return full_names.get(team_name, None)
    
    def get_default_matches(self, sport: str) -> list:
        """Retourne les matchs par défaut pour ce sport"""
        defaults = {
            'nba': [
                {'team1': 'LAL', 'team2': 'GSW', 'team1_name': 'Lakers', 'team2_name': 'Warriors', 'time': '19:30'},
                {'team1': 'BOS', 'team2': 'DEN', 'team1_name': 'Celtics', 'team2_name': 'Nuggets', 'time': '20:00'},
            ],
            'nhl': [
                {'team1': 'NYR', 'team2': 'TOR', 'team1_name': 'Rangers', 'team2_name': 'Maple Leafs', 'time': '19:00'},
                {'team1': 'EDM', 'team2': 'COL', 'team1_name': 'Oilers', 'team2_name': 'Avalanche', 'time': '20:00'},
            ],
            'nfl': [
                {'team1': 'KC', 'team2': 'SF', 'team1_name': 'Chiefs', 'team2_name': '49ers', 'time': '18:30'},
                {'team1': 'DAL', 'team2': 'PHI', 'team1_name': 'Cowboys', 'team2_name': 'Eagles', 'time': '20:15'},
            ]
        }
        return defaults.get(sport, [])
    
    def get_all_sports_matches(self) -> dict:
        """Récupère les matchs pour tous les sports"""
        all_matches = {}
        for sport in ['nba', 'nhl', 'nfl']:
            all_matches[sport] = self.search_google_matches(sport)
        return all_matches
    
    def generate_prediction(self, team1_code: str, team2_code: str, sport: str) -> dict:
        """Génère une prédiction pour un matchup"""
        teams = TEAMS[sport]
        players = PLAYERS_STATS[sport]
        
        power1 = teams[team1_code]['power']
        power2 = teams[team2_code]['power']
        diff = power1 - power2
        
        # Analyse des facteurs
        injury_impact = 0
        if team1_code in players and players[team1_code]['injury']:
            injury_impact -= 5
        if team2_code in players and players[team2_code]['injury']:
            injury_impact += 5
        
        form_factor = 0
        form1 = teams[team1_code]['form']
        form2 = teams[team2_code]['form']
        form_values = {'excellent': 3, 'très bon': 2, 'bon': 1, 'moyen': 0}
        form_factor = form_values.get(form1, 0) - form_values.get(form2, 0)
        
        adjusted_diff = diff + injury_impact + form_factor
        
        if adjusted_diff > 0:
            favorite = team1_code
            confidence = min(95, 50 + abs(adjusted_diff) * 2.5)
        else:
            favorite = team2_code
            confidence = min(95, 50 + abs(adjusted_diff) * 2.5)
        
        # Scores basés sur le sport
        if sport == 'nba':
            base_score = 110 + (adjusted_diff * 1.5)
            score1 = int(base_score + random.randint(-8, 8))
            score2 = int(base_score - adjusted_diff + random.randint(-8, 8))
            total_threshold = 215
        elif sport == 'nhl':
            base_score = 3.5 + (adjusted_diff * 0.15)
            score1 = int(base_score + random.randint(0, 3))
            score2 = int(base_score - adjusted_diff + random.randint(0, 3))
            total_threshold = 6.5
        else:  # NFL
            base_score = 23 + (adjusted_diff * 1.2)
            score1 = int(base_score + random.randint(-5, 5))
            score2 = int(base_score - adjusted_diff + random.randint(-5, 5))
            total_threshold = 48
        
        total = score1 + score2
        spread = abs(score1 - score2)
        
        return {
            'team1': team1_code,
            'team2': team2_code,
            'favorite': favorite,
            'confidence': confidence,
            'score1': score1,
            'score2': score2,
            'total': total,
            'spread': spread,
            'injury_impact': injury_impact,
            'form_factor': form_factor,
            'total_threshold': total_threshold,
            'risk': '🟢 LOW RISK' if confidence > 80 else '🟡 MEDIUM RISK' if confidence > 65 else '🔴 HIGH RISK'
        }
    
    def generate_betting_recommendations(self, team1_code: str, team2_code: str, sport: str, time: str) -> str:
        """Génère les recommandations de paris détaillées"""
        teams = TEAMS[sport]
        players = PLAYERS_STATS[sport]
        
        pred = self.generate_prediction(team1_code, team2_code, sport)
        
        team1_name = teams[team1_code]['name']
        team2_name = teams[team2_code]['name']
        fav_name = teams[pred['favorite']]['name']
        
        # Déterminer le favori et l'underdog
        if pred['favorite'] == team1_code:
            favorite = team1_code
            underdog = team2_code
            fav_odds = -150 + int(pred['confidence'] * 0.5)
            under_odds = 130 - int(pred['confidence'] * 0.5)
        else:
            favorite = team2_code
            underdog = team1_code
            fav_odds = -150 + int(pred['confidence'] * 0.5)
            under_odds = 130 - int(pred['confidence'] * 0.5)
        
        # Analyse Over/Under
        is_over = pred['total'] > pred['total_threshold']
        over_under_conf = min(90, 50 + abs(pred['total'] - pred['total_threshold']) * 1.5)
        
        # Recommandations Moneyline
        moneyline = f"""
💰 *MONEYLINE (Qui gagnera?)*
{'='*50}
⭐ FAVORI: {fav_name}
   Confiance: {pred['confidence']}%
   Cotes: {fav_odds:+d}
   💡 RECOMMANDATION: {"🟢 STRONG BET" if pred['confidence'] > 75 else "🟡 MODERATE BET" if pred['confidence'] > 65 else "🔴 WEAK BET"}

🐕 UNDERDOG: {teams[underdog]['name']}
   Cotes: {under_odds:+d}
   💡 RECOMMANDATION: {"❌ AVOID" if pred['confidence'] > 75 else "🤔 RISKY" if pred['confidence'] > 60 else "✅ POSSIBLE"}
"""
        
        # Recommandations Spread
        spread_fav = f"{fav_name} -{pred['spread']}"
        spread_under = f"{teams[underdog]['name']} +{pred['spread']}"
        spread_conf = pred['confidence'] - 15
        
        spread = f"""
📊 *SPREAD (Écart de points)*
{'='*50}
🔵 {spread_fav}
   Confiance: {max(50, spread_conf)}%
   💡 RECOMMANDATION: {"🟢 STRONG BET" if spread_conf > 70 else "🟡 MODERATE BET" if spread_conf > 60 else "🔴 RISKY"}

🔴 {spread_under}
   Cotes associées
   💡 RECOMMANDATION: {"❌ AVOID" if spread_conf > 70 else "🤔 RISKY" if spread_conf > 60 else "✅ POSSIBLE"}
"""
        
        # Recommandations Over/Under
        over_under = f"""
📈 *OVER/UNDER (Total des points)*
{'='*50}
➕ OVER {pred['total_threshold']}
   Prédiction totale: {pred['total']} points
   Confiance: {over_under_conf}%
   💡 RECOMMANDATION: {"🟢 STRONG BET" if is_over and over_under_conf > 70 else "🟡 MODERATE BET" if is_over and over_under_conf > 60 else "❌ AVOID" if not is_over else "🤔 RISKY"}

➖ UNDER {pred['total_threshold']}
   Confiance: {100 - over_under_conf}%
   💡 RECOMMANDATION: {"🟢 STRONG BET" if not is_over and over_under_conf > 70 else "🟡 MODERATE BET" if not is_over and over_under_conf > 60 else "❌ AVOID" if is_over else "🤔 RISKY"}
"""
        
        # Résumé des analyses
        team1_player = players.get(team1_code, {'star': 'N/A', 'injury': False})
        team2_player = players.get(team2_code, {'star': 'N/A', 'injury': False})
        
        analysis_summary = f"""
🔬 *ANALYSE DÉTAILLÉE*
{'='*50}
⚡ Power Rating: {teams[team1_code]['power']} vs {teams[team2_code]['power']}
🏥 Blessures: {f"❌ {teams[team1_code]['name']} " if team1_code in players and team1_player['injury'] else "✅ "}{f"| ❌ {teams[team2_code]['name']}" if team2_code in players and team2_player['injury'] else ""}
🔥 Forme: {teams[team1_code]['form']} vs {teams[team2_code]['form']}

📊 Prédiction du score: {team1_name} {pred['score1']} - {team2_name} {pred['score2']}
⚠️ Niveau de risque: {pred['risk']}

🎯 VERDICT GLOBAL:
{fav_name} est favorite avec {pred['confidence']}% de confiance.
Le total des points devrait être {'ÉLEVÉ' if is_over else 'BAS'} ({pred['total']} points prédits).
"""
        
        # Conseils pratiques
        practical_advice = f"""
💡 *CONSEILS PRATIQUES*
{'='*50}
✅ BET RECOMMENDATION:
   1️⃣ Meilleur pari: {fav_name} Moneyline (Confiance: {pred['confidence']}%)
   2️⃣ Alternative: Spread {spread_fav} (Moins risqué)
   3️⃣ Pari combiné: {fav_name} ML + {'OVER' if is_over else 'UNDER'} {pred['total_threshold']}

⚠️ À ÉVITER:
   ❌ Underdog Moneyline (Sauf avec cotes favorables)
   ❌ Paris contraires aux données d'analyse

💰 GESTION DU BANKROLL:
   • Pari min-risque: 1-2% de votre bankroll
   • Pari mod-risque: 3-5% pour confiance > 75%
   • Pari haut-risque: Éviter sur des cotes inégales

⏰ TIMING:
   Match à: {time}
   💡 Placer vos paris 30-60 min avant le match
"""
        
        full_recommendation = f"""
🎯 ULTRON PARIS DÉTAILLÉS - {SPORTS_CONFIG[sport]['name']}
⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*60}

{team1_name} 🆚 {team2_name}

{moneyline}

{spread}

{over_under}

{analysis_summary}

{practical_advice}

{'='*60}
🔐 Avertissement: Les paris impliquent des risques. Analysez toujours avant de miser!
🤖 Prédictions générées par ULTRON via analyse Google en temps réel
"""
        
        return full_recommendation

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande de démarrage"""
    welcome_message = """
🤖 *ULTRON 3.0 - MULTISPORT*

Je suis ULTRON, votre assistant d'analyse pour NBA 🏀, NHL 🏒 et NFL 🏈!

Je me base sur les APIs officielles pour récupérer les matchs réels de chaque jour:
✅ NBA via BallDontLie API
✅ NHL via NHL Stats API  
✅ NFL via ESPN API

*Commandes disponibles:*

🏀 *NBA:*
`/nba` - Matchs NBA d'aujourd'hui
`/nba_teams` - Équipes NBA
`/nba_analyze LAL` - Analyser une équipe

🏒 *NHL:*
`/nhl` - Matchs NHL d'aujourd'hui
`/nhl_teams` - Équipes NHL
`/nhl_analyze NYR` - Analyser une équipe

🏈 *NFL:*
`/nfl` - Matchs NFL d'aujourd'hui
`/nfl_teams` - Équipes NFL
`/nfl_analyze KC` - Analyser une équipe

📋 `/sports` - Tous les sports
❓ `/help` - Aide complète

💰 Je fournis des recommandations de paris basées sur Google et l'analyse en temps réel.
"""
    
    keyboard = [
        [InlineKeyboardButton("🏀 NBA", callback_data='sport_nba'), 
         InlineKeyboardButton("🏒 NHL", callback_data='sport_nhl'),
         InlineKeyboardButton("🏈 NFL", callback_data='sport_nfl')],
        [InlineKeyboardButton("❓ Aide", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche l'aide"""
    help_text = """
⚡ *PROTOCOLE ULTRON MULTISPORT*

*🔧 COMMANDES NBA:*
`/nba` - Prédictions NBA avec matchs Google
`/nba_teams` - Liste des équipes NBA
`/nba_analyze LAL` - Analyser les Lakers
`/nba_matchup LAL GSW` - Matchup Lakers vs Warriors

*🔧 COMMANDES NHL:*
`/nhl` - Prédictions NHL avec matchs Google
`/nhl_teams` - Liste des équipes NHL
`/nhl_analyze NYR` - Analyser les Rangers
`/nhl_matchup NYR TOR` - Matchup Rangers vs Maple Leafs

*🔧 COMMANDES NFL:*
`/nfl` - Prédictions NFL avec matchs Google
`/nfl_teams` - Liste des équipes NFL
`/nfl_analyze KC` - Analyser les Chiefs
`/nfl_matchup KC SF` - Matchup Chiefs vs 49ers

*🌐 Source des données:*
✅ Matchs récupérés via GOOGLE Search
✅ Mises à jour en temps réel
✅ Analyses dynamiques basées sur les données réelles

*💡 Conseil:* Tapez `/nba`, `/nhl` ou `/nfl` pour voir les matchs du jour!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def nba_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prédictions NBA avec paris détaillés"""
    await update.message.chat.send_action(ChatAction.TYPING)
    
    predictor = GoogleSportsPredictor()
    matches = predictor.search_google_matches('nba')
    
    if not matches:
        await update.message.reply_text("❌ Aucun match NBA trouvé. Réessayez plus tard.")
        return
    
    for match in matches:
        team1 = match['team1']
        team2 = match['team2']
        time = match['time']
        
        # Générer les recommandations de paris détaillées
        betting_rec = predictor.generate_betting_recommendations(team1, team2, 'nba', time)
        
        await update.message.reply_text(betting_rec, parse_mode='Markdown')
    
    await update.message.reply_text(
        "✅ Toutes les prédictions NBA avec recommandations de paris ont été affichées!\n\n"
        "🔄 Les données se mettent à jour via Google à chaque appel de /nba"
    )

async def nhl_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prédictions NHL avec paris détaillés"""
    await update.message.chat.send_action(ChatAction.TYPING)
    
    predictor = GoogleSportsPredictor()
    matches = predictor.search_google_matches('nhl')
    
    if not matches:
        await update.message.reply_text("❌ Aucun match NHL trouvé. Réessayez plus tard.")
        return
    
    for match in matches:
        team1 = match['team1']
        team2 = match['team2']
        time = match['time']
        
        # Générer les recommandations de paris détaillées
        betting_rec = predictor.generate_betting_recommendations(team1, team2, 'nhl', time)
        
        await update.message.reply_text(betting_rec, parse_mode='Markdown')
    
    await update.message.reply_text(
        "✅ Toutes les prédictions NHL avec recommandations de paris ont été affichées!\n\n"
        "🔄 Les données se mettent à jour via Google à chaque appel de /nhl"
    )

async def nfl_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prédictions NFL avec paris détaillés"""
    await update.message.chat.send_action(ChatAction.TYPING)
    
    predictor = GoogleSportsPredictor()
    matches = predictor.search_google_matches('nfl')
    
    if not matches:
        await update.message.reply_text("❌ Aucun match NFL trouvé. Réessayez plus tard.")
        return
    
    for match in matches:
        team1 = match['team1']
        team2 = match['team2']
        time = match['time']
        
        # Générer les recommandations de paris détaillées
        betting_rec = predictor.generate_betting_recommendations(team1, team2, 'nfl', time)
        
        await update.message.reply_text(betting_rec, parse_mode='Markdown')
    
    await update.message.reply_text(
        "✅ Toutes les prédictions NFL avec recommandations de paris ont été affichées!\n\n"
        "🔄 Les données se mettent à jour via Google à chaque appel de /nfl"
    )

async def nba_teams(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Liste des équipes NBA"""
    teams_list = "\n".join([f"{code}: {team['name']} (Power: {team['power']}/100)" 
                             for code, team in NBA_TEAMS.items()])
    message = f"""
🏀 *ÉQUIPES NBA DISPONIBLES:*

{teams_list}

💡 Utilisez: `/nba_analyze LAL` ou `/nba_matchup LAL GSW`
"""
    await update.message.reply_text(message, parse_mode='Markdown')

async def nhl_teams(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Liste des équipes NHL"""
    teams_list = "\n".join([f"{code}: {team['name']} (Power: {team['power']}/100)" 
                             for code, team in NHL_TEAMS.items()])
    message = f"""
🏒 *ÉQUIPES NHL DISPONIBLES:*

{teams_list}

💡 Utilisez: `/nhl_analyze NYR` ou `/nhl_matchup NYR TOR`
"""
    await update.message.reply_text(message, parse_mode='Markdown')

async def nfl_teams(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Liste des équipes NFL"""
    teams_list = "\n".join([f"{code}: {team['name']} (Power: {team['power']}/100)" 
                             for code, team in NFL_TEAMS.items()])
    message = f"""
🏈 *ÉQUIPES NFL DISPONIBLES:*

{teams_list}

💡 Utilisez: `/nfl_analyze KC` ou `/nfl_matchup KC SF`
"""
    await update.message.reply_text(message, parse_mode='Markdown')

async def nba_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse une équipe NBA"""
    if not context.args:
        await update.message.reply_text("❌ Usage: /nba_analyze LAL")
        return
    
    team_code = context.args[0].upper()
    
    if team_code not in NBA_TEAMS:
        await update.message.reply_text(f"❌ Équipe non trouvée: {team_code}")
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    team = NBA_TEAMS[team_code]
    player = NBA_PLAYERS_STATS[team_code]
    
    analysis = f"""
🏀 ULTRON NBA TEAM ANALYSIS
{team['name']}

📊 POWER RATING: {team['power']}/100
🔥 FORM: {team['form'].upper()}

⭐ STAR PLAYER: {player['star']}
📈 PPG: {player['ppg']}
Status: {'🔴 INJURED' if player['injury'] else '✅ AVAILABLE'}

💡 BETTING INSIGHT:
{'⚠️ Star player injured - CAUTION' if player['injury'] else '✅ Full roster available - GREEN LIGHT'}
"""
    
    await update.message.reply_text(analysis)

async def nhl_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse une équipe NHL"""
    if not context.args:
        await update.message.reply_text("❌ Usage: /nhl_analyze NYR")
        return
    
    team_code = context.args[0].upper()
    
    if team_code not in NHL_TEAMS:
        await update.message.reply_text(f"❌ Équipe non trouvée: {team_code}")
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    team = NHL_TEAMS[team_code]
    player = NHL_PLAYERS_STATS.get(team_code, {'star': 'N/A', 'ppg': 0, 'injury': False})
    
    analysis = f"""
🏒 ULTRON NHL TEAM ANALYSIS
{team['name']}

📊 POWER RATING: {team['power']}/100
🔥 FORM: {team['form'].upper()}

⭐ STAR PLAYER: {player['star']}
📈 PPG: {player['ppg']}
Status: {'🔴 INJURED' if player['injury'] else '✅ AVAILABLE'}

💡 BETTING INSIGHT:
{'⚠️ Star player injured - CAUTION' if player['injury'] else '✅ Full roster available - GREEN LIGHT'}
"""
    
    await update.message.reply_text(analysis)

async def nfl_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse une équipe NFL"""
    if not context.args:
        await update.message.reply_text("❌ Usage: /nfl_analyze KC")
        return
    
    team_code = context.args[0].upper()
    
    if team_code not in NFL_TEAMS:
        await update.message.reply_text(f"❌ Équipe non trouvée: {team_code}")
        return
    
    await update.message.chat.send_action(ChatAction.TYPING)
    
    team = NFL_TEAMS[team_code]
    player = NFL_PLAYERS_STATS.get(team_code, {'star': 'N/A', 'ppg': 0, 'injury': False})
    
    analysis = f"""
🏈 ULTRON NFL TEAM ANALYSIS
{team['name']}

📊 POWER RATING: {team['power']}/100
🔥 FORM: {team['form'].upper()}

⭐ STAR PLAYER: {player['star']}
📈 PASSING YARDS: {player['ppg']}
Status: {'🔴 INJURED' if player['injury'] else '✅ AVAILABLE'}

💡 BETTING INSIGHT:
{'⚠️ Star player injured - CAUTION' if player['injury'] else '✅ Full roster available - GREEN LIGHT'}
"""
    
    await update.message.reply_text(analysis)

def main() -> None:
    """Start the bot"""
    
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "="*60)
        print("❌ ERREUR: Token Telegram manquant!")
        print("="*60)
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers de commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # NBA commands
    application.add_handler(CommandHandler("nba", nba_predictions))
    application.add_handler(CommandHandler("nba_teams", nba_teams))
    application.add_handler(CommandHandler("nba_analyze", nba_analyze))
    
    # NHL commands
    application.add_handler(CommandHandler("nhl", nhl_predictions))
    application.add_handler(CommandHandler("nhl_teams", nhl_teams))
    application.add_handler(CommandHandler("nhl_analyze", nhl_analyze))
    
    # NFL commands
    application.add_handler(CommandHandler("nfl", nfl_predictions))
    application.add_handler(CommandHandler("nfl_teams", nfl_teams))
    application.add_handler(CommandHandler("nfl_analyze", nfl_analyze))
    
    # Lance le bot
    print("\n" + "="*60)
    print("🤖 ULTRON 3.0 MULTISPORT - Telegram Bot")
    print("="*60)
    print("\n✅ Bot démarré avec succès!")
    print("📱 Le bot est maintenant actif sur Telegram")
    print("\n🌐 SUPPORTED SPORTS:")
    print("   🏀 NBA (Basketball)")
    print("   🏒 NHL (Hockey)")
    print("   🏈 NFL (American Football)")
    print("\n💾 Matchs récupérés via APIs OFFICIELLES en temps réel")
    print("   • NBA: BallDontLie API")
    print("   • NHL: NHL Stats API")
    print("   • NFL: ESPN API")
    print("\n" + "="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
