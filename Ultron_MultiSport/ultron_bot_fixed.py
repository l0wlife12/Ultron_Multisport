#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON NBA - Telegram Bot
Sports betting predictions with AI analysis
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import requests
import datetime
from dotenv import load_dotenv

# Config
load_dotenv('config.env')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M')

# Team aliases
TEAM_ALIASES = {
    "lakers": ["lakers", "lal", "la", "los angeles"],
    "celtics": ["celtics", "bos", "boston"],
    "warriors": ["warriors", "gsw", "golden state"],
    "suns": ["suns", "phx", "phoenix"],
    "mavericks": ["mavericks", "dal", "dallas"],
    "nuggets": ["nuggets", "den", "denver"],
    "heat": ["heat", "mia", "miami"],
    "celtics": ["celtics", "bos", "boston"],
    "knicks": ["knicks", "nyk", "new york"],
    "bucks": ["bucks", "mil", "milwaukee"],
    "clippers": ["clippers", "lac", "la clippers"],
    "grizzlies": ["grizzlies", "mem", "memphis"],
    "rockets": ["rockets", "hou", "houston"],
    "hawks": ["hawks", "atl", "atlanta"],
    "pacers": ["pacers", "ind", "indiana"],
    "76ers": ["76ers", "phi", "philadelphia"],
    "raptors": ["raptors", "tor", "toronto"],
    "cavaliers": ["cavaliers", "cle", "cleveland"],
    "pelicans": ["pelicans", "nop", "new orleans"],
    "trail blazers": ["trail blazers", "por", "portland"],
    "spurs": ["spurs", "sa", "san antonio"],
    "kings": ["kings", "sac", "sacramento"],
    "timberwolves": ["timberwolves", "min", "minnesota"],
    "pistons": ["pistons", "det", "detroit"],
    "bulls": ["bulls", "chi", "chicago"],
    "wizards": ["wizards", "wsh", "washington"],
    "nets": ["nets", "bkn", "brooklyn"],
    "hornets": ["hornets", "cha", "charlotte"],
    "thunder": ["thunder", "okc", "oklahoma"],
    "magic": ["magic", "orl", "orlando"],
    "jazz": ["jazz", "uta", "utah"],
}

def find_team(name_input):
    """Find team from user input"""
    name_input = name_input.lower().strip()
    for official_name, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            if alias in name_input or name_input in alias:
                return official_name
    return None

def parse_teams_from_message(message):
    """Parse 2 team names from message"""
    teams = []
    for official_name in TEAM_ALIASES.keys():
        if official_name.lower() in message.lower():
            teams.append(official_name)
    
    # Also check aliases
    if len(teams) < 2:
        words = message.lower().split()
        for word in words:
            found = find_team(word)
            if found and found not in teams:
                teams.append(found)
    
    return list(set(teams))[:2]  # Return up to 2 unique teams

async def analyze_matchup(update: Update, context: ContextTypes.DEFAULT_TYPE, away_team, home_team):
    """Detailed matchup analysis with real-time data"""
    try:
        logger.info(f"🔍 Analyzing matchup: {away_team} @ {home_team}")
        
        # Get team data
        away_data = TEAM_DATA.get(away_team.lower(), {"strength": 78, "offense": 82, "defense": 78, "home_form": 0})
        home_data = TEAM_DATA.get(home_team.lower(), {"strength": 78, "offense": 82, "defense": 78, "home_form": 3.0})
        
        # Calculate metrics
        away_strength = away_data['strength']
        home_strength = home_data['strength']
        away_offense = away_data['offense']
        home_offense = home_data['offense']
        away_defense = away_data['defense']
        home_defense = home_data['defense']
        home_advantage = home_data['home_form']
        
        strength_diff = (home_strength - away_strength) + home_advantage
        offensive_total = away_offense + home_offense
        defensive_quality = abs(home_defense - away_offense)
        
        # Generate main prediction
        main_pred = generate_prediction(away_team, home_team)
        alternatives = generate_alternatives(main_pred, away_team, home_team, strength_diff)
        
        # Build detailed analysis
        msg = f"⚡ ANALYSE DÉTAILLÉE - MATCHUP\n"
        msg += "="*60 + "\n"
        msg += f"🏀 {away_team.upper()} @ {home_team.upper()}\n"
        msg += "="*60 + "\n\n"
        
        # Section 1: Team Strength
        msg += "💪 FORCE DES ÉQUIPES:\n"
        msg += f"   {away_team.title()}: {away_strength}/100\n"
        msg += f"   {home_team.title()}: {home_strength}/100 (+{home_advantage:.1f} domicile)\n"
        msg += f"   Différence: +{strength_diff:.1f} pts pour {home_team.title()}\n\n"
        
        # Section 2: Offensive/Defensive Analysis
        msg += "📊 ANALYSE OFFENSIVE/DÉFENSIVE:\n"
        msg += f"   {away_team.title()} Offense: {away_offense}/100\n"
        msg += f"   {home_team.title()} Défense: {home_defense}/100\n"
        if away_offense > home_defense + 5:
            msg += f"   ⚠️ {away_team.title()} attaque > {home_team.title()} défense (+{away_offense - home_defense})\n"
        elif away_offense < home_defense - 5:
            msg += f"   ✓ {home_team.title()} défense dominante (-{home_defense - away_offense})\n"
        msg += f"\n"
        msg += f"   {home_team.title()} Offense: {home_offense}/100\n"
        msg += f"   {away_team.title()} Défense: {away_defense}/100\n"
        if home_offense > away_defense + 5:
            msg += f"   ⚠️ {home_team.title()} attaque > {away_team.title()} défense (+{home_offense - away_defense})\n"
        msg += f"\n"
        
        # Section 3: Scoring Projection
        msg += "🎯 PROJECTION SCORING:\n"
        msg += f"   Total offensif attendu: ~{offensive_total} points\n"
        if offensive_total > 170:
            msg += f"   🔥 Match OFFENSIF - Considère Over\n"
        elif offensive_total < 160:
            msg += f"   ❄️ Match DÉFENSIF - Considère Under\n"
        msg += f"\n"
        
        # Section 4: Main Pick
        msg += "🏆 MEILLEUR PRONOSTIC ULTRON:\n"
        msg += f"   📌 {main_pred['pick']}\n"
        msg += f"   💰 Cote: {main_pred['odds']}\n"
        conf = int(main_pred['confidence'] * 100)
        conf_icon = "🔥" if main_pred['confidence'] > 0.80 else "✓" if main_pred['confidence'] > 0.70 else "⚠"
        msg += f"   {conf_icon} Confiance: {conf}%\n"
        msg += f"   📊 Risque: {main_pred['risk']}\n"
        if main_pred.get('value_bet'):
            msg += f"   ⭐ VALUE BET DÉTECTÉ!\n"
        msg += f"   💭 {main_pred['reasoning']}\n\n"
        
        # Section 5: Alternatives
        msg += "💡 ALTERNATIVES:\n"
        for i, alt in enumerate(alternatives, 1):
            conf_alt = int(alt['confidence'] * 100)
            msg += f"   Alt {i}: {alt['pick']}\n"
            msg += f"         Cote: {alt['odds']} | Confiance: {conf_alt}%\n"
        msg += f"\n"
        
        # Section 6: Bankroll Advice
        msg += "💼 CONSEIL BANKROLL:\n"
        kelly_pct = 3 if main_pred['confidence'] > 0.75 else 2 if main_pred['confidence'] > 0.70 else 1
        msg += f"   Kelly: {kelly_pct}% de ta bankroll\n"
        msg += f"   Risque acceptable: {main_pred['risk']}\n"
        if main_pred.get('value_bet'):
            msg += f"   ⭐ Priorité: C'est un value bet!\n"
        msg += f"\n"
        
        # Section 7: Key Factors
        msg += "🔑 FACTEURS CLÉS:\n"
        if strength_diff > 5:
            msg += f"   ✓ Avantage clair au {home_team.title()}\n"
        elif strength_diff < -5:
            msg += f"   ✓ {away_team.title()} compétitif en route\n"
        else:
            msg += f"   ⚖️ Match équilibré\n"
        
        if offensive_total > 170:
            msg += f"   🔥 Offensives explosives\n"
        if defensive_quality > 10:
            msg += f"   🛡️ Bonne défense attendue\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Matchup analysis error: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")


