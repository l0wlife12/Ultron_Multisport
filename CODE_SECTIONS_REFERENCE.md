# KEY CODE SECTIONS - Match Fetching Implementation

## File: `ultron_multisports_v6_0.py`

### 1. CACHE INITIALIZATION (Lines 160-163)
```python
# Cache des matchs par sport
MATCHES_CACHE_NBA = []
MATCHES_CACHE_NHL = []
MATCHES_CACHE_NFL = []
MATCHES_CACHE_TIME = None
```

### 2. NOTIFICATION DE-DUPLICATION (Line 2938)
```python
_notified_pronostics = set()
```

---

## GET_LIVE_MATCHES_NBA() - Full Implementation (Lines 793-861)

```python
def get_live_matches_nba() -> list:
    """Récupère les matchs NBA en direct (nba_api > ESPN > DÉMO)"""
    global MATCHES_CACHE_NBA, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NBA and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NBA
    
    # Essayer nba_api d'abord (données officielles)
    if NBA_API_AVAILABLE:
        try:
            matches = get_live_nba_games_api()
            if matches:
                MATCHES_CACHE_NBA = matches
                MATCHES_CACHE_TIME = datetime.datetime.now()
                logger.info(f"✅ {len(matches)} matchs NBA depuis nba_api")
                return matches
        except Exception as e:
            logger.debug(f"⚠️ nba_api erreur: {e}")
    
    # Fallback sur ESPN API
    try:
        today = datetime.datetime.now()
        
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed']
                        if not any(word in status_desc for word in blocked_statuses):
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                
                                if away and home:
                                    daily_matches.append((away, home))
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NBA = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    logger.info(f"✅ {len(daily_matches)} matchs NBA depuis ESPN")
                    return daily_matches
        
        logger.info("ℹ️ Aucun match NBA trouvé sur ESPN (hors saison?)")
    
    except Exception as e:
        logger.error(f"❌ Erreur ESPN NBA: {e}")
    
    return []
```

**Key Features:**
- 120-second cache with shared timer
- Falls back from nba_api to ESPN
- Searches 7 days forward
- Filters out Final/Completed/Cancelled/Postponed
- Returns empty list on failure

---

## GET_LIVE_MATCHES_NHL() - Full Implementation (Lines 684-735)

```python
def get_live_matches_nhl() -> list:
    """Récupère les matchs NHL en direct (ESPN API)"""
    global MATCHES_CACHE_NHL, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NHL and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NHL
    
    try:
        today = datetime.datetime.now()
        
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed']
                        if not any(word in status_desc for word in blocked_statuses):
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                
                                if away and home:
                                    daily_matches.append((away, home))
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NHL = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    return daily_matches
        
        logger.info("ℹ️ Aucun match NHL dans les 7 prochains jours (hors saison)")
        MATCHES_CACHE_NHL = []
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return []
    
    except Exception as e:
        logger.error(f"❌ Erreur NHL: {e}")
        return []
```

---

## GET_LIVE_MATCHES_NFL() - Full Implementation (Lines 738-789)

```python
def get_live_matches_nfl() -> list:
    """Récupère les matchs NFL en direct (ESPN API)"""
    global MATCHES_CACHE_NFL, MATCHES_CACHE_TIME
    
    if MATCHES_CACHE_NFL and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NFL
    
    try:
        today = datetime.datetime.now()
        
        for day_offset in range(7):
            search_date = today + datetime.timedelta(days=day_offset)
            date_str = search_date.strftime("%Y%m%d")
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                daily_matches = []
                
                for event in data.get('events', []):
                    try:
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                        
                        blocked_statuses = ['final', 'completed', 'cancelled', 'postponed']
                        if not any(word in status_desc for word in blocked_statuses):
                            if len(competitors) >= 2:
                                away = competitors[0].get('team', {}).get('name', '').strip()
                                home = competitors[1].get('team', {}).get('name', '').strip()
                                
                                if away and home:
                                    daily_matches.append((away, home))
                    except Exception:
                        continue
                
                if daily_matches:
                    MATCHES_CACHE_NFL = daily_matches
                    MATCHES_CACHE_TIME = datetime.datetime.now()
                    return daily_matches
        
        # Aucun match réel trouvé — ne jamais utiliser de faux matchs
        logger.info("ℹ️ Aucun match NFL dans les 7 prochains jours (hors saison)")
        MATCHES_CACHE_NFL = []
        MATCHES_CACHE_TIME = datetime.datetime.now()
        return []
    
    except Exception as e:
        logger.error(f"❌ Erreur NFL: {e}")
        return []
```

---

## GET_LIVE_NBA_GAMES_API() - Full Implementation (Lines 431-461)

```python
def get_live_nba_games_api():
    """Récupère les matchs NBA en direct depuis nba_api"""
    if not NBA_API_AVAILABLE:
        logger.warning("⚠️ nba_api non disponible - Utilisant ESPN")
        return None
    
    try:
        sb = scoreboard.ScoreboardV2()
        games = sb.get_data_frames()[0]
        
        if games.empty:
            return None
        
        matches = []
        for _, game in games.iterrows():
            try:
                away_team = game.get('VISITOR_TEAM_NAME', '').strip()
                home_team = game.get('HOME_TEAM_NAME', '').strip()
                game_status = game.get('GAME_STATUS_ID', 0)
                
                # Filtrer les matchs terminés (status = 3)
                if game_status != 3 and away_team and home_team:
                    matches.append((away_team, home_team))
                    logger.debug(f"Matchs NBA trouvé: {away_team} @ {home_team}")
            except Exception as e:
                logger.debug(f"⚠️ Error parsing game: {e}")
                continue
        
        return matches if matches else None
    
    except Exception as e:
        logger.error(f"❌ nba_api error: {e}")
        return None
```

