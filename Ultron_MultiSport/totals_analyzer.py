#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON — totals_analyzer.py

Module d'analyse des totaux O/U pour NBA, NHL et MLB.

Sources :
  • ESPN API   — stats offensives/défensives, forme récente, blessures
  • Odds API   — cotes O/U réelles en temps réel (totals market)

Logique :
  1. Prédit le total attendu via modèle ESPN (stats L10 + défense + contexte)
  2. Compare à la ligne bookmaker (Odds API)
  3. Calcule l'EV vs cotes réelles
  4. Envoie uniquement les picks avec EV > 0

Usage :
    from totals_analyzer import run_totals_analysis
    picks = run_totals_analysis()
"""

import os
import math
import logging
import datetime
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

ODDS_API_KEY   = os.environ.get("ODDS_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_VIP   = os.environ.get("TELEGRAM_CHAT_ID_VIP", "")

# Seuils
MIN_EV           = 0.01   # EV minimum pour envoyer (1%)
MIN_CONFIDENCE   = 58     # Confiance minimale /100
MIN_DIFF_TO_LINE = 1.5    # Écart minimum prédiction vs ligne pour valider

# Session HTTP réutilisable
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "UltronBot/6.0"})
_TIMEOUT = 10

# Cache en mémoire pour éviter les requêtes répétées dans un même run
_CACHE: dict = {}

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG PAR SPORT
# ─────────────────────────────────────────────────────────────────────────────

SPORT_CONFIG = {
    "NBA": {
        "odds_key":      "basketball_nba",
        "espn_sport":    "basketball/nba",
        "ou_label":      "Total Points",
        "emoji":         "🏀",
        "avg_total":     225.0,   # total moyen ligue NBA
        "std_dev":       12.0,    # écart-type typique des totaux NBA
        "home_boost":    2.5,     # pts bonus domicile
        "b2b_penalty":   5.0,     # pts retirés si back-to-back
        "off_key":       "avgPoints",
        "def_key":       "avgPointsAllowed",
    },
    "NHL": {
        "odds_key":      "icehockey_nhl",
        "espn_sport":    "hockey/nhl",
        "ou_label":      "Total Goals",
        "emoji":         "🏒",
        "avg_total":     5.8,
        "std_dev":       1.4,
        "home_boost":    0.15,
        "b2b_penalty":   0.4,
        "off_key":       "avgGoals",
        "def_key":       "avgGoalsAllowed",
    },
    "MLB": {
        "odds_key":      "baseball_mlb",
        "espn_sport":    "baseball/mlb",
        "ou_label":      "Total Runs",
        "emoji":         "⚾",
        "avg_total":     8.5,
        "std_dev":       2.2,
        "home_boost":    0.3,
        "b2b_penalty":   0.2,
        "off_key":       "avgRuns",
        "def_key":       "avgRunsAllowed",
    },
}

# Bookmakers prioritaires pour les cotes
BK_PRIORITY = ["draftkings", "fanduel", "betmgm", "bet365", "bovada", "pointsbet"]

# ─────────────────────────────────────────────────────────────────────────────
# PARK FACTORS MLB — multiplicateur de scoring selon le stade du match
# ─────────────────────────────────────────────────────────────────────────────
# 1.00 = neutre (score moyen ligue). >1.00 = favorise l'attaque (plus de runs).
# <1.00 = favorise le pitching (moins de runs). Basé sur des tendances connues
# et publiées (altitude, dimensions du terrain, conditions climatiques types).
# ⚠️ À RECALIBRER chaque saison avec les vrais park factors officiels
# (ex: source ESPN/FanGraphs park factors) — ces valeurs sont des estimations
# de départ, pas des chiffres officiels à jour.
MLB_PARK_FACTORS = {
    "COL": 1.15,  # Coors Field — altitude, l'effet le plus documenté du MLB
    "BOS": 1.06,  # Fenway Park — Green Monster, champ gauche court
    "CIN": 1.05,  # Great American Ball Park — dimensions favorables aux CC
    "TEX": 1.04,  # Globe Life Field
    "BAL": 1.03,  # Camden Yards
    "PHI": 1.02,  # Citizens Bank Park
    "MIN": 1.01,
    "HOU": 1.01,
    "CHC": 1.00,  # Wrigley Field — dépend fortement du vent (variable)
    "ATL": 1.00,
    "ARI": 1.00,
    "MIL": 0.99,
    "TOR": 0.99,
    "WSH": 0.99,
    "NYY": 0.98,
    "LAA": 0.98,
    "STL": 0.98,
    "CHW": 0.97,
    "KC":  0.97,
    "NYM": 0.97,
    "CLE": 0.96,
    "TB":  0.96,
    "DET": 0.96,
    "LAD": 0.95,
    "PIT": 0.95,
    "OAK": 0.94,
    "SD":  0.94,
    "MIA": 0.93,  # loanDepot Park — pitcher friendly
    "SEA": 0.93,  # T-Mobile Park — pitcher friendly, air marin
    "SF":  0.91,  # Oracle Park — le plus pitcher-friendly du MLB
}


def get_mlb_park_factor(home_abbr: str) -> float:
    """Retourne le park factor du stade domicile (1.00 si équipe inconnue)."""
    return MLB_PARK_FACTORS.get(home_abbr.upper(), 1.00)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS HTTP
# ─────────────────────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None) -> Optional[dict]:
    """GET avec cache mémoire, timeout et gestion d'erreur centralisée."""
    cache_key = url + str(sorted((params or {}).items()))
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    try:
        resp = _SESSION.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        _CACHE[cache_key] = data
        return data
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Timeout: {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"⚠️ HTTP {e.response.status_code}: {url}")
    except Exception as e:
        logger.error(f"❌ Requête échouée: {url} — {e}")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — MATCHS DU JOUR
