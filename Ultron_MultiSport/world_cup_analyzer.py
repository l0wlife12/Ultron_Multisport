#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON — world_cup_analyzer.py

Module d'analyse des matchs FIFA Coupe du Monde 2026.

Sources :
  • ESPN API     — matchs du jour (soccer/fifa.world)
  • Odds API     — cotes h2h en temps réel (soccer_fifa_world_cup)
  • FIFA Rankings — forces des équipes (estimations juin 2026)

Logique :
  1. Récupère les matchs WC depuis ESPN
  2. Calcule les probabilités via modèle Dixon-Coles
  3. Compare aux cotes Odds API → EV
  4. Envoie les picks BUY/MONITORING via Telegram

Usage :
    from world_cup_analyzer import run_wc_analysis
    picks = run_wc_analysis(send=False)
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
TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN", "")
    or os.environ.get("TELEGRAM_BOT_TOKEN", "")
)
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_VIP   = os.environ.get("TELEGRAM_CHAT_ID_VIP", "")

MIN_EV         = -0.20  # Accepte tous les picks WC (même EV légèrement négatif)
MIN_CONFIDENCE = 40     # Confiance minimale /100

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "UltronBot/6.0"})
_TIMEOUT = 10
_CACHE: dict = {}

# Nations hôtes (USA, Canada, Mexique) — léger avantage de support
HOST_NATIONS = {"usa", "united states", "canada", "mexico"}

# Bookmakers prioritaires
BK_PRIORITY = [
    "draftkings", "fanduel", "betmgm", "bet365", "bwin",
    "unibet", "bovada", "pointsbet",
]

# ─────────────────────────────────────────────────────────────────────────────
# FORCES FIFA — COUPE DU MONDE 2026
# strength : 0–100 (basé classement FIFA juin 2026)
# gf       : buts marqués par match (moyenne tournoi)
# ga       : buts concédés par match (moyenne tournoi)
# form     : multiplicateur forme récente (0.85–1.15)
# ─────────────────────────────────────────────────────────────────────────────

