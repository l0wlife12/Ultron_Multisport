#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESPN Context Module — Blessures + Stats en temps réel
Utilisé par ULTRON pour ajuster les probabilités avant les matchs
"""

import requests
from datetime import date, datetime
from typing import List

try:
    from zoneinfo import ZoneInfo
    MONTREAL_TZ = ZoneInfo("America/Toronto")
except ImportError:
    import pytz
    MONTREAL_TZ = pytz.timezone("America/Toronto")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports"

SPORT_PATHS = {
    'NBA': 'basketball/nba',
    'NHL': 'icehockey/nhl',
    'NFL': 'americanfootball/nfl',
}

# ─────────────────────────────────────────
# BLESSURES EN TEMPS RÉEL
# ─────────────────────────────────────────

def get_injuries(sport: str) -> dict:
    """
    Récupère toutes les blessures actives.
    Retourne un dict indexé par nom d'équipe.
    Impact direct sur les probabilités.
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return {}

    try:
        url  = f"{ESPN_BASE}/{path}/injuries"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        injuries_by_team = {}

        for team_data in data.get('injuries', []):
            team_name = team_data.get('team', {}).get('displayName', '')
            players   = []

            for inj in team_data.get('injuries', []):
                athlete = inj.get('athlete', {})
                status  = inj.get('status', '')
                detail  = inj.get('details', {})

                impact = _estimate_injury_impact(athlete, status, sport)

                players.append({
                    'name':     athlete.get('displayName', ''),
                    'position': athlete.get('position', {}).get('abbreviation', ''),
                    'status':   status,
                    'injury':   detail.get('type', ''),
                    'side':     detail.get('location', ''),
                    'impact':   impact,
                    'is_key':   impact >= 3.0,
                })

            if players:
                injuries_by_team[team_name] = {
                    'players':      players,
                    'key_injuries': [p for p in players if p['is_key']],
                    'total_impact': sum(p['impact'] for p in players),
                    'severity':     _team_injury_severity(players),
                }

        return injuries_by_team

    except Exception as e:
        print(f"Erreur injuries {sport}: {e}")
        return {}


def _estimate_injury_impact(athlete: dict, status: str, sport: str) -> float:
    """
    Estime l'impact d'une blessure sur le Win% de l'équipe.
    Score = points de probabilité perdus (ex: 3.5 = −3.5%).
    """
    position = athlete.get('position', {}).get('abbreviation', '')

    status_multiplier = {
        'Out':          1.0,
        'Doubtful':     0.75,
        'Questionable': 0.40,
        'Day-To-Day':   0.30,
        'Probable':     0.10,
    }.get(status, 0.0)

    if status_multiplier == 0:
        return 0.0

    if sport == 'NBA':
        position_impact = {'PG': 4.5, 'SG': 3.0, 'SF': 3.5, 'PF': 3.0, 'C': 3.5}.get(position, 2.0)
    elif sport == 'NHL':
        position_impact = {'G': 8.0, 'C': 4.0, 'LW': 3.0, 'RW': 3.0, 'D': 3.5}.get(position, 2.0)
    elif sport == 'NFL':
        position_impact = {'QB': 10.0, 'WR': 3.0, 'RB': 2.5, 'TE': 2.5, 'OT': 3.0, 'CB': 2.5}.get(position, 1.5)
    else:
        position_impact = 2.0

    return round(position_impact * status_multiplier, 2)


def _team_injury_severity(players: list) -> str:
    total = sum(p['impact'] for p in players)
    if total >= 8:   return 'CRITIQUE'
    elif total >= 5: return 'ÉLEVÉE'
    elif total >= 2: return 'MODÉRÉE'
    else:            return 'FAIBLE'


# ─────────────────────────────────────────
# STATS ÉQUIPES EN TEMPS RÉEL
# ─────────────────────────────────────────

