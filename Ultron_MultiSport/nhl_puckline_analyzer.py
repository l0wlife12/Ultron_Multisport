import os
import requests
from datetime import datetime, timedelta

# ─────────────────────────────────────────
#  CLÉS — stockées sur Railway
# ─────────────────────────────────────────
ODDS_API_KEY   = os.environ.get("ODDS_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────
#  PARAMÈTRES AJUSTABLES
# ─────────────────────────────────────────
CONFIDENCE_THRESHOLD  = 68    # Puck line — seuil élevé
MIN_ATS_RATE          = 0.60  # ATS hit rate minimum sur L10
MIN_WIN_BY_2_PCT      = 0.40  # % victoires par 2+ buts minimum
SHARP_MONEY_WEIGHT    = 20    # Bonus si sharp money détecté
BACKUP_GOALIE_PENALTY = 20    # Pénalité si gardien backup confirmé
ROAD_TRIP_PENALTY     = 10    # Pénalité si 3e match ou + en déplacement


# ══════════════════════════════════════════
#  1.  TELEGRAM
# ══════════════════════════════════════════
def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        print(f"❌ Telegram error {resp.status_code}: {resp.text}")


# ══════════════════════════════════════════
#  2.  ESPN — MATCHS NHL DU JOUR
# ══════════════════════════════════════════
def get_nhl_games_today() -> list[dict]:
    today = datetime.now().strftime("%Y%m%d")
    url   = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={today}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN scoreboard error: {e}")
        return []

    games = []
    for event in resp.json().get("events", []):
        comp  = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue

        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])

        games.append({
            "game_id":   event.get("id"),
            "game_name": event.get("name", ""),
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_abbr": home.get("team", {}).get("abbreviation", ""),
            "away_abbr": away.get("team", {}).get("abbreviation", ""),
            "venue":     comp.get("venue", {}).get("fullName", "Unknown Arena"),
            "status":    event.get("status", {}).get("type", {}).get("name", ""),
        })
    return games


# ══════════════════════════════════════════
#  3.  ESPN — TEAM ID
# ══════════════════════════════════════════
def get_team_id(team_abbr: str) -> str | None:
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        for t in resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = t.get("team", {})
            if team.get("abbreviation", "").upper() == team_abbr.upper():
                return team.get("id")
    except Exception as e:
        print(f"⚠️  ESPN team id error: {e}")
    return None


# ══════════════════════════════════════════
#  4.  ESPN — SCHEDULE + ROAD TRIP DÉTECTION
# ══════════════════════════════════════════
def get_team_schedule(team_abbr: str) -> dict:
    """
    Retourne:
    - last10        : derniers 10 matchs complétés
    - road_trip_game: numéro du match consécutif en déplacement (0 si domicile)
    - is_b2b        : True si match hier
    """
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {"last10": [], "road_trip_game": 0, "is_b2b": False}

    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN schedule error: {e}")
        return {"last10": [], "road_trip_game": 0, "is_b2b": False}

    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    completed = []
    upcoming_away_streak = 0

    for event in resp.json().get("events", []):
        date_str = event.get("date", "")[:10]
        comp     = event.get("competitions", [{}])[0]
        status   = comp.get("status", {}).get("type", {})

        competitors = comp.get("competitors", [])
        team_data   = next((c for c in competitors
                            if c.get("team", {}).get("abbreviation", "").upper() == team_abbr.upper()), None)
        opp_data    = next((c for c in competitors
                            if c.get("team", {}).get("abbreviation", "").upper() != team_abbr.upper()), None)

        if not team_data or not opp_data:
            continue

        is_away = team_data.get("homeAway") == "away"

        if status.get("completed"):
            team_score = int(team_data.get("score", 0))
            opp_score  = int(opp_data.get("score",  0))
            completed.append({
                "date":        date_str,
                "goals_for":   team_score,
                "goals_against": opp_score,
                "goal_diff":   team_score - opp_score,
                "won":         team_data.get("winner", False),
                "away":        is_away,
                "regulation_win": team_data.get("winner", False) and abs(team_score - opp_score) > 0,
            })

    # Road trip: compte les matchs away consécutifs récents avant aujourd'hui
    road_streak = 0
    for g in reversed(completed):
        if g["away"]:
            road_streak += 1
        else:
            break

    is_b2b = bool(completed and completed[-1]["date"] == yesterday)

    return {
        "last10":         completed[-10:],
        "road_trip_game": road_streak,
        "is_b2b":         is_b2b,
    }


