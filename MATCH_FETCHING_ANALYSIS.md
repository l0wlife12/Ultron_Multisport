# ULTRON MULTISPORT - Match Fetching Analysis

## Overview
The bot uses ESPN API as the primary source for live match data across NBA, NHL, and NFL. Matches are fetched on-demand and cached for 120 seconds to reduce API calls.

---

## 1. MATCH FETCHING FUNCTIONS

### Location: `ultron_multisports_v6_0.py`

### A. `get_live_matches_nba()` (Line 793)
**Purpose:** Fetch NBA live matches with fallback chain

**Fallback Chain:**
1. **nba_api** (Official NBA data) → if available
2. **ESPN API** → if nba_api fails
3. **Empty list** → if both fail (no demo data)

**Code Flow:**
```python
def get_live_matches_nba() -> list:
    # Cache check: 120-second TTL
    if MATCHES_CACHE_NBA and MATCHES_CACHE_TIME:
        elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
        if elapsed < 120:
            return MATCHES_CACHE_NBA  # Return cached data
    
    # Try nba_api first (official source)
    if NBA_API_AVAILABLE:
        matches = get_live_nba_games_api()
        if matches:
            return matches
    
    # Fallback: ESPN API (search next 7 days)
    for day_offset in range(7):
        date_str = (today + timedelta(days=day_offset)).strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            for event in data.get('events', []):
                status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
                
                # Filter condition: EXCLUDE 'final', 'completed', 'cancelled', 'postponed'
                BLOCKED_STATUSES = ['final', 'completed', 'cancelled', 'postponed']
                if not any(word in status_desc for word in BLOCKED_STATUSES):
                    if len(competitors) >= 2:
                        away = competitors[0].get('team', {}).get('name', '').strip()
                        home = competitors[1].get('team', {}).get('name', '').strip()
                        daily_matches.append((away, home))
            
            # Return first day with matches found
            if daily_matches:
                MATCHES_CACHE_NBA = daily_matches
                MATCHES_CACHE_TIME = datetime.datetime.now()
                return daily_matches
    
    return []  # No matches in 7 days
```

**ESPN Endpoint:** 
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={YYYYMMDD}`

**Key Conditions Preventing Match Detection:**
1. ❌ Status is `final`, `completed`, `cancelled`, or `postponed`
2. ❌ No events returned by ESPN API
3. ❌ JSON parsing error (missing competitors array)
4. ❌ Teams have empty/strip-down names
5. ❌ Cache still valid (< 120 seconds old)
6. ❌ Out of season (ESPN returns 0 events for 7 days)

---

### B. `get_live_matches_nhl()` (Line 684)
**Purpose:** Fetch NHL live matches

**Code:**
```python
def get_live_matches_nhl() -> list:
    # Cache check: 120-second TTL
    for day_offset in range(7):
        date_str = (today + timedelta(days=day_offset)).strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date_str}"
        resp = requests.get(url, timeout=10)
        
        # Same filtering logic as NBA
        BLOCKED_STATUSES = ['final', 'completed', 'cancelled', 'postponed']
        if not any(word in status_desc for word in BLOCKED_STATUSES):
            daily_matches.append((away, home))
    
    return daily_matches  # or empty list
```

**ESPN Endpoint:**
- `https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={YYYYMMDD}`

**Conditions Preventing Detection:**
- Same as NBA (see above)
- Off-season: Returns empty list with log message: `"ℹ️ Aucun match NHL dans les 7 prochains jours (hors saison)"`

---

### C. `get_live_matches_nfl()` (Line 738)
**Purpose:** Fetch NFL live matches

**Code:**
```python
def get_live_matches_nfl() -> list:
    # Cache check: 120-second TTL
    # Searches 7 days forward
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}"
    
    # Same filtering: EXCLUDE final/completed/cancelled/postponed
    BLOCKED_STATUSES = ['final', 'completed', 'cancelled', 'postponed']