FIFA_TEAM_STATS = {
    # ── CONMEBOL ────────────────────────────────────────────────────────────
    "argentina":    {"strength": 95, "gf": 2.1, "ga": 0.9, "form": 1.10},
    "brazil":       {"strength": 89, "gf": 1.9, "ga": 1.0, "form": 1.05},
    "colombia":     {"strength": 79, "gf": 1.6, "ga": 1.1, "form": 1.05},
    "uruguay":      {"strength": 82, "gf": 1.5, "ga": 0.9, "form": 1.00},
    "ecuador":      {"strength": 70, "gf": 1.4, "ga": 1.2, "form": 1.00},
    "paraguay":     {"strength": 67, "gf": 1.3, "ga": 1.2, "form": 0.95},
    "chile":        {"strength": 68, "gf": 1.3, "ga": 1.3, "form": 0.95},
    "venezuela":    {"strength": 64, "gf": 1.2, "ga": 1.3, "form": 0.90},
    "bolivia":      {"strength": 53, "gf": 1.0, "ga": 1.6, "form": 0.85},
    "peru":         {"strength": 63, "gf": 1.2, "ga": 1.3, "form": 0.92},
    # ── UEFA ────────────────────────────────────────────────────────────────
    "france":       {"strength": 93, "gf": 2.0, "ga": 0.8, "form": 1.08},
    "england":      {"strength": 91, "gf": 1.9, "ga": 0.8, "form": 1.07},
    "spain":        {"strength": 90, "gf": 1.8, "ga": 0.7, "form": 1.10},
    "portugal":     {"strength": 88, "gf": 1.9, "ga": 0.9, "form": 1.05},
    "germany":      {"strength": 85, "gf": 1.8, "ga": 1.0, "form": 1.03},
    "netherlands":  {"strength": 87, "gf": 1.8, "ga": 0.9, "form": 1.05},
    "belgium":      {"strength": 80, "gf": 1.6, "ga": 1.0, "form": 0.98},
    "italy":        {"strength": 84, "gf": 1.6, "ga": 0.8, "form": 1.00},
    "croatia":      {"strength": 83, "gf": 1.5, "ga": 0.9, "form": 1.00},
    "denmark":      {"strength": 81, "gf": 1.5, "ga": 0.9, "form": 1.00},
    "switzerland":  {"strength": 80, "gf": 1.5, "ga": 0.9, "form": 1.00},
    "austria":      {"strength": 76, "gf": 1.5, "ga": 1.1, "form": 1.02},
    "turkey":       {"strength": 73, "gf": 1.4, "ga": 1.1, "form": 0.98},
    "ukraine":      {"strength": 72, "gf": 1.4, "ga": 1.2, "form": 0.95},
    "serbia":       {"strength": 74, "gf": 1.4, "ga": 1.2, "form": 0.98},
    "poland":       {"strength": 71, "gf": 1.3, "ga": 1.2, "form": 0.95},
    "czech republic": {"strength": 65, "gf": 1.3, "ga": 1.3, "form": 0.95},
    "czechia":      {"strength": 65, "gf": 1.3, "ga": 1.3, "form": 0.95},
    "romania":      {"strength": 66, "gf": 1.2, "ga": 1.3, "form": 0.95},
    "slovakia":     {"strength": 64, "gf": 1.2, "ga": 1.3, "form": 0.95},
    "hungary":      {"strength": 60, "gf": 1.1, "ga": 1.4, "form": 0.92},
    "scotland":     {"strength": 69, "gf": 1.3, "ga": 1.2, "form": 0.97},
    "albania":      {"strength": 62, "gf": 1.1, "ga": 1.4, "form": 0.93},
    "georgia":      {"strength": 63, "gf": 1.2, "ga": 1.3, "form": 0.95},
    "slovenia":     {"strength": 61, "gf": 1.1, "ga": 1.3, "form": 0.93},
    "wales":        {"strength": 68, "gf": 1.2, "ga": 1.2, "form": 0.95},
    "norway":       {"strength": 74, "gf": 1.5, "ga": 1.1, "form": 1.00},
    "israel":       {"strength": 63, "gf": 1.2, "ga": 1.3, "form": 0.93},
    # ── CONCACAF ────────────────────────────────────────────────────────────
    "united states": {"strength": 75, "gf": 1.5, "ga": 1.1, "form": 1.05},
    "usa":           {"strength": 75, "gf": 1.5, "ga": 1.1, "form": 1.05},
    "mexico":        {"strength": 74, "gf": 1.5, "ga": 1.1, "form": 1.03},
    "canada":        {"strength": 68, "gf": 1.3, "ga": 1.2, "form": 1.02},
    "costa rica":    {"strength": 63, "gf": 1.2, "ga": 1.3, "form": 0.95},
    "panama":        {"strength": 58, "gf": 1.0, "ga": 1.4, "form": 0.92},
    "honduras":      {"strength": 56, "gf": 1.0, "ga": 1.5, "form": 0.90},
    "jamaica":       {"strength": 54, "gf": 1.0, "ga": 1.5, "form": 0.90},
    "el salvador":   {"strength": 55, "gf": 1.0, "ga": 1.5, "form": 0.88},
    "haiti":         {"strength": 51, "gf": 0.9, "ga": 1.5, "form": 0.87},
    "trinidad and tobago": {"strength": 52, "gf": 0.9, "ga": 1.5, "form": 0.87},
    "cuba":          {"strength": 48, "gf": 0.8, "ga": 1.6, "form": 0.85},
    # ── AFC ─────────────────────────────────────────────────────────────────
    "japan":         {"strength": 75, "gf": 1.6, "ga": 1.0, "form": 1.08},
    "south korea":   {"strength": 72, "gf": 1.4, "ga": 1.1, "form": 1.00},
    "korea republic": {"strength": 72, "gf": 1.4, "ga": 1.1, "form": 1.00},
    "iran":          {"strength": 66, "gf": 1.3, "ga": 1.2, "form": 0.95},
    "saudi arabia":  {"strength": 61, "gf": 1.2, "ga": 1.3, "form": 0.95},
    "australia":     {"strength": 69, "gf": 1.3, "ga": 1.2, "form": 0.98},
    "qatar":         {"strength": 55, "gf": 1.0, "ga": 1.5, "form": 0.88},
    "iraq":          {"strength": 59, "gf": 1.1, "ga": 1.4, "form": 0.90},
    "uzbekistan":    {"strength": 62, "gf": 1.2, "ga": 1.3, "form": 0.92},
    "indonesia":     {"strength": 50, "gf": 0.8, "ga": 1.6, "form": 0.85},
    "jordan":        {"strength": 56, "gf": 1.0, "ga": 1.4, "form": 0.90},
    "china":         {"strength": 54, "gf": 0.9, "ga": 1.5, "form": 0.88},
    "oman":          {"strength": 55, "gf": 1.0, "ga": 1.5, "form": 0.88},
    "bahrain":       {"strength": 53, "gf": 1.0, "ga": 1.5, "form": 0.88},
    "north korea":   {"strength": 56, "gf": 1.0, "ga": 1.4, "form": 0.88},
    "thailand":      {"strength": 50, "gf": 0.8, "ga": 1.6, "form": 0.85},
    # ── CAF ─────────────────────────────────────────────────────────────────
    "morocco":       {"strength": 78, "gf": 1.5, "ga": 0.8, "form": 1.08},
    "senegal":       {"strength": 73, "gf": 1.4, "ga": 1.0, "form": 1.00},
    "nigeria":       {"strength": 70, "gf": 1.4, "ga": 1.2, "form": 0.98},
    "egypt":         {"strength": 68, "gf": 1.3, "ga": 1.1, "form": 0.97},
    "cameroon":      {"strength": 62, "gf": 1.2, "ga": 1.3, "form": 0.93},
    "ghana":         {"strength": 63, "gf": 1.2, "ga": 1.3, "form": 0.93},
    "south africa":  {"strength": 59, "gf": 1.1, "ga": 1.4, "form": 0.92},
    "ivory coast":   {"strength": 65, "gf": 1.3, "ga": 1.2, "form": 0.95},
    "côte d'ivoire": {"strength": 65, "gf": 1.3, "ga": 1.2, "form": 0.95},
    "mali":          {"strength": 60, "gf": 1.1, "ga": 1.3, "form": 0.92},
    "tunisia":       {"strength": 61, "gf": 1.1, "ga": 1.2, "form": 0.93},
    "algeria":       {"strength": 63, "gf": 1.2, "ga": 1.2, "form": 0.95},
    "dr congo":      {"strength": 61, "gf": 1.1, "ga": 1.3, "form": 0.92},
    "democratic republic of congo": {"strength": 61, "gf": 1.1, "ga": 1.3, "form": 0.92},
    "cape verde":    {"strength": 57, "gf": 1.0, "ga": 1.3, "form": 0.92},
    "kenya":         {"strength": 48, "gf": 0.8, "ga": 1.5, "form": 0.85},
    "zambia":        {"strength": 48, "gf": 0.8, "ga": 1.5, "form": 0.85},
    "gabon":         {"strength": 54, "gf": 1.0, "ga": 1.4, "form": 0.88},
    # ── OFC ─────────────────────────────────────────────────────────────────
    "new zealand":   {"strength": 55, "gf": 1.0, "ga": 1.5, "form": 0.90},
}

