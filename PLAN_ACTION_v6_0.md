# PLAN D'ACTION - Refactoring Prioritaire

## 🎯 CRITICALS À FIXER EN PREMIER (Jours 1-2)

### ISSUE #1: Remplacer Variables Globales
**Effort:** 4 heures  
**Impact:** HIGH - Évite race conditions et état dupliqué  

```python
# ❌ AVANT: Globals partout
global MATCHES_CACHE_NBA, MATCHES_CACHE_TIME
MATCHES_CACHE_NBA = []
MATCHES_CACHE_TIME = None

global _ODDS_API_CACHE
_ODDS_API_CACHE = {}

# ✅ APRÈS: Classe centralisée
class CacheManager:
    def __init__(self):
        self.matches = {"nba": [], "nhl": [], "mlb": []}
        self.match_times = {"nba": None, "nhl": None, "mlb": None}
        self.odds_api = {}
        self.player_props = {}
        self.mlb_stats = {}
    
    def get_matches(self, sport: str, max_age_seconds: int = 120) -> List[Tuple]:
        if self.matches[sport] and self.match_times[sport]:
            age = (datetime.now() - self.match_times[sport]).total_seconds()
            if age < max_age_seconds:
                return self.matches[sport]
        return []
    
    def set_matches(self, sport: str, matches: List[Tuple]):
        self.matches[sport] = matches
        self.match_times[sport] = datetime.now()
    
    def get_odds(self, sport: str, max_age_seconds: int = 14400):
        cached = self.odds_api.get(sport)
        if cached:
            age = (datetime.now() - cached["fetched_at"]).total_seconds()
            if age < max_age_seconds:
                return cached["data"]
        return []
    
    def set_odds(self, sport: str, data: Dict):
        self.odds_api[sport] = {"data": data, "fetched_at": datetime.now()}

# Usage dans main():
cache_mgr = CacheManager()
matches = cache_mgr.get_matches("nba")
```

---

### ISSUE #2: Try/Except Générique → Spécifique
**Effort:** 2 heures  
**Impact:** CRITICAL - Les vrais erreurs sont cachées  

```python
# ❌ AVANT (Ligne 25-27):
try:
    from nba_api.live.nba.endpoints import scoreboard, playoffpicture
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

# ✅ APRÈS:
NBA_API_AVAILABLE = False
try:
    from nba_api.live.nba.endpoints import scoreboard, playoffpicture
    NBA_API_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ nba_api not installed: {e}. Install with 'pip install nba-api'")
except Exception as e:
    logger.error(f"❌ Unexpected error importing nba_api: {e}")
    NBA_API_AVAILABLE = False

# Template pour refactor systematique:
def safe_import(module_path: str, feature_name: str, attrs: List[str]) -> bool:
    try:
        mod = __import__(module_path, fromlist=attrs)
        for attr in attrs:
            if not hasattr(mod, attr):
                logger.warning(f"⚠️ {module_path}.{attr} not found")
                return False
        logger.info(f"✅ {feature_name} loaded")
        return True
    except ImportError:
        logger.warning(f"⚠️ {feature_name} not installed. Run: pip install {module_path}")
        return False
    except Exception as e:
        logger.error(f"❌ {feature_name}: {e}")
        return False
```

---

### ISSUE #3: Accès Dict Non Validé
**Effort:** 1.5 heure  
**Impact:** CRITICAL - Crash runtime  

