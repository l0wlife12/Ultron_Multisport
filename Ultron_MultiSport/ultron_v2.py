"""
╔══════════════════════════════════════════════════════════════╗
║           ULTRON v2.0 — MOTEUR DE PRÉDICTION COMPLET        ║
║  Intègre : Elo, No-Vig, Régression, ESPN, Qualité Filter    ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import json
import math
import statistics
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, asdict, field
from typing import Optional

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

ODDS_API_KEY  = os.getenv('ODDS_API_KEY', '')   # Lue depuis Railway env var
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ESPN_BASE     = "https://site.api.espn.com/apis/site/v2/sports"
NHL_API       = "https://api-web.nhle.com/v1"
MONTREAL_TZ   = ZoneInfo("America/Toronto")
DATA_DIR      = "/data" if os.path.isdir("/data") else "data"
ELO_FILE      = f"{DATA_DIR}/elo_ratings.json"

os.makedirs(DATA_DIR, exist_ok=True)

SPORTS_CONFIG = {
    'NBA': {
        'odds_key':      'basketball_nba',
        'espn_path':     'basketball/nba',
        'home_advantage': 65,    # Points Elo
        'k_factor':       20,
        'max_ev':         0.10,
        'min_prob':       0.45,
        'max_prob':       0.78,
    },
    'NHL': {
        'odds_key':      'icehockey_nhl',
        'espn_path':     'icehockey/nhl',
        'home_advantage': 40,
        'k_factor':       18,
        'max_ev':         0.10,
        'min_prob':       0.42,
        'max_prob':       0.75,
    },
    'NFL': {
        'odds_key':      'americanfootball_nfl',
        'espn_path':     'americanfootball/nfl',
        'home_advantage': 55,
        'k_factor':       25,
        'max_ev':         0.10,
        'min_prob':       0.40,
        'max_prob':       0.80,
    },
}

BOOKMAKERS_SHARP  = ['pinnacle', 'betfair']
BOOKMAKERS_SOFT   = ['draftkings', 'bet365', 'fanduel', 'betmgm', 'unibet']
ALL_BOOKMAKERS    = BOOKMAKERS_SHARP + BOOKMAKERS_SOFT


# ══════════════════════════════════════════
# MODULE 1 — SYSTÈME ELO
# ══════════════════════════════════════════

class EloSystem:
    """
    Ratings dynamiques par équipe
    Se met à jour après chaque match
    Représente la vraie force de chaque équipe
    """

    def __init__(self, sport: str):
        self.sport   = sport
        self.cfg     = SPORTS_CONFIG[sport]
        self.ratings = self._load()

    def _load(self) -> dict:
        if os.path.exists(ELO_FILE):
            try:
                data = json.load(open(ELO_FILE))
                return data.get(self.sport, {})
            except:
                pass
        return {}

    def _save(self):
        all_data = {}
        if os.path.exists(ELO_FILE):
            try:
                all_data = json.load(open(ELO_FILE))
            except:
                pass
        all_data[self.sport] = self.ratings
        json.dump(all_data, open(ELO_FILE, 'w'), indent=2)

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, 1500.0)

    def predict(self, home_team: str,
                away_team: str) -> tuple[float, float]:
        """
        Prédit les probabilités basées sur les ratings Elo
        Indépendamment des cotes bookmakers
        """
        home_r = self.get_rating(home_team)
        away_r = self.get_rating(away_team)
        ha     = self.cfg['home_advantage']

        home_prob = 1 / (1 + 10 ** ((away_r - (home_r + ha)) / 400))
        return round(home_prob, 4), round(1 - home_prob, 4)

    def update(self, winner: str, loser: str,
               margin: float, home_won: bool):
        """Met à jour après chaque match"""
        winner_r = self.get_rating(winner)
        loser_r  = self.get_rating(loser)
        K        = self.cfg['k_factor']

        expected = 1 / (1 + 10 ** ((loser_r - winner_r) / 400))
        margin_f = min(math.log(max(margin, 1) + 1) / 3, 2.0)
        change   = K * margin_f * (1 - expected)

        self.ratings[winner] = round(winner_r + change, 2)
        self.ratings[loser]  = round(loser_r  - change, 2)
        self._save()

    def get_rankings(self, top_n: int = 10) -> list:
        """Top N équipes selon leur rating"""
        sorted_teams = sorted(
            self.ratings.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_teams[:top_n]


# ══════════════════════════════════════════
# MODULE 2 — PROBABILITÉS NO-VIG
# ══════════════════════════════════════════

class ProbabilityEngine:
    """
    Calcule les vraies probabilités en retirant
    la marge des bookmakers (vig)
    + régression vers la moyenne
    """

    REGRESSION_FACTOR = 0.85  # Réduit les extrêmes de 15%

    @staticmethod
    def remove_vig(home_odds: float,
                   away_odds: float) -> tuple[float, float]:
        """Retire la marge — donne les vraies probabilités"""
        if home_odds <= 0 or away_odds <= 0:
            return 0.5, 0.5
        raw_h = 1 / home_odds
        raw_a = 1 / away_odds
        total = raw_h + raw_a
        return round(raw_h / total, 4), round(raw_a / total, 4)

    @staticmethod
    def apply_regression(prob: float) -> float:
        """
        Régresse vers 50% — les extrêmes sont toujours surestimés
        Ex: 80% → 72.5% (plus réaliste)
        """
        f = ProbabilityEngine.REGRESSION_FACTOR
        return round(0.50 + (prob - 0.50) * f, 4)

    @staticmethod
    def calculate_vig(odds_list: list) -> float:
        """Calcule le % de marge d'un bookmaker"""
        if not odds_list:
            return 0
        total = sum(1/o for o in odds_list if o > 0)
        return round((total - 1) / total * 100, 2)

    def get_consensus(self, h2h_odds: dict,
                      home_team: str,
                      away_team: str) -> dict:
        """
        Consensus de probabilité sur tous les bookmakers
        Utilise Pinnacle comme ancre (le plus sharp)
        """
        home_probs, away_probs = [], []
        pinnacle_prob           = None

        for bk, odds in h2h_odds.items():
            h = odds.get(home_team, 0)
            a = odds.get(away_team, 0)
            if h > 0 and a > 0:
                hp, ap = self.remove_vig(h, a)
                home_probs.append(hp)
                away_probs.append(ap)
                if bk == 'pinnacle':
                    pinnacle_prob = hp

        if not home_probs:
            return {'home': 0.5, 'away': 0.5,
                    'confidence': 'LOW', 'books': 0}

        # Médiane — plus robuste que la moyenne
        consensus_home = statistics.median(home_probs)
        consensus_away = 1 - consensus_home

        # Régression vers la moyenne
        reg_home = self.apply_regression(consensus_home)
        reg_away = round(1 - reg_home, 4)

        # Écart-type — mesure l'accord entre books
        std = (statistics.stdev(home_probs)
               if len(home_probs) > 1 else 0)

        # Si Pinnacle disponible → l'utiliser comme référence
        if pinnacle_prob:
            pin_reg = self.apply_regression(pinnacle_prob)
            # Moyenne pondérée : 60% Pinnacle + 40% consensus
            reg_home = round(pin_reg * 0.60 + reg_home * 0.40, 4)
            reg_away = round(1 - reg_home, 4)

        confidence = ('HIGH'   if std < 0.03 else
                      'MEDIUM' if std < 0.06 else 'LOW')

        return {
            'home':          reg_home,
            'away':          reg_away,
            'raw_home':      consensus_home,
            'uncertainty':   round(std, 4),
            'confidence':    confidence,
            'books':         len(home_probs),
            'pinnacle_used': pinnacle_prob is not None,
        }