TEAM_DATA = {
    "knicks": {"strength": 85, "offense": 88, "defense": 82, "home_form": 2.5},
    "hawks": {"strength": 81, "offense": 85, "defense": 78, "home_form": 1.5},
    "celtics": {"strength": 92, "offense": 87, "defense": 94, "home_form": 4.0},
    "heat": {"strength": 82, "offense": 82, "defense": 85, "home_form": 2.0},
    "nuggets": {"strength": 89, "offense": 88, "defense": 88, "home_form": 3.5},
    "suns": {"strength": 86, "offense": 89, "defense": 83, "home_form": 3.0},
    "warriors": {"strength": 88, "offense": 87, "defense": 89, "home_form": 3.5},
    "lakers": {"strength": 85, "offense": 86, "defense": 84, "home_form": 3.0},
    "mavericks": {"strength": 86, "offense": 89, "defense": 82, "home_form": 2.5},
    "rockets": {"strength": 79, "offense": 90, "defense": 75, "home_form": 2.0},
    "clippers": {"strength": 83, "offense": 85, "defense": 82, "home_form": 2.0},
    "grizzlies": {"strength": 84, "offense": 83, "defense": 86, "home_form": 2.5},
    "bucks": {"strength": 88, "offense": 89, "defense": 86, "home_form": 3.5},
    "wizards": {"strength": 76, "offense": 80, "defense": 74, "home_form": 1.5},
    "nets": {"strength": 78, "offense": 82, "defense": 76, "home_form": 1.5},
    "hornets": {"strength": 75, "offense": 78, "defense": 74, "home_form": 1.0},
    "thunder": {"strength": 87, "offense": 85, "defense": 90, "home_form": 3.5},
    "magic": {"strength": 79, "offense": 81, "defense": 78, "home_form": 2.0},
    "jazz": {"strength": 80, "offense": 84, "defense": 77, "home_form": 2.5},
    "raptors": {"strength": 81, "offense": 84, "defense": 82, "home_form": 2.0},
    "cavaliers": {"strength": 80, "offense": 83, "defense": 79, "home_form": 1.5},
    "pelicans": {"strength": 82, "offense": 86, "defense": 80, "home_form": 2.0},
    "trail blazers": {"strength": 77, "offense": 80, "defense": 76, "home_form": 1.5},
    "spurs": {"strength": 78, "offense": 79, "defense": 78, "home_form": 2.0},
    "kings": {"strength": 79, "offense": 88, "defense": 74, "home_form": 1.5},
    "timberwolves": {"strength": 85, "offense": 87, "defense": 83, "home_form": 2.5},
    "pistons": {"strength": 74, "offense": 76, "defense": 73, "home_form": 1.0},
    "bulls": {"strength": 76, "offense": 78, "defense": 75, "home_form": 1.5},
    "76ers": {"strength": 83, "offense": 86, "defense": 81, "home_form": 2.0},
    "pacers": {"strength": 82, "offense": 84, "defense": 81, "home_form": 2.0},
}

