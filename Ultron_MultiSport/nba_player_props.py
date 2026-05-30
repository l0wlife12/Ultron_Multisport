#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON — nba_player_props.py

Moteur de props joueurs NBA 100% données réelles.

Sources :
  • ESPN API  — stats saison + stats L10 + blessures + matchup défensif
  • Odds API  — cotes props points O/U en temps réel (player_props market)

Top 15 stars ciblées. Aucune donnée hardcodée — tout est récupéré en direct.

Usage :
    from nba_player_props import run_props_analysis
    picks = run_props_analysis()
    # picks → liste de dicts triés par EV décroissant
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

# Seuils de filtrage
MIN_EV         = 0.02   # EV minimum pour envoyer un pick (2%)
MIN_CONFIDENCE = 58     # Confiance minimale /100
MIN_SAMPLE     = 5      # Minimum de matchs dans le L10 pour valider

# Cache ESPN — évite de refaire les mêmes requêtes dans un même run
_CACHE: dict = {}
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "UltronBot/6.0"})
_TIMEOUT = 10

# ─────────────────────────────────────────────────────────────────────────────
# TOP 15 STARS NBA — identifiants ESPN fixes
# Mis à jour manuellement chaque saison (noms stables, IDs ESPN stables)
# ─────────────────────────────────────────────────────────────────────────────

TOP_STARS = [
    {"name": "Nikola Jokic",             "espn_id": "3112335", "team_abbr": "DEN", "pos": "C"},
    {"name": "Shai Gilgeous-Alexander",  "espn_id": "4278073", "team_abbr": "OKC", "pos": "G"},
    {"name": "Giannis Antetokounmpo",    "espn_id": "3032977", "team_abbr": "MIL", "pos": "F"},
    {"name": "Luka Doncic",              "espn_id": "3945274", "team_abbr": "DAL", "pos": "G"},
    {"name": "Jayson Tatum",             "espn_id": "4065648", "team_abbr": "BOS", "pos": "F"},
    {"name": "Anthony Davis",            "espn_id": "6583",    "team_abbr": "LAL", "pos": "C"},
    {"name": "Kevin Durant",             "espn_id": "3202",    "team_abbr": "PHX", "pos": "F"},
    {"name": "LeBron James",             "espn_id": "1966",    "team_abbr": "LAL", "pos": "F"},
    {"name": "Stephen Curry",            "espn_id": "3975",    "team_abbr": "GSW", "pos": "G"},
    {"name": "Devin Booker",             "espn_id": "3136193", "team_abbr": "PHX", "pos": "G"},
    {"name": "Damian Lillard",           "espn_id": "6606",    "team_abbr": "MIL", "pos": "G"},
    {"name": "Kawhi Leonard",            "espn_id": "6450",    "team_abbr": "LAC", "pos": "F"},
    {"name": "Joel Embiid",              "espn_id": "3059318", "team_abbr": "PHI", "pos": "C"},
    {"name": "Tyrese Haliburton",        "espn_id": "4432174", "team_abbr": "IND", "pos": "G"},
    {"name": "Donovan Mitchell",         "espn_id": "3908809", "team_abbr": "CLE", "pos": "G"},
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS HTTP
# ─────────────────────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None) -> Optional[dict]:
    """GET avec cache en mémoire, timeout et gestion d erreur centralisée."""
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
        logger.warning(f"Timeout: {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code}: {url}")
    except Exception as e:
        logger.error(f"Requete echouee: {url} — {e}")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — MATCHS DU JOUR
# ─────────────────────────────────────────────────────────────────────────────

def get_games_today() -> list:
    """
    Retourne les matchs NBA d aujourd hui depuis ESPN.
    Chaque dict contient home_abbr, away_abbr, home_team, away_team.
    """
    today = datetime.datetime.now().strftime("%Y%m%d")
    url   = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/scoreboard?dates={today}"
    )
    data = _get(url)
    if not data:
        return []

    games = []
    for event in data.get("events", []):
        status = event.get("status", {}).get("type", {}).get("name", "").lower()
        if "final" in status or "completed" in status:
            continue

        comp  = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue

        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])

        games.append({
            "home_team":  home.get("team", {}).get("displayName", ""),
            "away_team":  away.get("team", {}).get("displayName", ""),
            "home_abbr":  home.get("team", {}).get("abbreviation", ""),
            "away_abbr":  away.get("team", {}).get("abbreviation", ""),
            "game_id":    event.get("id", ""),
            "venue":      comp.get("venue", {}).get("fullName", ""),
        })

    logger.info(f"Matchs NBA aujourd hui: {len(games)}")
    return games


