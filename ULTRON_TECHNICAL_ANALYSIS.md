# ULTRON MULTISPORT v7.0 — COMPREHENSIVE TECHNICAL ANALYSIS

**Last Updated:** May 2026  
**Version:** 7.0  
**Status:** Production-ready multi-sport betting analysis system

---

## 1. MAIN ARCHITECTURE & SYSTEM FLOW

### 1.1 High-Level Design

ULTRON is a **multi-sport betting analysis engine** that analyzes sports matchups and generates predictions with confidence scores across three sports (NBA, NHL, MLB). The system is built around a **modular architecture** with layered responsibilities:

```
┌──────────────────────────────────────────────────────────────────┐
│                   ULTRON v7.0 ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Telegram Bot (FastAPI/python-telegram-bot)                      │
│  ├─ Commands: /nba, /nhl, /mlb, /pronostics, /daily_props       │
│  ├─ Rate limiting: @rate_limit(30s) on heavy commands            │
│  ├─ VIP Channel (all picks) + FREE Channel (top pick only)       │
│  └─ Scheduled Jobs: motivation (9h), auto-send (30min intervals) │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DATA LAYER - Real-time Data Fetching                   │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • ESPN API (scoreboard, teams, injuries, standings)   │   │
│  │   └─ Circuit breaker: 5 échecs → pause 60s auto       │   │
│  │ • nba_api (live NBA games — official NBA source)      │   │
│  │ • The Odds API (h2h, spreads, totals — TTL dynamique) │   │
│  │   └─ TTL <2h avant match: 5min | <6h: 30min | sinon 2h│   │
│  │ • Team Stats Cache (7 days — team strength/records)   │   │
│  │ • Player Props Cache (24h — ESPN player averages)     │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ PREDICTION LAYER - Scoring Engines (3-pillar system)  │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • MoneyLine: L10 form + ATS discipline + EV calc      │   │
│  │ • Spread (NBA)/Puckline (NHL)/Runline (MLB):          │   │
│  │   ATS L10 record (≥6/10 required) + margin analysis   │   │
│  │ • Over/Under: Projected totals vs line + L10 hit rate │   │
│  │ • ML Model (ModelRegistry): GradientBoosting/XGBoost  │   │
│  │   └─ Fallback automatique si fichier .pkl absent      │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ENRICHMENT LAYER - ESPN Advanced Stats                │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • NBA: Injuries + B2B detection + advanced stats      │   │
│  │ • NHL: Goalie confirmation + PP/PK + road trip        │   │
│  │ • MLB: Pitcher ERA + OPS + run differential           │   │
│  │ • Sharp Money: Line movement signals (seuil 0.08/0.15)│   │
│  └────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ PROBABILITY ENGINE - Fusion pondérée multi-signaux    │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • 40% modèle ML + 25% marché + 15% sharp + 10% inj   │   │
│  │ • ConfidenceEngine: calibration (déflation ≥75%)      │   │
│  │ • KellyEngine: half-Kelly, protégé div/zéro           │   │
│  │ • CLVTracker: suivi closing line value (edge réel)    │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ BRAIN LAYER - Auto-Learning & Optimization           │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • Track historical picks (picks_history.json)         │   │
│  │ • Calculate ROI, win rate by sport/type/confidence    │   │
│  │ • Update learned_thresholds.json dynamically          │   │
│  │ • Adjust model weights + confidence calibration       │   │
│  │ • PostgreSQL support (Railway DATABASE_URL)           │   │
│  │ • SHA-256 fingerprint deduplication (TTLCache 24h)    │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  DELIVERY LAYER - Telegram + Storage                            │
│  ├─ Persist picks → picks_history.json + PostgreSQL            │
│  ├─ Send notifications → VIP + FREE channels                   │
│  └─ Generate daily reports → win rate, ROI tracking            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Main Bot Flow

```
START (main.py / Dockerfile)
  ↓
load_config() — Validate TELEGRAM_TOKEN, CHAT_IDs, ODDS_API_KEY
  ↓
Build Telegram Application with handlers:
  ├─ /start, /help, /nba, /nhl, /mlb
  ├─ /pronostics <sport>
  ├─ /daily_props, /props_match, /player
  └─ Scheduled jobs:
      ├─ 09:00 Quebec: auto_daily_motivation() + injuries alert
      ├─ Every 30min: auto_send_pronostics() (main engine)
      └─ 23:00 Quebec: auto_daily_recap() + pick evaluation
  ↓
Application.run_polling() — Listen to Telegram updates
  ↓
[When match detected within 120 min window]
  ├─ Generate predictions (ML/Stats)
  ├─ Enrich with ESPN data
  ├─ Calculate confidence scores
  ├─ Fetch live odds (Odds API)
  ├─ Save to pick_memory
  ├─ Send to VIP (full picks) + FREE (top pick)
  └─ Track in _notified_pronostics (24h deduplication)
  ↓
[Daily at ~23h]
  ├─ Run ultron_brain analysis
  ├─ Update learned_thresholds.json
  ├─ Calculate daily ROI/win rate
  └─ Adjust model weights for tomorrow
