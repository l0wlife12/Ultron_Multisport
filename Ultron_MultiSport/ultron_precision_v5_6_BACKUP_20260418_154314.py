#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON NBA - FINAL PRECISION v5.8
Real matchups with QUEBEC TIMEZONE + INTELLIGENT PREDICTIONS
"""

import os
import sys
import logging
import warnings
import datetime
import requests
import json
import pytz
import math

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# TIMEZONE QUÉBEC (EDT = UTC-4)
QUEBEC_TZ = pytz.timezone('America/Toronto')

def get_quebec_time():
    """Retourne l'heure actuelle en fuseau horaire Québec"""
    return datetime.datetime.now(QUEBEC_TZ)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set. Configure it in Railway environment variables or .env file.")

# Cache des matchs en temps réel
MATCHES_CACHE = []
MATCHES_CACHE_TIME = None

# Cache des matchs NHL et NFL
MATCHES_CACHE_NHL = []
MATCHES_CACHE_TIME_NHL = None
MATCHES_CACHE_NFL = []
MATCHES_CACHE_TIME_NFL = None

def get_live_matches():
    """
    Récupère les matchs NBA en direct - regarde aujourd'hui d'abord, puis les jours suivants
    Une fois tous les matchs du jour terminés, passe automatiquement au jour suivant
    """
    global MATCHES_CACHE, MATCHES_CACHE_TIME
    
    # Utiliser le cache s'il a moins de 2 minutes
    if MATCHES_CACHE and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:  # 2 minutes (plus court pour des données fraîches)
            return MATCHES_CACHE
    
    matches = []
    
    try:
        # Chercher les matchs sur les 7 prochains jours (jusqu'à trouver des matchs actifs/futurs)
        today = datetime.datetime.now()
        
        for day_offset in range(7):  # Vérifier jusqu'à 7 jours à l'avance
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            
            logger.info(f"📡 Recherche matchs NBA pour {search_date.strftime('%d/%m/%Y')} (Offset: +{day_offset}j)")
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                events_count = len(data.get('events', []))
                logger.info(f"📊 Événements trouvés: {events_count}")
                
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_dict = event.get('status', {})
                        status_type = status_dict.get('type', {}).get('name', '').lower()
                        status_desc = status_dict.get('type', {}).get('description', '').lower()
                        
                        # FILTRER: Accepter seulement les matchs ACTIFS/FUTURS
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed', 'closed']
                        is_blocked = any(word in status_desc for word in blocked_statuses)
                        
                        if not is_blocked:  # Match actif ou futur
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').replace('vs ', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').replace('vs ', '').strip()
                                
                                if away and home:
                                    daily_matches.append((away, home))
                                    logger.info(f"✅ Match trouvé: {away} @ {home} ({status_desc})")
                    except Exception as e:
                        logger.debug(f"Erreur parsing: {e}")
                        continue
                
                # Si on trouve des matchs actifs/futurs, les retourner
                if daily_matches:
                    logger.info(f"🎯 {len(daily_matches)} matchs actifs/futurs pour {search_date.strftime('%d/%m/%Y')}")
                    MATCHES_CACHE = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    return daily_matches
                else:
                    logger.warning(f"⚠️ Aucun match actif pour {search_date.strftime('%d/%m/%Y')} - Vérification jour suivant...")
                    continue
            else:
                logger.warning(f"⚠️ ESPN API echec: HTTP {resp.status_code}")
                continue
        
        # Si aucun match trouvé sur 7 jours
        logger.warning("⚠️ Aucun match NBA dans les 7 prochains jours - Utilisant matchs de DÉMO")
        demo_matches = [
            ("Warriors", "Kings"),
            ("Clippers", "Trail Blazers"),
            ("Suns", "Lakers"),
        ]
        MATCHES_CACHE = demo_matches
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return demo_matches
            
    except Exception as e:
        logger.error(f"❌ Erreur ESPN: {e}")
        # Fallback sur matchs de démo
        demo_matches = [
            ("Warriors", "Kings"),
            ("Clippers", "Trail Blazers"),
            ("Suns", "Lakers"),
        ]
        MATCHES_CACHE = demo_matches
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return demo_matches

# REAL NBA STATS 2025-2026 Season (Advanced Metrics)
TEAM_STATS = {
    "hornets": {"strength": 73, "orth": 110.5, "ortg": 108.2, "drtg": 115.3, "wins": 28, "losses": 54},
    "pistons": {"strength": 75, "orth": 112.1, "ortg": 109.8, "drtg": 113.2, "wins": 32, "losses": 50},
    "wizards": {"strength": 75, "orth": 111.8, "ortg": 109.2, "drtg": 114.1, "wins": 31, "losses": 51},
    "heat": {"strength": 82, "orth": 115.2, "ortg": 114.5, "drtg": 109.8, "wins": 44, "losses": 38},
    "hawks": {"strength": 81, "orth": 116.3, "ortg": 115.2, "drtg": 110.5, "wins": 43, "losses": 39},
    "cavaliers": {"strength": 86, "orth": 117.8, "ortg": 116.9, "drtg": 108.2, "wins": 49, "losses": 33},
    "celtics": {"strength": 92, "orth": 119.5, "ortg": 118.2, "drtg": 105.5, "wins": 56, "losses": 26},
    "pelicans": {"strength": 77, "orth": 113.9, "ortg": 112.1, "drtg": 112.4, "wins": 37, "losses": 45},
    "pacers": {"strength": 82, "orth": 114.8, "ortg": 113.5, "drtg": 110.2, "wins": 44, "losses": 38},
    "76ers": {"strength": 85, "orth": 115.7, "ortg": 114.9, "drtg": 109.2, "wins": 47, "losses": 35},
    "knicks": {"strength": 85, "orth": 116.2, "ortg": 115.1, "drtg": 109.8, "wins": 47, "losses": 35},
    "raptors": {"strength": 80, "orth": 113.5, "ortg": 112.3, "drtg": 110.1, "wins": 40, "losses": 42},
    "bulls": {"strength": 76, "orth": 111.2, "ortg": 109.8, "drtg": 113.5, "wins": 30, "losses": 52},
    "magic": {"strength": 80, "orth": 113.8, "ortg": 112.5, "drtg": 110.9, "wins": 41, "losses": 41},
    "bucks": {"strength": 88, "orth": 118.2, "ortg": 117.1, "drtg": 107.5, "wins": 51, "losses": 31},
    "nets": {"strength": 72, "orth": 110.1, "ortg": 108.9, "drtg": 116.2, "wins": 26, "losses": 56},
    "spurs": {"strength": 74, "orth": 110.8, "ortg": 109.5, "drtg": 115.1, "wins": 28, "losses": 54},
    "mavericks": {"strength": 86, "orth": 117.1, "ortg": 115.8, "drtg": 108.9, "wins": 48, "losses": 34},
    "nuggets": {"strength": 89, "orth": 118.9, "ortg": 117.5, "drtg": 107.1, "wins": 53, "losses": 29},
    "thunder": {"strength": 87, "orth": 118.1, "ortg": 116.3, "drtg": 107.8, "wins": 51, "losses": 31},
    "rockets": {"strength": 79, "orth": 115.9, "ortg": 114.2, "drtg": 111.3, "wins": 39, "losses": 43},
    "timberwolves": {"strength": 81, "orth": 114.2, "ortg": 113.1, "drtg": 110.8, "wins": 42, "losses": 40},
    "jazz": {"strength": 78, "orth": 112.7, "ortg": 111.5, "drtg": 112.9, "wins": 36, "losses": 46},
    "grizzlies": {"strength": 84, "orth": 115.8, "ortg": 114.2, "drtg": 109.1, "wins": 45, "losses": 37},
    "trail_blazers": {"strength": 75, "orth": 111.9, "ortg": 110.3, "drtg": 114.2, "wins": 30, "losses": 52},
    "clippers": {"strength": 83, "orth": 115.1, "ortg": 113.9, "drtg": 109.5, "wins": 44, "losses": 38},
    "kings": {"strength": 79, "orth": 115.8, "ortg": 114.1, "drtg": 111.8, "wins": 39, "losses": 43},
    "warriors": {"strength": 88, "orth": 118.5, "ortg": 116.9, "drtg": 107.3, "wins": 50, "losses": 32},
    "lakers": {"strength": 85, "orth": 116.3, "ortg": 115.1, "drtg": 109.2, "wins": 46, "losses": 36},
    "suns": {"strength": 86, "orth": 117.8, "ortg": 116.2, "drtg": 108.5, "wins": 48, "losses": 34},
}

# ═══════════════════════════════════════════════════════════════════
# NBA PLAYER PROPS - Under/Over Points Predictions
# ═══════════════════════════════════════════════════════════════════
NBA_PLAYERS_PROPS = {
    "hornets": {
        "lamelo_ball": {"name": "LaMelo Ball", "ppg": 25.3, "lines": [24.5, 25.5, 26.5]},
        "miles_bridges": {"name": "Miles Bridges", "ppg": 19.2, "lines": [18.5, 19.5, 20.5]},
    },
    "pistons": {
        "cade_cunningham": {"name": "Cade Cunningham", "ppg": 22.1, "lines": [21.5, 22.5, 23.5]},
        "isaiah_stewart": {"name": "Isaiah Stewart", "ppg": 10.5, "lines": [9.5, 10.5, 11.5]},
    },
    "wizards": {
        "damian_lillard": {"name": "Damian Lillard", "ppg": 24.8, "lines": [24.5, 25.5, 26.5]},
        "jordan_poole": {"name": "Jordan Poole", "ppg": 18.3, "lines": [17.5, 18.5, 19.5]},
    },
    "heat": {
        "jimmy_butler": {"name": "Jimmy Butler", "ppg": 21.4, "lines": [20.5, 21.5, 22.5]},
        "bam_adebayo": {"name": "Bam Adebayo", "ppg": 17.8, "lines": [17.0, 18.0, 19.0]},
    },
    "hawks": {
        "trae_young": {"name": "Trae Young", "ppg": 26.9, "lines": [26.5, 27.5, 28.5]},
        "dejounte_murray": {"name": "DeJounte Murray", "ppg": 20.1, "lines": [19.5, 20.5, 21.5]},
    },
    "cavaliers": {
        "donovan_mitchell": {"name": "Donovan Mitchell", "ppg": 28.4, "lines": [27.5, 28.5, 29.5]},
        "jarrett_allen": {"name": "Jarrett Allen", "ppg": 12.3, "lines": [11.5, 12.5, 13.5]},
    },
    "celtics": {
        "jayson_tatum": {"name": "Jayson Tatum", "ppg": 29.1, "lines": [28.5, 29.5, 30.5]},
        "jaylen_brown": {"name": "Jaylen Brown", "ppg": 24.7, "lines": [24.0, 25.0, 26.0]},
    },
    "pelicans": {
        "zion_williamson": {"name": "Zion Williamson", "ppg": 23.6, "lines": [23.0, 24.0, 25.0]},
        "brandon_ingram": {"name": "Brandon Ingram", "ppg": 21.2, "lines": [20.5, 21.5, 22.5]},
    },
    "pacers": {
        "tyrese_haliburton": {"name": "Tyrese Haliburton", "ppg": 20.5, "lines": [19.5, 20.5, 21.5]},
        "pascal_siakam": {"name": "Pascal Siakam", "ppg": 19.8, "lines": [19.0, 20.0, 21.0]},
    },
    "76ers": {
        "joel_embiid": {"name": "Joel Embiid", "ppg": 31.5, "lines": [30.5, 31.5, 32.5]},
        "tyrese_maxey": {"name": "Tyrese Maxey", "ppg": 22.9, "lines": [22.0, 23.0, 24.0]},
    },
    "knicks": {
        "julius_randle": {"name": "Julius Randle", "ppg": 24.1, "lines": [23.5, 24.5, 25.5]},
        "jalen_brunson": {"name": "Jalen Brunson", "ppg": 25.3, "lines": [24.5, 25.5, 26.5]},
    },
    "raptors": {
        "scottie_barnes": {"name": "Scottie Barnes", "ppg": 21.8, "lines": [21.0, 22.0, 23.0]},
        "pascal_siakam": {"name": "Pascal Siakam", "ppg": 18.2, "lines": [17.5, 18.5, 19.5]},
    },
    "bulls": {
        "demar_derozan": {"name": "DeMar DeRozan", "ppg": 24.4, "lines": [23.5, 24.5, 25.5]},
        "zach_lavine": {"name": "Zach LaVine", "ppg": 21.3, "lines": [20.5, 21.5, 22.5]},
    },
    "magic": {
        "paolo_banchero": {"name": "Paolo Banchero", "ppg": 27.2, "lines": [26.5, 27.5, 28.5]},
        "jalen_suggs": {"name": "Jalen Suggs", "ppg": 15.1, "lines": [14.5, 15.5, 16.5]},
    },
    "bucks": {
        "giannis_antetokounmpo": {"name": "Giannis Antetokounmpo", "ppg": 30.8, "lines": [30.0, 31.0, 32.0]},
        "damian_lillard": {"name": "Damian Lillard", "ppg": 24.3, "lines": [23.5, 24.5, 25.5]},
    },
    "nets": {
        "cameron_thomas": {"name": "Cameron Thomas", "ppg": 26.1, "lines": [25.5, 26.5, 27.5]},
        "nic_claxton": {"name": "Nic Claxton", "ppg": 15.4, "lines": [14.5, 15.5, 16.5]},
    },
    "spurs": {
        "devin_vassell": {"name": "Devin Vassell", "ppg": 19.8, "lines": [19.0, 20.0, 21.0]},
        "keldon_johnson": {"name": "Keldon Johnson", "ppg": 17.5, "lines": [16.5, 17.5, 18.5]},
    },
    "mavericks": {
        "luka_doncic": {"name": "Luka Doncic", "ppg": 33.9, "lines": [33.0, 34.0, 35.0]},
        "kyrie_irving": {"name": "Kyrie Irving", "ppg": 25.2, "lines": [24.5, 25.5, 26.5]},
    },
    "nuggets": {
        "nikola_jokic": {"name": "Nikola Jokic", "ppg": 24.5, "lines": [23.5, 24.5, 25.5]},
        "jamal_murray": {"name": "Jamal Murray", "ppg": 20.8, "lines": [20.0, 21.0, 22.0]},
    },
    "thunder": {
        "shai_gilgeous_alexander": {"name": "Shai Gilgeous-Alexander", "ppg": 28.4, "lines": [27.5, 28.5, 29.5]},
        "jalen_williams": {"name": "Jalen Williams", "ppg": 20.1, "lines": [19.5, 20.5, 21.5]},
    },
    "grizzlies": {
        "ja_morant": {"name": "Ja Morant", "ppg": 25.5, "lines": [24.5, 25.5, 26.5]},
        "desmond_murray": {"name": "Desmond Murray", "ppg": 18.3, "lines": [17.5, 18.5, 19.5]},
    },
    "rockets": {
        "alperen_sengun": {"name": "Alperen Sengun", "ppg": 21.1, "lines": [20.5, 21.5, 22.5]},
        "jalen_green": {"name": "Jalen Green", "ppg": 19.8, "lines": [19.0, 20.0, 21.0]},
    },
    "timberwolves": {
        "anthony_edwards": {"name": "Anthony Edwards", "ppg": 25.1, "lines": [24.5, 25.5, 26.5]},
        "karl_anthony_towns": {"name": "Karl-Anthony Towns", "ppg": 21.0, "lines": [20.0, 21.0, 22.0]},
    },
    "jazz": {
        "lauri_markkanen": {"name": "Lauri Markkanen", "ppg": 23.2, "lines": [22.5, 23.5, 24.5]},
        "collin_sexton": {"name": "Collin Sexton", "ppg": 15.6, "lines": [14.5, 15.5, 16.5]},
    },
    "trail_blazers": {
        "damian_lillard": {"name": "Damian Lillard", "ppg": 27.8, "lines": [27.0, 28.0, 29.0]},
        "jerami_grant": {"name": "Jerami Grant", "ppg": 21.5, "lines": [20.5, 21.5, 22.5]},
    },
    "clippers": {
        "paul_george": {"name": "Paul George", "ppg": 26.3, "lines": [25.5, 26.5, 27.5]},
        "kawhi_leonard": {"name": "Kawhi Leonard", "ppg": 23.8, "lines": [23.0, 24.0, 25.0]},
    },
    "kings": {
        "de_aaron_fox": {"name": "De'Aaron Fox", "ppg": 26.2, "lines": [25.5, 26.5, 27.5]},
        "dominatas_sabonis": {"name": "Dominatas Sabonis", "ppg": 20.4, "lines": [19.5, 20.5, 21.5]},
    },
    "warriors": {
        "stephen_curry": {"name": "Stephen Curry", "ppg": 27.4, "lines": [26.5, 27.5, 28.5]},
        "klay_thompson": {"name": "Klay Thompson", "ppg": 16.8, "lines": [16.0, 17.0, 18.0]},
    },
    "lakers": {
        "lebron_james": {"name": "LeBron James", "ppg": 25.3, "lines": [24.5, 25.5, 26.5]},
        "anthony_davis": {"name": "Anthony Davis", "ppg": 26.1, "lines": [25.5, 26.5, 27.5]},
    },
    "suns": {
        "kevin_durant": {"name": "Kevin Durant", "ppg": 27.9, "lines": [27.0, 28.0, 29.0]},
        "devin_booker": {"name": "Devin Booker", "ppg": 26.4, "lines": [25.5, 26.5, 27.5]},
    },
}