_DEFAULT_STATS = {"strength": 55, "gf": 1.1, "ga": 1.3, "form": 0.90}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS HTTP
# ─────────────────────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None) -> Optional[dict]:
    """GET avec cache mémoire."""
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
        code = e.response.status_code if e.response else "?"
        logger.warning(f"⚠️ HTTP {code}: {url}")
    except Exception as e:
        logger.error(f"❌ Requête échouée: {url} — {e}")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — MATCHS WC
# ─────────────────────────────────────────────────────────────────────────────

def get_wc_games(days_ahead: int = 3) -> list:
    """
    Récupère les matchs WC via ESPN (soccer/fifa.world).
    Cherche aujourd'hui d'abord, puis les jours suivants.
    Retourne le premier jour avec des matchs.
    """
    today = datetime.datetime.now()

    for offset in range(days_ahead + 1):
        date = today + datetime.timedelta(days=offset)
        date_str = date.strftime("%Y%m%d")

        url = (
            "https://site.api.espn.com/apis/site/v2/sports"
            f"/soccer/fifa.world/scoreboard?dates={date_str}"
        )
        data = _get(url)
        if not data:
            continue

        day_games = []
        for event in data.get("events", []):
            try:
                status_type = event.get("status", {}).get("type", {})
                status_name = status_type.get("name", "").lower()
                status_desc = status_type.get("description", "").lower()

                blocked = ["final", "completed", "cancelled", "postponed", "full-time"]
                if any(w in status_desc or w in status_name for w in blocked):
                    continue

                comp        = event.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue

                home = next(
                    (t for t in competitors if t.get("homeAway") == "home"),
                    competitors[0],
                )
                away = next(
                    (t for t in competitors if t.get("homeAway") == "away"),
                    competitors[1],
                )

                home_name = home.get("team", {}).get("displayName", "")
                away_name  = away.get("team", {}).get("displayName", "")
                if not home_name or not away_name:
                    continue

                # Groupe depuis les notes ESPN
                group = ""
                for note in comp.get("notes", []):
                    headline = note.get("headline", "")
                    if "group" in headline.lower():
                        group = headline
                        break

                day_games.append({
                    "home_team":  home_name,
                    "away_team":  away_name,
                    "home_abbr":  home.get("team", {}).get("abbreviation",
                                  home_name[:3].upper()),
                    "away_abbr":  away.get("team", {}).get("abbreviation",
                                  away_name[:3].upper()),
                    "venue":      comp.get("venue", {}).get("fullName", ""),
                    "venue_city": comp.get("venue", {}).get("address", {}).get("city", ""),
                    "commence":   event.get("date", ""),
                    "group":      group,
                    "status":     status_desc,
                    "day_offset": offset,
                })
            except Exception as e:
                logger.debug(f"⚠️ Parse WC event: {e}")
                continue

        if day_games:
            label = "aujourd'hui" if offset == 0 else f"dans {offset}j"
            logger.info(f"⚽ WC: {len(day_games)} matchs {label}")
            return day_games

    logger.info("ℹ️ Aucun match WC trouvé dans la période")
    return []