```

### 1.3 Critical Constants & Configuration

```python
# QUEBEC TIMEZONE (all times displayed in America/Toronto)
QUEBEC_TZ = pytz.timezone('America/Toronto')

# TELEGRAM CHANNELS
TELEGRAM_CHAT_ID     = os.getenv('TELEGRAM_CHAT_ID')      # FREE public channel
TELEGRAM_CHAT_ID_VIP = os.getenv('TELEGRAM_CHAT_ID_VIP')  # VIP subscribers
TELEGRAM_TOKEN       = os.getenv('TELEGRAM_TOKEN')         # Bot auth

# ODDS API (Dynamic Caching — TTL varie selon proximité du match)
_ODDS_CACHE_TTL_NEAR  = 300    # 5 min si match dans < 2h
_ODDS_CACHE_TTL_MID   = 1800   # 30 min si match dans 2-6h
_ODDS_CACHE_TTL_FAR   = 7200   # 2h si match dans > 6h
_ODDS_API_CACHE = {sport_key: {"data": [...], "fetched_at": datetime}}
# Max quota: ~500 requests/month (shared across sports)

# ML MODELS — ModelRegistry (chargement avec fallback gracieux)
model_registry = ModelRegistry()  # Charge nba_model.pkl, props_model.pkl
# Si fichier absent: log warning, continue sans ML (pas de crash)

# PICK DEDUPLICATION — SHA-256 fingerprint + TTLCache 24h
pick_cache = TTLCache(maxsize=10_000, ttl=86400)
# fingerprint = sha256(f"{sport}_{matchup}_{pick_type}_{line}_{odds}")
# MD5 remplacé par SHA-256 (meilleure résistance aux collisions)
_notified_pronostics = {}  # {f"prono_{date}_{sport}_{away}_{home}": last_sent_time}
PRONO_RENOTIFY_HOURS = 24  # Don't re-send same pick for 24h

# MLB DAILY LIMIT
MLB_PICKS_MAX_PER_DAY = 5  # Prevent oversaturation
_mlb_picks_sent_today = {"date": None, "count": 0}

# RATE LIMITING (anti-spam Telegram)
_CMD_COOLDOWN_SECONDS = 15   # /pronostics: 30s | /picks, /daily_props: 60s
```

---

## 2. SPORTS SUPPORTED & ANALYZERS

### 2.1 Supported Sports

| Sport | League | Analyzer Module | Data Source | Season |
|-------|--------|-----------------|-------------|--------|
| **Basketball** | NBA | nba_moneyline_analyzer_advanced.py | ESPN API, nba_api | 2025-26 |
| **Hockey** | NHL | nhl_moneyline_analyzer_advanced.py | ESPN API | 2025-26 |
| **Baseball** | MLB | mlb_moneyline_analyzer_advanced.py | ESPN API | 2025 |

### 2.2 Prediction Types (3-Pillar Model)

Each sport has **3 independent prediction pillars**:

#### **PILLAR 1: MoneyLine (ML)**
- **Models**: 4-Factor statistical model + optional ML (GradientBoosting)
- **Inputs**: 
  - Team strength (win %)
  - Points for/against (PPG/PA for NBA, GF/GA for NHL, R/RA for MLB)
  - L10 form (last 10 games)
  - ATS discipline (against the spread track record)
  - Home advantage correction (calibrated by Ultron Brain)
- **Confidence Threshold**: ≥55% to qualify (62% to send as BUY)
- **Decision**: Market consensus vs. model blend (50-60% model weight)

#### **PILLAR 2: Spread/Puckline/Runline**
- **NBA Spread** (points): -3.5 to +10.0 range
- **NHL Puckline** (goals): ±1.5 (binary)
- **MLB Runline** (runs): ±1.5 (binary)
- **Requirement**: ATS L10 record ≥ 6/10 (disciplined betting)
- **Confidence Threshold**: ≥68% to send as BUY

#### **PILLAR 3: Over/Under (Totals)**
- **NBA**: ~225.5 total points
- **NHL**: ~5.5 total goals
- **MLB**: ~8.5 total runs
- **Model**: Projected totals vs line, hit rate L10
- **Confidence Threshold**: ≥65% to send as BUY

### 2.3 Analyzers Details

#### **nba_moneyline_analyzer_advanced.py**
- **Inputs**: 
  - Team schedule (rest days, B2B detection)
  - Advanced stats (NetRtg, pace, efficiency)
  - Injuries (impact adjustment per player)
  - Odds data (line movement, sharp signals)
- **Special Features**:
  - **B2B Penalty**: -12% confidence if team on back-to-back
  - **Injury Impact**: -15 pts per key player OUT, -7 per QUESTIONABLE
  - **Sharp Money**: Detect if large bet volumes shift line
- **Confidence Range**: 0-100 (target send: ≥62)

#### **nhl_moneyline_analyzer_advanced.py**
- **Inputs**:
  - Goalie confirmation (starter vs. backup)
  - PP/PK percentages
  - Road trip status (penalty for multi-game road trips)
  - Injuries (defensemen/forwards tracked separately)
- **Special Features**:
  - **Backup Goalie Penalty**: -20% confidence
  - **Road Trip Penalty**: -10% if 4+ games away
  - **PP/PK Bonus**: +8% if PP/PK in top 10% league-wide
- **Confidence Range**: 0-100 (target send: ≥62)

#### **mlb_moneyline_analyzer_advanced.py**
- **Inputs**:
  - Pitcher ERA, WHIP
  - OPS (team offensive power)
  - Run differential (runs scored - runs allowed)
  - Last 10 games record
- **Special Features**:
  - **Ace Pitcher Bonus**: +18% if starting pitcher ERA ≤ 3.00
  - **Weak Pitcher Penalty**: -15% if ERA ≥ 5.00
  - **Live Stats**: Fetches W-L records from ESPN scoreboard (updated daily)
- **Confidence Range**: 0-100 (target send: ≥55)

---

## 3. CORE FEATURES & ANALYSIS ENGINES

### 3.1 Confidence Score Calculation

```python
# MONEYLINE SCORING FORMULA
base_score = 50