# ══════════════════════════════════════════
#  5.  ESPN — STATS ÉQUIPE NHL
# ══════════════════════════════════════════
def get_team_stats(team_abbr: str) -> dict:
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/statistics"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN team stats error: {e}")
        return {}

    stats = {}
    for cat in resp.json().get("results", {}).get("stats", {}).get("categories", []):
        for s in cat.get("stats", []):
            stats[s.get("name", "")] = s.get("value", 0)

    return {
        "goals_for_avg":    stats.get("avgGoalsFor",          0),
        "goals_against_avg": stats.get("avgGoalsAgainst",     0),
        "power_play_pct":   stats.get("powerPlayPct",         0),
        "penalty_kill_pct": stats.get("penaltyKillPct",       0),
        "shots_for_avg":    stats.get("avgShotsFor",          0),
        "shots_against_avg": stats.get("avgShotsAgainst",     0),
        "win_pct":          stats.get("winPct",               0),
        "home_win_pct":     stats.get("homeWinPct",           0),
        "away_win_pct":     stats.get("awayWinPct",           0),
        "regulation_win_pct": stats.get("regulationWinPct",   0),
        "save_pct":         stats.get("savePct",              0),
    }


# ══════════════════════════════════════════
#  6.  ESPN — GARDIEN PARTANT
# ══════════════════════════════════════════
def get_starting_goalie(team_abbr: str, game_id: str) -> dict:
    """
    Récupère le gardien partant depuis le game summary ESPN.
    Retourne ses stats et si c'est le gardien #1 ou backup.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={game_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Cherche dans les probables goalies
        for entry in data.get("probables", []):
            abbr = entry.get("team", {}).get("abbreviation", "")
            if abbr.upper() != team_abbr.upper():
                continue

            athlete = entry.get("athlete", {})
            stats   = entry.get("statistics", [])

            save_pct  = next((float(s.get("value", 0)) for s in stats if s.get("name") == "savePct"),  0.900)
            gaa       = next((float(s.get("value", 0)) for s in stats if s.get("name") == "goalsAgainstAvg"), 3.00)
            wins      = next((int(s.get("value",   0)) for s in stats if s.get("name") == "wins"),     0)
            games     = next((int(s.get("value",   1)) for s in stats if s.get("name") == "gamesPlayed"), 1)

            # Considéré backup si < 15 matchs joués cette saison
            is_backup = games < 15

            return {
                "name":      athlete.get("displayName", "TBD"),
                "save_pct":  save_pct,
                "gaa":       gaa,
                "wins":      wins,
                "games":     games,
                "is_backup": is_backup,
                "confirmed": True,
            }

    except Exception as e:
        print(f"⚠️  ESPN goalie error: {e}")

    return {
        "name":      "TBD",
        "save_pct":  0.900,
        "gaa":       3.00,
        "wins":      0,
        "games":     0,
        "is_backup": False,
        "confirmed": False,
    }


# ══════════════════════════════════════════
#  7.  ESPN — BLESSURES NHL
# ══════════════════════════════════════════
def get_nhl_injuries() -> list[dict]:
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN injuries error: {e}")
        return []

    injuries = []
    for team in resp.json().get("injuries", []):
        team_name = team.get("team", {}).get("displayName", "")
        for p in team.get("injuries", []):
            injuries.append({
                "team":   team_name,
                "player": p.get("athlete", {}).get("displayName", ""),
                "status": p.get("status", ""),
                "pos":    p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
            })
    return injuries


def get_team_injury_impact(team_name: str, injuries: list) -> dict:
    """
    Évalue l'impact des blessures sur le puck line.
    Top-6 forwards et top-4 D sont les plus critiques.
    """
    forward_positions = {"LW", "RW", "C", "F"}
    defense_positions = {"D", "LD", "RD"}

    team_injuries = [i for i in injuries if team_name.lower() in i["team"].lower()]

    forwards_out = [i for i in team_injuries
                    if i["pos"].upper() in forward_positions
                    and "out" in i["status"].lower()]
    defense_out  = [i for i in team_injuries
                    if i["pos"].upper() in defense_positions
                    and "out" in i["status"].lower()]
    questionable = [i for i in team_injuries
                    if "questionable" in i["status"].lower()
                    or "day-to-day" in i["status"].lower()]

    return {
        "forwards_out":   forwards_out,
        "defense_out":    defense_out,
        "questionable":   questionable,
        "fwd_out_count":  len(forwards_out),
        "def_out_count":  len(defense_out),
        "qtb_count":      len(questionable),
    }


# ══════════════════════════════════════════
#  8.  ODDS API — PUCK LINE + SHARP MONEY
# ══════════════════════════════════════════
def get_nhl_odds_events() -> list[dict]:
    url = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/events"
    try:
        resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️  Odds API NHL events error: {e}")
        return []


def get_puck_line_odds(odds_event_id: str) -> dict:
    """
    Retourne la puck line actuelle (±1.5), mouvement, et signal sharp money.
    Récupère aussi la cote moneyline pour comparer l'implied probability.
    """
    url = f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/events/{odds_event_id}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "spreads,h2h",
        "oddsFormat": "american",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  Odds API puck line error: {e}")
        return {}

    data       = resp.json()
    bookmakers = data.get("bookmakers", [])
    if not bookmakers:
        return {}

    home_team     = data.get("home_team", "")
    home_pl_pts   = []   # puck line points collectés sur tous les books
    opening_home  = None
    home_ml_odds  = []   # moneyline pour implied prob

    for bm in bookmakers:
        for market in bm.get("markets", []):
            key = market.get("key")

            if key == "spreads":
                for outcome in market.get("outcomes", []):
                    pt = outcome.get("point", 0)
                    if outcome.get("name") == home_team:
                        home_pl_pts.append(pt)
                        if opening_home is None:
                            opening_home = pt

            if key == "h2h":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == home_team:
                        home_ml_odds.append(outcome.get("price", 0))

    if not home_pl_pts:
        return {}

    current_home = home_pl_pts[-1]
    opening_home = opening_home or current_home
    movement     = round(current_home - opening_home, 1)
    sharp_signal = abs(movement) >= 0.5

    # Implied probability depuis la moneyline
    implied_prob_home = 0.50
    if home_ml_odds:
        avg_ml = sum(home_ml_odds) / len(home_ml_odds)
        if avg_ml < 0:
            implied_prob_home = abs(avg_ml) / (abs(avg_ml) + 100)
        else:
            implied_prob_home = 100 / (avg_ml + 100)

    return {
        "home_spread":        current_home,        # ex: -1.5
        "away_spread":        -current_home,        # ex: +1.5
        "opening_spread":     opening_home,
        "line_movement":      movement,
        "sharp_signal":       sharp_signal,
        "sharp_direction":    "home" if movement < 0 else "away",
        "implied_prob_home":  round(implied_prob_home, 3),
        "implied_prob_away":  round(1 - implied_prob_home, 3),
        "consensus_books":    len(bookmakers),
    }


def match_odds_event(home_abbr: str, away_abbr: str, odds_events: list) -> str | None:
    for event in odds_events:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if home_abbr.lower() in h or away_abbr.lower() in a:
            return event.get("id")
    return None


# ══════════════════════════════════════════
#  9.  CALCUL ATS PUCK LINE SUR L10
# ══════════════════════════════════════════
def calculate_puck_line_ats(last10: list[dict], spread: float) -> dict:
    """
    NHL: spread est toujours ±1.5.
    favori  (-1.5): couvre si goal_diff > 1  (gagne par 2+)
    underdog(+1.5): couvre si goal_diff > -2 (perd par 1 ou moins, ou gagne)
    """
    if not last10:
        return {
            "ats_wins": 0, "ats_rate": 0.0, "avg_diff": 0.0,
            "win_by_2_pct": 0.0, "regulation_win_pct": 0.0,
            "empty_net_games": 0,
        }

    ats_wins        = 0
    win_by_2        = 0
    regulation_wins = 0
    empty_net_games = 0   # Victoires par 2+ buts peuvent inclure empty nets

    diffs = []
    for g in last10:
        diff = g["goal_diff"]
        diffs.append(diff)

        covered = diff > 1 if spread < 0 else diff > -2
        if covered:
            ats_wins += 1
        if diff >= 2:
            win_by_2 += 1
            if diff >= 2:
                empty_net_games += 1   # Proxy: victoires nettes
        if g.get("regulation_win"):
            regulation_wins += 1

    n = len(last10)
    return {
        "ats_wins":           ats_wins,
        "ats_rate":           round(ats_wins / n, 2),
        "avg_diff":           round(sum(diffs) / n, 2),
        "win_by_2_pct":       round(win_by_2 / n, 2),
        "regulation_win_pct": round(regulation_wins / n, 2),
        "empty_net_games":    empty_net_games,
    }


# ══════════════════════════════════════════
#  10.  SCORE DE CONFIANCE PUCK LINE
# ══════════════════════════════════════════
def score_puck_line(
    team_name:     str,
    side:          str,        # "home" ou "away"
    spread:        float,      # -1.5 ou +1.5
    schedule:      dict,
    team_stats:    dict,
    goalie:        dict,
    injury_impact: dict,
    odds_data:     dict,
) -> dict:

    last10  = schedule.get("last10", [])
    is_b2b  = schedule.get("is_b2b", False)
    road_n  = schedule.get("road_trip_game", 0)
    score   = 50
    reasons = []
    penalties = []

    ats = calculate_puck_line_ats(last10, spread)

    # ── Back-to-back ──────────────────────
    if is_b2b:
        score -= 12
        penalties.append("Back-to-back — risque de fatigue")

    # ── Road trip (3e match ou +) ─────────
    if road_n >= 3:
        score -= ROAD_TRIP_PENALTY
        penalties.append(f"Road trip — {road_n}e match consécutif à l'extérieur")

    # ── ATS record L10 ────────────────────
    if ats["ats_rate"] >= 0.70:
        score += 20
        reasons.append(f"Excellent ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")
    elif ats["ats_rate"] >= MIN_ATS_RATE:
        score += 12
        reasons.append(f"Bon ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")
    elif ats["ats_rate"] <= 0.40:
        score -= 15
        penalties.append(f"Mauvais ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")

    # ── Win by 2+ buts % ──────────────────
    # Pour -1.5 (favori), c'est critique
    if spread < 0:
        if ats["win_by_2_pct"] >= 0.55:
            score += 15
            reasons.append(f"Gagne par 2+ buts souvent ({ats['win_by_2_pct']:.0%})")
        elif ats["win_by_2_pct"] < MIN_WIN_BY_2_PCT:
            score -= 15
            penalties.append(f"Rarement +2 buts d'écart ({ats['win_by_2_pct']:.0%}) — -1.5 risqué")

    # ── Regulation win % ──────────────────
    reg_wp = ats["regulation_win_pct"]
    if reg_wp >= 0.55:
        score += 10
        reasons.append(f"Gagne souvent en temps règlementaire ({reg_wp:.0%})")
    elif reg_wp <= 0.30:
        score -= 8
        penalties.append(f"Peu de victoires en règlementaire ({reg_wp:.0%})")

    # ── Goal differential moyen ───────────
    if ats["avg_diff"] >= 1.5:
        score += 12
        reasons.append(f"Goal diff moyen fort (+{ats['avg_diff']:.1f} buts)")
    elif ats["avg_diff"] >= 0.5:
        score += 6
        reasons.append(f"Goal diff moyen positif (+{ats['avg_diff']:.1f} buts)")
    elif ats["avg_diff"] < 0:
        score -= 10
        penalties.append(f"Goal diff moyen négatif ({ats['avg_diff']:.1f} buts)")

    # ── Power play offensif ───────────────
    pp_pct = team_stats.get("power_play_pct", 0)
    if pp_pct >= 25:
        score += 8
        reasons.append(f"Power play excellent ({pp_pct:.1f}%)")
    elif pp_pct >= 20:
        score += 4
        reasons.append(f"Bon power play ({pp_pct:.1f}%)")
    elif pp_pct <= 14:
        score -= 5
        penalties.append(f"Power play faible ({pp_pct:.1f}%)")

    # ── Penalty kill défensif ─────────────
    pk_pct = team_stats.get("penalty_kill_pct", 0)
    if pk_pct >= 84:
        score += 8
        reasons.append(f"Penalty kill solide ({pk_pct:.1f}%)")
    elif pk_pct <= 76:
        score -= 6
        penalties.append(f"Penalty kill faible ({pk_pct:.1f}%)")

    # ── Gardien partant ───────────────────
    if goalie["confirmed"]:
        if goalie["is_backup"]:
            score -= BACKUP_GOALIE_PENALTY
            penalties.append(f"⚠️ Gardien backup: {goalie['name']} ({goalie['games']} matchs)")
        else:
            sv  = goalie["save_pct"]
            gaa = goalie["gaa"]

            if sv >= 0.920:
                score += 18
                reasons.append(f"Gardien élite: {goalie['name']} SV% {sv:.3f} | GAA {gaa:.2f}")
            elif sv >= 0.910:
                score += 10
                reasons.append(f"Bon gardien: {goalie['name']} SV% {sv:.3f} | GAA {gaa:.2f}")
            elif sv <= 0.895:
                score -= 12
                penalties.append(f"Gardien faible: {goalie['name']} SV% {sv:.3f} | GAA {gaa:.2f}")

            if gaa <= 2.50:
                score += 8
                reasons.append(f"GAA excellent: {gaa:.2f}")
            elif gaa >= 3.20:
                score -= 8
                penalties.append(f"GAA élevé: {gaa:.2f}")
    else:
        score -= 8
        penalties.append("Gardien partant non confirmé (TBD)")

    # ── Sharp money ──────────────────────
    if odds_data.get("sharp_signal"):
        mv        = odds_data.get("line_movement", 0)
        sharp_dir = odds_data.get("sharp_direction", "")
        if sharp_dir == side:
            score += SHARP_MONEY_WEIGHT
            reasons.append(f"Sharp money dans notre sens (mvt: {mv:+.1f})")
        else:
            score -= 12
            penalties.append(f"Sharp money contre nous (mvt: {mv:+.1f})")

    # ── Implied probability edge ──────────
    implied = (odds_data.get("implied_prob_home", 0.5) if side == "home"
               else odds_data.get("implied_prob_away", 0.5))
    # Pour le puck line -1.5, on estime que gagner par 2+ arrive ~55% si implied ML > 65%
    if side == "home" and spread < 0 and implied >= 0.65:
        score += 8
        reasons.append(f"Équipe fortement favorite (implied {implied:.0%})")
    elif implied <= 0.40:
        score -= 8
        penalties.append(f"Pas assez favori pour couvrir -1.5 (implied {implied:.0%})")

    # ── Blessures ────────────────────────
    fwd_out = injury_impact.get("fwd_out_count", 0)
    def_out = injury_impact.get("def_out_count", 0)
    qtb     = injury_impact.get("qtb_count", 0)

    if fwd_out >= 2:
        score -= 18
        names = ", ".join(i["player"] for i in injury_impact["forwards_out"][:2])
        penalties.append(f"Forwards clés OUT: {names}")
    elif fwd_out == 1:
        score -= 10
        penalties.append(f"Forward clé OUT: {injury_impact['forwards_out'][0]['player']}")

    if def_out >= 2:
        score -= 12
        names = ", ".join(i["player"] for i in injury_impact["defense_out"][:2])
        penalties.append(f"Défenseurs clés OUT: {names}")
    elif def_out == 1:
        score -= 6
        penalties.append(f"Défenseur clé OUT: {injury_impact['defense_out'][0]['player']}")

    if qtb >= 2:
        score -= 6
        penalties.append(f"{qtb} joueurs incertains (Questionable/DTD)")

    final = max(0, min(100, score))
    return {
        "team":           team_name,
        "side":           side,
        "spread":         spread,
        "ats_record":     f"{ats['ats_wins']}/10",
        "ats_rate":       ats["ats_rate"],
        "avg_diff":       ats["avg_diff"],
        "win_by_2_pct":   ats["win_by_2_pct"],
        "reg_win_pct":    ats["regulation_win_pct"],
        "goalie":         goalie,
        "pp_pct":         team_stats.get("power_play_pct", 0),
        "pk_pct":         team_stats.get("penalty_kill_pct", 0),
        "is_b2b":         is_b2b,
        "road_trip":      road_n,
        "line_move":      odds_data.get("line_movement", 0),
        "sharp":          odds_data.get("sharp_signal", False),
        "sharp_dir":      odds_data.get("sharp_direction", ""),
        "confidence":     final,
        "reasons":        reasons,
        "penalties":      penalties,
        "send":           final >= CONFIDENCE_THRESHOLD,
    }


# ══════════════════════════════════════════
#  11.  MESSAGE TELEGRAM
# ══════════════════════════════════════════
def build_telegram_message(r: dict, game: dict) -> str:
    # 🔒 Lock (haute confiance) | ⚡ Medium | 🎲 Risqué (voir seuils convenus)
    c = r["confidence"]
    emoji      = "🔒" if c >= 75 else ("⚡" if c >= 60 else "🎲")
    spread_str = f"{r['spread']:+.1f}"
    side_str   = "DOMICILE" if r["side"] == "home" else "EXTÉRIEUR"
    b2b_str    = " ⚠️ B2B" if r["is_b2b"] else ""
    road_str   = f" 🛫 Road trip #{r['road_trip']}" if r["road_trip"] >= 2 else ""
    sharp_str  = f"Oui ({r['sharp_dir'].upper()})" if r["sharp"] else "Non"
    mv_str     = f"{r['line_move']:+.1f}"
    pos_text   = "\n".join(f"  ✅ {x}" for x in r["reasons"])   or "  —"
    neg_text   = "\n".join(f"  ⚠️ {x}" for x in r["penalties"]) or "  —"

    goalie_line = (
        f"🥅 Gardien: *{r['goalie']['name']}* "
        f"(SV% {r['goalie']['save_pct']:.3f} | GAA {r['goalie']['gaa']:.2f})"
        if r["goalie"]["confirmed"]
        else "🥅 Gardien: *TBD*"
    )

    return (
        f"{emoji} *ULTRON — NHL PUCK LINE*\n"
        f"🏒 *{game['away_team']} @ {game['home_team']}*\n"
        f"🏟 {game['venue']}\n\n"
        f"🎯 Pick: *{r['team']} {spread_str} ({side_str})*{b2b_str}{road_str}\n"
        f"📊 Confiance: *{r['confidence']}/100*\n\n"
        f"📈 ATS L10: *{r['ats_record']}* ({r['ats_rate']:.0%})\n"
        f"📈 Goal diff moyen: *{r['avg_diff']:+.2f} buts*\n"
        f"📈 Win by 2+ buts: *{r['win_by_2_pct']:.0%}*\n"
        f"📈 Victoires règlementaire: *{r['reg_win_pct']:.0%}*\n"
        f"{goalie_line}\n"
        f"⚡ PP: *{r['pp_pct']:.1f}%* | PK: *{r['pk_pct']:.1f}%*\n"
        f"💰 Sharp money: *{sharp_str}* (mouvement: {mv_str})\n\n"
        f"✅ *Points positifs:*\n{pos_text}\n\n"
        f"⚠️ *Points négatifs:*\n{neg_text}"
    )


# ══════════════════════════════════════════
#  12.  POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════
def run_nhl_puckline() -> None:
    print("🏒 Ultron — Analyse Puck Line NHL...")

    injuries    = get_nhl_injuries()
    espn_games  = get_nhl_games_today()
    odds_events = get_nhl_odds_events()

    if not espn_games:
        print("Aucun match NHL trouvé aujourd'hui.")
        return

    for game in espn_games:
        print(f"\n🔍 Analyse: {game['away_team']} @ {game['home_team']}")

        # Données ESPN
        home_schedule = get_team_schedule(game["home_abbr"])
        away_schedule = get_team_schedule(game["away_abbr"])
        home_stats    = get_team_stats(game["home_abbr"])
        away_stats    = get_team_stats(game["away_abbr"])
        home_goalie   = get_starting_goalie(game["home_abbr"], game["game_id"])
        away_goalie   = get_starting_goalie(game["away_abbr"], game["game_id"])
        home_injuries = get_team_injury_impact(game["home_team"], injuries)
        away_injuries = get_team_injury_impact(game["away_team"], injuries)

        # Données Odds API
        odds_id   = match_odds_event(game["home_abbr"], game["away_abbr"], odds_events)
        odds_data = get_puck_line_odds(odds_id) if odds_id else {}

        if not odds_data:
            print(f"  ⏭️  Pas de cote puck line disponible — skip")
            continue

        home_spread = odds_data.get("home_spread", -1.5)
        away_spread = odds_data.get("away_spread",  1.5)

        # Alerte si gardien backup détecté
        if home_goalie["is_backup"]:
            print(f"  ⚠️  Gardien backup HOME: {home_goalie['name']}")
        if away_goalie["is_backup"]:
            print(f"  ⚠️  Gardien backup AWAY: {away_goalie['name']}")

        # Score les deux côtés
        results = []
        for team_name, side, spread, schedule, stats, goalie, inj in [
            (game["home_team"], "home", home_spread, home_schedule, home_stats, home_goalie, home_injuries),
            (game["away_team"], "away", away_spread, away_schedule, away_stats, away_goalie, away_injuries),
        ]:
            result = score_puck_line(
                team_name, side, spread,
                schedule, stats, goalie, inj, odds_data
            )
            b2b_tag  = " [B2B]"           if result["is_b2b"]     else ""
            road_tag = f" [Road #{result['road_trip']}]" if result["road_trip"] >= 2 else ""
            print(f"  {team_name} {spread:+.1f} → {result['confidence']}/100{b2b_tag}{road_tag}")
            results.append(result)

        # Envoie uniquement le meilleur pick si ≥ seuil
        best = max(results, key=lambda r: r["confidence"])
        if best["send"]:
            msg = build_telegram_message(best, game)
            send_telegram(msg)
            print(f"  ✅ Pick envoyé: {best['team']} {best['spread']:+.1f} — {best['confidence']}/100")
        else:
            top = max(r["confidence"] for r in results)
            print(f"  ❌ Confiance trop basse ({top}/100) — pick ignoré")


if __name__ == "__main__":
    run_nhl_puckline()