# ─────────────────────────────────────────────────────────────────────────────
# ODDS API — h2h World Cup
# ─────────────────────────────────────────────────────────────────────────────

def get_wc_odds() -> list:
    """
    Récupère les cotes h2h WC depuis Odds API.
    Cache 4h. Gère le code 422 (sport pas encore actif).
    """
    if not ODDS_API_KEY:
        logger.warning("⚠️ ODDS_API_KEY absent — cotes WC indisponibles")
        return []

    cache_key = f"wc_odds_{datetime.datetime.now().strftime('%Y%m%d_%H')}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    url = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us,eu",
        "markets":    "h2h",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        resp      = _SESSION.get(url, params=params, timeout=_TIMEOUT)
        remaining = resp.headers.get("x-requests-remaining", "?")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            _CACHE[cache_key] = data
            logger.info(
                f"✅ Odds API WC: {len(data)} matchs | restantes={remaining}"
            )
            return data
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        if code == 422:
            logger.warning("⚠️ Odds API: sport WC pas encore actif (422)")
        elif code == 401:
            logger.error("❌ Odds API: clé invalide (401)")
        elif code == 429:
            logger.warning("⚠️ Odds API: quota dépassé (429)")
        else:
            logger.warning(f"⚠️ Odds API WC: HTTP {code}")
    except Exception as e:
        logger.error(f"❌ Odds API WC: {e}")
    return []


def _extract_h2h_odds(
    odds_events: list, home_team: str, away_team: str
) -> dict:
    """
    Cherche les cotes h2h pour un match WC dans la liste Odds API.
    Retourne {home_ml, away_ml, draw_odds, bookmaker} ou {}.
    """
    if not odds_events:
        return {}

    home_tokens = [w for w in home_team.lower().split() if len(w) > 3]
    away_tokens = [w for w in away_team.lower().split() if len(w) > 3]

    best_event = None
    best_score = 0

    for event in odds_events:
        ev_home = event.get("home_team", "").lower()
        ev_away = event.get("away_team", "").lower()
        score = 0
        for t in home_tokens:
            if t in ev_home:
                score += 2
        for t in away_tokens:
            if t in ev_away:
                score += 2
        # Tolérance ordre inversé
        for t in home_tokens:
            if t in ev_away:
                score += 1
        for t in away_tokens:
            if t in ev_home:
                score += 1
        if score > best_score:
            best_score = score
            best_event = event

    if not best_event or best_score < 2:
        return {}

    sorted_bk = sorted(
        best_event.get("bookmakers", []),
        key=lambda b: BK_PRIORITY.index(b["key"])
        if b["key"] in BK_PRIORITY else 99,
    )

    for bk in sorted_bk:
        for market in bk.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes  = market.get("outcomes", [])
            home_ml   = None
            away_ml   = None
            draw_odds = None

            for o in outcomes:
                name  = o.get("name", "").lower()
                price = float(o.get("price", 0) or 0)
                if price <= 1.0:
                    continue
                if name in ("draw", "tie"):
                    draw_odds = price
                elif any(t in name for t in home_tokens):
                    home_ml = price
                elif any(t in name for t in away_tokens):
                    away_ml = price

            if home_ml and away_ml:
                return {
                    "home_ml":   home_ml,
                    "away_ml":   away_ml,
                    "draw_odds": draw_odds or 3.50,
                    "bookmaker": bk.get("title", bk["key"]),
                }
    return {}

# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP ÉQUIPE FIFA
# ─────────────────────────────────────────────────────────────────────────────

