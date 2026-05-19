"""
════════════════════════════════════════════════════════════════════════════════
  ULTRON — NBA PLAYER PROPS ANALYZER  v2.0
════════════════════════════════════════════════════════════════════════════════

Analyse automatique des props joueurs NBA (Over/Under Points):
- Récupère les blessures ESPN
- Récupère les stats ESPN (saison + derniers matchs)
- Récupère les props The Odds API
- Score chaque prop avec filtre injury + confiance
- Envoie picks sur Telegram

Exécution: python ultron_props_analyzer.py
"""

import os
import requests
import logging
from typing import Optional

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  CLÉS — stockées sur Railway
# ─────────────────────────────────────────
ODDS_API_KEY    = os.environ.get("ODDS_API_KEY", "")
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")

if not ODDS_API_KEY:
    logger.warning("⚠️  ODDS_API_KEY non configurée")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
    logger.warning("⚠️  TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID non configurée")

# ─────────────────────────────────────────
#  PARAMÈTRES AJUSTABLES
# ─────────────────────────────────────────
CONFIDENCE_THRESHOLD = 65   # Pick ignoré si en dessous
MIN_AVG_POINTS       = 18.0  # Moyenne min pour être considéré "star"
MIN_AVG_MINUTES      = 28.0  # Minutes min par match