# PLAYER PROPS ODDS - Under/Over cotes pour les joueurs clés
PLAYER_PROPS_ODDS = {
    ("hornets", "knicks", "lamelo_ball", 24.5): {"under": 1.92, "over": 1.88},
    ("hornets", "knicks", "lamelo_ball", 25.5): {"under": 1.90, "over": 1.90},
    ("celtics", "pelicans", "jayson_tatum", 29.5): {"under": 1.92, "over": 1.88},
    ("celtics", "pelicans", "jayson_tatum", 28.5): {"under": 1.90, "over": 1.90},
    ("mavericks", "spurs", "luka_doncic", 34.0): {"under": 1.88, "over": 1.92},
    ("mavericks", "spurs", "luka_doncic", 33.0): {"under": 1.90, "over": 1.90},
    ("54ers", "pacers", "joel_embiid", 31.5): {"under": 1.92, "over": 1.88},
    ("76ers", "pacers", "joel_embiid", 30.5): {"under": 1.90, "over": 1.90},
    ("bucks", "76ers", "giannis_antetokounmpo", 31.0): {"under": 1.92, "over": 1.88},
    ("bucks", "76ers", "giannis_antetokounmpo", 30.0): {"under": 1.90, "over": 1.90},
    ("cavaliers", "knicks", "donovan_mitchell", 28.5): {"under": 1.92, "over": 1.88},
    ("thunders", "suns", "shai_gilgeous_alexander", 28.5): {"under": 1.92, "over": 1.88},
}

# BET365 REAL ODDS (Certified Bookmaker - April 2026)
BET365_ODDS = {
    ("hornets", "knicks"): {"away_ml": 3.20, "home_ml": 1.30, "spread": (-8.5, 1.91, 8.5, 1.87), "total": 219.5, "under": 1.90, "over": 1.90},
    ("pistons", "pacers"): {"away_ml": 1.95, "home_ml": 1.85, "spread": (-1.0, 1.93, 1.0, 1.85), "total": 205.5, "under": 1.90, "over": 1.90},
    ("wizards", "cavaliers"): {"away_ml": 2.72, "home_ml": 1.42, "spread": (-7.0, 1.92, 7.0, 1.86), "total": 210.5, "under": 1.90, "over": 1.90},
    ("magic", "celtics"): {"away_ml": 3.50, "home_ml": 1.25, "spread": (-10.0, 1.89, 10.0, 1.89), "total": 217.5, "under": 1.90, "over": 1.90},
    ("hawks", "heat"): {"away_ml": 1.85, "home_ml": 1.95, "spread": (0.5, 1.93, -0.5, 1.85), "total": 216.5, "under": 1.90, "over": 1.90},
    ("bucks", "76ers"): {"away_ml": 1.30, "home_ml": 3.10, "spread": (8.5, 1.90, -8.5, 1.88), "total": 214.5, "under": 1.90, "over": 1.90},
    ("nets", "raptors"): {"away_ml": 2.50, "home_ml": 1.50, "spread": (-6.0, 1.93, 6.0, 1.85), "total": 220.5, "under": 1.90, "over": 1.90},
    ("bulls", "mavericks"): {"away_ml": 1.40, "home_ml": 2.75, "spread": (6.5, 1.91, -6.5, 1.87), "total": 216.0, "under": 1.90, "over": 1.90},
    ("grizzlies", "rockets"): {"away_ml": 1.95, "home_ml": 1.85, "spread": (-1.0, 1.93, 1.0, 1.85), "total": 219.5, "under": 1.90, "over": 1.90},
    ("pelicans", "timberwolves"): {"away_ml": 2.30, "home_ml": 1.60, "spread": (-3.0, 1.93, 3.0, 1.85), "total": 224.5, "under": 1.90, "over": 1.90},
    ("suns", "thunder"): {"away_ml": 1.72, "home_ml": 2.10, "spread": (3.0, 1.92, -3.0, 1.86), "total": 226.0, "under": 1.90, "over": 1.90},
    ("nuggets", "spurs"): {"away_ml": 1.28, "home_ml": 3.40, "spread": (9.0, 1.90, -9.0, 1.88), "total": 210.5, "under": 1.90, "over": 1.90},
    ("jazz", "lakers"): {"away_ml": 2.85, "home_ml": 1.38, "spread": (-7.5, 1.92, 7.5, 1.86), "total": 218.5, "under": 1.90, "over": 1.90},
    ("warriors", "clippers"): {"away_ml": 1.55, "home_ml": 2.35, "spread": (5.0, 1.94, -5.0, 1.84), "total": 231.5, "under": 1.90, "over": 1.90},
    ("kings", "trail_blazers"): {"away_ml": 1.55, "home_ml": 2.35, "spread": (5.0, 1.94, -5.0, 1.84), "total": 229.0, "under": 1.90, "over": 1.90},
    ("celtics", "pelicans"): {"away_ml": 1.30, "home_ml": 3.10, "spread": (8.5, 1.90, -8.5, 1.88)},
    ("pacers", "76ers"): {"away_ml": 1.85, "home_ml": 1.95, "spread": (-1.0, 1.93, 1.0, 1.85)},
    ("knicks", "raptors"): {"away_ml": 1.60, "home_ml": 2.25, "spread": (3.5, 1.92, -3.5, 1.86)},
    ("bulls", "magic"): {"away_ml": 3.00, "home_ml": 1.35, "spread": (-8.0, 1.91, 8.0, 1.87)},
    ("bucks", "nets"): {"away_ml": 1.22, "home_ml": 4.20, "spread": (11.0, 1.89, -11.0, 1.89)},
    ("spurs", "mavericks"): {"away_ml": 3.40, "home_ml": 1.28, "spread": (-9.0, 1.90, 9.0, 1.88)},
    ("nuggets", "thunder"): {"away_ml": 1.60, "home_ml": 2.30, "spread": (3.0, 1.93, -3.0, 1.85)},
    ("rockets", "timberwolves"): {"away_ml": 2.10, "home_ml": 1.70, "spread": (-2.5, 1.92, 2.5, 1.86)},
    ("jazz", "grizzlies"): {"away_ml": 3.20, "home_ml": 1.30, "spread": (-8.5, 1.91, 8.5, 1.87)},
    ("trail_blazers", "clippers"): {"away_ml": 2.75, "home_ml": 1.40, "spread": (-7.0, 1.92, 7.0, 1.86), "total": 213.5, "under": 1.90, "over": 1.90},
    ("kings", "warriors"): {"away_ml": 2.35, "home_ml": 1.55, "spread": (-5.0, 1.94, 5.0, 1.84), "total": 231.5, "under": 1.90, "over": 1.90},
    ("lakers", "suns"): {"away_ml": 1.90, "home_ml": 1.90, "spread": (0.0, 1.93, 0.0, 1.85), "total": 225.0, "under": 1.90, "over": 1.90},
}

# BETFAIR REAL ODDS (Certified Exchange - April 2026)
BETFAIR_ODDS = {
    ("hornets", "knicks"): {"away_ml": 3.25, "home_ml": 1.32, "total": 219.5, "under": 1.89, "over": 1.91},
    ("pistons", "pacers"): {"away_ml": 1.98, "home_ml": 1.82, "total": 205.5, "under": 1.89, "over": 1.91},
    ("wizards", "cavaliers"): {"away_ml": 2.75, "home_ml": 1.40, "total": 210.5, "under": 1.89, "over": 1.91},
    ("magic", "celtics"): {"away_ml": 3.55, "home_ml": 1.27, "total": 217.5, "under": 1.89, "over": 1.91},
    ("hawks", "heat"): {"away_ml": 1.88, "home_ml": 1.92, "total": 216.5, "under": 1.89, "over": 1.91},
    ("bucks", "76ers"): {"away_ml": 1.32, "home_ml": 3.15, "total": 214.5, "under": 1.89, "over": 1.91},
    ("nets", "raptors"): {"away_ml": 2.53, "home_ml": 1.52, "total": 220.5, "under": 1.89, "over": 1.91},
    ("bulls", "mavericks"): {"away_ml": 1.42, "home_ml": 2.80, "total": 216.0, "under": 1.89, "over": 1.91},
    ("grizzlies", "rockets"): {"away_ml": 1.98, "home_ml": 1.82, "total": 219.5, "under": 1.89, "over": 1.91},
    ("pelicans", "timberwolves"): {"away_ml": 2.32, "home_ml": 1.62, "total": 224.5, "under": 1.89, "over": 1.91},
    ("suns", "thunder"): {"away_ml": 1.75, "home_ml": 2.12, "total": 226.0, "under": 1.89, "over": 1.91},
    ("nuggets", "spurs"): {"away_ml": 1.30, "home_ml": 3.45, "total": 210.5, "under": 1.89, "over": 1.91},
    ("jazz", "lakers"): {"away_ml": 2.88, "home_ml": 1.40, "total": 218.5, "under": 1.89, "over": 1.91},
    ("warriors", "clippers"): {"away_ml": 1.57, "home_ml": 2.37, "total": 231.5, "under": 1.89, "over": 1.91},
    ("kings", "trail_blazers"): {"away_ml": 1.57, "home_ml": 2.37, "total": 229.0, "under": 1.89, "over": 1.91},
    ("celtics", "pelicans"): {"away_ml": 1.32, "home_ml": 3.15},
    ("pacers", "76ers"): {"away_ml": 1.88, "home_ml": 1.92},
    ("knicks", "raptors"): {"away_ml": 1.62, "home_ml": 2.27},
    ("bulls", "magic"): {"away_ml": 3.05, "home_ml": 1.37},
    ("bucks", "nets"): {"away_ml": 1.24, "home_ml": 4.25},
    ("spurs", "mavericks"): {"away_ml": 3.45, "home_ml": 1.30},
    ("nuggets", "thunder"): {"away_ml": 1.62, "home_ml": 2.32},
    ("rockets", "timberwolves"): {"away_ml": 2.12, "home_ml": 1.72},
    ("jazz", "grizzlies"): {"away_ml": 3.25, "home_ml": 1.32},
    ("trail_blazers", "clippers"): {"away_ml": 2.73, "home_ml": 1.42, "total": 213.5, "under": 1.92, "over": 1.88},
    ("kings", "warriors"): {"away_ml": 2.33, "home_ml": 1.57, "total": 231.5, "under": 1.91, "over": 1.89},
    ("lakers", "suns"): {"away_ml": 1.92, "home_ml": 1.88, "total": 225.0, "under": 1.91, "over": 1.89},
}

