#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON Picks Engine — ultron_picks.py

Génère les picks journaliers en croisant :
  • Odds API   (cotes h2h + spreads + totals, cache 4h, free plan)
  • ESPN       (blessures en temps réel + stats + forme récente)
  • Modèle ML  (implied-probability + EV + ajustement ESPN)

Usage rapide :
    from ultron_picks import generate_daily_picks
    result = generate_daily_picks(bankroll=1000)
    # result["picks"]          → list de picks triés par confiance
    # result["injuries_alert"] → message Telegram formaté
    # result["buy_picks"]      → picks avec EV > 0
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

ODDS_API_KEY  = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

SPORTS = {
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "NFL": "americanfootball_nfl",
}

# Cache Odds API — 4h TTL par sport (économise le quota mensuel free plan)
_ODDS_CACHE: dict = {}
_ODDS_CACHE_TTL = 14400  # secondes — 4 heures

# Ordre de priorité des bookmakers américains
_BK_PRIORITY = ["draftkings", "fanduel", "betmgm", "bet365", "bovada", "pointsbet"]

# Seuils de filtrage
MIN_EV         = 0.0   # EV ≥ 0 = au moins neutre
MIN_CONFIDENCE = 52    # confiance minimale en % pour garder un pick

# ─────────────────────────────────────────────────────────────────────────────
# ESPN CONTEXT — import optionnel (graceful degradation si fichier absent)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from espn_context import (
        get_full_context_all_sports,
        format_injuries_alert,
    )
    _ESPN_AVAILABLE = True
except ImportError:
    _ESPN_AVAILABLE = False
    logger.warning("⚠️ espn_context non disponible — picks sans ajustement ESPN")


# ─────────────────────────────────────────────────────────────────────────────
# ODDS API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sport_odds(sport_key: str) -> list:
    """
    Récupère les cotes h2h + spreads + totals via The Odds API.
    Cache 4h pour économiser le quota mensuel (free plan ≈ 500 req/mois).
    Retourne [] si clé absente, quota dépassé ou erreur réseau.
    """
    if not ODDS_API_KEY:
        logger.warning("⚠️ ODDS_API_KEY absent — cotes live indisponibles")
        return []

    now    = datetime.now()
    cached = _ODDS_CACHE.get(sport_key)
    if cached:
        elapsed = (now - cached["fetched_at"]).total_seconds()
        if elapsed < _ODDS_CACHE_TTL:
            logger.debug(f"📦 Cache Odds API {sport_key} ({int(elapsed / 60)} min)")
            return cached["data"]

    try:
        url = (
            f"{ODDS_API_BASE}/{sport_key}/odds/"
            f"?apiKey={ODDS_API_KEY}"
            f"&regions=us"
            f"&markets=h2h,spreads,totals"
            f"&oddsFormat=decimal"
            f"&dateFormat=iso"
        )
        resp      = requests.get(url, timeout=10)
        remaining = resp.headers.get("x-requests-remaining", "?")
        used      = resp.headers.get("x-requests-used", "?")

        if resp.status_code == 200:
            data = resp.json()
            _ODDS_CACHE[sport_key] = {"data": data, "fetched_at": now}
            logger.info(
                f"✅ Odds API {sport_key}: {len(data)} matchs "
                f"| restantes={remaining} utilisées={used}"
            )
            return data
        elif resp.status_code == 401:
            logger.error("❌ Odds API: clé invalide (401)")
        elif resp.status_code == 429:
            logger.warning("⚠️ Odds API: quota mensuel dépassé (429)")
        else:
            logger.warning(f"⚠️ Odds API {sport_key}: HTTP {resp.status_code}")

    except Exception as e:
        logger.error(f"❌ Odds API {sport_key}: {e}")

    return []


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE D'UN MATCH
# ─────────────────────────────────────────────────────────────────────────────

def _compute_ev(prob: float, odds: float) -> float:
    """EV = (odds − 1) × P(gagner) − P(perdre)"""
    return round((odds - 1) * prob - (1 - prob), 4)