# Alias pour les noms ESPN potentiellement différents
_TEAM_ALIASES: dict = {
    "united states":         "united states",
    "u.s.":                  "united states",
    "usmnt":                 "united states",
    "us":                    "united states",
    "korea republic":        "south korea",
    "republic of korea":     "south korea",
    "dpr korea":             "north korea",
    "korea dpr":             "north korea",
    "côte d'ivoire":         "ivory coast",
    "cote d'ivoire":         "ivory coast",
    "cote divoire":          "ivory coast",
    "czech rep":             "czech republic",
    "czechia":               "czech republic",
    "dr congo":              "democratic republic of congo",
    "congo dr":              "democratic republic of congo",
    "drc":                   "democratic republic of congo",
    "t&t":                   "trinidad and tobago",
    "trinidad & tobago":     "trinidad and tobago",
}


def _find_team(display_name: str) -> dict:
    """
    Trouve les stats FIFA d'une équipe par son nom ESPN.
    Gère les alias, les variantes de noms et la recherche par token.
    """
    name_lower = display_name.lower().strip()

    # 1. Match direct
    if name_lower in FIFA_TEAM_STATS:
        return FIFA_TEAM_STATS[name_lower]

    # 2. Alias
    resolved = _TEAM_ALIASES.get(name_lower)
    if resolved and resolved in FIFA_TEAM_STATS:
        return FIFA_TEAM_STATS[resolved]

    # 3. Recherche par alias partiel
    for alias, canonical in _TEAM_ALIASES.items():
        if alias in name_lower or name_lower in alias:
            if canonical in FIFA_TEAM_STATS:
                return FIFA_TEAM_STATS[canonical]

    # 4. Recherche par token
    name_tokens = [t for t in name_lower.split() if len(t) > 3]
    best_match  = None
    best_score  = 0
    for team_key, stats in FIFA_TEAM_STATS.items():
        score = 0
        for token in name_tokens:
            if token in team_key:
                score += 2
        for key_token in team_key.split():
            if len(key_token) > 3 and key_token in name_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_match = stats

    if best_match and best_score >= 2:
        return best_match

    logger.debug(f"⚠️ Équipe WC non trouvée: '{display_name}' — stats par défaut")
    return dict(_DEFAULT_STATS)

# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE DIXON-COLES
# ─────────────────────────────────────────────────────────────────────────────

def _host_bonus(team_name: str) -> float:
    """Bonus de force pour les nations hôtes (USA, Canada, Mexique)."""
    name_lower = team_name.lower()
    for host in HOST_NATIONS:
        if host in name_lower:
            return 5.0
    return 0.0


def _dixon_coles_probs(
    home_att: float,
    home_def: float,
    away_att: float,
    away_def: float,
    home_advantage: float = 0.0,
) -> dict:
    """
    Dixon-Coles simplifié : calcule P(home), P(draw), P(away).

    home_advantage : 0.15 si équipe hôte joue dans son pays,
                     0.0 pour matchs sur terrain neutre.
    """
    lam_h = max(0.3, min(5.0, home_att * away_def * (1.0 + home_advantage)))
    lam_a = max(0.3, min(5.0, away_att * home_def))

    p_home_win = p_draw = p_away_win = 0.0
    max_goals  = 7
    rho        = -0.1  # légère corrélation pour résultats serrés

    for i in range(max_goals):
        fi = math.exp(-lam_h) * (lam_h ** i) / math.factorial(i)
        for j in range(max_goals):
            fj = math.exp(-lam_a) * (lam_a ** j) / math.factorial(j)

            # Correction Dixon-Coles pour les petits scores
            if i == 0 and j == 0:
                tau = 1.0 - lam_h * lam_a * rho
            elif i == 0 and j == 1:
                tau = 1.0 + lam_h * rho
            elif i == 1 and j == 0:
                tau = 1.0 + lam_a * rho
            elif i == 1 and j == 1:
                tau = 1.0 - rho
            else:
                tau = 1.0

            p_ij = fi * fj * max(0.0, tau)

            if i > j:
                p_home_win += p_ij
            elif i == j:
                p_draw += p_ij
            else:
                p_away_win += p_ij

    total = p_home_win + p_draw + p_away_win
    if total > 0:
        p_home_win /= total
        p_draw     /= total
        p_away_win /= total
    else:
        p_home_win = p_draw = p_away_win = 1 / 3

    return {
        "p_home":        round(p_home_win, 4),
        "p_draw":        round(p_draw,     4),
        "p_away":        round(p_away_win, 4),
        "lambda_home":   round(lam_h, 2),
        "lambda_away":   round(lam_a, 2),
    }


