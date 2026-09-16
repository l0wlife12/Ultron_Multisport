#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBA ADVANCED MONEYLINE ANALYZER v1.0
ESPN Data + Odds API Analysis for MoneyLine picks
Fallback/Advanced module for ULTRON v6.0
"""

import os
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  API KEYS — loaded from environment
# ─────────────────────────────────────────
try:
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
except Exception:
    ODDS_API_KEY = ""

# ─────────────────────────────────────────
#  THRESHOLDS — aligned with ULTRON v6.0
# ─────────────────────────────────────────
CONFIDENCE_THRESHOLD = 55     # MoneyLine: ≥55% BUY
MIN_EDGE_PCT = 0.05           # Edge minimum vs implied probability (5%)
SHARP_MONEY_WEIGHT = 20       # Bonus if sharp money detected
B2B_PENALTY = 12              # Back-to-back fatigue penalty


# ══════════════════════════════════════════
#  1. TELEGRAM HELPER
# ══════════════════════════════════════════
def send_telegram(message: str) -> None:
    """Send formatted Telegram message (optional fallback)"""
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.debug(f"Telegram send skipped: {e}")


# ══════════════════════════════════════════
#  2. ESPN — NBA GAMES TODAY
# ══════════════════════════════════════════
def get_nba_games_today() -> list:
    """Fetch today's NBA games from ESPN"""
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"⚠️ ESPN scoreboard error: {e}")
        return []

    games = []
    for event in resp.json().get("events", []):
        comp = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue
        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
        games.append({
            "game_id": event.get("id"),
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_abbr": home.get("team", {}).get("abbreviation", ""),
            "away_abbr": away.get("team", {}).get("abbreviation", ""),
            "venue": comp.get("venue", {}).get("fullName", "Unknown Arena"),
        })
    return games


# ══════════════════════════════════════════
#  3. ESPN — TEAM ID LOOKUP
# ══════════════════════════════════════════
def get_team_id(team_abbr: str) -> str:
    """Get ESPN team ID from abbreviation"""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        for t in resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = t.get("team", {})
            if team.get("abbreviation", "").upper() == team_abbr.upper():
                return team.get("id")
    except Exception as e:
        logger.debug(f"ESPN team id error: {e}")
    return None


# ══════════════════════════════════════════
#  4. ESPN — SCHEDULE + B2B DETECTION
# ══════════════════════════════════════════
def get_team_schedule(team_abbr: str) -> dict:
    """Get team schedule with L10, B2B, home/away splits"""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {"last10": [], "is_b2b": False, "home_last5": [], "away_last5": []}

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"ESPN schedule error: {e}")
        return {"last10": [], "is_b2b": False, "home_last5": [], "away_last5": []}

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    completed = []

    for event in resp.json().get("events", []):
        date_str = event.get("date", "")[:10]
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if not comp.get("status", {}).get("type", {}).get("completed"):
            continue

        team_data = next((c for c in competitors
                          if c.get("team", {}).get("abbreviation", "").upper() == team_abbr.upper()), None)
        opp_data = next((c for c in competitors
                         if c.get("team", {}).get("abbreviation", "").upper() != team_abbr.upper()), None)
        if not team_data or not opp_data:
            continue

        completed.append({
            "date": date_str,
            "won": team_data.get("winner", False),
            "home": team_data.get("homeAway") == "home",
            "pts": int(team_data.get("score", 0)),
            "opp_pts": int(opp_data.get("score", 0)),
        })

    last10 = completed[-10:]
    home_last5 = [g for g in completed if g["home"]][-5:]
    away_last5 = [g for g in completed if not g["home"]][-5:]
    is_b2b = bool(completed and completed[-1]["date"] == yesterday)

    return {
        "last10": last10,
        "is_b2b": is_b2b,
        "home_last5": home_last5,
        "away_last5": away_last5,
    }