def get_team_stats(sport: str) -> dict:
    """
    Stats offensives/défensives de toutes les équipes via les standings ESPN.
    Utilisé pour ajuster les probabilités de base.
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return {}

    try:
        url  = f"{ESPN_BASE}/{path}/standings"
        resp = requests.get(url, timeout=10)
        data = resp.json()

        stats = {}
        for group in data.get('children', []):
            for entry in group.get('standings', {}).get('entries', []):
                team      = entry['team']['displayName']
                raw_stats = {s['name']: s.get('value', 0) for s in entry.get('stats', [])}

                stats[team] = {
                    'wins':           raw_stats.get('wins', 0),
                    'losses':         raw_stats.get('losses', 0),
                    'win_pct':        raw_stats.get('winPercent', 0.5),
                    'points_for':     raw_stats.get('pointsFor', raw_stats.get('avgPoints', 0)),
                    'points_against': raw_stats.get('pointsAgainst', raw_stats.get('avgPointsAgainst', 0)),
                    'home_record':    raw_stats.get('homeWinPct', 0.5),
                    'away_record':    raw_stats.get('awayWinPct', 0.5),
                    'last_10':        raw_stats.get('last10Wins', 5),
                    'streak':         raw_stats.get('streak', 0),
                    'diff':           raw_stats.get('pointsFor', 0) - raw_stats.get('pointsAgainst', 0),
                }

        return stats

    except Exception as e:
        print(f"Erreur team stats {sport}: {e}")
        return {}


# ─────────────────────────────────────────
# MATCHS DU JOUR + CONTEXTE COMPLET
# ─────────────────────────────────────────

def get_games_with_context(sport: str) -> List[dict]:
    """
    Récupère les matchs du jour avec blessures, forme récente,
    stats et ajustement de probabilité intégré.
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return []

    try:
        today = date.today().strftime("%Y%m%d")
        url   = f"{ESPN_BASE}/{path}/scoreboard?dates={today}"
        resp  = requests.get(url, timeout=10)
        data  = resp.json()

        injuries   = get_injuries(sport)
        team_stats = get_team_stats(sport)
        games      = []

        for event in data.get('events', []):
            comp = event['competitions'][0]

            home_data = next((t for t in comp['competitors'] if t['homeAway'] == 'home'), None)
            away_data = next((t for t in comp['competitors'] if t['homeAway'] == 'away'), None)
            if not home_data or not away_data:
                continue

            home_name = home_data['team']['displayName']
            away_name = away_data['team']['displayName']

            home_inj   = injuries.get(home_name, {})
            away_inj   = injuries.get(away_name, {})
            home_stats = team_stats.get(home_name, {})
            away_stats = team_stats.get(away_name, {})

            prob_adjustment = _calculate_prob_adjustment(
                home_inj, away_inj, home_stats, away_stats, is_home=True
            )

            games.append({
                'sport':    sport,
                'game_id':  event.get('id', ''),
                'home_team': home_name,
                'away_team': away_name,
                'start_time': _to_local_time(event.get('date', '')),
                'status':   event['status']['type']['name'],

                'home_injuries':     home_inj,
                'away_injuries':     away_inj,
                'home_inj_severity': home_inj.get('severity', 'FAIBLE'),
                'away_inj_severity': away_inj.get('severity', 'FAIBLE'),
                'home_inj_impact':   home_inj.get('total_impact', 0),
                'away_inj_impact':   away_inj.get('total_impact', 0),

                'home_win_pct':  home_stats.get('win_pct', 0.5),
                'away_win_pct':  away_stats.get('win_pct', 0.5),
                'home_form':     home_stats.get('last_10', 5) / 10,
                'away_form':     away_stats.get('last_10', 5) / 10,
                'home_diff':     home_stats.get('diff', 0),
                'away_diff':     away_stats.get('diff', 0),
                'home_streak':   home_stats.get('streak', 0),
                'away_streak':   away_stats.get('streak', 0),

                'prob_adjustment': prob_adjustment,
            })

        return games

    except Exception as e:
        print(f"Erreur games context {sport}: {e}")
        return []