# ══════════════════════════════════════════
# MODULE 3 — DONNÉES ESPN (Blessures + Stats)
# ══════════════════════════════════════════

class ESPNDataFetcher:
    """
    Blessures en temps réel, stats équipes,
    lineups confirmés via ESPN API gratuite
    """

    def __init__(self, sport: str):
        self.sport    = sport
        self.path     = SPORTS_CONFIG[sport]['espn_path']
        self._cache   = {}

    def _get(self, url: str, cache_key: str = None) -> dict:
        """Fetch avec cache 30 minutes"""
        if cache_key and cache_key in self._cache:
            cached_at, data = self._cache[cache_key]
            if time.time() - cached_at < 1800:  # 30 min
                return data
        try:
            resp = requests.get(url, timeout=12)
            data = resp.json() if resp.status_code == 200 else {}
            if cache_key:
                self._cache[cache_key] = (time.time(), data)
            return data
        except Exception as e:
            print(f"ESPN fetch error: {e}")
            return {}

    def get_injuries(self) -> dict:
        """Toutes les blessures actives indexées par équipe"""
        url  = f"{ESPN_BASE}/{self.path}/injuries"
        data = self._get(url, f"injuries_{self.sport}")
        result = {}

        for team_data in data.get('injuries', []):
            team_name = team_data.get('team', {}).get('displayName', '')
            players   = []

            for inj in team_data.get('injuries', []):
                athlete  = inj.get('athlete', {})
                status   = inj.get('status', '')
                position = athlete.get('position', {}).get('abbreviation', '')
                impact   = self._injury_impact(position, status)

                if impact > 0:
                    players.append({
                        'name':     athlete.get('displayName', ''),
                        'position': position,
                        'status':   status,
                        'impact':   impact,
                        'is_key':   impact >= 3.0,
                    })

            if players:
                total_impact = sum(p['impact'] for p in players)
                result[team_name] = {
                    'players':      players,
                    'key_players':  [p for p in players if p['is_key']],
                    'total_impact': round(total_impact, 2),
                    'severity':     self._severity(total_impact),
                }

        return result

    def _injury_impact(self, position: str, status: str) -> float:
        """Impact d'une blessure sur la probabilité de victoire"""
        status_mult = {
            'Out':          1.00,
            'Doubtful':     0.75,
            'Questionable': 0.40,
            'Day-To-Day':   0.25,
            'Probable':     0.10,
        }.get(status, 0.0)

        if status_mult == 0:
            return 0.0

        pos_impact = {
            'NBA': {'PG': 5.0, 'SG': 3.0, 'SF': 3.5,
                    'PF': 3.0, 'C': 3.5},
            'NHL': {'G': 9.0, 'C': 4.0, 'LW': 3.0,
                    'RW': 3.0, 'D': 3.5},
            'NFL': {'QB': 12.0, 'WR': 3.0, 'RB': 2.5,
                    'TE': 2.5, 'OT': 3.0, 'CB': 2.5},
        }.get(self.sport, {}).get(position, 2.0)

        return round(pos_impact * status_mult, 2)

    def _severity(self, total: float) -> str:
        if total >= 8:   return 'CRITIQUE'
        elif total >= 5: return 'ÉLEVÉE'
        elif total >= 2: return 'MODÉRÉE'
        return 'FAIBLE'

    def get_team_stats(self) -> dict:
        """Stats saison + forme récente de toutes les équipes"""
        url  = f"{ESPN_BASE}/{self.path}/standings"
        data = self._get(url, f"standings_{self.sport}")
        stats = {}

        for group in data.get('children', []):
            for entry in (group.get('standings', {})
                              .get('entries', [])):
                team = entry['team']['displayName']
                raw  = {s['name']: s.get('value', 0)
                        for s in entry.get('stats', [])}

                wins   = raw.get('wins', 0)
                losses = raw.get('losses', 0)
                gp     = wins + losses

                stats[team] = {
                    'win_pct':    raw.get('winPercent', 0.5),
                    'wins':       wins,
                    'losses':     losses,
                    'pts_for':    raw.get('pointsFor', 0),
                    'pts_against': raw.get('pointsAgainst', 0),
                    'home_wpct':  raw.get('homeWinPct', 0.5),
                    'away_wpct':  raw.get('awayWinPct', 0.5),
                    'last_10':    raw.get('last10Wins', 5),
                    'streak':     raw.get('streak', 0),
                    'diff':       (raw.get('pointsFor', 0) -
                                   raw.get('pointsAgainst', 0)),
                    'form':       raw.get('last10Wins', 5) / 10,
                }

        return stats

    def get_nhl_confirmed_goalie(self, team_abbr: str) -> dict:
        """
        Gardien confirmé pour le match du soir
        CRITIQUE en NHL — ne jamais ignorer
        """
        try:
            url  = f"{NHL_API}/schedule/now"
            data = requests.get(url, timeout=10).json()

            for week in data.get('gameWeek', []):
                for game in week.get('games', []):
                    home = game.get('homeTeam', {})
                    away = game.get('awayTeam', {})

                    for team_data in [home, away]:
                        if team_data.get('abbrev') == team_abbr:
                            goalie = team_data.get('startingGoalie', {})
                            if goalie:
                                return {
                                    'confirmed': True,
                                    'name':      goalie.get('name', {}).get('default', ''),
                                    'sv_pct':    goalie.get('savePctg', 0.900),
                                    'gaa':       goalie.get('goalsAgainstAvg', 3.0),
                                    'is_starter': True,
                                }
            return {'confirmed': False, 'name': 'TBD'}
        except:
            return {'confirmed': False, 'name': 'TBD'}

    def calculate_prob_adjustment(self,
                                   home_inj: dict,
                                   away_inj: dict,
                                   home_stats: dict,
                                   away_stats: dict) -> float:
        """
        Ajustement de probabilité basé sur ESPN
        Retourne un delta à appliquer sur la prob home
        """
        adj = 0.0

        # Impact blessures différentiel
        h_pen = home_inj.get('total_impact', 0) / 100
        a_pen = away_inj.get('total_impact', 0) / 100
        adj  += (a_pen - h_pen)

        # Forme récente
        h_form = home_stats.get('form', 0.5)
        a_form = away_stats.get('form', 0.5)
        adj   += (h_form - a_form) * 0.08

        # Point differential
        h_diff = home_stats.get('diff', 0)
        a_diff = away_stats.get('diff', 0)
        adj   += (h_diff - a_diff) / 300

        # Avantage domicile
        adj += 0.03

        # Plafond ±12%
        return round(max(min(adj, 0.12), -0.12), 4)