# ══════════════════════════════════════════
#  5. ESPN — ADVANCED STATS
# ══════════════════════════════════════════
def get_team_advanced_stats(team_abbr: str) -> dict:
    """Get team advanced stats (net rating, pace, efficiency)"""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/statistics"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"ESPN stats error: {e}")
        return {}

    stats = {}
    for cat in resp.json().get("results", {}).get("stats", {}).get("categories", []):
        for s in cat.get("stats", []):
            stats[s.get("name", "")] = s.get("value", 0)

    return {
        "win_pct": stats.get("winPct", 0),
        "home_win_pct": stats.get("homeWinPct", 0),
        "away_win_pct": stats.get("awayWinPct", 0),
        "net_rating": stats.get("netRating", 0),
        "off_rating": stats.get("offensiveRating", 0),
        "def_rating": stats.get("defensiveRating", 0),
        "pace": stats.get("pace", 0),
        "pts_avg": stats.get("avgPoints", 0),
        "pts_allowed": stats.get("avgPointsAllowed", 0),
        "bench_pts": stats.get("benchPoints", 0),
    }


# ══════════════════════════════════════════
#  6. ESPN — NBA INJURIES
# ══════════════════════════════════════════
def get_nba_injuries() -> list:
    """Fetch all NBA injuries"""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"ESPN injuries error: {e}")
        return []

    injuries = []
    for team in resp.json().get("injuries", []):
        team_name = team.get("team", {}).get("displayName", "")
        for p in team.get("injuries", []):
            injuries.append({
                "team": team_name,
                "player": p.get("athlete", {}).get("displayName", ""),
                "status": p.get("status", ""),
                "pos": p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
            })
    return injuries


def get_team_injury_impact(team_name: str, injuries: list) -> dict:
    """Get injury impact for specific team (star players OUT/questionable)"""
    key_pos = {"PG", "SG", "SF", "PF", "C", "G", "F"}
    team_inj = [i for i in injuries if team_name.lower() in i["team"].lower()
                and i["pos"].upper() in key_pos]
    stars_out = [i for i in team_inj if "out" in i["status"].lower()]
    stars_qtb = [i for i in team_inj if "questionable" in i["status"].lower()
                 or "day-to-day" in i["status"].lower()]
    return {
        "stars_out": stars_out,
        "stars_qtb": stars_qtb,
        "out_count": len(stars_out),
        "qtb_count": len(stars_qtb),
    }


# ══════════════════════════════════════════
#  7. ODDS API — MONEYLINE ODDS
# ══════════════════════════════════════════
def get_nba_odds_events() -> list:
    """Fetch all NBA events from Odds API"""
    if not ODDS_API_KEY:
        return []
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    try:
        resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug(f"Odds API events error: {e}")
        return []


def get_moneyline_odds(odds_event_id: str) -> dict:
    """Get MoneyLine odds + sharp money detection"""
    if not ODDS_API_KEY:
        return {}
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{odds_event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"Odds API ML error: {e}")
        return {}

    data = resp.json()
    bookmakers = data.get("bookmakers", [])
    if not bookmakers:
        return {}

    home_team = data.get("home_team", "")
    home_odds_list = []
    away_odds_list = []
    opening_home = None

    for bm in bookmakers:
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                price = outcome.get("price", 0)
                if outcome.get("name") == home_team:
                    home_odds_list.append(price)
                    if opening_home is None:
                        opening_home = price
                else:
                    away_odds_list.append(price)

    if not home_odds_list:
        return {}

    def american_to_prob(odds: float) -> float:
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        return 100 / (odds + 100)

    avg_home_odds = sum(home_odds_list) / len(home_odds_list)
    avg_away_odds = sum(away_odds_list) / len(away_odds_list)
    current_home = home_odds_list[-1]
    movement = round(current_home - (opening_home or current_home), 1)
    sharp_signal = abs(movement) >= 10

    return {
        "home_ml": round(avg_home_odds),
        "away_ml": round(avg_away_odds),
        "implied_prob_home": round(american_to_prob(avg_home_odds), 3),
        "implied_prob_away": round(american_to_prob(avg_away_odds), 3),
        "line_movement": movement,
        "sharp_signal": sharp_signal,
        "sharp_direction": "home" if movement < 0 else "away",
        "consensus_books": len(bookmakers),
    }


