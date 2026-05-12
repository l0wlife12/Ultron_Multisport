#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON MULTISPORTS v6.0 - NBA + NHL + NFL
Real matchups with QUEBEC TIMEZONE + INTELLIGENT PREDICTIONS
Multi-league sports betting analysis system
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

# NBA APIs
try:
    from nba_api.live.nba.endpoints import scoreboard, playoffpicture
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    
try:
    from sportsreference.nba.teams import Teams as NBATeams
    SPORTSREFERENCE_AVAILABLE = True
except ImportError:
    SPORTSREFERENCE_AVAILABLE = False

# ML Models for NBA Predictions
try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import TimeSeriesSplit
    import pandas as pd
    SKLEARN_AVAILABLE = True
    ML_MODEL = None  # Sera entraîné au démarrage
except ImportError:
    SKLEARN_AVAILABLE = False

# Player Props Regression Model
try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
    PROPS_MODEL = None  # Sera entraîné au démarrage
except ImportError:
    XGBOOST_AVAILABLE = False

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

# ESPN Context — blessures + stats en temps réel
try:
    from espn_context import (
        get_full_context_all_sports,
        format_injuries_alert,
        get_games_with_context,
        find_game_context,
        format_all_boxscores,
        format_leaders_message,
        get_live_player_props,
        get_team_stats,
        get_live_game_ids,
    )
    ESPN_CONTEXT_AVAILABLE = True
except ImportError:
    ESPN_CONTEXT_AVAILABLE = False
    logger = logging.getLogger(__name__)

# Mémoire des picks — auto-notation des résultats via ESPN
try:
    from pick_memory import (
        save_pick,
        check_and_update_results,
        format_daily_report,
        format_today_recap,
        format_result_notification,
        backup_to_telegram,
        restore_from_telegram,
    )
    PICK_MEMORY_AVAILABLE = True
except ImportError:
    PICK_MEMORY_AVAILABLE = False
    logger = logging.getLogger(__name__)

# Brain — auto-analyse ROI et optimisation des seuils
try:
    from ultron_brain import (
        run_analysis,
        should_send_pick,
        format_brain_report,
        get_model_adjustments,
        load_thresholds as brain_load_thresholds,
    )
    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False
    def get_model_adjustments(sport):   # noqa: E302 — fallback silencieux
        return {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0}

# Ultron v2 — moteur Elo + No-Vig + ESPN + filtre qualité
try:
    from ultron_v2 import (
        UltronV2,
        EloSystem as EloSystemV2,
        format_daily_report as format_v2_report,
    )
    ULTRON_V2_AVAILABLE = True
except ImportError:
    ULTRON_V2_AVAILABLE = False

# ⚠️ IMPORTANT: Sur Railway, SEULEMENT charger variables d'environnement (pas config.env)
# config.env est ignoré par .gitignore donc n'existe pas sur Railway
# Cela évite de charger un ancien token depuis config.env
IS_RAILWAY = os.getenv('RAILWAY_ENVIRONMENT') is not None
if not IS_RAILWAY and os.path.exists('config.env'):
    # En développement local: on peut charger config.env
    load_dotenv('config.env')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not SKLEARN_AVAILABLE:
    logger.warning("⚠️ scikit-learn non disponible - Utilisant modèle statistique simple")

# TIMEZONE QUÉBEC (EDT = UTC-4)
QUEBEC_TZ = pytz.timezone('America/Toronto')

def get_quebec_time() -> datetime.datetime:
    """Retourne l'heure actuelle en fuseau horaire Québec"""
    return datetime.datetime.now(QUEBEC_TZ)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set. Configure it in Railway environment variables.")

TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_CHAT_ID_VIP = os.getenv('TELEGRAM_CHAT_ID_VIP')
ODDS_API_KEY = os.getenv('ODDS_API_KEY')

if TELEGRAM_CHAT_ID:
    logger.info(f"✅ TELEGRAM_CHAT_ID configuré")
if TELEGRAM_CHAT_ID_VIP:
    logger.info(f"✅ TELEGRAM_CHAT_ID_VIP configuré")
if ODDS_API_KEY:
    logger.info(f"✅ ODDS_API_KEY configuré")
else:
    logger.warning("⚠️ ODDS_API_KEY non configuré - cotes en temps réel désactivées")

# Cache des matchs par sport
MATCHES_CACHE_NBA = []
MATCHES_CACHE_NHL = []
MATCHES_CACHE_NFL = []
MATCHES_CACHE_TIME = None

# Cache Odds API — une requête toutes les 4h par sport, seulement avant les matchs
_ODDS_API_CACHE = {}  # sport_key → {"data": [...], "fetched_at": datetime}
_ODDS_API_CACHE_TTL = 14400  # 4 heures
_ODDS_API_SPORT_KEYS = {
    "nba": "basketball_nba",
    "nhl": "icehockey_nhl",
    "nfl": "americanfootball_nfl",
}

# ═══════════════════════════════════════════════════════════════════════════
# NHL TEAMS STATS (2025-2026 Season) - Advanced Metrics
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
    "avalanche_2": {"strength": 80, "gf": 3.22, "ga": 3.12, "wins": 40, "losses": 32, "gp": 82},
    "kraken": {"strength": 76, "gf": 3.10, "ga": 3.15, "wins": 36, "losses": 36, "gp": 82},
}

# ═══════════════════════════════════════════════════════════════════════════
# NFL TEAMS STATS (2025-2026 Season) - Advanced Metrics
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
    ("hurricanes", "avalanche"): {"away_ml": 2.40, "home_ml": 1.55, "total": 6.5, "under": 1.92, "over": 1.88},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.85, "home_ml": 1.95, "total": 6.0, "under": 1.90, "over": 1.90},
    ("rangers", "oilers"): {"away_ml": 2.10, "home_ml": 1.72, "total": 6.5, "under": 1.91, "over": 1.89},
    ("stars", "lightning"): {"away_ml": 1.95, "home_ml": 1.85, "total": 6.0, "under": 1.90, "over": 1.90},
    ("panthers", "capitals"): {"away_ml": 1.60, "home_ml": 2.30, "total": 6.0, "under": 1.91, "over": 1.89},
    ("bruins", "canadiens"): {"away_ml": 1.72, "home_ml": 2.10, "total": 5.5, "under": 1.92, "over": 1.88},
    ("wild", "jets"): {"away_ml": 1.80, "home_ml": 2.00, "total": 6.0, "under": 1.90, "over": 1.90},
    ("kings", "ducks"): {"away_ml": 1.90, "home_ml": 1.90, "total": 5.5, "under": 1.91, "over": 1.89},
}

BETFAIR_ODDS_NHL = {
    ("hurricanes", "avalanche"): {"away_ml": 2.42, "home_ml": 1.57, "total": 6.5, "under": 1.91, "over": 1.89},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.87, "home_ml": 1.93, "total": 6.0, "under": 1.89, "over": 1.91},
    ("rangers", "oilers"): {"away_ml": 2.12, "home_ml": 1.70, "total": 6.5, "under": 1.90, "over": 1.90},
    ("stars", "lightning"): {"away_ml": 1.97, "home_ml": 1.83, "total": 6.0, "under": 1.89, "over": 1.91},
    ("panthers", "capitals"): {"away_ml": 1.62, "home_ml": 2.28, "total": 6.0, "under": 1.90, "over": 1.90},
    ("bruins", "canadiens"): {"away_ml": 1.74, "home_ml": 2.08, "total": 5.5, "under": 1.91, "over": 1.89},
    ("wild", "jets"): {"away_ml": 1.82, "home_ml": 1.98, "total": 6.0, "under": 1.89, "over": 1.91},
    ("kings", "ducks"): {"away_ml": 1.92, "home_ml": 1.88, "total": 5.5, "under": 1.90, "over": 1.90},
}

DRAFTKINGS_ODDS_NHL = {
    ("hurricanes", "avalanche"): {"away_ml": 2.45, "home_ml": 1.53, "total": 6.5, "under": 1.88, "over": 1.92},
    ("maple_leafs", "golden_knights"): {"away_ml": 1.88, "home_ml": 1.92, "total": 6.0, "under": 1.88, "over": 1.92},
    ("rangers", "oilers"): {"away_ml": 2.15, "home_ml": 1.68, "total": 6.5, "under": 1.88, "over": 1.92},
    ("stars", "lightning"): {"away_ml": 1.98, "home_ml": 1.82, "total": 6.0, "under": 1.88, "over": 1.92},
    ("panthers", "capitals"): {"away_ml": 1.65, "home_ml": 2.25, "total": 6.0, "under": 1.88, "over": 1.92},
    ("bruins", "canadiens"): {"away_ml": 1.75, "home_ml": 2.05, "total": 5.5, "under": 1.88, "over": 1.92},
    ("wild", "jets"): {"away_ml": 1.85, "home_ml": 1.95, "total": 6.0, "under": 1.88, "over": 1.92},
    ("kings", "ducks"): {"away_ml": 1.95, "home_ml": 1.85, "total": 5.5, "under": 1.88, "over": 1.92},
}

# ═══════════════════════════════════════════════════════════════════════════
# FOOTBALL ODDS (BET365, BETFAIR, DRAFTKINGS)
# ═══════════════════════════════════════════════════════════════════════════
BET365_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.95, "home_ml": 1.85, "spread": (3.5, 1.91, -3.5, 1.87), "total": 46.5, "under": 1.90, "over": 1.90},
    ("eagles", "ravens"): {"away_ml": 2.20, "home_ml": 1.65, "spread": (-2.5, 1.93, 2.5, 1.85), "total": 44.0, "under": 1.91, "over": 1.89},
    ("cowboys", "patriots"): {"away_ml": 1.72, "home_ml": 2.10, "spread": (4.0, 1.90, -4.0, 1.88), "total": 43.0, "under": 1.90, "over": 1.90},
    ("bills", "dolphins"): {"away_ml": 1.85, "home_ml": 1.95, "spread": (0.0, 1.93, 0.0, 1.85), "total": 45.0, "under": 1.90, "over": 1.90},
    ("packers", "lions"): {"away_ml": 2.15, "home_ml": 1.68, "spread": (-2.0, 1.94, 2.0, 1.84), "total": 44.5, "under": 1.91, "over": 1.89},
    ("bengals", "texans"): {"away_ml": 1.90, "home_ml": 1.90, "spread": (1.5, 1.92, -1.5, 1.86), "total": 43.5, "under": 1.90, "over": 1.90},
    ("chargers", "raiders"): {"away_ml": 1.75, "home_ml": 2.05, "spread": (3.5, 1.91, -3.5, 1.87), "total": 42.0, "under": 1.91, "over": 1.89},
    ("broncos", "seahawks"): {"away_ml": 1.88, "home_ml": 1.92, "spread": (0.5, 1.93, -0.5, 1.85), "total": 41.5, "under": 1.90, "over": 1.90},
}

BETFAIR_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.97, "home_ml": 1.83, "total": 46.5, "under": 1.89, "over": 1.91},
    ("eagles", "ravens"): {"away_ml": 2.22, "home_ml": 1.63, "total": 44.0, "under": 1.90, "over": 1.90},
    ("cowboys", "patriots"): {"away_ml": 1.74, "home_ml": 2.08, "total": 43.0, "under": 1.90, "over": 1.90},
    ("bills", "dolphins"): {"away_ml": 1.87, "home_ml": 1.93, "total": 45.0, "under": 1.89, "over": 1.91},
    ("packers", "lions"): {"away_ml": 2.17, "home_ml": 1.66, "total": 44.5, "under": 1.90, "over": 1.90},
    ("bengals", "texans"): {"away_ml": 1.92, "home_ml": 1.88, "total": 43.5, "under": 1.89, "over": 1.91},
    ("chargers", "raiders"): {"away_ml": 1.77, "home_ml": 2.03, "total": 42.0, "under": 1.90, "over": 1.90},
    ("broncos", "seahawks"): {"away_ml": 1.90, "home_ml": 1.90, "total": 41.5, "under": 1.89, "over": 1.91},
}

DRAFTKINGS_ODDS_NFL = {
    ("chiefs", "49ers"): {"away_ml": 1.98, "home_ml": 1.82, "total": 46.5, "under": 1.88, "over": 1.92},
    ("eagles", "ravens"): {"away_ml": 2.25, "home_ml": 1.60, "total": 44.0, "under": 1.88, "over": 1.92},
    ("cowboys", "patriots"): {"away_ml": 1.76, "home_ml": 2.06, "total": 43.0, "under": 1.88, "over": 1.92},
    ("bills", "dolphins"): {"away_ml": 1.88, "home_ml": 1.92, "total": 45.0, "under": 1.88, "over": 1.92},
    ("packers", "lions"): {"away_ml": 2.20, "home_ml": 1.64, "total": 44.5, "under": 1.88, "over": 1.92},
    ("bengals", "texans"): {"away_ml": 1.95, "home_ml": 1.85, "total": 43.5, "under": 1.88, "over": 1.92},
    ("chargers", "raiders"): {"away_ml": 1.80, "home_ml": 2.00, "total": 42.0, "under": 1.88, "over": 1.92},
    ("broncos", "seahawks"): {"away_ml": 1.92, "home_ml": 1.88, "total": 41.5, "under": 1.88, "over": 1.92},
}

# ═══════════════════════════════════════════════════════════════════════════
# NBA TEAMS STATS (2025-2026 Season) - Advanced Metrics
# ═══════════════════════════════════════════════════════════════════════════
NBA_TEAM_STATS = {
    "celtics": {"strength": 97, "ppg": 118.5, "pa": 108.2, "wins": 62, "losses": 20, "gp": 82},
    "nuggets": {"strength": 95, "ppg": 116.8, "pa": 109.5, "wins": 61, "losses": 21, "gp": 82},
    "warriors": {"strength": 93, "ppg": 115.2, "pa": 110.1, "wins": 59, "losses": 23, "gp": 82},
    "bucks": {"strength": 92, "ppg": 117.3, "pa": 111.2, "wins": 58, "losses": 24, "gp": 82},
    "suns": {"strength": 91, "ppg": 116.5, "pa": 112.3, "wins": 57, "losses": 25, "gp": 82},
    "lakers": {"strength": 89, "ppg": 114.8, "pa": 113.5, "wins": 55, "losses": 27, "gp": 82},
    "heat": {"strength": 87, "ppg": 113.2, "pa": 114.1, "wins": 52, "losses": 30, "gp": 82},
    "mavericks": {"strength": 88, "ppg": 115.5, "pa": 113.2, "wins": 54, "losses": 28, "gp": 82},
    "76ers": {"strength": 86, "ppg": 113.8, "pa": 114.5, "wins": 51, "losses": 31, "gp": 82},
    "kings": {"strength": 84, "ppg": 112.5, "pa": 115.2, "wins": 49, "losses": 33, "gp": 82},
    "nets": {"strength": 82, "ppg": 111.2, "pa": 116.3, "wins": 47, "losses": 35, "gp": 82},
    "cavaliers": {"strength": 85, "ppg": 113.5, "pa": 114.2, "wins": 50, "losses": 32, "gp": 82},
    "grizzlies": {"strength": 83, "ppg": 112.1, "pa": 115.8, "wins": 48, "losses": 34, "gp": 82},
    "raptors": {"strength": 81, "ppg": 110.8, "pa": 116.5, "wins": 46, "losses": 36, "gp": 82},
    "bulls": {"strength": 80, "ppg": 110.2, "pa": 117.1, "wins": 45, "losses": 37, "gp": 82},
    "clippers": {"strength": 86, "ppg": 113.9, "pa": 114.1, "wins": 51, "losses": 31, "gp": 82},
    "knicks": {"strength": 84, "ppg": 112.8, "pa": 115.3, "wins": 49, "losses": 33, "gp": 82},
    "blazers": {"strength": 79, "ppg": 109.5, "pa": 117.8, "wins": 44, "losses": 38, "gp": 82},
    "pelicans": {"strength": 82, "ppg": 111.9, "pa": 116.2, "wins": 47, "losses": 35, "gp": 82},
    "spurs": {"strength": 78, "ppg": 109.1, "pa": 118.2, "wins": 43, "losses": 39, "gp": 82},
}

# ═══════════════════════════════════════════════════════════════════════════
# BASKETBALL ODDS (BET365, BETFAIR, DRAFTKINGS)
# ═══════════════════════════════════════════════════════════════════════════
BET365_ODDS_NBA = {
    ("celtics", "warriors"): {"away_ml": 1.60, "home_ml": 2.30, "total": 217.5, "under": 1.91, "over": 1.89},
    ("nuggets", "lakers"): {"away_ml": 1.75, "home_ml": 2.05, "total": 220.0, "under": 1.91, "over": 1.89},
    ("suns", "bucks"): {"away_ml": 1.88, "home_ml": 1.92, "total": 218.5, "under": 1.90, "over": 1.90},
    ("heat", "mavericks"): {"away_ml": 2.10, "home_ml": 1.70, "total": 215.0, "under": 1.91, "over": 1.89},
    ("76ers", "kings"): {"away_ml": 1.95, "home_ml": 1.85, "total": 216.0, "under": 1.90, "over": 1.90},
    ("nets", "cavaliers"): {"away_ml": 2.20, "home_ml": 1.65, "total": 214.5, "under": 1.91, "over": 1.89},
    ("grizzlies", "raptors"): {"away_ml": 1.72, "home_ml": 2.10, "total": 212.0, "under": 1.91, "over": 1.89},
    ("clippers", "bulls"): {"away_ml": 1.65, "home_ml": 2.15, "total": 213.0, "under": 1.90, "over": 1.90},
}