def _calculate_prob_adjustment(home_inj: dict, away_inj: dict,
                                home_stats: dict, away_stats: dict,
                                is_home: bool) -> float:
    """
    Calcule l'ajustement de probabilité basé sur le contexte ESPN.
    Retourne un delta entre −0.15 et +0.15.
    """
    adjustment = 0.0

    home_inj_penalty = home_inj.get('total_impact', 0) / 100
    away_inj_penalty = away_inj.get('total_impact', 0) / 100
    adjustment += away_inj_penalty - home_inj_penalty

    home_form = home_stats.get('last_10', 5) / 10
    away_form = away_stats.get('last_10', 5) / 10
    adjustment += (home_form - away_form) * 0.10

    home_diff = home_stats.get('diff', 0)
    away_diff = away_stats.get('diff', 0)
    adjustment += (home_diff - away_diff) / 200

    if is_home:
        adjustment += 0.03  # avantage domicile

    return round(max(min(adjustment, 0.15), -0.15), 4)


def _to_local_time(utc_str: str) -> str:
    if not utc_str:
        return "TBD"
    try:
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        local = dt.astimezone(MONTREAL_TZ)
        return local.strftime("%H:%M")
    except Exception:
        return utc_str


# ─────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────

def get_full_context_all_sports() -> dict:
    """
    Récupère le contexte complet NBA + NHL + NFL.
    Appelé une fois le matin — résultats partagés toute la journée.
    """
    context = {}
    for sport in ['NBA', 'NHL', 'NFL']:
        games = get_games_with_context(sport)
        if games:
            context[sport] = games
    return context


def format_injuries_alert(context: dict) -> str:
    """
    Génère un message Telegram avec les alertes blessures importantes.
    Retourne une chaîne vide si aucune blessure clé.
    """
    alerts = []

    for sport, games in context.items():
        sport_e = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(sport, "🎯")
        for game in games:
            for side in ['home', 'away']:
                team  = game[f'{side}_team']
                inj   = game[f'{side}_injuries']
                key_p = inj.get('key_injuries', [])

                if key_p:
                    names = ', '.join(
                        f"{p['name']} ({p['status']})" for p in key_p[:2]
                    )
                    sev   = inj.get('severity', '')
                    emoji = "🔴" if sev == 'CRITIQUE' else ("🟡" if sev == 'ÉLEVÉE' else "🟢")
                    alerts.append(f"{emoji} {sport_e} {team} : {names}")

    if not alerts:
        return ""

    msg  = "🏥 ALERTES BLESSURES DU JOUR\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "\n".join(alerts)
    msg += "\n\n⚙️ Impact intégré dans les picks ULTRON"
    return msg


def find_game_context(away: str, home: str, games: List[dict]) -> dict:
    """
    Trouve le contexte ESPN d'un match à partir des noms d'équipes.
    Retourne {} si introuvable.
    """
    away_l = away.lower()
    home_l = home.lower()

    for game in games:
        g_away = game['away_team'].lower()
        g_home = game['home_team'].lower()

        away_parts = [w for w in away_l.split() if len(w) > 3]
        home_parts = [w for w in home_l.split() if len(w) > 3]

        away_match = any(p in g_away for p in away_parts)
        home_match = any(p in g_home for p in home_parts)

        if away_match and home_match:
            return game

    return {}


# ─────────────────────────────────────────
# BOX SCORE EN DIRECT
# ─────────────────────────────────────────

