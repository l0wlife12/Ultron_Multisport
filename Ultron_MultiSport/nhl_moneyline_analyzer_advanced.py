#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NHL ADVANCED MONEYLINE ANALYZER v1.0
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
CONFIDENCE_THRESHOLD  = 55     # MoneyLine: ≥55% BUY
MIN_EDGE_PCT          = 0.05   # Edge minimum vs implied probability (5%)
SHARP_MONEY_WEIGHT    = 20     # Bonus if sharp money detected
BACKUP_GOALIE_PENALTY = 20     # Backup goalie penalty
ROAD_TRIP_PENALTY     = 10     # Road trip penalty


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
#  2. ESPN — NHL GAMES TODAY
# ══════════════════════════════════════════
def get_nhl_games_today() -> list:
    """Fetch today's NHL games from ESPN"""
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={today}"
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
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams"
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
#  4. ESPN — SCHEDULE + ROAD TRIP DETECTION
# ══════════════════════════════════════════
def get_team_schedule(team_abbr: str) -> dict:
    """Get team schedule with L10, B2B, road trip detection"""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {"last10": [], "is_b2b": False, "road_trip_game": 0, "home_last5": [], "away_last5": []}

    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"ESPN schedule error: {e}")
        return {"last10": [], "is_b2b": False, "road_trip_game": 0, "home_last5": [], "away_last5": []}

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
            "goals_for": int(team_data.get("score", 0)),
            "goals_against": int(opp_data.get("score", 0)),
        })

    # Road trip streak
    road_streak = 0
    for g in reversed(completed):
        if not g["home"]:
            road_streak += 1
        else:
            break

    is_b2b = bool(completed and completed[-1]["date"] == yesterday)
    last10 = completed[-10:]
    home_last5 = [g for g in completed if g["home"]][-5:]
    away_last5 = [g for g in completed if not g["home"]][-5:]

    return {
        "last10": last10,
        "is_b2b": is_b2b,
        "road_trip_game": road_streak,
        "home_last5": home_last5,
        "away_last5": away_last5,
    }


# ══════════════════════════════════════════
#  5. ESPN — NHL TEAM STATS
# ══════════════════════════════════════════
def get_team_stats(team_abbr: str) -> dict:
    """Get NHL team stats (PP, PK, regulation win %, etc.)"""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/statistics"
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
        "regulation_win_pct": stats.get("regulationWinPct", 0),
        "goals_for_avg": stats.get("avgGoalsFor", 0),
        "goals_against_avg": stats.get("avgGoalsAgainst", 0),
        "power_play_pct": stats.get("powerPlayPct", 0),
        "penalty_kill_pct": stats.get("penaltyKillPct", 0),
        "shots_for_avg": stats.get("avgShotsFor", 0),
        "save_pct": stats.get("savePct", 0),
    }