# ══════════════════════════════════════════
# MODULE 4 — FETCH COTES BOOKMAKERS
# ══════════════════════════════════════════

class OddsFetcher:
    """Récupère les cotes de tous les bookmakers"""

    def __init__(self):
        self._remaining = None

    def fetch(self, sport_key: str,
              markets: list = None) -> list:
        markets = markets or ['h2h', 'spreads', 'totals']
        if not ODDS_API_KEY:
            print(f"  [API] ODDS_API_KEY non configuré — skip {sport_key}")
            return []
        try:
            url    = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
            params = {
                'apiKey':     ODDS_API_KEY,
                'regions':    'us,us2,eu',
                'markets':    ','.join(markets),
                'oddsFormat': 'decimal',
                'bookmakers': ','.join(ALL_BOOKMAKERS),
            }
            resp = requests.get(url, params=params, timeout=15)
            self._remaining = resp.headers.get(
                'x-requests-remaining', '?'
            )
            print(f"  [API] {sport_key} "
                  f"— requêtes restantes: {self._remaining}")
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            print(f"Erreur odds {sport_key}: {e}")
            return []

    def extract_h2h(self, game: dict) -> dict:
        """Extrait toutes les cotes h2h par bookmaker"""
        result = {}
        for bk in game.get('bookmakers', []):
            for mkt in bk.get('markets', []):
                if mkt['key'] == 'h2h':
                    result[bk['key']] = {
                        o['name']: o['price']
                        for o in mkt.get('outcomes', [])
                    }
        return result

    def extract_totals(self, game: dict) -> dict:
        """Extrait les cotes Over/Under"""
        lines, over_list, under_list = [], [], []
        for bk in game.get('bookmakers', []):
            for mkt in bk.get('markets', []):
                if mkt['key'] == 'totals':
                    for o in mkt.get('outcomes', []):
                        if o['name'] == 'Over':
                            over_list.append(o['price'])
                            if o.get('point'):
                                lines.append(o['point'])
                        elif o['name'] == 'Under':
                            under_list.append(o['price'])

        if not lines:
            return {}

        line = statistics.median(lines)
        bo   = max(over_list)  if over_list  else 0
        bu   = max(under_list) if under_list else 0

        if bo > 0 and bu > 0:
            op, _ = ProbabilityEngine.remove_vig(bo, bu)
        else:
            op = 0.5

        return {
            'line':       round(line, 1),
            'best_over':  bo,
            'best_under': bu,
            'over_prob':  round(op, 3),
            'under_prob': round(1 - op, 3),
            'lean':       ('Over'  if op > 0.53 else
                           'Under' if op < 0.47 else 'None'),
        }

    def find_best_odds(self, h2h_odds: dict,
                       team: str) -> dict:
        """Meilleure cote disponible pour une équipe"""
        best = {'odds': 0, 'book': ''}
        for bk, odds in h2h_odds.items():
            if odds.get(team, 0) > best['odds']:
                best = {'odds': odds[team], 'book': bk}
        return best