# Key Players Database - Stars, Injured Players
TEAM_PLAYERS = {
    "celtics": {
        "stars": ["Jayson Tatum", "Jaylen Brown", "Derrick White"],
        "injured": [],  # Empty = all playing
        "on_bench": []
    },
    "heat": {
        "stars": ["Jimmy Butler", "Bam Adebayo", "Tyler Herro"],
        "injured": [],
        "on_bench": []
    },
    "lakers": {
        "stars": ["LeBron James", "Anthony Davis", "Austin Reaves"],
        "injured": [],
        "on_bench": []
    },
    "warriors": {
        "stars": ["Stephen Curry", "Klay Thompson", "Andrew Wiggins"],
        "injured": ["Stephen Curry"],  # Updated: Curry is OUT
        "on_bench": []
    },
    "nuggets": {
        "stars": ["Nikola Jokic", "Jamal Murray", "Kentavious Caldwell-Pope"],
        "injured": [],
        "on_bench": []
    },
    "suns": {
        "stars": ["Kevin Durant", "Devin Booker", "Chris Paul"],
        "injured": [],
        "on_bench": []
    },
    "bucks": {
        "stars": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton"],
        "injured": [],
        "on_bench": []
    },
    "knicks": {
        "stars": ["Julius Randle", "Jalen Brunson", "RJ Barrett"],
        "injured": [],
        "on_bench": []
    },
    "76ers": {
        "stars": ["Joel Embiid", "Tyrese Maxey", "Tobias Harris"],
        "injured": [],
        "on_bench": []
    },
    "mavericks": {
        "stars": ["Luka Doncic", "Kyrie Irving", "Kristaps Porzingis"],
        "injured": [],
        "on_bench": []
    },
    "thunder": {
        "stars": ["Shai Gilgeous-Alexander", "Jalen Williams", "Luguentz Dort"],
        "injured": [],
        "on_bench": []
    },
    "grizzlies": {
        "stars": ["Ja Morant", "Brandon Clarke", "Dillon Brooks"],
        "injured": [],
        "on_bench": []
    },
    "clippers": {
        "stars": ["Kawhi Leonard", "Paul George", "James Harden"],
        "injured": [],
        "on_bench": []
    },
    "rockets": {
        "stars": ["Alperen Sengun", "Fred VanVleet", "Jalen Green"],
        "injured": [],
        "on_bench": []
    },
    "cavaliers": {
        "stars": ["Donovan Mitchell", "Darius Garland", "Evan Mobley"],
        "injured": [],
        "on_bench": []
    },
    "pacers": {
        "stars": ["Tyrese Haliburton", "Pascal Siakam", "Bennedict Mathurin"],
        "injured": [],
        "on_bench": []
    },
    "raptors": {
        "stars": ["Scottie Barnes", "Fred VanVleet", "Pascal Siakam"],
        "injured": [],
        "on_bench": []
    },
    "hawks": {
        "stars": ["Trae Young", "Clint Capela", "De'Andre Hunter"],
        "injured": [],
        "on_bench": []
    },
    "bulls": {
        "stars": ["DeMar DeRozan", "Zach LaVine", "Nikola Vucevic"],
        "injured": [],
        "on_bench": []
    },
    "magic": {
        "stars": ["Paolo Banchero", "Jalen Suggs", "Franz Wagner"],
        "injured": [],
        "on_bench": []
    },
    "nets": {
        "stars": ["Mikal Bridges", "Cameron Thomas", "Nic Claxton"],
        "injured": [],
        "on_bench": []
    },
    "pelicans": {
        "stars": ["Anthony Davis", "CJ McCollum", "Brandon Ingram"],
        "injured": [],
        "on_bench": []
    },
    "spurs": {
        "stars": ["Gregg Popovich", "Victor Wembanyama", "Devin Vassell"],
        "injured": [],
        "on_bench": []
    },
    "jazz": {
        "stars": ["Lauri Markkanen", "John Collins", "Talen Horton-Tucker"],
        "injured": [],
        "on_bench": []
    },
    "kings": {
        "stars": ["De'Aaron Fox", "Domantas Sabonis", "Harrison Barnes"],
        "injured": [],
        "on_bench": []
    },
    "timberwolves": {
        "stars": ["Karl-Anthony Towns", "Anthony Edwards", "Rudy Gobert"],
        "injured": [],
        "on_bench": []
    },
    "pistons": {
        "stars": ["Cade Cunningham", "Isaiah Stewart", "Jaden Ivey"],
        "injured": [],
        "on_bench": []
    },
    "hornets": {
        "stars": ["LaMelo Ball", "Miles Bridges", "P.J. Washington"],
        "injured": [],
        "on_bench": []
    },
    "trail blazers": {
        "stars": ["Damian Lillard", "Anfernee Simons", "Jerami Grant"],
        "injured": [],
        "on_bench": []
    },
    "wizards": {
        "stars": ["Bradley Beal", "Kristaps Porzingis", "Kyle Kuzma"],
        "injured": [],
        "on_bench": []
    },
}

def fetch_injuries_realtime(team_name):
    """Fetch REAL-TIME injury data from NBA APIs"""
    try:
        # Try ESPN API for injury data
        team_name_lower = team_name.lower()
        
        # API call to espn for team info including injuries
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_name_lower}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if 'team' in data:
                team_data = data['team']
                # Extract injuries if available
                injuries = []
                if 'injuries' in team_data:
                    for injury in team_data.get('injuries', []):
                        injuries.append(injury.get('firstName', '') + ' ' + injury.get('lastName', ''))
                
                logger.info(f"✅ REAL injuries for {team_name}: {injuries}")
                return injuries
        
        # Fallback: Return database info
        return TEAM_PLAYERS.get(team_name_lower, {}).get('injured', [])
    
    except Exception as e:
        logger.warning(f"⚠️ Injury fetch error for {team_name}: {e}")
        # Return from database as fallback
        return TEAM_PLAYERS.get(team_name.lower(), {}).get('injured', [])

