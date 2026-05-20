"""
ULTRON MLB RUNLINE ANALYZER
Analyse des Run Lines avec ATS, Sharp Money, Lanceurs, Blessures
"""
import os
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  CLÉS — stockées sur Railway
# ─────────────────────────────────────────
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# ─────────────────────────────────────────
#  PARAMÈTRES AJUSTABLES
# ─────────────────────────────────────────
CONFIDENCE_THRESHOLD = 68    # Runline: seuil plus élevé
MIN_ATS_RATE         = 0.60  # ATS hit rate minimum sur L10
MIN_WIN_BY_2_PCT     = 0.40  # % de victoires par 2+ runs minimum
SHARP_MONEY_WEIGHT   = 20    # Bonus si sharp money détecté


# ══════════════════════════════════════════
#  ESPN — STATS ÉQUIPE (L10 + saison)
# ══════════════════════════════════════════
def get_team_id(team_abbr: str) -> str:
    """Récupère l'ID ESPN d'une équipe par son abréviation."""
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        for t in resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = t.get("team", {})
            if team.get("abbreviation", "").upper() == team_abbr.upper():
                return team.get("id", "")
    except Exception as e:
        logger.debug(f"⚠️  ESPN team id error [{team_abbr}]: {e}")
    return ""


def get_team_season_stats(team_abbr: str) -> dict:
    """Retourne les stats offensives/défensives de la saison."""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams/{team_id}/statistics"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  ESPN team stats error [{team_abbr}]: {e}")
        return {}

    stats = {}
    for cat in resp.json().get("results", {}).get("stats", {}).get("categories", []):
        for s in cat.get("stats", []):
            stats[s.get("name", "")] = s.get("value", 0)

    return {
        "runs_scored_avg":  float(stats.get("avgRunsScored", 0)),
        "runs_allowed_avg": float(stats.get("avgRunsAllowed", 0)),
        "win_pct":          float(stats.get("winPct", 0)),
        "ops":              float(stats.get("OPS", 0)),
        "era":              float(stats.get("ERA", 0)),
    }


def get_team_last10_games(team_abbr: str) -> list:
    """Retourne les 10 derniers matchs avec runs_scored, runs_allowed, won, run_diff."""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return []

    url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  ESPN schedule error [{team_abbr}]: {e}")
        return []

    games = []
    for event in resp.json().get("events", []):
        comp = event.get("competitions", [{}])[0]
        if comp.get("status", {}).get("type", {}).get("completed") is not True:
            continue

        competitors = comp.get("competitors", [])
        team_data = next((c for c in competitors
                          if c.get("team", {}).get("abbreviation", "").upper() == team_abbr.upper()), None)
        opp_data   = next((c for c in competitors
                          if c.get("team", {}).get("abbreviation", "").upper() != team_abbr.upper()), None)
        if not team_data or not opp_data:
            continue

        team_score = int(team_data.get("score", 0))
        opp_score  = int(opp_data.get("score", 0))
        games.append({
            "runs_scored":  team_score,
            "runs_allowed": opp_score,
            "run_diff":     team_score - opp_score,
            "won":          team_data.get("winner", False),
        })

    return games[-10:]  # Derniers 10 matchs complétés


def get_starting_pitcher(team_abbr: str, game_id: str) -> dict:
    """Récupère le lanceur partant annoncé pour ce match."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={game_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Cherche dans les probables pitchers
        for team_info in data.get("probables", []):
            abbr = team_info.get("team", {}).get("abbreviation", "")
            if abbr.upper() == team_abbr.upper():
                athlete = team_info.get("athlete", {})
                stats   = team_info.get("statistics", [])

                era  = next((float(s.get("value", 0)) for s in stats if s.get("name") == "ERA"),  4.50)
                whip = next((float(s.get("value", 0)) for s in stats if s.get("name") == "WHIP"), 1.30)
                wins = next((int(s.get("value", 0)) for s in stats if s.get("name") == "wins"), 0)
                ip   = next((float(s.get("value", 0)) for s in stats if s.get("name") == "inningsPitched"), 0)

                return {
                    "name": athlete.get("displayName", "TBD"),
                    "era":  era,
                    "whip": whip,
                    "wins": wins,
                    "avg_innings": ip / max(wins + 1, 1),
                }
    except Exception as e:
        logger.debug(f"⚠️  ESPN pitcher error [{team_abbr}]: {e}")

    return {"name": "TBD", "era": 4.50, "whip": 1.30, "wins": 0, "avg_innings": 5.5}


def get_mlb_injuries() -> list:
    """Retourne toutes les blessures MLB actuelles."""
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  ESPN injuries error: {e}")
        return []

    injuries = []
    for team in resp.json().get("injuries", []):
        team_name = team.get("team", {}).get("displayName", "")
        for p in team.get("injuries", []):
            status = p.get("status", "")
            if status.lower() in ["out", "day-to-day", "questionable"]:
                injuries.append({
                    "team":   team_name,
                    "player": p.get("athlete", {}).get("displayName", ""),
                    "status": status,
                    "pos":    p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                })
    return injuries


def get_team_key_injuries(team_name: str, injuries: list) -> list:
    """Retourne les blessures offensives clés pour l'équipe."""
    key_positions = {"OF", "CF", "LF", "RF", "1B", "2B", "SS", "3B", "C", "DH"}
    return [
        i for i in injuries
        if team_name.lower() in i["team"].lower()
        and i["pos"].upper() in key_positions
    ]