# ─────────────────────────────────────────────────────────────────────────────

def get_games_today(sport: str) -> list:
    """
    Retourne les matchs du jour pour un sport donné.
    Filtre les matchs déjà terminés.
    """
    cfg   = SPORT_CONFIG[sport]
    today = datetime.datetime.now().strftime("%Y%m%d")
    url   = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/scoreboard?dates={today}"
    )
    data = _get(url)
    if not data:
        return []

    games = []
    for event in data.get("events", []):
        status = event.get("status", {}).get("type", {}).get("name", "").lower()
        if "final" in status or "completed" in status:
            continue

        # Filtre matchs déjà commencés (cotes instables)
        commence = event.get("date", "")
        if commence:
            try:
                from datetime import timezone
                game_dt = datetime.datetime.fromisoformat(
                    commence.replace("Z", "+00:00")
                )
                if game_dt < datetime.datetime.now(timezone.utc):
                    continue
            except Exception:
                pass

        comp  = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue

        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])

        games.append({
            "game_id":   event.get("id", ""),
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_abbr": home.get("team", {}).get("abbreviation", ""),
            "away_abbr": away.get("team", {}).get("abbreviation", ""),
            "commence":  commence,
            "venue":     comp.get("venue", {}).get("fullName", ""),
        })

    logger.info(f"📅 {sport}: {len(games)} matchs trouvés")
    return games

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — STATS ÉQUIPE
# ─────────────────────────────────────────────────────────────────────────────

def _get_team_id(sport: str, team_abbr: str) -> Optional[str]:
    """
    Récupère l'ID ESPN d'une équipe.
    Cache global pour éviter les requêtes répétées.
    """
    cache_key = f"team_id_{sport}_{team_abbr.upper()}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    cfg = SPORT_CONFIG[sport]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/teams"
    )
    data = _get(url)
    if not data:
        return None

    try:
        teams = (
            data.get("sports", [{}])[0]
                .get("leagues", [{}])[0]
                .get("teams", [])
        )
        for t in teams:
            team = t.get("team", {})
            abbr = team.get("abbreviation", "").upper()
            tid  = team.get("id")
            if abbr and tid:
                _CACHE[f"team_id_{sport}_{abbr}"] = tid
    except Exception as e:
        logger.warning(f"⚠️ _get_team_id {sport} {team_abbr}: {e}")

    return _CACHE.get(cache_key)


def get_team_stats(sport: str, team_abbr: str) -> dict:
    """
    Récupère les stats offensives/défensives ESPN d'une équipe.
    Retourne les moyennes de points/buts/runs marqués et concédés.
    """
    team_id = _get_team_id(sport, team_abbr)
    if not team_id:
        return {}

    cfg = SPORT_CONFIG[sport]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/teams/{team_id}/statistics"
    )
    data = _get(url)
    if not data:
        return {}

    # Parse les stats dans un dict plat
    raw: dict = {}
    try:
        for cat in data.get("results", {}).get("stats", {}).get("categories", []):
            for s in cat.get("stats", []):
                raw[s.get("name", "")] = float(s.get("value", 0) or 0)
    except Exception as e:
        logger.warning(f"⚠️ Parsing stats {sport} {team_abbr}: {e}")

    # Mapping universel par sport
    off_val = raw.get(cfg["off_key"], 0)
    def_val = raw.get(cfg["def_key"], 0)

    # Fallbacks ESPN selon le sport si clé absente
    if off_val == 0:
        for fallback in ["avgPoints", "avgGoals", "avgRuns", "pointsPerGame"]:
            if raw.get(fallback, 0) > 0:
                off_val = raw[fallback]
                break
    if def_val == 0:
        for fallback in ["avgPointsAllowed", "avgGoalsAllowed", "avgRunsAllowed"]:
            if raw.get(fallback, 0) > 0:
                def_val = raw[fallback]
                break

    return {
        "off_avg":      round(off_val, 2),
        "def_avg":      round(def_val, 2),
        "net":          round(off_val - def_val, 2),
        "win_pct":      raw.get("winPct", 0.5),
        "home_off_avg": raw.get("homeAvgPoints",
                        raw.get("homeAvgGoals",
                        raw.get("homeAvgRuns", off_val))),
        "away_off_avg": raw.get("awayAvgPoints",
                        raw.get("awayAvgGoals",
                        raw.get("awayAvgRuns", off_val))),
    }