# ══════════════════════════════════════════
#  6. ESPN — STARTING GOALIE
# ══════════════════════════════════════════
def get_starting_goalie(team_abbr: str, game_id: str) -> dict:
    """Get starting goalie stats"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={game_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        for entry in resp.json().get("probables", []):
            if entry.get("team", {}).get("abbreviation", "").upper() != team_abbr.upper():
                continue
            athlete = entry.get("athlete", {})
            stats = entry.get("statistics", [])
            sv = next((float(s.get("value", 0.900)) for s in stats if s.get("name") == "savePct"), 0.900)
            gaa = next((float(s.get("value", 3.00)) for s in stats if s.get("name") == "goalsAgainstAvg"), 3.00)
            games = next((int(s.get("value", 0)) for s in stats if s.get("name") == "gamesPlayed"), 0)
            return {
                "name": athlete.get("displayName", "TBD"),
                "save_pct": sv,
                "gaa": gaa,
                "games": games,
                "is_backup": games < 15,
                "confirmed": True,
            }
    except Exception as e:
        logger.debug(f"ESPN goalie error: {e}")

    return {"name": "TBD", "save_pct": 0.900, "gaa": 3.00, "games": 0, "is_backup": False, "confirmed": False}


# ══════════════════════════════════════════
#  7. ESPN — NHL INJURIES
# ══════════════════════════════════════════
def get_nhl_injuries() -> list:
    """Fetch all NHL injuries"""
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
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
    """Get injury impact for specific team (key players OUT)"""
    fwd_pos = {"LW", "RW", "C", "F"}
    def_pos = {"D", "LD", "RD"}
    team_inj = [i for i in injuries if team_name.lower() in i["team"].lower()]
    fwd_out = [i for i in team_inj if i["pos"].upper() in fwd_pos and "out" in i["status"].lower()]
    def_out = [i for i in team_inj if i["pos"].upper() in def_pos and "out" in i["status"].lower()]
    qtb = [i for i in team_inj if "questionable" in i["status"].lower() or "day-to-day" in i["status"].lower()]
    return {
        "forwards_out": fwd_out,
        "defense_out": def_out,
        "questionable": qtb,
        "fwd_out_count": len(fwd_out),
        "def_out_count": len(def_out),
        "qtb_count": len(qtb),
    }


# ══════════════════════════════════════════
#  8. ODDS API — MONEYLINE ODDS
# ══════════════════════════════════════════
def get_nhl_odds_events() -> list:
    """Fetch all NHL events from Odds API"""
    if not ODDS_API_KEY:
        return []
    url = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/events"
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
    url = f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/events/{odds_event_id}/odds"
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
#  9. PROBABILITY CALCULATION
# ══════════════════════════════════════════
def calculate_espn_win_prob(schedule: dict, team_stats: dict, side: str) -> float:
    """
    Estimate win probability from ESPN data.
    Combines: season win%, L10 form, home/away record
    """
    last10 = schedule.get("last10", [])
    wins_l10 = sum(1 for g in last10 if g["won"])
    form_l10 = wins_l10 / len(last10) if last10 else 0.5

    season_wp = team_stats.get("win_pct", 0.5)
    loc_wp = (team_stats.get("home_win_pct", 0.5) if side == "home"
              else team_stats.get("away_win_pct", 0.5))

    # Weighting: 40% season, 35% L10 form, 25% home/away record
    prob = (season_wp * 0.40) + (form_l10 * 0.35) + (loc_wp * 0.25)
    return round(min(0.95, max(0.05, prob)), 3)


# ══════════════════════════════════════════
#  10. MONEYLINE SCORING ENGINE
# ══════════════════════════════════════════
def score_moneyline(
    team_name: str,
    side: str,
    schedule: dict,
    team_stats: dict,
    goalie: dict,
    injury_impact: dict,
    odds_data: dict,
) -> dict:
    """
    Advanced MoneyLine confidence score (0-100)
    Factors: ESPN win prob vs implied, L10 form, goalie, 
             PP/PK, road trip, injuries, sharp money
    
    ULTRON v6.0 threshold: ≥55% BUY
    """
    last10 = schedule.get("last10", [])
    is_b2b = schedule.get("is_b2b", False)
    road_n = schedule.get("road_trip_game", 0)
    score = 50
    reasons = []
    penalties = []

    espn_prob = calculate_espn_win_prob(schedule, team_stats, side)
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

    # ── 3. HOME/AWAY RECORD ────────────────────────────────
    if side == "home":
        home_wp = team_stats.get("home_win_pct", 0.5)
        if home_wp >= 0.65:
            score += 10
            reasons.append(f"Strong at home ({home_wp:.0%})")
        elif home_wp <= 0.40:
            score -= 8
            penalties.append(f"Weak at home ({home_wp:.0%})")
    else:
        away_wp = team_stats.get("away_win_pct", 0.5)
        if away_wp >= 0.55:
            score += 10
            reasons.append(f"Solid on road ({away_wp:.0%})")
        elif away_wp <= 0.35:
            score -= 8
            penalties.append(f"Weak on road ({away_wp:.0%})")

    # ── 4. REGULATION WIN % (NHL SPECIFIC) ──────────────────
    reg_wp = team_stats.get("regulation_win_pct", 0)
    if reg_wp >= 0.55:
        score += 10
        reasons.append(f"Strong regulation wins ({reg_wp:.0%})")
    elif reg_wp <= 0.35:
        score -= 6
        penalties.append(f"Low regulation wins ({reg_wp:.0%})")

    # ── 5. POWER PLAY / PENALTY KILL ───────────────────────
    pp_pct = team_stats.get("power_play_pct", 0)
    pk_pct = team_stats.get("penalty_kill_pct", 0)
    if pp_pct >= 25:
        score += 6
        reasons.append(f"Excellent PP ({pp_pct:.1f}%)")
    if pk_pct >= 84:
        score += 6
        reasons.append(f"Strong PK ({pk_pct:.1f}%)")
    elif pk_pct <= 76:
        score -= 5
        penalties.append(f"Weak PK ({pk_pct:.1f}%)")

    # ── 6. STARTING GOALIE ────────────────────────────────
    if goalie["confirmed"]:
        if goalie["is_backup"]:
            score -= BACKUP_GOALIE_PENALTY
            penalties.append(f"Backup goalie: {goalie['name']}")
        else:
            sv = goalie["save_pct"]
            gaa = goalie["gaa"]
            if sv >= 0.920:
                score += 15
                reasons.append(f"Elite goalie: {goalie['name']} SV% {sv:.3f}")
            elif sv >= 0.910:
                score += 8
                reasons.append(f"Good goalie: {goalie['name']} SV% {sv:.3f}")
            elif sv <= 0.895:
                score -= 10
                penalties.append(f"Weak goalie: {goalie['name']} SV% {sv:.3f}")
            if gaa <= 2.50:
                score += 6
                reasons.append(f"Excellent GAA: {gaa:.2f}")
            elif gaa >= 3.20:
                score -= 6
                penalties.append(f"High GAA: {gaa:.2f}")
    else:
        score -= 6
        penalties.append("Starting goalie TBD")

    # ── 7. BACK-TO-BACK ───────────────────────────────────
    if is_b2b:
        score -= 10
        penalties.append("Back-to-back fatigue")

    # ── 8. ROAD TRIP ───────────────────────────────────────
    if road_n >= 3:
        score -= ROAD_TRIP_PENALTY
        penalties.append(f"Road trip — game #{road_n}")

    # ── 9. SHARP MONEY ────────────────────────────────────
    if odds_data.get("sharp_signal"):
        mv = odds_data.get("line_movement", 0)
        sharp_dir = odds_data.get("sharp_direction", "")
        if sharp_dir == side:
            score += SHARP_MONEY_WEIGHT
            reasons.append(f"Sharp money aligned (movement: {mv:+})")
        else:
            score -= 12
            penalties.append(f"Sharp money against us (movement: {mv:+})")

    # ── 10. INJURIES ──────────────────────────────────────
    fwd_out = injury_impact.get("fwd_out_count", 0)
    def_out = injury_impact.get("def_out_count", 0)
    if fwd_out >= 2:
        score -= 18
        names = ", ".join(i["player"] for i in injury_impact["forwards_out"][:2])
        penalties.append(f"Multiple forwards OUT: {names}")
    elif fwd_out == 1:
        score -= 9
        penalties.append(f"Key forward OUT: {injury_impact['forwards_out'][0]['player']}")
    if def_out >= 2:
        score -= 10
        penalties.append(f"{def_out} defensemen OUT")

    final = max(0, min(100, score))
    return {
        "team": team_name,
        "side": side,
        "espn_prob": espn_prob,
        "implied_prob": implied_prob,
        "edge": edge,
        "wins_l10": wins_l10,
        "goalie": goalie,
        "pp_pct": pp_pct,
        "pk_pct": pk_pct,
        "is_b2b": is_b2b,
        "road_trip": road_n,
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
#  11. TELEGRAM MESSAGE BUILDER
# ══════════════════════════════════════════
def build_telegram_message(r: dict, game: dict) -> str:
    """Build detailed Telegram message for MoneyLine pick"""
    # 🔒 Lock (haute confiance) | ⚡ Medium | 🎲 Risqué (voir seuils convenus)
    c = r["confidence"]
    emoji = "🔒" if c >= 75 else ("⚡" if c >= 60 else "🎲")
    side_str = "HOME" if r["side"] == "home" else "AWAY"
    b2b_str = " ⚠️ B2B" if r["is_b2b"] else ""
    road_str = f" 🛫 Road #{r['road_trip']}" if r["road_trip"] >= 2 else ""
    ml_str = f"{r['ml_odds']:+}" if r['ml_odds'] else "N/A"
    sharp_str = f"Yes ({r['sharp_dir'].upper()})" if r["sharp"] else "No"
    mv_str = f"{r['line_move']:+}"
    pos_text = "\n".join(f"  ✅ {x}" for x in r["reasons"]) or "  —"
    neg_text = "\n".join(f"  ⚠️ {x}" for x in r["penalties"]) or "  —"
    goalie_line = (f"🥅 Goalie: *{r['goalie']['name']}* SV% {r['goalie']['save_pct']:.3f}"
                   if r["goalie"]["confirmed"] else "🥅 Goalie: *TBD*")

    return (
        f"{emoji} *ULTRON — NHL MONEYLINE (Advanced)*\n"
        f"🏒 *{game['away_team']} @ {game['home_team']}*\n"
        f"🏟 {game['venue']}\n\n"
        f"🎯 Pick: *{r['team']} ({side_str})* @ *{ml_str}*{b2b_str}{road_str}\n"
        f"📊 Confidence: *{r['confidence']}/100*\n\n"
        f"📈 ESPN Prob: *{r['espn_prob']:.0%}* vs Implied: *{r['implied_prob']:.0%}*\n"
        f"💹 Edge: *{r['edge']:+.0%}*\n"
        f"📊 L10 Form: *{r['wins_l10']}/10*\n"
        f"{goalie_line}\n"
        f"⚡ PP: *{r['pp_pct']:.1f}%* | PK: *{r['pk_pct']:.1f}%*\n"
        f"💰 Sharp Money: *{sharp_str}* (movement: {mv_str})\n\n"
        f"✅ *Strengths:*\n{pos_text}\n\n"
        f"⚠️ *Concerns:*\n{neg_text}"
    )


# ══════════════════════════════════════════
#  12. MAIN ENTRY POINT
# ══════════════════════════════════════════
def run_nhl_moneyline_advanced() -> list:
    """
    Run comprehensive NHL MoneyLine analysis.
    Returns list of qualified picks (confidence ≥ threshold + positive edge)
    """
    logger.info("🏒 Starting NHL Advanced MoneyLine Analysis...")

    injuries = get_nhl_injuries()
    espn_games = get_nhl_games_today()
    odds_events = get_nhl_odds_events()

    if not espn_games:
        logger.info("ℹ️ No NHL games found today")
        return []

    qualified_picks = []

    for game in espn_games:
        logger.info(f"🔍 Analyzing: {game['away_team']} @ {game['home_team']}")

        home_schedule = get_team_schedule(game["home_abbr"])
        away_schedule = get_team_schedule(game["away_abbr"])
        home_stats = get_team_stats(game["home_abbr"])
        away_stats = get_team_stats(game["away_abbr"])
        home_goalie = get_starting_goalie(game["home_abbr"], game["game_id"])
        away_goalie = get_starting_goalie(game["away_abbr"], game["game_id"])
        home_injuries = get_team_injury_impact(game["home_team"], injuries)
        away_injuries = get_team_injury_impact(game["away_team"], injuries)

        odds_id = match_odds_event(game["home_abbr"], game["away_abbr"], odds_events)
        odds_data = get_moneyline_odds(odds_id) if odds_id else {}

        if not odds_data:
            logger.debug(f"  ⏭️  No MoneyLine odds available — skipping")
            continue

        if home_goalie["is_backup"]:
            logger.info(f"  ⚠️  Backup goalie HOME: {home_goalie['name']}")
        if away_goalie["is_backup"]:
            logger.info(f"  ⚠️  Backup goalie AWAY: {away_goalie['name']}")

        results = []
        for team_name, side, schedule, stats, goalie, inj in [
            (game["home_team"], "home", home_schedule, home_stats, home_goalie, home_injuries),
            (game["away_team"], "away", away_schedule, away_stats, away_goalie, away_injuries),
        ]:
            result = score_moneyline(team_name, side, schedule, stats, goalie, inj, odds_data)
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
    picks = run_nhl_moneyline_advanced()
    for p in picks:
        print(p["message"])