# ══════════════════════════════════════════
#  ODDS API — RUN LINE ODDS
# ══════════════════════════════════════════
def get_run_line_odds(odds_event_id: str) -> dict:
    """Retourne la runline, mouvement, et sharp money indicators."""
    if not ODDS_API_KEY or not odds_event_id:
        return {}

    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{odds_event_id}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "spreads",
        "oddsFormat": "american",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"⚠️  Odds API runline error [{odds_event_id}]: {e}")
        return {}

    data       = resp.json()
    bookmakers = data.get("bookmakers", [])
    if not bookmakers:
        return {}

    # Collecte les cotes de tous les bookmakers
    all_home_points = []
    all_away_points = []
    opening_home    = None
    current_home    = None

    for bm in bookmakers:
        for market in bm.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                point = outcome.get("point", 0)
                if outcome.get("name") == data.get("home_team", ""):
                    all_home_points.append(point)
                    if opening_home is None:
                        opening_home = point
                    current_home = point
                else:
                    all_away_points.append(point)

    if not all_home_points:
        return {}

    current_home  = all_home_points[-1]
    opening_home  = all_home_points[0] if all_home_points else current_home
    line_movement = current_home - opening_home

    # Sharp money: mouvement > 0.5 pts
    sharp_signal = abs(line_movement) >= 0.5

    return {
        "home_spread":    current_home,
        "away_spread":    -current_home,
        "opening_spread": opening_home,
        "line_movement":  round(line_movement, 2),
        "sharp_signal":   sharp_signal,
        "consensus_books": len(bookmakers),
    }


# ══════════════════════════════════════════
#  ATS & STATS CALCULATIONS
# ══════════════════════════════════════════
def calculate_ats_stats(last10: list, spread: float) -> dict:
    """Calcule le ATS record sur les 10 derniers matchs."""
    if not last10:
        return {"ats_wins": 0, "ats_rate": 0.0, "avg_run_diff": 0.0,
                "win_by_2_pct": 0.0, "blowout_pct": 0.0}

    ats_wins   = 0
    win_by_2   = 0
    blowouts   = 0
    run_diffs  = []

    for game in last10:
        diff = game["run_diff"]
        run_diffs.append(diff)

        # ATS: équipe couvre si run_diff > |spread| (favori) ou > -spread (underdog)
        if spread < 0:   # favori
            if diff > abs(spread):
                ats_wins += 1
        else:            # underdog
            if diff > -spread:
                ats_wins += 1

        if diff >= 2:
            win_by_2 += 1
        if abs(diff) >= 5:
            blowouts += 1

    n = len(last10)
    return {
        "ats_wins":    ats_wins,
        "ats_rate":    round(ats_wins / n, 2),
        "avg_run_diff": round(sum(run_diffs) / n, 2) if run_diffs else 0.0,
        "win_by_2_pct": round(win_by_2 / n, 2),
        "blowout_pct":  round(blowouts / n, 2),
    }