# 1. EV vs Market (Edge Valuation)
ev = (my_prob * decimal_odds) - 1
if ev > 0.05:           # Positive EV (edge)
    base_score += 20
elif abs(model_prob - market_prob) > 3%:
    base_score += 10    # Divergence signal

# 2. Form (L10 Record)
if team_l10_pct >= 70%: # 7+ wins in last 10
    base_score += 15
elif team_l10_pct <= 30%:
    base_score -= 15    # Cold streak penalty

# 3. ATS Discipline
if team_ats_pct >= 60%: # Covering 6+ spreads
    base_score += 12
elif team_ats_pct <= 40%:
    base_score -= 8     # Poor ATS penalty

# 4. ESPN/Context Adjustment (optional)
if injuries_impact < 0:
    base_score -= (|impact| * 5)
if sharp_money_detected:
    base_score += 20    # Market sharp signal

FINAL_SCORE = max(0, min(100, base_score))
SEND = FINAL_SCORE >= 62
```

### 3.2 Expected Value (EV) Calculation

```python
# TRUE EV Formula (Kelly-based)
EV = (probability * decimal_odds) - 1

# Interpretation:
#  EV = +0.05  (+5%)  → BUY (positive expectancy)
#  EV = 0.00           → FAIR (break-even)
#  EV = -0.02  (-2%)   → PASS (negative edge)

# Example:
# Celtics: my_prob=55%, odds=1.90
# EV = (0.55 * 1.90) - 1 = +0.045 (+4.5%)  ✅ BUY
```

### 3.3 Kelly Criterion & Bankroll Management

```python
# HALF-KELLY STAKE (conservative) — protégé division par zéro
def calculate_stake(probability, odds, bankroll):
    b = odds - 1
    if b <= 0:
        return 0.0  # Cote ≤ 1.0 = aucune valeur possible
    q = 1 - probability
    kelly = ((b * probability) - q) / b
    half_kelly = max(0.0, kelly * 0.5)  # Jamais négatif
    return bankroll * half_kelly

# Where:
#  b = decimal_odds - 1
#  p = my_probability
#  q = 1 - p
#  bankroll = total betting bank

# Example: 1% bankroll with $10k bank = $100 per pick
```

### 3.4 Confidence Calibration

```python
# ConfidenceEngine — déflation légère des hautes probabilités
def calibrate(probability):
    confidence = probability * 100
    if confidence >= 75:
        confidence *= 0.95  # Évite sur-confiance sur matchs serrés
    return round(confidence, 2)

# Raison: les picks à 75%+ sont souvent surestimés par le modèle.
# La déflation de 5% les ramène à un niveau plus réaliste.
```

### 3.5 Probability Engine (Fusion Pondérée)

```python
# Poids des signaux (calibrés empiriquement)
final_probability = (
    0.40 * model_probability    # ML ou stats sport-specific
  + 0.25 * market_probability   # Cote implicite du marché
  + 0.15 * sharp_signal         # Mouvement de ligne sharp
  + 0.10 * injury_factor        # Impact des blessures
  + 0.10 * schedule_factor      # B2B, road trips, repos
)
final_probability = max(0.01, min(0.99, final_probability))
```

### 3.6 CLV Tracker (Closing Line Value)

```python
# CLV = mesure si on a battu la cote de fermeture
# Une CLV positive = edge réel détecté AVANT le marché
def calculate_clv(sent_line, closing_line):
    return closing_line - sent_line  # Positif = on était ahead

# Exemple:
# Cote envoyée: 1.90, Cote fermeture: 1.72
# CLV = 1.72 - 1.90 = -0.18  ❌ Le marché a bougé contre nous
#
# Cote envoyée: 1.90, Cote fermeture: 2.05
# CLV = 2.05 - 1.90 = +0.15  ✅ On a eu meilleure valeur