def match_odds_event(home_abbr: str, away_abbr: str, odds_events: list) -> str:
    """Match ESPN game with Odds API event by team abbreviation"""
    for event in odds_events:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if home_abbr.lower() in h or away_abbr.lower() in a:
            return event.get("id")
    return None


# ══════════════════════════════════════════
#  8. PROBABILITY CALCULATION
# ══════════════════════════════════════════
def calculate_espn_win_prob(schedule: dict, adv_stats: dict, side: str) -> float:
    """
    Estimate win probability from ESPN data.
    Combines: season win%, L10 form, home/away record
    """
    last10 = schedule.get("last10", [])
    wins_l10 = sum(1 for g in last10 if g["won"])
    form_l10 = wins_l10 / len(last10) if last10 else 0.5

    season_wp = adv_stats.get("win_pct", 0.5)
    loc_wp = (adv_stats.get("home_win_pct", 0.5) if side == "home"
              else adv_stats.get("away_win_pct", 0.5))

    # Weighting: 40% season, 35% L10 form, 25% home/away record
    prob = (season_wp * 0.40) + (form_l10 * 0.35) + (loc_wp * 0.25)
    return round(min(0.95, max(0.05, prob)), 3)


# ══════════════════════════════════════════
#  9. MONEYLINE SCORING ENGINE
# ══════════════════════════════════════════
def score_moneyline(
    team_name: str,
    side: str,
    schedule: dict,
    adv_stats: dict,
    injury_impact: dict,
    odds_data: dict,
) -> dict:
    """
    Advanced MoneyLine confidence score (0-100)
    Factors: ESPN win prob vs implied, L10 form, ATS record, 
             net rating, B2B, injuries, sharp money
    
    ULTRON v6.0 threshold: ≥55% BUY
    """
    last10 = schedule.get("last10", [])
    is_b2b = schedule.get("is_b2b", False)
    score = 50
    reasons = []
    penalties = []

    espn_prob = calculate_espn_win_prob(schedule, adv_stats, side)
    implied_prob = (odds_data.get("implied_prob_home", 0.5) if side == "home"
                    else odds_data.get("implied_prob_away", 0.5))
    edge = round(espn_prob - implied_prob, 3)

    # ── 1. EDGE vs MARKET ──────────────────────────────────
    if edge >= 0.10:
        score += 25
        reasons.append(f"Strong edge: ESPN {espn_prob:.0%} vs implied {implied_prob:.0%} (+{edge:.0%})")
    elif edge >= MIN_EDGE_PCT:
        score += 15
        reasons.append(f"Positive edge: ESPN {espn_prob:.0%} vs implied {implied_prob:.0%} (+{edge:.0%})")
    elif edge < -0.05:
        score -= 15
        penalties.append(f"Negative edge: ESPN {espn_prob:.0%} vs implied {implied_prob:.0%} ({edge:.0%})")

    # ── 2. L10 FORM ────────────────────────────────────────
    wins_l10 = sum(1 for g in last10 if g["won"])
    if wins_l10 >= 8:
        score += 18
        reasons.append(f"Excellent form L10: {wins_l10}/10")
    elif wins_l10 >= 6:
        score += 10
        reasons.append(f"Good form L10: {wins_l10}/10")
    elif wins_l10 <= 3:
        score -= 15
        penalties.append(f"Poor form L10: {wins_l10}/10")
    elif wins_l10 <= 4:
        score -= 8
        penalties.append(f"Inconsistent form L10: {wins_l10}/10")

    # ── 3. HOME/AWAY RECORD ────────────────────────────────
    if side == "home":
        loc_games = schedule.get("home_last5", [])
        loc_wins = sum(1 for g in loc_games if g["won"])
        loc_label = "home"
        home_wp = adv_stats.get("home_win_pct", 0.5)
        if home_wp >= 0.65:
            score += 10
            reasons.append(f"Strong at home ({home_wp:.0%})")
        elif home_wp <= 0.40:
            score -= 8
            penalties.append(f"Weak at home ({home_wp:.0%})")
    else:
        loc_games = schedule.get("away_last5", [])
        loc_wins = sum(1 for g in loc_games if g["won"])
        loc_label = "away"
        away_wp = adv_stats.get("away_win_pct", 0.5)
        if away_wp >= 0.55:
            score += 10
            reasons.append(f"Solid on road ({away_wp:.0%})")
        elif away_wp <= 0.35:
            score -= 8
            penalties.append(f"Weak on road ({away_wp:.0%})")

    if loc_games:
        if loc_wins >= 4:
            score += 8
            reasons.append(f"L5 form ({loc_label}): {loc_wins}/5")
        elif loc_wins <= 1:
            score -= 8
            penalties.append(f"L5 form ({loc_label}): {loc_wins}/5")

    # ── 4. NET RATING ─────────────────────────────────────
    net = adv_stats.get("net_rating", 0)
    if net >= 8:
        score += 12
        reasons.append(f"Dominant net rating: +{net:.1f}")
    elif net >= 4:
        score += 6
        reasons.append(f"Positive net rating: +{net:.1f}")
    elif net <= -4:
        score -= 10
        penalties.append(f"Negative net rating: {net:.1f}")

    # ── 5. BACK-TO-BACK ────────────────────────────────────
    if is_b2b:
        score -= B2B_PENALTY
        penalties.append(f"Back-to-back fatigue (-{B2B_PENALTY}pts)")

    # ── 6. SHARP MONEY ────────────────────────────────────
    if odds_data.get("sharp_signal"):
        mv = odds_data.get("line_movement", 0)
        sharp_dir = odds_data.get("sharp_direction", "")
        if sharp_dir == side:
            score += SHARP_MONEY_WEIGHT
            reasons.append(f"Sharp money aligned (movement: {mv:+})")
        else:
            score -= 12
            penalties.append(f"Sharp money against us (movement: {mv:+})")

    # ── 7. INJURIES ────────────────────────────────────────
    out_count = injury_impact.get("out_count", 0)
    qtb_count = injury_impact.get("qtb_count", 0)
    stars_out = injury_impact.get("stars_out", [])

    if out_count >= 2:
        score -= 22
        names = ", ".join(i["player"] for i in stars_out[:2])
        penalties.append(f"Multiple stars OUT: {names}")
    elif out_count == 1:
        score -= 12
        penalties.append(f"Star OUT: {stars_out[0]['player']}")
    if qtb_count >= 2:
        score -= 6
        penalties.append(f"{qtb_count} players uncertain")

    final = max(0, min(100, score))
    return {
        "team": team_name,
        "side": side,
        "espn_prob": espn_prob,
        "implied_prob": implied_prob,
        "edge": edge,
        "wins_l10": wins_l10,
        "net_rating": adv_stats.get("net_rating", 0),
        "is_b2b": is_b2b,
        "line_move": odds_data.get("line_movement", 0),
        "sharp": odds_data.get("sharp_signal", False),
        "sharp_dir": odds_data.get("sharp_direction", ""),
        "ml_odds": (odds_data.get("home_ml", 0) if side == "home"
                    else odds_data.get("away_ml", 0)),
        "confidence": final,
        "reasons": reasons,
        "penalties": penalties,
        "send": final >= CONFIDENCE_THRESHOLD and edge >= MIN_EDGE_PCT,
    }