def get_live_game_ids(sport: str) -> list:
    """
    Retourne la liste des matchs du jour avec leur ID ESPN.
    Inclut les matchs en cours, à venir et terminés aujourd'hui.
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return []
    try:
        today = date.today().strftime("%Y%m%d")
        url = f"{ESPN_BASE}/{path}/scoreboard?dates={today}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        games = []
        for event in resp.json().get('events', []):
            comp = event.get('competitions', [{}])[0]
            competitors = comp.get('competitors', [])
            if len(competitors) < 2:
                continue
            away = next((t for t in competitors if t.get('homeAway') == 'away'), competitors[0])
            home = next((t for t in competitors if t.get('homeAway') == 'home'), competitors[1])
            status = event.get('status', {})
            games.append({
                'id':     event['id'],
                'away':   away['team']['displayName'],
                'home':   home['team']['displayName'],
                'status': status.get('type', {}).get('description', ''),
                'clock':  status.get('displayClock', ''),
                'period': status.get('period', 0),
            })
        return games
    except Exception as e:
        print(f"Erreur get_live_game_ids {sport}: {e}")
        return []


def get_boxscore(sport: str, game_id: str) -> dict:
    """
    Récupère le box score complet d'un match via l'endpoint summary ESPN.
    Retourne {} si indisponible.
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return {}
    try:
        url = f"{ESPN_BASE}/{path}/summary?event={game_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        boxscore = data.get('boxscore', {})
        header   = data.get('header', {})

        result = {
            'sport':      sport,
            'game_id':    game_id,
            'home':       '',
            'away':       '',
            'home_score': 0,
            'away_score': 0,
            'status':     '',
            'clock':      '',
            'period':     0,
            'teams':      [],
        }

        # Score + statut depuis le header
        competitions = header.get('competitions', [{}])[0] if header else {}
        for comp in competitions.get('competitors', []):
            side  = comp.get('homeAway', '')
            name  = comp.get('team', {}).get('displayName', '')
            score = int(comp.get('score', 0) or 0)
            if side == 'home':
                result['home']       = name
                result['home_score'] = score
            else:
                result['away']       = name
                result['away_score'] = score
        status_data = competitions.get('status', {})
        result['status'] = status_data.get('type', {}).get('description', '')
        result['clock']  = status_data.get('displayClock', '')
        result['period'] = status_data.get('period', 0)

        # Stats joueurs
        for team_data in boxscore.get('players', []):
            team_name = team_data.get('team', {}).get('displayName', '')
            players   = []
            for stat_group in team_data.get('statistics', []):
                keys = stat_group.get('names', stat_group.get('keys', []))
                for athlete_data in stat_group.get('athletes', []):
                    if athlete_data.get('didNotPlay', False):
                        continue
                    athlete    = athlete_data.get('athlete', {})
                    stats_vals = athlete_data.get('stats', [])
                    player_stats = {
                        keys[i]: stats_vals[i]
                        for i in range(min(len(keys), len(stats_vals)))
                    }
                    players.append({
                        'name':     athlete.get('displayName', ''),
                        'position': athlete.get('position', {}).get('abbreviation', ''),
                        'stats':    player_stats,
                    })
            result['teams'].append({'name': team_name, 'players': players})

        return result
    except Exception as e:
        print(f"Erreur get_boxscore {sport}/{game_id}: {e}")
        return {}


def _period_label(sport: str, period: int) -> str:
    """Retourne le libellé de la période (Q1, OT, 1re, etc.)."""
    if sport == 'NBA':
        return f"Q{period}" if period <= 4 else f"OT{period - 4}"
    elif sport == 'NHL':
        return {1: '1re', 2: '2e', 3: '3e'}.get(period, f"OT{period - 3}")
    elif sport == 'NFL':
        return f"Q{period}" if period <= 4 else "OT"
    return f"P{period}"


def _get_display_keys(sport: str) -> list:
    """Colonnes prioritaires à afficher dans le box score."""
    if sport == 'NBA':
        return ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', '+/-']
    elif sport == 'NHL':
        return ['G', 'A', 'PTS', '+/-', 'SOG', 'TOI']
    elif sport == 'NFL':
        return ['CMP', 'YDS', 'TD', 'INT']
    return ['PTS']