# Objectif long terme: CLV moyen > 0 = edge systématique
```

### 3.8 Sharp Money Detection

```python
# Détecte si un mouvement de cote est causé par l'argent sharp
def detect_sharp_action(opening_odds, current_odds):
    movement = abs(current_odds - opening_odds)
    if movement >= 0.15:
        return 0.75   # Fort signal sharp → forte conviction
    if movement >= 0.08:
        return 0.60   # Signal modéré
    return 0.50        # Neutre (pas de détection)

# Ce signal pèse 15% dans le ProbabilityEngine
```

### 3.9 Hedge Strategy (Risk Mitigation)

```python
# HEDGE STRUCTURE (optional protection)
main_stake = kelly_stake(main_prob, main_odds, bankroll, 0.5)
hedge_stake = main_stake * 0.35  # 35% offset

# Outcomes:
#  If main wins: profit = main_stake * (odds-1) - hedge_stake
#  If hedge wins: profit = hedge_stake * (odds-1) - main_stake
#  Best case: +50-100% of hedge stake
#  Worst case: protected by hedge (limit loss)
```

### 3.10 Player Props Analysis (NBA Stars)

**Database**: ~60 NBA star players with props (ESPN averages)

```python
# MODEL: XGBoost Regressor (trained on historical data)
# INPUT FEATURES:
#  - Player season average (e.g., Tatum 27.5 PPG)
#  - Opponent defense efficiency
#  - Home/Away factor (-1.5 pts on road)
#  - Injury status of teammates
#  - Pace differential

# PREDICTION ADJUSTMENTS:
if player_recent_avg > 22:
    calibration_boost = 1.02  # Hot player
elif player_recent_avg > 18:
    calibration_boost = 1.01  # Good form
else:
    calibration_boost = 1.00  # Neutral

predicted_points = model_output * calibration_boost
# Clamp to realistic range [3, 60]
```

---

## 4. DATA SOURCES & REAL-TIME INTEGRATION

### 4.1 Primary Data Sources

| Source | Use Case | Update Frequency | Reliability |
|--------|----------|------------------|-------------|
| **ESPN API** | Games, scores, standings, injuries | Real-time | Very High |
| **nba_api** | Official NBA live games | Real-time | High |
| **The Odds API** | MoneyLine, spreads, totals from 10+ books | Dynamic TTL (5min/30min/2h) | High |
| **sportsreference.com** | Historical team stats (optional) | Daily | Medium |
| **PostgreSQL (Railway)** | Persistent pick history | On-write | High |
| **JSON Local Storage** | Cache + learned parameters | On-update | High |

### 4.2 Caching Strategy

```python
# TEAM STATS CACHE (7 days)
_TEAM_STATS_CACHE = {}
_TEAM_STATS_CACHE_TIME = {}
_TEAM_STATS_TTL_SECONDS = 7 * 24 * 3600

# PLAYER PROPS CACHE (24 hours)
_PLAYER_PROPS_CACHE = {}
_PLAYER_PROPS_CACHE_DATE = ""  # YYYY-MM-DD

# ODDS API CACHE — TTL DYNAMIQUE (nouveau en v7)
# Le TTL varie selon la proximité du match:
class DynamicTTL:
    def get_ttl(self, starts_at):
        delta = (starts_at - datetime.utcnow()).total_seconds()
        if delta <= 7_200:    # < 2h avant le match
            return 300        # 5 min (cotes bougent vite)
        if delta <= 21_600:   # < 6h avant le match
            return 1_800      # 30 min
        return 7_200          # 2h (matchs lointains)

# PICK DEDUPLICATION CACHE (24h)
pick_cache = TTLCache(maxsize=10_000, ttl=86400)
# Clé: SHA-256 de (sport + matchup + pick_type + line + odds)

# MATCHES CACHE (2 minutes)
MATCHES_CACHE_NBA = []
MATCHES_CACHE_NHL = []
MATCHES_CACHE_MLB = []
MATCHES_CACHE_TIME = None
```

### 4.3 API Call Economy

**Goal**: Minimize quota usage (Odds API = ~500 req/month limit)

```
# DAILY CALL PATTERN (estimated):
09:00 Quebec    : Motivation + injuries alert (1 ESPN call)
Every 30 min    : Check matches (3 ESPN calls, 1 Odds API per sport if matches found)
23:00 Quebec    : Daily recap (1 ESPN call)
23:30 Quebec    : Brain analysis (file I/O only)