def predict_wc_match(
    home_team:   str,
    away_team:   str,
    home_stats:  dict,
    away_stats:  dict,
    venue_city:  str = "",
) -> dict:
    """
    Prédit le résultat via Dixon-Coles + ajustements contextuels.
    Retourne p_home, p_draw, p_away, predicted_score, confidence.
    """
    home_bonus = _host_bonus(home_team)
    away_bonus = _host_bonus(away_team)

    home_att = home_stats["gf"] * home_stats["form"] * (1.0 + home_bonus / 100.0)
    home_def = home_stats["ga"]
    away_att = away_stats["gf"] * away_stats["form"] * (1.0 + away_bonus / 100.0)
    away_def = away_stats["ga"]

    # Avantage terrain uniquement si nation hôte joue chez elle
    host_cities = [
        "new york", "los angeles", "dallas", "miami", "seattle",
        "san francisco", "houston", "boston", "philadelphia",
        "atlanta", "kansas city", "toronto", "vancouver",
        "guadalajara", "mexico city", "monterrey",
    ]
    is_home_host = (
        home_bonus > 0
        and any(city in venue_city.lower() for city in host_cities)
    )
    home_adv = 0.15 if is_home_host else 0.0

    probs = _dixon_coles_probs(home_att, home_def, away_att, away_def, home_adv)

    # Confiance basée sur l'écart de forces
    strength_diff = abs(
        (home_stats["strength"] + home_bonus) - (away_stats["strength"] + away_bonus)
    )
    if strength_diff >= 20:
        confidence = 75
    elif strength_diff >= 12:
        confidence = 65
    elif strength_diff >= 6:
        confidence = 57
    else:
        confidence = 50

    if home_stats.get("gf", 0) > 0 and away_stats.get("gf", 0) > 0:
        confidence = min(85, confidence + 5)

    return {
        "p_home":          probs["p_home"],
        "p_draw":          probs["p_draw"],
        "p_away":          probs["p_away"],
        "predicted_score": f"{probs['lambda_home']:.1f}-{probs['lambda_away']:.1f}",
        "lambda_home":     probs["lambda_home"],
        "lambda_away":     probs["lambda_away"],
        "confidence":      confidence,
        "home_strength":   int(home_stats["strength"] + home_bonus),
        "away_strength":   int(away_stats["strength"] + away_bonus),
        "host_bonus_home": home_bonus > 0,
        "host_bonus_away": away_bonus > 0,
    }

# ─────────────────────────────────────────────────────────────────────────────
# CALCUL EV
# ─────────────────────────────────────────────────────────────────────────────

def compute_ev(prob: float, odds: float) -> float:
    """EV = (odds - 1) × P(win) - P(lose)"""
    return round((odds - 1.0) * prob - (1.0 - prob), 4)


def _find_best_pick(
    p_home: float, p_draw: float, p_away: float,
    home_ml: float, draw_odds: float, away_ml: float,
    home_team: str, away_team: str,
) -> Optional[dict]:
    """Retourne toujours le pick avec le meilleur EV parmi home/draw/away."""
    candidates = [
        {"pick": f"{home_team} ML",  "prob": p_home, "odds": home_ml,   "side": "home"},
        {"pick": "Nul / Draw",       "prob": p_draw, "odds": draw_odds,  "side": "draw"},
        {"pick": f"{away_team} ML",  "prob": p_away, "odds": away_ml,    "side": "away"},
    ]
    best_ev   = float('-inf')   # toujours garder le meilleur candidat
    best_pick = None
    for c in candidates:
        if c["odds"] <= 1.0:
            continue
        ev = compute_ev(c["prob"], c["odds"])
        if ev > best_ev:
            best_ev   = ev
            best_pick = {**c, "ev": ev}
    return best_pick

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE D'UN MATCH WC
# ─────────────────────────────────────────────────────────────────────────────