BETFAIR_ODDS_NBA = {
    ("celtics", "warriors"): {"away_ml": 1.62, "home_ml": 2.28, "total": 217.5, "under": 1.89, "over": 1.91},
    ("nuggets", "lakers"): {"away_ml": 1.77, "home_ml": 2.03, "total": 220.0, "under": 1.89, "over": 1.91},
    ("suns", "bucks"): {"away_ml": 1.90, "home_ml": 1.90, "total": 218.5, "under": 1.89, "over": 1.91},
    ("heat", "mavericks"): {"away_ml": 2.12, "home_ml": 1.68, "total": 215.0, "under": 1.89, "over": 1.91},
    ("76ers", "kings"): {"away_ml": 1.97, "home_ml": 1.83, "total": 216.0, "under": 1.89, "over": 1.91},
    ("nets", "cavaliers"): {"away_ml": 2.22, "home_ml": 1.63, "total": 214.5, "under": 1.89, "over": 1.91},
    ("grizzlies", "raptors"): {"away_ml": 1.74, "home_ml": 2.08, "total": 212.0, "under": 1.89, "over": 1.91},
    ("clippers", "bulls"): {"away_ml": 1.67, "home_ml": 2.13, "total": 213.0, "under": 1.89, "over": 1.91},
}

DRAFTKINGS_ODDS_NBA = {
    ("celtics", "warriors"): {"away_ml": 1.64, "home_ml": 2.26, "total": 217.5, "under": 1.88, "over": 1.92},
    ("nuggets", "lakers"): {"away_ml": 1.79, "home_ml": 2.01, "total": 220.0, "under": 1.88, "over": 1.92},
    ("suns", "bucks"): {"away_ml": 1.92, "home_ml": 1.88, "total": 218.5, "under": 1.88, "over": 1.92},
    ("heat", "mavericks"): {"away_ml": 2.15, "home_ml": 1.66, "total": 215.0, "under": 1.88, "over": 1.92},
    ("76ers", "kings"): {"away_ml": 2.00, "home_ml": 1.80, "total": 216.0, "under": 1.88, "over": 1.92},
    ("nets", "cavaliers"): {"away_ml": 2.25, "home_ml": 1.61, "total": 214.5, "under": 1.88, "over": 1.92},
    ("grizzlies", "raptors"): {"away_ml": 1.76, "home_ml": 2.06, "total": 212.0, "under": 1.88, "over": 1.92},
    ("clippers", "bulls"): {"away_ml": 1.70, "home_ml": 2.10, "total": 213.0, "under": 1.88, "over": 1.92},
}

# ═══════════════════════════════════════════════════════════════════════════
# FONCTIONS POUR CHARGER LES DONNÉES NBA EN DIRECT
# ═══════════════════════════════════════════════════════════════════════════

def load_nba_stats_real_time():
    """Charge les stats NBA réelles depuis sportsreference"""
    if not SPORTSREFERENCE_AVAILABLE:
        logger.warning("⚠️ sportsreference non disponible - Utilising stats par défaut")
        return NBA_TEAM_STATS
    
    try:
        teams_data = {}
        nba_teams = NBATeams()
        
        for team in nba_teams:
            try:
                team_name = team.name.lower().replace(" ", "_").replace("the_", "")
                team_key = None
                
                # Trouver la clé correspondante
                if team_name in NBA_TEAM_STATS:
                    team_key = team_name
                else:
                    # Chercher par alias
                    for key in NBA_TEAM_STATS.keys():
                        if key in team_name or team_name in key:
                            team_key = key
                            break
                
                if team_key:
                    # Charger les vraies stats
                    wins = int(team.wins) if hasattr(team, 'wins') else NBA_TEAM_STATS[team_key]["wins"]
                    losses = int(team.losses) if hasattr(team, 'losses') else NBA_TEAM_STATS[team_key]["losses"]
                    ppg = float(team.points_per_game) if hasattr(team, 'points_per_game') else NBA_TEAM_STATS[team_key]["ppg"]
                    pa = float(team.points_against_per_game) if hasattr(team, 'points_against_per_game') else NBA_TEAM_STATS[team_key]["pa"]
                    
                    strength = int(100 * wins / (wins + losses)) if (wins + losses) > 0 else 50
                    
                    teams_data[team_key] = {
                        "strength": strength,
                        "ppg": ppg,
                        "pa": pa,
                        "wins": wins,
                        "losses": losses,
                        "gp": wins + losses
                    }
                    logger.debug(f"✅ {team_key}: W-L {wins}-{losses} | PPG {ppg:.1f} | PA {pa:.1f}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement {team.name}: {e}")
                continue
        
        if teams_data:
            logger.info(f"✅ {len(teams_data)} équipes NBA chargées depuis sportsreference")
            # Fusionner avec les stats par défaut
            return {**NBA_TEAM_STATS, **teams_data}
        else:
            return NBA_TEAM_STATS
            
    except Exception as e:
        logger.warning(f"⚠️ Erreur sportsreference: {e} - Utilisant stats par défaut")
        return NBA_TEAM_STATS

def get_live_nba_games_api():
    """Récupère les matchs NBA en direct depuis nba_api"""
    if not NBA_API_AVAILABLE:
        logger.warning("⚠️ nba_api non disponible - Utilisant ESPN")
        return None
    
    try:
        sb = scoreboard.ScoreboardV2()
        games = sb.get_data_frames()[0]
        
        if games.empty:
            return None
        
        matches = []
        for _, game in games.iterrows():
            try:
                away_team = game.get('VISITOR_TEAM_NAME', '').strip()
                home_team = game.get('HOME_TEAM_NAME', '').strip()
                game_status = game.get('GAME_STATUS_ID', 0)
                
                # Filtrer les matchs terminés (status = 3)
                if game_status != 3 and away_team and home_team:
                    matches.append((away_team, home_team))
                    logger.debug(f"Matchs NBA trouvé: {away_team} @ {home_team}")
            except Exception as e:
                logger.debug(f"⚠️ Erreur parse match NBA: {e}")
                continue
        
        if matches:
            logger.info(f"✅ {len(matches)} matchs NBA en direct depuis nba_api")
            return matches
        
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur nba_api: {e}")
        return None

# Charger les stats NBA réelles au démarrage (optionnel - peut être lent)
NBA_TEAM_STATS_REAL = NBA_TEAM_STATS

# ═══════════════════════════════════════════════════════════════════════════
# STATS D'ÉQUIPE DYNAMIQUES (ESPN standings) - cache hebdomadaire
# ═══════════════════════════════════════════════════════════════════════════

_TEAM_STATS_CACHE: dict = {}          # {sport: merged_dict}
_TEAM_STATS_CACHE_TIME: dict = {}     # {sport: datetime}
_TEAM_STATS_TTL_SECONDS = 7 * 24 * 3600  # 7 jours

# Clé offensive, clé défensive, seuil de détection "valeur totale" par sport
_TEAM_STAT_KEYS = {
    'NBA': ('ppg', 'pa', 200),
    'NHL': ('gf',  'ga',  10),
    'NFL': ('pf',  'pa',  40),
}


def get_dynamic_team_stats(sport: str) -> dict:
    """
    Retourne les stats d'équipes ESPN à jour (standings hebdomadaires).
    Cache de 7 jours — fallback automatique sur les dicts statiques.
    La clé de sortie est le short key (ex: 'celtics'), identique aux dicts statiques.
    """
    global _TEAM_STATS_CACHE, _TEAM_STATS_CACHE_TIME
    now = datetime.datetime.now()
    cached_time = _TEAM_STATS_CACHE_TIME.get(sport)
    if cached_time and (now - cached_time).total_seconds() < _TEAM_STATS_TTL_SECONDS:
        return _TEAM_STATS_CACHE[sport]

    base = {'NBA': NBA_TEAM_STATS, 'NHL': NHL_TEAM_STATS, 'NFL': NFL_TEAM_STATS}.get(sport, {})
    if not ESPN_CONTEXT_AVAILABLE:
        return base

    try:
        espn_data = get_team_stats(sport)
        if not espn_data:
            return base

        find_fn = {'NBA': find_team_nba, 'NHL': find_team_nhl, 'NFL': find_team_nfl}.get(sport)
        off_key, def_key, threshold = _TEAM_STAT_KEYS.get(sport, ('ppg', 'pa', 200))

        live = {}
        for display_name, stats in espn_data.items():
            short_key = find_fn(display_name) if find_fn else None
            if not short_key:
                continue
            wins    = int(stats.get('wins', 0) or 0)
            losses  = int(stats.get('losses', 0) or 0)
            gp      = max(1, wins + losses)
            raw_for = float(stats.get('points_for', 0) or 0)
            raw_aga = float(stats.get('points_against', 0) or 0)
            off_val = round(raw_for / gp if raw_for > threshold else raw_for, 2)
            def_val = round(raw_aga / gp if raw_aga > threshold else raw_aga, 2)
            live[short_key] = {
                'strength': int((stats.get('win_pct', 0.5) or 0.5) * 100),
                off_key:    off_val,
                def_key:    def_val,
                'wins':     wins,
                'losses':   losses,
                'gp':       gp,
            }

        merged = {**base, **live}
        _TEAM_STATS_CACHE[sport]      = merged
        _TEAM_STATS_CACHE_TIME[sport] = now
        logger.info(f"✅ Stats ESPN {sport}: {len(live)} équipes mises à jour")
        return merged

    except Exception as e:
        logger.warning(f"⚠️ get_dynamic_team_stats {sport}: {e}")
        return base


# ═══════════════════════════════════════════════════════════════════════════
# NBA PLAYER PROPS - STARS OVER/UNDER LINES
# ═══════════════════════════════════════════════════════════════════════════

# ── Props joueurs dynamiques (ESPN) ─────────────────────────────────────────
# Cache journalier : rafraîchi une fois par jour depuis l'API ESPN leaders.
# Fallback automatique vers NBA_PLAYER_PROPS si ESPN est indisponible.
_PLAYER_PROPS_CACHE: dict = {}
_PLAYER_PROPS_CACHE_DATE: str = ""


def get_dynamic_player_props() -> dict:
    """
    Retourne les props joueurs NBA à jour (moyennes de saison ESPN).
    Cache journalier — un seul appel ESPN par journée.
    Fallback sur NBA_PLAYER_PROPS statique si ESPN est indisponible.
    """
    global _PLAYER_PROPS_CACHE, _PLAYER_PROPS_CACHE_DATE
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if _PLAYER_PROPS_CACHE and _PLAYER_PROPS_CACHE_DATE == today:
        return _PLAYER_PROPS_CACHE
    if ESPN_CONTEXT_AVAILABLE:
        try:
            live = get_live_player_props('NBA', max_players=60)
            if live:
                _PLAYER_PROPS_CACHE      = live
                _PLAYER_PROPS_CACHE_DATE = today
                logger.info(f"✅ Props ESPN chargés: {len(live)} joueurs NBA")
                return _PLAYER_PROPS_CACHE
        except Exception as _e:
            logger.warning(f"⚠️ Props ESPN erreur: {_e}")
    logger.warning("⚠️ Props ESPN indisponibles — données statiques utilisées")
    return NBA_PLAYER_PROPS


NBA_PLAYER_PROPS = {
    # EASTERN CONFERENCE - STARS
    "Jayson Tatum": {
        "team": "Celtics",
        "position": "SF",
        "props": {
            "points": {"line": 27.5, "over": 1.90, "under": 1.90},
            "rebounds": {"line": 8.5, "over": 1.88, "under": 1.92},
            "assists": {"line": 2.5, "over": 1.95, "under": 1.85},
        }
    },
    "Luka Doncic": {
        "team": "Mavericks",
        "position": "PG",
        "props": {
            "points": {"line": 33.5, "over": 1.88, "under": 1.92},
            "rebounds": {"line": 9.5, "over": 1.90, "under": 1.90},
            "assists": {"line": 8.5, "over": 1.88, "under": 1.92},
        }
    },
    "Devin Booker": {
        "team": "Suns",
        "position": "SG",
        "props": {
            "points": {"line": 27.5, "over": 1.92, "under": 1.88},
            "rebounds": {"line": 4.5, "over": 1.95, "under": 1.85},
            "assists": {"line": 7.5, "over": 1.90, "under": 1.90},
        }
    },
    "Giannis Antetokounmpo": {
        "team": "Bucks",
        "position": "PF",
        "props": {
            "points": {"line": 30.5, "over": 1.88, "under": 1.92},
            "rebounds": {"line": 11.5, "over": 1.90, "under": 1.90},
            "assists": {"line": 5.5, "over": 1.92, "under": 1.88},
        }
    },
    
    # WESTERN CONFERENCE - STARS
    "LeBron James": {
        "team": "Lakers",
        "position": "SF",
        "props": {
            "points": {"line": 25.5, "over": 1.90, "under": 1.90},
            "rebounds": {"line": 7.5, "over": 1.88, "under": 1.92},
            "assists": {"line": 8.5, "over": 1.90, "under": 1.90},
        }
    },
    "Stephen Curry": {
        "team": "Warriors",
        "position": "PG",
        "props": {
            "points": {"line": 28.5, "over": 1.88, "under": 1.92},
            "rebounds": {"line": 4.5, "over": 1.92, "under": 1.88},
            "assists": {"line": 6.5, "over": 1.90, "under": 1.90},
        }
    },
    "Kevin Durant": {
        "team": "Suns",
        "position": "SF",
        "props": {
            "points": {"line": 28.5, "over": 1.90, "under": 1.90},
            "rebounds": {"line": 6.5, "over": 1.88, "under": 1.92},
            "assists": {"line": 2.5, "over": 1.92, "under": 1.88},
        }
    },
    "Anthony Davis": {
        "team": "Lakers",
        "position": "PF",
        "props": {
            "points": {"line": 25.5, "over": 1.92, "under": 1.88},
            "rebounds": {"line": 10.5, "over": 1.88, "under": 1.92},
            "assists": {"line": 2.5, "over": 1.95, "under": 1.85},
        }
    },
    "Shai Gilgeous-Alexander": {
        "team": "Thunder",
        "position": "SG",
        "props": {
            "points": {"line": 29.5, "over": 1.90, "under": 1.90},
            "rebounds": {"line": 5.5, "over": 1.90, "under": 1.90},
            "assists": {"line": 6.5, "over": 1.88, "under": 1.92},
        }
    },
    "Damian Lillard": {
        "team": "Bucks",
        "position": "PG",
        "props": {
            "points": {"line": 24.5, "over": 1.88, "under": 1.92},
            "rebounds": {"line": 2.5, "over": 1.92, "under": 1.88},
            "assists": {"line": 6.5, "over": 1.90, "under": 1.90},
        }
    },
    "Nikola Jokic": {
        "team": "Nuggets",
        "position": "C",
        "props": {
            "points": {"line": 24.5, "over": 1.90, "under": 1.90},
            "rebounds": {"line": 11.5, "over": 1.88, "under": 1.92},
            "assists": {"line": 9.5, "over": 1.90, "under": 1.90},
        }
    },
}

def get_live_matches_nhl() -> list:
    """Récupère les matchs NHL en direct (ESPN API)"""
    global MATCHES_CACHE_NHL, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NHL and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
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
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NHL = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    return daily_matches
        
        logger.info("ℹ️ Aucun match NHL dans les 7 prochains jours (hors saison)")
        MATCHES_CACHE_NHL = []
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return []
    
    except Exception as e:
        logger.error(f"❌ Erreur NHL: {e}")
        return []

def get_live_matches_nfl() -> list:
    """Récupère les matchs NFL en direct (ESPN API)"""
    global MATCHES_CACHE_NFL, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NFL and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
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
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NFL = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    return daily_matches
        
        # Aucun match réel trouvé — ne jamais utiliser de faux matchs
        logger.info("ℹ️ Aucun match NFL dans les 7 prochains jours (hors saison)")
        MATCHES_CACHE_NFL = []
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return []
    
    except Exception as e:
        logger.error(f"❌ Erreur NFL: {e}")
        return []

def get_live_matches_nba() -> list:
    """Récupère les matchs NBA en direct (nba_api > ESPN > DÉMO)"""
    global MATCHES_CACHE_NBA, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NBA and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NBA
    
    # Essayer nba_api d'abord (données officielles)
    if NBA_API_AVAILABLE:
        try:
            matches = get_live_nba_games_api()
            if matches:
                MATCHES_CACHE_NBA = matches
                MATCHES_CACHE_TIME = datetime.datetime.now()
                logger.info(f"✅ {len(matches)} matchs NBA depuis nba_api")
                return matches
        except Exception as e:
            logger.debug(f"⚠️ nba_api erreur: {e}")
    
    # Fallback sur ESPN API
    try:
        today = datetime.datetime.now()
        
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
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
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NBA = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    logger.info(f"✅ {len(daily_matches)} matchs NBA depuis ESPN")
                    return daily_matches
        
        logger.info("ℹ️ Aucun match NBA trouvé sur ESPN (hors saison?)")
    
    except Exception as e:
        logger.error(f"❌ Erreur ESPN NBA: {e}")
    
    return []