# PER SPORT:
Odds API: ~1 call per 4h IF matches exist = 6 calls/day max × 3 sports = ~18/day
ESPN:     ~5-10 calls/day (matches + injuries + standings)
TOTAL:    ~25-30 API calls/day (very conservative)
```

---

## 5. BETTING METRICS & TRACKING

### 5.1 Per-Pick Metrics

```python
{
    "pick_id": "uuid",
    "date_sent": "2026-05-10",
    "sport": "NBA",
    "type": "MoneyLine|Spread|O/U|Props",
    "pick": "Celtics ML",
    "odds": 1.95,
    "confidence": 65,
    "ev_pct": 4.5,
    "bankroll_pct": 1.0,  # 1% bankroll = $100
    "status": "BUY|MONITORING|PASS",
    "channel": "VIP|FREE",
    "fingerprint": "sha256hex",  # Déduplication (nouveau v7)
    "clv": +0.12,               # Closing Line Value (nouveau v7)
    
    # RESULT (filled after game)
    "result": "WIN|LOSS|VOID|PENDING",
    "profit": 95.00,  # $95 win on $100 stake
    "roi": 95.0,      # 95% return
}
```

### 5.2 Aggregate Statistics

```python
# DAILY REPORT:
{
    "date": "2026-05-10",
    "picks_sent": {
        "nba": {"buy": 3, "monitoring": 2, "pass": 5},
        "nhl": {"buy": 2, "monitoring": 1, "pass": 3},
        "mlb": {"buy": 0, "monitoring": 0, "pass": 2},  # Capped at 5/day
    },
    "results": {
        "wins": 4,
        "losses": 2,
        "pending": 3,
        "win_rate": 66.7,
    },
    "roi": {
        "total_risked": 600,
        "total_won": 642,
        "net_profit": 42,
        "roi_pct": 7.0,
    },
    "confidence_buckets": {
        "high (65+)": {"w": 3, "l": 1, "roi": 150},
        "medium (55-64)": {"w": 1, "l": 1, "roi": 0},
        "low (-54)": {"w": 0, "l": 0, "roi": 0},
    }
}

# WEEKLY SUMMARY (7-day rolling)
# MONTHLY SUMMARY (30-day rolling)
```

### 5.3 Learned Thresholds (Ultron Brain)

```python
{
    "min_confidence": {
        "NBA": 58,      # Updated from 55 if ROI improves at 58+
        "NHL": 58,
        "MLB": 58,
    },
    "min_ev_pct": {
        "NBA": 0.5,     # Minimum EV edge required
        "NHL": 0.5,
        "MLB": 0.0,
    },
    "best_pick_types": {
        "NBA": ["ML", "Spread"],      # BANNED: O/U if hit rate < 50%
        "NHL": ["ML", "Puckline"],
        "MLB": ["ML"],                # BLOCKED: Runline if ATS < 40%
    },
    "model_adjustments": {
        "NBA": {
            "model_weight": 0.60,                    # 60% ML model, 40% market
            "confidence_scale": 1.05,                # We're 5% too confident
            "home_advantage_delta": +0.02,           # Home wins 2% more
        },
        "NHL": {
            "model_weight": 0.50,
            "confidence_scale": 0.95,                # We're 5% overconfident
            "home_advantage_delta": +0.01,
        },
        "MLB": {
            "model_weight": 0.55,
            "confidence_scale": 1.00,
            "home_advantage_delta": 0.00,
        },
    },
    "sample_size": 487,
    "updated_at": "2026-05-09T23:30:00",
    "roi_overall": 3.2,
    "win_rate_overall": 54.1,
}
```

---

## 6. DATABASE INTEGRATION

### 6.1 PostgreSQL (Railway)

```sql
-- TABLE: pick_store (JSONB storage)
CREATE TABLE IF NOT EXISTS pick_store (
    id   INTEGER PRIMARY KEY DEFAULT 1,
    data JSONB NOT NULL
);

-- Example data:
{
  "picks_all_time": [...],
  "daily_reports": {...},
  "learned_thresholds": {...},
}

-- Usage in Python:
DATABASE_URL = os.environ.get("DATABASE_URL")  # Railway injects this
# Format: postgresql://user:password@host:port/database
```

### 6.2 Local JSON Storage (Fallback)

```python
# FILES:
"/data/picks_history.json"        # All picks + results (persistent)
"/data/backup_meta.json"          # Backup metadata
"/data/learned_thresholds.json"   # Ultron Brain updates
"/data/brain_analysis.json"       # Last analysis report

# On Railway: /data = Volume (persistent across restarts)
# Local dev: ./ = current directory
```

### 6.3 Telegram Cloud Backup

```python
# BACKUP STRATEGY (auto-daily):
# 1. Get picks history from JSON/PostgreSQL
# 2. Compress to CSV
# 3. Send as file to Telegram VIP channel (backup)
# 4. Store locally for restore

# RESTORE (if file system corrupted):
# /restore_backup — download from Telegram
```

---

## 7. TELEGRAM BOT INTEGRATION

### 7.1 Channel Setup

| Channel | Audience | Content | Limit |
|---------|----------|---------|-------|
| **FREE** | Public | Top pick only (highest confidence per hour) | Public (no limit) |
| **VIP** | Subscribers | All 3-pillar picks (ML, Spread, O/U) + props | ~10-15 per day |

### 7.2 Commands

```
/start              — Welcome menu
/help               — Full command list

# LIVE GAMES
/nba                — NBA teams in action TODAY
/nhl                — NHL teams in action TODAY
/mlb                — MLB teams in action TODAY