# ══════════════════════════════════════════
#  10. TELEGRAM MESSAGE BUILDER
# ══════════════════════════════════════════
def build_telegram_message(r: dict, game: dict) -> str:
    """Build detailed Telegram message for MoneyLine pick"""
    # 🔒 Lock (haute confiance) | ⚡ Medium | 🎲 Risqué (voir seuils convenus)
    c = r["confidence"]
    emoji = "🔒" if c >= 75 else ("⚡" if c >= 60 else "🎲")
    side_str = "HOME" if r["side"] == "home" else "AWAY"
    b2b_str = " ⚠️ B2B" if r["is_b2b"] else ""
    ml_str = f"{r['ml_odds']:+}" if r['ml_odds'] else "N/A"
    sharp_str = f"Yes ({r['sharp_dir'].upper()})" if r["sharp"] else "No"
    mv_str = f"{r['line_move']:+}"
    pos_text = "\n".join(f"  ✅ {x}" for x in r["reasons"]) or "  —"
    neg_text = "\n".join(f"  ⚠️ {x}" for x in r["penalties"]) or "  —"

    return (
        f"{emoji} *ULTRON — NBA MONEYLINE (Advanced)*\n"
        f"🏀 *{game['away_team']} @ {game['home_team']}*\n"
        f"🏟 {game['venue']}\n\n"
        f"🎯 Pick: *{r['team']} ({side_str})* @ *{ml_str}*{b2b_str}\n"
        f"📊 Confidence: *{r['confidence']}/100*\n\n"
        f"📈 ESPN Prob: *{r['espn_prob']:.0%}* vs Implied: *{r['implied_prob']:.0%}*\n"
        f"💹 Edge: *{r['edge']:+.0%}*\n"
        f"📊 L10 Form: *{r['wins_l10']}/10*\n"
        f"📈 Net Rating: *{r['net_rating']:+.1f}*\n"
        f"💰 Sharp Money: *{sharp_str}* (movement: {mv_str})\n\n"
        f"✅ *Strengths:*\n{pos_text}\n\n"
        f"⚠️ *Concerns:*\n{neg_text}"
    )