**Key Points:**
- Returns `None` if package unavailable or DataFrame empty
- Filters by game_status != 3 (3 = finished)
- Only returns if matches found, otherwise None to trigger ESPN fallback

---

## AUTO_SEND_PRONOSTICS() - Match Detection Section (Lines 3148-3245)

```python
async def auto_send_pronostics(context):
    """
    Toutes les 30 minutes: vérifie s'il y a des matchs qui commencent
    dans moins d'1 heure et envoie les picks pour ces matchs.
    """
    if not TELEGRAM_CHAT_ID:
        return

    quebec_time = get_quebec_time()
    now_utc = datetime.datetime.now(pytz.utc)
    date_key = quebec_time.strftime('%Y-%m-%d')

    sports_config = [
        ("basketball/nba", "nba", "🏀"),
        ("hockey/nhl", "nhl", "🏒"),
        ("football/nfl", "nfl", "🏈"),
    ]

    upcoming_matches = []  # [(sport_key, emoji, away, home)]

    for sport_path, sport_key, emoji in sports_config:
        try:
            # Vérifier aujourd'hui ET demain (UTC)
            # ex: 22h EDT = 02h00 UTC lendemain
            now_utc_date = datetime.datetime.utcnow()
            dates_to_check = [
                now_utc_date.strftime("%Y%m%d"),
                (now_utc_date + datetime.timedelta(days=1)).strftime("%Y%m%d"),
            ]

            all_events = []
            for date_str_q in dates_to_check:
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date_str_q}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    all_events.extend(resp.json().get('events', []))

            for event in all_events:
                try:
                    status_type = event.get('status', {}).get('type', {})
                    status_desc = status_type.get('description', '').lower()
                    status_name = status_type.get('name', '').lower()
                    
                    # Ignorer matchs terminés
                    if any(s in status_desc for s in ['final', 'completed']):
                        continue
                    if 'status_final' in status_name:
                        continue

                    date_str = event.get('date', '')
                    
                    # Parsing robuste : ESPN retourne avec ou sans secondes
                    # ex: "2026-05-10T23:00Z" ou "2026-05-10T23:00:00Z"
                    utc_dt = None
                    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
                        try:
                            utc_dt = datetime.datetime.strptime(date_str, fmt).replace(tzinfo=pytz.utc)
                            break
                        except ValueError:
                            continue
                    
                    if utc_dt is None:
                        logger.warning(f"⚠️ auto_send_pronostics: format date inconnu '{date_str}' ({sport_key})")
                        continue

                    minutes_until = (utc_dt - now_utc).total_seconds() / 60

                    # Fenêtre d'envoi: dans les 120 min avant le match OU match en cours
                    if minutes_until <= 120:
                        is_live = minutes_until < 20
                        
                        comp = event.get('competitions', [{}])[0]
                        competitors = comp.get('competitors', [])
                        
                        if len(competitors) >= 2:
                            away = competitors[0].get('team', {}).get('displayName', '?')
                            home = competitors[1].get('team', {}).get('displayName', '?')
                            
                            notify_key = f"prono_{date_key}_{sport_key}_{away}_{home}"
                            if notify_key not in _notified_pronostics:
                                _notified_pronostics.add(notify_key)
                                upcoming_matches.append((sport_key, emoji, away, home, utc_dt, is_live))
                                logger.info(f"🎯 Match trouvé [{sport_key}]: {away} @ {home} dans {minutes_until:.0f} min (live={is_live})")
                            else:
                                logger.debug(f"⏭️ Déjà notifié [{sport_key}]: {away} @ {home}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ auto_send_pronostics event error [{sport_key}]: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"⚠️ auto_send_pronostics {sport_key}: {e}")

    if not upcoming_matches:
        return

    # ... Continue with pick generation ...
```

**Key Points:**
- Queries TODAY + TOMORROW (UTC) to catch EDT evening games
- De-duplicates with `_notified_pronostics` set
- Sends if `minutes_until <= 120` (2-hour window)
- Date parsing robust (3 format support)
- Filters: Final/Completed status excluded
- **Problem:** Uses direct ESPN API, bypasses cache

---

## ERROR HANDLING PATTERNS

### Pattern 1: Exception & Continue
```python
except Exception:
    continue  # Skip malformed event
```

### Pattern 2: Try Multiple Formats
```python
for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
    try:
        utc_dt = datetime.datetime.strptime(date_str, fmt).replace(tzinfo=pytz.utc)
        break
    except ValueError:
        continue
```

### Pattern 3: Fallback Chain
```python
try:
    if NBA_API_AVAILABLE:
        matches = get_live_nba_games_api()
        if matches:
            return matches
except Exception:
    pass

# Fallback to ESPN
# ...
```

### Pattern 4: Cache TTL Check
```python
if MATCHES_CACHE_NBA and MATCHES_CACHE_TIME:
    elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
    if elapsed < 120:
        return MATCHES_CACHE_NBA
```

---

## DEPENDENCIES

Required imports:
```python
import datetime
import requests
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Optional (fallback sources)
try:
    from nba_api.live.nba.endpoints import scoreboard
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
```

ESPN API: Always available (public endpoint, no authentication)