def get_team_last10(sport: str, team_abbr: str) -> dict:
    """
    Récupère les 10 derniers matchs depuis ESPN gamelog.
    Calcule la moyenne offensive et défensive récente.
    """
    team_id = _get_team_id(sport, team_abbr)
    if not team_id:
        return {}

    cfg = SPORT_CONFIG[sport]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/teams/{team_id}/schedule"
    )
    data = _get(url)
    if not data:
        return {}

    completed = []
    try:
        for event in data.get("events", []):
            comp   = event.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {})
            if not status.get("completed"):
                continue

            competitors = comp.get("competitors", [])
            team_data = next(
                (c for c in competitors
                 if c.get("team", {}).get("abbreviation", "").upper()
                 == team_abbr.upper()),
                None,
            )
            opp_data = next(
                (c for c in competitors
                 if c.get("team", {}).get("abbreviation", "").upper()
                 != team_abbr.upper()),
                None,
            )
            if not team_data or not opp_data:
                continue

            try:
                pts_for     = float(team_data.get("score", 0) or 0)
                pts_against = float(opp_data.get("score", 0) or 0)
                completed.append({
                    "pts_for":     pts_for,
                    "pts_against": pts_against,
                    "total":       pts_for + pts_against,
                })
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.warning(f"⚠️ get_team_last10 {sport} {team_abbr}: {e}")

    last10 = completed[-10:]
    if not last10:
        return {}

    n         = len(last10)
    avg_for   = sum(g["pts_for"]     for g in last10) / n
    avg_ag    = sum(g["pts_against"] for g in last10) / n
    avg_total = sum(g["total"]       for g in last10) / n

    return {
        "off_l10":    round(avg_for,   2),
        "def_l10":    round(avg_ag,    2),
        "total_l10":  round(avg_total, 2),
        "games":      n,
        "totals_list": [g["total"] for g in last10],
    }


def get_injuries(sport: str) -> list:
    """Récupère les blessures ESPN pour un sport."""
    cfg = SPORT_CONFIG[sport]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/injuries"
    )
    data = _get(url)
    if not data:
        return []

    injuries = []
    for team in data.get("injuries", []):
        team_name = team.get("team", {}).get("displayName", "")
        for p in team.get("injuries", []):
            injuries.append({
                "team":   team_name,
                "player": p.get("athlete", {}).get("displayName", ""),
                "status": p.get("status", "").lower(),
                "pos":    p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
            })
    return injuries


def _count_key_injuries(team_name: str, injuries: list, sport: str) -> int:
    """
    Compte les joueurs clés OUT pour une équipe.
    NBA: G/F avec OUT
    NHL: Gardien (G) ou attaquant vedette
    MLB: Lanceur partant ou frappeur cleanup
    """
    key_pos = {
        "NBA": {"PG", "SG", "SF", "PF", "C", "G", "F"},
        "NHL": {"G", "C", "LW", "RW", "D"},
        "MLB": {"SP", "RP", "1B", "2B", "3B", "SS", "OF", "C", "DH"},
    }.get(sport, set())

    count = 0
    for inj in injuries:
        if (team_name.lower() in inj["team"].lower()
                and "out" in inj["status"]
                and inj["pos"].upper() in key_pos):
            count += 1
    return count


def is_b2b(sport: str, team_abbr: str) -> bool:
    """Vérifie si une équipe joue en back-to-back aujourd'hui."""
    yesterday = (
        datetime.datetime.now() - datetime.timedelta(days=1)
    ).strftime("%Y%m%d")

    cfg = SPORT_CONFIG[sport]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{cfg['espn_sport']}/scoreboard?dates={yesterday}"
    )
    data = _get(url)
    if not data:
        return False

    abbr = team_abbr.upper()
    for event in data.get("events", []):
        status = event.get("status", {}).get("type", {})
        if not (status.get("completed") or "final" in
                event.get("status", {}).get("type", {}).get("name", "").lower()):
            continue
        comp  = event.get("competitions", [{}])[0]
        for t in comp.get("competitors", []):
            if t.get("team", {}).get("abbreviation", "").upper() == abbr:
                return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# ODDS API — TOTAUX O/U
# ─────────────────────────────────────────────────────────────────────────────

def get_totals_odds(sport: str) -> list:
    """
    Récupère les cotes O/U totaux depuis The Odds API.
    Retourne une liste d'événements avec leur ligne et cotes O/U.
    Cache 4h pour économiser le quota mensuel.
    """
    if not ODDS_API_KEY:
        logger.warning("⚠️ ODDS_API_KEY absent — cotes O/U indisponibles")
        return []

    cache_key = f"totals_{sport}_{datetime.datetime.now().strftime('%Y%m%d_%H')}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    cfg = SPORT_CONFIG[sport]
    url = f"https://api.the-odds-api.com/v4/sports/{cfg['odds_key']}/odds/"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "totals",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    try:
        resp = _SESSION.get(url, params=params, timeout=_TIMEOUT)
        remaining = resp.headers.get("x-requests-remaining", "?")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            _CACHE[cache_key] = data
            logger.info(
                f"✅ Odds API {sport} totals: {len(data)} matchs "
                f"| restantes={remaining}"
            )
            return data
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        if code == 401:
            logger.error("❌ Odds API: clé invalide (401)")
        elif code == 429:
            logger.warning("⚠️ Odds API: quota dépassé (429)")
        else:
            logger.warning(f"⚠️ Odds API {sport}: HTTP {code}")
    except Exception as e:
        logger.error(f"❌ Odds API {sport} totals: {e}")

    return []