def format_boxscore_message(sport: str, game_id: str) -> str:
    """Formate le box score d'un match pour Telegram."""
    data = get_boxscore(sport, game_id)
    if not data:
        return "❌ Box score indisponible pour ce match."

    sport_emoji = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(sport, "🎯")
    away   = data['away'] or '?'
    home   = data['home'] or '?'
    status = data.get('status', '')
    clock  = data.get('clock', '')
    period = data.get('period', 0)

    msg  = f"{sport_emoji} BOX SCORE — {sport}\n"
    msg += f"🏟  {away}  {data['away_score']} – {data['home_score']}  {home}\n"
    if 'progress' in status.lower() and period:
        msg += f"⏱  {_period_label(sport, period)}  |  {clock}\n"
    elif 'final' in status.lower():
        msg += "🏁  FINAL\n"
    elif status:
        msg += f"📅  {status}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    keys = _get_display_keys(sport)
    for team_data in data.get('teams', []):
        players = team_data.get('players', [])
        if not players:
            continue
        msg += f"\n🔷 {team_data['name']}\n"
        # En-tête colonnes
        header = f"{'Joueur':<16}" + "".join(f" {k:>5}" for k in keys)
        msg += header + "\n"
        msg += "─" * len(header) + "\n"
        for p in players[:8]:
            nom   = p['name'].split()[-1][:14]
            ligne = f"{nom:<16}" + "".join(
                f" {str(p['stats'].get(k, '-'))[:5]:>5}" for k in keys
            )
            msg += ligne + "\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📡 Source : ESPN"
    return msg


def format_all_boxscores(sport: str) -> List[str]:
    """
    Retourne une liste de messages (un par match du jour).
    À envoyer séquentiellement dans Telegram.
    """
    games = get_live_game_ids(sport)
    if not games:
        sport_emoji = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(sport, "🎯")
        return [f"{sport_emoji} Aucun match {sport} aujourd'hui."]
    messages = []
    for g in games:
        msg = format_boxscore_message(sport, g['id'])
        messages.append(msg)
    return messages


# ─────────────────────────────────────────
# LEADERS DE STATS
# ─────────────────────────────────────────

_LEADER_CATEGORIES = {
    'NBA': ['pointsPerGame', 'reboundsPerGame', 'assistsPerGame',
            'stealsPerGame', 'blocksPerGame'],
    'NHL': ['points', 'goals', 'assists', 'plusMinus', 'savePercentage'],
    'NFL': ['passingYards', 'rushingYards', 'receivingYards',
            'passingTouchdowns', 'sacks'],
}


def get_stat_leaders(sport: str, max_per_cat: int = 5) -> list:
    """
    Récupère les leaders de statistiques depuis ESPN.
    Retourne liste de dicts :
      { 'name': str, 'abbreviation': str, 'leaders': [{name, team, value}] }
    """
    path = SPORT_PATHS.get(sport)
    if not path:
        return []
    try:
        url  = f"{ESPN_BASE}/{path}/leaders"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data          = resp.json()
        target_cats   = _LEADER_CATEGORIES.get(sport, [])
        categories    = []

        for cat in data.get('categories', []):
            if cat.get('name', '') not in target_cats:
                continue
            leaders = []
            for entry in cat.get('leaders', [])[:max_per_cat]:
                athlete = entry.get('athlete', {})
                team    = (
                    athlete.get('team', {}).get('shortDisplayName', '') or
                    athlete.get('team', {}).get('displayName', '')
                )
                leaders.append({
                    'name':  athlete.get('displayName', athlete.get('shortName', '?')),
                    'team':  team,
                    'value': entry.get('displayValue', '?'),
                })
            if leaders:
                categories.append({
                    'name':         cat.get('displayName', cat.get('name', '')),
                    'abbreviation': cat.get('abbreviation', cat.get('name', '')[:3].upper()),
                    'leaders':      leaders,
                })
        return categories
    except Exception as e:
        print(f"Erreur get_stat_leaders {sport}: {e}")
        return []


def format_leaders_message(sport: str) -> str:
    """Formate les leaders stats d'un sport pour Telegram."""
    categories = get_stat_leaders(sport)
    if not categories:
        return f"❌ Leaders stats {sport} indisponibles (hors saison?)."

    sport_emoji = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(sport, "🎯")
    ranks       = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    msg  = f"{sport_emoji} LEADERS {sport} — SAISON EN COURS\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for cat in categories:
        msg += f"\n📊 {cat['name']}\n"
        for i, leader in enumerate(cat['leaders']):
            rank = ranks[i] if i < len(ranks) else f"{i + 1}."
            team = f"({leader['team']})" if leader['team'] else ""
            msg += f"  {rank} {leader['name']} {team} — {leader['value']}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📡 Source : ESPN"
    return msg