def score_run_line(
    team_abbr: str,
    team_name: str,
    side: str,
    spread: float,
    last10: list,
    pitcher: dict,
    injuries: list,
    odds_data: dict,
) -> dict:
    """Scoring complet pour le runline: ATS + lanceur + injuries + sharp money."""
    score    = 50
    reasons  = []
    penalties = []

    # ── ATS record L10 ───────────────────
    ats = calculate_ats_stats(last10, spread)

    if ats["ats_rate"] >= 0.70:
        score += 20
        reasons.append(f"Excellent ATS L10: {ats['ats_wins']}/10")
    elif ats["ats_rate"] >= MIN_ATS_RATE:
        score += 12
        reasons.append(f"Bon ATS L10: {ats['ats_wins']}/10")
    elif ats["ats_rate"] <= 0.40:
        score -= 15
        penalties.append(f"Mauvais ATS L10: {ats['ats_wins']}/10")

    # ── Win by 2+ runs % ─────────────────
    if ats["win_by_2_pct"] >= 0.55:
        score += 15
        reasons.append(f"Gagne par 2+ runs souvent ({ats['win_by_2_pct']:.0%})")
    elif ats["win_by_2_pct"] < MIN_WIN_BY_2_PCT:
        score -= 12
        penalties.append(f"Rarement +2 runs d'écart ({ats['win_by_2_pct']:.0%})")

    # ── Run diff moyen ────────────────────
    if ats["avg_run_diff"] >= 2.0:
        score += 12
        reasons.append(f"Run diff moyen fort (+{ats['avg_run_diff']} runs)")
    elif ats["avg_run_diff"] >= 1.0:
        score += 6
        reasons.append(f"Run diff moyen positif (+{ats['avg_run_diff']} runs)")
    elif ats["avg_run_diff"] < 0:
        score -= 10
        penalties.append(f"Run diff moyen négatif ({ats['avg_run_diff']} runs)")

    # ── Lanceur partant ───────────────────
    if pitcher["name"] != "TBD":
        if pitcher["era"] <= 3.00:
            score += 18
            reasons.append(f"Lanceur dominant: {pitcher['name']} ERA {pitcher['era']:.2f}")
        elif pitcher["era"] <= 3.80:
            score += 10
            reasons.append(f"Bon lanceur: {pitcher['name']} ERA {pitcher['era']:.2f}")
        elif pitcher["era"] >= 5.00:
            score -= 15
            penalties.append(f"Lanceur faible: {pitcher['name']} ERA {pitcher['era']:.2f}")
        elif pitcher["era"] >= 4.50:
            score -= 8
            penalties.append(f"Lanceur moyen: {pitcher['name']} ERA {pitcher['era']:.2f}")

        if pitcher["whip"] <= 1.10:
            score += 8
            reasons.append(f"WHIP excellent: {pitcher['whip']:.2f}")
        elif pitcher["whip"] >= 1.40:
            score -= 8
            penalties.append(f"WHIP élevé: {pitcher['whip']:.2f}")
    else:
        score -= 10
        penalties.append("Lanceur partant non confirmé (TBD)")

    # ── Sharp money ───────────────────────
    if odds_data.get("sharp_signal"):
        mv = odds_data.get("line_movement", 0)
        if (spread < 0 and mv < 0) or (spread > 0 and mv > 0):
            # Mouvement favorable à notre côté
            score += SHARP_MONEY_WEIGHT
            reasons.append(f"Sharp money dans notre sens (mvt: {mv:+.1f})")
        else:
            score -= 10
            penalties.append(f"Sharp money contre nous (mvt: {mv:+.1f})")

    # ── Blessures lineup offensif ─────────
    key_injuries = get_team_key_injuries(team_name, injuries)
    out_count  = sum(1 for i in key_injuries if "out" in i["status"].lower())
    dtd_count  = sum(1 for i in key_injuries if "day" in i["status"].lower()
                                              or "questionable" in i["status"].lower())
    if out_count >= 2:
        score -= 20
        penalties.append(f"{out_count} frappeurs clés OUT")
    elif out_count == 1:
        score -= 10
        penalties.append(f"1 frappeur clé OUT")
    if dtd_count >= 2:
        score -= 10
        penalties.append(f"{dtd_count} joueurs incertains")

    final = max(0, min(100, score))
    return {
        "team":       team_name,
        "spread":     spread,
        "side":       side,
        "ats_record": f"{ats['ats_wins']}/10",
        "ats_rate":   ats["ats_rate"],
        "avg_diff":   ats["avg_run_diff"],
        "win_by_2":   ats["win_by_2_pct"],
        "pitcher":    pitcher,
        "line_move":  odds_data.get("line_movement", 0),
        "sharp":      odds_data.get("sharp_signal", False),
        "confidence": int(final),
        "reasons":    reasons,
        "penalties":  penalties,
        "send":       final >= CONFIDENCE_THRESHOLD,
    }