def _extract_totals_line(bookmakers: list) -> dict:
    """
    Extrait la meilleure ligne O/U parmi les bookmakers.
    Priorité: DraftKings > FanDuel > BetMGM > autres.
    Retourne: {line, over_odds, under_odds, bookmaker}
    """
    sorted_bk = sorted(
        bookmakers,
        key=lambda b: BK_PRIORITY.index(b["key"])
        if b["key"] in BK_PRIORITY else 99,
    )

    for bk in sorted_bk:
        for market in bk.get("markets", []):
            if market.get("key") != "totals":
                continue
            over_odd  = None
            under_odd = None
            line_val  = None

            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "").lower()
                pt   = outcome.get("point", 0)
                price = outcome.get("price", 1.91)
                if "over" in name:
                    over_odd = price
                    line_val = pt
                elif "under" in name:
                    under_odd = price

            if over_odd and under_odd and line_val:
                return {
                    "line":       float(line_val),
                    "over_odds":  float(over_odd),
                    "under_odds": float(under_odd),
                    "bookmaker":  bk.get("title", bk["key"]),
                }

    return {}


def _match_game_to_odds(
    home_team: str, away_team: str, odds_events: list
) -> Optional[dict]:
    """
    Trouve l'événement Odds API correspondant à un match ESPN.
    Match strict: les deux équipes doivent correspondre.
    """
    home_token = home_team.lower().split()[-1]
    away_token = away_team.lower().split()[-1]

    for event in odds_events:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if home_token in h and away_token in a:
            return event

    # Deuxième passe plus souple
    for event in odds_events:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        home_words = [w for w in home_team.lower().split() if len(w) > 3]
        away_words = [w for w in away_team.lower().split() if len(w) > 3]
        if any(w in h for w in home_words) and any(w in a for w in away_words):
            return event

    return None

# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE DE PRÉDICTION DU TOTAL
# ─────────────────────────────────────────────────────────────────────────────