```

**ESPN Endpoint:**
- `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={YYYYMMDD}`

---

### D. `get_live_nba_games_api()` (Line 431)
**Purpose:** Fetch NBA matches using official nba_api library (if installed)

**Code:**
```python
def get_live_nba_games_api():
    if not NBA_API_AVAILABLE:
        return None
    
    try:
        sb = scoreboard.ScoreboardV2()
        games = sb.get_data_frames()[0]
        
        if games.empty:
            return None
        
        matches = []
        for _, game in games.iterrows():
            away_team = game.get('VISITOR_TEAM_NAME', '').strip()
            home_team = game.get('HOME_TEAM_NAME', '').strip()
            game_status = game.get('GAME_STATUS_ID', 0)
            
            # Filter: EXCLUDE games with status 3 (finished)
            if game_status != 3 and away_team and home_team:
                matches.append((away_team, home_team))
    
    except:
        return None
```

**Conditions Preventing Detection:**
- `NBA_API_AVAILABLE = False` (package not installed)
- Games DataFrame is empty
- Game status is 3 (finished)

---

## 2. AUTO_SEND_PRONOSTICS FLOW

### Location: `ultron_multisports_v6_0.py` Line 3148

**Purpose:** Every 30 minutes, check for matches starting within 120 minutes and send predictions

**Key Code Section:**
```python
async def auto_send_pronostics(context):
    """Every 30 min: check for matches in < 1 hour, send picks"""
    
    # Check TODAY + TOMORROW (UTC)
    # Why? EDT evening games = UTC+1 day (e.g., 22h EDT = 02h UTC next day)
    now_utc_date = datetime.datetime.utcnow()
    dates_to_check = [
        now_utc_date.strftime("%Y%m%d"),
        (now_utc_date + datetime.timedelta(days=1)).strftime("%Y%m%d"),
    ]
    
    # For each sport (NBA, NHL, NFL)
    for sport_path, sport_key, emoji in [
        ("basketball/nba", "nba", "🏀"),
        ("hockey/nhl", "nhl", "🏒"),
        ("football/nfl", "nfl", "🏈"),
    ]:
        for date_str in dates_to_check:
            # Direct ESPN API call (NOT using get_live_matches_*())
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=8)
            all_events.extend(resp.json().get('events', []))
        
        # Filter for matches within 120-minute window
        for event in all_events:
            status_desc = event.get('status', {}).get('type', {}).get('description', '').lower()
            status_name = event.get('status', {}).get('type', {}).get('name', '').lower()
            
            # SKIP if finished
            if any(s in status_desc for s in ['final', 'completed']):
                continue
            if 'status_final' in status_name:
                continue
            
            # Parse event datetime (robust, handles multiple formats)
            date_str = event.get('date', '')  # e.g., "2026-05-10T23:00Z"
            for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
                try:
                    utc_dt = datetime.datetime.strptime(date_str, fmt).replace(tzinfo=pytz.utc)
                    break  # Success
                except ValueError:
                    continue
            
            if utc_dt is None:
                logger.warning(f"⚠️ Unknown date format: '{date_str}' ({sport_key})")
                continue
            
            minutes_until = (utc_dt - now_utc).total_seconds() / 60
            
            # Send if within 120 minutes (or already live: < 20 min until)
            if minutes_until <= 120:
                is_live = minutes_until < 20
                
                # De-duplication check
                notify_key = f"prono_{date_key}_{sport_key}_{away}_{home}"
                if notify_key not in _notified_pronostics:
                    _notified_pronostics.add(notify_key)
                    upcoming_matches.append((sport_key, emoji, away, home, utc_dt, is_live))