```python
# ❌ AVANT (Ligne ~1325):
odds = odds_dict.get(key_forward, odds_dict.get(key_reverse, {}))
if odds:
    away_ml = odds.get("away_ml", 1.0) if key_forward in odds_dict else odds.get("home_ml", 1.0)
    # BUG: Si odds est {} (dict vide), .get() retourne 1.0 mais on ignore l'erreur

# ✅ APRÈS: Validation robuste
def extract_odds(odds_dict: Dict, away_team: str, home_team: str) -> Dict:
    """Extract odds safe, with fallback to default values"""
    key_fwd = (away_team.lower(), home_team.lower())
    key_rev = (home_team.lower(), away_team.lower())
    
    odds = odds_dict.get(key_fwd, odds_dict.get(key_rev))
    
    if not odds or not isinstance(odds, dict):
        logger.debug(f"No odds found for {key_fwd}, using defaults")
        return {"away_ml": 1.90, "home_ml": 1.90, "away_book": "DEFAULT", "home_book": "DEFAULT"}
    
    # Valider que toutes les clés attendues existent
    required_keys = ["away_ml", "home_ml"]
    if not all(k in odds for k in required_keys):
        logger.warning(f"Incomplete odds dict: {odds.keys()}")
        return {"away_ml": 1.90, "home_ml": 1.90, "away_book": "DEFAULT", "home_book": "DEFAULT"}
    
    # Valider que les valeurs sont des nombres > 1.0
    try:
        away_ml = float(odds["away_ml"])
        home_ml = float(odds["home_ml"])
        if not (1.0 <= away_ml <= 100.0 and 1.0 <= home_ml <= 100.0):
            raise ValueError(f"Odds out of range: {away_ml}, {home_ml}")
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid odds values: {e}")
        return {"away_ml": 1.90, "home_ml": 1.90, "away_book": "DEFAULT", "home_book": "DEFAULT"}
    
    return {
        "away_ml": away_ml,
        "home_ml": home_ml,
        "away_book": odds.get("away_book", "DEFAULT"),
        "home_book": odds.get("home_book", "DEFAULT")
    }
```

---

### ISSUE #4: Configuration Non Validée
**Effort:** 1 heure  
**Impact:** CRITICAL - Manque de clés → crash silencieux  

```python
# ❌ AVANT (Ligne 251-266):
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set...")

TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # ← Peut être None!
TELEGRAM_CHAT_ID_VIP = os.getenv('TELEGRAM_CHAT_ID_VIP')  # ← Peut être None!
ODDS_API_KEY = os.getenv('ODDS_API_KEY')  # ← Peut être None!

if TELEGRAM_CHAT_ID:
    logger.info(f"✅ TELEGRAM_CHAT_ID configuré")
# Mais ensuite le code assume que TELEGRAM_CHAT_ID existe...

# ✅ APRÈS: Validation centralisée
from dataclasses import dataclass
from typing import Optional

@dataclass
class BotConfig:
    telegram_token: str
    telegram_chat_id: str
    telegram_chat_id_vip: Optional[str] = None
    odds_api_key: Optional[str] = None
    request_timeout: int = 10
    cache_ttl_odds: int = 14400
    cache_ttl_stats: int = 604800  # 7 days
    max_retry_attempts: int = 3
    
    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            raise ValueError(
                "❌ TELEGRAM_TOKEN NOT SET. Configure with:\n"
                "  export TELEGRAM_TOKEN='...' (develop)\n"
                "  Railway Environment Variables (production)"
            )
        
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not chat_id:
            raise ValueError(
                "❌ TELEGRAM_CHAT_ID NOT SET. Configure with:\n"
                "  export TELEGRAM_CHAT_ID='...' (develop)\n"
                "  Railway Environment Variables (production)"
            )
        
        odds_key = os.getenv('ODDS_API_KEY')
        if not odds_key:
            logger.warning("⚠️ ODDS_API_KEY not set - using static odds only")
        
        vip_id = os.getenv('TELEGRAM_CHAT_ID_VIP')
        if not vip_id:
            logger.warning("⚠️ TELEGRAM_CHAT_ID_VIP not set - VIP features disabled")
        
        return cls(
            telegram_token=token,
            telegram_chat_id=chat_id,
            telegram_chat_id_vip=vip_id,
            odds_api_key=odds_key,
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '10')),
            cache_ttl_odds=int(os.getenv('CACHE_TTL_ODDS', '14400')),
            cache_ttl_stats=int(os.getenv('CACHE_TTL_STATS', '604800')),
        )
    
    def validate(self):
        """Ensure all required configs are set and valid"""
        assert self.telegram_token, "token is empty"
        assert len(self.telegram_token) > 20, "token too short"
        assert self.telegram_chat_id.isdigit(), "chat_id must be numeric"
        assert self.request_timeout > 0, "timeout must be positive"
        logger.info(f"✅ Config validated: {len(self.telegram_token)} chars token, chat={self.telegram_chat_id}")

# Usage dans main():
try:
    config = BotConfig.from_env()
    config.validate()
except ValueError as e:
    logger.error(e)
    sys.exit(1)
```

---