def find_team_nhl(name_input: str) -> str | None:
    """Trouve une équipe NHL par son nom - avec table de correspondance"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    
    # Table de correspondance explicite pour ESPN
    team_aliases = {
        "rangers": ["new_york_rangers", "ny_rangers", "rangers"],
        "hurricanes": ["carolina_hurricanes", "hurricanes"],
        "avalanche": ["colorado_avalanche", "avalanche"],
        "maple_leafs": ["toronto_maple_leafs", "maple_leafs", "toronto_mapple_leafs"],
        "oilers": ["edmonton_oilers", "oilers"],
        "golden_knights": ["vegas_golden_knights", "golden_knights"],
        "stars": ["dallas_stars", "stars"],
        "lightning": ["tampa_bay_lightning", "lightning"],
        "panthers": ["florida_panthers", "panthers"],
        "capitals": ["washington_capitals", "capitals"],
        "bruins": ["boston_bruins", "bruins"],
        "penguins": ["pittsburgh_penguins", "penguins"],
        "sabres": ["buffalo_sabres", "sabres"],
        "isles": ["new_york_islanders", "islanders", "isles"],
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
    
    # Chercher dans les aliases
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    # Fallback sur la recherche dans le dictionnaire
    for team_key in NHL_TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    logger.warning(f"⚠️ Équipe NHL non trouvée: {name_input}")
    return None

def find_team_nfl(name_input: str) -> str | None:
    """Trouve une équipe NFL par son nom - avec table de correspondance"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    
    # Table de correspondance explicite pour ESPN
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
    
    # Chercher dans les aliases
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    # Fallback sur la recherche dans le dictionnaire
    for team_key in NFL_TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    logger.warning(f"⚠️ Équipe NFL non trouvée: {name_input}")
    return None

def find_team_nba(name_input: str) -> str | None:
    """Trouve une équipe NBA par son nom - avec table de correspondance"""
    name_clean = name_input.lower().replace("the ", "").replace(" ", "_").strip()
    
    # Table de correspondance explicite pour ESPN
    team_aliases = {
        "celtics": ["boston_celtics", "celtics"],
        "warriors": ["golden_state_warriors", "warriors"],
        "nuggets": ["denver_nuggets", "nuggets"],
        "suns": ["phoenix_suns", "suns"],
        "lakers": ["los_angeles_lakers", "lakers"],
        "heat": ["miami_heat", "heat"],
        "mavericks": ["dallas_mavericks", "mavericks"],
        "bucks": ["milwaukee_bucks", "bucks"],
        "knicks": ["new_york_knicks", "knicks", "new_york_knicks"],
        "76ers": ["philadelphia_76ers", "philadelphia_sixers", "76ers"],
        "clippers": ["los_angeles_clippers", "clippers"],
        "kings": ["sacramento_kings", "kings"],
        "raptors": ["toronto_raptors", "raptors"],
        "cavaliers": ["cleveland_cavaliers", "cavaliers"],
        "bulls": ["chicago_bulls", "bulls"],
        "pelicans": ["new_orleans_pelicans", "pelicans"],
        "grizzlies": ["memphis_grizzlies", "grizzlies"],
        "nets": ["brooklyn_nets", "nets"],
        "blazers": ["portland_trail_blazers", "blazers"],
        "spurs": ["san_antonio_spurs", "spurs"],
    }
    
    # Chercher dans les aliases
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if alias == name_clean or name_clean in alias or alias in name_clean:
                return team_key
    
    # Fallback sur la recherche dans le dictionnaire
    for team_key in NBA_TEAM_STATS.keys():
        if team_key in name_clean or name_clean in team_key:
            return team_key
    
    logger.warning(f"⚠️ Équipe NBA non trouvée: {name_input}")
    return None

def get_best_odds_nhl(away_team: str, home_team: str) -> dict:
    """LINE SHOPPING pour NHL"""
    away_clean = find_team_nhl(away_team) or away_team.lower()
    home_clean = find_team_nhl(home_team) or home_team.lower()
    
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    bookmakers = [
        ("BET365", BET365_ODDS_NHL),
        ("BETFAIR", BETFAIR_ODDS_NHL),
        ("DRAFTKINGS", DRAFTKINGS_ODDS_NHL),
    ]
    
    # Cotes par défaut basées sur la force relative  
    _nhl_ts = get_dynamic_team_stats('NHL')
    away_stats = _nhl_ts.get(away_clean, {"strength": 75})
    home_stats = _nhl_ts.get(home_clean, {"strength": 75})
    
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
    
    logger.debug(f"Cotes pour {away_clean} @ {home_clean}: AWAY={best_away['odds']:.2f} ({best_away['book']}), HOME={best_home['odds']:.2f} ({best_home['book']})")
    
    return {
        "away_ml": best_away["odds"],
        "home_ml": best_home["odds"],
        "away_book": best_away["book"],
        "home_book": best_home["book"],
    }

def get_best_odds_nfl(away_team: str, home_team: str) -> dict:
    """LINE SHOPPING pour NFL"""
    away_clean = find_team_nfl(away_team) or away_team.lower()
    home_clean = find_team_nfl(home_team) or home_team.lower()
    
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    bookmakers = [
        ("BET365", BET365_ODDS_NFL),
        ("BETFAIR", BETFAIR_ODDS_NFL),
        ("DRAFTKINGS", DRAFTKINGS_ODDS_NFL),
    ]
    
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
    
    return {
        "away_ml": best_away["odds"],
        "home_ml": best_home["odds"],
        "away_book": best_away["book"],
        "home_book": best_home["book"],
    }