# PREDICTIONS
/pronostics nba     — All NBA picks (BUY/MONITORING/PASS tiers)
/pronostics nhl     — All NHL picks
/pronostics mlb     — All MLB picks

# PLAYER PROPS
/daily_props        — All NBA star props for today's games
/props_match [T1] vs [T2] — Props for specific matchup
/player [name]      — Single player analysis (Tatum, LeBron, etc.)
/all_props          — List all tracked stars

# ESPN LIVE
/boxscore nba       — Live box scores (scores, stats)
/boxscore nhl       — Live hockey stats
/boxscore mlb       — Live baseball stats
/leaders nba        — Season leaders (PPG, assists, rebounds)
/leaders nhl        — Season leaders (goals, assists, +/-)
/leaders nfl        — Season leaders (passing, rushing, etc.)

# ADMIN
/analyse            — Trigger Ultron Brain analysis
/test               — Send test notification
```

### 7.3 Message Format (AUTO_SEND)

```
🏀 ULTRON v7.0 — MoneyLine Guide
═══════════════════════════════════════════════════════════

🎯 Celtics @ Heat
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 19:30 (Québec) | 💼 DraftKings
💵 Cote: 1.95
✅ BUY (EV: +4.5%)

📊 ML: 🟢 Celtics ML @ 1.95
   Confiance: 68/100 | L10: 8-2 | ATS: 7-3

📏 SPREAD: 🟢 Celtics -2.5 @ 1.90
   Confiance: 62/100 | Spread favorable

🔢 TOTAL: 🟢 Over 225.5 @ 1.90
   Confiance: 55/100 | Hit rate L10: 62%

📈 Motivation: "Discipline beats motivation every day"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 FREE: Top pick only | VIP: Full 3-pillar analysis
```

---

## 8. DEPLOYMENT

### 8.1 Railway Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-u", "main.py"]
```

```yaml
# railway.json (config)
{
  "build": {"builder": "dockerfile"},
  "deploy": {
    "startCommand": "python -u main.py",
    "restartPolicyMaxRetries": 5
  }
}
```

### 8.2 Environment Variables (Railway Settings)

```
TELEGRAM_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_CHAT_ID_VIP=-1001234567891
ODDS_API_KEY=your_key_here
DATABASE_URL=postgresql://user:pass@host:port/db
RAILWAY_ENVIRONMENT=production
```

### 8.3 Startup Flow

```bash
# 1. Load config (validate tokens)
# 2. Initialize PostgreSQL (if DATABASE_URL set)
# 3. Load learned_thresholds.json (Ultron Brain state)
# 4. Train ML models (GradientBoosting NBAmodel, XGBoost props)
# 5. Start Telegram bot (polling mode)
# 6. Schedule jobs (motivation, auto_send_pronostics, recap)
# 7. Listen for commands and scheduled tasks
```

### 8.4 Logs & Monitoring

```
bot.log           — All events
bot_error.log     — Errors and warnings
bot_debug.log     — Debug-level details

# Log rotation: daily
```

---

## 9. CURRENT LIMITATIONS & BOTTLENECKS

### 9.1 Technical Limitations

| Issue | Impact | Workaround |
|-------|--------|-----------|
| **Odds API Quota (500/month)** | Stops after quota → no live odds | Dynamic TTL (5min/30min/2h), limit checks to 120-min window |
| **ESPN Data Delays** | Injuries/stats lag 5-10 min | Accept slight delay, validate before SEND |
| **ESPN API Instability** | 500/503 errors aléatoires | Circuit breaker: 5 échecs → pause 60s auto |
| **Railway Filesystem (ephemeral)** | Loses pick history on restart | Use Volume mount + PostgreSQL backup |
| **nba_api Intermittent** | Occasional 503 errors | Fallback to ESPN API automatically |
| **sportsreference Slow** | 30+ sec per team load | Make optional, use static fallback |
| **SQLite pool_size warnings** | Warning au démarrage | Pool args appliqués seulement si PostgreSQL détecté |

### 9.2 Missing Features / Areas for Improvement

#### **HIGH PRIORITY**

1. **NFL Integration**
   - **Why**: 3rd major sport, massive betting volume
   - **Effort**: Moderate (copy NBA pattern)
   - **Status**: Partially started in file structure

2. **Live Game Adjustments**
   - **Current**: Only pre-game picks
   - **Needed**: Adjust confidence in-game for injuries, score swings
   - **Effort**: Medium (requires real-time ESPN updates)

3. **Propensity Modeling**
   - **Current**: Simple averaging for props
   - **Needed**: XGBoost with 100+ features (opponent def, days rest, etc.)
   - **Effort**: High (data collection + tuning)

4. **Telegram VIP Gateway**
   - **Current**: Manual invitation only
   - **Needed**: Subscription/payment integration
   - **Effort**: High (complex, regulatory)

#### **MEDIUM PRIORITY**

5. **Line Movement API**
   - **Current**: Can't detect sharp money movements
   - **Needed**: Monitor line changes throughout day
   - **Effort**: Medium (periodic polls to Odds API)