def predict_total(
    sport:          str,
    home_stats:     dict,
    away_stats:     dict,
    home_l10:       dict,
    away_l10:       dict,
    home_injuries:  int,
    away_injuries:  int,
    home_is_b2b:    bool,
    away_is_b2b:    bool,
    park_factor:    float = 1.00,
) -> dict:
    """
    Prédit le total attendu pour un match.

    Formule en 3 couches :
      1. Base saison   (40%) : avg_off_home + avg_def_away + avg_off_away + avg_def_home
      2. Forme récente (40%) : total_l10 des deux équipes
      3. Ajustements   (20%) : B2B, blessures, avantage domicile, park factor (MLB)

    Retourne: predicted_total, confidence (0-100), details
    """
    cfg = SPORT_CONFIG[sport]

    # ── Couche 1 : Base saison ───────────────────────────────────────────────
    home_off = home_stats.get("off_avg", cfg["avg_total"] / 2)
    home_def = home_stats.get("def_avg", cfg["avg_total"] / 2)
    away_off = away_stats.get("off_avg", cfg["avg_total"] / 2)
    away_def = away_stats.get("def_avg", cfg["avg_total"] / 2)

    # Total attendu = attaque de chaque équipe vs défense adverse
    total_season = (
        (home_off + away_def) / 2 +   # ce que home va marquer
        (away_off + home_def) / 2      # ce que away va marquer
    )

    # ── Couche 2 : Forme récente L10 ────────────────────────────────────────
    home_total_l10 = home_l10.get("total_l10", 0)
    away_total_l10 = away_l10.get("total_l10", 0)

    # Moyenne des totaux L10 des deux équipes
    if home_total_l10 > 0 and away_total_l10 > 0:
        total_l10 = (home_total_l10 + away_total_l10) / 2
    elif home_total_l10 > 0:
        total_l10 = home_total_l10
    elif away_total_l10 > 0:
        total_l10 = away_total_l10
    else:
        total_l10 = total_season

    # Blend saison + L10
    if total_season > 0 and total_l10 > 0:
        base = total_season * 0.40 + total_l10 * 0.40
    elif total_season > 0:
        base = total_season
    else:
        base = cfg["avg_total"]

    # ── Couche 3 : Ajustements contextuels ──────────────────────────────────
    adjustments = []
    adj_total   = 0.0

    # Avantage domicile (léger boost offensif)
    adj_total += cfg["home_boost"] * 0.20
    adjustments.append(f"+{cfg['home_boost']*0.20:.2f} domicile")

    # Back-to-back — équipes fatiguées marquent moins
    if home_is_b2b:
        adj_total -= cfg["b2b_penalty"]
        adjustments.append(f"-{cfg['b2b_penalty']} B2B home")
    if away_is_b2b:
        adj_total -= cfg["b2b_penalty"]
        adjustments.append(f"-{cfg['b2b_penalty']} B2B away")

    # Blessures — joueurs offensifs out = moins de points
    if home_injuries >= 2:
        inj_pen = cfg["b2b_penalty"] * 0.6
        adj_total -= inj_pen
        adjustments.append(f"-{inj_pen:.1f} blessures home ({home_injuries})")
    elif home_injuries == 1:
        inj_pen = cfg["b2b_penalty"] * 0.3
        adj_total -= inj_pen
        adjustments.append(f"-{inj_pen:.1f} blessure home (1)")

    if away_injuries >= 2:
        inj_pen = cfg["b2b_penalty"] * 0.6
        adj_total -= inj_pen
        adjustments.append(f"-{inj_pen:.1f} blessures away ({away_injuries})")
    elif away_injuries == 1:
        inj_pen = cfg["b2b_penalty"] * 0.3
        adj_total -= inj_pen
        adjustments.append(f"-{inj_pen:.1f} blessure away (1)")

    predicted = round(base + adj_total, 1)

    # Park factor MLB — appliqué au total complet, affecte les deux équipes
    # (Coors gonfle les runs pour QUI QUE CE SOIT qui frappe là-bas)
    if sport == "MLB" and park_factor != 1.00:
        pre_park = predicted
        predicted = round(predicted * park_factor, 1)
        adjustments.append(
            f"×{park_factor:.2f} park factor ({pre_park}→{predicted})"
        )

    predicted = max(cfg["avg_total"] * 0.6, predicted)  # plancher réaliste

    # ── Confiance ────────────────────────────────────────────────────────────
    conf_score = 50

    # Données L10 disponibles
    home_games = home_l10.get("games", 0)
    away_games = away_l10.get("games", 0)
    data_quality = min(home_games, away_games) / 10.0
    conf_score += int(data_quality * 20)

    # Cohérence saison vs L10
    if total_l10 > 0 and total_season > 0:
        deviation = abs(total_l10 - total_season) / total_season
        if deviation < 0.05:       # très cohérent
            conf_score += 15
        elif deviation < 0.10:
            conf_score += 8
        elif deviation > 0.20:     # forme très différente de la saison
            conf_score -= 10

    # Stats saison disponibles
    if home_off > 0 and away_off > 0:
        conf_score += 10

    # Pénalité si beaucoup d'ajustements négatifs
    negative_adjs = sum(1 for a in adjustments if a.startswith("-"))
    conf_score -= negative_adjs * 5

    confidence = max(10, min(95, conf_score))

    return {
        "predicted":    predicted,
        "base_season":  round(total_season, 1),
        "base_l10":     round(total_l10, 1),
        "adjustments":  adjustments,
        "confidence":   confidence,
        "data_quality": f"{min(home_games, away_games)}/10 matchs L10",
        "park_factor":  park_factor,
    }

# ─────────────────────────────────────────────────────────────────────────────
# CALCUL EV + HIT RATE
# ─────────────────────────────────────────────────────────────────────────────

def compute_ev(prob: float, odds: float) -> float:
    """EV = (odds - 1) × P(win) - P(lose)"""
    return round((odds - 1.0) * prob - (1.0 - prob), 4)


def compute_prob_from_diff(diff: float, std_dev: float) -> float:
    """
    Probabilité que le total dépasse/descende sous la ligne
    basée sur la distribution normale des totaux.

    diff > 0 → prédiction > ligne → OVER
    diff < 0 → prédiction < ligne → UNDER
    """
    z = abs(diff) / std_dev
    # Approximation CDF normale : P(Z < z)
    prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    # Clamp entre 40% et 85% — évite les certitudes excessives
    return max(0.40, min(0.85, prob))


def calculate_hit_rate(totals_list: list, line: float, side: str) -> float:
    """
    Calcule le hit rate historique L10 d'une équipe sur la ligne donnée.
    side: "OVER" ou "UNDER"
    """
    if not totals_list:
        return 0.5
    n = len(totals_list)
    if side == "OVER":
        hits = sum(1 for t in totals_list if t > line)
    else:
        hits = sum(1 for t in totals_list if t < line)
    return round(hits / n, 2)

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE D'UN MATCH
# ─────────────────────────────────────────────────────────────────────────────