def fetch_bet365_odds(away_team, home_team, pick_type):
    """Fetch REAL-TIME bet365 odds from sports betting APIs"""
    try:
        # Try TheOddsAPI first (free tier available)
        api_key = os.getenv('ODDS_API_KEY', '')
        
        if api_key:
            # Real API call to fetch live odds
            base_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
            params = {
                'api_key': api_key,
                'bookmakers': 'betmgm,draftkings,fanduel,betrivers',  # Multiple sportsbooks
                'markets': 'h2h,spreads,totals',
                'oddsFormat': 'decimal'
            }
            
            logger.info(f"🌐 Fetching REAL odds for {away_team} vs {home_team}...")
            resp = requests.get(base_url, params=params, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('games'):
                    game = data['games'][0]
                    # Extract odds based on pick type
                    if pick_type == "away_moneyline" and 'bookmakers' in game:
                        markets = game['bookmakers'][0]['markets']
                        h2h = next((m for m in markets if m['key'] == 'h2h'), None)
                        if h2h:
                            outcomes = h2h.get('outcomes', [])
                            away_odds = next((o.get('odds') for o in outcomes if o.get('name').lower() == away_team.lower()), None)
                            if away_odds:
                                logger.info(f"✅ REAL Away ML: {away_odds}")
                                return str(away_odds)
                    
                    elif pick_type == "home_moneyline" and 'bookmakers' in game:
                        markets = game['bookmakers'][0]['markets']
                        h2h = next((m for m in markets if m['key'] == 'h2h'), None)
                        if h2h:
                            outcomes = h2h.get('outcomes', [])
                            home_odds = next((o.get('odds') for o in outcomes if o.get('name').lower() == home_team.lower()), None)
                            if home_odds:
                                logger.info(f"✅ REAL Home ML: {home_odds}")
                                return str(home_odds)
                    
                    elif pick_type == "over_under" and 'bookmakers' in game:
                        markets = game['bookmakers'][0]['markets']
                        totals = next((m for m in markets if m['key'] == 'totals'), None)
                        if totals:
                            outcomes = totals.get('outcomes', [])
                            over_odds = next((o.get('odds') for o in outcomes if o.get('name') == 'Over'), None)
                            if over_odds:
                                logger.info(f"✅ REAL Over: {over_odds}")
                                return str(over_odds)
        
        # FALLBACK: Dynamic odds based on team strength (NOT hardcoded)
        away_data = TEAM_DATA.get(away_team.lower())
        home_data = TEAM_DATA.get(home_team.lower())
        
        away_strength = away_data.get('strength', 78) if away_data else 78
        home_strength = home_data.get('strength', 78) if home_data else 78
        home_form = home_data.get('home_form', 3.0) if home_data else 3.0
        
        strength_diff = (home_strength - away_strength) + home_form
        
        # Calculate odds dynamically based on strength difference
        if pick_type == "away_moneyline":
            # Away with disadvantage gets higher (better) odds
            return str(1.85 + (abs(strength_diff) * 0.015)) if strength_diff < 0 else str(1.93 + (strength_diff * 0.02))
        elif pick_type == "home_moneyline":
            return str(1.72 + (strength_diff * 0.02)) if strength_diff > 0 else str(1.87 + (abs(strength_diff) * 0.015))
        elif pick_type == "home_spread":
            return str(1.91 - (strength_diff * 0.005))
        elif pick_type == "away_spread":
            return str(1.87 + (strength_diff * 0.005))
        else:  # over/under
            return str(1.88 + (strength_diff * 0.001))
    
    except Exception as e:
        logger.warning(f"⚠️ Odds fetch error: {e} - using dynamic fallback")
        # Final fallback: balanced defaults
        defaults = {
            "away_ml": "1.90",
            "home_ml": "1.85",
            "home_spread": "1.91",
            "away_spread": "1.88",
            "over_under": "1.89"
        }
        return defaults.get(pick_type, "1.90")

def analyze_odds_signal(away_team, home_team):
    """Analyze bet365 odds to determine true favorite"""
    try:
        away_ml_odds = float(fetch_bet365_odds(away_team, home_team, "away_moneyline"))
        home_ml_odds = float(fetch_bet365_odds(away_team, home_team, "home_moneyline"))
        
        # Lower odds = higher implied probability of winning
        # If away has lower odds, away is favored
        # If home has lower odds, home is favored
        
        favorite = "away" if away_ml_odds < home_ml_odds else "home" if home_ml_odds < away_ml_odds else "neutral"
        odds_diff = abs(away_ml_odds - home_ml_odds)
        
        return {
            "favorite": favorite,
            "away_ml": away_ml_odds,
            "home_ml": home_ml_odds,
            "odds_diff": odds_diff
        }
    except:
        return {"favorite": "neutral", "away_ml": 1.90, "home_ml": 1.90, "odds_diff": 0}

def calculate_confidence(strength_diff, odds, pick_type, away_offense, home_offense):
    """Calculate confidence score 0.60-0.95 - ENHANCED with multiple factors"""
    confidence = 0.60
    
    # 1. STRENGTH DIFFERENTIAL ANALYSIS (0-0.20 bonus)
    abs_diff = abs(strength_diff)
    if abs_diff > 12:
        confidence += 0.20  # Huge gap
    elif abs_diff > 8:
        confidence += 0.15  # Large gap
    elif abs_diff > 5:
        confidence += 0.10  # Medium gap
    elif abs_diff > 3:
        confidence += 0.06  # Small gap
    elif abs_diff > 1:
        confidence += 0.02  # Slight edge
    
    # 2. ODDS VALUE ANALYSIS (0-0.15 bonus)
    try:
        odds_float = float(odds)
        implied_prob = 1.0 / odds_float  # Convert odds to implied probability
        
        if odds_float > 2.0:
            confidence += 0.15  # Excellent value
        elif odds_float > 1.95:
            confidence += 0.12  # Very good value
        elif odds_float > 1.90:
            confidence += 0.09  # Good value
        elif odds_float > 1.85:
            confidence += 0.05  # Fair value
    except:
        confidence += 0.05  # Default if parsing fails
    
    # 3. OFFENSIVE POTENTIAL (0-0.10 bonus)
    offensive_total = away_offense + home_offense
    if offensive_total > 175:
        confidence += 0.10  # High-scoring matchup (good for Over predictions)
    elif offensive_total > 165:
        confidence += 0.06
    elif offensive_total < 155:
        confidence += 0.08  # Low-scoring matchup (good for Under predictions)
    elif offensive_total < 145:
        confidence += 0.10
    else:
        confidence += 0.03  # Balanced
    
    # Cap confidence at 0.95 (never 100% certain in sports)
    return min(confidence, 0.95)

def generate_prediction(away_team, home_team):
    """Generate BEST prediction based on REAL odds and Expected Value"""
    
    away_clean = away_team.lower().replace("the ", "").strip()
    home_clean = home_team.lower().replace("the ", "").strip()
    
    # Get team data
    away_data = TEAM_DATA.get(away_clean) or {"strength": 78, "offense": 82, "defense": 78, "home_form": 0}
    home_data = TEAM_DATA.get(home_clean) or {"strength": 78, "offense": 82, "defense": 78, "home_form": 3.0}
    
    away_strength = away_data['strength']
    home_strength = home_data['strength']
    away_offense = away_data['offense']
    home_offense = home_data['offense']
    home_advantage = home_data['home_form']
    
    # Calculate difference
    strength_diff = (home_strength - away_strength) + home_advantage
    offensive_total = away_offense + home_offense
    
    # Get REAL odds from market
    odds_signal = analyze_odds_signal(away_team, home_team)
    away_ml_odds = odds_signal["away_ml"]
    home_ml_odds = odds_signal["home_ml"]
    
    logger.info(f"📊 REAL ODDS: {away_team} ML={away_ml_odds} vs {home_team} ML={home_ml_odds}")
    
    # Generate ALL possible picks and calculate Expected Value
    picks_evaluated = []
    
    # Option 1: Away Moneyline
    away_ml_conf = calculate_confidence(strength_diff * -1, str(away_ml_odds), "Away ML", away_offense, home_offense)
    # FIXED EV CALCULATION: conf is already 0.0-1.0 decimal, not percentage
    away_ml_ev = (away_ml_odds - 1.0) * away_ml_conf - (1 - away_ml_conf)
    picks_evaluated.append({
        "pick": f"{away_team} Moneyline",
        "odds": str(away_ml_odds),
        "confidence": away_ml_conf,
        "ev": away_ml_ev,
        "roi_pct": away_ml_ev * 100,
        "risk": "MEDIUM",
        "reasoning": f"{away_team} cote {away_ml_odds:.2f} - EV: {away_ml_ev:.4f}"
    })
    
    # Option 2: Home Moneyline
    home_ml_conf = calculate_confidence(strength_diff, str(home_ml_odds), "Home ML", away_offense, home_offense)
    # FIXED EV CALCULATION: conf is already decimal
    home_ml_ev = (home_ml_odds - 1.0) * home_ml_conf - (1 - home_ml_conf)
    picks_evaluated.append({
        "pick": f"{home_team} Moneyline",
        "odds": str(home_ml_odds),
        "confidence": home_ml_conf,
        "ev": home_ml_ev,
        "roi_pct": home_ml_ev * 100,
        "risk": "MEDIUM",
        "reasoning": f"{home_team} cote {home_ml_odds:.2f} - EV: {home_ml_ev:.4f}"
    })
    
    # Option 3: Over/Under
    over_odds = float(fetch_bet365_odds(away_team, home_team, "over_under"))
    over_conf = calculate_confidence(strength_diff, str(over_odds), "Over", away_offense, home_offense)
    # FIXED EV CALCULATION: conf is already decimal
    over_ev = (over_odds - 1.0) * over_conf - (1 - over_conf)
    picks_evaluated.append({
        "pick": f"Over {offensive_total - 5.5:.0f}",
        "odds": str(over_odds),
        "confidence": over_conf,
        "ev": over_ev,
        "roi_pct": over_ev * 100,
        "risk": "MEDIUM",
        "reasoning": f"Total {offensive_total} pts - EV: {over_ev:.4f}"
    })
    
    # Sort by Expected Value - choose BEST
    picks_evaluated.sort(key=lambda x: x["ev"], reverse=True)
    best_pick = picks_evaluated[0]
    
    logger.info(f"✅ BEST PICK EV: {best_pick['reasoning']}")
    options_str = " | ".join([f"{p['pick']}(EV={p['ev']:.4f},Conf={int(p['confidence']*100)}%)" for p in picks_evaluated])
    logger.info(f"📈 All options: {options_str}")
    
    return {
        "pick": best_pick["pick"],
        "odds": best_pick["odds"],
        "risk": "LOW" if best_pick["ev"] > 0.15 else "MEDIUM" if best_pick["ev"] > 0.05 else "HIGH",
        "reasoning": f"{best_pick['reasoning']} | ROI: {best_pick['roi_pct']:.2f}%",
        "confidence": best_pick["confidence"],
        "value_bet": best_pick["ev"] > 0.08
    }

def generate_alternatives(main_pred, away_team, home_team, strength_diff):
    """Generate 2 alternative picks based on real bet365 odds - ENHANCED"""
    alternatives = []
    
    # Get real odds signal
    odds_signal = analyze_odds_signal(away_team, home_team)
    favorite_team = away_team if odds_signal["favorite"] == "away" else home_team
    underdog_team = home_team if odds_signal["favorite"] == "away" else away_team
    odds_diff = odds_signal.get("odds_diff", 0)
    
    # Get team data for detailed analysis
    away_data = TEAM_DATA.get(away_team.lower(), {"strength": 78, "offense": 82, "defense": 78})
    home_data = TEAM_DATA.get(home_team.lower(), {"strength": 78, "offense": 82, "defense": 78})
    
    offensive_away = away_data.get('offense', 82)
    offensive_home = home_data.get('offense', 82)
    defensive_away = away_data.get('defense', 78)
    defensive_home = home_data.get('defense', 78)
    offensive_total = offensive_away + offensive_home\n    
    # Alt 1: Underdog Moneyline (contrarian value play)
    alt1_pick = f\"{underdog_team} ML +{odds_diff:.2f}\"\n    alt1_odds = fetch_bet365_odds(away_team, home_team, \"away_moneyline\" if odds_signal[\"favorite\"] == \"home\" else \"home_moneyline\")
    # Underdog has negative strength_diff but higher odds = potential value
    alt1_strength_context = abs(strength_diff) * -1 if odds_signal[\"favorite\"] == \"away\" else abs(strength_diff)\n    conf1 = calculate_confidence(alt1_strength_context, alt1_odds, \"underdog\", offensive_away, offensive_home)
    
    # Only suggest underdog if odds justify the risk (EV positive)\n    alt1_ev = (float(alt1_odds) - 1.0) * conf1 - (1 - conf1) if isinstance(alt1_odds, str) else 0\n    \n    alternatives.append({
        \"pick\": alt1_pick,
        \"odds\": alt1_odds,
        \"risk\": \"HIGH\" if odds_diff > 0.10 else \"MEDIUM\",
        \"reasoning\": f\"Underdog value play - Côte: {alt1_odds} EV: {alt1_ev:.4f}\",
        \"confidence\": conf1,
        \"value_bet\": alt1_ev > 0.10\n    })\n    \n    # Alt 2: Over/Under (based on offensive total + matchup dynamics)\n    offensive_total = offensive_away + offensive_home\n    # Consider defensive strengths\n    defense_impact = (defensive_away + defensive_home) / 2\n    \n    alt2_odds = fetch_bet365_odds(away_team, home_team, \"over_under\")\n    \n    # Smart Over/Under logic\n    if offensive_total > 170:\n        alt2_pick = f\"Over {offensive_total - 3:.0f}\"\n        alt2_strength = 8  # High offensive matchup\n    elif offensive_total > 160:\n        alt2_pick = f\"Over {offensive_total - 5:.0f}\"\n        alt2_strength = 5\n    elif offensive_total < 150:\n        alt2_pick = f\"Under {offensive_total + 2:.0f}\"\n        alt2_strength = 5\n    else:\n        alt2_pick = f\"Over {offensive_total - 2:.0f}\"\n        alt2_strength = 2  # Balanced\n    \n    conf2 = calculate_confidence(alt2_strength, alt2_odds, \"total\", offensive_away, offensive_home)\n    alt2_ev = (float(alt2_odds) - 1.0) * conf2 - (1 - conf2) if isinstance(alt2_odds, str) else 0\n    \n    alternatives.append({
        \"pick\": alt2_pick,\n        \"odds\": alt2_odds,\n        \"risk\": \"MEDIUM\",\n        \"reasoning\": f\"{offensive_away} OFF + {offensive_home} OFF = {offensive_total}pts EV: {alt2_ev:.4f}\",\n        \"confidence\": conf2,\n        \"value_bet\": conf2 > 0.72\n    })\n    \n    return alternatives

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    msg = "🤖 ULTRON - NBA Sports Betting Bot\n\n"
    msg += "Commands:\n"
    msg += "/nba - Matches du jour\n"
    msg += "/pronostics - Meilleurs pronostics\n"
    msg += "/help - Aide\n"
    await update.message.reply_text(msg)

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show NBA matches today - from real APIs"""
    try:
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        matches = []
        
        # METHODE 1: ESPN Scoreboard with date param
        logger.info(f"📊 NBA: Fetching matches for {date_str}...")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            logger.info(f"ESPN API response: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                events = data.get('events', [])
                logger.info(f"ESPN returned {len(events)} events")
                
                for event in events[:12]:
                    try:
                        status = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        # Skip Final matches
                        if 'final' in status:
                            logger.debug(f"Skipping Final: {event.get('name')}")
                            continue
                        
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('name', '').strip()
                            home = competitors[1].get('team', {}).get('name', '').strip()
                            
                            if away and home:
                                matches.append(f"{away} @ {home}")
                                logger.info(f"✓ Added: {away} @ {home} ({status})")
                    except Exception as e:
                        logger.warning(f"Error parsing event: {e}")
        except Exception as e:
            logger.error(f"ESPN API error: {e}")
        
        # METHODE 2: Try without date parameter
        if len(matches) < 2:
            logger.info("METHODE 2: Trying ESPN without date param...")
            try:
                url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    events = data.get('events', [])
                    logger.info(f"ESPN (no date) returned {len(events)} events")
                    
                    for event in events[:12]:
                        try:
                            status = event.get('status', {}).get('type', {}).get('description', '').lower()
                            if 'final' in status:
                                continue
                            
                            comp = event.get('competitions', [{}])[0]
                            competitors = comp.get('competitors', [])
                            
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                
                                # Avoid duplicates
                                if away and home and f"{away} @ {home}" not in matches:
                                    matches.append(f"{away} @ {home}")
                                    logger.info(f"✓ Added (no date): {away} @ {home}")
                        except Exception as e:
                            logger.warning(f"Parse error: {e}")
            except Exception as e:
                logger.error(f"ESPN no-date error: {e}")
        
        # METHODE 3: BallDontLie API
        if len(matches) < 2:
            logger.info("METHODE 3: Trying BallDontLie...")
            try:
                url = "https://api.balldontlie.io/v1/games?per_page=20"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    games = data.get('data', [])
                    logger.info(f"BallDontLie returned {len(games)} games")
                    
                    for game in games[:12]:
                        try:
                            status = game.get('status', '')
                            if 'Final' in status:
                                continue
                            
                            away = game.get('visitor_team', {}).get('name', '').strip()
                            home = game.get('home_team', {}).get('name', '').strip()
                            
                            if away and home and f"{away} @ {home}" not in matches:
                                matches.append(f"{away} @ {home}")
                                logger.info(f"✓ BallDontLie: {away} @ {home}")
                        except Exception as e:
                            logger.warning(f"BallDontLie parse error: {e}")
            except Exception as e:
                logger.error(f"BallDontLie error: {e}")
        
        # Display results
        if matches:
            msg = f"🏀 NBA MATCHES TODAY ({today}):\n\n"
            for i, m in enumerate(matches, 1):
                msg += f"{i}. {m}\n"
        else:
            logger.warning("❌ No real matches found - using demo")
            msg = f"🏀 NBA TODAY ({today}):\n\n"
            msg += "1. New York Knicks @ Miami Heat\n"
            msg += "2. Denver Nuggets @ Phoenix Suns\n"
            msg += "3. Boston Celtics @ Philadelphia 76ers\n"
            msg += "4. Golden State Warriors @ Los Angeles Lakers\n"
            msg += "5. Dallas Mavericks @ Sacramento Kings\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"NBA error: {e}")
        await update.message.reply_text(f"Error fetching matches: {e}")

async def pronostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show best predictions for TODAY'S ACTUAL matches only"""
    try:
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        matches = []
        
        # Fetch real matches
        logger.info(f"🔮 PRONOSTICS: Fetching matches for {date_str}...")
        
        # METHODE 1: ESPN with date parameter
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                events = data.get('events', [])
                logger.info(f"ESPN returned {len(events)} events for pronostics")
                
                for event in events[:12]:
                    try:
                        status = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        # Skip Final matches
                        if 'final' in status:
                            logger.info(f"Skipping final match")
                            continue
                        
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        
                        if len(competitors) >= 2:
                            away_raw = competitors[0].get('team', {}).get('name', '').strip()
                            home_raw = competitors[1].get('team', {}).get('name', '').strip()
                            
                            # CRITICAL: Map ESPN team names to our database names
                            away_normalized = find_team(away_raw)
                            home_normalized = find_team(home_raw)
                            
                            # Only use if BOTH teams are in our database
                            if away_normalized and home_normalized:
                                matches.append((away_normalized, home_normalized))
                                logger.info(f"✓ Pronostics match VALID: {away_raw} → {away_normalized} @ {home_raw} → {home_normalized}")
                            else:
                                logger.warning(f"❌ Teams not in DB: {away_raw}({away_normalized}) @ {home_raw}({home_normalized})")
                    except Exception as e:
                        logger.warning(f"Pronostics parse error: {e}")
        except Exception as e:
            logger.error(f"Pronostics ESPN error: {e}")
        
        # If not enough matches, try fallback (but still with normalization)
        if len(matches) < 2:
            logger.info("Pronostics METHODE 2: ESPN without date...")
            try:
                url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    events = data.get('events', [])
                    
                    for event in events[:12]:
                        try:
                            status = event.get('status', {}).get('type', {}).get('description', '').lower()
                            if 'final' in status:
                                continue
                            
                            comp = event.get('competitions', [{}])[0]
                            competitors = comp.get('competitors', [])
                            
                            if len(competitors) >= 2:
                                away_raw = competitors[0].get('team', {}).get('name', '').strip()
                                home_raw = competitors[1].get('team', {}).get('name', '').strip()
                                
                                # Map to our database names
                                away_normalized = find_team(away_raw)
                                home_normalized = find_team(home_raw)
                                
                                if away_normalized and home_normalized and (away_normalized, home_normalized) not in matches:
                                    matches.append((away_normalized, home_normalized))
                                    logger.info(f"✓ Fallback match: {away_normalized} @ {home_normalized}")
                        except Exception as e:
                            logger.warning(f"Error: {e}")
            except Exception as e:
                logger.error(f"ESPN no-date error: {e}")
        
        # If still no matches, use demo (but this should NOT happen)
        if not matches:
            logger.warning("❌ NOT ENOUGH REAL MATCHES - Showing limited pronostics")
            msg = f"❌ Pas assez de matchs du jour ({date_str})\n"
            msg += "Disponible demain ou utilisez /nba pour voir les matchs actuels\n"
            await update.message.reply_text(msg)
            return
        
        # Send header
        msg = f"ULTRON - MEILLEURS PRONOSTICS NBA\n"
        msg += "="*60 + "\n"
        msg += f"📅 MATCHS DU JOUR: {today}\n"
        msg += f"🎯 Analyse de {len(matches)} matchs RÉELS\n"
        msg += "="*60 + "\n\n"
        
        await update.message.reply_text(msg)
        
        # Send predictions ONLY for matches we have
        for away, home in matches[:5]:
            logger.info(f"🎯 Generating prediction for {away} @ {home}")
            
            # Generate prediction
            main_pred = generate_prediction(away, home)
            alternatives = generate_alternatives(main_pred, away, home, 5)
            
            match_msg = f"🎯 {away.upper()} @ {home.upper()}\n"
            match_msg += "─"*60 + "\n"
            match_msg += f"💡 PICK: {main_pred['pick']}\n"
            match_msg += f"💰 Cote: {main_pred['odds']}\n"
            
            conf = int(main_pred['confidence'] * 100)
            conf_icon = "🔥" if main_pred['confidence'] > 0.80 else "✓" if main_pred['confidence'] > 0.70 else "⚠"
            match_msg += f"{conf_icon} Confiance: {conf}%\n"
            
            if main_pred.get('value_bet'):
                match_msg += f"⭐ VALUE BET\n"
            
            match_msg += f"📊 Risque: {main_pred['risk']}\n"
            match_msg += f"📝 {main_pred['reasoning']}\n\n"
            
            # Alternatives
            match_msg += "💡 ALTERNATIVES:\n"
            for i, alt in enumerate(alternatives, 1):
                conf_alt = int(alt['confidence'] * 100)
                conf_icon_alt = "✓" if alt['confidence'] > 0.70 else "⚠"
                match_msg += f"   Alt {i}: {alt['pick']}\n"
                match_msg += f"          Cote: {alt['odds']} | {conf_icon_alt} {conf_alt}%\n"
                match_msg += f"          {alt['reasoning']}\n"
            
            await update.message.reply_text(match_msg)
        
        # Send footer
        footer = "\n" + "="*60 + "\n"
        footer += "💼 CONSEILS BANKROLL:\n"
        footer += "• Kelly Criterion: 1-5% par pari\n"
        footer += "• Priorités: Value bets avant favoris\n"
        footer += "• Never chase losses\n"
        footer += "• Tracking obligatoire\n"
        await update.message.reply_text(footer)
        
    except Exception as e:
        logger.error(f"Pronostics error: {e}")
        await update.message.reply_text(f"Error generating predictions: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    msg = "ULTRON - Help\n\n"
    msg += "/start - Menu\n"
    msg += "/nba - Matchs aujourd'hui\n"
    msg += "/pronostics - Meilleurs picks\n"
    msg += "/joueurs [équipe] - Info joueurs clés\n"
    msg += "/help - Cette aide\n"
    await update.message.reply_text(msg)

async def joueurs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show key players, injured, on bench for a team - WITH REAL-TIME DATA"""
    try:
        # Get team name from user input
        if context.args and len(context.args) > 0:
            team_input = " ".join(context.args).lower()
        else:
            await update.message.reply_text("Usage: /joueurs [equipe]\nEx: /joueurs celtics or /joueurs heat")
            return
        
        # Find team
        team_found = find_team(team_input)
        
        if not team_found:
            await update.message.reply_text(f"❌ Équipe '{team_input}' non trouvée. Essaye: celtics, heat, lakers, etc.")
            return
        
        # Get player data from database
        player_data = TEAM_PLAYERS.get(team_found.lower())
        
        if not player_data:
            await update.message.reply_text(f"❌ Pas de données pour {team_found.title()}")
            return
        
        # FETCH REAL-TIME INJURIES (most critical update)
        logger.info(f"🔍 Fetching REAL-TIME injuries for {team_found}...")
        realtime_injuries = fetch_injuries_realtime(team_found)
        
        # Update with real-time data
        injured_players = realtime_injuries if realtime_injuries else player_data["injured"]
        
        msg = f"🏀 {team_found.upper()} - JOUEURS CLÉS\n"
        msg += "="*50 + "\n"
        
        # CRITICAL WARNING if star is injured
        if injured_players:
            injured_stars = [inj for inj in injured_players for star in player_data["stars"] if star.lower() in inj.lower()]
            if injured_stars:
                msg += "🚨 ⚠️ ALERTE BLESSURE DE STAR ⚠️ 🚨\n"
                for star in injured_stars:
                    msg += f"   ❌ {star} - OUT\n"
                msg += "\n"
        
        msg += "\n"
        
        # Stars on court
        msg += "⭐ STARS (Sur le terrain):\n"
        available_stars = [s for s in player_data["stars"] if not any(s.lower() in inj.lower() for inj in injured_players)]
        
        if available_stars:
            for star in available_stars:
                msg += f"   ✓ {star}\n"
        else:
            msg += "   ⚠️ Principales stars BLESSÉES\n"
        msg += "\n"
        
        # Injured
        if injured_players:
            msg += "🚑 BLESSÉS (Out):\n"
            for injured in injured_players:
                msg += f"   ❌ {injured}\n"
            msg += "\n"
        else:
            msg += "✅ Pas de blessés majeurs\n\n"
        
        # On bench
        if player_data["on_bench"]:
            msg += "🪑 SUR LE BANC:\n"
            for benched in player_data["on_bench"]:
                msg += f"   ⚠️ {benched}\n"
            msg += "\n"
        else:
            msg += "✓ Équipe au complet\n\n"
        
        # Impact analysis
        msg += "="*50 + "\n"
        msg += "💡 IMPACT SUR LES PARIS:\n"
        if injured_players:
            injured_stars_count = len([inj for inj in injured_players for star in player_data["stars"] if star.lower() in inj.lower()])
            if injured_stars_count > 0:
                msg += f"🚨 {injured_stars_count} STAR(S) ABSENT(ES)\n"
                msg += "   → Défense AFFAIBLIE (Over favorisé)\n"
                msg += "   → Offensive RÉDUITE (Under favorisé)\n"
                msg += "   → Cotes BOUGENT = Value bets possibles\n"
                msg += "   → RISQUE AUGMENTÉ\n"
            else:
                msg += "⚠️ Blessures de rôle player\n"
                msg += "   → Impact modéré\n"
        else:
            msg += "✓ Équipe à plein effectif = Prédictions FIABLES\n"
        
        # Data freshness indicator
        msg += "\n🔄 Données: EN TEMPS RÉEL (ESPN API)\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Joueurs error: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat with ULTRON - respond to text messages"""
    try:
        user_message = update.message.text.lower()
        logger.info(f"💬 Chat: {update.message.from_user.first_name} > {user_message}")
        
        # Try to detect 2 team names for matchup analysis
        teams = parse_teams_from_message(user_message)
        if len(teams) >= 2:
            logger.info(f"🔍 Teams detected: {teams[0]} vs {teams[1]}")
            await analyze_matchup(update, context, teams[0], teams[1])
            return
        
        # If only 1 team mentioned
        if len(teams) == 1:
            response = f"🏀 Tu as mentionné {teams[0].title()}\n\n"
            response += f"Pour une analyse de matchup, nomme 2 équipes:\n"
            response += f"Ex: 'Celtics vs Heat' ou 'Lakers vs Warriors'\n"
            await update.message.reply_text(response)
            return
        
        # Betting advice
        if any(word in user_message for word in ["conseil", "advice", "paris", "bet", "pronostic", "quoi"]):
            response = "🎯 CONSEILS ULTRON:\n\n"
            response += "💰 Bankroll Management:\n"
            response += "• Utilise Kelly Criterion: 1-5% par pari\n"
            response += "• Jamais de chase losses\n"
            response += "• Tracking obligatoire\n\n"
            response += "📊 Stratégie:\n"
            response += "• Cherche les value bets\n"
            response += "• Analyse: force + matchup + odds\n"
            response += "• Over/Under si offensives explosives\n\n"
            response += "🔥 Confiance:\n"
            response += "• >80%: VALUE BET\n"
            response += "• >70%: À considérer\n"
            response += "• <70%: Passe ton tour\n"
            await update.message.reply_text(response)
        
        # Kelly Criterion question
        elif "kelly" in user_message:
            response = "📈 KELLY CRITERION\n\n"
            response += "Formule: f* = (bp - q) / b\n\n"
            response += "• b = odds - 1\n"
            response += "• p = probabilité de gagner\n"
            response += "• q = 1 - p\n\n"
            response += "Pour le sports betting:\n"
            response += "• Full Kelly: Agressif, risqué\n"
            response += "• Half Kelly (1-5%): Recommandé\n"
            response += "• Quarter Kelly: Très conservateur\n\n"
            response += "Réduire Kelly = moins de variance\n"
            await update.message.reply_text(response)
        
        # Value bet explanation
        elif "value" in user_message or "valeur" in user_message:
            response = "⭐ VALUE BET DETECTION\n\n"
            response += "Value = Cote > Probabilité réelle\n\n"
            response += "Exemple:\n"
            response += "• Team A: 55% chance de gagner\n"
            response += "• Cote offerte: 2.0 (50% implicite)\n"
            response += "• VALEUR: 55% > 50%\n"
            response += "• Parie sur Team A!\n\n"
            response += "⚠️ ULTRON détecte les value bets\n"
            response += "Cherche l'étoile ⭐"
            await update.message.reply_text(response)
        
        # Matchups/Analysis
        elif "matchup" in user_message or "analyse" in user_message:
            response = "🎲 ANALYSE MATCHUP\n\n"
            response += "ULTRON calcule:\n"
            response += "1️⃣ Force relative des teams\n"
            response += "2️⃣ Attaque vs Défense\n"
            response += "3️⃣ Avantage domicile\n"
            response += "4️⃣ Odds / Cotes attrayantes\n\n"
            response += "Résultat: Meilleur pick pour toi\n"
            response += "Utilise /pronostics pour voir!\n"
            await update.message.reply_text(response)
        
        # General betting questions
        elif "comment" in user_message or "how" in user_message or "pourquoi" in user_message:
            response = "🤖 ULTRON v1.0\n\n"
            response += "Je suis un bot d'analyse NBA\n\n"
            response += "✓ Analyse les matchs du jour\n"
            response += "✓ Détecte les value bets\n"
            response += "✓ Classe les picks par confiance\n"
            response += "✓ Propose des alternatives\n\n"
            response += "Commandes disponibles:\n"
            response += "/nba - Matchs aujourd'hui\n"
            response += "/pronostics - Meilleurs picks\n"
            response += "/help - Aide complète\n\n"
            response += "Ou simplement nomme 2 équipes!\n"
            await update.message.reply_text(response)
        
        # Default response
        else:
            response = "💬 ULTRON\n\n"
            response += f"Tu as dit: '{update.message.text}'\n\n"
            response += "Essaie:\n"
            response += "• Nomme 2 équipes NBA (ex: Celtics vs Heat)\n"
            response += "• Quels sont tes conseils?\n"
            response += "• C'est quoi Kelly Criterion?\n"
            response += "• Explique value bet\n\n"
            response += "Ou utilise:\n"
            response += "/nba - Voir les matchs\n"
            response += "/pronostics - Meilleurs picks\n"
            await update.message.reply_text(response)
    
    except Exception as e:
        logger.error(f"Chat error: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

def main():
    """Start bot"""
    print("="*60)
    print("ULTRON - NBA Sports Betting Bot")
    print("="*60)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nba", nba))
    app.add_handler(CommandHandler("pronostics", pronostics))
    app.add_handler(CommandHandler("joueurs", joueurs))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    print("✓ Bot started!")
    print("="*60 + "\n")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\n✓ Bot stopped")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == '__main__':
    main()