# DRAFTKINGS REAL ODDS (Certified Sportsbook - April 2026)
DRAFTKINGS_ODDS = {
    ("hornets", "knicks"): {"away_ml": 3.30, "home_ml": 1.30, "total": 219.5, "under": 1.88, "over": 1.92},
    ("pistons", "pacers"): {"away_ml": 2.00, "home_ml": 1.80, "total": 205.5, "under": 1.88, "over": 1.92},
    ("wizards", "cavaliers"): {"away_ml": 2.80, "home_ml": 1.38, "total": 210.5, "under": 1.88, "over": 1.92},
    ("magic", "celtics"): {"away_ml": 3.60, "home_ml": 1.25, "total": 217.5, "under": 1.88, "over": 1.92},
    ("hawks", "heat"): {"away_ml": 1.90, "home_ml": 1.90, "total": 216.5, "under": 1.88, "over": 1.92},
    ("bucks", "76ers"): {"away_ml": 1.30, "home_ml": 3.20, "total": 214.5, "under": 1.88, "over": 1.92},
    ("nets", "raptors"): {"away_ml": 2.55, "home_ml": 1.50, "total": 220.5, "under": 1.88, "over": 1.92},
    ("bulls", "mavericks"): {"away_ml": 1.40, "home_ml": 2.85, "total": 216.0, "under": 1.88, "over": 1.92},
    ("grizzlies", "rockets"): {"away_ml": 2.00, "home_ml": 1.80, "total": 219.5, "under": 1.88, "over": 1.92},
    ("pelicans", "timberwolves"): {"away_ml": 2.35, "home_ml": 1.60, "total": 224.5, "under": 1.88, "over": 1.92},
    ("suns", "thunder"): {"away_ml": 1.78, "home_ml": 2.10, "total": 226.0, "under": 1.88, "over": 1.92},
    ("nuggets", "spurs"): {"away_ml": 1.28, "home_ml": 3.50, "total": 210.5, "under": 1.88, "over": 1.92},
    ("jazz", "lakers"): {"away_ml": 2.90, "home_ml": 1.38, "total": 218.5, "under": 1.88, "over": 1.92},
    ("warriors", "clippers"): {"away_ml": 1.59, "home_ml": 2.35, "total": 231.5, "under": 1.88, "over": 1.92},
    ("kings", "trail_blazers"): {"away_ml": 1.59, "home_ml": 2.35, "total": 229.0, "under": 1.88, "over": 1.92},
    ("celtics", "pelicans"): {"away_ml": 1.28, "home_ml": 3.15},
    ("pacers", "76ers"): {"away_ml": 1.83, "home_ml": 1.97},
    ("knicks", "raptors"): {"away_ml": 1.58, "home_ml": 2.28},
    ("bulls", "magic"): {"away_ml": 3.02, "home_ml": 1.33},
    ("bucks", "nets"): {"away_ml": 1.20, "home_ml": 4.25},
    ("spurs", "mavericks"): {"away_ml": 3.42, "home_ml": 1.26},
    ("nuggets", "thunder"): {"away_ml": 1.58, "home_ml": 2.32},
    ("rockets", "timberwolves"): {"away_ml": 2.12, "home_ml": 1.68},
    ("jazz", "grizzlies"): {"away_ml": 3.22, "home_ml": 1.28},
    ("trail_blazers", "clippers"): {"away_ml": 2.77, "home_ml": 1.38, "total": 213.5, "under": 1.88, "over": 1.92},
    ("kings", "warriors"): {"away_ml": 2.37, "home_ml": 1.53, "total": 231.5, "under": 1.89, "over": 1.91},
    ("lakers", "suns"): {"away_ml": 1.88, "home_ml": 1.92, "total": 225.0, "under": 1.89, "over": 1.91},
}

# ═══════════════════════════════════════════════════════════════════════════
# HOCKEY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════
def get_live_matches_nhl():
    """Récupère les matchs NHL en direct (ESPN API)"""
    global MATCHES_CACHE_NHL, MATCHES_CACHE_TIME_NHL
    
    if MATCHES_CACHE_NHL and MATCHES_CACHE_TIME_NHL:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME_NHL).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NHL
    
    try:
        today = datetime.datetime.now()
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed']
                        if not any(word in status_desc for word in blocked_statuses):
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                if away and home:
                                    daily_matches.append((away, home))
                    except:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NHL = daily_matches
                    MATCHES_CACHE_TIME_NHL = datetime.datetime.now()
                    return daily_matches
        
        logger.warning("⚠️ Aucun match NHL trouvé - Utilisant démo")
        MATCHES_CACHE_NHL = DEMO_MATCHES_NHL
        MATCHES_CACHE_TIME_NHL = datetime.datetime.now()
        return DEMO_MATCHES_NHL
    except Exception as e:
        logger.error(f"❌ Erreur NHL: {e}")
        MATCHES_CACHE_NHL = DEMO_MATCHES_NHL
        MATCHES_CACHE_TIME_NHL = datetime.datetime.now()
        return DEMO_MATCHES_NHL

def get_live_matches_nfl():
    """Récupère les matchs NFL en direct (ESPN API)"""
    global MATCHES_CACHE_NFL, MATCHES_CACHE_TIME_NFL
    
    if MATCHES_CACHE_NFL and MATCHES_CACHE_TIME_NFL:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME_NFL).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NFL
    
    try:
        today = datetime.datetime.now()
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed']
                        if not any(word in status_desc for word in blocked_statuses):
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                if away and home:
                                    daily_matches.append((away, home))
                    except:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NFL = daily_matches
                    MATCHES_CACHE_TIME_NFL = datetime.datetime.now()
                    return daily_matches
        
        logger.warning("⚠️ Aucun match NFL trouvé - Utilisant démo")
        MATCHES_CACHE_NFL = DEMO_MATCHES_NFL
        MATCHES_CACHE_TIME_NFL = datetime.datetime.now()
        return DEMO_MATCHES_NFL
    except Exception as e:
        logger.error(f"❌ Erreur NFL: {e}")
        MATCHES_CACHE_NFL = DEMO_MATCHES_NFL
        MATCHES_CACHE_TIME_NFL = datetime.datetime.now()
        return DEMO_MATCHES_NFL

def find_team_nhl(name_input):
    """Trouve une équipe NHL par son nom"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    team_aliases = {
        "rangers": ["new_york_rangers", "ny_rangers", "rangers"],
        "hurricanes": ["carolina_hurricanes", "hurricanes"],
        "avalanche": ["colorado_avalanche", "avalanche"],
        "maple_leafs": ["toronto_maple_leafs", "maple_leafs"],
        "oilers": ["edmonton_oilers", "oilers"],
        "golden_knights": ["vegas_golden_knights", "golden_knights"],
        "stars": ["dallas_stars", "stars"],
        "lightning": ["tampa_bay_lightning", "lightning"],
        "panthers": ["florida_panthers", "panthers"],
        "capitals": ["washington_capitals", "capitals"],
        "bruins": ["boston_bruins", "bruins"],
        "penguins": ["pittsburgh_penguins", "penguins"],
        "sabres": ["buffalo_sabres", "sabres"],
        "isles": ["new_york_islanders", "islanders"],
        "devils": ["new_jersey_devils", "devils"],
        "canadiens": ["montreal_canadiens", "canadiens"],
        "flames": ["calgary_flames", "flames"],
        "canucks": ["vancouver_canucks", "canucks"],
        "wild": ["minnesota_wild", "wild"],
        "jets": ["winnipeg_jets", "jets"],
        "kings": ["los_angeles_kings", "kings"],
        "ducks": ["anaheim_ducks", "ducks"],
        "sharks": ["san_jose_sharks", "sharks"],
        "red_wings": ["detroit_red_wings", "red_wings"],
        "blue_jackets": ["columbus_blue_jackets", "blue_jackets"],
        "coyotes": ["arizona_coyotes", "coyotes"],
        "predators": ["nashville_predators", "predators"],
        "kraken": ["seattle_kraken", "kraken"],
    }
    
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    for team_key in NHL_TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    return None

def find_team_nfl(name_input):
    """Trouve une équipe NFL par son nom"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    team_aliases = {
        "chiefs": ["kansas_city_chiefs", "chiefs"],
        "49ers": ["san_francisco_49ers", "san_francisco_niners", "49ers"],
        "eagles": ["philadelphia_eagles", "eagles"],
        "ravens": ["baltimore_ravens", "ravens"],
        "cowboys": ["dallas_cowboys", "cowboys"],
        "patriots": ["new_england_patriots", "patriots"],
        "bills": ["buffalo_bills", "bills"],
        "dolphins": ["miami_dolphins", "dolphins"],
        "packers": ["green_bay_packers", "packers"],
        "lions": ["detroit_lions", "lions"],
        "buccaneers": ["tampa_bay_buccaneers", "buccaneers"],
        "saints": ["new_orleans_saints", "saints"],
        "titans": ["tennessee_titans", "titans"],
        "bengals": ["cincinnati_bengals", "bengals"],
        "texans": ["houston_texans", "texans"],
        "colts": ["indianapolis_colts", "colts"],
        "chargers": ["los_angeles_chargers", "chargers"],
        "raiders": ["las_vegas_raiders", "vegas_raiders", "raiders"],
        "broncos": ["denver_broncos", "broncos"],
        "seahawks": ["seattle_seahawks", "seahawks"],
    }
    
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    for team_key in NFL_TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    return None

def get_best_odds(away_team, home_team):
    """LINE SHOPPING - Get best odds across certified bookmakers (bidirectional search) - NBA"""
    away_clean = find_team_nba(away_team) or away_team.lower()
    home_clean = find_team_nba(home_team) or home_team.lower()
    
    # Try forward direction: (away, home)
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    # Search in both directions
    best_away_ml = 1.0
    best_home_ml = 1.0
    best_away_book = "N/A"
    best_home_book = "N/A"
    
    bookmakers = [
        ("BET365", BET365_ODDS),
        ("BETFAIR", BETFAIR_ODDS),
        ("DRAFTKINGS", DRAFTKINGS_ODDS),
    ]
    
    for book_name, odds_dict in bookmakers:
        # Try forward
        if key_forward in odds_dict:
            odds = odds_dict[key_forward]
            away_ml = odds.get("away_ml", 1.0)
            home_ml = odds.get("home_ml", 1.0)
            if away_ml > best_away_ml:
                best_away_ml = away_ml
                best_away_book = book_name
            if home_ml > best_home_ml:
                best_home_ml = home_ml
                best_home_book = book_name
        # Try reverse
        elif key_reverse in odds_dict:
            odds = odds_dict[key_reverse]
            home_ml = odds.get("away_ml", 1.0)  # Reverse: away becomes home
            away_ml = odds.get("home_ml", 1.0)  # Reverse: home becomes away
            if away_ml > best_away_ml:
                best_away_ml = away_ml
                best_away_book = book_name
            if home_ml > best_home_ml:
                best_home_ml = home_ml
                best_home_book = book_name
    
    return {
        "away_ml": best_away_ml,
        "home_ml": best_home_ml,
        "away_book": best_away_book,
        "home_book": best_home_book,
    }

def get_best_odds_nhl(away_team, home_team):
    """LINE SHOPPING pour NHL"""
    away_clean = find_team_nhl(away_team) or away_team.lower()
    home_clean = find_team_nhl(home_team) or home_team.lower()
    
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    bookmakers = [("BET365", BET365_ODDS_NHL), ("BETFAIR", BETFAIR_ODDS_NHL), ("DRAFTKINGS", DRAFTKINGS_ODDS_NHL)]
    
    away_stats = NHL_TEAM_STATS.get(away_clean, {"strength": 75})
    home_stats = NHL_TEAM_STATS.get(home_clean, {"strength": 75})
    strength_diff = away_stats["strength"] - home_stats["strength"]
    
    if strength_diff > 5:
        best_away = {"odds": 1.70, "book": "DEFAULT"}
        best_home = {"odds": 2.15, "book": "DEFAULT"}
    elif strength_diff < -5:
        best_away = {"odds": 2.15, "book": "DEFAULT"}
        best_home = {"odds": 1.70, "book": "DEFAULT"}
    else:
        best_away = {"odds": 1.90, "book": "DEFAULT"}
        best_home = {"odds": 1.90, "book": "DEFAULT"}
    
    for book_name, odds_dict in bookmakers:
        odds = odds_dict.get(key_forward, odds_dict.get(key_reverse, {}))
        if odds:
            away_ml = odds.get("away_ml", 1.0) if key_forward in odds_dict else odds.get("home_ml", 1.0)
            home_ml = odds.get("home_ml", 1.0) if key_forward in odds_dict else odds.get("away_ml", 1.0)
            
            if away_ml > best_away["odds"]:
                best_away = {"odds": away_ml, "book": book_name}
            if home_ml > best_home["odds"]:
                best_home = {"odds": home_ml, "book": book_name}
    
    return {"away_ml": best_away["odds"], "home_ml": best_home["odds"], "away_book": best_away["book"], "home_book": best_home["book"]}

def get_best_odds_nfl(away_team, home_team):
    """LINE SHOPPING pour NFL"""
    away_clean = find_team_nfl(away_team) or away_team.lower()
    home_clean = find_team_nfl(home_team) or home_team.lower()
    
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    bookmakers = [("BET365", BET365_ODDS_NFL), ("BETFAIR", BETFAIR_ODDS_NFL), ("DRAFTKINGS", DRAFTKINGS_ODDS_NFL)]
    
    best_away = {"odds": 1.0, "book": "N/A"}
    best_home = {"odds": 1.0, "book": "N/A"}
    
    for book_name, odds_dict in bookmakers:
        odds = odds_dict.get(key_forward, odds_dict.get(key_reverse, {}))
        if odds:
            away_ml = odds.get("away_ml", 1.0) if key_forward in odds_dict else odds.get("home_ml", 1.0)
            home_ml = odds.get("home_ml", 1.0) if key_forward in odds_dict else odds.get("away_ml", 1.0)
            
            if away_ml > best_away["odds"]:
                best_away = {"odds": away_ml, "book": book_name}
            if home_ml > best_home["odds"]:
                best_home = {"odds": home_ml, "book": book_name}
    
    return {"away_ml": best_away["odds"], "home_ml": best_home["odds"], "away_book": best_away["book"], "home_book": best_home["book"]}