def get_best_odds_nba(away_team: str, home_team: str) -> dict:
    """LINE SHOPPING pour NBA"""
    away_clean = find_team_nba(away_team) or away_team.lower()
    home_clean = find_team_nba(home_team) or home_team.lower()
    
    key_forward = (away_clean, home_clean)
    key_reverse = (home_clean, away_clean)
    
    bookmakers = [
        ("BET365", BET365_ODDS_NBA),
        ("BETFAIR", BETFAIR_ODDS_NBA),
        ("DRAFTKINGS", DRAFTKINGS_ODDS_NBA),
    ]
    
    # Cotes par défaut basées sur la force relative  
    _nba_ts = get_dynamic_team_stats('NBA')
    away_stats = _nba_ts.get(away_clean, {"strength": 85})
    home_stats = _nba_ts.get(home_clean, {"strength": 85})
    
    strength_diff = away_stats["strength"] - home_stats["strength"]
    if strength_diff > 5:
        best_away = {"odds": 1.75, "book": "DEFAULT"}
        best_home = {"odds": 2.05, "book": "DEFAULT"}
    elif strength_diff < -5:
        best_away = {"odds": 2.05, "book": "DEFAULT"}
        best_home = {"odds": 1.75, "book": "DEFAULT"}
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
    
    logger.debug(f"Cotes pour {away_clean} @ {home_clean}: AWAY={best_away['odds']:.2f} ({best_away['book']}), HOME={best_home['odds']:.2f} ({best_home['book']})")
    
    return {
        "away_ml": best_away["odds"],
        "home_ml": best_home["odds"],
        "away_book": best_away["book"],
        "home_book": best_home["book"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# ODDS API EN TEMPS RÉEL — économie maximale de requêtes
# Appelé UNIQUEMENT depuis auto_send_pronostics (avant-match)
# Cache 4h par sport = max ~3 requêtes/jour si matchs existent
# ═══════════════════════════════════════════════════════════════════════════

def fetch_odds_api(sport_key: str) -> list:
    """
    Appelle The Odds API une seule fois par tranche de 4h par sport.
    Retourne la liste brute d'événements avec cotes (h2h + spreads + totals).
    Retourne [] si clé absente, quota dépassé ou erreur réseau.
    """
    global _ODDS_API_CACHE
    if not ODDS_API_KEY:
        return []

    now = datetime.datetime.now()
    cached = _ODDS_API_CACHE.get(sport_key)
    if cached:
        elapsed = (now - cached["fetched_at"]).total_seconds()
        if elapsed < _ODDS_API_CACHE_TTL:
            logger.debug(f"📦 Odds API cache {sport_key} ({int(elapsed/60)} min ago)")
            return cached["data"]

    api_sport = _ODDS_API_SPORT_KEYS.get(sport_key)
    if not api_sport:
        return []

    try:
        url = (
            f"https://api.the-odds-api.com/v4/sports/{api_sport}/odds/"
            f"?apiKey={ODDS_API_KEY}"
            f"&regions=us"
            f"&markets=h2h,spreads,totals"
            f"&oddsFormat=decimal"
            f"&dateFormat=iso"
        )
        resp = requests.get(url, timeout=10)
        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")

        if resp.status_code == 200:
            data = resp.json()
            _ODDS_API_CACHE[sport_key] = {"data": data, "fetched_at": now}
            logger.info(f"✅ Odds API {sport_key}: {len(data)} matchs | restantes={remaining} utilisées={used}")
            return data
        elif resp.status_code == 401:
            logger.error("❌ Odds API: clé invalide (401)")
        elif resp.status_code == 429:
            logger.warning("⚠️ Odds API: quota mensuel dépassé (429)")
        else:
            logger.warning(f"⚠️ Odds API {sport_key}: HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"❌ Odds API erreur {sport_key}: {e}")

    return []


def get_live_odds_for_match(away_team: str, home_team: str, api_events: list) -> dict:
    """
    Cherche les cotes en temps réel pour un match dans la réponse Odds API.
    Retourne dict avec ml_away, ml_home, spread_pick, spread_odds, ou_pick, ou_odds
    ou dict vide si introuvable.
    """
    if not api_events:
        return {}

    away_parts = [p for p in away_team.lower().split() if len(p) > 3]
    home_parts = [p for p in home_team.lower().split() if len(p) > 3]

    best_event = None
    best_score = 0

    for event in api_events:
        ev_away = event.get("away_team", "").lower()
        ev_home = event.get("home_team", "").lower()
        score = 0
        for p in away_parts:
            if p in ev_away: score += 2
            if p in ev_home: score += 1  # inversé possible
        for p in home_parts:
            if p in ev_home: score += 2
            if p in ev_away: score += 1
        if score > best_score:
            best_score = score
            best_event = event

    if not best_event or best_score < 2:
        return {}

    ml_away, ml_home = None, None
    spread_pick, spread_odds = "", "1.91"
    ou_pick, ou_odds = "", "1.91"

    # Priorité bookmakers US
    priority = ["draftkings", "fanduel", "betmgm", "bet365", "bovada", "pointsbet"]
    bookmakers = sorted(
        best_event.get("bookmakers", []),
        key=lambda b: priority.index(b["key"]) if b["key"] in priority else 99
    )

    for bk in bookmakers:
        for market in bk.get("markets", []):
            mkey = market["key"]
            outcomes = market.get("outcomes", [])

            if mkey == "h2h" and ml_away is None:
                for o in outcomes:
                    name = o["name"].lower()
                    if any(p in name for p in away_parts):
                        ml_away = o["price"]
                    elif any(p in name for p in home_parts):
                        ml_home = o["price"]

            elif mkey == "spreads" and not spread_pick:
                for o in outcomes:
                    name = o["name"].lower()
                    pt = o.get("point", 0)
                    if any(p in name for p in away_parts):
                        sign = "+" if pt > 0 else ""
                        spread_pick = f"{away_team.upper()} {sign}{pt}"
                        spread_odds = f"{o['price']:.2f}"
                        break

            elif mkey == "totals" and not ou_pick:
                for o in outcomes:
                    if o["name"] == "Over":
                        pt = o.get("point", 0)
                        ou_pick = f"OVER {pt}"
                        ou_odds = f"{o['price']:.2f}"
                        break

        if ml_away and ml_home and spread_pick and ou_pick:
            break

    if ml_away is None or ml_home is None:
        return {}

    return {
        "ml_away": ml_away,
        "ml_home": ml_home,
        "spread_pick": spread_pick,
        "spread_odds": spread_odds,
        "ou_pick": ou_pick,
        "ou_odds": ou_odds,
    }


def generate_prediction_nhl(away_team: str, home_team: str) -> dict:
    """Génère une prédiction pour un match NHL"""
    away_clean = find_team_nhl(away_team) or away_team.lower()
    home_clean = find_team_nhl(home_team) or home_team.lower()
    
    _nhl_ts = get_dynamic_team_stats('NHL')
    away_stats = _nhl_ts.get(away_clean, {"strength": 75, "gf": 3.0, "ga": 3.0, "wins": 30, "losses": 30})
    home_stats = _nhl_ts.get(home_clean, {"strength": 75, "gf": 3.0, "ga": 3.0, "wins": 30, "losses": 30})
    
    odds_data = get_best_odds_nhl(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    
    # Calcul du modèle 4-facteurs pour le hockey
    away_gf_diff = away_stats["gf"] - home_stats["ga"]
    home_gf_diff = home_stats["gf"] - away_stats["ga"]
    
    point_diff = away_gf_diff - home_gf_diff - 0.3  # Avantage route
    
    try:
        win_prob_away = 1 / (1 + math.exp(-point_diff / 1.8))
    except Exception:
        win_prob_away = 0.5 + (point_diff / 3.0)
    
    win_prob_away = max(0.05, min(0.95, win_prob_away))
    
    # ── Paramètres appris par Ultron Brain (calibration auto) ────────────
    _adj_nhl      = get_model_adjustments("NHL")
    _model_w_nhl  = _adj_nhl.get("model_weight", 0.50)
    _conf_cal_nhl = _adj_nhl.get("confidence_scale", 1.0)
    _home_d_nhl   = _adj_nhl.get("home_advantage_delta", 0.0)
    # Correction avantage domicile (win_prob_away = prob visiteur):
    # home_delta > 0 → domicile performe + → réduire prob visiteur
    win_prob_away = max(0.05, min(0.95, win_prob_away - _home_d_nhl))

    # Consensus du marché
    market_away_avg = (1.0 / best_away_ml + 1.0 / best_home_ml)
    market_consensus_away = (1.0 / best_away_ml) / market_away_avg
    
    blended_prob = (_model_w_nhl * win_prob_away) + ((1.0 - _model_w_nhl) * market_consensus_away)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    # EV calculation
    ev_away = (best_away_ml - 1.0) * blended_prob - (1.0 - blended_prob)
    ev_home = (best_home_ml - 1.0) * (1.0 - blended_prob) - blended_prob
    
    logger.debug(f"{away_team.upper()} @ {home_team.upper()}: {away_clean}/{home_clean} | Cotes: {best_away_ml:.2f}/{best_home_ml:.2f} | Blended: {blended_prob:.1%} | EV: {ev_away:.4f}/{ev_home:.4f}")
    
    if ev_away > ev_home:
        pick = f"{away_team.upper()} ML"
        odds = best_away_ml
        confidence = int(min(97, max(50, blended_prob * 100 * _conf_cal_nhl)))
        ev = ev_away
        book = odds_data["away_book"]
    else:
        pick = f"{home_team.upper()} ML"
        odds = best_home_ml
        confidence = int(min(97, max(50, (1.0 - blended_prob) * 100 * _conf_cal_nhl)))
        ev = ev_home
        book = odds_data["home_book"]
    
    if ev > 0.01:
        status = "✅ BUY"
    elif ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"

    # ── PUCK LINE (±1.5) ──────────────────────────────────────────────────
    # Favoris fort (>60%) : on les joue -1.5 | Underdogs : +1.5
    if blended_prob > 0.60:
        spread_pick = f"{away_team.upper()} -1.5"
        spread_conf = min(72, int(blended_prob * 100))
        spread_odds = 2.10
    elif blended_prob < 0.40:
        spread_pick = f"{home_team.upper()} -1.5"
        spread_conf = min(72, int((1.0 - blended_prob) * 100))
        spread_odds = 2.10
    else:
        # Match serré → jouer le favori +1.5 (valeur sur l'underdog)
        if ev_away > ev_home:
            spread_pick = f"{away_team.upper()} +1.5"
        else:
            spread_pick = f"{home_team.upper()} +1.5"
        spread_conf = 58
        spread_odds = 1.65

    # ── O/U (Total buts) ──────────────────────────────────────────────────
    projected_total = away_stats["gf"] + home_stats["gf"]
    ou_line = 5.5
    if projected_total > ou_line:
        ou_pick = f"OVER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 15 + 50))
    else:
        ou_pick = f"UNDER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 15 + 50))
    ou_odds = 1.909

    return {
        "pick": pick,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
        "ev": f"{ev:.4f}",
        "ev_pct": f"{ev*100:.2f}%",
        "status": status,
        "bookmaker": book,
        # ML
        "ml_pick": pick,
        "ml_odds": f"{odds:.2f}",
        "ml_confidence": confidence,
        "ml_ev_pct": f"{ev*100:.2f}%",
        # Puck Line
        "spread_pick": spread_pick,
        "spread_odds": f"{spread_odds:.2f}",
        "spread_confidence": spread_conf,
        # O/U
        "ou_pick": ou_pick,
        "ou_odds": f"{ou_odds:.2f}",
        "ou_confidence": ou_conf,
    }

def generate_prediction_nfl(away_team: str, home_team: str) -> dict:
    """Génère une prédiction pour un match NFL"""
    away_clean = find_team_nfl(away_team) or away_team.lower()
    home_clean = find_team_nfl(home_team) or home_team.lower()
    
    _nfl_ts = get_dynamic_team_stats('NFL')
    away_stats = _nfl_ts.get(away_clean, {"strength": 80, "pf": 25.0, "pa": 23.0, "wins": 8, "losses": 9})
    home_stats = _nfl_ts.get(home_clean, {"strength": 80, "pf": 25.0, "pa": 23.0, "wins": 8, "losses": 9})
    
    odds_data = get_best_odds_nfl(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    
    # Calcul du modèle 4-facteurs pour le football
    away_pf_diff = away_stats["pf"] - home_stats["pa"]
    home_pf_diff = home_stats["pf"] - away_stats["pa"]
    
    point_diff = away_pf_diff - home_pf_diff - 2.5  # Avantage route
    
    try:
        win_prob_away = 1 / (1 + math.exp(-point_diff / 14.0))
    except Exception:
        win_prob_away = 0.5 + (point_diff / 80.0)
    
    win_prob_away = max(0.05, min(0.95, win_prob_away))
    
    # ── Paramètres appris par Ultron Brain (calibration auto) ────────────
    _adj_nfl      = get_model_adjustments("NFL")
    _model_w_nfl  = _adj_nfl.get("model_weight", 0.50)
    _conf_cal_nfl = _adj_nfl.get("confidence_scale", 1.0)
    _home_d_nfl   = _adj_nfl.get("home_advantage_delta", 0.0)
    win_prob_away = max(0.05, min(0.95, win_prob_away - _home_d_nfl))

    # Consensus du marché
    market_away_avg = (1.0 / best_away_ml + 1.0 / best_home_ml)
    market_consensus_away = (1.0 / best_away_ml) / market_away_avg
    
    blended_prob = (_model_w_nfl * win_prob_away) + ((1.0 - _model_w_nfl) * market_consensus_away)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    # EV calculation
    ev_away = (best_away_ml - 1.0) * blended_prob - (1.0 - blended_prob)
    ev_home = (best_home_ml - 1.0) * (1.0 - blended_prob) - blended_prob
    
    if ev_away > ev_home:
        pick = f"{away_team.upper()} ML"
        odds = best_away_ml
        confidence = int(min(97, max(50, blended_prob * 100 * _conf_cal_nfl)))
        ev = ev_away
        book = odds_data["away_book"]
    else:
        pick = f"{home_team.upper()} ML"
        odds = best_home_ml
        confidence = int(min(97, max(50, (1.0 - blended_prob) * 100 * _conf_cal_nfl)))
        ev = ev_home
        book = odds_data["home_book"]
    
    if ev > 0.01:
        status = "✅ BUY"
    elif ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"

    # ━━ SPREAD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # point_diff > 0 → away favori
    raw_spread = round(point_diff * 2) / 2  # arrondir au 0.5 près
    if raw_spread > 0:
        spread_pick = f"{away_team.upper()} -{raw_spread}"
        spread_conf = min(72, int(blended_prob * 100) + 5)
    elif raw_spread < 0:
        spread_pick = f"{home_team.upper()} -{abs(raw_spread)}"
        spread_conf = min(72, int((1.0 - blended_prob) * 100) + 5)
    else:
        spread_pick = f"{home_team.upper()} PK"
        spread_conf = 50
    spread_odds = 1.909

    # ━━ O/U (Total) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    projected_total = away_stats["pf"] + home_stats["pf"]
    ou_line = 45.5  # ligne typique NFL
    if projected_total > ou_line:
        ou_pick = f"OVER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 3 + 50))
    else:
        ou_pick = f"UNDER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 3 + 50))
    ou_odds = 1.909

    return {
        "pick": pick,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
        "ev": f"{ev:.4f}",
        "ev_pct": f"{ev*100:.2f}%",
        "status": status,
        "bookmaker": book,
        # ML
        "ml_pick": pick,
        "ml_odds": f"{odds:.2f}",
        "ml_confidence": confidence,
        "ml_ev_pct": f"{ev*100:.2f}%",
        # Spread
        "spread_pick": spread_pick,
        "spread_odds": f"{spread_odds:.2f}",
        "spread_confidence": spread_conf,
        # O/U
        "ou_pick": ou_pick,
        "ou_odds": f"{ou_odds:.2f}",
        "ou_confidence": ou_conf,
    }
# ═══════════════════════════════════════════════════════════════════════════

def implied_probability(decimal_odds: float) -> float:
    """Convertit une cote décimale en probabilité implicite"""
    if decimal_odds <= 1:
        return 0.0
    return 1 / decimal_odds

def expected_value(my_prob: float, decimal_odds: float) -> float:
    """Calcule l'EV d'un pari
    
    EV positif = pari intéressant
    EV = (probabilité * (cote - 1)) - (1 - probabilité)
    """
    if decimal_odds <= 1 or not (0 <= my_prob <= 1):
        return 0.0
    return (my_prob * (decimal_odds - 1)) - (1 - my_prob)

def kelly_stake(my_prob: float, decimal_odds: float, bankroll: float, fraction: float = 0.5) -> float:
    """Mise optimale selon le demi-Kelly (fraction=0.5)
    
    Kelly = (b*p - q) / b où:
    - b = cote - 1
    - p = probabilité de victoire
    - q = 1 - p
    - demi-Kelly = kelly * 0.5 pour réduire la variance
    """
    if decimal_odds <= 1 or not (0 < my_prob < 1) or bankroll <= 0:
        return 0.0
    
    b = decimal_odds - 1
    q = 1 - my_prob
    kelly = (b * my_prob - q) / b
    half_kelly = kelly * fraction
    return max(0, half_kelly * bankroll)

# ═══════════════════════════════════════════════════════════════════════════
# ML MODEL FOR NBA PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════════

def build_nba_features(away_team, home_team):
    """Construit les features pour le modèle ML NBA"""
    if not SKLEARN_AVAILABLE:
        return None
    
    away_clean = find_team_nba(away_team) or away_team.lower()
    home_clean = find_team_nba(home_team) or home_team.lower()
    
    _nba_ts = get_dynamic_team_stats('NBA')
    away_stats = _nba_ts.get(away_clean, {"strength": 85, "ppg": 115.0, "pa": 112.0, "wins": 40})
    home_stats = _nba_ts.get(home_clean, {"strength": 85, "ppg": 115.0, "pa": 112.0, "wins": 40})
    
    try:
        # Features principales
        features_dict = {
            'home_netrtg_weighted': home_stats.get("ppg", 115.0) - home_stats.get("pa", 112.0),
            'away_netrtg_weighted': away_stats.get("ppg", 115.0) - away_stats.get("pa", 112.0),
            'home_rest_days': 2.0,  # Par défaut 2 jours de repos
            'away_rest_days': 1.5,  # Équipe à l'extérieur généralement moins reposée
            'rest_differential': 0.5,
            'home_injury_adjustment': 1.0,  # 1.0 = pas de blessure
            'away_injury_adjustment': 1.0,
            'home_home_netrtg': home_stats.get("ppg", 115.0) - home_stats.get("pa", 112.0),
            'away_away_netrtg': away_stats.get("ppg", 115.0) - away_stats.get("pa", 112.0) - 2.5,  # Pénalité route
            'h2h_last_8': 0.50,  # 50% par défaut
        }
        
        return pd.DataFrame([features_dict])
    except Exception as e:
        logger.warning(f"⚠️ Erreur construction features: {e}")
        return None

def train_nba_model():
    """Entraîne le modèle GradientBoosting pour NBA"""
    global ML_MODEL
    
    if not SKLEARN_AVAILABLE:
        logger.warning("⚠️ scikit-learn non disponible")
        return False
    
    try:
        logger.info("🤖 Entraînement du modèle ML NBA...")
        
        # Créer des données d'entraînement synthétiques basées sur les équipes
        training_data = []
        
        teams = list(NBA_TEAM_STATS.keys())
        for i, home_team in enumerate(teams[:10]):  # Top 10 équipes
            for j, away_team in enumerate(teams[:10]):
                if home_team != away_team:
                    features = build_nba_features(away_team, home_team)
                    if features is not None:
                        home_strength = NBA_TEAM_STATS[home_team]["strength"]
                        away_strength = NBA_TEAM_STATS[away_team]["strength"]
                        
                        # Victoire domicile probable si home_strength > away_strength
                        home_win = 1 if home_strength > away_strength else 0
                        features['target'] = home_win
                        training_data.append(features)
        
        if not training_data:
            logger.warning("⚠️ Pas assez de données d'entraînement")
            return False
        
        X = pd.concat(training_data, ignore_index=True).drop('target', axis=1)
        y = pd.concat(training_data, ignore_index=True)['target'].values
        
        # TimeSeriesSplit pour éviter l'overfitting sur matchs futurs
        tscv = TimeSeriesSplit(n_splits=5)
        
        base_model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.1,
            random_state=42
        )
        
        ML_MODEL = CalibratedClassifierCV(base_model, cv=tscv, method='isotonic')
        ML_MODEL.fit(X, y)
        
        logger.info("✅ Modèle ML NBA entraîné avec succès")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur entraînement ML: {e}")
        return False

def predict_with_ml_model(away_team, home_team):
    """Prédit le résultat avec le modèle ML calibré"""
    global ML_MODEL
    
    if not SKLEARN_AVAILABLE or ML_MODEL is None:
        return None
    
    try:
        features = build_nba_features(away_team, home_team)
        if features is None or features.empty:
            return None
        
        # Probabilité réelle de victoire domicile
        try:
            prob_home_win = ML_MODEL.predict_proba(features)[0][1]
        except Exception:
            # Fallback si predict_proba échoue
            pred = ML_MODEL.predict(features)[0]
            prob_home_win = float(pred)
        
        # Assurer que la probabilité est entre 0.05 et 0.95
        prob_home_win = max(0.05, min(0.95, prob_home_win))
        
        logger.debug(f"ML Prediction: {away_team} @ {home_team} - Home Win Prob: {prob_home_win:.1%}")
        
        return prob_home_win
    except Exception as e:
        logger.warning(f"⚠️ Erreur prédiction ML: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# PLAYER PROPS MODEL (POINTS PREDICTION)
# ═══════════════════════════════════════════════════════════════════════════

def build_player_props_features(player_name, opponent_team, home_away, 
                                 player_avg_pts_last_10=20.0, 
                                 opponent_def_rating=110.0,
                                 opponent_pts_allowed_pos=25.0,
                                 pace_matchup=100.0,
                                 minutes_last_5=32.0,
                                 b2b_flag=0,
                                 vegas_line=220.0):
    """Construit les features pour modèle de prédiction points joueur"""
    if not XGBOOST_AVAILABLE:
        return None
    
    try:
        features_dict = {
            'player_avg_pts_last_10': player_avg_pts_last_10,      # Moyenne récente pondérée
            'opponent_def_rating': opponent_def_rating,             # Défense adverse vs position
            'opponent_pts_allowed_to_pos': opponent_pts_allowed_pos, # Points alloués à la position
            'home_away': 1.0 if home_away.lower() == 'home' else 0.0,  # 1 = domicile, 0 = extérieur
            'pace_matchup': pace_matchup,                           # Pace des deux équipes
            'minutes_last_5': minutes_last_5,                       # Charge récente en minutes
            'b2b_flag': float(b2b_flag),                            # 1 = back-to-back, 0 = sinon
            'vegas_line': vegas_line,                               # Ligne Vegas (total attendu)
        }
        
        return pd.DataFrame([features_dict])
    except Exception as e:
        logger.warning(f"⚠️ Erreur construction features props: {e}")
        return None

def train_player_props_model():
    """Entraîne le modèle XGBoost pour prédictions points joueurs"""
    global PROPS_MODEL
    
    if not XGBOOST_AVAILABLE:
        logger.warning("⚠️ XGBoost non disponible")
        return False
    
    try:
        logger.info("🤖 Entraînement du modèle XGBoost Player Props...")
        
        # Données d'entraînement synthétiques
        training_data = []
        
        # Scénarios variés pour entraînement
        for avg_pts in [15, 18, 20, 22, 25, 28, 30]:
            for def_rating in [105, 110, 115, 120]:
                for minutes in [25, 28, 30, 32, 34]:
                    for b2b in [0, 1]:
                        for home in [0, 1]:
                            features = build_player_props_features(
                                player_name="synthetic",
                                opponent_team="opponent",
                                home_away="home" if home else "away",
                                player_avg_pts_last_10=avg_pts,
                                opponent_def_rating=def_rating,
                                opponent_pts_allowed_pos=def_rating - 110 + 25,
                                pace_matchup=98 + (def_rating - 110) * 0.1,
                                minutes_last_5=minutes,
                                b2b_flag=b2b,
                                vegas_line=220 + (avg_pts - 20) * 5
                            )
                            
                            if features is not None:
                                # Cible synthétique : moyenne pondérée des factors
                                predicted_pts = (
                                    avg_pts * 0.4 +                    # 40% moyenne récente
                                    (130 - def_rating) * 0.1 +          # 10% défense adverse
                                    minutes * 0.02 +                    # 2% minutes
                                    (1.5 if home else 0) +              # +1.5 si domicile
                                    (-1 if b2b else 0) * 1.5            # -1.5 si back-to-back
                                )
                                features['points'] = predicted_pts
                                training_data.append(features)
        
        if not training_data:
            logger.warning("⚠️ Pas assez de données synthétiques")
            return False
        
        X = pd.concat(training_data, ignore_index=True).drop('points', axis=1)
        y = pd.concat(training_data, ignore_index=True)['points'].values
        
        # TimeSeriesSplit pour validation temporelle
        tscv = TimeSeriesSplit(n_splits=3)
        
        PROPS_MODEL = XGBRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        # Entraîner sur tous les données (pas de cross-val pour régression simple)
        PROPS_MODEL.fit(X, y)
        
        logger.info("✅ Modèle XGBoost Player Props entraîné avec succès")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur entraînement Props: {e}")
        return False

def predict_player_points(player_name, opponent_team, home_away, 
                          player_avg_pts_last_10=20.0,
                          opponent_def_rating=110.0,
                          opponent_pts_allowed_pos=25.0,
                          pace_matchup=100.0,
                          minutes_last_5=32.0,
                          b2b_flag=0,
                          vegas_line=220.0):
    """Prédit les points d'un joueur avec le modèle XGBoost"""
    global PROPS_MODEL
    
    if not XGBOOST_AVAILABLE or PROPS_MODEL is None:
        return None
    
    try:
        features = build_player_props_features(
            player_name=player_name,
            opponent_team=opponent_team,
            home_away=home_away,
            player_avg_pts_last_10=player_avg_pts_last_10,
            opponent_def_rating=opponent_def_rating,
            opponent_pts_allowed_pos=opponent_pts_allowed_pos,
            pace_matchup=pace_matchup,
            minutes_last_5=minutes_last_5,
            b2b_flag=b2b_flag,
            vegas_line=vegas_line
        )
        
        if features is None or features.empty:
            return None
        
        predicted_points = PROPS_MODEL.predict(features)[0]
        
        # Assurer que la prédiction est réaliste (3-60 points)
        predicted_points = max(3, min(60, predicted_points))
        
        logger.debug(f"Props Prediction: {player_name} - Predicted Points: {predicted_points:.1f}")
        
        return predicted_points
    except Exception as e:
        logger.warning(f"⚠️ Erreur prédiction props: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# SPREAD PREDICTION MODEL
# ═══════════════════════════════════════════════════════════════════════════

def predict_spread(home_adj_netrtg, away_adj_netrtg, home_advantage=2.5):
    """
    Prédit l'écart de points attendu (spread)
    
    Arguments:
        home_adj_netrtg: NetRtg ajusté de l'équipe domicile
        away_adj_netrtg: NetRtg ajusté de l'équipe extérieure
        home_advantage: Avantage domicile moyen en NBA (par défaut 2.5 pts)
    
    Retour:
        Écart de points prédit (négatif = away gagne, positif = home gagne)
    
    Utilisation:
        - Si predicted_margin > spread_bookmaker + 2pts → VALUE sur home
        - Si predicted_margin < spread_bookmaker - 2pts → VALUE sur away
        - Écart > 2pts = prise en compte de la valeur
    """
    try:
        # Formule : (NetRtg_home - NetRtg_away) / 2.5 + avantage domicile
        predicted_margin = (home_adj_netrtg - away_adj_netrtg) / 2.5 + home_advantage
        
        # Limiter le spread à des valeurs réalistes (-30 à +30)
        predicted_margin = max(-30, min(30, float(predicted_margin)))
        
        return round(predicted_margin, 1)
    except Exception as e:
        logger.warning(f"⚠️ Erreur prédiction spread: {e}")
        return None

def analyze_spread_value(predicted_margin, bookmaker_spread, min_threshold=2.0):
    """
    Analyse la valeur d'un spread donné comparé à la prédiction
    
    Arguments:
        predicted_margin: Écart prédit par le modèle
        bookmaker_spread: Spread offert par le bookmaker
        min_threshold: Écart minimum pour considérer comme value (par défaut 2.0 pts)
    
    Retour:
        {'side': 'home'|'away'|'none', 'value': float, 'confidence': str}
    """
    try:
        if predicted_margin is None:
            return {'side': 'none', 'value': 0, 'confidence': 'low'}
        
        # Écart entre prédiction et cote bookmaker
        value_margin = predicted_margin - bookmaker_spread
        
        result = {
            'side': 'none',
            'value': round(value_margin, 2),
            'confidence': 'low'
        }
        
        if value_margin > min_threshold:
            # Value sur home (notre prédiction home est plus haute que spread)
            result['side'] = 'home'
            result['confidence'] = 'high' if value_margin > 3.5 else 'medium'
        elif value_margin < -min_threshold:
            # Value sur away (notre prédiction away est meilleure que spread)
            result['side'] = 'away'
            result['confidence'] = 'high' if value_margin < -3.5 else 'medium'
        
        return result
    except Exception as e:
        logger.warning(f"⚠️ Erreur analyse spread value: {e}")
        return {'side': 'none', 'value': 0, 'confidence': 'low'}

# ═══════════════════════════════════════════════════════════════════════════
# PLAYER PROPS OVER/UNDER ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_player_props_ou(predicted_points, bookmaker_ou_line, ou_odds={'over': 1.90, 'under': 1.90}, min_threshold=0.5):
    """
    Analyse la valeur d'un over/under joueur comparé à la prédiction
    
    Arguments:
        predicted_points: Points prédits par XGBoost (ex: 24.5)
        bookmaker_ou_line: Ligne over/under du bookmaker (ex: 23.5)
        ou_odds: Cotes pour over/under {'over': 1.90, 'under': 2.10}
        min_threshold: Écart minimum en points pour considérer comme value (par défaut 0.5)
    
    Retour:
        {
            'side': 'over'|'under'|'none',
            'difference': float (points d'écart),
            'predicted_points': float,
            'line': float,
            'confidence': 'high'|'medium'|'low',
            'value_margin': float (en pourcentage)
        }
    """
    try:
        if predicted_points is None or bookmaker_ou_line is None:
            return {
                'side': 'none',
                'difference': 0,
                'predicted_points': predicted_points,
                'line': bookmaker_ou_line,
                'confidence': 'low',
                'value_margin': 0
            }
        
        # Écart entre prédiction et ligne bookmaker
        difference = predicted_points - bookmaker_ou_line
        
        result = {
            'predicted_points': round(predicted_points, 1),
            'line': bookmaker_ou_line,
            'difference': round(difference, 2),
            'side': 'none',
            'confidence': 'low',
            'value_margin': 0.0
        }
        
        # OVER VALUE: prédiction > ligne + seuil
        if difference > min_threshold:
            result['side'] = 'over'
            # Calculer la marge de profit implicite
            value_margin = (difference / bookmaker_ou_line) * 100
            result['value_margin'] = round(value_margin, 1)
            
            if difference > 1.5:
                result['confidence'] = 'high'
            elif difference > 0.75:
                result['confidence'] = 'medium'
            else:
                result['confidence'] = 'low'
        
        # UNDER VALUE: prédiction < ligne - seuil
        elif difference < -min_threshold:
            result['side'] = 'under'
            value_margin = abs(difference / bookmaker_ou_line) * 100
            result['value_margin'] = round(value_margin, 1)
            
            if difference < -1.5:
                result['confidence'] = 'high'
            elif difference < -0.75:
                result['confidence'] = 'medium'
            else:
                result['confidence'] = 'low'
        
        return result
    except Exception as e:
        logger.warning(f"⚠️ Erreur analyse props O/U: {e}")
        return {
            'side': 'none',
            'difference': 0,
            'predicted_points': predicted_points,
            'line': bookmaker_ou_line,
            'confidence': 'low',
            'value_margin': 0
        }

def format_player_props_message(player_name, predicted_points, analysis_ou, odds_ou={'over': 1.90, 'under': 1.90}):
    """
    Formate un message de propositions joueur pour Telegram
    
    Arguments:
        player_name: Nom du joueur
        predicted_points: Points prédits
        analysis_ou: Résultat de analyze_player_props_ou()
        odds_ou: Cotes O/U disponibles
    
    Retour:
        Message formaté pour Telegram
    """
    try:
        side = analysis_ou['side']
        difference = analysis_ou['difference']
        confidence = analysis_ou['confidence']
        
        if side == 'none':
            return f"📊 {player_name}\nPrédiction: {predicted_points:.1f} pts\nLigne: {analysis_ou['line']}\n➡️ Pas de value identifiée"
        
        # Emoji de confiance
        confidence_emoji = {
            'high': '🔥',
            'medium': '⚡',
            'low': '📌'
        }.get(confidence, '📌')
        
        side_text = 'OVER ⬆️' if side == 'over' else 'UNDER ⬇️'
        odds = odds_ou['over'] if side == 'over' else odds_ou['under']
        
        message = f"""
{confidence_emoji} {player_name}
━━━━━━━━━━━━━━━━
Prédiction: {predicted_points:.1f} pts
Ligne: {analysis_ou['line']} pts
Écart: {abs(difference):.1f} pts

✅ {side_text} ({confidence.upper()})
💰 Cote: {odds}
📈 Valeur: +{analysis_ou['value_margin']:.1f}%
"""
        return message
    except Exception as e:
        logger.warning(f"⚠️ Erreur formatage props message: {e}")
        return "❌ Erreur dans l'analyse"

# ═══════════════════════════════════════════════════════════════════════════
# PLAYER PROPS LOOKUP & ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_player_props(player_name: str) -> dict | None:
    """
    Récupère les props d'un joueur NBA (données ESPN en temps réel, fallback statique).
    Retourne {'team': str, 'position': str, 'props': {...}} ou None si non trouvé.
    """
    try:
        props_db = get_dynamic_player_props()
        # Recherche exacte
        if player_name in props_db:
            return props_db[player_name]
        # Recherche approximative (case-insensitive)
        normalized = player_name.lower().strip()
        for player, data in props_db.items():
            if normalized == player.lower():
                return data
        # Recherche partielle
        for player, data in props_db.items():
            if normalized in player.lower() or player.lower() in normalized:
                return data
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erreur récupération props: {e}")
        return None

def get_all_players_by_team(team_name: str) -> list:
    """
    Retourne tous les joueurs connus d'une équipe (données ESPN en temps réel, fallback statique).
    """
    try:
        team_normalized = team_name.lower().strip()
        props_db = get_dynamic_player_props()
        players = [
            player for player, data in props_db.items()
            if team_normalized in data['team'].lower()
            or data['team'].lower() in team_normalized
        ]
        return sorted(players)
    except Exception as e:
        logger.warning(f"⚠️ Erreur récupération équipe: {e}")
        return []

def analyze_all_player_props(home_team, away_team):
    """
    Analyse les props de tous les joueurs des deux équipes
    
    Retour:
        {
            'home_team': [{'player': str, 'analysis': dict}, ...],
            'away_team': [...]
        }
    """
    try:
        results = {
            'home_team': [],
            'away_team': []
        }
        
        # Analyser les joueurs domicile
        home_players = get_all_players_by_team(home_team)
        for player in home_players:
            props = get_player_props(player)
            if props and 'points' in props['props']:
                # Prédire les points avec le modèle
                predicted_pts = predict_player_points(
                    player_name=player,
                    opponent_team=away_team,
                    home_away='home',
                    player_avg_pts_last_10=props['props']['points']['line'] + 2  # Estimation
                )
                
                if predicted_pts:
                    analysis = analyze_player_props_ou(
                        predicted_pts,
                        props['props']['points']['line'],
                        props['props']['points'],
                        min_threshold=0.5
                    )
                    results['home_team'].append({
                        'player': player,
                        'analysis': analysis,
                        'predicted': predicted_pts
                    })
        
        # Analyser les joueurs extérieur
        away_players = get_all_players_by_team(away_team)
        for player in away_players:
            props = get_player_props(player)
            if props and 'points' in props['props']:
                predicted_pts = predict_player_points(
                    player_name=player,
                    opponent_team=home_team,
                    home_away='away',
                    player_avg_pts_last_10=props['props']['points']['line'] - 1
                )
                
                if predicted_pts:
                    analysis = analyze_player_props_ou(
                        predicted_pts,
                        props['props']['points']['line'],
                        props['props']['points'],
                        min_threshold=0.5
                    )
                    results['away_team'].append({
                        'player': player,
                        'analysis': analysis,
                        'predicted': predicted_pts
                    })
        
        return results
    except Exception as e:
        logger.warning(f"⚠️ Erreur analyse props équipes: {e}")
        return {'home_team': [], 'away_team': []}

def format_team_props_summary(team_name, props_analysis):
    """
    Formate un résumé des props pour une équipe
    
    Retour:
        Message formaté pour Telegram
    """
    try:
        if not props_analysis:
            return f"❌ Pas de joueurs stars recommandés pour {team_name}"
        
        # Filtrer les analyses avec value (side != 'none')
        value_picks = [p for p in props_analysis if p['analysis']['side'] != 'none']
        
        if not value_picks:
            return f"📊 {team_name}\n➡️ Pas de value identifiée sur les props"
        
        message = f"🏀 {team_name.upper()}\n"
        message += f"━━━━━━━━━━━━━━━━━━\n"
        message += f"💰 {len(value_picks)} value(s) trouvée(s)\n\n"
        
        for pick in value_picks[:5]:  # Top 5 picks
            player = pick['player']
            analysis = pick['analysis']
            confidence_emoji = {
                'high': '🔥',
                'medium': '⚡',
                'low': '📌'
            }.get(analysis['confidence'], '📌')
            
            side_text = 'OVER' if analysis['side'] == 'over' else 'UNDER'
            message += f"{confidence_emoji} {player}\n"
            message += f"   {side_text} {analysis['line']} | Pred: {analysis['predicted_points']:.1f}\n"
            message += f"   +{analysis['value_margin']:.1f}%\n\n"
        
        return message
    except Exception as e:
        logger.warning(f"⚠️ Erreur formatage résumé props: {e}")
        return "❌ Erreur"

def generate_prediction_nba(away_team: str, home_team: str) -> dict:
    """Génère une prédiction pour un match NBA avec modèle ML si disponible"""
    away_clean = find_team_nba(away_team) or away_team.lower()
    home_clean = find_team_nba(home_team) or home_team.lower()
    
    odds_data = get_best_odds_nba(away_clean, home_clean)
    best_away_ml = odds_data["away_ml"]
    best_home_ml = odds_data["home_ml"]
    
    # Essayer d'utiliser le modèle ML d'abord
    model_source = "STATS"
    prob_home_win = None
    
    if SKLEARN_AVAILABLE and ML_MODEL is not None:
        prob_home_win = predict_with_ml_model(away_team, home_team)
        if prob_home_win is not None:
            model_source = "ML"
    
    # Fallback sur le modèle statistique 4-facteurs
    if prob_home_win is None:
        _nba_ts = get_dynamic_team_stats('NBA')
        away_stats = _nba_ts.get(away_clean, {"strength": 85, "ppg": 115.0, "pa": 112.0, "wins": 40, "losses": 42})
        home_stats = _nba_ts.get(home_clean, {"strength": 85, "ppg": 115.0, "pa": 112.0, "wins": 40, "losses": 42})
        
        # Calcul du modèle 4-facteurs pour le basketball
        away_ppg_diff = away_stats["ppg"] - home_stats["pa"]
        home_ppg_diff = home_stats["ppg"] - away_stats["pa"]
        
        point_diff = away_ppg_diff - home_ppg_diff - 2.5  # Avantage route
        
        try:
            win_prob_away = 1 / (1 + math.exp(-point_diff / 11.0))
        except Exception:
            win_prob_away = 0.5 + (point_diff / 50.0)
        
        prob_away_win = max(0.05, min(0.95, win_prob_away))
        prob_home_win = 1.0 - prob_away_win
    
    # Consensus du marché
    market_away_avg = (1.0 / best_away_ml + 1.0 / best_home_ml)
    market_consensus_away = (1.0 / best_away_ml) / market_away_avg
    prob_home_market = 1.0 - market_consensus_away
    
    # ── Paramètres appris par Ultron Brain (calibration auto) ────────────
    _adj_nba      = get_model_adjustments("NBA")
    _model_w_nba  = _adj_nba.get("model_weight", 0.60)
    _conf_cal_nba = _adj_nba.get("confidence_scale", 1.0)
    _home_d_nba   = _adj_nba.get("home_advantage_delta", 0.0)
    # Correction avantage domicile (prob_home_win)
    prob_home_win = max(0.05, min(0.95, prob_home_win + _home_d_nba))

    # Blended probability (poids appris)
    blended_prob = (_model_w_nba * prob_home_win) + ((1.0 - _model_w_nba) * prob_home_market)
    blended_prob = max(0.05, min(0.95, blended_prob))
    
    # EV calculation
    prob_away = 1.0 - blended_prob
    ev_away = (best_away_ml - 1.0) * prob_away - blended_prob
    ev_home = (best_home_ml - 1.0) * blended_prob - prob_away
    
    logger.debug(f"{away_team.upper()} @ {home_team.upper()}: [{model_source}] | Cotes: {best_away_ml:.2f}/{best_home_ml:.2f} | Blended: {blended_prob:.1%} | EV: {ev_away:.4f}/{ev_home:.4f}")
    
    if ev_away > ev_home:
        pick = f"{away_team.upper()} ML"
        odds = best_away_ml
        confidence = int(min(97, max(50, prob_away * 100 * _conf_cal_nba)))
        ev = ev_away
        book = odds_data["away_book"]
    else:
        pick = f"{home_team.upper()} ML"
        odds = best_home_ml
        confidence = int(min(97, max(50, blended_prob * 100 * _conf_cal_nba)))
        ev = ev_home
        book = odds_data["home_book"]
    
    if ev > 0.01:
        status = "✅ BUY"
    elif ev > 0.0:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"

    # ── SPREAD ────────────────────────────────────────────────────────────
    # Estimer le spread depuis les probabilités blendées
    estimated_spread = (prob_away - 0.5) * 22.0  # ~pts défavorables pour home
    raw_spread = round(estimated_spread * 2) / 2
    if raw_spread > 0:
        spread_pick = f"{away_team.upper()} -{raw_spread}"
        spread_conf = min(72, int(prob_away * 100) + 3)
    elif raw_spread < 0:
        spread_pick = f"{home_team.upper()} -{abs(raw_spread)}"
        spread_conf = min(72, int(blended_prob * 100) + 3)
    else:
        spread_pick = f"{home_team.upper()} PK"
        spread_conf = 50
    spread_odds = 1.909

    # ── O/U (Total points) ───────────────────────────────────────────────
    nba_away = NBA_TEAM_STATS.get(away_clean, {"ppg": 115.0, "pa": 112.0})
    nba_home = NBA_TEAM_STATS.get(home_clean, {"ppg": 115.0, "pa": 112.0})
    projected_total = nba_away["ppg"] + nba_home["ppg"]
    ou_line = 225.5
    if projected_total > ou_line:
        ou_pick = f"OVER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 2 + 50))
    else:
        ou_pick = f"UNDER {ou_line}"
        ou_conf = min(70, int(abs(projected_total - ou_line) * 2 + 50))
    ou_odds = 1.909

    return {
        "pick": pick,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
        "ev": f"{ev:.4f}",
        "ev_pct": f"{ev*100:.2f}%",
        "status": status,
        "bookmaker": book,
        "model": model_source,
        # ML
        "ml_pick": pick,
        "ml_odds": f"{odds:.2f}",
        "ml_confidence": confidence,
        "ml_ev_pct": f"{ev*100:.2f}%",
        # Spread
        "spread_pick": spread_pick,
        "spread_odds": f"{spread_odds:.2f}",
        "spread_confidence": spread_conf,
        # O/U
        "ou_pick": ou_pick,
        "ou_odds": f"{ou_odds:.2f}",
        "ou_confidence": ou_conf,
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal"""
    msg = "🤖 ULTRON v6.0 - MULTISPORTS\n"
    msg += "NBA 🏀 + NHL 🏒 + NFL 🏈\n\n"
    msg += "🕐 Heure Québec | 🌍 ESPN Live Data\n"
    msg += "📊 3 Bookmakers | Line Shopping | Smart Filtering\n\n"
    msg += "COMMANDES:\n"
    msg += "/nba - Équipes NBA en direct\n"
    msg += "/nhl - Équipes NHL en direct\n"
    msg += "/nfl - Équipes NFL en direct\n"
    msg += "/pronostics <sport> - Pronostics (nba/nhl/nfl)\n"
    msg += "/help - Aide"
    await update.message.reply_text(msg)

async def nhl_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les équipes NHL en direct"""
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
        logger.error(f"❌ nhl_matches: {e}")
        await update.message.reply_text(f"❌ Erreur NHL: {e}")

async def nfl_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les équipes NFL en direct"""
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
        logger.error(f"❌ nfl_matches: {e}")
        await update.message.reply_text(f"❌ Erreur NFL: {e}")

async def nba_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les équipes NBA en direct"""
    try:
        matches = get_live_matches_nba()
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
        msg += "💡 Utilise /pronostics nba pour les prédictions"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"❌ nba_matches: {e}")
        await update.message.reply_text(f"❌ Erreur NBA: {e}")

async def pronostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les pronostics pour un sport: /pronostics nha/nhl/nfl"""
    if not context.args:
        msg = "❌ Usage: /pronostics <sport>\n\n"
        msg += "Exemple:\n"
        msg += "/pronostics nba - Pronostics NBA\n"
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
    """Affiche les pronostics NBA"""
    try:
        matches = get_live_matches_nba()
        quebec_time = get_quebec_time()
        
        if not matches:
            await update.message.reply_text("❌ Aucun match NBA actuel")
            return
        
        predictions = []
        for away, home in matches:
            try:
                pred = generate_prediction_nba(away, home)
                predictions.append((away, home, pred))
            except Exception as e:
                logger.warning(f"⚠️ Erreur prédiction {away} @ {home}: {e}")
                continue
        
        if not predictions:
            await update.message.reply_text("⚠️ Impossible de générer les prédictions NBA")
            return
        
        buy_picks = [(a, h, p) for a, h, p in predictions if "BUY" in p['status']]
        monitoring_picks = [(a, h, p) for a, h, p in predictions if "MONITORING" in p['status']]
        pass_picks = [(a, h, p) for a, h, p in predictions if "PASS" in p['status']]
        
        # Message 1
        msg1 = "🏀 ULTRON v6.0 - PRÉDICTIONS NBA\n"
        msg1 += "═" * 70 + "\n"
        msg1 += f"🕐 {quebec_time.strftime('%H:%M:%S')} (Heure Québec)\n"
        msg1 += f"📡 {len(matches)} matchs NBA en direct | {len(predictions)} avec prédictions\n"
        
        # Afficher le modèle utilisé
        models_used = set(p['model'] for a, h, p in predictions)
        msg1 += f"🤖 Modèle: {', '.join(models_used)}\n"
        msg1 += "═" * 70 + "\n\n"
        
        if buy_picks:
            msg1 += "✅ ACHETER - Meilleure valeur\n"
            msg1 += "─" * 70 + "\n\n"
            for i, (away, home, pred) in enumerate(buy_picks, 1):
                msg1 += f"{i}️⃣ {away.upper()} @ {home.upper()}\n"
                msg1 += f"   💡 {pred['pick']} @ {pred['odds']}\n"
                msg1 += f"   🔥 Confiance: {pred['confidence']}% | EV: {pred['ev_pct']}\n"
                msg1 += f"   📊 Bookmaker: {pred['bookmaker']} | Model: {pred['model']}\n\n"
        else:
            msg1 += "✅ Aucun pick BUY actuellement\n\n"
        
        await update.message.reply_text(msg1)
        
        # Message 2
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
        logger.error(f"❌ pronostics_nba: {e}")
        await update.message.reply_text(f"❌ Erreur NBA: {e}")

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
        
        # Message 1
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
        
        # Message 2
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
        logger.error(f"❌ pronostics_nhl: {e}")
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
        
        # Message 1
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
        
        # Message 2
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
        logger.error(f"❌ pronostics_nfl: {e}")
        await update.message.reply_text(f"❌ Erreur NFL: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche l'aide"""
    msg = "🤖 ULTRON v6.0 - AIDE\n\n"
    msg += "COMMANDES MATCHS (Équipes en direct):\n"
    msg += "/nba - Équipes NBA 🏀\n"
    msg += "/nhl - Équipes NHL 🏒\n"
    msg += "/nfl - Équipes NFL 🏈\n\n"
    msg += "COMMANDES PRONOSTICS:\n"
    msg += "/pronostics nba - Prédictions NBA\n"
    msg += "/pronostics nhl - Prédictions NHL 🏒\n"
    msg += "/pronostics nfl - Prédictions NFL 🏈\n\n"
    msg += "COMMANDES PLAYER PROPS:\n"
    msg += "/daily_props - Props de TOUS les matchs du jour 🔥\n"
    msg += "/props_match [équipe1] vs [équipe2] - Props du match\n"
    msg += "/player [nom] - Props d'un joueur star 🌟\n"
    msg += "/all_props - Tous les joueurs stars disponibles\n\n"
    msg += "COMMANDES ESPN EN DIRECT:\n"
    msg += "/boxscore nba — Box scores en direct 📊\n"
    msg += "/boxscore nhl — Box scores NHL 🏒\n"
    msg += "/boxscore nfl — Box scores NFL 🏈\n"
    msg += "/leaders nba — Leaders stats saison NBA 🏆\n"
    msg += "/leaders nhl — Leaders stats saison NHL 🏒\n"
    msg += "/leaders nfl — Leaders stats saison NFL 🏈\n\n"
    msg += "EXPLICATION DES PICKS:\n"
    msg += "✅ BUY - Valeur EV > +1%\n"
    msg += "👀 MONITORING - EV entre 0% et +1%\n"
    msg += "⏸ PASS - EV ≤ 0%\n\n"
    msg += "💰 Bankroll Management: Risk 1-2% par pick!\n"
    await update.message.reply_text(msg)

async def player_props(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyse les props d'un joueur spécifique"""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /player [nom du joueur]\nEx: /player LeBron James")
            return
        
        player_name = " ".join(context.args)
        props = get_player_props(player_name)
        
        if not props:
            props_db  = get_dynamic_player_props()
            available = "\n".join(sorted(props_db.keys())[:10])
            msg = f"❌ Joueur non trouvé: {player_name}\n\n"
            msg += "Joueurs disponibles:\n"
            msg += available + "\n"
            msg += f"\n... et {max(0, len(props_db) - 10)} autres"
            await update.message.reply_text(msg)
            return
        
        # Prédire les points
        predicted_pts = predict_player_points(
            player_name=player_name,
            opponent_team="opponent",
            home_away="home"
        )
        
        if not predicted_pts:
            await update.message.reply_text(f"❌ Impossible de prédire les points pour {player_name}")
            return
        
        # Analyser les props
        analysis = analyze_player_props_ou(
            predicted_pts,
            props['props']['points']['line'],
            props['props']['points'],
            min_threshold=0.5
        )
        
        # Formater le message
        msg = f"""
🏀 {player_name}
Équipe: {props['team']} | Position: {props['position']}
━━━━━━━━━━━━━━━━━━━━
Ligne: {analysis['line']} pts
Prédiction: {analysis['predicted_points']} pts
Écart: {abs(analysis['difference']):.1f} pts

"""
        
        if analysis['side'] != 'none':
            confidence_emoji = {
                'high': '🔥',
                'medium': '⚡',
                'low': '📌'
            }.get(analysis['confidence'], '📌')
            
            side_text = f"OVER ⬆️ @ {props['props']['points']['over']}" if analysis['side'] == 'over' else f"UNDER ⬇️ @ {props['props']['points']['under']}"
            
            msg += f"{confidence_emoji} RECOMMANDATION: {side_text}\n"
            msg += f"Value: +{analysis['value_margin']:.1f}%\n"
            msg += f"Confiance: {analysis['confidence'].upper()}\n"
        else:
            msg += "➡️ Pas de value identifiée\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Erreur /player: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

async def match_props(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyse les props de tous les joueurs d'un match"""
    try:
        if len(context.args) < 3 or context.args[1].lower() != 'vs':
            await update.message.reply_text("Usage: /props_match [équipe1] vs [équipe2]\nEx: /props_match Lakers vs Celtics")
            return
        
        home_team = context.args[0]
        away_team = " ".join(context.args[2:])
        
        await update.message.reply_text("⏳ Analyse en cours...")
        
        # Analyser tous les props
        results = analyze_all_player_props(home_team, away_team)
        
        msg = f"🏀 {home_team.upper()} vs {away_team.upper()}\n"
        msg += "━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Joueurs domicile
        if results['home_team']:
            home_msg = format_team_props_summary(home_team, results['home_team'])
            msg += home_msg + "\n"
        else:
            msg += f"❌ Pas de props pour {home_team}\n\n"
        
        # Joueurs extérieur
        if results['away_team']:
            away_msg = format_team_props_summary(away_team, results['away_team'])
            msg += away_msg
        else:
            msg += f"❌ Pas de props pour {away_team}\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"❌ Erreur /props_match: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

async def all_props(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liste tous les joueurs stars disponibles"""
    try:
        msg = "⭐ JOUEURS STARS NBA DISPONIBLES\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Grouper par équipe (données ESPN temps réel)
        props_db = get_dynamic_player_props()
        teams = {}
        for player, data in props_db.items():
            team = data['team']
            if team not in teams:
                teams[team] = []
            teams[team].append(player)

        # Afficher par équipe
        for team in sorted(teams.keys()):
            msg += f"🏀 {team}\n"
            for player in teams[team]:
                props = props_db[player]
                line = props['props']['points']['line']
                msg += f"   • {player} ({line})\n"
            msg += "\n"
        
        msg += "\n💡 Utilise: /player [nom]\nEx: /player LeBron James"
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"❌ Erreur /all_props: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

async def daily_props(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les props de tous les matchs NBA du jour"""
    try:
        await update.message.reply_text("⏳ Compilation des props du jour...")
        
        # Récupérer les matchs NBA du jour
        matches = get_live_matches_nba()
        
        if not matches:
            await update.message.reply_text("❌ Aucun match NBA aujourd'hui")
            return
        
        quebec_time = get_quebec_time()
        msg = f"🏀 PROPS NBA DU JOUR\n"
        msg += f"📅 {quebec_time.strftime('%d/%m/%Y %H:%M')}\n"
        msg += "═" * 50 + "\n\n"
        
        total_picks = 0
        
        # Analyser chaque match
        for match_num, (away_team, home_team) in enumerate(matches, 1):
            msg += f"🎯 MATCH {match_num}: {away_team.upper()} @ {home_team.upper()}\n"
            msg += "━" * 50 + "\n"
            
            # Récupérer les joueurs des 2 équipes
            home_players = get_all_players_by_team(home_team)
            away_players = get_all_players_by_team(away_team)
            
            match_picks = []
            
            # Analyser joueurs domicile
            for player in home_players:
                props = get_player_props(player)
                if props and 'points' in props['props']:
                    predicted_pts = predict_player_points(
                        player_name=player,
                        opponent_team=away_team,
                        home_away='home'
                    )
                    
                    if predicted_pts:
                        analysis = analyze_player_props_ou(
                            predicted_pts,
                            props['props']['points']['line'],
                            props['props']['points'],
                            min_threshold=0.5
                        )
                        
                        if analysis['side'] != 'none':
                            match_picks.append({
                                'player': player,
                                'analysis': analysis,
                                'predicted': predicted_pts,
                                'line': props['props']['points']['line'],
                                'odds': props['props']['points']
                            })
            
            # Analyser joueurs extérieur
            for player in away_players:
                props = get_player_props(player)
                if props and 'points' in props['props']:
                    predicted_pts = predict_player_points(
                        player_name=player,
                        opponent_team=home_team,
                        home_away='away'
                    )
                    
                    if predicted_pts:
                        analysis = analyze_player_props_ou(
                            predicted_pts,
                            props['props']['points']['line'],
                            props['props']['points'],
                            min_threshold=0.5
                        )
                        
                        if analysis['side'] != 'none':
                            match_picks.append({
                                'player': player,
                                'analysis': analysis,
                                'predicted': predicted_pts,
                                'line': props['props']['points']['line'],
                                'odds': props['props']['points']
                            })
            
            # Afficher les picks triés par confiance
            if match_picks:
                # Trier: HIGH confiance en premier, puis par value
                match_picks.sort(
                    key=lambda x: (
                        {'high': 0, 'medium': 1, 'low': 2}[x['analysis']['confidence']],
                        -x['analysis']['value_margin']
                    )
                )
                
                for pick in match_picks[:4]:  # Max 4 picks par match
                    player = pick['player']
                    analysis = pick['analysis']
                    
                    confidence_emoji = {
                        'high': '🔥',
                        'medium': '⚡',
                        'low': '📌'
                    }[analysis['confidence']]
                    
                    side_text = 'OVER' if analysis['side'] == 'over' else 'UNDER'
                    odds = pick['odds']['over'] if analysis['side'] == 'over' else pick['odds']['under']
                    
                    msg += f"{confidence_emoji} {player}\n"
                    msg += f"   {side_text} {analysis['line']} | Pred: {analysis['predicted_points']:.1f}\n"
                    msg += f"   +{analysis['value_margin']:.1f}% @ {odds}\n"
                    total_picks += 1
            else:
                msg += "   ➡️ Pas de value identifiée\n"
            
            msg += "\n"
        
        msg += "═" * 50 + "\n"
        msg += f"📊 Total: {total_picks} picks avec value\n"
        msg += "💡 Utilise /player [nom] pour plus de détails"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"❌ Erreur /daily_props: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# AUTOMATIONS - ENVOIS AUTOMATIQUES
# ═══════════════════════════════════════════════════════════════════════════

# Suivi des matchs déjà notifiés (évite les doublons)
_notified_starts = set()
_notified_pronostics = set()

MOTIVATION_MESSAGES = [
    "🔥 Every expert was once a beginner. Trust the process, trust the data.",
    "💎 Discipline beats motivation every single day. Show up, analyze, win.",
    "🧠 The best bet you can make is on yourself. Stay sharp, stay focused.",
    "⚡ Success is not luck — it's preparation meeting opportunity.",
    "🎯 One good decision today builds tomorrow's winning streak.",
    "🚀 The grind is silent. The results speak loud. Keep going.",
    "💪 Consistency is what separates the amateurs from the professionals.",
    "🌟 Today is a new opportunity to make smarter picks than yesterday.",
    "🏆 Champions don't skip their morning routine. Neither should you.",
    "🔑 Value is found by those who look harder. Look harder today.",
    "📊 Trust the model. Trust the process. The edge is real.",
    "⚔️ Stay patient. The right play at the right time — that's everything.",
    "🎲 Randomness is temporary. Edge is permanent. Stay disciplined.",
    "🌅 A new day, a new edge. Let ULTRON guide your picks.",
    "💡 Smart money is quiet money. Analyze, decide, execute.",
]

def _build_picks_for_sport(sport: str):
    """Génère la liste des picks pour un sport donné. Retourne liste de dicts."""
    picks = []
    if sport == "nba":
        matches = get_live_matches_nba()
        for away, home in matches:
            try:
                pred = generate_prediction_nba(away, home)
                if pred and pred.get('status', '') != 'PASS':
                    picks.append({
                        "label": f"🏀 {away} @ {home}",
                        "pick": pred.get('pick', ''),
                        "odds": pred.get('odds', ''),
                        "confidence": pred.get('confidence', 0),
                        "ev": pred.get('ev_pct', ''),
                        "status": pred.get('status', ''),
                    })
            except Exception:
                continue
    elif sport == "nhl":
        matches = get_live_matches_nhl()
        for away, home in matches:
            try:
                pred = generate_prediction_nhl(away, home)
                if pred and pred.get('status', '') != 'PASS':
                    picks.append({
                        "label": f"🏒 {away} @ {home}",
                        "pick": pred.get('pick', ''),
                        "odds": pred.get('odds', ''),
                        "confidence": pred.get('confidence', 0),
                        "ev": pred.get('ev_pct', ''),
                        "status": pred.get('status', ''),
                    })
            except Exception:
                continue
    elif sport == "nfl":
        matches = get_live_matches_nfl()
        for away, home in matches:
            try:
                pred = generate_prediction_nfl(away, home)
                if pred and pred.get('status', '') != 'PASS':
                    picks.append({
                        "label": f"🏈 {away} @ {home}",
                        "pick": pred.get('pick', ''),
                        "odds": pred.get('odds', ''),
                        "confidence": pred.get('confidence', 0),
                        "ev": pred.get('ev_pct', ''),
                        "status": pred.get('status', ''),
                    })
            except Exception:
                continue
    # Trier par confiance décroissante
    picks.sort(key=lambda x: x['confidence'], reverse=True)
    return picks


async def auto_daily_motivation(context):
    """9h00 Quebec: Message de motivation + résumé des matchs + alertes blessures"""
    if not TELEGRAM_CHAT_ID:
        return

    quebec_time = get_quebec_time()
    day_index = quebec_time.timetuple().tm_yday % len(MOTIVATION_MESSAGES)
    quote = MOTIVATION_MESSAGES[day_index]

    msg = f"🌅 GOOD MORNING — {quebec_time.strftime('%A, %B %d %Y')}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"{quote}\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Résumé des matchs du jour
    sports_config = [
        ("basketball/nba", "🏀 NBA"),
        ("hockey/nhl", "🏒 NHL"),
        ("football/nfl", "🏈 NFL"),
    ]
    total_matches = 0
    today = datetime.datetime.now().strftime("%Y%m%d")

    for sport_path, sport_label in sports_config:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={today}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get('events', [])
                if events:
                    msg += f"\n{sport_label}: {len(events)} matchs aujourd'hui\n"
                    for ev in events[:3]:  # max 3 par sport
                        comp = ev.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('shortDisplayName', '?')
                            home = competitors[1].get('team', {}).get('shortDisplayName', '?')
                            date_str = ev.get('date', '')
                            try:
                                utc_dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ")
                                utc_dt = utc_dt.replace(tzinfo=pytz.utc)
                                qc_dt = utc_dt.astimezone(QUEBEC_TZ)
                                heure_match = qc_dt.strftime('%H:%M')
                            except Exception:
                                heure_match = "?"
                            msg += f"  • {away} @ {home} ({heure_match})\n"
                    total_matches += len(events)
        except Exception:
            continue

    if total_matches == 0:
        msg += "\nAucun match programmé aujourd'hui.\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🤖 ULTRON envoie les picks 1h avant chaque match!"

    try:
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        if TELEGRAM_CHAT_ID_VIP:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=msg)
        logger.info("✅ Motivation + résumé matinal envoyés")
    except Exception as e:
        logger.error(f"❌ Erreur motivation: {e}")

    # ── Alertes blessures (message séparé, seulement si matchs aujourd'hui) ──
    if ESPN_CONTEXT_AVAILABLE and total_matches > 0:
        try:
            logger.info("🏥 ESPN: récupération blessures...")
            espn_ctx = get_full_context_all_sports()
            inj_msg = format_injuries_alert(espn_ctx)
            if inj_msg:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=inj_msg)
                if TELEGRAM_CHAT_ID_VIP:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=inj_msg)
                logger.info("✅ Alertes blessures envoyées")
            else:
                logger.info("ℹ️ Aucune blessure clé aujourd'hui")
        except Exception as e:
            logger.error(f"❌ Erreur alertes blessures: {e}")


def _player_props_msg_for_match(away: str, home: str) -> str:
    """
    Analyse et formate les props joueurs NBA pour un match.
    Retourne une chaîne vide si aucune value n'est identifiée.
    (Limité à NBA car NBA_PLAYER_PROPS ne couvre que le basket.)
    """
    try:
        results = analyze_all_player_props(home, away)
        away_summary = format_team_props_summary(away, results['away_team'])
        home_summary = format_team_props_summary(home, results['home_team'])
        has_away = 'value(s) trouvée(s)' in away_summary
        has_home = 'value(s) trouvée(s)' in home_summary
        if not has_away and not has_home:
            return ""
        msg  = "🌟  P R O P S  J O U E U R S\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if has_away:
            msg += away_summary + "\n"
        if has_home:
            msg += home_summary
        return msg.strip()
    except Exception as e:
        logger.debug(f"⚠️ _player_props_msg_for_match: {e}")
        return ""


async def auto_send_pronostics(context):
    """
    Toutes les 30 minutes: vérifie s'il y a des matchs qui commencent
    dans moins d'1 heure et envoie les picks pour ces matchs.
    FREE = 1 pick | VIP = tous les picks
    """
    if not TELEGRAM_CHAT_ID:
        return

    quebec_time = get_quebec_time()
    now_utc = datetime.datetime.now(pytz.utc)
    date_key = quebec_time.strftime('%Y-%m-%d')

    sports_config = [
        ("basketball/nba", "nba", "🏀"),
        ("hockey/nhl", "nhl", "🏒"),
        ("football/nfl", "nfl", "🏈"),
    ]

    upcoming_matches = []  # [(sport_key, emoji, away, home)]

    for sport_path, sport_key, emoji in sports_config:
        try:
            # Vérifier aujourd'hui ET demain (UTC) — les matchs de soirée EDT
            # ex: 22h EDT = 02h00 UTC lendemain. ESPN indexe par date UTC.
            now_utc_date = datetime.datetime.utcnow()
            dates_to_check = [
                now_utc_date.strftime("%Y%m%d"),
                (now_utc_date + datetime.timedelta(days=1)).strftime("%Y%m%d"),
            ]

            all_events = []
            for date_str_q in dates_to_check:
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date_str_q}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    all_events.extend(resp.json().get('events', []))

            for event in all_events:
                try:
                    status_type = event.get('status', {}).get('type', {})
                    status_desc = status_type.get('description', '').lower()
                    status_name = status_type.get('name', '').lower()
                    # Ignorer matchs terminés
                    if any(s in status_desc for s in ['final', 'completed']):
                        continue
                    if 'status_final' in status_name:
                        continue

                    date_str = event.get('date', '')
                    # ── Parsing robuste : ESPN retourne parfois avec ou sans secondes
                    # ex: "2026-05-10T23:00Z"  ou  "2026-05-10T23:00:00Z"
                    utc_dt = None
                    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
                        try:
                            utc_dt = datetime.datetime.strptime(date_str, fmt).replace(tzinfo=pytz.utc)
                            break
                        except ValueError:
                            continue
                    if utc_dt is None:
                        logger.warning(f"⚠️ auto_send_pronostics: format date inconnu '{date_str}' ({sport_key})")
                        continue

                    minutes_until = (utc_dt - now_utc).total_seconds() / 60

                    # is_live = match déjà commencé (heure passée) mais pas terminé.
                    # On utilise minutes_until plutôt que le texte de statut ESPN
                    # car NHL peut retourner "End of 1st Period", "Overtime", etc.
                    is_live = minutes_until < 20

                    # Fenêtre d'envoi : dans les 120 min avant le match OU match en cours
                    if minutes_until <= 120:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('displayName', '?')
                            home = competitors[1].get('team', {}).get('displayName', '?')
                            notify_key = f"prono_{date_key}_{sport_key}_{away}_{home}"
                            if notify_key not in _notified_pronostics:
                                _notified_pronostics.add(notify_key)
                                upcoming_matches.append((sport_key, emoji, away, home, utc_dt, is_live))
                                logger.info(f"🎯 Match trouvé [{sport_key}]: {away} @ {home} dans {minutes_until:.0f} min (live={is_live})")
                            else:
                                logger.debug(f"⏭️ Déjà notifié [{sport_key}]: {away} @ {home}")
                    else:
                        # Log pour diagnostiquer les matchs hors fenêtre
                        try:
                            comp = event.get('competitions', [{}])[0]
                            t1 = comp.get('competitors', [{}])[0].get('team', {}).get('displayName', '?')
                            t2 = comp.get('competitors', [{}])[1].get('team', {}).get('displayName', '?') if len(comp.get('competitors', [])) > 1 else '?'
                            logger.info(f"⏳ Hors fenêtre [{sport_key}]: {t1}@{t2} dans {minutes_until:.0f} min (statut: {status_desc})")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"⚠️ auto_send_pronostics event error [{sport_key}]: {e}")
                    continue
        except Exception as e:
            logger.debug(f"⚠️ auto_send_pronostics {sport_key}: {e}")

    if not upcoming_matches:
        return

    # ── Récupérer les cotes en temps réel UNE FOIS par sport (Odds API) ──
    # Une seule requête par sport toutes les 4h — économie maximale de quota
    sports_in_play = {sk for sk, *_ in upcoming_matches}
    live_odds_by_sport = {}
    for sk in sports_in_play:
        live_odds_by_sport[sk] = fetch_odds_api(sk)

    # ── Contexte ESPN : blessures + stats (si module disponible) ──────────
    espn_games_by_sport = {}
    if ESPN_CONTEXT_AVAILABLE:
        try:
            for sk in sports_in_play:
                espn_sport = sk.upper()  # "nba" → "NBA" etc.
                espn_games_by_sport[sk] = get_games_with_context(espn_sport)
            logger.info(f"✅ ESPN context chargé pour: {list(espn_games_by_sport.keys())}")
        except Exception as e:
            logger.warning(f"⚠️ ESPN context non disponible: {e}")

    # Générer les picks pour chaque match trouvé
    all_picks = []
    for sport_key, emoji, away, home, match_time, match_is_live in upcoming_matches:
        try:
            if sport_key == "nba":
                pred = generate_prediction_nba(away, home)
            elif sport_key == "nhl":
                pred = generate_prediction_nhl(away, home)
            else:
                pred = generate_prediction_nfl(away, home)

            if pred:
                qc_time = match_time.astimezone(QUEBEC_TZ)

                # Remplacer ML + Spread + O/U par les cotes réelles si disponibles
                live = get_live_odds_for_match(away, home, live_odds_by_sport.get(sport_key, []))
                if live:
                    ml_pick_away = f"{away.upper()} ML"
                    ml_pick_home = f"{home.upper()} ML"
                    if live["ml_away"] > live["ml_home"]:
                        real_ml_pick = ml_pick_away
                        real_ml_odds = f"{live['ml_away']:.2f}"
                    else:
                        real_ml_pick = ml_pick_home
                        real_ml_odds = f"{live['ml_home']:.2f}"
                    real_spread_pick = live["spread_pick"]
                    real_spread_odds = live["spread_odds"]
                    real_ou_pick = live["ou_pick"]
                    real_ou_odds = live["ou_odds"]
                    source_tag = "🟢"  # cotes réelles
                else:
                    real_ml_pick = pred.get('ml_pick', pred.get('pick', ''))
                    real_ml_odds = pred.get('ml_odds', pred.get('odds', ''))
                    real_spread_pick = pred.get('spread_pick', '')
                    real_spread_odds = pred.get('spread_odds', '')
                    real_ou_pick = pred.get('ou_pick', '')
                    real_ou_odds = pred.get('ou_odds', '')
                    source_tag = "📊"  # cotes calculées

                # ── Ajustement ESPN (blessures + stats) ──────────────────
                base_ml_conf = pred.get('ml_confidence', pred.get('confidence', 50))
                espn_tag = ""
                ctx_game = None
                if ESPN_CONTEXT_AVAILABLE and espn_games_by_sport.get(sport_key):
                    ctx_game = find_game_context(away, home, espn_games_by_sport[sport_key])
                if ctx_game:
                    prob_adj = ctx_game.get('prob_adjustment', 0.0)
                    if prob_adj != 0.0:
                        # Determine if our pick aligns with ESPN's adjustment
                        home_in_pick = home.lower() in real_ml_pick.lower()
                        espn_agrees = (home_in_pick and prob_adj > 0) or \
                                      (not home_in_pick and prob_adj < 0)
                        delta = min(10, int(abs(prob_adj) * 100))
                        if espn_agrees:
                            base_ml_conf = min(97, base_ml_conf + delta)
                            espn_tag = " 🏥✅"
                        else:
                            base_ml_conf = max(10, base_ml_conf - delta)
                            espn_tag = " 🏥⚠️"

                late_tag = " ⚡ EN COURS" if match_is_live else ""
                all_picks.append({
                    "label": f"{emoji} {away} @ {home}{late_tag}",
                    "heure": qc_time.strftime('%H:%M') if not match_is_live else "EN COURS",
                    "source": source_tag,
                    # ML
                    "ml_pick": real_ml_pick,
                    "ml_odds": real_ml_odds,
                    "ml_confidence": base_ml_conf,
                    "ml_ev_pct": pred.get('ml_ev_pct', pred.get('ev_pct', '')),
                    "ml_status": pred.get('status', '') + espn_tag,
                    # Spread
                    "spread_pick": real_spread_pick,
                    "spread_odds": real_spread_odds,
                    "spread_confidence": pred.get('spread_confidence', 0),
                    # O/U
                    "ou_pick": real_ou_pick,
                    "ou_odds": real_ou_odds,
                    "ou_confidence": pred.get('ou_confidence', 0),
                    # pick FREE = ML
                    "pick": real_ml_pick,
                    "odds": real_ml_odds,
                    "confidence": base_ml_conf,
                    "ev": pred.get('ev_pct', ''),
                })
        except Exception as _pred_err:
            logger.warning(f"⚠️ Erreur prédiction [{sport_key}] {away} @ {home}: {_pred_err}")
            continue

    if not all_picks:
        return

    all_picks.sort(key=lambda x: x['confidence'], reverse=True)

    # ── Filtrage Brain : retire les picks sous le seuil appris ───────────
    if BRAIN_AVAILABLE and PICK_MEMORY_AVAILABLE:
        filtered = []
        for p in all_picks:
            sport_key = "NBA" if "🏀" in p["label"] else ("NHL" if "🏒" in p["label"] else "NFL")
            if should_send_pick(sport_key, p["confidence"], p.get("pick_type", "ML")):
                filtered.append(p)
            else:
                logger.info(f"🧠 Brain filter: BLOQUÉ {p['label']} conf={p['confidence']}% (sous seuil {sport_key})")
        if filtered:
            all_picks = filtered
            logger.info(f"🧠 Brain filter: {len(all_picks)} pick(s) retenus")

    heure_qc = quebec_time.strftime('%H:%M')

    # ── Canal FREE : 1 seul pick ML ───────────────────────────────────────
    free = all_picks[0]
    msg_free  = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg_free += f"🎯  U L T R O N  —  P I C K  G R A T U I T\n"
    msg_free += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg_free += f"🏟️  {free['label']}\n"
    msg_free += f"🕐  Match à  {free['heure']}  (heure Québec)\n\n"
    msg_free += f"✅  {free['ml_pick']}\n"
    msg_free += f"💵  Cote :  {free['ml_odds']}\n"
    msg_free += f"🔥  Confiance :  {free['ml_confidence']}%\n"
    msg_free += f"📈  EV :  {free['ml_ev_pct']}\n\n"
    msg_free += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg_free += f"💎  Spread + O/U + {len(all_picks)-1} autre(s) pick(s)\n"
    msg_free += "     disponibles en  V I P  ↑"

    try:
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg_free)
        logger.info(f"✅ Pick FREE envoyé: {free['label']}")
    except Exception as e:
        logger.error(f"❌ Erreur FREE: {e}")

    # ── Canal VIP : tous les picks avec ML + Spread + O/U ────────────────
    if TELEGRAM_CHAT_ID_VIP:
        src_label = "🟢 Cotes live" if any(p.get('source') == '🟢' for p in all_picks) else "📊 Modèle ML"
        msg_vip  = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg_vip += f"💎  U L T R O N  V I P\n"
        msg_vip += f"     {len(all_picks)} MATCH(S)  •  {heure_qc}  •  {src_label}\n"
        msg_vip += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, p in enumerate(all_picks, 1):
            emoji_rank = "🥇" if i == 1 else ("🥈" if i == 2 else "🏅")
            src = p.get('source', '📊')
            msg_vip += f"\n{emoji_rank}  {p['label']}  {src}\n"
            msg_vip += f"🕐  {p['heure']}  (heure Québec)\n\n"
            msg_vip += f"   📊  ML\n"
            msg_vip += f"        {p['ml_pick']}\n"
            msg_vip += f"        Cote {p['ml_odds']}  •  {p['ml_confidence']}%  •  {p['ml_status']}\n"
            if p['spread_pick']:
                msg_vip += f"\n   📏  SPREAD\n"
                msg_vip += f"        {p['spread_pick']}\n"
                msg_vip += f"        Cote {p['spread_odds']}  •  {p['spread_confidence']}%\n"
            if p['ou_pick']:
                msg_vip += f"\n   🔢  TOTAL (O/U)\n"
                msg_vip += f"        {p['ou_pick']}\n"
                msg_vip += f"        Cote {p['ou_odds']}  •  {p['ou_confidence']}%\n"
            msg_vip += f"\n   💰  EV :  {p['ml_ev_pct']}\n"
            msg_vip += "   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─\n"
        msg_vip += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg_vip += "🧠  Modèle ML  ULTRON v6.0\n"
        msg_vip += "     Bonne chance! 🍀"
        try:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=msg_vip)
            logger.info(f"✅ {len(all_picks)} picks VIP envoyés (ML+Spread+O/U)")
        except Exception as e:
            logger.error(f"❌ Erreur VIP: {e}")

    # ── Mémorisation des picks (auto-notation) ────────────────────────────
    if PICK_MEMORY_AVAILABLE:
        today_date = quebec_time.strftime('%Y-%m-%d')
        for p in all_picks:
            # On extrait le sport_key depuis le label (emoji)
            sport_label = "NBA" if "🏀" in p["label"] else ("NHL" if "🏒" in p["label"] else "NFL")
            # Extrait away/home depuis le label ex: "🏀 Boston Celtics @ Miami Heat"
            label_clean = p["label"].split(" ", 1)[-1]  # retire l'emoji
            parts = label_clean.split(" @ ")
            away_t = parts[0].strip() if len(parts) == 2 else p["label"]
            home_t = parts[1].strip() if len(parts) == 2 else ""
            save_pick(
                sport=sport_label,
                away_team=away_t,
                home_team=home_t,
                pick_type="ML",
                pick_team=p["ml_pick"].replace(" ML", "").strip().title(),
                odds=p["ml_odds"],
                confidence=p["ml_confidence"],
                ev_pct=p.get("ml_ev_pct", ""),
                game_date=today_date,
            )
        logger.info(f"💾 {len(all_picks)} picks mémorisés pour auto-notation")

    # ── Player Props NBA : joueurs des équipes concernées ────────────────
    import asyncio as _asyncio
    for p in all_picks:
        if "🏀" not in p["label"]:
            continue  # NBA uniquement
        label_clean = p["label"].split(" ", 1)[-1]  # retire l'emoji
        parts = label_clean.split(" @ ")
        if len(parts) != 2:
            continue
        away_t, home_t = parts[0].strip(), parts[1].strip()
        props_msg = _player_props_msg_for_match(away_t, home_t)
        if not props_msg:
            continue
        full_props = f"🏀 {away_t} @ {home_t}\n" + props_msg
        try:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_props)
            if TELEGRAM_CHAT_ID_VIP:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=full_props)
            logger.info(f"🌟 Props joueurs envoyés: {away_t} @ {home_t}")
        except Exception as _pe:
            logger.error(f"❌ Props joueurs envoi: {_pe}")
        await _asyncio.sleep(0.5)