6. **Player Availability Confirmation**
   - **Current**: Injuries listed but game-day confirmations lag
   - **Needed**: Real-time player status API
   - **Effort**: Low-Medium (ESPN gamebooks have this)

7. **Parlay Optimizer**
   - **Current**: Manual parlay suggestions only
   - **Needed**: Auto-suggest high-correl parlay combos
   - **Effort**: Medium (optimization algorithm)

8. **Advanced Props (Assist, Rebounds, etc.)**
   - **Current**: Points only (most mature)
   - **Needed**: Full suite (A+R+B combos, player duels)
   - **Effort**: High (new trainers for each prop type)

#### **LOW PRIORITY**

9. **Hedging Automation**
   - **Current**: Suggest hedge, user manually places
   - **Needed**: Auto-place hedge on partner sportsbook API
   - **Effort**: Very High (sportsbook integrations)

10. **Historical Match Simulator**
    - **Current**: No backtesting framework
    - **Needed**: Replay picks against historical odds
    - **Effort**: Medium (data collection)

### 9.3 Optimization Opportunities

| Optimization | Benefit | Effort |
|--------------|---------|--------|
| **Batch ESPN calls** | 50% less latency | Easy |
| **Cache spreads for 24h** | Reduce Odds API quota | Low |
| **Pre-train models** during off-season | Faster startup | Medium |
| **Implement ELO for teams** | Better team strength tracking | Medium |
| **Multi-threading for enrichment** | Parallel ESPN queries | Medium |
| **Redis cache layer** | Faster asset retrieval, Railway-compatible | High |

---

## 10. CRITICAL FUNCTIONS BY MODULE

### 10.1 **ultron_multisports_v6_0.py** + **ultron_v7_core.py** (Main)

| Function | Purpose | Criticality |
|----------|---------|------------|
| `get_live_matches_nba()` | Fetch NBA games from ESPN API | **CRITICAL** |
| `generate_prediction_nba()` | ML + Stats blend for NBA picks | **CRITICAL** |
| `score_moneyline_enhanced()` | Confidence calc (L10 + ATS + EV) | **CRITICAL** |
| `auto_send_pronostics()` | Scheduled job that sends picks | **CRITICAL** |
| `fetch_odds_api()` | Get real-time odds with dynamic TTL | **HIGH** |
| `enrich_*_score()` (3 variants) | Add ESPN advanced data to picks | **HIGH** |
| `predict_player_points()` | XGBoost-based prop prediction | **MEDIUM** |
| `ESPNClient.get_games()` | ESPN fetch + circuit breaker | **HIGH** |
| `KellyEngine.fraction()` | Half-Kelly stake (div-by-zero safe) | **HIGH** |
| `CLVTracker.log()` | Record closing line value per pick | **MEDIUM** |
| `ModelRegistry.predict()` | ML inference + fallback gracieux | **MEDIUM** |

### 10.2 **pick_memory.py**

| Function | Purpose |
|----------|---------|
| `save_pick()` | Log new pick to history |
| `check_and_update_results()` | Mark pick as WIN/LOSS after game |
| `format_daily_report()` | Generate daily recap message |
| `backup_to_telegram()` | Cloud backup of history |
| `restore_from_telegram()` | Restore history from Telegram |

### 10.3 **ultron_brain.py**

| Function | Purpose |
|----------|---------|
| `run_analysis()` | Analyze ROI by confidence/type/sport |
| `get_model_adjustments()` | Return learned calibration params |
| `should_send_pick()` | Filter by learned thresholds |
| `format_brain_report()` | Generate analysis report |

### 10.4 **{nba,nhl,mlb}_moneyline_analyzer_advanced.py**

| Function | Purpose |
|----------|---------|
| `get_*_games_today()` | ESPN scoreboard fetch |
| `get_team_id()` | ESPN team ID lookup |
| `get_team_schedule()` | Last 10 games + B2B detection |
| `get_*_injuries()` | Injury list from ESPN |
| `score_moneyline()` | Advanced scoring with all factors |

### 10.5 **espn_context.py**

| Function | Purpose |
|----------|---------|
| `get_full_context_all_sports()` | Master call: injuries + standings + leaders |
| `format_injuries_alert()` | Format injury notification |
| `get_games_with_context()` | Games + injuries + key stats |
| `find_game_context()` | Lookup specific game data |
| `get_live_player_props()` | ESPN season averages for stars |

---

## 11. QUICK-START GUIDE FOR DEVELOPERS

### To Add a New Sport (e.g., NFL)

1. **Create analyzer module**: `nfl_moneyline_analyzer_advanced.py`
   - Copy NBA/NHL pattern
   - Adjust metrics: yards, TDs, pass/rush splits

2. **Add to main**: `ultron_multisports_v6_0.py`
   - Import + availability check
   - Add `get_live_matches_nfl()` function
   - Write `generate_prediction_nfl()` function
   - Add to `auto_send_pronostics()` loop

3. **Add Telegram command**: `/pronostics nfl`