# ══════════════════════════════════════════
# MODULE 5 — FILTRE DE QUALITÉ
# ══════════════════════════════════════════

class QualityFilter:
    """
    Filtre strict — rejette les picks douteux
    Mieux vaut ne rien envoyer que d'envoyer du mauvais
    """

    def __init__(self, sport: str):
        self.cfg = SPORTS_CONFIG[sport]
        self.sport = sport

    def validate(self, pick: dict) -> tuple[bool, str]:
        """Valide un pick — retourne (is_valid, reason)"""

        ev   = pick.get('ev', 0)
        prob = pick.get('probability', 0)

        # ── Règle 1 : EV minimum réaliste ──
        if ev < 0.025:
            return False, f"EV trop faible ({ev:.1%})"

        # ── Règle 2 : EV trop beau → suspect ──
        if ev > self.cfg['max_ev']:
            return False, f"EV suspect ({ev:.1%}) — données incorrectes"

        # ── Règle 3 : Probabilité dans la zone raisonnable ──
        if prob < self.cfg['min_prob']:
            return False, f"Prob trop faible ({prob:.0%}) — underdog extrême"

        if prob > self.cfg['max_prob']:
            return False, f"Prob trop élevée ({prob:.0%}) — extrême irréaliste"

        # ── Règle 4 : NHL sans gardien confirmé ──
        if self.sport == 'NHL':
            goalie = pick.get('goalie_info', {})
            if not goalie.get('confirmed'):
                return False, "Gardien NHL non confirmé — skip"

        # ── Règle 5 : Blessure critique sans compensation ──
        inj_impact = pick.get('injury_impact', 0)
        if inj_impact > 9.0:
            return False, f"Blessure majeure (impact {inj_impact}) — incertain"

        # ── Règle 6 : Pas assez de books pour consensus ──
        books = pick.get('books_count', 0)
        if books < 3:
            return False, f"Seulement {books} books — consensus insuffisant"

        # ── Règle 7 : Incertitude trop élevée ──
        uncertainty = pick.get('uncertainty', 0)
        if uncertainty > 0.06:
            return False, f"Books trop divergents (σ={uncertainty:.3f})"

        # ── Règle 8 : Match bientôt — vérification données ──
        if pick.get('data_freshness_mins', 0) > 120:
            return False, "Données trop vieilles — refresh requis"

        return True, "✅ Pick validé"

    def select_best(self, picks: list,
                    max_picks: int = 3) -> list:
        """
        Sélectionne les N meilleurs picks
        Score composite : EV + confiance + consensus
        """
        valid = []
        for pick in picks:
            ok, reason = self.validate(pick)
            pick['filter_result'] = reason
            if ok:
                valid.append(pick)
            else:
                print(f"  ❌ Skip [{pick.get('pick_team','?')}]: {reason}")

        def composite_score(p):
            ev_score   = min(p.get('ev', 0) * 300, 40)
            conf_score = p.get('confidence', 0) * 0.35
            prob_score = min(abs(p.get('probability', 0.5) - 0.5) * 100, 15)
            elo_score  = p.get('elo_confirms', False) * 10
            return ev_score + conf_score + prob_score + elo_score

        return sorted(valid,
                      key=composite_score,
                      reverse=True)[:max_picks]