```

**Key Points:**
- Searches TWO dates (today + tomorrow UTC) for EDT evening games
- Uses direct ESPN API instead of cached `get_live_matches_*()`
- Filters: `minutes_until <= 120` (only matches within 2 hours)
- De-duplication: `_notified_pronostics` set tracks sent notifications
- Date parsing is robust (handles 3 formats)

---

## 3. CACHING MECHANISM

### Global Variables (Line 160-163):
```python
MATCHES_CACHE_NBA = []
MATCHES_CACHE_NHL = []
MATCHES_CACHE_NFL = []
MATCHES_CACHE_TIME = None
```

### Cache Logic (ALL functions):
```python
if MATCHES_CACHE and MATCHES_CACHE_TIME:
    elapsed = (datetime.datetime.now() - MATCHES_CACHE_TIME).total_seconds()
    if elapsed < 120:  # 2-minute TTL
        return MATCHES_CACHE
```

**Issue:** Cache is per-sport but uses shared `MATCHES_CACHE_TIME`
- When NBA cache is updated, `MATCHES_CACHE_TIME` updates for ALL sports
- Example: If `get_live_matches_nba()` runs at 10:00:00, then `get_live_matches_nhl()` at 10:00:30 sees elapsed=30s, still cached

---

## 4. ESPN API ENDPOINTS & RESPONSE FORMAT

### General Format:
```
https://site.api.espn.com/apis/site/v2/sports/{SPORT}/{LEAGUE}/scoreboard?dates={YYYYMMDD}
```

### Sports Paths:
- NBA: `basketball/nba`
- NHL: `hockey/nhl`
- NFL: `football/nfl`

### Response JSON Structure:
```json
{
  "events": [
    {
      "id": "...",
      "date": "2026-05-10T23:00Z",
      "status": {
        "type": {
          "id": "...",
          "name": "STATUS_...",
          "description": "Scheduled|Live|Final|..."
        }
      },
      "competitions": [
        {
          "competitors": [
            {"team": {"name": "Team A", "displayName": "Team A"}},
            {"team": {"name": "Team B", "displayName": "Team B"}}
          ]
        }
      ]
    }
  ]
}
```

---

## 5. KEY CONDITIONS PREVENTING MATCHES FROM BEING FOUND

### **Season-Based (Off-Season)**
- **Problem:** Functions search 7 days forward but return empty if no events found
- **Symptom:** Log message: `"ℹ️ Aucun match {SPORT} dans les 7 prochains jours (hors saison)"`
- **Example:** NFL during off-season (June-August)

### **Status Filtering**
- **Blocked statuses:** `final`, `completed`, `cancelled`, `postponed`
- **Hidden matches:** If ESPN returns a match but status is "Final" before the match actually starts (data lag)
- **Current game logic:** Only runs when `minutes_until <= 120`

### **Date/Time Parsing**
- **Issue:** ESPN returns multiple date formats, only 3 supported
- **Fallback:** Log warning and skip event if parse fails
- **UTC/EDT timezone confusion in auto_send_pronostics**
  - Checks TODAY + TOMORROW UTC (correct for EDT evening games)
  - BUT time windows are in UTC, not EDT

### **API Timeout**
- All requests have `timeout=10` or `timeout=8`
- Timeout → returns `[]` with error log
- Example: `logger.error(f"❌ Erreur {SPORT}: {e}")`

### **JSON Parsing Errors**
- Missing `competitors` array → skip event
- Team names empty after `.strip()` → skip event
- No events in response → return empty

### **Cache Collisions**
- All sports share `MATCHES_CACHE_TIME`
- If NBA query runs, NHL/NFL cache expires at same time (even if not queried recently)

### **De-duplication in auto_send_pronostics**
- `_notified_pronostics` set prevents re-sending same match
- **Issue:** No expiration. If bot restarts, memory lost.
- Key format: `f"prono_{date_key}_{sport_key}_{away}_{home}"`

---

## 6. ISSUES & BUGS IDENTIFIED

### ✅ **Issue 1: Shared Cache Timer**
- **File:** `ultron_multisports_v6_0.py` Line 163
- **Problem:** All 3 sports share `MATCHES_CACHE_TIME`, not separate timers
- **Impact:** When one sport's cache updates, others' are implicitly invalidated
- **Fix:** Use per-sport cache times
  ```python
  MATCHES_CACHE_TIME_NBA = None
  MATCHES_CACHE_TIME_NHL = None
  MATCHES_CACHE_TIME_NFL = None
  ```

### ⚠️ **Issue 2: Date Parsing in auto_send_pronostics**
- **File:** `ultron_multisports_v6_0.py` Line 3208
- **Problem:** Multiple date format support, but silently skips unparseable events
- **Impact:** Some events might be missed if ESPN changes format
- **Log:** `"⚠️ auto_send_pronostics: format date inconnu '{date_str}'"`
- **Fix:** Add more format patterns or use `dateutil.parser.parse()`

### 🔴 **Issue 3: auto_send_pronostics Bypasses Cache**
- **File:** `ultron_multisports_v6_0.py` Line 3180-3185
- **Problem:** Makes direct ESPN API calls instead of using `get_live_matches_*()`
- **Impact:** 
  - Duplicates API logic
  - Doesn't benefit from fallback chain (nba_api, retries)
  - Different error handling
- **Fix:** Call `get_live_matches_*()`

### 🔴 **Issue 4: De-duplication Memory Loss on Restart**
- **File:** `ultron_multisports_v6_0.py` Line 2938, 3226-3227
- **Problem:** `_notified_pronostics = set()` is in-memory only
- **Impact:** If bot restarts, same matches sent again
- **Fix:** Store in file or database

### 🔴 **Issue 5: Missing Error Handling for <120 min window**
- **File:** `ultron_multisports_v6_0.py` Line 3219
- **Problem:** If date parsing fails, `utc_dt` could be None, then `minutes_until` calculation crashes
- **Current:** Wrapped in try-except, logs warning and continues
- **Fix:** Already handled (see log message), but not obvious from code structure

### ⚠️ **Issue 6: nba_api Fallback Timing**
- **File:** `ultron_multisports_v6_0.py` Line 805
- **Problem:** If nba_api returns matches, ESPN API is never queried
- **Impact:** Misses ESPN context (injuries, stats) if nba_api is offline
- **Fix:** Include both sources, merge, or log which was used

---

## 7. TEST ENDPOINT

Quick test to check for current matches:

```bash
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260515"
```

**For testing:**
- [check_matches.py](check_matches.py) — dumps current matches to console
- Run: `python Ultron_MultiSport/check_matches.py`

---

## 8. SUMMARY TABLE

| Function | Endpoint | Cache TTL | Fallback | Off-Season Behavior |
|----------|----------|-----------|----------|-------------------|
| `get_live_matches_nba()` | ESPN or nba_api | 120s | nba_api → ESPN → [] | Empty list + log |
| `get_live_matches_nhl()` | ESPN | 120s | ESPN only | Empty list + log |
| `get_live_matches_nfl()` | ESPN | 120s | ESPN only | Empty list + log |
| `auto_send_pronostics()` | ESPN (direct, no cache) | N/A | None (fails silently) | No matches sent |

---

## 9. RECOMMENDATIONS

### Critical Fixes:
1. **Fix shared cache timer** → Use per-sport timers
2. **Consolidate auto_send_pronostics** → Use cached `get_live_matches_*()` functions
3. **Persistent de-duplication** → Store `_notified_pronostics` in file/DB

### Improvements:
1. Add retry logic for ESPN API timeouts
2. Support more date formats in parser
3. Log when ESPN API returns 0 events (vs. when we return 0 after filtering)
4. Add metrics: events returned, events filtered, picks sent

### Monitoring:
1. Alert if `get_live_matches_*()` returns empty for 24+ hours during season
2. Track cache hit rate
3. Monitor ESPN API response times