def _best_odds_from_bookmakers(bookmakers: list, away_team: str, home_team: str) -> dict:
    """
    Extrait les meilleures cotes ML, spread et total parmi les bookmakers
    dans l'ordre de priorité défini par _BK_PRIORITY.
    """
    sorted_bk = sorted(
        bookmakers,
        key=lambda b: _BK_PRIORITY.index(b["key"]) if b["key"] in _BK_PRIORITY else 99,
    )

    ml_away = ml_home = None
    spread_pick = spread_odds_val = ""
    ou_pick = ou_odds_val = ""

    away_lower = away_team.lower()
    home_lower = home_team.lower()

    for bk in sorted_bk:
        for mkt in bk.get("markets", []):
            mkey     = mkt["key"]
            outcomes = mkt.get("outcomes", [])

            if mkey == "h2h" and ml_away is None:
                for o in outcomes:
                    name = o["name"].lower()
                    # Match fuzzy sur le dernier mot du nom d'équipe
                    if any(p in name for p in away_lower.split()[-2:] if len(p) > 3):
                        ml_away = {"team": o["name"], "odds": o["price"]}
                    elif any(p in name for p in home_lower.split()[-2:] if len(p) > 3):
                        ml_home = {"team": o["name"], "odds": o["price"]}

            elif mkey == "spreads" and not spread_pick:
                for o in outcomes:
                    pt   = o.get("point", 0)
                    sign = "+" if pt > 0 else ""
                    spread_pick     = f"{o['name'].upper()} {sign}{pt}"
                    spread_odds_val = f"{o['price']:.2f}"
                    break  # prend la première ligne (équipe away)

            elif mkey == "totals" and not ou_pick:
                for o in outcomes:
                    if o["name"] == "Over":
                        ou_pick     = f"OVER {o.get('point', '')}".strip()
                        ou_odds_val = f"{o['price']:.2f}"
                        break

        if ml_away and ml_home and spread_pick and ou_pick:
            break

    return {
        "ml_away":     ml_away,
        "ml_home":     ml_home,
        "spread_pick": spread_pick,
        "spread_odds": spread_odds_val or "1.91",
        "ou_pick":     ou_pick,
        "ou_odds":     ou_odds_val or "1.91",
    }