def analyze_wc_match(game: dict, odds_events: list) -> Optional[dict]:
    """
    Analyse complète d'un match WC.
    Retourne None si EV négatif ou confiance insuffisante.
    """
    home_team  = game["home_team"]
    away_team  = game["away_team"]
    venue_city = game.get("venue_city", "")

    home_stats = _find_team(home_team)
    away_stats = _find_team(away_team)

    pred = predict_wc_match(
        home_team, away_team, home_stats, away_stats, venue_city
    )

    if pred["confidence"] < MIN_CONFIDENCE:
        logger.debug(
            f"⏭️ Conf trop faible ({pred['confidence']}/100): "
            f"{away_team} vs {home_team}"
        )
        return None

    # Cotes Odds API
    odds = _extract_h2h_odds(odds_events, home_team, away_team)

    if not odds:
        # Cotes calculées depuis les probs avec marge 5%
        margin = 1.05
        odds = {
            "home_ml":   round(1.0 / (pred["p_home"] * margin), 2)
                         if pred["p_home"] > 0 else 2.50,
            "away_ml":   round(1.0 / (pred["p_away"] * margin), 2)
                         if pred["p_away"] > 0 else 2.50,
            "draw_odds": round(1.0 / (pred["p_draw"] * margin), 2)
                         if pred["p_draw"] > 0 else 3.50,
            "bookmaker": "Calculé (pas d'Odds API)",
        }
        pred["confidence"] = max(10, pred["confidence"] - 15)

    home_ml   = odds["home_ml"]
    away_ml   = odds["away_ml"]
    draw_odds = odds.get("draw_odds", 3.50)
    bookmaker = odds.get("bookmaker", "N/A")

    best = _find_best_pick(
        p_home=pred["p_home"],  p_draw=pred["p_draw"],  p_away=pred["p_away"],
        home_ml=home_ml,        draw_odds=draw_odds,     away_ml=away_ml,
        home_team=home_team,    away_team=away_team,
    )
    if not best:
        logger.debug(f"⏭️ Pas d'EV+: {away_team} vs {home_team}")
        return None

    status = "✅ BUY" if best["ev"] >= 0.03 else "👀 MONITORING"

    return {
        "home_team":       home_team,
        "away_team":       away_team,
        "home_abbr":       game.get("home_abbr", home_team[:3].upper()),
        "away_abbr":       game.get("away_abbr", away_team[:3].upper()),
        "venue":           game.get("venue", ""),
        "venue_city":      venue_city,
        "group":           game.get("group", ""),
        "commence":        game.get("commence", ""),
        "day_offset":      game.get("day_offset", 0),
        "pick":            best["pick"],
        "pick_side":       best["side"],
        "bet_odds":        best["odds"],
        "ev":              best["ev"],
        "ev_pct":          f"{best['ev']*100:+.2f}%",
        "status":          status,
        "p_home":          pred["p_home"],
        "p_draw":          pred["p_draw"],
        "p_away":          pred["p_away"],
        "predicted_score": pred["predicted_score"],
        "confidence":      pred["confidence"],
        "home_ml":         home_ml,
        "away_ml":         away_ml,
        "draw_odds":       draw_odds,
        "bookmaker":       bookmaker,
        "home_strength":   pred["home_strength"],
        "away_strength":   pred["away_strength"],
        "host_bonus_home": pred["host_bonus_home"],
        "host_bonus_away": pred["host_bonus_away"],
    }

# ─────────────────────────────────────────────────────────────────────────────
# FORMATAGE TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def _prob_bar(p: float, width: int = 8) -> str:
    """Barre de probabilité ASCII."""
    filled = round(p * width)
    return "█" * filled + "░" * (width - filled)


def _format_single_pick(pick: dict) -> str:
    """Formate un pick WC individuel pour Telegram."""
    conf_emoji = "🔥" if pick["confidence"] >= 70 else "✅"
    side_emoji = {"home": "🏠", "draw": "🤝", "away": "✈️"}.get(pick["pick_side"], "⚽")

    host_tags = []
    if pick["host_bonus_home"]:
        host_tags.append(pick["home_abbr"])
    if pick["host_bonus_away"]:
        host_tags.append(pick["away_abbr"])
    host_str  = f" 🇺🇸🇨🇦🇲🇽 ({', '.join(host_tags)})" if host_tags else ""

    venue_str = f" | 📍 {pick['venue_city']}" if pick["venue_city"] else ""
    group_str = f" | {pick['group']}"          if pick["group"]      else ""

    prob_line = (
        f"   🏠{pick['p_home']:.0%}{_prob_bar(pick['p_home'],5)} "
        f"🤝{pick['p_draw']:.0%} "
        f"✈️{pick['p_away']:.0%}{_prob_bar(pick['p_away'],5)}"
    )

    lines = [
        f"{conf_emoji} *{pick['away_team']} vs {pick['home_team']}*"
        f"{host_str}{venue_str}{group_str}",
        f"   {side_emoji} *{pick['pick']}* @ `{pick['bet_odds']:.2f}`",
        (
            f"   ⚽ Score prédit: *{pick['predicted_score']}* "
            f"| 💪 {pick['away_strength']} vs {pick['home_strength']}"
        ),
        prob_line,
        (
            f"   🎯 EV: *{pick['ev_pct']}* "
            f"| Conf: *{pick['confidence']}/100* "
            f"| 💼 {pick['bookmaker']}"
        ),
    ]
    return "\n".join(lines)