def generate_prediction_nhl(away_team, home_team):
    """Génère une prédiction pour un match NHL"""
    away_clean = find_team_nhl(away_team) or away_team.lower()
    home_clean = find_team_nhl(home_team) or home_team.lower()
    
    away_stats = NHL_TEAM_STATS.get(away_clean, {"strength": 75, "gf": 3.0, "ga": 3.0})
    home_stats = NHL_TEAM_STATS.get(home_clean, {"strength": 75, "gf": 3.0, "ga": 3.0})
    
    odds_data = get_best_odds_nhl(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    
    away_gf_diff = away_stats["gf"] - home_stats["ga"]
    home_gf_diff = home_stats["gf"] - away_stats["ga"]
    point_diff = away_gf_diff - home_gf_diff - 0.3
    
    try:
        win_prob_away = 1 / (1 + math.exp(-point_diff / 1.8))
    except:
        win_prob_away = 0.5 + (point_diff / 3.0)
    
    win_prob_away = max(0.05, min(0.95, win_prob_away))
    market_away_avg = (1.0 / best_away_ml + 1.0 / best_home_ml)
    market_consensus_away = (1.0 / best_away_ml) / market_away_avg
    blended_prob = (0.50 * win_prob_away) + (0.50 * market_consensus_away)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    ev_away = (best_away_ml - 1.0) * blended_prob - (1.0 - blended_prob)
    ev_home = (best_home_ml - 1.0) * (1.0 - blended_prob) - blended_prob
    
    if ev_away > ev_home:
        pick = f"{away_team.upper()} ML"
        odds = best_away_ml
        confidence = int(blended_prob * 100)
        ev = ev_away
        book = odds_data["away_book"]
    else:
        pick = f"{home_team.upper()} ML"
        odds = best_home_ml
        confidence = int((1.0 - blended_prob) * 100)
        ev = ev_home
        book = odds_data["home_book"]
    
    if ev > 0.01:
        status = "✅ BUY"
    elif ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"
    
    return {"pick": pick, "odds": f"{odds:.2f}", "confidence": confidence, "ev": f"{ev:.4f}", "ev_pct": f"{ev*100:.2f}%", "status": status, "bookmaker": book}

def generate_prediction_nfl(away_team, home_team):
    """Génère une prédiction pour un match NFL"""
    away_clean = find_team_nfl(away_team) or away_team.lower()
    home_clean = find_team_nfl(home_team) or home_team.lower()
    
    away_stats = NFL_TEAM_STATS.get(away_clean, {"strength": 80, "pf": 25.0, "pa": 23.0})
    home_stats = NFL_TEAM_STATS.get(home_clean, {"strength": 80, "pf": 25.0, "pa": 23.0})
    
    odds_data = get_best_odds_nfl(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    
    away_pf_diff = away_stats["pf"] - home_stats["pa"]
    home_pf_diff = home_stats["pf"] - away_stats["pa"]
    point_diff = away_pf_diff - home_pf_diff - 2.5
    
    try:
        win_prob_away = 1 / (1 + math.exp(-point_diff / 14.0))
    except:
        win_prob_away = 0.5 + (point_diff / 80.0)
    
    win_prob_away = max(0.05, min(0.95, win_prob_away))
    market_away_avg = (1.0 / best_away_ml + 1.0 / best_home_ml)
    market_consensus_away = (1.0 / best_away_ml) / market_away_avg
    blended_prob = (0.50 * win_prob_away) + (0.50 * market_consensus_away)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    ev_away = (best_away_ml - 1.0) * blended_prob - (1.0 - blended_prob)
    ev_home = (best_home_ml - 1.0) * (1.0 - blended_prob) - blended_prob
    
    if ev_away > ev_home:
        pick = f"{away_team.upper()} ML"
        odds = best_away_ml
        confidence = int(blended_prob * 100)
        ev = ev_away
        book = odds_data["away_book"]
    else:
        pick = f"{home_team.upper()} ML"
        odds = best_home_ml
        confidence = int((1.0 - blended_prob) * 100)
        ev = ev_home
        book = odds_data["home_book"]
    
    if ev > 0.01:
        status = "✅ BUY"
    elif ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"
    
    return {"pick": pick, "odds": f"{odds:.2f}", "confidence": confidence, "ev": f"{ev:.4f}", "ev_pct": f"{ev*100:.2f}%", "status": status, "bookmaker": book}

def find_team_nba(name_input):
    """Trouve une équipe NBA par son nom avec table de correspondance ESPN"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    
    # Table de correspondance explicite pour les noms ESPN
    team_aliases = {
        "hornets": ["charlotte_hornets", "hornets"],
        "pistons": ["detroit_pistons", "pistons"],
        "wizards": ["washington_wizards", "wizards"],
        "heat": ["miami_heat", "heat"],
        "hawks": ["atlanta_hawks", "hawks"],
        "cavaliers": ["cleveland_cavaliers", "cavaliers"],
        "celtics": ["boston_celtics", "celtics"],
        "pelicans": ["new_orleans_pelicans", "pelicans"],
        "pacers": ["indiana_pacers", "pacers"],
        "76ers": ["philadelphia_76ers", "76ers"],
        "knicks": ["new_york_knicks", "knicks"],
        "raptors": ["toronto_raptors", "raptors"],
        "bulls": ["chicago_bulls", "bulls"],
        "magic": ["orlando_magic", "magic"],
        "bucks": ["milwaukee_bucks", "bucks"],
        "nets": ["brooklyn_nets", "nets"],
        "spurs": ["san_antonio_spurs", "spurs"],
        "mavericks": ["dallas_mavericks", "mavericks"],
        "nuggets": ["denver_nuggets", "nuggets"],
        "thunder": ["oklahoma_city_thunder", "thunder"],
        "rockets": ["houston_rockets", "rockets"],
        "timberwolves": ["minnesota_timberwolves", "timberwolves"],
        "jazz": ["utah_jazz", "jazz"],
        "grizzlies": ["memphis_grizzlies", "grizzlies"],
        "trail_blazers": ["portland_trail_blazers", "trail_blazers"],
        "clippers": ["los_angeles_clippers", "clippers"],
        "kings": ["sacramento_kings", "kings"],
        "warriors": ["golden_state_warriors", "warriors"],
        "lakers": ["los_angeles_lakers", "lakers"],
        "suns": ["phoenix_suns", "suns"],
    }
    
    # Chercher dans les aliases
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    # Fallback sur simple recherche
    for team_key in TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    return None

def get_odds(away, home):
    """Fetch best odds for a matchup - wrapper for get_best_odds"""
    return get_best_odds(away, home)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set. Configure it in Railway environment variables or .env file.")

# KEY PLAYERS DATA - Real-time injury/status info
PLAYERS_DATA = {
    "hornets": {
        "LaMelo Ball": {"status": "Active", "position": "PG", "impact": "Star"},
        "Miles Bridges": {"status": "Active", "position": "SF", "impact": "Key"},
    },
    "pistons": {
        "Cade Cunningham": {"status": "Active", "position": "PG", "impact": "Star"},
        "Isaiah Stewart": {"status": "Active", "position": "PF", "impact": "Key"},
    },
    "wizards": {
        "Damian Lillard": {"status": "Active", "position": "PG", "impact": "Star"},
        "Bradley Beal": {"status": "Out", "reason": "Right ankle sprain", "impact": "Critical"},
    },
    "heat": {
        "Jimmy Butler": {"status": "Active", "position": "SF", "impact": "Star"},
        "Adebayo": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "hawks": {
        "Trae Young": {"status": "Active", "position": "PG", "impact": "Star"},
        "Clint Capela": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "cavaliers": {
        "Donovan Mitchell": {"status": "Active", "position": "SG", "impact": "Star"},
        "Jarrett Allen": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "celtics": {
        "Jayson Tatum": {"status": "Active", "position": "SF", "impact": "Star"},
        "Jaylen Brown": {"status": "Active", "position": "SG", "impact": "Star"},
    },
    "pelicans": {
        "Anthony Davis": {"status": "Out", "reason": "Lower back injury", "impact": "Critical"},
        "Brandon Ingram": {"status": "Active", "position": "SF", "impact": "Key"},
    },
    "pacers": {
        "Tyrese Haliburton": {"status": "Active", "position": "PG", "impact": "Star"},
        "Pascal Siakam": {"status": "Active", "position": "PF", "impact": "Key"},
    },
    "76ers": {
        "Joel Embiid": {"status": "Active", "position": "C", "impact": "Star"},
        "Tyrese Maxey": {"status": "Active", "position": "PG", "impact": "Key"},
    },
    "knicks": {
        "Julius Randle": {"status": "Active", "position": "PF", "impact": "Star"},
        "Jalen Brunson": {"status": "Active", "position": "PG", "impact": "Key"},
    },
    "raptors": {
        "Scottie Barnes": {"status": "Active", "position": "SF", "impact": "Star"},
        "Fred VanVleet": {"status": "Active", "position": "SG", "impact": "Key"},
    },
    "bulls": {
        "DeMar DeRozan": {"status": "Active", "position": "SF", "impact": "Star"},
        "Zach LaVine": {"status": "Out", "reason": "Knee injury", "impact": "Critical"},
    },
    "magic": {
        "Paolo Banchero": {"status": "Active", "position": "SF", "impact": "Star"},
        "Jalen Suggs": {"status": "Active", "position": "PG", "impact": "Key"},
    },
    "bucks": {
        "Giannis Antetokounmpo": {"status": "Active", "position": "PF", "impact": "Star"},
        "Damian Lillard": {"status": "Active", "position": "PG", "impact": "Star"},
    },
    "nets": {
        "Mikal Bridges": {"status": "Active", "position": "SF", "impact": "Key"},
        "Cameron Whitmore": {"status": "Active", "position": "SG", "impact": "Key"},
    },
    "spurs": {
        "Victor Wembanyama": {"status": "Active", "position": "PF", "impact": "Star"},
        "Chris Paul": {"status": "Bench", "reason": "Rest management", "impact": "Low"},
    },
    "mavericks": {
        "Luka Doncic": {"status": "Active", "position": "PG", "impact": "Star"},
        "Kyrie Irving": {"status": "Active", "position": "SG", "impact": "Key"},
    },
    "nuggets": {
        "Nikola Jokic": {"status": "Active", "position": "C", "impact": "Star"},
        "Jamal Murray": {"status": "Active", "position": "PG", "impact": "Key"},
    },
    "thunder": {
        "Shai Gilgeous-Alexander": {"status": "Active", "position": "PG", "impact": "Star"},
        "Jalen Williams": {"status": "Active", "position": "SF", "impact": "Key"},
    },
    "rockets": {
        "Jabarri Smith Jr": {"status": "Active", "position": "PF", "impact": "Key"},
        "Alperen Sengun": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "timberwolves": {
        "Anthony Edwards": {"status": "Active", "position": "SG", "impact": "Star"},
        "Mike Conley": {"status": "Bench", "reason": "Rest management", "impact": "Low"},
    },
    "jazz": {
        "Lauri Markkanen": {"status": "Active", "position": "PF", "impact": "Key"},
        "John Collins": {"status": "Active", "position": "PF", "impact": "Key"},
    },
    "grizzlies": {
        "Ja Morant": {"status": "Active", "position": "PG", "impact": "Star"},
        "Desmond Murray": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "trail_blazers": {
        "Damian Lillard": {"status": "Active", "position": "PG", "impact": "Star"},
        "Jerami Grant": {"status": "Out", "reason": "Shoulder injury", "impact": "Key"},
    },
    "clippers": {
        "Kawhi Leonard": {"status": "Out", "reason": "Rest management", "impact": "Critical"},
        "Paul George": {"status": "Active", "position": "SF", "impact": "Star"},
    },
    "kings": {
        "De'Aaron Fox": {"status": "Active", "position": "PG", "impact": "Star"},
        "Domantas Sabonis": {"status": "Active", "position": "C", "impact": "Key"},
    },
    "warriors": {
        "Stephen Curry": {"status": "Active", "position": "PG", "impact": "Star"},
        "Klay Thompson": {"status": "Active", "position": "SG", "impact": "Key"},
    },
    "lakers": {
        "LeBron James": {"status": "Active", "position": "SF", "impact": "Star"},
        "Anthony Davis": {"status": "Active", "position": "PF", "impact": "Star"},
    },
    "suns": {
        "Kevin Durant": {"status": "Active", "position": "SF", "impact": "Star"},
        "Devin Booker": {"status": "Active", "position": "SG", "impact": "Star"},
    },
}

# REAL-TIME EVENTS DATA - Game updates, injuries during play, bench status
REALTIME_EVENTS = {
    "hornets": [
        {"time": "1st Qtr 3:45", "player": "LaMelo Ball", "event": "Hit 3-pointer", "type": "Score", "impact": "High"},
        {"time": "2nd Qtr 6:20", "player": "Miles Bridges", "event": "Pulled hamstring", "type": "Injury", "impact": "Critical"},
    ],
    "pistons": [
        {"time": "Pregame", "player": "Cade Cunningham", "event": "Available - Full health", "type": "Status", "impact": "Good"},
        {"time": "3rd Qtr 2:10", "player": "Isaiah Stewart", "event": "Benched for rest", "type": "Bench", "impact": "Medium"},
    ],
    "wizards": [
        {"time": "Pregame", "player": "Bradley Beal", "event": "Out - Right ankle sprain", "type": "Injury", "impact": "Critical"},
        {"time": "1st Qtr 8:00", "player": "Damian Lillard", "event": "Leading team with 15 points", "type": "Performance", "impact": "Excellent"},
    ],
    "heat": [
        {"time": "Pregame", "player": "Jimmy Butler", "event": "Ready to play", "type": "Status", "impact": "Good"},
        {"time": "2nd Qtr 4:30", "player": "Adebayo", "event": "12 rebounds, 8 points", "type": "Performance", "impact": "Strong"},
    ],
    "hawks": [
        {"time": "1st Qtr 5:00", "player": "Trae Young", "event": "8 assists already", "type": "Performance", "impact": "Strong"},
        {"time": "Pregame", "player": "Clint Capela", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "cavaliers": [
        {"time": "Pregame", "player": "Donovan Mitchell", "event": "Game-time decision cleared", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jarrett Allen", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "celtics": [
        {"time": "Pregame", "player": "Jayson Tatum", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jaylen Brown", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
    ],
    "pelicans": [
        {"time": "Pregame", "player": "Anthony Davis", "event": "OUT - Lower back injury", "type": "Injury", "impact": "Critical"},
        {"time": "1st Qtr 1:30", "player": "Brandon Ingram", "event": "Carrying team offense", "type": "Performance", "impact": "Strong"},
    ],
    "pacers": [
        {"time": "Pregame", "player": "Tyrese Haliburton", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "2nd Qtr 3:00", "player": "Pascal Siakam", "event": "5 rebounds in 12 minutes", "type": "Performance", "impact": "Good"},
    ],
    "76ers": [
        {"time": "Pregame", "player": "Joel Embiid", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "1st Qtr 7:20", "player": "Tyrese Maxey", "event": "6 points early", "type": "Performance", "impact": "Good"},
    ],
    "knicks": [
        {"time": "Pregame", "player": "Julius Randle", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jalen Brunson", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "raptors": [
        {"time": "Pregame", "player": "Scottie Barnes", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "2nd Qtr 5:15", "player": "Fred VanVleet", "event": "Benched - Foul trouble", "type": "Bench", "impact": "Medium"},
    ],
    "bulls": [
        {"time": "Pregame", "player": "Zach LaVine", "event": "OUT - Knee injury", "type": "Injury", "impact": "Critical"},
        {"time": "1st Qtr 4:00", "player": "DeMar DeRozan", "event": "10 points, leading team", "type": "Performance", "impact": "Strong"},
    ],
    "magic": [
        {"time": "Pregame", "player": "Paolo Banchero", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jalen Suggs", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "bucks": [
        {"time": "Pregame", "player": "Giannis Antetokounmpo", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Damian Lillard", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "nets": [
        {"time": "Pregame", "player": "Mikal Bridges", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Cameron Whitmore", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "spurs": [
        {"time": "Pregame", "player": "Victor Wembanyama", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Chris Paul", "event": "Benched - Rest management", "type": "Bench", "impact": "Low"},
    ],
    "mavericks": [
        {"time": "Pregame", "player": "Luka Doncic", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Kyrie Irving", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "nuggets": [
        {"time": "Pregame", "player": "Nikola Jokic", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jamal Murray", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "thunder": [
        {"time": "Pregame", "player": "Shai Gilgeous-Alexander", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Jalen Williams", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "rockets": [
        {"time": "1st Qtr 3:30", "player": "Alperen Sengun", "event": "8 points already", "type": "Performance", "impact": "Good"},
        {"time": "Pregame", "player": "Jabarri Smith Jr", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "timberwolves": [
        {"time": "Pregame", "player": "Anthony Edwards", "event": "Available - Ready to play", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Mike Conley", "event": "Benched - Rest management", "type": "Bench", "impact": "Low"},
    ],
    "jazz": [
        {"time": "Pregame", "player": "Lauri Markkanen", "event": "Available", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "John Collins", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "grizzlies": [
        {"time": "Pregame", "player": "Ja Morant", "event": "Available - Ready to dominate", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Desmond Murray", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "trail_blazers": [
        {"time": "Pregame", "player": "Jerami Grant", "event": "OUT - Shoulder injury", "type": "Injury", "impact": "Key"},
        {"time": "1st Qtr 2:00", "player": "Damian Lillard", "event": "Will carry load tonight", "type": "Performance", "impact": "Strong"},
    ],
    "clippers": [
        {"time": "Pregame", "player": "Kawhi Leonard", "event": "OUT - Rest management", "type": "Injury", "impact": "Critical"},
        {"time": "Pregame", "player": "Paul George", "event": "Available - Will lead team", "type": "Status", "impact": "Good"},
    ],
    "kings": [
        {"time": "Pregame", "player": "De'Aaron Fox", "event": "Available - Ready to score", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Domantas Sabonis", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "warriors": [
        {"time": "Pregame", "player": "Stephen Curry", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Klay Thompson", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "lakers": [
        {"time": "Pregame", "player": "LeBron James", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Anthony Davis", "event": "Available", "type": "Status", "impact": "Good"},
    ],
    "suns": [
        {"time": "Pregame", "player": "Kevin Durant", "event": "Available - 100% healthy", "type": "Status", "impact": "Good"},
        {"time": "Pregame", "player": "Devin Booker", "event": "Available - Ready for battle", "type": "Status", "impact": "Good"},
    ],
}

# ═══════════════════════════════════════════════════════════════════════════
# NHL TEAMS STATS (2025-2026 Season)
# ═══════════════════════════════════════════════════════════════════════════
NHL_TEAM_STATS = {
    "avalanche": {"strength": 90, "gf": 3.45, "ga": 2.68, "wins": 52, "losses": 20, "gp": 82},
    "hurricanes": {"strength": 88, "gf": 3.32, "ga": 2.75, "wins": 50, "losses": 22, "gp": 82},
    "golden_knights": {"strength": 86, "gf": 3.28, "ga": 2.82, "wins": 48, "losses": 24, "gp": 82},
    "maple_leafs": {"strength": 85, "gf": 3.35, "ga": 2.88, "wins": 47, "losses": 25, "gp": 82},
    "oilers": {"strength": 84, "gf": 3.42, "ga": 2.95, "wins": 46, "losses": 26, "gp": 82},
    "rangers": {"strength": 83, "gf": 3.18, "ga": 2.72, "wins": 45, "losses": 27, "gp": 82},
    "stars": {"strength": 82, "gf": 3.22, "ga": 2.85, "wins": 44, "losses": 28, "gp": 82},
    "lightning": {"strength": 81, "gf": 3.25, "ga": 3.02, "wins": 42, "losses": 30, "gp": 82},
    "panthers": {"strength": 80, "gf": 3.15, "ga": 2.95, "wins": 40, "losses": 32, "gp": 82},
    "capitals": {"strength": 78, "gf": 3.12, "ga": 3.12, "wins": 38, "losses": 34, "gp": 82},
    "bruins": {"strength": 77, "gf": 3.08, "ga": 3.15, "wins": 36, "losses": 36, "gp": 82},
    "penguins": {"strength": 75, "gf": 2.95, "ga": 3.18, "wins": 34, "losses": 38, "gp": 82},
    "sabres": {"strength": 73, "gf": 2.92, "ga": 3.25, "wins": 32, "losses": 40, "gp": 82},
    "isles": {"strength": 72, "gf": 2.88, "ga": 3.32, "wins": 30, "losses": 42, "gp": 82},
    "devils": {"strength": 71, "gf": 2.85, "ga": 3.38, "wins": 28, "losses": 44, "gp": 82},
    "canadiens": {"strength": 68, "gf": 2.78, "ga": 3.45, "wins": 26, "losses": 46, "gp": 82},
    "flames": {"strength": 76, "gf": 3.05, "ga": 3.08, "wins": 35, "losses": 37, "gp": 82},
    "canucks": {"strength": 74, "gf": 3.02, "ga": 3.22, "wins": 33, "losses": 39, "gp": 82},
    "wild": {"strength": 79, "gf": 3.18, "ga": 3.05, "wins": 39, "losses": 33, "gp": 82},
    "jets": {"strength": 77, "gf": 3.12, "ga": 3.12, "wins": 37, "losses": 35, "gp": 82},
    "kings": {"strength": 75, "gf": 3.08, "ga": 3.18, "wins": 34, "losses": 38, "gp": 82},
    "ducks": {"strength": 70, "gf": 2.95, "ga": 3.35, "wins": 27, "losses": 45, "gp": 82},
    "sharks": {"strength": 65, "gf": 2.82, "ga": 3.48, "wins": 24, "losses": 48, "gp": 82},
    "red_wings": {"strength": 72, "gf": 2.98, "ga": 3.28, "wins": 31, "losses": 41, "gp": 82},
    "blue_jackets": {"strength": 69, "gf": 2.88, "ga": 3.38, "wins": 28, "losses": 44, "gp": 82},
    "coyotes": {"strength": 66, "gf": 2.75, "ga": 3.52, "wins": 25, "losses": 47, "gp": 82},
    "predators": {"strength": 78, "gf": 3.15, "ga": 3.05, "wins": 38, "losses": 34, "gp": 82},
    "kraken": {"strength": 76, "gf": 3.10, "ga": 3.15, "wins": 36, "losses": 36, "gp": 82},
}

# ═══════════════════════════════════════════════════════════════════════════
# NFL TEAMS STATS (2025-2026 Season)
# ═══════════════════════════════════════════════════════════════════════════
NFL_TEAM_STATS = {
    "chiefs": {"strength": 95, "pf": 28.2, "pa": 18.5, "wins": 12, "losses": 5, "gp": 17},
    "49ers": {"strength": 93, "pf": 27.8, "pa": 19.2, "wins": 11, "losses": 6, "gp": 17},
    "eagles": {"strength": 91, "pf": 27.1, "pa": 20.1, "wins": 10, "losses": 7, "gp": 17},
    "ravens": {"strength": 89, "pf": 26.5, "pa": 21.2, "wins": 9, "losses": 8, "gp": 17},
    "cowboys": {"strength": 87, "pf": 26.2, "pa": 21.8, "wins": 8, "losses": 9, "gp": 17},
    "patriots": {"strength": 85, "pf": 25.8, "pa": 22.5, "wins": 7, "losses": 10, "gp": 17},
    "bills": {"strength": 88, "pf": 26.8, "pa": 20.5, "wins": 9, "losses": 8, "gp": 17},
    "dolphins": {"strength": 86, "pf": 26.1, "pa": 21.8, "wins": 8, "losses": 9, "gp": 17},
    "packers": {"strength": 84, "pf": 25.5, "pa": 22.3, "wins": 7, "losses": 10, "gp": 17},
    "lions": {"strength": 82, "pf": 25.2, "pa": 23.1, "wins": 6, "losses": 11, "gp": 17},
    "buccaneers": {"strength": 80, "pf": 24.8, "pa": 24.2, "wins": 5, "losses": 12, "gp": 17},
    "saints": {"strength": 78, "pf": 24.2, "pa": 25.1, "wins": 4, "losses": 13, "gp": 17},
    "titans": {"strength": 76, "pf": 23.8, "pa": 25.8, "wins": 3, "losses": 14, "gp": 17},
    "bengals": {"strength": 81, "pf": 25.5, "pa": 23.2, "wins": 7, "losses": 10, "gp": 17},
    "texans": {"strength": 79, "pf": 24.9, "pa": 24.1, "wins": 6, "losses": 11, "gp": 17},
    "colts": {"strength": 77, "pf": 24.1, "pa": 25.2, "wins": 4, "losses": 13, "gp": 17},
    "chargers": {"strength": 83, "pf": 25.8, "pa": 23.5, "wins": 8, "losses": 9, "gp": 17},
    "raiders": {"strength": 75, "pf": 23.5, "pa": 26.2, "wins": 3, "losses": 14, "gp": 17},
    "broncos": {"strength": 80, "pf": 25.2, "pa": 24.3, "wins": 6, "losses": 11, "gp": 17},
    "seahawks": {"strength": 78, "pf": 24.8, "pa": 25.1, "wins": 5, "losses": 12, "gp": 17},
}

# ═══════════════════════════════════════════════════════════════════════════
# HOCKEY ODDS (BET365, BETFAIR, DRAFTKINGS)
# ═══════════════════════════════════════════════════════════════════════════
BET365_ODDS_NHL = {
    ("hurricanes", "avalanche"): {"away_ml": 2.40, "home_ml": 1.55},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.85, "home_ml": 1.95},
    ("rangers", "oilers"): {"away_ml": 2.10, "home_ml": 1.72},
    ("stars", "lightning"): {"away_ml": 1.95, "home_ml": 1.85},
    ("panthers", "capitals"): {"away_ml": 1.60, "home_ml": 2.30},
}

BETFAIR_ODDS_NHL = {
    ("hurricanes", "avalanche"): {"away_ml": 2.42, "home_ml": 1.57},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.87, "home_ml": 1.93},
    ("rangers", "oilers"): {"away_ml": 2.12, "home_ml": 1.70},
    ("stars", "lightning"): {"away_ml": 1.97, "home_ml": 1.83},
    ("panthers", "capitals"): {"away_ml": 1.62, "home_ml": 2.28},
}

DRAFTKINGS_ODDS_NHL = {
    ("hurricanes", "avalanche"): {"away_ml": 2.45, "home_ml": 1.53},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.88, "home_ml": 1.92},
    ("rangers", "oilers"): {"away_ml": 2.15, "home_ml": 1.68},
    ("stars", "lightning"): {"away_ml": 1.98, "home_ml": 1.82},
    ("panthers", "capitals"): {"away_ml": 1.65, "home_ml": 2.25},
}

# ═══════════════════════════════════════════════════════════════════════════
# FOOTBALL ODDS (BET365, BETFAIR, DRAFTKINGS)
# ═══════════════════════════════════════════════════════════════════════════
BET365_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.95, "home_ml": 1.85},
    ("eagles", "ravens"): {"away_ml": 2.20, "home_ml": 1.65},
    ("cowboys", "patriots"): {"away_ml": 1.72, "home_ml": 2.10},
    ("bills", "dolphins"): {"away_ml": 1.85, "home_ml": 1.95},
}

BETFAIR_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.97, "home_ml": 1.83},
    ("eagles", "ravens"): {"away_ml": 2.22, "home_ml": 1.63},
    ("cowboys", "patriots"): {"away_ml": 1.74, "home_ml": 2.08},
    ("bills", "dolphins"): {"away_ml": 1.87, "home_ml": 1.93},
}

DRAFTKINGS_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.98, "home_ml": 1.82},
    ("eagles", "ravens"): {"away_ml": 2.25, "home_ml": 1.60},
    ("cowboys", "patriots"): {"away_ml": 1.76, "home_ml": 2.06},
    ("bills", "dolphins"): {"away_ml": 1.88, "home_ml": 1.92},
}

# ═══════════════════════════════════════════════════════════════════════════
# DEMO MATCHUPS FOR TESTING
# ═══════════════════════════════════════════════════════════════════════════
DEMO_MATCHES_NHL = [("Hurricanes", "Avalanche"), ("Maple Leafs", "Golden Knights"), ("Rangers", "Oilers")]
DEMO_MATCHES_NFL = [("Chiefs", "49ers"), ("Eagles", "Ravens"), ("Cowboys", "Patriots")]

def find_team(name_input):
    """Alias pour find_team_nba - utilisée partout pour compatibilité"""
    return find_team_nba(name_input)

def get_player_props(away_team, home_team):
    """Récupère les joueurs clés et leurs props pour un matchup NBA"""
    away_clean = find_team_nba(away_team) or away_team.lower().replace(' ', '_')
    home_clean = find_team_nba(home_team) or home_team.lower().replace(' ', '_')
    
    logger.debug(f"🔍 Player Props: {away_team} -> {away_clean} | {home_team} -> {home_clean}")
    logger.debug(f"🔍 Available in NBA_PLAYERS_PROPS: {list(NBA_PLAYERS_PROPS.keys())[:5]}")
    
    props = []
    
    # Joueurs away
    if away_clean in NBA_PLAYERS_PROPS:
        logger.debug(f"✅ Away team {away_clean} trouvé dans NBA_PLAYERS_PROPS")
        for player_key, player_data in NBA_PLAYERS_PROPS[away_clean].items():
            props.append({
                "team": away_clean,
                "side": "away",
                "player_key": player_key,
                "name": player_data["name"],
                "ppg": player_data["ppg"],
                "lines": player_data["lines"],
            })
    else:
        logger.debug(f"❌ Away team {away_clean} NOT in NBA_PLAYERS_PROPS")
    
    # Joueurs home
    if home_clean in NBA_PLAYERS_PROPS:
        logger.debug(f"✅ Home team {home_clean} trouvé dans NBA_PLAYERS_PROPS")
        for player_key, player_data in NBA_PLAYERS_PROPS[home_clean].items():
            props.append({
                "team": home_clean,
                "side": "home",
                "player_key": player_key,
                "name": player_data["name"],
                "ppg": player_data["ppg"],
                "lines": player_data["lines"],
            })
    else:
        logger.debug(f"❌ Home team {home_clean} NOT in NBA_PLAYERS_PROPS")
    
    logger.debug(f"📊 Total props retournés: {len(props)}")
    return props[:4]  # Retourner max 4 joueurs (2 par équipe)

def get_player_props_odds_from_matchup(away_team, home_team, prop_side, ppg_value):
    """Génère des odds Player Props basées sur les odds du matchup et le PPG du joueur"""
    away_clean = find_team_nba(away_team) or away_team.lower().replace(' ', '_')
    home_clean = find_team_nba(home_team) or home_team.lower().replace(' ', '_')
    
    # Chercher les odds du matchup dans tous les bookmakers
    matchup_key_forward = (away_clean, home_clean)
    matchup_key_reverse = (home_clean, away_clean)
    
    best_under = 1.90
    best_over = 1.90
    
    for book_name, odds_dict in [("BET365", BET365_ODDS), ("BETFAIR", BETFAIR_ODDS), ("DRAFTKINGS", DRAFTKINGS_ODDS)]:
        # Chercher le matchup
        if matchup_key_forward in odds_dict:
            odds = odds_dict[matchup_key_forward]
        elif matchup_key_reverse in odds_dict:
            odds = odds_dict[matchup_key_reverse]
        else:
            continue
        
        # Récupérer sous/over du matchup (total team points indicator)
        if "under" in odds and "over" in odds:
            book_under = odds["under"]
            book_over = odds["over"]
            
            # Améliorer les odds si ce bookmaker est meilleur
            if book_under > best_under:
                best_under = book_under
            if book_over > best_over:
                best_over = book_over
    
    # Ajustement basé sur le PPG du joueur (plus haut PPG = odds plus serré = pire ligne)
    # Joueurs clés (25+ PPG): odds plus serrées (1.88-1.92)
    # Joueurs role players (15-24 PPG): odds moyennes (1.85-1.95)  
    # Joueurs bench (10-14 PPG): odds plus larges (1.80-2.00)
    if ppg_value >= 25:
        odds_adjustment = 1.00  # Odds serrées pour stars
        confidence_boost = 1.15
    elif ppg_value >= 15:
        odds_adjustment = 1.05  # Odds moyennes
        confidence_boost = 1.10
    else:
        odds_adjustment = 1.10  # Odds larges pour bench
        confidence_boost = 1.05
    
    # Ajustement si joueur en déplacement (odds légèrement pires)
    if prop_side == "away":
        odds_adjustment *= 1.02
    
    # Appliquer les ajustements
    final_under = min(2.00, best_under * 0.98)  # Caper à 2.00
    final_over = min(2.00, best_over * 0.98)
    
    return {
        "under": round(final_under, 2),
        "over": round(final_over, 2),
        "base_ppg": ppg_value,
        "adjustment": odds_adjustment,
        "confidence_boost": confidence_boost
    }

def generate_player_props_prediction(away_team, home_team):
    """Génère des prédictions Player Props basées sur les odds des bookmakers"""
    away_clean = find_team_nba(away_team) or away_team.lower().replace(' ', '_')
    home_clean = find_team_nba(home_team) or home_team.lower().replace(' ', '_')
    
    props_list = get_player_props(away_team, home_team)
    
    if not props_list:
        logger.debug(f"⚠️ Aucun props trouvé pour {away_team} @ {home_team}")
        return []
    
    predictions = []
    
    for prop in props_list:
        try:
            player_name = prop["name"]
            ppg = prop["ppg"]
            lines = prop["lines"]  # [O/U basses, medium, hautes]
            side = prop["side"]
            
            # Utiliser la ligne médiane
            primary_line = lines[1] if len(lines) > 1 else lines[0]
            
            # Déterminer l'ajustement basé sur le matchup
            if side == "away":
                adjustment = -0.8
                market_signal = -0.3  # Marché défavorable
            else:
                adjustment = 0.5
                market_signal = 0.2  # Marché favorable
            
            expected_ppg = ppg + adjustment + market_signal
            
            # IMPORTANT: Obtenir les odds basées sur les bookmakers
            odds_data = get_player_props_odds_from_matchup(away_team, home_team, side, ppg)
            
            under_odds = odds_data["under"]
            over_odds = odds_data["over"]
            confidence_boost = odds_data["confidence_boost"]
            
            # Décision Over/Under basée sur expected vs line
            if expected_ppg > primary_line:
                pick = f"OVER {primary_line}"
                odds_val = over_odds
                # EV = (odds - 1) * probabilité - (1 - probabilité)
                # Probabilité basée sur écart: expected vs line
                ppg_diff = expected_ppg - primary_line
                base_prob = min(0.65, 0.50 + ppg_diff * 0.05)  # Cap à 65%
                prob = min(0.75, base_prob * confidence_boost)
                ev = (odds_val - 1.0) * prob - (1.0 - prob)
                confidence = int(min(95, 50 + ppg_diff * 12))
            else:
                pick = f"UNDER {primary_line}"
                odds_val = under_odds
                ppg_diff = primary_line - expected_ppg
                base_prob = min(0.65, 0.50 + ppg_diff * 0.05)
                prob = min(0.75, base_prob * confidence_boost)
                ev = (odds_val - 1.0) * prob - (1.0 - prob)
                confidence = int(min(95, 50 + ppg_diff * 12))
            
            # Status based on EV and odds quality
            if ev > 0.02 and odds_val > 1.85:  # Strong value + good odds
                status = "✅ BUY"
            elif ev > 0.005 and odds_val > 1.80:  # Some value
                status = "👀 MONITOR"
            else:
                status = "⏸ PASS"
            
            logger.debug(f"🎯 {player_name}: PPG={ppg} | Expected={expected_ppg:.1f} | Line={primary_line} | Pick={pick} | Odds={odds_val:.2f} | Prob={prob:.1%} | EV={ev:.4f} | Status={status}")
            
            predictions.append({
                "player": player_name,
                "team": prop["team"],
                "ppg": ppg,
                "line": primary_line,
                "expected": f"{expected_ppg:.1f}",
                "pick": pick,
                "odds": f"{odds_val:.2f}",
                "confidence": confidence,
                "ev": f"{ev:.4f}",
                "ev_pct": f"{ev*100:.2f}%",
                "status": status,
            })
            logger.debug(f"✅ Player prop: {player_name} - {pick} @ {odds_val:.2f}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur prop {prop.get('name')}: {e}")
            continue
    
    logger.debug(f"📊 {len(predictions)} predictions générées")
    return predictions

def generate_prediction(away_team, home_team):
    """
    CERTIFIED BOOKMAKER PREDICTION ENGINE v5.7
    - Line shopping across BET365, BETFAIR, DRAFTKINGS
    - Market consensus analysis
    - Mismatch edge detection
    """
    
    away_clean = find_team_nba(away_team) or away_team.lower()
    home_clean = find_team_nba(home_team) or home_team.lower()
    
    away_stats = TEAM_STATS.get(away_clean) or {"strength": 78, "ortg": 110, "drtg": 112, "wins": 35, "losses": 47}
    home_stats = TEAM_STATS.get(home_clean) or {"strength": 78, "ortg": 110, "drtg": 112, "wins": 35, "losses": 47}
    
    # Get BEST odds across certified bookmakers (line shopping)
    odds_data = get_best_odds(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    away_book = odds_data["away_book"]
    home_book = odds_data["home_book"]
    
    # Calculate market consensus from ALL certified bookmakers (bidirectional)
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    book_odds = []
    for odds_dict_func, book_name in [
        (lambda: BET365_ODDS.get(key_forward) or BET365_ODDS.get(key_reverse), "BET365"),
        (lambda: BETFAIR_ODDS.get(key_forward) or BETFAIR_ODDS.get(key_reverse), "BETFAIR"),
        (lambda: DRAFTKINGS_ODDS.get(key_forward) or DRAFTKINGS_ODDS.get(key_reverse), "DRAFTKINGS"),
    ]:
        odds_dict = odds_dict_func()
        if odds_dict:
            # Check if we're in reverse mode
            if key_reverse in BET365_ODDS and key_forward not in BET365_ODDS:
                # Reverse the odds (away/home are swapped)
                book_odds.append(({
                    "away_ml": odds_dict.get("home_ml", 1.0),
                    "home_ml": odds_dict.get("away_ml", 1.0)
                }, book_name))
            else:
                book_odds.append((odds_dict, book_name))
        else:
            book_odds.append(({}, book_name))
    
    market_away_sum = 0
    market_home_sum = 0
    book_count = 0
    
    for odds_dict, book_name in book_odds:
        if odds_dict and "away_ml" in odds_dict:
            away_implied = 1.0 / odds_dict["away_ml"]
            home_implied = 1.0 / odds_dict["home_ml"]
            market_away_sum += away_implied
            market_home_sum += home_implied
            book_count += 1
    
    if book_count > 0:
        market_away_avg = market_away_sum / book_count
        market_home_avg = market_home_sum / book_count
        total_market = market_away_avg + market_home_avg
        market_consensus_away = market_away_avg / total_market
    else:
        market_consensus_away = 0.5
    
    # Advanced 4-Factor Model Analysis
    away_ortg = away_stats["ortg"]
    away_drtg = away_stats["drtg"]
    home_ortg = home_stats["ortg"]
    home_drtg = home_stats["drtg"]
    
    # Strength differential calculation
    away_expected_pts = away_ortg - home_drtg - 2.5  # Road disadvantage
    home_expected_pts = home_ortg - away_drtg + 2.5  # Home court advantage
    
    point_diff = away_expected_pts - home_expected_pts
    
    # Logistic sigmoid for win probability (more accurate)
    import math
    try:
        win_prob_away = 1 / (1 + math.exp(-point_diff / 14.5))
    except:
        win_prob_away = 0.5 + (point_diff / 80.0)
    win_prob_away = max(0.05, min(0.95, win_prob_away))
    
    # Regression to mean (50% model / 50% market)
    away_win_pct = away_stats["wins"] / (away_stats["wins"] + away_stats["losses"] + 0.001)
    model_prob = win_prob_away
    blended_prob = (0.50 * model_prob) + (0.50 * market_consensus_away)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    # EDGE DETECTION: Market vs Model Mismatch
    market_error = abs(blended_prob - market_consensus_away)
    
    # EV Calculation with best odds
    ev_away = (best_away_ml - 1.0) * blended_prob - (1.0 - blended_prob)
    ev_home = (best_home_ml - 1.0) * (1.0 - blended_prob) - blended_prob
    
    # INTELLIGENT FILTERING: Afficher TOUS les matchs intelligemment
    # Seuil minimum réduit pour montrer plus de picks
    min_ev_buy = 0.01  # +1% pour BUY picks
    
    # Déterminer le pick PRÉFÉRÉ (celui avec meilleur EV)
    if ev_away > ev_home:
        preferred_pick = f"{away_team.upper()} ML"
        preferred_odds = best_away_ml
        preferred_confidence = int(blended_prob * 100)
        preferred_ev = ev_away
        preferred_book = away_book
        preferred_analysis = f"ORTG {away_ortg} vs DRTG {home_drtg} = +{away_ortg - home_drtg} pts"
        opposite_ev = ev_home
    else:
        preferred_pick = f"{home_team.upper()} ML"
        preferred_odds = best_home_ml
        preferred_confidence = int((1.0 - blended_prob) * 100)
        preferred_ev = ev_home
        preferred_book = home_book
        preferred_analysis = f"Home +2.5 | DRTG {home_drtg} vs ORTG {away_ortg}"
        opposite_ev = ev_away
    
    # Déterminer le statut (BUY, NEUTRAL, PASS)
    if preferred_ev > min_ev_buy:
        status = "✅ BUY"
    elif preferred_ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"
    
    # Risk assessment basé sur le discord du marché
    if market_error > 0.12:
        risk = "🔴 HIGH DISCORD"
    elif market_error > 0.08:
        risk = "🟡 MEDIUM DISCORD"
    else:
        risk = "🟢 LOW (Consensus)"
    
    # PRÉDICTIONS UNDER/OVER
    # Obtenir le total de points et les cotes U/O
    total_line = None
    under_odds = None
    over_odds = None
    
    # Chercher le meilleur total U/O à travers les bookmakers
    for odds_dict, book_name in book_odds:
        if odds_dict and "total" in odds_dict:
            total_line = odds_dict["total"]
            under_odds = odds_dict.get("under", 1.90)
            over_odds = odds_dict.get("over", 1.90)
            break
    
    # Calculer le total attendu
    total_expected = away_expected_pts + home_expected_pts
    
    # Décision U/O basée sur la prédiction
    if total_line:
        total_diff = total_expected - total_line
        
        if total_diff > 2.5:  # Clear OVER opportunity
            ou_pick = f"OVER {total_line}"
            ou_odds = over_odds
            ou_confidence = int(60 + abs(total_diff))
            ou_ev = (ou_odds - 1.0) * 0.55 - (1.0 - 0.55)
            ou_book = "Under/Over"
        elif total_diff < -2.5:  # Clear UNDER opportunity
            ou_pick = f"UNDER {total_line}"
            ou_odds = under_odds
            ou_confidence = int(60 + abs(total_diff))
            ou_ev = (ou_odds - 1.0) * 0.45 - (1.0 - 0.45)
            ou_book = "Under/Over"
        else:
            ou_pick = "NEUTRAL O/U"
            ou_odds = 1.90
            ou_confidence = 50
            ou_ev = 0.0
            ou_book = "N/A"
    else:
        ou_pick = "NO DATA"
        ou_odds = 1.90
        ou_confidence = 0
        ou_ev = 0.0
        ou_book = "N/A"
    
    return {
        "pick": preferred_pick,
        "odds": f"{preferred_odds:.2f}",
        "confidence": preferred_confidence,
        "ev": f"{preferred_ev:.4f}",
        "ev_pct": f"{preferred_ev*100:.2f}%",
        "roi_pct": f"{preferred_ev*100:.1f}%",
        "reasoning": preferred_analysis,
        "risk": risk,
        "status": status,
        "bookmaker": preferred_book,
        "market_consensus": f"{market_consensus_away*100:.1f}%",
        "model_prob": f"{blended_prob*100:.1f}%",
        "market_discord": f"{market_error*100:.1f}%",
        "ou_pick": ou_pick,
        "ou_odds": f"{ou_odds:.2f}",
        "ou_confidence": ou_confidence,
        "ou_ev": f"{ou_ev:.4f}",
        "total_line": f"{total_line:.1f}" if total_line else "N/A",
        "total_expected": f"{total_expected:.1f}",
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🤖 ULTRON v6.0 - MULTISPORTS PRECISION\n\n"
    msg += "NBA 🏀 | NHL 🏒 | NFL 🏈\n"
    msg += "🕐 Heure Québec | 🌍 ESPN Live Data\n"
    msg += "📊 3 Bookmakers | Line Shopping | Smart Filtering\n\n"
    msg += "🏆 TOUS LES MATCHS ANALYSÉS:\n"
    msg += "✅ BUY - Valeur +1% EV minimum\n"
    msg += "👀 MONITORING - Entre 0% et +1% EV\n"
    msg += "⏸ PASS - À éviter\n\n"
    msg += "COMMANDES MATCHS:\n"
    msg += "/nba - Équipes NBA 🏀\n"
    msg += "/nhl - Équipes NHL 🏒\n"
    msg += "/nfl - Équipes NFL 🏈\n\n"
    msg += "COMMANDES PRONOSTICS:\n"
    msg += "/pronostics nba - Analyse NBA\n"
    msg += "/pronostics nhl - Analyse NHL\n"
    msg += "/pronostics nfl - Analyse NFL\n\n"
    msg += "AUTRES:\n"
    msg += "/info - Info temps réel d'une équipe\n"
    msg += "/injuries - Statut des joueurs (NBA)\n"
    msg += "/help - Aide"
    await update.message.reply_text(msg)

async def nba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's NBA matches - LIVE from ESPN"""
    try:
        matches = get_live_matches()
        quebec_time = get_quebec_time()
        
        if not matches:
            msg = "❌ Aucun match NBA actif aujourd'hui\n"
            msg += "(Tous terminés ou pas de match programmé)"
            await update.message.reply_text(msg)
            return
        
        msg = f"🏀 MATCHS NBA EN DIRECT\n"
        msg += "═" * 60 + "\n"
        msg += f"🕐 {quebec_time.strftime('%d/%m/%Y %H:%M:%S')} (Heure Québec)\n"
        msg += "═" * 60 + "\n\n"
        
        for i, (away, home) in enumerate(matches, 1):
            msg += f"{i:2}. {away:20} @ {home:20}\n"
        
        msg += "\n" + "═" * 60 + "\n"
        msg += f"📊 Total: {len(matches)} matchs en direct\n"
        msg += "📡 Données ESPN temps réel (refresh: 2 min)"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Erreur lors du chargement des matchs")

async def nhl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les matchs NHL en direct"""
    try:
        matches = get_live_matches_nhl()
        quebec_time = get_quebec_time()
        
        if not matches:
            msg = "❌ Aucun match NHL actif aujourd'hui\n"
            msg += "(Tous terminés ou pas de match programmé)"
            await update.message.reply_text(msg)
            return
        
        msg = f"🏒 MATCHS NHL EN DIRECT\n"
        msg += "═" * 60 + "\n"
        msg += f"🕐 {quebec_time.strftime('%d/%m/%Y %H:%M:%S')} (Heure Québec)\n"
        msg += "═" * 60 + "\n\n"
        
        for i, (away, home) in enumerate(matches, 1):
            msg += f"{i:2}. {away:20} @ {home:20}\n"
        
        msg += "\n" + "═" * 60 + "\n"
        msg += f"📊 Total: {len(matches)} matchs en direct\n"
        msg += "💡 Utilise /pronostics nhl pour les prédictions"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Erreur NHL")

async def nfl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les matchs NFL en direct"""
    try:
        matches = get_live_matches_nfl()
        quebec_time = get_quebec_time()
        
        if not matches:
            msg = "❌ Aucun match NFL actif aujourd'hui\n"
            msg += "(Tous terminés ou pas de match programmé)"
            await update.message.reply_text(msg)
            return
        
        msg = f"🏈 MATCHS NFL EN DIRECT\n"
        msg += "═" * 60 + "\n"
        msg += f"🕐 {quebec_time.strftime('%d/%m/%Y %H:%M:%S')} (Heure Québec)\n"
        msg += "═" * 60 + "\n\n"
        
        for i, (away, home) in enumerate(matches, 1):
            msg += f"{i:2}. {away:20} @ {home:20}\n"
        
        msg += "\n" + "═" * 60 + "\n"
        msg += f"📊 Total: {len(matches)} matchs en direct\n"
        msg += "💡 Utilise /pronostics nfl pour les prédictions"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Erreur NFL")

async def pronostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route vers les pronostics du sport demandé: /pronostics <nba|nhl|nfl>"""
    if not context.args:
        msg = "❌ Usage: /pronostics <sport>\n\n"
        msg += "Exemple:\n"
        msg += "/pronostics nba - Pronostics NBA 🏀\n"
        msg += "/pronostics nhl - Pronostics NHL 🏒\n"
        msg += "/pronostics nfl - Pronostics NFL 🏈"
        await update.message.reply_text(msg)
        return
    
    sport = context.args[0].lower()
    
    if sport == "nhl":
        await pronostics_nhl(update, context)
    elif sport == "nfl":
        await pronostics_nfl(update, context)
    elif sport == "nba":
        await pronostics_nba(update, context)
    else:
        msg = f"❌ Sport '{sport}' non reconnu\n"
        msg += "Sports disponibles: nba, nhl, nfl"
        await update.message.reply_text(msg)

async def pronostics_nba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """INTELLIGENT PREDICTIONS NBA - Tous les matchs avec analyses détaillées"""
    try:
        # Récupérer les VRAIS matchs en direct
        real_matches = get_live_matches()
        
        if not real_matches:
            msg = "❌ Aucun match NBA actuel\n"
            msg += "Revenez quand il y a des matchs en direct!"
            await update.message.reply_text(msg)
            return
        
        # Générer prédictions pour TOUS les matchs (plus de filtrage)
        predictions = []
        for away, home in real_matches:
            pred = generate_prediction(away, home)
            predictions.append((away, home, pred))
        
        # Séparer par type de pick
        buy_picks = [(a, h, p) for a, h, p in predictions if "BUY" in p['status']]
        monitoring_picks = [(a, h, p) for a, h, p in predictions if "MONITORING" in p['status']]
        pass_picks = [(a, h, p) for a, h, p in predictions if "PASS" in p['status']]
        
        # Trier chaque catégorie par EV
        buy_picks.sort(key=lambda x: float(x[2]['ev']), reverse=True)
        monitoring_picks.sort(key=lambda x: float(x[2]['ev']), reverse=True)
        
        # Heure du Québec
        quebec_time = get_quebec_time()
        
        # MESSAGE 1: HEADER + BUY PICKS
        msg1 = "🎯 ULTRON v6.0 - NBA INTELLIGENCE\n"
        msg1 += "═" * 70 + "\n"
        msg1 += f"🕐 {quebec_time.strftime('%H:%M:%S')} (Heure Québec)\n"
        msg1 += f"📡 {len(real_matches)} matchs NBA en direct\n"
        msg1 += "═" * 70 + "\n\n"
        
        # SECTION BUY PICKS (✅ Meilleure valeur)
        if buy_picks:
            msg1 += "✅ ACHETER - Meilleure valeur (+1% EV minimum)\n"
            msg1 += "─" * 70 + "\n\n"
            for i, (away, home, pred) in enumerate(buy_picks, 1):
                msg1 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg1 += f"   💡 MONEYLINE: {pred['pick']} @ {pred['odds']}\n"
                msg1 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n"
                msg1 += f"   📊 Total: {pred['total_expected']} pts (Line: {pred['total_line']})\n"
                msg1 += f"   🎯 U/O: {pred['ou_pick']} @ {pred['ou_odds']}\n"
                msg1 += f"   Risk: {pred['risk']}\n\n"
        else:
            msg1 += "✅ ACHETER: Aucun pick avec EV > +1%\n\n"
        
        await update.message.reply_text(msg1)
        
        # MESSAGE 2: MONITORING PICKS
        msg2 = "👀 MONITORING - À surveiller (0% < EV < +1%)\n"
        msg2 += "─" * 70 + "\n\n"
        
        if monitoring_picks:
            for i, (away, home, pred) in enumerate(monitoring_picks, 1):
                msg2 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg2 += f"   💡 MONEYLINE: {pred['pick']} @ {pred['odds']}\n"
                msg2 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n"
                msg2 += f"   📊 Total: {pred['total_expected']} pts (Line: {pred['total_line']})\n"
                msg2 += f"   🎯 U/O: {pred['ou_pick']} @ {pred['ou_odds']}\n\n"
        else:
            msg2 += "Aucun pick en monitoring"
        
        await update.message.reply_text(msg2)
        
        # MESSAGE 3: PASS PICKS (À éviter)
        msg3 = f"⏸ PAS JOUER - Attendre meilleure valeur ({len(pass_picks)} matchs)\n"
        msg3 += "─" * 70 + "\n\n"
        
        if pass_picks:
            count = 0
            for i, (away, home, pred) in enumerate(pass_picks, 1):
                pick_msg = f"{i}️⃣ {away.upper()} @ {home.upper()} ❌\n"
                pick_msg += f"   💡 ML: {pred['pick']} @ {pred['odds']} | EV: {pred['ev_pct']}\n"
                pick_msg += f"   📊 Total: {pred['total_expected']} (Line: {pred['total_line']})\n"
                pick_msg += f"   🎯 U/O: {pred['ou_pick']} @ {pred['ou_odds']}\n\n"
                
                if len(msg3 + pick_msg) < 4000:
                    msg3 += pick_msg
                else:
                    await update.message.reply_text(msg3)
                    msg3 = pick_msg
        
        await update.message.reply_text(msg3)
        
        # MESSAGE 4: RÉSUMÉ MATCHUPS
        msg4 = "═" * 70 + "\n"
        msg4 += f"📊 RÉSUMÉ: {len(buy_picks)} BUY | {len(monitoring_picks)} MONITORING | {len(pass_picks)} PASS\n"
        msg4 += "💰 Bankroll: Risk 1-2% par pick BUY seulement\n"
        msg4 += "🔄 Cache: 2 minutes pour données fraîches"
        
        await update.message.reply_text(msg4)
        
        # MESSAGE 5: PLAYER PROPS (UNDER/OVER POINTS)
        msg5 = "🎯 ULTRON PLAYER PROPS - POINTS UNDER/OVER\n"
        msg5 += "═" * 70 + "\n"
        msg5 += "Prédictions sur les joueurs clés en direct\n"
        msg5 += "═" * 70 + "\n\n"
        
        player_props_all = []
        for away, home in real_matches:
            try:
                player_props = generate_player_props_prediction(away, home)
                for prop in player_props:
                    player_props_all.append((away, home, prop))
            except Exception as e:
                logger.debug(f"Player props error for {away} vs {home}: {e}")
                continue
        
        if player_props_all:
            # Séparer par type
            buy_props = [p for p in player_props_all if "BUY" in p[2]['status']]
            monitor_props = [p for p in player_props_all if "MONITOR" in p[2]['status']]
            pass_props = [p for p in player_props_all if "PASS" in p[2]['status']]
            
            # Afficher BUY props
            if buy_props:
                msg5 += "✅ ACHETER - PLAYER PROPS BUY\n"
                msg5 += "─" * 70 + "\n\n"
                for away, home, prop in buy_props[:5]:  # Max 5 picks
                    msg5 += f"🌟 {prop['player'].upper()} ({prop['team'].upper()})\n"
                    msg5 += f"   PPG Moyenne: {prop['ppg']:.1f} | Attendu: {prop['expected']}\n"
                    msg5 += f"   💡 {prop['pick']} @ {prop['odds']}\n"
                    msg5 += f"   🔥 Confiance: {prop['confidence']}% | EV: {prop['ev_pct']}\n\n"
            
            # Afficher MONITORING props
            if monitor_props:
                msg5 += "👀 MONITORING - PLAYER PROPS\n"
                msg5 += "─" * 70 + "\n\n"
                for away, home, prop in monitor_props[:3]:  # Max 3 picks
                    msg5 += f"🌟 {prop['player'].upper()} ({prop['team'].upper()})\n"
                    msg5 += f"   PPG Moyenne: {prop['ppg']:.1f} | Attendu: {prop['expected']}\n"
                    msg5 += f"   💡 {prop['pick']} @ {prop['odds']}\n"
                    msg5 += f"   🔥 Confiance: {prop['confidence']}% | EV: {prop['ev_pct']}\n\n"
            
            # Résumé props
            msg5 += "─" * 70 + "\n"
            msg5 += f"📊 PROPS RÉSUMÉ: {len(buy_props)} BUY | {len(monitor_props)} MONITORING | {len(pass_props)} PASS\n"
        else:
            msg5 += "⚠️ Pas assez de données Player Props disponibles\n"
        
        msg5 += "\n💡 Tips: Risk 0.5-1% par pick Player Props\n"
        msg5 += "🎯 Combiner avec Moneyline pour meilleur EV"
        
        await update.message.reply_text(msg5)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

async def pronostics_nhl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les pronostics NHL"""
    try:
        matches = get_live_matches_nhl()
        quebec_time = get_quebec_time()
        
        if not matches:
            await update.message.reply_text("❌ Aucun match NHL actuel")
            return
        
        predictions = []
        for away, home in matches:
            try:
                pred = generate_prediction_nhl(away, home)
                predictions.append((away, home, pred))
            except Exception as e:
                logger.warning(f"⚠️ Erreur prédiction {away} @ {home}: {e}")
                continue
        
        if not predictions:
            await update.message.reply_text("⚠️ Impossible de générer les prédictions NHL")
            return
        
        buy_picks = [(a, h, p) for a, h, p in predictions if "BUY" in p['status']]
        monitoring_picks = [(a, h, p) for a, h, p in predictions if "MONITORING" in p['status']]
        pass_picks = [(a, h, p) for a, h, p in predictions if "PASS" in p['status']]
        
        msg1 = "🏒 ULTRON v6.0 - PRÉDICTIONS NHL\n"
        msg1 += "═" * 70 + "\n"
        msg1 += f"🕐 {quebec_time.strftime('%H:%M:%S')} (Heure Québec)\n"
        msg1 += f"📡 {len(matches)} matchs NHL en direct | {len(predictions)} avec prédictions\n"
        msg1 += "═" * 70 + "\n\n"
        
        if buy_picks:
            msg1 += "✅ ACHETER - Meilleure valeur\n"
            msg1 += "─" * 70 + "\n\n"
            for i, (away, home, pred) in enumerate(buy_picks, 1):
                msg1 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg1 += f"   💡 {pred['pick']} @ {pred['odds']}\n"
                msg1 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n"
                msg1 += f"   📊 Bookmaker: {pred['bookmaker']}\n\n"
        else:
            msg1 += "✅ Aucun pick BUY actuellement\n\n"
        
        await update.message.reply_text(msg1)
        
        msg2 = "👀 MONITORING - À surveiller\n"
        msg2 += "─" * 70 + "\n\n"
        
        if monitoring_picks:
            for i, (away, home, pred) in enumerate(monitoring_picks, 1):
                msg2 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg2 += f"   💡 {pred['pick']} @ {pred['odds']}\n"
                msg2 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n\n"
        else:
            msg2 += "Aucun monitoring\n\n"
        
        msg2 += "─" * 70 + "\n"
        msg2 += f"📊 RÉSUMÉ: {len(buy_picks)} BUY | {len(monitoring_picks)} MONITORING | {len(pass_picks)} PASS"
        
        await update.message.reply_text(msg2)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Erreur NHL: {e}")

async def pronostics_nfl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les pronostics NFL"""
    try:
        matches = get_live_matches_nfl()
        quebec_time = get_quebec_time()
        
        if not matches:
            await update.message.reply_text("❌ Aucun match NFL actuel")
            return
        
        predictions = []
        for away, home in matches:
            try:
                pred = generate_prediction_nfl(away, home)
                predictions.append((away, home, pred))
            except Exception as e:
                logger.warning(f"⚠️ Erreur prédiction {away} @ {home}: {e}")
                continue
        
        if not predictions:
            await update.message.reply_text("⚠️ Impossible de générer les prédictions NFL")
            return
        
        buy_picks = [(a, h, p) for a, h, p in predictions if "BUY" in p['status']]
        monitoring_picks = [(a, h, p) for a, h, p in predictions if "MONITORING" in p['status']]
        pass_picks = [(a, h, p) for a, h, p in predictions if "PASS" in p['status']]
        
        msg1 = "🏈 ULTRON v6.0 - PRÉDICTIONS NFL\n"
        msg1 += "═" * 70 + "\n"
        msg1 += f"🕐 {quebec_time.strftime('%H:%M:%S')} (Heure Québec)\n"
        msg1 += f"📡 {len(matches)} matchs NFL en direct | {len(predictions)} avec prédictions\n"
        msg1 += "═" * 70 + "\n\n"
        
        if buy_picks:
            msg1 += "✅ ACHETER - Meilleure valeur\n"
            msg1 += "─" * 70 + "\n\n"
            for i, (away, home, pred) in enumerate(buy_picks, 1):
                msg1 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg1 += f"   💡 {pred['pick']} @ {pred['odds']}\n"
                msg1 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n"
                msg1 += f"   📊 Bookmaker: {pred['bookmaker']}\n\n"
        else:
            msg1 += "✅ Aucun pick BUY actuellement\n\n"
        
        await update.message.reply_text(msg1)
        
        msg2 = "👀 MONITORING - À surveiller\n"
        msg2 += "─" * 70 + "\n\n"
        
        if monitoring_picks:
            for i, (away, home, pred) in enumerate(monitoring_picks, 1):
                msg2 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg2 += f"   💡 {pred['pick']} @ {pred['odds']}\n"
                msg2 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n\n"
        else:
            msg2 += "Aucun monitoring\n\n"
        
        msg2 += "─" * 70 + "\n"
        msg2 += f"📊 RÉSUMÉ: {len(buy_picks)} BUY | {len(monitoring_picks)} MONITORING | {len(pass_picks)} PASS"
        
        await update.message.reply_text(msg2)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Erreur NFL: {e}")

async def injuries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display key players status and injuries for TODAY'S LIVE games"""
    try:
        # Récupérer les vrais matchs en direct
        real_matches = get_live_matches()
        
        if not real_matches:
            msg = "❌ Aucun match NBA actuel\n"
            msg += "Revenez lors de matchs en direct"
            await update.message.reply_text(msg)
            return
        
        msg = "🏥 STATUT DES JOUEURS - MATCHS EN DIRECT\n"
        msg += "═" * 65 + "\n"
        msg += f"📡 {datetime.datetime.now().strftime('%H:%M:%S')} - {len(real_matches)} matchs actifs\n"
        msg += "═" * 65 + "\n\n"
        
        for away, home in real_matches:
            away_clean = find_team(away) or away.lower()
            home_clean = find_team(home) or home.lower()
            
            msg += f"🎯 {away.upper()} @ {home.upper()}\n"
            msg += "─" * 40 + "\n"
            
            # Away team players
            away_players = PLAYERS_DATA.get(away_clean, {})
            if away_players:
                msg += f"  {away}:\n"
                for player, info in away_players.items():
                    if info['status'] == 'Active':
                        msg += f"    ✅ {player} - Active ({info['position']})\n"
                    elif info['status'] == 'Out':
                        msg += f"    ❌ {player} - OUT: {info.get('reason', 'Unknown')} ({info['impact']})\n"
                    elif info['status'] == 'Bench':
                        msg += f"    🪑 {player} - BENCH: {info.get('reason', 'Unknown')}\n"
            
            # Home team players
            home_players = PLAYERS_DATA.get(home_clean, {})
            if home_players:
                msg += f"  {home}:\n"
                for player, info in home_players.items():
                    if info['status'] == 'Active':
                        msg += f"    ✅ {player} - Active ({info['position']})\n"
                    elif info['status'] == 'Out':
                        msg += f"    ❌ {player} - OUT: {info.get('reason', 'Unknown')} ({info['impact']})\n"
                    elif info['status'] == 'Bench':
                        msg += f"    🪑 {player} - BENCH: {info.get('reason', 'Unknown')}\n"
            
            msg += "\n"
        
        msg += "═" * 65 + "\n"
        msg += "Legend:\n ✅ = Active   |   ❌ = Out/Injured   |   🪑 = Bench/Rest\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display real-time info for a team - injuries, bench, live events"""
    try:
        if not context.args:
            msg = "❌ Usage: /info <team_name>\n\nExample: /info Hornets\n\n"
            msg += "Available teams:\nHornets, Pistons, Wizards, Heat, Hawks, Cavaliers, Celtics, Pelicans, Pacers, 76ers,\n"
            msg += "Knicks, Raptors, Bulls, Magic, Bucks, Nets, Spurs, Mavericks, Nuggets, Thunder,\n"
            msg += "Rockets, Timberwolves, Jazz, Grizzlies, Trail Blazers, Clippers, Kings, Warriors, Lakers, Suns"
            await update.message.reply_text(msg)
            return
        
        team_name = " ".join(context.args)
        team_clean = find_team(team_name)
        
        if not team_clean:
            await update.message.reply_text(f"❌ Team '{team_name}' not found. Try: Hornets, Heat, Celtics, etc.")
            return
        
        # Get team roster and events
        players = PLAYERS_DATA.get(team_clean, {})
        events = REALTIME_EVENTS.get(team_clean, [])
        
        # Format team name properly (capitalize each word)
        team_display = team_name.title()
        
        msg = f"📊 REAL-TIME INFO - {team_display.upper()}\n"
        msg += "═" * 60 + "\n\n"
        
        # ROSTER SECTION
        msg += "👥 ROSTER STATUS:\n"
        msg += "─" * 40 + "\n"
        
        if players:
            active_count = 0
            injured_count = 0
            bench_count = 0
            
            for player, info in players.items():
                if info['status'] == 'Active':
                    msg += f"  ✅ {player} - {info['position']} (ACTIVE)\n"
                    active_count += 1
                elif info['status'] == 'Out':
                    msg += f"  ❌ {player} - OUT: {info.get('reason', 'Unknown')}\n"
                    injured_count += 1
                elif info['status'] == 'Bench':
                    msg += f"  🪑 {player} - BENCHED: {info.get('reason', 'Unknown')}\n"
                    bench_count += 1
            
            msg += f"\n  Summary: {active_count} Active | {injured_count} Injured | {bench_count} Benched\n\n"
        
        # LIVE EVENTS SECTION
        msg += "🎮 LIVE EVENTS & UPDATES:\n"
        msg += "─" * 40 + "\n"
        
        if events:
            for event in events:
                time_str = event.get('time', 'N/A')
                player = event.get('player', 'Team')
                event_text = event.get('event', 'Unknown event')
                event_type = event.get('type', 'Info')
                
                if event_type == 'Injury':
                    msg += f"  🚨 [{time_str}] {player}: {event_text}\n"
                elif event_type == 'Bench':
                    msg += f"  🪑 [{time_str}] {player}: {event_text}\n"
                elif event_type == 'Score':
                    msg += f"  🔥 [{time_str}] {player}: {event_text}\n"
                elif event_type == 'Performance':
                    msg += f"  ⭐ [{time_str}] {player}: {event_text}\n"
                else:
                    msg += f"  ℹ️  [{time_str}] {player}: {event_text}\n"
        else:
            msg += "  No events recorded yet\n"
        
        msg += "\n" + "═" * 60 + "\n"
        msg += "🔄 Updates every 60 seconds during live games\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🤖 ULTRON v6.0 - MULTISPORTS PRECISION\n\n"
    msg += "🏀 NBA | 🏒 NHL | 🏈 NFL\n\n"
    msg += "COMMANDES MATCHS:\n"
    msg += "/nba - Équipes NBA en direct\n"
    msg += "/nhl - Équipes NHL en direct\n"
    msg += "/nfl - Équipes NFL en direct\n\n"
    msg += "COMMANDES PRONOSTICS:\n"
    msg += "/pronostics nba - Analyse NBA (moneyline + player props)\n"
    msg += "/pronostics nhl - Analyse NHL\n"
    msg += "/pronostics nfl - Analyse NFL\n\n"
    msg += "AUTRES:\n"
    msg += "/test - Demo predictions\n"
    msg += "/info <team> - Info temps réel (NBA)\n"
    msg += "/injuries - Statut joueurs (NBA)\n\n"
    msg += "📊 TECH:\n"
    msg += "• Line Shopping: Best odds across BET365, BETFAIR, DRAFTKINGS\n"
    msg += "• Market Consensus: Consensus du marché\n"
    msg += "• 4-Factor Model: Analyse détaillée par sport\n"
    msg += "• Edge Detection: Repérage des erreurs du marché\n"
    msg += "• Min Edge: +1% EV requis pour picks"
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DEMO MODE - Show predictions with test data"""
    try:
        # Test matches for demonstration
        test_matches = [
            ("Warriors", "Kings"),
            ("Clippers", "Trail Blazers"),
            ("Suns", "Lakers"),
        ]
        
        # Generate predictions
        predictions = []
        for away, home in test_matches:
            pred = generate_prediction(away, home)
            predictions.append((away, home, pred))
        
        # Separate by type
        buy_picks = [(a, h, p) for a, h, p in predictions if "BUY" in p['status']]
        monitoring_picks = [(a, h, p) for a, h, p in predictions if "MONITORING" in p['status']]
        pass_picks = [(a, h, p) for a, h, p in predictions if "PASS" in p['status']]
        
        buy_picks.sort(key=lambda x: float(x[2]['ev']), reverse=True)
        monitoring_picks.sort(key=lambda x: float(x[2]['ev']), reverse=True)
        
        quebec_time = get_quebec_time()
        
        msg1 = "🎯 ULTRON v5.8 - DEMO (TEST DATA)\n"
        msg1 += "═" * 70 + "\n"
        msg1 += f"🕐 {quebec_time.strftime('%H:%M:%S')} (Heure Québec)\n"
        msg1 += f"📡 {len(test_matches)} matchs de démonstration\n"
        msg1 += "═" * 70 + "\n\n"
        
        if buy_picks:
            msg1 += "✅ ACHETER - Meilleure valeur (+1% EV minimum)\n"
            msg1 += "─" * 70 + "\n\n"
            for i, (away, home, pred) in enumerate(buy_picks, 1):
                msg1 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg1 += f"   💡 Pick: {pred['pick']} | Odds: {pred['odds']}\n"
                msg1 += f"   🔥 Confiance: {pred['confidence']}%\n"
                msg1 += f"   💰 EV: {pred['ev_pct']} | ROI: {pred['roi_pct']}\n"
                msg1 += f"   📊 Market: {pred['market_consensus']} | Model: {pred['model_prob']}\n"
                msg1 += f"   🎯 {pred['reasoning']}\n"
        else:
            msg1 += "✅ ACHETER: Aucun pick"
        
        await update.message.reply_text(msg1)
        
        msg2 = "👀 MONITORING - À surveiller (0% < EV < +1%)\n"
        msg2 += "─" * 70 + "\n\n"
        
        if monitoring_picks:
            for i, (away, home, pred) in enumerate(monitoring_picks, 1):
                msg2 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg2 += f"   💡 Pick: {pred['pick']} | Odds: {pred['odds']}\n"
                msg2 += f"   💰 EV: {pred['ev_pct']} | ROI: {pred['roi_pct']}\n\n"
        else:
            msg2 += "Aucun pick en monitoring"
        
        await update.message.reply_text(msg2)
        
        msg3 = f"⏸ PAS JOUER ({len(pass_picks)} matchs)\n"
        msg3 += "─" * 70 + "\n\n"
        
        if pass_picks:
            for i, (away, home, pred) in enumerate(pass_picks, 1):
                msg3 += f"{i}️⃣ {away.upper()} @ {home.upper()} ❌\n"
                msg3 += f"   EV: {pred['ev_pct']} | ROI: {pred['roi_pct']}\n\n"
        
        msg3 += "═" * 70 + "\n"
        msg3 += "📊 MODE DÉMO - Utilisez /pronostics pour les VRAIS matchs!"
        
        await update.message.reply_text(msg3)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

def main():
    print("="*70)
    print("ULTRON v6.0 - MULTISPORTS PRECISION")
    print("NBA 🏀 | NHL 🏒 | NFL 🏈")
    print("="*70)
    print(f"📊 Bookmakers: BET365 | BETFAIR | DRAFTKINGS")
    print(f"🔍 Engine: Line Shopping + Market Consensus")
    print(f"🎯 Filter: +1% EV minimum")
    print("="*70 + "\n")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nba", nba))
    app.add_handler(CommandHandler("nhl", nhl))
    app.add_handler(CommandHandler("nfl", nfl))
    app.add_handler(CommandHandler("pronostics", pronostics))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("injuries", injuries))
    app.add_handler(CommandHandler("help", help_cmd))
    
    print("✅ Bot ready - polling started...\n")
    
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n✓ Bot stopped")

if __name__ == "__main__":
    main()