def analyze_game(game: dict, sport: str) -> Optional[dict]:
    """
    Analyse un événement brut de l'Odds API.
    Les probabilités sont dérivées des cotes h2h (implied probability corrigée
    de la marge bookmaker), sans dépendre des stats statiques hardcodées.

    Retourne None si les données sont insuffisantes ou sous le seuil MIN_CONFIDENCE.
    """
    away_team  = game.get("away_team", "")
    home_team  = game.get("home_team", "")
    bookmakers = game.get("bookmakers", [])

    if not away_team or not home_team or not bookmakers:
        return None

    odds_data = _best_odds_from_bookmakers(bookmakers, away_team, home_team)
    ml_away   = odds_data["ml_away"]
    ml_home   = odds_data["ml_home"]

    if not ml_away or not ml_home:
        return None

    # Probabilités implicites normalisées (retire la marge du book)
    raw_away  = 1 / ml_away["odds"]
    raw_home  = 1 / ml_home["odds"]
    total     = raw_away + raw_home
    away_prob = raw_away / total
    home_prob = raw_home / total

    # Favori = équipe avec la probabilité la plus haute
    if away_prob >= home_prob:
        fav_team, fav_prob, fav_odds_info = away_team, away_prob, ml_away
        dog_team, dog_prob, dog_odds_info = home_team, home_prob, ml_home
    else:
        fav_team, fav_prob, fav_odds_info = home_team, home_prob, ml_home
        dog_team, dog_prob, dog_odds_info = away_team, away_prob, ml_away

    fav_ev = _compute_ev(fav_prob, fav_odds_info["odds"])
    dog_ev = _compute_ev(dog_prob, dog_odds_info["odds"])

    confidence = min(95, max(10, int(fav_prob * 100)))
    if confidence < MIN_CONFIDENCE:
        return None

    if fav_ev > 0.01:
        status = "✅ BUY"
    elif fav_ev >= MIN_EV:
        status = "👀 MONITORING"
    else:
        status = "⏸ PASS"

    return {
        "sport":         sport,
        "away_team":     away_team,
        "home_team":     home_team,
        "fav_team":      fav_team,
        "dog_team":      dog_team,
        "fav_prob":      round(fav_prob, 4),
        "dog_prob":      round(dog_prob, 4),
        "best_fav_odds": fav_odds_info,
        "best_dog_odds": dog_odds_info,
        "fav_ev":        fav_ev,
        "dog_ev":        dog_ev,
        "spread_pick":   odds_data["spread_pick"],
        "spread_odds":   odds_data["spread_odds"],
        "ou_pick":       odds_data["ou_pick"],
        "ou_odds":       odds_data["ou_odds"],
        "confidence":    confidence,
        "status":        status,
        "espn_context":  None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS ESPN
# ─────────────────────────────────────────────────────────────────────────────

def _match_espn_game(home: str, away: str, espn_games: list) -> Optional[dict]:
    """
    Trouve le match ESPN correspondant par fuzzy match sur les derniers mots
    du nom d'équipe (ex: "Boston Celtics" → cherche "celtics").
    """
    for g in espn_games:
        if (any(p in g["home_team"] for p in home.split()[-2:])
                and any(p in g["away_team"] for p in away.split()[-2:])):
            return g
    return None


def _apply_espn_adjustment(analysis: dict, espn_game: dict) -> dict:
    """
    Applique l'ajustement ESPN (blessures + forme + stats) sur la prob du favori.
    Le prob_adjustment d'ESPN est un delta centré sur l'équipe home :
      • positif → home est favorisée par le contexte ESPN
      • négatif → away est favorisée

    On inverse le signe si notre favori ML est l'équipe away.
    """
    adj          = espn_game.get("prob_adjustment", 0)
    fav_is_home  = analysis["fav_team"] == espn_game.get("home_team", "")
    signed_adj   = adj if fav_is_home else -adj

    old_fav_prob = analysis["fav_prob"]
    new_fav_prob = round(min(max(old_fav_prob + signed_adj, 0.30), 0.90), 4)

    analysis["fav_prob"] = new_fav_prob
    analysis["dog_prob"] = round(1 - new_fav_prob, 4)

    # Recalcule EV avec la probabilité ajustée
    analysis["fav_ev"] = _compute_ev(
        new_fav_prob,
        analysis["best_fav_odds"]["odds"],
    )

    # Met à jour la confiance et le statut
    analysis["confidence"] = min(95, max(10, int(new_fav_prob * 100)))

    # Enrichissement du contexte ESPN sur l'analyse
    analysis["espn_context"] = {
        "home_inj_severity": espn_game["home_inj_severity"],
        "away_inj_severity": espn_game["away_inj_severity"],
        "home_inj_impact":   espn_game["home_inj_impact"],
        "away_inj_impact":   espn_game["away_inj_impact"],
        "home_form":         espn_game["home_form"],
        "away_form":         espn_game["away_form"],
        "prob_adjustment":   adj,
        "key_injuries": (
            espn_game.get("home_injuries", {}).get("key_injuries", [])
            + espn_game.get("away_injuries", {}).get("key_injuries", [])
        ),
    }

    # Pénalité confiance si blessure critique présente (QB out, Gardien out, superstar)
    if (espn_game["home_inj_severity"] == "CRITIQUE"
            or espn_game["away_inj_severity"] == "CRITIQUE"):
        analysis["confidence"] = max(analysis["confidence"] - 15, 0)
        analysis["status"] = "⚠️ BLESSURE CRITIQUE"
    elif analysis["fav_ev"] > 0.01:
        analysis["status"] = "✅ BUY"
    elif analysis["fav_ev"] >= MIN_EV:
        analysis["status"] = "👀 MONITORING"
    else:
        analysis["status"] = "⏸ PASS"

    return analysis


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def generate_daily_picks(bankroll: float = 1000) -> dict:
    """Version améliorée avec contexte ESPN"""

    # 1. Contexte ESPN (blessures + stats + forme)
    print("📡 ESPN — fetch contexte complet...")
    espn_context = get_full_context_all_sports() if _ESPN_AVAILABLE else {}

    # 2. Cotes bookmakers (Odds API — inchangé)
    print("💰 Odds API — fetch cotes...")
    all_odds = {}
    for sport_name, sport_key in SPORTS.items():
        games = fetch_sport_odds(sport_key)
        if games:
            all_odds[sport_name] = games

    # 3. Croise les deux sources
    all_analyses = []
    for sport, games in all_odds.items():
        espn_games = espn_context.get(sport, [])

        for game in games:
            analysis = analyze_game(game, sport)
            if not analysis:
                continue

            # Trouve le contexte ESPN correspondant
            espn_game = _match_espn_game(
                analysis['home_team'],
                analysis['away_team'],
                espn_games
            )

            if espn_game:
                # Ajuste les probabilités avec ESPN
                analysis = _apply_espn_adjustment(
                    analysis, espn_game
                )

            all_analyses.append(analysis)

    # Trier par confiance décroissante
    all_analyses.sort(key=lambda a: a["fav_prob"], reverse=True)

    # Alerte blessures (message Telegram séparé)
    injuries_msg = ""
    if _ESPN_AVAILABLE and espn_context:
        try:
            injuries_msg = format_injuries_alert(espn_context)
        except Exception as e:
            logger.warning(f"⚠️ format_injuries_alert: {e}")

    return {
        "picks":          all_analyses,
        "injuries_alert": injuries_msg,
        "bankroll":       bankroll,
        "timestamp":      datetime.now().isoformat(),
        "total":          len(all_analyses),
        "buy_picks":      [a for a in all_analyses if a["fav_ev"] > MIN_EV],
    }