def analyze_game_total(
    sport:       str,
    game:        dict,
    odds_events: list,
    injuries:    list,
) -> Optional[dict]:
    """
    Analyse complète du total O/U pour un match.
    Retourne None si EV négatif ou confiance insuffisante.
    """
    cfg        = SPORT_CONFIG[sport]
    home_abbr  = game["home_abbr"]
    away_abbr  = game["away_abbr"]
    home_team  = game["home_team"]
    away_team  = game["away_team"]

    # ── 1. Cotes Odds API ────────────────────────────────────────────────────
    odds_event = _match_game_to_odds(home_team, away_team, odds_events)
    if not odds_event:
        logger.debug(f"⏭️ Odds introuvables: {away_team} @ {home_team}")
        return None

    totals = _extract_totals_line(odds_event.get("bookmakers", []))
    if not totals or totals.get("line", 0) <= 0:
        logger.debug(f"⏭️ Pas de ligne O/U: {away_team} @ {home_team}")
        return None

    book_line  = totals["line"]
    over_odds  = totals["over_odds"]
    under_odds = totals["under_odds"]
    bookmaker  = totals["bookmaker"]

    # ── 2. Stats ESPN ─────────────────────────────────────────────────────────
    home_stats = get_team_stats(sport, home_abbr)
    away_stats = get_team_stats(sport, away_abbr)
    home_l10   = get_team_last10(sport, home_abbr)
    away_l10   = get_team_last10(sport, away_abbr)

    home_b2b   = is_b2b(sport, home_abbr)
    away_b2b   = is_b2b(sport, away_abbr)
    home_inj   = _count_key_injuries(home_team, injuries, sport)
    away_inj   = _count_key_injuries(away_team, injuries, sport)

    # Park factor — uniquement pertinent pour MLB (stade domicile fixe)
    park_factor = get_mlb_park_factor(home_abbr) if sport == "MLB" else 1.00

    # ── 3. Prédiction ─────────────────────────────────────────────────────────
    prediction = predict_total(
        sport         = sport,
        home_stats    = home_stats,
        away_stats    = away_stats,
        home_l10      = home_l10,
        away_l10      = away_l10,
        home_injuries = home_inj,
        away_injuries = away_inj,
        home_is_b2b   = home_b2b,
        away_is_b2b   = away_b2b,
        park_factor   = park_factor,
    )

    predicted  = prediction["predicted"]
    confidence = prediction["confidence"]
    diff       = predicted - book_line

    # Filtre écart minimum
    if abs(diff) < MIN_DIFF_TO_LINE:
        logger.debug(
            f"⏭️ Écart trop faible ({diff:+.1f}): "
            f"{away_team} @ {home_team} | ligne {book_line}"
        )
        return None

    # ── 4. Probabilité & EV ───────────────────────────────────────────────────
    side = "OVER" if diff > 0 else "UNDER"
    prob = compute_prob_from_diff(diff, cfg["std_dev"])
    ev   = compute_ev(prob, over_odds if side == "OVER" else under_odds)
    bet_odds = over_odds if side == "OVER" else under_odds

    # Filtre EV positif — critère principal
    if ev <= MIN_EV:
        logger.debug(
            f"⏭️ EV négatif ({ev:.3f}): "
            f"{away_team} @ {home_team} {side} {book_line}"
        )
        return None

    if confidence < MIN_CONFIDENCE:
        logger.debug(
            f"⏭️ Confiance trop faible ({confidence}/100): "
            f"{away_team} @ {home_team}"
        )
        return None

    # ── 5. Hit rate historique ────────────────────────────────────────────────
    home_totals = home_l10.get("totals_list", [])
    away_totals = away_l10.get("totals_list", [])

    hit_rate_home = calculate_hit_rate(home_totals, book_line, side)
    hit_rate_away = calculate_hit_rate(away_totals, book_line, side)
    hit_rate_combined = (
        (hit_rate_home + hit_rate_away) / 2
        if home_totals and away_totals
        else (hit_rate_home or hit_rate_away or 0.5)
    )

    # Bonus confiance si hit rate élevé
    if hit_rate_combined >= 0.70:
        confidence = min(95, confidence + 12)
    elif hit_rate_combined >= 0.60:
        confidence = min(95, confidence + 6)
    elif hit_rate_combined <= 0.30:
        confidence = max(10, confidence - 10)

    # Statut final
    if ev >= 0.04:
        status = "✅ BUY"
    else:
        status = "👀 MONITORING"

    return {
        # Identité du match
        "sport":          sport,
        "away_team":      away_team,
        "home_team":      home_team,
        "away_abbr":      away_abbr,
        "home_abbr":      home_abbr,
        # Pick
        "side":           side,
        "book_line":      book_line,
        "predicted":      predicted,
        "diff":           round(diff, 1),
        "bet_odds":       bet_odds,
        "over_odds":      over_odds,
        "under_odds":     under_odds,
        "bookmaker":      bookmaker,
        # Modèle
        "prob":           round(prob, 4),
        "ev":             ev,
        "ev_pct":         f"{ev*100:+.2f}%",
        "confidence":     confidence,
        "status":         status,
        # Contexte
        "base_season":    prediction["base_season"],
        "base_l10":       prediction["base_l10"],
        "adjustments":    prediction["adjustments"],
        "data_quality":   prediction["data_quality"],
        "hit_rate_home":  hit_rate_home,
        "hit_rate_away":  hit_rate_away,
        "hit_rate_comb":  round(hit_rate_combined, 2),
        "home_b2b":       home_b2b,
        "away_b2b":       away_b2b,
        "home_injuries":  home_inj,
        "away_injuries":  away_inj,
        "home_off":       home_stats.get("off_avg", 0),
        "away_off":       away_stats.get("off_avg", 0),
        "home_def":       home_stats.get("def_avg", 0),
        "away_def":       away_stats.get("def_avg", 0),
        "park_factor":    park_factor,
    }

