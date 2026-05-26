#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON Picks Engine — ultron_picks.py  (VERSION CORRIGÉE)

Corrections appliquées :
  FIX 1 — print() remplacés par logger partout
  FIX 2 — Fuzzy match équipes renforcé (évite faux positifs)
  FIX 3 — Spread pick corrigé (ne prend plus toujours l'équipe away)
  FIX 4 — Filtre matchs déjà commencés
  FIX 5 — MIN_CONFIDENCE relevé à 57
  FIX 6 — ESPN fetch protégé dans try/except (ne bloque plus Telegram)
  FIX 7 — _match_espn_game renforcé contre les faux positifs multi-mots

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
from datetime import datetime, timezone
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

# FIX 5 — Seuils relevés pour éviter les picks sans edge réel
MIN_EV         = 0.0   # EV ≥ 0 = au moins neutre
MIN_CONFIDENCE = 57    # Relevé de 52 → 57 (52% = quasi pile-ou-face avec marge book)

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


# FIX 2 — Fuzzy match renforcé
# Mots trop génériques qui causent des faux positifs (ex: "state", "city", "new")
_FUZZY_STOPWORDS = {
    "state", "city", "new", "los", "san", "las", "golden", "the",
    "bay", "north", "south", "east", "west", "old", "great", "red",
}

def _team_tokens(name: str) -> list:
    """
    Extrait les tokens significatifs d'un nom d'équipe.
    Filtre les stopwords et les tokens trop courts.
    Ex: "Golden State Warriors" → ["warriors"]
        "Oklahoma City Thunder" → ["thunder"]
        "New York Knicks"       → ["york", "knicks"]
    """
    tokens = [
        w for w in name.lower().split()
        if len(w) > 3 and w not in _FUZZY_STOPWORDS
    ]
    if not tokens:
        tokens = [name.lower().split()[-1]]
    return tokens


def _team_name_match(name_a: str, name_b: str) -> bool:
    """
    Vérifie si deux noms d'équipes correspondent.
    Requiert que TOUS les tokens significatifs de name_a soient dans name_b.
    """
    tokens_a = _team_tokens(name_a)
    name_b_lower = name_b.lower()
    return all(t in name_b_lower for t in tokens_a)


def _best_odds_from_bookmakers(bookmakers: list, away_team: str, home_team: str) -> dict:
    """
    Extrait les meilleures cotes ML, spread et total parmi les bookmakers
    dans l'ordre de priorité défini par _BK_PRIORITY.

    FIX 2 — Utilise _team_name_match() au lieu du fuzzy fragile
    FIX 3 — Spread pick : cherche les deux côtés, prend le meilleur EV
    """
    sorted_bk = sorted(
        bookmakers,
        key=lambda b: _BK_PRIORITY.index(b["key"]) if b["key"] in _BK_PRIORITY else 99,
    )

    ml_away = ml_home = None
    spread_away = spread_home = None
    ou_pick = ou_odds_val = ""

    for bk in sorted_bk:
        for mkt in bk.get("markets", []):
            mkey     = mkt["key"]
            outcomes = mkt.get("outcomes", [])

            # ── MoneyLine ───────────────────────────────────────────────
            if mkey == "h2h" and (ml_away is None or ml_home is None):
                for o in outcomes:
                    if _team_name_match(away_team, o["name"]) and ml_away is None:
                        ml_away = {"team": o["name"], "odds": o["price"]}
                    elif _team_name_match(home_team, o["name"]) and ml_home is None:
                        ml_home = {"team": o["name"], "odds": o["price"]}

            # ── Spread — FIX 3 : collecte les deux côtés ────────────────
            elif mkey == "spreads" and spread_away is None:
                for o in outcomes:
                    pt   = o.get("point", 0)
                    sign = "+" if pt > 0 else ""
                    entry = {
                        "pick": f"{o['name'].upper()} {sign}{pt}",
                        "odds": f"{o['price']:.2f}",
                        "price": o["price"],
                        "point": pt,
                    }
                    if _team_name_match(away_team, o["name"]):
                        spread_away = entry
                    elif _team_name_match(home_team, o["name"]):
                        spread_home = entry

            # ── Total O/U ────────────────────────────────────────────────
            elif mkey == "totals" and not ou_pick:
                for o in outcomes:
                    if o["name"] == "Over":
                        ou_pick     = f"OVER {o.get('point', '')}".strip()
                        ou_odds_val = f"{o['price']:.2f}"
                        break

        if ml_away and ml_home and (spread_away or spread_home) and ou_pick:
            break

    # FIX 3 — Choisit le spread avec la meilleure cote
    best_spread = None
    if spread_away and spread_home:
        best_spread = spread_away if spread_away["price"] >= spread_home["price"] else spread_home
    elif spread_away:
        best_spread = spread_away
    elif spread_home:
        best_spread = spread_home

    return {
        "ml_away":     ml_away,
        "ml_home":     ml_home,
        "spread_pick": best_spread["pick"] if best_spread else "",
        "spread_odds": best_spread["odds"] if best_spread else "1.91",
        "ou_pick":     ou_pick,
        "ou_odds":     ou_odds_val or "1.91",
    }


def analyze_game(game: dict, sport: str) -> Optional[dict]:
    """
    Analyse un événement brut de l'Odds API.

    FIX 4 — Filtre les matchs déjà commencés (cotes instables).
    Les probabilités sont dérivées des cotes h2h (implied probability corrigée
    de la marge bookmaker), sans dépendre des stats statiques hardcodées.

    Retourne None si les données sont insuffisantes ou sous le seuil MIN_CONFIDENCE.
    """
    away_team  = game.get("away_team", "")
    home_team  = game.get("home_team", "")
    bookmakers = game.get("bookmakers", [])

    if not away_team or not home_team or not bookmakers:
        return None

    # FIX 4 — Ignorer les matchs déjà commencés
    commence_time = game.get("commence_time", "")
    if commence_time:
        try:
            game_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            if game_dt < datetime.now(timezone.utc):
                logger.debug(f"⏭️ Match déjà commencé, ignoré: {away_team} @ {home_team}")
                return None
        except Exception as e:
            logger.debug(f"⚠️ Parsing commence_time échoué: {e}")

    odds_data = _best_odds_from_bookmakers(bookmakers, away_team, home_team)
    ml_away   = odds_data["ml_away"]
    ml_home   = odds_data["ml_home"]

    if not ml_away or not ml_home:
        logger.debug(f"⚠️ Cotes ML introuvables: {away_team} @ {home_team}")
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
        logger.debug(
            f"⏭️ Confiance {confidence}% < seuil {MIN_CONFIDENCE}%: "
            f"{away_team} @ {home_team}"
        )
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
        "commence_time": commence_time,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FIX 7 — _match_espn_game renforcé
# ─────────────────────────────────────────────────────────────────────────────

def _match_espn_game(home: str, away: str, espn_games: list) -> Optional[dict]:
    """
    Trouve le match ESPN correspondant.

    FIX 7 — Utilise _team_name_match() (strict) au lieu du fuzzy fragile.
    Requiert que home ET away matchent tous les deux pour valider le match.
    Évite les faux positifs entre équipes de la même ville (ex: Knicks vs Rangers).
    """
    for g in espn_games:
        home_match = _team_name_match(home, g.get("home_team", ""))
        away_match = _team_name_match(away, g.get("away_team", ""))
        if home_match and away_match:
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
    """
    Génère les picks journaliers en croisant Odds API + ESPN.

    FIX 1 — print() remplacés par logger (visibles dans Railway)
    FIX 6 — ESPN fetch protégé dans try/except (ne bloque plus Telegram)
    """

    # 1. Contexte ESPN — FIX 6 : protégé, non bloquant
    espn_context = {}
    if _ESPN_AVAILABLE:
        try:
            logger.info("📡 ESPN — fetch contexte complet...")
            espn_context = get_full_context_all_sports()
            logger.info(f"✅ ESPN contexte chargé: {len(espn_context)} sports")
        except Exception as e:
            logger.error(f"❌ ESPN fetch échoué (picks sans ajustement ESPN): {e}")

    # 2. Cotes bookmakers — FIX 1 : logger au lieu de print()
    logger.info("💰 Odds API — fetch cotes...")
    all_odds: dict = {}
    for sport_name, sport_key in SPORTS.items():
        games = fetch_sport_odds(sport_key)
        if games:
            all_odds[sport_name] = games
            logger.info(f"  ✅ {sport_name}: {len(games)} matchs trouvés")
        else:
            logger.warning(f"  ⚠️ {sport_name}: aucun match ou API indisponible")

    # 3. Croise les deux sources
    all_analyses = []
    for sport, games in all_odds.items():
        espn_games = espn_context.get(sport, [])

        for game in games:
            analysis = analyze_game(game, sport)
            if not analysis:
                continue

            # Trouve le contexte ESPN correspondant — FIX 7
            espn_game = _match_espn_game(
                analysis["home_team"],
                analysis["away_team"],
                espn_games,
            )

            if espn_game:
                analysis = _apply_espn_adjustment(analysis, espn_game)

            all_analyses.append(analysis)

    logger.info(f"📊 Picks générés: {len(all_analyses)} total")

    # Trier par confiance décroissante
    all_analyses.sort(key=lambda a: a["fav_prob"], reverse=True)

    # Alerte blessures (message Telegram séparé)
    injuries_msg = ""
    if _ESPN_AVAILABLE and espn_context:
        try:
            injuries_msg = format_injuries_alert(espn_context)
        except Exception as e:
            logger.warning(f"⚠️ format_injuries_alert: {e}")

    buy_picks = [a for a in all_analyses if a["fav_ev"] > MIN_EV]
    logger.info(
        f"✅ BUY: {len(buy_picks)} | "
        f"Total: {len(all_analyses)} | "
        f"Bankroll: ${bankroll}"
    )

    return {
        "picks":          all_analyses,
        "injuries_alert": injuries_msg,
        "bankroll":       bankroll,
        "timestamp":      datetime.now().isoformat(),
        "total":          len(all_analyses),
        "buy_picks":      buy_picks,
    }