async def auto_check_results(context):
    """
    Toutes les 2h: vérifie via ESPN les matchs terminés et note les picks.
    Envoie une notification de résultats dans FREE + VIP si des picks ont été gradés.
    Met aussi à jour les ratings Elo après chaque match gradé.
    """
    if not PICK_MEMORY_AVAILABLE or not TELEGRAM_CHAT_ID:
        return
    try:
        updated = check_and_update_results()
        if not updated:
            logger.info("ℹ️ auto_check_results: aucun nouveau résultat")
            return

        notif = format_result_notification(updated)
        if notif:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=notif)
            if TELEGRAM_CHAT_ID_VIP:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=notif)
            logger.info(f"✅ Résultats notifiés: {len(updated)} picks gradés")

        # ── Mise à jour Elo v2 pour chaque match gradé ──────────────────
        if ULTRON_V2_AVAILABLE:
            for pick in updated:
                try:
                    sport = pick.get('sport', '').upper()
                    if sport not in ('NBA', 'NHL', 'NFL'):
                        continue
                    score_str = pick.get('score', '')
                    if not score_str or '-' not in score_str:
                        continue
                    parts = score_str.split('-')
                    home_score = int(parts[0].strip())
                    away_score = int(parts[1].strip())
                    home_team  = pick.get('home_team', '')
                    away_team  = pick.get('away_team', '')
                    if not home_team or not away_team:
                        continue
                    home_won = home_score > away_score
                    winner   = home_team if home_won else away_team
                    loser    = away_team if home_won else home_team
                    margin   = abs(home_score - away_score)
                    elo = EloSystemV2(sport)
                    elo.update(winner, loser, margin, home_won)
                    logger.info(f"📊 Elo mis à jour [{sport}]: {winner} +, {loser} - (marge {margin})")
                except Exception as _elo_err:
                    logger.debug(f"⚠️ Elo update ignoré: {_elo_err}")
    except Exception as e:
        logger.error(f"❌ auto_check_results: {e}")