def get_teams_playing_today() -> set:
    """Retourne l ensemble des abreviations d equipes qui jouent aujourd hui."""
    games = get_games_today()
    teams = set()
    for g in games:
        teams.add(g["home_abbr"].upper())
        teams.add(g["away_abbr"].upper())
    return teams


def get_opponent_today(team_abbr: str) -> Optional[str]:
    """Retourne l abréviation de l adversaire d aujourd hui."""
    games = get_games_today()
    abbr  = team_abbr.upper()
    for g in games:
        if g["home_abbr"].upper() == abbr:
            return g["away_abbr"].upper()
        if g["away_abbr"].upper() == abbr:
            return g["home_abbr"].upper()
    return None


def is_home_today(team_abbr: str) -> bool:
    """Retourne True si l equipe joue a domicile aujourd hui."""
    games = get_games_today()
    abbr  = team_abbr.upper()
    for g in games:
        if g["home_abbr"].upper() == abbr:
            return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — STATS SAISON DU JOUEUR
# ─────────────────────────────────────────────────────────────────────────────

def get_player_season_stats(espn_id: str) -> dict:
    """
    Recupere les stats de saison depuis ESPN.
    Retourne: pts_avg, reb_avg, ast_avg, min_avg, games_played, status
    """
    url  = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/athletes/{espn_id}"
    )
    data = _get(url)
    if not data:
        return {}

    status = "Active"
    injuries = data.get("athlete", {}).get("injuries", [])
    if injuries:
        status = injuries[0].get("status", "Active")

    stats_raw = {}
    try:
        for category in data.get("athlete", {}).get("statistics", []):
            for split in category.get("splits", {}).get("categories", []):
                for stat in split.get("stats", []):
                    stats_raw[stat.get("name", "")] = stat.get("value", 0)
    except Exception as e:
        logger.debug(f"Parsing stats saison {espn_id}: {e}")

    return {
        "pts_avg":      float(stats_raw.get("avgPoints",   0)),
        "reb_avg":      float(stats_raw.get("avgRebounds", 0)),
        "ast_avg":      float(stats_raw.get("avgAssists",  0)),
        "min_avg":      float(stats_raw.get("avgMinutes",  0)),
        "games_played": int(stats_raw.get("gamesPlayed",   0)),
        "status":       status,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — STATS L10 DU JOUEUR (10 derniers matchs)
# ─────────────────────────────────────────────────────────────────────────────

def get_player_last10(espn_id: str) -> dict:
    """
    Recupere le game log ESPN et calcule les moyennes sur les 10 derniers matchs.
    Retourne: pts_l10, reb_l10, ast_l10, min_l10, games, pts_list
    """
    url  = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/athletes/{espn_id}/gamelog"
    )
    data = _get(url)
    if not data:
        return {}

    try:
        events = data.get("events", {})
        labels = data.get("labels", [])
        if not labels:
            return {}

        idx = {}
        for field, candidates in {
            "pts": ["PTS", "Points"],
            "reb": ["REB", "Rebounds", "OREB"],
            "ast": ["AST", "Assists"],
            "min": ["MIN", "Minutes"],
        }.items():
            for c in candidates:
                if c in labels:
                    idx[field] = labels.index(c)
                    break

        game_entries = []
        for event_id, event_data in events.items():
            stats_list = event_data.get("stats", [])
            if not stats_list:
                continue
            game_entries.append({
                "date":  event_data.get("gameDate", ""),
                "stats": stats_list,
            })

        game_entries.sort(key=lambda x: x["date"], reverse=True)
        last10 = game_entries[:10]

        if not last10:
            return {}

        def safe_stat(stats, i):
            try:
                val = stats[i] if i < len(stats) else "0"
                if ":" in str(val):
                    parts = str(val).split(":")
                    return float(parts[0]) + float(parts[1]) / 60
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        pts_list = [safe_stat(g["stats"], idx.get("pts", 0)) for g in last10]
        reb_list = [safe_stat(g["stats"], idx.get("reb", 1)) for g in last10]
        ast_list = [safe_stat(g["stats"], idx.get("ast", 2)) for g in last10]
        min_list = [safe_stat(g["stats"], idx.get("min", 3)) for g in last10]

        n = len(last10)
        return {
            "pts_l10":  round(sum(pts_list) / n, 1),
            "reb_l10":  round(sum(reb_list) / n, 1),
            "ast_l10":  round(sum(ast_list) / n, 1),
            "min_l10":  round(sum(min_list) / n, 1),
            "games":    n,
            "pts_list": pts_list,
        }

    except Exception as e:
        logger.warning(f"Parsing gamelog {espn_id}: {e}")
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — DÉFENSE ADVERSE SUR LA POSITION
# ─────────────────────────────────────────────────────────────────────────────