# ─────────────────────────────────────────────────────────────────────────────
# FORMATAGE TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def _format_single_pick(pick: dict) -> str:
    """Formate un pick O/U individuel pour Telegram."""
    cfg        = SPORT_CONFIG[pick["sport"]]
    side_emoji = "⬆️" if pick["side"] == "OVER" else "⬇️"
    conf_emoji = "🔥" if pick["confidence"] >= 75 else "✅"
    b2b_tags   = []
    if pick["home_b2b"]:
        b2b_tags.append(f"{pick['home_abbr']} B2B")
    if pick["away_b2b"]:
        b2b_tags.append(f"{pick['away_abbr']} B2B")
    b2b_str = f" ⚠️ {', '.join(b2b_tags)}" if b2b_tags else ""

    inj_parts = []
    if pick["home_injuries"] > 0:
        inj_parts.append(f"{pick['home_abbr']} -{pick['home_injuries']}")
    if pick["away_injuries"] > 0:
        inj_parts.append(f"{pick['away_abbr']} -{pick['away_injuries']}")
    inj_str = f" 🏥 {', '.join(inj_parts)}" if inj_parts else ""

    adj_str = " | ".join(pick["adjustments"][:3]) if pick["adjustments"] else "—"

    park_str = ""
    if pick["sport"] == "MLB" and pick.get("park_factor", 1.0) != 1.0:
        pf = pick["park_factor"]
        tag = "🏟️ terrain offensif" if pf > 1.0 else "🏟️ terrain pitching"
        park_str = f" {tag} (×{pf:.2f})"

    lines = [
        f"{conf_emoji} *{pick['away_team']} @ {pick['home_team']}*{b2b_str}{inj_str}{park_str}",
        (
            f"   {side_emoji} *{pick['side']} {pick['book_line']}* "
            f"{cfg['ou_label']} @ `{pick['bet_odds']:.2f}`"
        ),
        (
            f"   📊 Prédit: *{pick['predicted']}* "
            f"| Saison: {pick['base_season']} "
            f"| L10: {pick['base_l10']}"
        ),
        (
            f"   🎯 Hit rate L10: *{pick['hit_rate_comb']:.0%}* "
            f"| EV: *{pick['ev_pct']}*"
        ),
        f"   🔧 Ajust.: {adj_str}",
        (
            f"   💡 Confiance: *{pick['confidence']}/100* "
            f"| 💼 {pick['bookmaker']}"
        ),
    ]
    return "\n".join(lines)


def format_totals_message(picks: list) -> str:
    """Formate le message complet des picks O/U pour Telegram."""
    if not picks:
        return "❌ Aucun pick O/U avec EV positif trouvé aujourd'hui."

    now = datetime.datetime.now().strftime("%H:%M")

    buy_picks = [p for p in picks if p["status"] == "✅ BUY"]
    mon_picks = [p for p in picks if p["status"] == "👀 MONITORING"]

    # Regrouper par sport
    sport_counts = {}
    for p in picks:
        sport_counts[p["sport"]] = sport_counts.get(p["sport"], 0) + 1

    sport_summary = " | ".join(
        f"{SPORT_CONFIG[s]['emoji']} {s}: {n}"
        for s, n in sport_counts.items()
    )

    lines = [
        "🎯 *ULTRON — TOTAUX O/U*",
        f"🕐 {now} (Québec) | {sport_summary}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if buy_picks:
        lines.append(f"\n✅ *BUY — EV ≥ +4% ({len(buy_picks)})*\n")
        for p in buy_picks:
            lines.append(_format_single_pick(p))
            lines.append("")

    if mon_picks:
        lines.append(f"👀 *MONITORING — EV positif ({len(mon_picks)})*\n")
        for p in mon_picks[:4]:  # max 4 monitoring pour éviter message trop long
            lines.append(_format_single_pick(p))
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"📊 {len(picks)} pick(s) EV+ | "
        f"{len(buy_picks)} BUY | {len(mon_picks)} MONITORING"
    )
    lines.append(
        "⚠️ _Mise suggérée: 1-2% bankroll par pick. "
        "Ne jamais miser plus de 5% sur un seul pari._"
    )

    return "\n".join(lines)