async def cmd_stats(update, context):
    """/stats — affiche le rapport de performance d'Ultron"""
    if not PICK_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Module de mémoire non disponible.")
        return

    # Parse l'argument optionnel: /stats 7 | /stats 30 | /stats 1 (défaut 7)
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
        except ValueError:
            pass

    report = format_daily_report(days=days)
    await update.message.reply_text(report)


async def cmd_recap(update, context):
    """/recap — envoie le récap des picks d'aujourd'hui avec résultats"""
    if not PICK_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Module de mémoire non disponible.")
        return
    try:
        # Vérification ESPN avant le récap
        updated = check_and_update_results()
        if updated:
            notif = format_result_notification(updated)
            if notif:
                await update.message.reply_text(notif)

        recap = format_today_recap()
        if recap:
            await update.message.reply_text(recap)
        else:
            await update.message.reply_text(
                "📋 Aucun pick enregistré aujourd'hui.\n"
                "Les picks sont sauvegardés automatiquement quand Ultron les envoie 1h avant un match."
            )
    except Exception as e:
        logger.error(f"❌ cmd_recap: {e}")
        await update.message.reply_text(f"❌ Erreur: {e}")


async def cmd_boxscore(update, context):
    """/boxscore <nba|nhl|nfl> — box scores en direct des matchs du jour"""
    if not ESPN_CONTEXT_AVAILABLE:
        await update.message.reply_text("⚠️ Module ESPN non disponible.")
        return
    sport = (context.args[0].upper() if context.args else "NBA")
    if sport not in ("NBA", "NHL", "NFL"):
        await update.message.reply_text("❌ Usage: /boxscore <nba|nhl|nfl>")
        return
    try:
        await update.message.reply_text(f"⏳ Récupération box scores {sport}...")
        messages = format_all_boxscores(sport)
        import asyncio
        for msg in messages:
            await update.message.reply_text(msg)
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"❌ cmd_boxscore: {e}")
        await update.message.reply_text(f"❌ Erreur boxscore: {e}")