## 📅 PLANNING HEBDOMADAIRE

### Semaine 1: Criticals

| Jour | Tâche | Effort | Fichier(s) |
|-----|-------|--------|-----------|
| Lun | Créer CacheManager | 4h | A valider + intégrer |
| Lun | Refactor try/except | 2h | imports section |
| Mar | Dict validation | 1.5h | functions odds + stats |
| Mar | Config validation | 1h | __init__ |
| Mer | Tests unitaires config | 1h | tests/test_config.py |
| Mer-Jeu | Intégration + tests | 6h | full integration test |
| Ven | Performance + logs | 2h | versioning |

---

### Semaine 2: Architecture

| Jour | Tâche | Effort | Fichier(s) |
|-----|-------|--------|-----------|
| Lun | BaseSportsAnalyzer class | 3h | sports_analyzer.py |
| Lun-Mar | Implémenter NBAAnalyzer | 4h | nba_analyzer.py |
| Mer | Implémenter NHLAnalyzer | 3h | nhl_analyzer.py |
| Mer-Jeu | Implémenter MLBAnalyzer | 3h | mlb_analyzer.py |
| Jeu-Ven | Migrer code existant | 6h | refactor existing |

---

### Semaine 3: Quality + Testing

| Jour | Tâche | Effort | Fichier(s) |
|-----|-------|--------|-----------|
| Lun-Mar | Ajouter type hints | 8h | mypy --strict |
| Mar | Tests OddsAPI fallback | 2h | tests/test_odds.py |
| Mer | Tests predictions | 4h | tests/test_predictions.py |
| Jeu | Logs structured | 3h | logging_config.py |
| Ven | Performance audit | 2h | benchmarks/ |

---

## 🔧 CHECKLIST DÉTAILLÉ SEMAINE 1

### Lundi Matin: CacheManager

- [ ] Créer `ultron_cache.py`
- [ ] Implémenter classe CacheManager
- [ ] Tests unitaires pour get/set
- [ ] Docstrings complets
- [ ] Validation TTL

### Lundi Après-midi: Try/Except Refactor

- [ ] Créer fonction `safe_import()`
- [ ] Refactor section imports (L25-200)
- [ ] Tests: chaque import fonctionne
- [ ] Logger messages cohérents

### Mardi: Dict Validation

- [ ] Créer fonction `extract_odds()`
- [ ] Créer fonction `extract_stats()`
- [ ] Tester edge cases (dict vide, ValueError, KeyError)
- [ ] Benchmark performance

### Mardi Soir: Config Validation

- [ ] Créer dataclass BotConfig
- [ ] from_env() setter
- [ ] validate() checker
- [ ] Tests de startup

### Mercredi: Tests Unitaires

- [ ] Setup pytest + fixtures
- [ ] Test config validation
- [ ] Test cache expiration
- [ ] Test dict extraction

---

## 📊 MÉTRIQUES DE SUCCÈS

Après refactoring, avant/après:

| Métrique | Avant | Après | ✅ |
|----------|-------|-------|---|
| Globals count | 15 | 1 (config) | ● |
| Try/except vague | 70+ | 0 | ● |
| Type hints coverage | 15% | 95% | ● |
| Test coverage | 0% | 50%+ | ● |
| Lines per function (max) | 450 | 100 | ● |
| Code duplication | 30% | 5% | ● |

---

## 💡 NOTES D'IMPLÉMENTATION

1. **Backward compatibility:** Wrapper functions pour l'ancien code:
   ```python
   # Ancien code compatible:
   get_live_matches_nba() → analyzer.get_matches("nba")
   ```

2. **Migration graduelle:** Refactor d'abord config, puis globals, puis architecture.

3. **Testing:** Avant chaque changement:
   ```bash
   pytest tests/
   mypy --strict ultron_multisports_v6_0.py
   ```

4. **Versioning:** Tag commits:
   - `v6.0.1-hotfix`: Cache + config
   - `v6.1.0-refactor`: Architecture basée sur classes
   - `v6.2.0-quality`: Type hints + tests complets

---

**Début:** Lundi 26 mai 2026  
**Fin prévue:** Vendredi 14 juin 2026 (3 semaines)  
**Reviewers:** Lead dev + QA  
**Master branch merge:** Après Week 3 ✅