4. **Validate**:
   - Test with `/pronostics nfl` command
   - Verify picks generate with high confidence
   - Check send format

### To Integrate a New ML Model (ModelRegistry):

1. Train model, save as `models/nfl_model.pkl`
2. Register in `ModelRegistry` with sport key + version string
3. Call `model_registry.predict(sport, features)` in pick engine
4. If file absent, system falls back silently (no crash)

### To Read CLV Trends:

1. After game closes, `CLVTracker.log(pick_id, sent_odds, closing_odds)` is called
2. Check `clv_log.json` for all recorded entries
3. Positive average CLV = system is consistently finding edge before the market

### To Update Learned Thresholds:

- Ultron Brain auto-updates every night at 23:30
- Manual override: Edit `learned_thresholds.json`
- Restart bot to apply new weights

### To Debug a Low Win Rate:

1. Check `brain_analysis.json` (last analysis report)
2. Look for problematic `pick_type` or `confidence_bucket`
3. Review `model_adjustments` — may need lower `model_weight`
4. Analyze recent picks: Were they trending down in confidence?

---

## 12. PERFORMANCE METRICS & BENCHMARKS

| Metric | Target | Current |
|--------|--------|---------|
| **API Response Time** | <5s per pick generation | ~3-4s |
| **Telegram Message Latency** | <2s after pick generated | ~1-2s |
| **Database Write** | <100ms | ~50-80ms (PostgreSQL) |
| **Odds API Quota** | <30 calls/day | ~18-25 calls/day |
| **Win Rate (All)** | >52% (break-even) | ~54% |
| **Win Rate (BUY picks)** | >55% | ~56% |
| **ROI (All)** | >0% (positive) | ~+2-3% |
| **Uptime** | >99% | ~98% (rare errors) |

---

## CONCLUSION

**ULTRON v7.0** is a **production-ready, modular sports betting analysis system** with:

- ✅ **Multi-sport coverage** (NBA, NHL, MLB)
- ✅ **Real-time data integration** (ESPN + circuit breaker, nba_api, Odds API dynamic TTL)
- ✅ **Advanced scoring engines** (probabilistic fusion 5-signaux, EV-based)
- ✅ **Self-learning system** (Ultron Brain, adaptive thresholds)
- ✅ **Persistent tracking** (PostgreSQL + JSON backup)
- ✅ **Telegram integration** (VIP + FREE channels, rate limiting)
- ✅ **Deployment-ready** (Dockerfile, Railway config)
- ✅ **CLV tracking** (mesure de l'edge réel vs marché)
- ✅ **SHA-256 pick deduplication** (TTLCache 24h anti-doublon)
- ✅ **Kelly Engine** (half-Kelly protégé div/zéro)
- ✅ **ModelRegistry** (versionning ML + fallback gracieux)

**Next steps for improvement**:
1. **Add NFL** (~1-2 weeks)
2. **Implement live game adjustments** (~2-3 weeks)
3. **Advanced props modeling** (ongoing)
4. **Line movement tracking** (déjà partiel avec Sharp Money Detection 15%)
5. **VIP monetization** (complex, regulatory)

---

## 13. CHANGELOG V7.0

### New Features Added in v7.0

| Feature | Description | Impact |
|---------|-------------|--------|
| **SHA-256 Fingerprinting** | Remplacement de MD5 pour la déduplication des picks | Sécurité, collision resistance |
| **Dynamic TTL Cache** | TTL varie selon proximité du match (5min/30min/2h) | Cotes toujours fraiche avant match |
| **Circuit Breaker ESPN** | 5 échecs HTTP → pause automatique 60s | Stabilité, évite ban IP |
| **CLV Tracker** | Suivi de la Closing Line Value par pick | Mesure l'edge réel vs marché |
| **Probability Engine** | Fusion 5-signaux (ML 40%, marché 25%, sharp 15%, inj 10%, planning 10%) | Meilleure calibration |
| **Confidence Calibration** | Déflation 5% pour picks ≥75% (anticorps sur-confiance) | Précision accrue |
| **KellyEngine safe** | Protection division par zéro si b ≤ 0 | Plus de crash sur cotes ≤1.0 |
| **ModelRegistry** | Versioning ML + chargement pkl avec fallback auto | Robustesse en production |
| **Session aiohttp réutilisée** | ESPNClient garde 1 session ouverte | -30% overhead réseau |
| **PostgreSQL pool guard** | pool_size/max_overflow ignorés si SQLite | Élimine les warnings |
| **Semaphore per-instance** | asyncio.Semaphore créé dans le bon event loop | Fix race condition asyncio |
| **Rate limiting** | @rate_limit(30s/60s) sur commandes lourdes | Anti-spam Telegram |
| **Sharp Money threshold** | Seuils 0.08/0.15 documentés et appliqués | Signal plus précis |
| **team_name_match strict** | Stopwords + tokenisation pour matcher ESPN ↔ Odds API | Moins de faux positifs |

---

*Document compiled: May 22, 2026 | Codebase: ultron_multisports_v6_0.py*