def get_opponent_defense_vs_position(opp_abbr: str, position: str) -> dict:
    """
    Recupere les points accordes par l adversaire aux joueurs de la meme position.
    Retourne: pts_allowed_to_pos, def_rank, def_rating, pts_allowed_avg
    """
    url  = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    data = _get(url)
    if not data:
        return {"pts_allowed_to_pos": 25.0, "def_rank": 15}

    team_id = None
    try:
        for t in (
            data.get("sports", [{}])[0]
                .get("leagues", [{}])[0]
                .get("teams", [])
        ):
            team = t.get("team", {})
            if team.get("abbreviation", "").upper() == opp_abbr.upper():
                team_id = team.get("id")
                break
    except Exception:
        pass

    if not team_id:
        return {"pts_allowed_to_pos": 25.0, "def_rank": 15}

    url2  = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/teams/{team_id}/statistics"
    )
    data2 = _get(url2)
    if not data2:
        return {"pts_allowed_to_pos": 25.0, "def_rank": 15}

    stats = {}
    try:
        for cat in data2.get("results", {}).get("stats", {}).get("categories", []):
            for s in cat.get("stats", []):
                stats[s.get("name", "")] = s.get("value", 0)
    except Exception:
        pass

    def_rating  = float(stats.get("defensiveRating", 112.0))
    pts_allowed = float(stats.get("avgPointsAllowed", 115.0))

    pos_upper = position.upper()
    if pos_upper in ("PG", "SG", "G"):
        adj = (115.0 - def_rating) * 0.8
    elif pos_upper in ("SF", "PF", "F"):
        adj = (115.0 - def_rating) * 0.6
    else:
        adj = (115.0 - def_rating) * 0.5

    pts_allowed_to_pos = max(15.0, 25.0 + adj)
    def_rank = max(1, min(30, int((def_rating - 105) * 2)))

    return {
        "pts_allowed_to_pos": round(pts_allowed_to_pos, 1),
        "def_rating":         round(def_rating, 1),
        "pts_allowed_avg":    round(pts_allowed, 1),
        "def_rank":           def_rank,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ODDS API — COTES PROPS POINTS O/U
# ─────────────────────────────────────────────────────────────────────────────

def get_props_odds_today() -> dict:
    """
    Recupere les cotes de props points O/U depuis The Odds API.
    Market: player_points
    Retourne: {player_name_lower: {"line": float, "over": float, "under": float}}
    """
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY absent — cotes props indisponibles")
        return {}

    url_events  = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_data = _get(url_events, params={"apiKey": ODDS_API_KEY})
    if not events_data or not isinstance(events_data, list):
        return {}

    props_by_player = {}
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    for event in events_data:
        commence = event.get("commence_time", "")
        if today_str not in commence:
            continue

        event_id = event.get("id", "")
        if not event_id:
            continue

        url_props = (
            "https://api.the-odds-api.com/v4/sports/basketball_nba"
            f"/events/{event_id}/odds"
        )
        params = {
            "apiKey":     ODDS_API_KEY,
            "regions":    "us",
            "markets":    "player_points",
            "oddsFormat": "decimal",
        }
        data = _get(url_props, params=params)
        if not data:
            continue

        priority = {"draftkings": 0, "fanduel": 1, "betmgm": 2}

        for bookmaker in data.get("bookmakers", []):
            bk_key  = bookmaker.get("key", "")
            bk_rank = priority.get(bk_key, 99)

            for market in bookmaker.get("markets", []):
                if market.get("key") != "player_points":
                    continue

                for outcome in market.get("outcomes", []):
                    player_name = outcome.get("description", "").lower().strip()
                    side        = outcome.get("name", "").lower()
                    line        = float(outcome.get("point", 0))
                    odds_val    = float(outcome.get("price", 1.91))

                    if not player_name or line <= 0:
                        continue

                    if player_name not in props_by_player:
                        props_by_player[player_name] = {
                            "line":    line,
                            "over":    1.91,
                            "under":   1.91,
                            "bk_rank": bk_rank,
                        }

                    existing_rank = props_by_player[player_name].get("bk_rank", 99)
                    if bk_rank <= existing_rank:
                        props_by_player[player_name]["line"]    = line
                        props_by_player[player_name]["bk_rank"] = bk_rank
                        if "over" in side:
                            props_by_player[player_name]["over"]  = odds_val
                        elif "under" in side:
                            props_by_player[player_name]["under"] = odds_val

    logger.info(f"Odds API props: {len(props_by_player)} joueurs trouves")
    return props_by_player


def _find_player_odds(player_name: str, props_db: dict) -> Optional[dict]:
    """
    Cherche les cotes d un joueur dans le dict retourne par get_props_odds_today().
    Fuzzy match sur le nom (last name suffisant pour la plupart).
    """
    name_lower = player_name.lower()

    if name_lower in props_db:
        return props_db[name_lower]

    tokens = [t for t in name_lower.split() if len(t) > 3]
    for db_name, odds in props_db.items():
        if all(t in db_name for t in tokens):
            return odds

    last_name = name_lower.split()[-1]
    for db_name, odds in props_db.items():
        if last_name in db_name:
            return odds

    return None

# ─────────────────────────────────────────────────────────────────────────────
# MODELE DE PRÉDICTION — POINTS O/U
# ─────────────────────────────────────────────────────────────────────────────

def predict_points(
    season_avg:     float,
    l10_avg:        float,
    min_avg:        float,
    opp_def_rating: float,
    is_home:        bool,
    is_b2b:         bool,
    games_l10:      int,
) -> dict:
    """
    Predit les points d un joueur pour le prochain match.

    Formule ponderee :
      - 40% moyenne saison (stabilite long terme)
      - 40% moyenne L10 (forme recente)
      - 20% ajustements contextuels (defense, domicile, B2B)
    """
    if season_avg <= 0 or l10_avg <= 0:
        return {"predicted_pts": 0.0, "confidence_factor": 0.0}

    base = (season_avg * 0.40) + (l10_avg * 0.40)

    def_adj = (opp_def_rating - 112.0) * 0.15
    base += def_adj * 0.20

    if is_home:
        base += 0.8
    if is_b2b:
        base -= 2.5

    if min_avg > 0:
        min_factor = min_avg / 34.0
        base = base * (0.7 + 0.3 * min_factor)

    confidence_factor = min(1.0, games_l10 / 10.0)

    if games_l10 < MIN_SAMPLE:
        base = base * 0.85 + season_avg * 0.15

    return {
        "predicted_pts":     round(max(0.0, base), 1),
        "confidence_factor": round(confidence_factor, 2),
    }


def compute_ev(prob: float, odds: float) -> float:
    """EV = (odds - 1) x P(win) - P(lose)"""
    return round((odds - 1.0) * prob - (1.0 - prob), 4)


def analyze_player_prop(
    player:       dict,
    season_stats: dict,
    l10_stats:    dict,
    opp_defense:  dict,
    prop_odds:    Optional[dict],
    is_home:      bool,
    is_b2b:       bool,
) -> Optional[dict]:
    """
    Analyse complete d un prop Points O/U pour un joueur.
    Retourne None si pas assez de donnees ou sous les seuils.
    """
    if not season_stats or season_stats.get("pts_avg", 0) < 5:
        logger.debug(f"Skip {player['name']}: stats saison insuffisantes")
        return None

    if not l10_stats or l10_stats.get("games", 0) < MIN_SAMPLE:
        logger.debug(f"Skip {player['name']}: moins de {MIN_SAMPLE} matchs L10")
        return None

    injury_status = season_stats.get("status", "Active")
    if any(s in injury_status.lower() for s in ["out", "inactive", "injured"]):
        logger.info(f"Skip {player['name']}: {injury_status}")
        return None

    season_avg  = season_stats["pts_avg"]
    l10_avg     = l10_stats["pts_l10"]
    min_avg     = l10_stats.get("min_l10", season_stats.get("min_avg", 32.0))
    opp_def_rat = opp_defense.get("def_rating", 112.0)
    games_l10   = l10_stats.get("games", 0)

    prediction = predict_points(
        season_avg=season_avg,
        l10_avg=l10_avg,
        min_avg=min_avg,
        opp_def_rating=opp_def_rat,
        is_home=is_home,
        is_b2b=is_b2b,
        games_l10=games_l10,
    )

    predicted_pts     = prediction["predicted_pts"]
    confidence_factor = prediction["confidence_factor"]

    if predicted_pts <= 0:
        return None

    if prop_odds and prop_odds.get("line", 0) > 0:
        book_line  = prop_odds["line"]
        over_odds  = prop_odds.get("over",  1.91)
        under_odds = prop_odds.get("under", 1.91)
        source     = "ODDS_API"
    else:
        raw_line   = season_avg
        book_line  = round(raw_line * 2) / 2
        over_odds  = 1.91
        under_odds = 1.91
        source     = "ESTIMEE"

    diff = predicted_pts - book_line

    if diff > 0:
        side     = "OVER"
        prob_win = 1 / (1 + math.exp(-diff / 3.0))
        bet_odds = over_odds
    else:
        side     = "UNDER"
        prob_win = 1 / (1 + math.exp(abs(diff) / 3.0))
        bet_odds = under_odds

    prob_win = max(0.40, min(0.85, prob_win))
    ev       = compute_ev(prob_win, bet_odds)

    base_score = 50
    abs_diff   = abs(diff)
    if abs_diff >= 4.0:
        base_score += 25
    elif abs_diff >= 2.5:
        base_score += 15
    elif abs_diff >= 1.5:
        base_score += 8
    else:
        base_score -= 10

    pts_list = l10_stats.get("pts_list", [])
    if pts_list and len(pts_list) >= MIN_SAMPLE:
        hits_over  = sum(1 for p in pts_list if p > book_line)
        hits_under = sum(1 for p in pts_list if p < book_line)
        hit_rate   = hits_over / len(pts_list) if side == "OVER" else hits_under / len(pts_list)
        if hit_rate >= 0.70:
            base_score += 20
        elif hit_rate >= 0.60:
            base_score += 12
        elif hit_rate <= 0.30:
            base_score -= 15
    else:
        hit_rate = 0.5

    def_rank = opp_defense.get("def_rank", 15)
    if side == "OVER" and def_rank >= 20:
        base_score += 10
    elif side == "OVER" and def_rank <= 5:
        base_score -= 12
    elif side == "UNDER" and def_rank <= 5:
        base_score += 10

    if is_home:
        base_score += 5
    if is_b2b:
        base_score -= 10

    if source == "ODDS_API":
        base_score += 5
    else:
        base_score -= 5

    if ev >= 0.05:
        base_score += 10
    elif ev >= MIN_EV:
        base_score += 5
    elif ev < 0:
        base_score -= 10

    confidence = int(max(0, min(100, base_score * confidence_factor
                                + base_score * (1 - confidence_factor) * 0.8)))

    if confidence < MIN_CONFIDENCE:
        logger.debug(f"Skip {player['name']}: confiance {confidence}/100 < {MIN_CONFIDENCE}")
        return None

    if ev < MIN_EV:
        logger.debug(f"Skip {player['name']}: EV {ev:.3f} < {MIN_EV}")
        return None

    return {
        "player":          player["name"],
        "team":            player["team_abbr"],
        "position":        player["pos"],
        "side":            side,
        "book_line":       book_line,
        "predicted_pts":   predicted_pts,
        "diff":            round(diff, 1),
        "season_avg":      season_avg,
        "l10_avg":         l10_avg,
        "hit_rate_l10":    round(hit_rate, 2),
        "ev":              ev,
        "confidence":      confidence,
        "over_odds":       over_odds,
        "under_odds":      under_odds,
        "bet_odds":        bet_odds,
        "opp_def_rank":    def_rank,
        "opp_def_rating":  opp_def_rat,
        "is_home":         is_home,
        "is_b2b":          is_b2b,
        "injury_status":   injury_status,
        "source":          source,
        "status":          "BUY" if ev >= 0.04 else "MONITORING",
    }

# ─────────────────────────────────────────────────────────────────────────────
# B2B DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_team_b2b(team_abbr: str) -> bool:
    """
    Verifie si une equipe joue en back-to-back aujourd hui
    en consultant le scoreboard ESPN d hier.
    """
    yesterday = (
        datetime.datetime.now() - datetime.timedelta(days=1)
    ).strftime("%Y%m%d")
    url  = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/scoreboard?dates={yesterday}"
    )
    data = _get(url)
    if not data:
        return False

    abbr = team_abbr.upper()
    for event in data.get("events", []):
        status = event.get("status", {}).get("type", {}).get("name", "").lower()
        if "final" not in status and "completed" not in status:
            continue
        comp  = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        for t in teams:
            if t.get("team", {}).get("abbreviation", "").upper() == abbr:
                return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# FORMATAGE TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def format_prop_pick(pick: dict) -> str:
    """Formate un pick prop pour Telegram."""
    side_emoji = "Up" if pick["side"] == "OVER" else "Down"
    conf_emoji = "HOT" if pick["confidence"] >= 75 else "OK"
    home_str   = "Home" if pick["is_home"] else "Away"
    b2b_str    = " B2B" if pick["is_b2b"] else ""
    source_str = "Cote reelle" if pick["source"] == "ODDS_API" else "Ligne estimee"

    return (
        f"{conf_emoji} *{pick['player']}* {home_str}{b2b_str}\n"
        f"   {side_emoji} *{pick['side']} {pick['book_line']} pts*"
        f" @ `{pick['bet_odds']:.2f}`\n"
        f"   Predit: *{pick['predicted_pts']}* "
        f"| Saison: {pick['season_avg']} | L10: {pick['l10_avg']}\n"
        f"   Hit rate L10: *{pick['hit_rate_l10']:.0%}*"
        f" | EV: *{pick['ev']*100:+.1f}%*\n"
        f"   Defense adverse: rang #{pick['opp_def_rank']}/30\n"
        f"   Confiance: *{pick['confidence']}/100*"
        f" | {source_str}\n"
    )