def send_telegram(message: str, chat_id: str) -> None:
    if not TELEGRAM_TOKEN or not chat_id:
        return
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "Markdown",
    }
    try:
        resp = _SESSION.post(url, json=payload, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.error(f"❌ Telegram {resp.status_code}: {resp.text[:150]}")
        else:
            logger.info(f"✅ Message Telegram envoyé → {chat_id}")
    except Exception as e:
        logger.error(f"❌ Telegram send: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_totals_analysis(
    sports: list = None,
    send:   bool = True,
) -> list:
    """
    Lance l'analyse O/U pour tous les sports (ou ceux spécifiés).

    1. Récupère les matchs ESPN du jour par sport
    2. Récupère les cotes O/U Odds API (une requête par sport)
    3. Pour chaque match: stats + L10 + blessures + B2B + prédiction
    4. Filtre uniquement les picks avec EV positif
    5. Envoie via Telegram si send=True

    Retourne la liste des picks triés par EV décroissant.
    """
    if sports is None:
        sports = ["NBA", "NHL", "MLB"]

    logger.info(f"🎯 Ultron — Analyse Totaux O/U: {', '.join(sports)}")

    # Vider le cache à chaque run pour avoir des données fraîches
    _CACHE.clear()

    all_picks = []

    for sport in sports:
        if sport not in SPORT_CONFIG:
            logger.warning(f"⚠️ Sport inconnu: {sport}")
            continue

        logger.info(f"\n{'─'*40}")
        logger.info(f"{SPORT_CONFIG[sport]['emoji']} Analyse {sport}...")

        # Matchs du jour
        games = get_games_today(sport)
        if not games:
            logger.info(f"ℹ️ Aucun match {sport} aujourd'hui")
            continue

        # Cotes Odds API (une seule requête pour tous les matchs du sport)
        odds_events = get_totals_odds(sport)
        if not odds_events:
            logger.warning(f"⚠️ Cotes {sport} indisponibles — sport ignoré")
            continue

        # Blessures ESPN (une seule requête pour tous les matchs du sport)
        injuries = get_injuries(sport)
        logger.info(f"🏥 {sport}: {len(injuries)} blessures chargées")

        # Analyse par match
        sport_picks = []
        for game in games:
            try:
                logger.info(
                    f"  🔍 {game['away_team']} @ {game['home_team']}"
                )
                result = analyze_game_total(sport, game, odds_events, injuries)
                if result:
                    sport_picks.append(result)
                    logger.info(
                        f"     ✅ {result['side']} {result['book_line']} "
                        f"| Prédit: {result['predicted']} "
                        f"| EV: {result['ev_pct']} "
                        f"| Conf: {result['confidence']}/100"
                    )
                else:
                    logger.info(f"     ⏭️ Pas de valeur EV+")
            except Exception as e:
                logger.error(
                    f"❌ Erreur analyse {sport} "
                    f"{game['away_team']} @ {game['home_team']}: {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"  📊 {sport}: {len(sport_picks)} pick(s) EV+")
        all_picks.extend(sport_picks)

    # Trier par EV décroissant
    all_picks.sort(key=lambda x: x["ev"], reverse=True)

    buy_count = sum(1 for p in all_picks if p["status"] == "✅ BUY")
    logger.info(
        f"\n✅ Totaux terminés: {len(all_picks)} pick(s) EV+ "
        f"| BUY: {buy_count}"
    )

    # Envoi Telegram
    if send and all_picks:
        msg = format_totals_message(all_picks)
        if TELEGRAM_CHAT:
            send_telegram(msg, TELEGRAM_CHAT)
        if TELEGRAM_VIP:
            send_telegram(msg, TELEGRAM_VIP)

    return all_picks

# ─────────────────────────────────────────────────────────────────────────────
# INTÉGRATION pick_memory — sauvegarde automatique des picks
# ─────────────────────────────────────────────────────────────────────────────

def run_totals_and_save(sports: list = None, send: bool = True) -> list:
    """
    Lance l'analyse O/U ET sauvegarde les picks dans PostgreSQL.
    À utiliser à la place de run_totals_analysis() si pick_memory est disponible.
    """
    picks = run_totals_analysis(sports=sports, send=send)

    try:
        from pick_memory import save_pick
        today = datetime.date.today().isoformat()
        for p in picks:
            save_pick(
                sport      = p["sport"],
                away_team  = p["away_team"],
                home_team  = p["home_team"],
                pick_type  = "OU",
                pick_team  = f"{p['side']} {p['book_line']}",
                odds       = p["bet_odds"],
                game_date  = today,
                pick_side  = p["side"],
                line       = p["book_line"],
                confidence = p["confidence"],
                ev_pct     = p["ev_pct"],
                predicted_value = p["predicted"],
                notes      = f"Prédit: {p['predicted']} | L10: {p['base_l10']}",
            )
        if picks:
            logger.info(f"💾 {len(picks)} picks O/U sauvegardés en base")
    except ImportError:
        logger.debug("ℹ️ pick_memory non disponible — picks non sauvegardés")
    except Exception as e:
        logger.error(f"❌ Sauvegarde picks O/U: {e}")

    return picks

# ─────────────────────────────────────────────────────────────────────────────
# TEST LOCAL
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    picks = run_totals_analysis(send=False)

    print(f"\n{'='*60}")
    print(f"RÉSULTAT: {len(picks)} pick(s) O/U avec EV positif")
    print(f"{'='*60}")

    for p in picks:
        emoji = SPORT_CONFIG[p["sport"]]["emoji"]
        print(
            f"\n{emoji} [{p['sport']}] "
            f"{p['away_team']} @ {p['home_team']}\n"
            f"   {p['side']} {p['book_line']} | "
            f"Prédit: {p['predicted']} | "
            f"EV: {p['ev_pct']} | "
            f"Conf: {p['confidence']}/100\n"
            f"   Hit rate L10: {p['hit_rate_comb']:.0%} | "
            f"Statut: {p['status']}"
        )

    if picks:
        print(f"\n{'─'*60}")
        print(format_totals_message(picks))