async def cmd_leaders(update, context):
    """/leaders <nba|nhl|nfl> — leaders de statistiques de la saison"""
    if not ESPN_CONTEXT_AVAILABLE:
        await update.message.reply_text("⚠️ Module ESPN non disponible.")
        return
    sport = (context.args[0].upper() if context.args else "NBA")
    if sport not in ("NBA", "NHL", "NFL"):
        await update.message.reply_text("❌ Usage: /leaders <nba|nhl|nfl>")
        return
    try:
        await update.message.reply_text(f"⏳ Récupération leaders {sport}...")
        msg = format_leaders_message(sport)
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"❌ cmd_leaders: {e}")
        await update.message.reply_text(f"❌ Erreur leaders: {e}")


async def auto_check_game_starts(context):
    """
    Toutes les 5 minutes: alerte quand un match passe à 'In Progress'.
    Envoyé dans FREE et VIP.
    """
    if not TELEGRAM_CHAT_ID:
        return

    sports_config = [
        ("basketball/nba", "🏀"),
        ("hockey/nhl", "🏒"),
        ("football/nfl", "🏈"),
    ]

    for sport_path, emoji in sports_config:
        sport_key = sport_path.split('/')[1]
        try:
            now_utc_d = datetime.datetime.utcnow()
            dates_to_check = [
                now_utc_d.strftime("%Y%m%d"),
                (now_utc_d + datetime.timedelta(days=1)).strftime("%Y%m%d"),
            ]
            all_events_s = []
            for dq in dates_to_check:
                r2 = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={dq}", timeout=8)
                if r2.status_code == 200:
                    all_events_s.extend(r2.json().get('events', []))

            for event in all_events_s:
                try:
                    status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                    event_id = event.get('id', '')
                    notify_key = f"start_{sport_key}_{event_id}"

                    if 'in progress' in status_desc and notify_key not in _notified_starts:
                        _notified_starts.add(notify_key)
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('displayName', '?')
                            home = competitors[1].get('team', {}).get('displayName', '?')
                            msg = f"{emoji} MATCH EN COURS!\n"
                            msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
                            msg += f"  {away} @ {home}\n"
                            msg += f"  🕐 {get_quebec_time().strftime('%H:%M')} heure Québec\n"
                            msg += f"━━━━━━━━━━━━━━━━━━━━━"
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                            if TELEGRAM_CHAT_ID_VIP:
                                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=msg)
                            logger.info(f"✅ Alerte match en cours: {away} @ {home}")
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"⚠️ check_starts {sport_key}: {e}")