# ══════════════════════════════════════════
# MODULE 6 — KELLY + CALCULS FINANCIERS
# ══════════════════════════════════════════

def calculate_ev(prob: float, odds: float) -> float:
    if odds <= 1:
        return -1.0
    return round((prob * (odds - 1)) - (1 - prob), 4)


def kelly_stake(prob: float, odds: float,
                bankroll: float,
                fraction: float = 0.5) -> float:
    """Demi-Kelly avec plafond à 5% de bankroll"""
    b = odds - 1
    if b <= 0:
        return 0
    k = (b * prob - (1 - prob)) / b
    return round(min(max(k * fraction * bankroll, 0),
                     bankroll * 0.05), 2)


# ══════════════════════════════════════════
# MODULE 7 — MOTEUR PRINCIPAL
# ══════════════════════════════════════════

class UltronV2:
    """
    Moteur principal d'Ultron v2.0
    Orchestre tous les modules ensemble
    """

    def __init__(self, bankroll: float = 1000):
        self.bankroll  = bankroll
        self.fetcher   = OddsFetcher()
        self.prob_eng  = ProbabilityEngine()

    def run(self) -> dict:
        """
        Génère les picks du jour
        Appelé à 9h00 par le scheduler
        """
        print("\n" + "="*55)
        print("🤖  ULTRON v2.0 — Génération des picks")
        print("="*55)

        all_picks = []

        for sport, cfg in SPORTS_CONFIG.items():
            print(f"\n📡 Analyse {sport}...")
            picks = self._analyze_sport(sport, cfg)
            all_picks.extend(picks)
            print(f"  → {len(picks)} picks générés pour {sport}")

        # Sélection finale — top 3 tous sports confondus
        best = self._global_select(all_picks)

        print(f"\n✅ {len(best)} picks retenus sur {len(all_picks)}")
        print("="*55)

        return {
            'date':       str(date.today()),
            'picks':      best,
            'total_raw':  len(all_picks),
            'bankroll':   self.bankroll,
        }

    def _analyze_sport(self, sport: str, cfg: dict) -> list:
        """Analyse complète d'un sport"""
        picks = []

        # 1. Fetch cotes
        games = self.fetcher.fetch(cfg['odds_key'])
        if not games:
            print(f"  ⚠️  Aucun match {sport} aujourd'hui")
            return []

        # 2. Données ESPN
        espn   = ESPNDataFetcher(sport)
        inj    = espn.get_injuries()
        stats  = espn.get_team_stats()

        # 3. Système Elo
        elo = EloSystem(sport)

        # 4. Filtre qualité
        qf = QualityFilter(sport)

        for game in games:
            try:
                pick = self._analyze_game(
                    game, sport, espn, inj, stats, elo, qf
                )
                if pick:
                    picks.append(pick)
            except Exception as e:
                print(f"  ⚠️  Erreur analyse: {e}")

        return picks

    def _analyze_game(self, game: dict, sport: str,
                      espn: ESPNDataFetcher,
                      injuries: dict, team_stats: dict,
                      elo: EloSystem,
                      qf: QualityFilter) -> Optional[dict]:
        """Analyse complète d'un match"""

        home = game.get('home_team', '')
        away = game.get('away_team', '')
        if not home or not away:
            return None

        # ── Cotes brutes ──
        h2h_odds = self.fetcher.extract_h2h(game)
        ou_data  = self.fetcher.extract_totals(game)
        if not h2h_odds:
            return None

        # ── Probabilités no-vig consensus ──
        consensus = self.prob_eng.get_consensus(
            h2h_odds, home, away
        )
        if consensus['books'] < 3:
            return None

        # ── Probabilités Elo (opinion indépendante) ──
        elo_home, elo_away = elo.predict(home, away)

        # ── Données ESPN ──
        home_inj   = injuries.get(home, {})
        away_inj   = injuries.get(away, {})
        home_stats = team_stats.get(home, {})
        away_stats = team_stats.get(away, {})

        espn_adj = espn.calculate_prob_adjustment(
            home_inj, away_inj, home_stats, away_stats
        )

        # ── Probabilité finale fusionnée ──
        # 45% consensus books + 35% Elo + 20% ESPN adjustment
        base_prob = (consensus['home'] * 0.45 +
                     elo_home         * 0.35 +
                     (consensus['home'] + espn_adj) * 0.20)
        base_prob = round(min(max(base_prob, 0.25), 0.85), 4)
        away_prob = round(1 - base_prob, 4)

        # ── Déterminer favori ──
        if base_prob >= away_prob:
            fav, fav_prob = home, base_prob
            dog, dog_prob = away, away_prob
        else:
            fav, fav_prob = away, away_prob
            dog, dog_prob = home, base_prob

        # ── Meilleures cotes ──
        best_fav = self.fetcher.find_best_odds(h2h_odds, fav)
        best_dog = self.fetcher.find_best_odds(h2h_odds, dog)

        if best_fav['odds'] <= 0:
            return None

        # ── EV ──
        fav_ev = calculate_ev(fav_prob, best_fav['odds'])
        dog_ev = calculate_ev(dog_prob, best_dog['odds'])

        # ── Décide sur quoi miser ──
        if dog_ev > fav_ev + 0.02 and dog_ev > 0.03:
            # Value sur l'underdog
            pick_team = dog
            pick_prob = dog_prob
            pick_odds = best_dog
            pick_ev   = dog_ev
            pick_type = "VALUE UPSET"
        else:
            pick_team = fav
            pick_prob = fav_prob
            pick_odds = best_fav
            pick_ev   = fav_ev
            pick_type = "FAVORI"

        # ── Score de confiance ──
        confidence = self._confidence_score(
            pick_prob, pick_ev, consensus,
            elo_home, base_prob,
            home_inj, away_inj
        )

        # ── Gardien NHL ──
        goalie_info = {}
        if sport == 'NHL':
            goalie_info = espn.get_nhl_confirmed_goalie('')

        # ── Mise Kelly ──
        stake = kelly_stake(pick_prob, pick_odds['odds'],
                            self.bankroll)
        pot_win = round(stake * (pick_odds['odds'] - 1), 2)

        # ── Heure locale ──
        start = game.get('commence_time', '')
        time_str = self._format_time(start)

        # ── Elo confirme ? ──
        elo_confirms = (
            (pick_team == home and elo_home > 0.52) or
            (pick_team == away and elo_away > 0.52)
        )

        return {
            'sport':         sport,
            'home_team':     home,
            'away_team':     away,
            'start_time':    time_str,
            'pick_team':     pick_team,
            'pick_type':     pick_type,
            'probability':   pick_prob,
            'best_odds':     pick_odds['odds'],
            'best_book':     pick_odds['book'],
            'ev':            pick_ev,
            'confidence':    confidence,
            'stake':         stake,
            'potential_win': pot_win,
            'books_count':   consensus['books'],
            'uncertainty':   consensus['uncertainty'],
            'consensus_prob': consensus['home'],
            'elo_prob':      elo_home,
            'espn_adj':      espn_adj,
            'elo_confirms':  elo_confirms,
            'home_injury':   home_inj.get('severity', 'FAIBLE'),
            'away_injury':   away_inj.get('severity', 'FAIBLE'),
            'injury_impact': max(home_inj.get('total_impact', 0),
                                 away_inj.get('total_impact', 0)),
            'key_injuries':  (home_inj.get('key_players', []) +
                              away_inj.get('key_players', [])),
            'goalie_info':   goalie_info,
            'ou_data':       ou_data,
            'all_odds':      h2h_odds,
            'data_freshness_mins': 0,
        }

    def _confidence_score(self, prob: float, ev: float,
                           consensus: dict,
                           elo_home: float, base_prob: float,
                           home_inj: dict, away_inj: dict) -> int:
        score = 0

        # Probabilité forte (0-25 pts)
        if prob >= 0.65:   score += 25
        elif prob >= 0.58: score += 17
        elif prob >= 0.53: score += 10

        # EV positif (0-25 pts)
        if ev > 0.06:   score += 25
        elif ev > 0.04: score += 17
        elif ev > 0.02: score += 10

        # Consensus élevé (0-20 pts)
        if consensus.get('confidence') == 'HIGH':   score += 20
        elif consensus.get('confidence') == 'MEDIUM': score += 12

        # Pinnacle utilisé (0-15 pts)
        if consensus.get('pinnacle_used'): score += 15

        # Elo proche du consensus (0-10 pts)
        if abs(elo_home - base_prob) < 0.05: score += 10

        # Pénalité blessures
        if home_inj.get('severity') == 'CRITIQUE': score -= 15
        elif home_inj.get('severity') == 'ÉLEVÉE': score -= 8
        if away_inj.get('severity') == 'CRITIQUE': score -= 10

        return max(min(score, 100), 0)

    def _global_select(self, all_picks: list,
                        max_total: int = 3) -> list:
        """
        Sélection finale — max 3 picks/jour
        Diversifie les sports
        """
        valid = []
        for pick in all_picks:
            qf = QualityFilter(pick['sport'])
            ok, reason = qf.validate(pick)
            pick['filter_result'] = reason
            if ok:
                valid.append(pick)

        def score(p):
            return (
                p.get('ev', 0)         * 350 +
                p.get('confidence', 0) * 0.30 +
                (1 if p.get('elo_confirms') else 0) * 12 +
                (1 if p.get('consensus', {}).get(
                    'pinnacle_used') else 0) * 10
            )

        sorted_picks = sorted(valid, key=score, reverse=True)

        # Max 2 par sport
        final, sport_count = [], {}
        for pick in sorted_picks:
            sport = pick['sport']
            if sport_count.get(sport, 0) < 2:
                final.append(pick)
                sport_count[sport] = sport_count.get(sport, 0) + 1
            if len(final) >= max_total:
                break

        return final

    def _format_time(self, utc_str: str) -> str:
        if not utc_str:
            return "TBD"
        try:
            dt = datetime.fromisoformat(
                utc_str.replace('Z', '+00:00')
            )
            return dt.astimezone(MONTREAL_TZ).strftime("%H:%M")
        except:
            return utc_str