# ══════════════════════════════════════════
#  11. MAIN ENTRY POINT
# ══════════════════════════════════════════
def run_nba_moneyline_advanced() -> list:
    """
    Run comprehensive NBA MoneyLine analysis.
    Returns list of qualified picks (confidence ≥ threshold + positive edge)
    """
    logger.info("🏀 Starting NBA Advanced MoneyLine Analysis...")

    injuries = get_nba_injuries()
    espn_games = get_nba_games_today()
    odds_events = get_nba_odds_events()

    if not espn_games:
        logger.info("ℹ️ No NBA games found today")
        return []

    qualified_picks = []

    for game in espn_games:
        logger.info(f"🔍 Analyzing: {game['away_team']} @ {game['home_team']}")

        home_schedule = get_team_schedule(game["home_abbr"])
        away_schedule = get_team_schedule(game["away_abbr"])
        home_stats = get_team_advanced_stats(game["home_abbr"])
        away_stats = get_team_advanced_stats(game["away_abbr"])
        home_injuries = get_team_injury_impact(game["home_team"], injuries)
        away_injuries = get_team_injury_impact(game["away_team"], injuries)

        odds_id = match_odds_event(game["home_abbr"], game["away_abbr"], odds_events)
        odds_data = get_moneyline_odds(odds_id) if odds_id else {}

        if not odds_data:
            logger.debug(f"  ⏭️  No MoneyLine odds available — skipping")
            continue

        results = []
        for team_name, side, schedule, stats, inj in [
            (game["home_team"], "home", home_schedule, home_stats, home_injuries),
            (game["away_team"], "away", away_schedule, away_stats, away_injuries),
        ]:
            result = score_moneyline(team_name, side, schedule, stats, inj, odds_data)
            logger.info(f"  {team_name} ({side}) → {result['confidence']}/100 | edge: {result['edge']:+.0%}")
            results.append(result)

        best = max(results, key=lambda r: r["confidence"])
        if best["send"]:
            qualified_picks.append({
                "game": game,
                "pick": best,
                "message": build_telegram_message(best, game),
            })
            logger.info(f"  ✅ Pick qualified: {best['team']} — {best['confidence']}/100")
        else:
            top = max(r["confidence"] for r in results)
            logger.info(f"  ❌ Confidence too low ({top}/100) or insufficient edge — rejected")

    logger.info(f"✅ Analysis complete: {len(qualified_picks)} qualified pick(s)")
    return qualified_picks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    picks = run_nba_moneyline_advanced()
    for p in picks:
        print(p["message"])
