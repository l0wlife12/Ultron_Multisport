import os
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  CLÉS — stockées sur Railway
# ─────────────────────────────────────────
ODDS_API_KEY   = os.environ.get("ODDS_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────
#  PARAMÈTRES AJUSTABLES
# ─────────────────────────────────────────
CONFIDENCE_THRESHOLD = 68    # Spread NBA — seuil élevé
MIN_ATS_RATE         = 0.60  # ATS hit rate minimum sur L10
MIN_MARGIN_AVG       = 4.0   # Point diff moyen minimum pour couvrir -3.5+
SHARP_MONEY_WEIGHT   = 20    # Bonus si sharp money détecté
B2B_PENALTY          = 15    # Pénalité back-to-back


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
#  2.  ESPN — MATCHS NBA DU JOUR
# ══════════════════════════════════════════
def get_nba_games_today() -> list[dict]:
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN scoreboard error: {e}")
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
#  3.  ESPN — SCHEDULE & BACK-TO-BACK
# ══════════════════════════════════════════
def get_team_id(team_abbr: str) -> str | None:
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
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


def get_team_schedule(team_abbr: str) -> dict:
    """
    Retourne:
    - last10: liste des 10 derniers matchs (score, opponent, home/away, won)
    - is_b2b: True si le match d'aujourd'hui est un back-to-back
    """
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {"last10": [], "is_b2b": False}

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN schedule error: {e}")
        return {"last10": [], "is_b2b": False}

    today_str  = datetime.now().strftime("%Y-%m-%d")
    completed  = []
    upcoming   = []

    for event in resp.json().get("events", []):
        date_str = event.get("date", "")[:10]
        comp     = event.get("competitions", [{}])[0]
        status   = comp.get("status", {}).get("type", {})

        if status.get("completed"):
            competitors = comp.get("competitors", [])
            team_data   = next((c for c in competitors
                                if c.get("team", {}).get("abbreviation", "").upper() == team_abbr.upper()), None)
            opp_data    = next((c for c in competitors
                                if c.get("team", {}).get("abbreviation", "").upper() != team_abbr.upper()), None)
            if team_data and opp_data:
                team_score = int(team_data.get("score", 0))
                opp_score  = int(opp_data.get("score", 0))
                completed.append({
                    "date":       date_str,
                    "pts_scored": team_score,
                    "pts_allowed": opp_score,
                    "pt_diff":    team_score - opp_score,
                    "won":        team_data.get("winner", False),
                    "home":       team_data.get("homeAway") == "home",
                })
        elif date_str >= today_str:
            upcoming.append(date_str)

    # Back-to-back: dernier match complété était hier
    is_b2b = False
    if completed:
        last_date = completed[-1]["date"]
        yesterday = (datetime.now().__class__.today() - __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
        is_b2b = last_date == yesterday

    return {"last10": completed[-10:], "is_b2b": is_b2b}


# ══════════════════════════════════════════
#  4.  ESPN — STATS AVANCÉES ÉQUIPE
# ══════════════════════════════════════════
def get_team_advanced_stats(team_abbr: str) -> dict:
    """Retourne net rating, pace, offensive/defensive rating."""
    team_id = get_team_id(team_abbr)
    if not team_id:
        return {}

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/statistics"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  ESPN advanced stats error: {e}")
        return {}

    stats = {}
    for cat in resp.json().get("results", {}).get("stats", {}).get("categories", []):
        for s in cat.get("stats", []):
            stats[s.get("name", "")] = s.get("value", 0)

    return {
        "off_rating":   stats.get("offensiveRating",  0),
        "def_rating":   stats.get("defensiveRating",  0),
        "net_rating":   stats.get("netRating",        0),
        "pace":         stats.get("pace",             0),
        "pts_avg":      stats.get("avgPoints",        0),
        "pts_allowed":  stats.get("avgPointsAllowed", 0),
        "win_pct":      stats.get("winPct",           0),
        "home_win_pct": stats.get("homeWinPct",       0),
        "away_win_pct": stats.get("awayWinPct",       0),
        "bench_pts":    stats.get("benchPoints",      0),
    }


# ══════════════════════════════════════════
#  5.  ESPN — BLESSURES NBA
# ══════════════════════════════════════════
def get_nba_injuries() -> list[dict]:
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
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
            status = p.get("status", "")
            injuries.append({
                "team":   team_name,
                "player": p.get("athlete", {}).get("displayName", ""),
                "status": status,
                "pos":    p.get("athlete", {}).get("position", {}).get("abbreviation", ""),
            })
    return injuries


def get_team_injury_impact(team_name: str, injuries: list) -> dict:
    """
    Calcule l'impact des blessures sur le spread.
    Les stars (G, F) out ont un impact direct sur la marge de victoire.
    """
    key_positions = {"PG", "SG", "SF", "PF", "C", "G", "F"}
    team_injuries = [
        i for i in injuries
        if team_name.lower() in i["team"].lower()
        and i["pos"].upper() in key_positions
    ]

    stars_out          = [i for i in team_injuries if "out" in i["status"].lower()]
    stars_questionable = [i for i in team_injuries if "questionable" in i["status"].lower()
                                                    or "day-to-day" in i["status"].lower()]

    return {
        "stars_out":          stars_out,
        "stars_questionable": stars_questionable,
        "out_count":          len(stars_out),
        "questionable_count": len(stars_questionable),
    }


# ══════════════════════════════════════════
#  6.  ODDS API — SPREAD NBA + SHARP MONEY
# ══════════════════════════════════════════
def get_nba_odds_events() -> list[dict]:
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    try:
        resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️  Odds API events error: {e}")
        return []


def get_nba_spread_odds(odds_event_id: str) -> dict:
    """
    Retourne le spread actuel, mouvement, et signal sharp money.
    """
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{odds_event_id}/odds"
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
        print(f"⚠️  Odds API spread error: {e}")
        return {}

    data       = resp.json()
    bookmakers = data.get("bookmakers", [])
    if not bookmakers:
        return {}

    home_team      = data.get("home_team", "")
    all_home_pts   = []
    all_away_pts   = []

    for bm in bookmakers:
        for market in bm.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                pt = outcome.get("point", 0)
                if outcome.get("name") == home_team:
                    all_home_pts.append(pt)
                else:
                    all_away_pts.append(pt)

    if not all_home_pts:
        return {}

    opening = all_home_pts[0]
    current = all_home_pts[-1]
    movement = round(current - opening, 1)

    # Reverse line movement = sharp signal
    # Ex: public bet home mais ligne monte pour away = sharp sur away
    sharp_signal    = abs(movement) >= 0.5
    sharp_direction = "home" if movement < 0 else "away"  # ligne monte pour away = sharp away

    return {
        "home_spread":     current,
        "away_spread":     -current,
        "opening_spread":  opening,
        "line_movement":   movement,
        "sharp_signal":    sharp_signal,
        "sharp_direction": sharp_direction,
        "consensus_books": len(bookmakers),
    }


def match_odds_event(home_abbr: str, away_abbr: str, odds_events: list) -> str | None:
    for event in odds_events:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if home_abbr.lower() in h or away_abbr.lower() in a:
            return event.get("id")
    return None


# ══════════════════════════════════════════
#  7.  CALCUL ATS SUR L10
# ══════════════════════════════════════════
def calculate_ats(last10: list[dict], spread: float) -> dict:
    """
    spread: négatif si favori (ex: -5.5), positif si underdog (+5.5)
    """
    if not last10:
        return {"ats_wins": 0, "ats_rate": 0.0, "avg_diff": 0.0,
                "blowout_pct": 0.0, "close_pct": 0.0}

    ats_wins = 0
    blowouts = 0
    close    = 0
    diffs    = []

    for g in last10:
        diff = g["pt_diff"]
        diffs.append(diff)

        # Couvre si diff > |spread| (favori) ou > -spread (underdog)
        covered = diff > abs(spread) if spread < 0 else diff > -spread
        if covered:
            ats_wins += 1
        if abs(diff) >= 15:
            blowouts += 1
        if abs(diff) <= 5:
            close += 1

    n = len(last10)
    return {
        "ats_wins":   ats_wins,
        "ats_rate":   round(ats_wins / n, 2),
        "avg_diff":   round(sum(diffs) / n, 1),
        "blowout_pct": round(blowouts / n, 2),
        "close_pct":   round(close / n, 2),
    }


# ══════════════════════════════════════════
#  8.  SCORE DE CONFIANCE SPREAD NBA
# ══════════════════════════════════════════
def score_nba_spread(
    team_name: str,
    side: str,             # "home" ou "away"
    spread: float,         # ex: -5.5 ou +5.5
    schedule: dict,
    adv_stats: dict,
    injury_impact: dict,
    odds_data: dict,
) -> dict:

    last10   = schedule.get("last10", [])
    is_b2b   = schedule.get("is_b2b", False)
    score    = 50
    reasons  = []
    penalties = []

    ats = calculate_ats(last10, spread)

    # ── Back-to-back (priorité absolue) ──
    if is_b2b:
        score -= B2B_PENALTY
        penalties.append(f"Back-to-back — fatigue significative (-{B2B_PENALTY}pts)")

    # ── ATS record L10 ───────────────────
    if ats["ats_rate"] >= 0.70:
        score += 20
        reasons.append(f"Excellent ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")
    elif ats["ats_rate"] >= MIN_ATS_RATE:
        score += 12
        reasons.append(f"Bon ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")
    elif ats["ats_rate"] <= 0.40:
        score -= 15
        penalties.append(f"Mauvais ATS L10: {ats['ats_wins']}/10 ({ats['ats_rate']:.0%})")

    # ── Point differential moyen ─────────
    if ats["avg_diff"] >= 8.0:
        score += 15
        reasons.append(f"Point diff moyen dominant (+{ats['avg_diff']} pts)")
    elif ats["avg_diff"] >= MIN_MARGIN_AVG:
        score += 8
        reasons.append(f"Point diff moyen positif (+{ats['avg_diff']} pts)")
    elif ats["avg_diff"] < 0:
        score -= 12
        penalties.append(f"Point diff moyen négatif ({ats['avg_diff']} pts)")

    # ── Blowout % (bon si favori) ─────────
    if spread < 0 and ats["blowout_pct"] >= 0.40:
        score += 10
        reasons.append(f"Gagne souvent par large écart ({ats['blowout_pct']:.0%} de blowouts)")
    elif spread < 0 and ats["close_pct"] >= 0.50:
        score -= 10
        penalties.append(f"Beaucoup de matchs serrés ({ats['close_pct']:.0%}) — risque de ne pas couvrir")

    # ── Net rating (stats avancées) ───────
    net = adv_stats.get("net_rating", 0)
    if net >= 8:
        score += 12
        reasons.append(f"Net rating excellent: +{net:.1f}")
    elif net >= 4:
        score += 6
        reasons.append(f"Net rating positif: +{net:.1f}")
    elif net <= -4:
        score -= 10
        penalties.append(f"Net rating négatif: {net:.1f}")

    # ── Home/Away advantage ───────────────
    if side == "home":
        home_wp = adv_stats.get("home_win_pct", 0)
        if home_wp >= 0.65:
            score += 8
            reasons.append(f"Très fort à domicile ({home_wp:.0%} wins home)")
        elif home_wp <= 0.40:
            score -= 8
            penalties.append(f"Faible à domicile ({home_wp:.0%} wins home)")
    else:
        away_wp = adv_stats.get("away_win_pct", 0)
        if away_wp >= 0.55:
            score += 8
            reasons.append(f"Solide en déplacement ({away_wp:.0%} wins away)")
        elif away_wp <= 0.35:
            score -= 8
            penalties.append(f"Faible en déplacement ({away_wp:.0%} wins away)")

    # ── Bench points (important si stars blessées) ──
    bench = adv_stats.get("bench_pts", 0)
    if bench >= 45:
        score += 6
        reasons.append(f"Bon banc ({bench:.0f} pts/match)")
    elif bench <= 28:
        score -= 5
        penalties.append(f"Banc faible ({bench:.0f} pts/match)")

    # ── Sharp money ──────────────────────
    if odds_data.get("sharp_signal"):
        mv  = odds_data.get("line_movement", 0)
        sharp_dir = odds_data.get("sharp_direction", "")
        if sharp_dir == side:
            score += SHARP_MONEY_WEIGHT
            reasons.append(f"Sharp money dans notre sens (mvt: {mv:+.1f})")
        else:
            score -= 12
            penalties.append(f"Sharp money contre nous (mvt: {mv:+.1f})")

    # ── Blessures ────────────────────────
    out_count = injury_impact.get("out_count", 0)
    qtb_count = injury_impact.get("questionable_count", 0)
    stars_out = injury_impact.get("stars_out", [])

    if out_count >= 2:
        score -= 22
        names = ", ".join(i["player"] for i in stars_out[:2])
        penalties.append(f"Stars OUT: {names}")
    elif out_count == 1:
        score -= 12
        penalties.append(f"Star OUT: {stars_out[0]['player']}")
    if qtb_count >= 2:
        score -= 8
        penalties.append(f"{qtb_count} joueurs incertains (Questionable/DTD)")

    final = max(0, min(100, score))
    return {
        "team":       team_name,
        "side":       side,
        "spread":     spread,
        "ats_record": f"{ats['ats_wins']}/10",
        "ats_rate":   ats["ats_rate"],
        "avg_diff":   ats["avg_diff"],
        "blowout_pct": ats["blowout_pct"],
        "close_pct":   ats["close_pct"],
        "net_rating":  adv_stats.get("net_rating", 0),
        "is_b2b":      is_b2b,
        "line_move":   odds_data.get("line_movement", 0),
        "sharp":       odds_data.get("sharp_signal", False),
        "sharp_dir":   odds_data.get("sharp_direction", ""),
        "confidence":  final,
        "reasons":     reasons,
        "penalties":   penalties,
        "send":        final >= CONFIDENCE_THRESHOLD,
    }


# ══════════════════════════════════════════
#  9.  MESSAGE TELEGRAM
# ══════════════════════════════════════════
def build_telegram_message(r: dict, game: dict) -> str:
    emoji      = "🔥" if r["confidence"] >= 80 else "✅"
    spread_str = f"{r['spread']:+.1f}"
    side_str   = "DOMICILE" if r["side"] == "home" else "EXTÉRIEUR"
    b2b_str    = " ⚠️ B2B" if r["is_b2b"] else ""
    sharp_str  = f"Oui ({r['sharp_dir'].upper()})" if r["sharp"] else "Non"
    mv_str     = f"{r['line_move']:+.1f}"
    pos_text   = "\n".join(f"  ✅ {x}" for x in r["reasons"])   or "  —"
    neg_text   = "\n".join(f"  ⚠️ {x}" for x in r["penalties"]) or "  —"

    return (
        f"{emoji} *ULTRON — NBA SPREAD*\n"
        f"🏀 *{game['away_team']} @ {game['home_team']}*\n"
        f"🏟 {game['venue']}\n\n"
        f"🎯 Pick: *{r['team']} {spread_str} ({side_str})*{b2b_str}\n"
        f"📊 Confiance: *{r['confidence']}/100*\n\n"
        f"📈 ATS L10: *{r['ats_record']}* ({r['ats_rate']:.0%})\n"
        f"📈 Point diff moyen: *{r['avg_diff']:+.1f} pts*\n"
        f"📈 Blowout L10: *{r['blowout_pct']:.0%}* | Serré: *{r['close_pct']:.0%}*\n"
        f"📊 Net rating: *{r['net_rating']:+.1f}*\n"
        f"💰 Sharp money: *{sharp_str}* (mouvement: {mv_str})\n\n"
        f"✅ *Points positifs:*\n{pos_text}\n\n"
        f"⚠️ *Points négatifs:*\n{neg_text}"
    )


# ══════════════════════════════════════════
#  10.  POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════
def run_nba_spread() -> None:
    print("🏀 Ultron — Analyse Spread NBA...")

    injuries    = get_nba_injuries()
    espn_games  = get_nba_games_today()
    odds_events = get_nba_odds_events()

    if not espn_games:
        print("Aucun match NBA trouvé aujourd'hui.")
        return

    for game in espn_games:
        print(f"\n🔍 Analyse: {game['away_team']} @ {game['home_team']}")

        # Données ESPN
        home_schedule = get_team_schedule(game["home_abbr"])
        away_schedule = get_team_schedule(game["away_abbr"])
        home_stats    = get_team_advanced_stats(game["home_abbr"])
        away_stats    = get_team_advanced_stats(game["away_abbr"])
        home_injuries = get_team_injury_impact(game["home_team"], injuries)
        away_injuries = get_team_injury_impact(game["away_team"], injuries)

        # Skip si back-to-back des deux côtés (matchs trop imprévisibles)
        if home_schedule["is_b2b"] and away_schedule["is_b2b"]:
            print(f"  ⏭️  Double B2B — trop imprévisible, skip")
            continue

        # Données Odds API
        odds_id   = match_odds_event(game["home_abbr"], game["away_abbr"], odds_events)
        odds_data = get_nba_spread_odds(odds_id) if odds_id else {}

        if not odds_data:
            print(f"  ⏭️  Pas de cote spread disponible — skip")
            continue

        home_spread = odds_data.get("home_spread", -3.5)
        away_spread = odds_data.get("away_spread",  3.5)

        # Score les deux côtés
        results = []
        for team_name, side, spread, schedule, stats, inj in [
            (game["home_team"], "home", home_spread, home_schedule, home_stats, home_injuries),
            (game["away_team"], "away", away_spread, away_schedule, away_stats, away_injuries),
        ]:
            result = score_nba_spread(
                team_name, side, spread,
                schedule, stats, inj, odds_data
            )
            print(f"  {team_name} {spread:+.1f} → confiance: {result['confidence']}/100"
                  + (" [B2B]" if result["is_b2b"] else ""))
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
    run_nba_spread()