# ══════════════════════════════════════════
# MODULE 8 — FORMATEUR TELEGRAM
# ══════════════════════════════════════════

def format_pick_message(pick: dict) -> str:
    """Formate un pick en message Telegram"""
    sport_e = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(
        pick['sport'], "🎯"
    )
    conf    = pick['confidence']
    conf_bar = "█" * (conf // 10) + "░" * (10 - conf // 10)

    # Niveau confiance
    if conf >= 75:   conf_label = "🔥 TRÈS HAUTE"
    elif conf >= 55: conf_label = "✅ HAUTE"
    else:            conf_label = "🟡 MODÉRÉE"

    # Elo confirme
    elo_str = ("✅ Elo confirme" if pick.get('elo_confirms')
               else "⚠️ Elo diverge")

    # Blessures
    inj_str = ""
    key_inj = pick.get('key_injuries', [])
    if key_inj:
        names   = ', '.join(
            f"{p['name']} ({p['status']})"
            for p in key_inj[:2]
        )
        inj_str = f"\n🏥 *Blessures :* _{names}_"

    # Top 3 cotes
    all_odds = pick.get('all_odds', {})
    team     = pick['pick_team']
    top_odds = sorted(
        [(bk, odds.get(team, 0))
         for bk, odds in all_odds.items()
         if odds.get(team, 0) > 0],
        key=lambda x: x[1],
        reverse=True
    )[:3]
    odds_str = "\n".join(
        f"   {'⭐' if i == 0 else '  '} "
        f"`{bk:<12}` → *{o:.3f}*"
        for i, (bk, o) in enumerate(top_odds)
    )

    # O/U
    ou = pick.get('ou_data', {})
    ou_str = ""
    if ou and ou.get('lean') not in [None, 'None']:
        ou_str = (
            f"\n📊 *O/U :* {ou['lean']} {ou.get('line', '')} "
            f"(`{ou['over_prob']:.0%}` over "
            f"/ `{ou['under_prob']:.0%}` under)"
        )

    # Gardien NHL
    goalie_str = ""
    if pick['sport'] == 'NHL':
        g = pick.get('goalie_info', {})
        if g.get('confirmed'):
            goalie_str = (
                f"\n🥅 *Gardien :* {g['name']} "
                f"(sv% {g.get('sv_pct', 0):.3f})"
            )
        else:
            goalie_str = "\n🥅 *Gardien :* TBD"

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{sport_e} *{pick['away_team']}*"
        f" @ *{pick['home_team']}*\n"
        f"🕐 {pick['start_time']} (Montréal)\n"
        f"\n🎯 *MISE SUR : {pick['pick_team'].upper()}*\n"
        f"   Type : _{pick['pick_type']}_\n"
        f"\n📈 *Probabilité :* `{pick['probability']:.0%}`\n"
        f"⚡ *EV :* `+{pick['ev']:.1%}`\n"
        f"🎚 *Confiance :* {conf_bar} "
        f"`{conf}/100` — {conf_label}\n"
        f"\n🔬 *Sources :*\n"
        f"   • Consensus {pick['books_count']} books : "
        f"`{pick['consensus_prob']:.0%}`\n"
        f"   • Elo Ultron : `{pick['elo_prob']:.0%}`\n"
        f"   • Ajust ESPN : `{pick['espn_adj']:+.1%}`\n"
        f"   • {elo_str}\n"
        f"{inj_str}"
        f"{goalie_str}"
        f"{ou_str}\n"
        f"\n💰 *Meilleures cotes :*\n"
        f"{odds_str}\n"
        f"\n💸 *Mise suggérée :* `${pick['stake']:.0f}`\n"
        f"✅ *Gain potentiel :* `+${pick['potential_win']:.0f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_daily_report(result: dict) -> list:
    """
    Formate le rapport complet du jour
    Retourne une liste de messages Telegram
    """
    messages = []
    picks    = result.get('picks', [])
    today    = result.get('date', str(date.today()))

    if not picks:
        return [(
            "🤖 *ULTRON v2.0*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "😴 Aucun pick à valeur aujourd'hui.\n"
            "_Ultron protège ta bankroll._\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )]

    # En-tête
    header = (
        f"🤖 *ULTRON v2.0 — {today}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *{len(picks)} pick(s) sélectionné(s)*\n"
        f"   sur {result.get('total_raw', 0)} analysés\n"
        f"💰 *Bankroll :* ${result.get('bankroll', 0):,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Modèle : Elo + No-Vig + ESPN + Régression_"
    )
    messages.append(header)

    # Un message par pick
    for pick in picks:
        messages.append(format_pick_message(pick))

    return messages


# ══════════════════════════════════════════
# TEST LOCAL
# ══════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Test Ultron v2.0...")
    engine   = UltronV2(bankroll=1000)
    result   = engine.run()
    messages = format_daily_report(result)

    print(f"\n{'='*55}")
    print(f"RÉSULTAT : {len(result['picks'])} picks")
    print(f"{'='*55}\n")

    for msg in messages:
        print(msg)
        print()