async def auto_boxscore(context):
    """
    Toutes les 20 minutes: envoie les box scores des matchs en cours.
    Envoyé uniquement si au moins un match est 'In Progress'.
    """
    if not ESPN_CONTEXT_AVAILABLE or not TELEGRAM_CHAT_ID:
        return
    import asyncio
    for sport in ("NBA", "NHL", "NFL"):
        try:
            games = get_live_game_ids(sport)
            live = [g for g in games if 'progress' in g.get('status', '').lower()]
            if not live:
                continue
            messages = format_all_boxscores(sport)
            for msg in messages:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                if TELEGRAM_CHAT_ID_VIP:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=msg)
                await asyncio.sleep(0.5)
            logger.info(f"📊 Auto box scores {sport}: {len(live)} match(s) en cours")
        except Exception as e:
            logger.error(f"❌ auto_boxscore {sport}: {e}")


async def auto_leaders_daily(context):
    """
    Chaque jour à midi heure Québec: envoie les leaders de stats pour NBA, NHL et NFL.
    """
    if not ESPN_CONTEXT_AVAILABLE or not TELEGRAM_CHAT_ID:
        return
    for sport in ("NBA", "NHL", "NFL"):
        try:
            msg = format_leaders_message(sport)
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
            if TELEGRAM_CHAT_ID_VIP:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=msg)
            logger.info(f"🏆 Auto leaders {sport} envoyés")
        except Exception as e:
            logger.error(f"❌ auto_leaders_daily {sport}: {e}")


def run_ultron_pipeline(bankroll=1000):
    """Lance le pipeline ULTRON (wrapper pour compatibilité avec main.py)"""
    logger.info(f"💰 Bankroll: ${bankroll}")
    main()

async def _post_init(app):
    """Exécuté au démarrage du bot — restaure la mémoire depuis Telegram si nécessaire."""
    if PICK_MEMORY_AVAILABLE and TELEGRAM_CHAT_ID:
        try:
            restored = await restore_from_telegram(app.bot, TELEGRAM_CHAT_ID)
            if restored:
                logger.info("♻️ Mémoire picks restaurée depuis Telegram")
        except Exception as e:
            logger.warning(f"⚠️ Restauration Telegram échouée: {e}")


async def auto_backup_memory(context):
    """Toutes les 6h : sauvegarde picks_history.json dans Telegram."""
    if PICK_MEMORY_AVAILABLE and TELEGRAM_CHAT_ID:
        await backup_to_telegram(context.bot, TELEGRAM_CHAT_ID)


async def auto_daily_recap(context):
    """23h00 heure Québec : résumé de tous les picks du jour avec résultats."""
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ auto_daily_recap: TELEGRAM_CHAT_ID non configuré")
        return
    try:
        if PICK_MEMORY_AVAILABLE:
            # Force une dernière vérification des résultats avant le récap
            updated = check_and_update_results()
            if updated:
                notif = format_result_notification(updated)
                if notif:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=notif)
                    if TELEGRAM_CHAT_ID_VIP:
                        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=notif)

            recap = format_today_recap()
        else:
            import datetime as dt
            recap = (
                "📋  U L T R O N  —  R É C A P  D U  J O U R\n"
                f"     {dt.datetime.now().strftime('%Y-%m-%d  %H:%M')} UTC\n\n"
                "⚠️  Module mémoire non disponible (pick_memory).\n"
                "    Vérifie les logs Railway pour l'erreur d'import."
            )

        if not recap:
            recap = "📋 Récap 23h — aucun pick enregistré aujourd'hui."

        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=recap)
        if TELEGRAM_CHAT_ID_VIP:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=recap)
        logger.info("✅ Récap journalier envoyé")
    except Exception as e:
        logger.error(f"❌ auto_daily_recap: {e}")
        try:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"❌ Erreur récap 23h:\n{e}"
            )
        except Exception:
            pass


async def auto_brain_analysis(context):
    """
    23h30 heure Québec (30 min après le récap) : auto-analyse ROI.
    Met à jour les seuils appris et envoie un rapport hebdomadaire (lundi seulement).
    Lance aussi run_analysis() silencieusement chaque soir pour garder les seuils à jour.
    """
    if not BRAIN_AVAILABLE or not TELEGRAM_CHAT_ID:
        return
    try:
        analysis = run_analysis()   # met toujours à jour les seuils
        # Rapport complet uniquement le lundi
        from datetime import datetime as _dt
        try:
            import pytz as _pytz
            _tz = _pytz.timezone("America/Toronto")
            _dow = _dt.now(_tz).weekday()   # 0 = lundi
        except Exception:
            _dow = _dt.now().weekday()

        if _dow == 0:   # lundi → rapport hebdomadaire
            report = format_brain_report(analysis)
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=report)
            if TELEGRAM_CHAT_ID_VIP:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID_VIP, text=report)
            logger.info("✅ Rapport Brain hebdomadaire envoyé (lundi)")
        else:
            logger.info("🧠 Brain: analyse silencieuse — seuils mis à jour")
    except Exception as e:
        logger.error(f"❌ auto_brain_analysis: {e}")


async def cmd_picks(update, context):
    """/picks — génère les picks du jour via moteur Elo + No-Vig + ESPN"""
    if not ULTRON_V2_AVAILABLE:
        await update.message.reply_text("⚠️ Module Ultron v2 non disponible.")
        return
    try:
        await update.message.reply_text(
            "🤖 *Ultron v2.0 analyse...*\n"
            "_Elo + No-Vig + ESPN + Régression_",
            parse_mode="Markdown"
        )
        engine   = UltronV2(bankroll=1000)
        result   = engine.run()
        messages = format_v2_report(result)
        import asyncio
        for msg in messages:
            await update.message.reply_text(msg, parse_mode="Markdown")
            await asyncio.sleep(1)
        logger.info(f"✅ /picks envoyé: {len(result.get('picks', []))} picks")

        # ── Props joueurs NBA pour chaque match retenu ────────────────
        nba_matches_seen: set = set()
        for pick in result.get('picks', []):
            if pick.get('sport', '').upper() != 'NBA':
                continue
            away_t = pick.get('away_team', '')
            home_t = pick.get('home_team', '')
            key = f"{away_t}@{home_t}"
            if key in nba_matches_seen or not away_t or not home_t:
                continue
            nba_matches_seen.add(key)
            props_msg = _player_props_msg_for_match(away_t, home_t)
            if props_msg:
                await update.message.reply_text(
                    f"🏀 {away_t} @ {home_t}\n" + props_msg
                )
                await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"❌ cmd_picks: {e}")
        await update.message.reply_text(f"❌ Erreur picks v2: {e}")


async def cmd_analyse(update, context):
    """/analyse — rapport d'auto-analyse ROI immédiat"""
    if not BRAIN_AVAILABLE:
        await update.message.reply_text("⚠️ Module Brain non disponible.")
        return
    try:
        await update.message.reply_text("🧠 Analyse en cours...")
        analysis = run_analysis()
        report   = format_brain_report(analysis)
        await update.message.reply_text(report)
    except Exception as e:
        logger.error(f"❌ cmd_analyse: {e}")
        await update.message.reply_text(f"❌ Erreur analyse: {e}")


def main():
    """Démarre le bot Telegram avec toutes les automations"""
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(_post_init).build()

    # ── Commandes manuelles ──────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nba", nba_matches))
    app.add_handler(CommandHandler("nhl", nhl_matches))
    app.add_handler(CommandHandler("nfl", nfl_matches))
    app.add_handler(CommandHandler("pronostics", pronostics))
    app.add_handler(CommandHandler("player", player_props))
    app.add_handler(CommandHandler("props_match", match_props))
    app.add_handler(CommandHandler("all_props", all_props))
    app.add_handler(CommandHandler("daily_props", daily_props))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("recap", cmd_recap))
    app.add_handler(CommandHandler("analyse", cmd_analyse))
    app.add_handler(CommandHandler("picks", cmd_picks))
    app.add_handler(CommandHandler("boxscore", cmd_boxscore))
    app.add_handler(CommandHandler("leaders", cmd_leaders))

    # ── Automations (JobQueue) ───────────────────────────────────────────
    job_queue = app.job_queue

    # Auto-pronostics: toutes les 30 minutes, vérifie les matchs dans ~1h
    job_queue.run_repeating(auto_send_pronostics, interval=1800, first=60)
    logger.info("⏰ Auto-pronostics: toutes les 30 minutes (1h avant matchs)")

    # Vérification des résultats: toutes les 2h (ESPN scoreboard final)
    if PICK_MEMORY_AVAILABLE:
        job_queue.run_repeating(auto_check_results, interval=7200, first=120)
        logger.info("📊 Auto-résultats: toutes les 2h via ESPN")

        # Backup Telegram: toutes les 6h (sauvegarde avant redéploiement)
        job_queue.run_repeating(auto_backup_memory, interval=21600, first=300)
        logger.info("🔒 Backup Telegram mémoire: toutes les 6h")

    # Alertes début de match: toutes les 5 minutes
    job_queue.run_repeating(auto_check_game_starts, interval=300, first=30)
    logger.info("🔔 Alertes matchs: toutes les 5 minutes")

    # Box scores en direct: toutes les 20 minutes (seulement si match en cours)
    if ESPN_CONTEXT_AVAILABLE:
        job_queue.run_repeating(auto_boxscore, interval=1200, first=90)
        logger.info("📊 Auto box scores: toutes les 20 min si match en cours")

        # Leaders de stats: chaque jour à midi heure Québec (UTC 16:00)
        import datetime as dt_l
        job_queue.run_daily(auto_leaders_daily, time=dt_l.time(hour=16, minute=0, tzinfo=pytz.utc))
        logger.info("🏆 Auto leaders: chaque jour à 12h00 heure Québec")

    # Message de motivation + résumé du jour: 9h00 heure Québec (UTC 13:00)
    import datetime as dt
    job_queue.run_daily(auto_daily_motivation, time=dt.time(hour=13, minute=0, tzinfo=pytz.utc))
    logger.info("🌅 Motivation + résumé quotidien: 9h00 heure Québec")

    # Récap de fin de journée: 23h00 heure Québec
    # Calcule dynamiquement le délai jusqu'au prochain 23h00 Québec
    # (évite le bug run_daily qui rate la soirée si le bot redémarre après 23h)
    _tz_qc = pytz.timezone("America/Toronto")
    _now_qc = dt.datetime.now(_tz_qc)
    _target_qc = _now_qc.replace(hour=23, minute=0, second=0, microsecond=0)
    if _target_qc <= _now_qc:
        _target_qc += dt.timedelta(days=1)
    _first_recap = max(10, (_target_qc - _now_qc).total_seconds())
    job_queue.run_repeating(auto_daily_recap, interval=86400, first=_first_recap)
    logger.info(f"📋 Récap journalier picks: 23h00 heure Québec (dans {int(_first_recap/3600)}h{int((_first_recap%3600)/60)}m)")

    # Auto-analyse Brain: 23h30 heure Québec (30 min après le récap)
    if BRAIN_AVAILABLE:
        _target_brain = _now_qc.replace(hour=23, minute=30, second=0, microsecond=0)
        if _target_brain <= _now_qc:
            _target_brain += dt.timedelta(days=1)
        _first_brain = max(10, (_target_brain - _now_qc).total_seconds())
        job_queue.run_repeating(auto_brain_analysis, interval=86400, first=_first_brain)
        logger.info(f"🧠 Auto-analyse Brain: 23h30 heure Québec (rapport lundi) (dans {int(_first_brain/3600)}h{int((_first_brain%3600)/60)}m)")

    logger.info("🚀 ULTRON v6.0 MULTISPORTS - DÉMARRAGE")
    logger.info("✅ NBA 🏀 + NHL 🏒 + NFL 🏈")

    # Modèles ML
    if SKLEARN_AVAILABLE:
        logger.info("🤖 Initialisation du modèle ML NBA...")
        train_nba_model()
    else:
        logger.warning("⚠️ scikit-learn non disponible - Utilisant modèle statistique")

    if XGBOOST_AVAILABLE:
        logger.info("🤖 Initialisation du modèle Player Props XGBoost...")
        train_player_props_model()
    else:
        logger.warning("⚠️ XGBoost non disponible - Prédictions player props désactivées")

    app.run_polling()

if __name__ == "__main__":
    main()