def format_props_message(picks: list) -> str:
    """Formate le message complet des props pour Telegram."""
    if not picks:
        return "Aucun prop joueur avec valeur detecte aujourd hui."

    now       = datetime.datetime.now().strftime("%H:%M")
    buy_picks = [p for p in picks if p["status"] == "BUY"]
    mon_picks = [p for p in picks if p["status"] == "MONITORING"]

    lines = [
        "*ULTRON — PROPS JOUEURS NBA*",
        f"{now} (Quebec) | Top 15 stars analysees",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if buy_picks:
        lines.append(f"\n*BUY ({len(buy_picks)} pick{'s' if len(buy_picks) > 1 else ''})*\n")
        for p in buy_picks:
            lines.append(format_prop_pick(p))

    if mon_picks:
        lines.append(f"\n*MONITORING ({len(mon_picks)})*\n")
        for p in mon_picks[:3]:
            lines.append(format_prop_pick(p))

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"{len(picks)} props analyses | "
        f"{len(buy_picks)} BUY | {len(mon_picks)} MONITORING"
    )
    lines.append("Ligne estimee si Odds API props indisponible")

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
            logger.error(f"Telegram {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        logger.error(f"Telegram send: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# POINT D ENTREE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_props_analysis(send: bool = True) -> list:
    """
    Lance l analyse complete des props pour les stars jouant aujourd hui.

    1. Recupere les matchs du jour
    2. Filtre les stars qui jouent
    3. Recupere les cotes Odds API (player_points market)
    4. Pour chaque star : stats saison + L10 + defense adverse + B2B
    5. Predit les points et calcule l EV vs ligne bookmaker
    6. Envoie les picks via Telegram si send=True

    Retourne la liste des picks tries par confiance decroissante.
    """
    logger.info("Ultron — Analyse Props Joueurs NBA...")

    teams_today = get_teams_playing_today()
    if not teams_today:
        logger.info("Aucun match NBA aujourd hui.")
        return []

    logger.info(f"Equipes en jeu: {', '.join(sorted(teams_today))}")

    stars_today = [
        s for s in TOP_STARS
        if s["team_abbr"].upper() in teams_today
    ]
    logger.info(f"Stars en jeu: {len(stars_today)}/{len(TOP_STARS)}")

    if not stars_today:
        logger.info("Aucune star dans les matchs d aujourd hui.")
        return []

    props_odds_db = get_props_odds_today()

    picks = []
    for player in stars_today:
        try:
            logger.info(f"Analyse: {player['name']} ({player['team_abbr']})")

            season_stats = get_player_season_stats(player["espn_id"])
            l10_stats    = get_player_last10(player["espn_id"])

            opp_abbr = get_opponent_today(player["team_abbr"])
            is_home  = is_home_today(player["team_abbr"])
            is_b2b   = is_team_b2b(player["team_abbr"])
            opp_def  = (
                get_opponent_defense_vs_position(opp_abbr, player["pos"])
                if opp_abbr else {"def_rating": 112.0, "def_rank": 15}
            )

            prop_odds = _find_player_odds(player["name"], props_odds_db)

            result = analyze_player_prop(
                player=player,
                season_stats=season_stats,
                l10_stats=l10_stats,
                opp_defense=opp_def,
                prop_odds=prop_odds,
                is_home=is_home,
                is_b2b=is_b2b,
            )

            if result:
                picks.append(result)
                logger.info(
                    f"  {result['side']} {result['book_line']} "
                    f"| Predit: {result['predicted_pts']} "
                    f"| EV: {result['ev']*100:+.1f}% "
                    f"| Conf: {result['confidence']}/100"
                )
            else:
                logger.info("  Pas de valeur detectee")

        except Exception as e:
            logger.error(f"Erreur analyse {player['name']}: {e}", exc_info=True)
            continue

    picks.sort(key=lambda x: x["confidence"], reverse=True)

    logger.info(
        f"Props termine: {len(picks)} pick(s) | "
        f"BUY: {sum(1 for p in picks if p['status'] == 'BUY')}"
    )

    if send and picks:
        msg = format_props_message(picks)
        if TELEGRAM_CHAT:
            send_telegram(msg, TELEGRAM_CHAT)
            logger.info("Props envoyes -> FREE channel")
        if TELEGRAM_VIP:
            send_telegram(msg, TELEGRAM_VIP)
            logger.info("Props envoyes -> VIP channel")

    return picks


# ─────────────────────────────────────────────────────────────────────────────
# TEST LOCAL
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    picks = run_props_analysis(send=False)
    print(f"\n{'='*60}")
    print(f"RESULTAT: {len(picks)} pick(s) trouve(s)")
    print(f"{'='*60}")
    for p in picks:
        print(
            f"\n{p['player']} ({p['team']})"
            f"\n   {p['side']} {p['book_line']} | Predit: {p['predicted_pts']}"
            f"\n   EV: {p['ev']*100:+.1f}% | Conf: {p['confidence']}/100"
            f"\n   Source: {p['source']}"
        )