# ══════════════════════════════════════════
#  1.  TELEGRAM
# ══════════════════════════════════════════
def send_telegram(message: str) -> None:
    """Envoie un message sur Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        logger.warning("❌ Telegram non configuré — message non envoyé")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"❌ Telegram error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"❌ Telegram send error: {e}")


# ══════════════════════════════════════════
#  2.  BLESSURES ESPN
# ══════════════════════════════════════════
def get_nba_injuries() -> list:
    """Retourne la liste de toutes les blessures NBA du jour."""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"⚠️  ESPN injuries error: {e}")
        return []

    injuries = []
    for team in resp.json().get("injuries", []):
        team_name = team.get("team", {}).get("displayName", "")
        for p in team.get("injuries", []):
            injuries.append({
                "team":   team_name,
                "player": p.get("athlete", {}).get("displayName", ""),
                "status": p.get("status", ""),          # Out / Questionable / Day-To-Day
                "pos":    p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
            })
    logger.info(f"✅ Blessures NBA: {len(injuries)} joueurs affectés")
    return injuries


def player_injury_status(player_name: str, injuries: list) -> Optional[str]:
    """Retourne le status de blessure d'un joueur, ou None s'il est sain."""
    name_lower = player_name.lower()
    for i in injuries:
        if name_lower in i["player"].lower():
            return i["status"]
    return None


# ══════════════════════════════════════════
#  3.  STATS ESPN — saison & derniers matchs
# ══════════════════════════════════════════
def _get_athlete_id(player_name: str) -> Optional[str]:
    """Récupère l'ID ESPN d'un joueur."""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/athletes"
    try:
        resp = requests.get(url, params={"search": player_name, "limit": 1}, timeout=10)
        resp.raise_for_status()
        athletes = resp.json().get("athletes", [])
        return athletes[0]["id"] if athletes else None
    except Exception as e:
        logger.debug(f"⚠️  ESPN athlete search error: {e}")
        return None


def get_season_stats(player_name: str) -> dict:
    """Retourne avg_points et avg_minutes de la saison."""
    athlete_id = _get_athlete_id(player_name)
    if not athlete_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/athletes/{athlete_id}/stats"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  ESPN stats error: {e}")
        return {}

    stats_map = {}
    for cat in resp.json().get("stats", {}).get("splits", {}).get("categories", []):
        for s in cat.get("stats", []):
            stats_map[s["name"]] = s.get("value", 0)

    return {
        "avg_points":  stats_map.get("avgPoints",  0),
        "avg_minutes": stats_map.get("avgMinutes", 0),
    }


def get_last_n_points(player_name: str, n: int = 10) -> list:
    """Retourne les points des N derniers matchs du joueur."""
    athlete_id = _get_athlete_id(player_name)
    if not athlete_id:
        return []

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/athletes/{athlete_id}/gamelog"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  ESPN gamelog error: {e}")
        return []

    points = []
    for game in resp.json().get("events", {}).get("events", [])[:n]:
        for s in game.get("stats", []):
            if s.get("name") == "points":
                points.append(float(s.get("value", 0)))
                break
    return points


# ══════════════════════════════════════════
#  4.  PROPS O/U — The Odds API
# ══════════════════════════════════════════
def get_nba_game_ids() -> list:
    """Récupère les IDs des matchs NBA du jour."""
    if not ODDS_API_KEY:
        logger.warning("⚠️  ODDS_API_KEY absent — impossible de récupérer les matchs")
        return []
        
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    try:
        resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=10)
        resp.raise_for_status()
        return [e["id"] for e in resp.json()]
    except Exception as e:
        logger.warning(f"⚠️  Odds API events error: {e}")
        return []


def get_player_props(game_id: str) -> list:
    """Retourne les props O/U points pour un match."""
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{game_id}/odds"
    params = {
        "apiKey":      ODDS_API_KEY,
        "regions":     "us",
        "markets":     "player_points",
        "oddsFormat":  "american",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  Odds API props error: {e}")
        return []

    props = []
    data = resp.json()
    bookmakers = data.get("bookmakers", [])
    if not bookmakers:
        return []

    for market in bookmakers[0].get("markets", []):
        if market["key"] != "player_points":
            continue
        for outcome in market.get("outcomes", []):
            props.append({
                "player": outcome.get("description", ""),
                "line":   outcome.get("point", 0),
                "side":   outcome.get("name", ""),    # "Over" ou "Under"
                "odds":   outcome.get("price", 0),
            })
    return props


# ══════════════════════════════════════════
#  5.  FILTRE STARS
# ══════════════════════════════════════════
def is_star(player_name: str) -> bool:
    """Vérifie si le joueur est une 'star' (min avg points & minutes)."""
    stats = get_season_stats(player_name)
    return (
        stats.get("avg_points",  0) >= MIN_AVG_POINTS and
        stats.get("avg_minutes", 0) >= MIN_AVG_MINUTES
    )


# ══════════════════════════════════════════
#  6.  SCORE DE CONFIANCE
# ══════════════════════════════════════════
def score_prop(player: str, line: float, side: str, injuries: list) -> dict:
    """
    Retourne un dict avec confidence (0-100), reasons, penalties, send (bool).
    
    Paramètres:
    - player: nom du joueur
    - line: ligne Over/Under (ex: 25.5)
    - side: "Over" ou "Under"
    - injuries: liste des blessures ESPN
    
    Retourne:
    - confidence (0-100)
    - send (bool): True si ≥ CONFIDENCE_THRESHOLD
    - reasons, penalties (listes)
    - avg10, avg5, hit_rate (stats détaillées)
    """
    last10 = get_last_n_points(player, n=10)

    # Pas assez de données → on skip
    if len(last10) < 5:
        return {
            "confidence": 0,
            "send": False,
            "reasons": [],
            "penalties": ["Pas assez de matchs récents"],
            "avg10": 0,
            "avg5": 0,
            "hit_rate": 0,
        }

    last5      = last10[:5]
    avg10      = sum(last10) / len(last10)
    avg5       = sum(last5)  / len(last5)
    hit_rate   = sum(1 for p in last10 if (p > line if side == "Over" else p < line)) / len(last10)

    score    = 50
    reasons  = []
    penalties = []

    # ── Moyenne L10 vs ligne ──────────────────
    gap = avg10 - line if side == "Over" else line - avg10
    if gap >= 4:
        score += 25
        reasons.append(f"Moyenne L10 ({avg10:.1f} pts) très favorable vs ligne {line}")
    elif gap >= 2:
        score += 15
        reasons.append(f"Moyenne L10 ({avg10:.1f} pts) favorable vs ligne {line}")
    elif gap < 0:
        score -= 15
        penalties.append(f"Moyenne L10 ({avg10:.1f} pts) défavorable vs ligne {line}")

    # ── Tendance L5 vs L10 ────────────────────
    trend = avg5 - avg10
    if side == "Over" and trend >= 2:
        score += 10
        reasons.append(f"Joueur en hausse de forme (+{trend:.1f} pts sur L5 vs L10)")
    elif side == "Under" and trend <= -2:
        score += 10
        reasons.append(f"Joueur en baisse de forme ({trend:.1f} pts sur L5 vs L10)")
    elif side == "Over" and trend <= -2:
        score -= 8
        penalties.append(f"Légère baisse de forme ({trend:.1f} pts sur L5 vs L10)")
    elif side == "Under" and trend >= 2:
        score -= 8
        penalties.append(f"Joueur en hausse malgré pick Under")

    # ── Hit rate ─────────────────────────────
    if hit_rate >= 0.70:
        score += 15
        reasons.append(f"Hit rate élevé: {hit_rate:.0%} sur L10")
    elif hit_rate >= 0.60:
        score += 8
        reasons.append(f"Bon hit rate: {hit_rate:.0%} sur L10")
    elif hit_rate <= 0.40:
        score -= 10
        penalties.append(f"Hit rate faible: {hit_rate:.0%} sur L10")

    # ── Blessure du joueur ────────────────────
    injury = player_injury_status(player, injuries)
    if injury:
        status_lower = injury.lower()
        if "out" in status_lower:
            score -= 50
            penalties.append(f"⛔ Joueur déclaré OUT!")
        elif "questionable" in status_lower or "day-to-day" in status_lower:
            score -= 25
            penalties.append(f"⚠️ Joueur incertain ({injury})")

    final = max(0, min(100, score))
    return {
        "player":    player,
        "line":      line,
        "side":      side,
        "avg10":     round(avg10, 1),
        "avg5":      round(avg5,  1),
        "hit_rate":  round(hit_rate * 100),
        "confidence": final,
        "reasons":   reasons,
        "penalties": penalties,
        "send":      final >= CONFIDENCE_THRESHOLD,
    }


# ══════════════════════════════════════════
#  7.  MESSAGE TELEGRAM
# ══════════════════════════════════════════
def build_message(r: dict) -> str:
    """Construit un message Telegram formaté."""
    emoji = "🔥" if r["confidence"] >= 80 else "✅"
    pos   = "\n".join(f"  ✅ {x}" for x in r["reasons"])  or "  —"
    neg   = "\n".join(f"  ⚠️ {x}" for x in r["penalties"]) or "  —"

    return (
        f"{emoji} *ULTRON — NBA PLAYER PROP*\n"
        f"👤 *{r['player']}*\n"
        f"🎯 Pick: *{r['side'].upper()} {r['line']} PTS*\n"
        f"📊 Confiance: *{r['confidence']}/100*\n\n"
        f"📈 Moyenne L10: *{r['avg10']} pts*\n"
        f"📈 Moyenne L5:  *{r['avg5']} pts*\n"
        f"🎯 Hit rate L10: *{r['hit_rate']}%*\n\n"
        f"✅ *Points positifs:*\n{pos}\n\n"
        f"⚠️ *Points négatifs:*\n{neg}"
    )


# ══════════════════════════════════════════
#  8.  POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════
def run_nba_props() -> None:
    """Lance l'analyse complète des props NBA du jour."""
    logger.info("🏀 Ultron — Analyse des props NBA...")

    injuries  = get_nba_injuries()
    game_ids  = get_nba_game_ids()

    if not game_ids:
        logger.info("ℹ️  Aucun match NBA trouvé aujourd'hui.")
        return

    seen = set()   # évite les doublons Over+Under pour le même joueur
    sent_count = 0

    for game_id in game_ids:
        props = get_player_props(game_id)

        for prop in props:
            player = prop["player"]
            line   = prop["line"]
            side   = prop["side"]

            key = (player, line, side)
            if key in seen:
                continue
            seen.add(key)

            # ── Filtre stars uniquement ──────────
            if not is_star(player):
                logger.debug(f"⏭️  {player} ignoré (pas une star)")
                continue

            # ── Score de confiance ───────────────
            result = score_prop(player, line, side, injuries)

            if not result["send"]:
                logger.debug(f"❌ {player} {side} {line} — confiance trop basse ({result['confidence']}/100)")
                continue

            # ── Envoi Telegram ───────────────────
            msg = build_message(result)
            send_telegram(msg)
            logger.info(f"✅ Envoyé: {player} {side} {line} pts — {result['confidence']}/100")
            sent_count += 1

    logger.info(f"🎯 Props NBA: {sent_count} pick(s) envoyé(s)")


if __name__ == "__main__":
    run_nba_props()