def format_wc_message(picks: list) -> str:
    """Formate le message complet des picks WC pour Telegram."""
    if not picks:
        return (
            "❌ Aucun pick Coupe du Monde avec EV positif aujourd'hui.\n"
            "_(Vérifiez que des matchs sont programmés ce jour)_"
        )

    now       = datetime.datetime.now().strftime("%H:%M")
    buy_picks = [p for p in picks if p["status"] == "✅ BUY"]
    mon_picks = [p for p in picks if p["status"] == "👀 MONITORING"]

    lines = [
        "🏆 *ULTRON — COUPE DU MONDE FIFA 2026*",
        f"🕐 {now} (Québec) | {len(picks)} match(s) analysé(s)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if buy_picks:
        lines.append(f"\n✅ *BUY — EV ≥ +3% ({len(buy_picks)})*\n")
        for p in buy_picks:
            lines.append(_format_single_pick(p))
            lines.append("")

    if mon_picks:
        lines.append(f"👀 *MONITORING — EV positif ({len(mon_picks)})*\n")
        for p in mon_picks[:5]:
            lines.append(_format_single_pick(p))
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"📊 {len(picks)} analyse(s) | {len(buy_picks)} BUY | {len(mon_picks)} MONITORING"
    )
    lines.append(
        "⚠️ _Mise suggérée: 1-2% bankroll. "
        "Tournoi = variance élevée, gérez votre bankroll._"
    )
    return "\n".join(lines)


def send_telegram(message: str, chat_id: str) -> None:
    if not TELEGRAM_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = _SESSION.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.error(f"❌ Telegram {resp.status_code}: {resp.text[:150]}")
        else:
            logger.info(f"✅ Message Telegram envoyé → {chat_id}")
    except Exception as e:
        logger.error(f"❌ Telegram send: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_wc_analysis(days_ahead: int = 2, send: bool = True) -> list:
    """
    Lance l'analyse Coupe du Monde FIFA 2026.

    1. Récupère les matchs ESPN (soccer/fifa.world)
    2. Récupère les cotes Odds API (soccer_fifa_world_cup)
    3. Pour chaque match: Dixon-Coles + EV + confiance
    4. Filtre picks EV positif
    5. Envoie via Telegram si send=True

    Retourne la liste des picks triés par EV décroissant.
    """
    logger.info("🏆 Ultron — Analyse Coupe du Monde FIFA 2026")
    _CACHE.clear()

    games = get_wc_games(days_ahead=days_ahead)
    if not games:
        logger.info("ℹ️ Aucun match WC trouvé")
        return []

    logger.info(f"⚽ WC: {len(games)} matchs à analyser")
    odds_events = get_wc_odds()
    if not odds_events:
        logger.warning("⚠️ Cotes WC indisponibles — analyse sans cotes réelles")

    picks = []
    for game in games:
        try:
            logger.info(f"  🔍 {game['away_team']} vs {game['home_team']}")
            result = analyze_wc_match(game, odds_events)
            if result:
                picks.append(result)
                logger.info(
                    f"     ✅ {result['pick']} @ {result['bet_odds']:.2f} "
                    f"| EV: {result['ev_pct']} | Conf: {result['confidence']}/100"
                )
            else:
                logger.info(f"     ⏭️ Pas d'EV+")
        except Exception as e:
            logger.error(
                f"❌ WC {game.get('away_team')} vs {game.get('home_team')}: {e}",
                exc_info=True,
            )

    picks.sort(key=lambda x: x["ev"], reverse=True)

    buy_count = sum(1 for p in picks if p["status"] == "✅ BUY")
    logger.info(f"✅ WC terminé: {len(picks)} pick(s) EV+ | BUY: {buy_count}")

    if send and picks:
        msg = format_wc_message(picks)
        if TELEGRAM_CHAT:
            send_telegram(msg, TELEGRAM_CHAT)
        if TELEGRAM_VIP:
            send_telegram(msg, TELEGRAM_VIP)

    return picks

# ─────────────────────────────────────────────────────────────────────────────
# TEST LOCAL
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=_logging.INFO,
    )
    picks = run_wc_analysis(send=False)

    print(f"\n{'='*60}")
    print(f"RÉSULTAT: {len(picks)} pick(s) WC avec EV positif")
    print(f"{'='*60}")

    for p in picks:
        print(
            f"\n⚽ {p['away_team']} vs {p['home_team']}\n"
            f"   {p['pick']} @ {p['bet_odds']:.2f} | "
            f"EV: {p['ev_pct']} | Conf: {p['confidence']}/100\n"
            f"   Probs: H {p['p_home']:.0%} D {p['p_draw']:.0%} "
            f"A {p['p_away']:.0%}\n"
            f"   Statut: {p['status']}"
        )

    if picks:
        print(f"\n{'─'*60}")
        print(format_wc_message(picks))
