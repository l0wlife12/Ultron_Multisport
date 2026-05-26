#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON V7 — Single-file Production Core

Features:
  - PostgreSQL / SQLite support (auto-detected)
  - Dynamic cache TTL
  - CLV tracking
  - Confidence calibration
  - Async protection (semaphore per instance, not class)
  - Sharp money framework
  - Pick deduplication (SHA-256 fingerprint)
  - Probabilistic engine
  - Model versioning (registry)
  - Kelly bankroll engine (half-Kelly, division-by-zero safe)
  - Circuit breaker on ESPN API
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
import joblib
import numpy as np
from cachetools import TTLCache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ultron.db")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ULTRON_V7")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE — pool_size/max_overflow sont ignorés silencieusement par SQLite,
# mais causaient des warnings. On les applique seulement pour PostgreSQL.
# ─────────────────────────────────────────────────────────────────────────────

_is_postgres = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **({"pool_size": 10, "max_overflow": 20} if _is_postgres else {}),
)

SessionLocal = sessionmaker(bind=engine)

# ─────────────────────────────────────────────────────────────────────────────
# CACHE LAYERS
# ─────────────────────────────────────────────────────────────────────────────

pick_cache: TTLCache = TTLCache(maxsize=10_000, ttl=86400)
_odds_store: Dict = {}  # Renommé pour éviter le conflit avec la classe OddsCache

# ─────────────────────────────────────────────────────────────────────────────
# MODEL REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ModelRegistry:
    """Charge et expose les modèles ML. Échec silencieux si fichier absent."""

    def __init__(self) -> None:
        self.models: Dict = {}

    def load_models(self) -> None:
        for name, path in [("nba", "nba_model.pkl"), ("props", "props_model.pkl")]:
            try:
                self.models[name] = joblib.load(path)
                logger.info(f"✅ Modèle {name} chargé depuis {path}")
            except FileNotFoundError:
                logger.warning(f"⚠️ Modèle {name} introuvable ({path}) — fonctionnement sans ML")
            except Exception as exc:  # joblib peut lever diverses exceptions
                logger.warning(f"⚠️ Erreur chargement modèle {name}: {exc}")

    def get(self, name: str):
        return self.models.get(name)


model_registry = ModelRegistry()
model_registry.load_models()

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Game:
    sport: str
    home_team: str
    away_team: str
    odds_home: float
    odds_away: float
    market_prob_home: float
    model_prob_home: float
    injury_factor: float
    sharp_signal: float
    schedule_factor: float
    starts_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE STORE
# ─────────────────────────────────────────────────────────────────────────────

class FeatureStore:
    """Construit le vecteur de features numpy pour l'inférence ML."""

    def build_features(self, game: Game) -> np.ndarray:
        return np.array([
            game.market_prob_home,
            game.model_prob_home,
            game.injury_factor,
            game.sharp_signal,
            game.schedule_factor,
        ]).reshape(1, -1)


feature_store = FeatureStore()

# ─────────────────────────────────────────────────────────────────────────────
# PROBABILITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class ProbabilityEngine:
    """Fusionne les signaux pondérés en une probabilité finale [0.01, 0.99]."""

    def calculate_probability(
        self,
        model_probability: float,
        market_probability: float,
        sharp_signal: float,
        injury_factor: float,
        schedule_factor: float,
    ) -> float:
        raw = (
            0.40 * model_probability
            + 0.25 * market_probability
            + 0.15 * sharp_signal
            + 0.10 * injury_factor
            + 0.10 * schedule_factor
        )
        return max(0.01, min(0.99, raw))


probability_engine = ProbabilityEngine()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE ENGINE — calibration légère des hautes probabilités
# ─────────────────────────────────────────────────────────────────────────────

class ConfidenceEngine:
    """Convertit une probabilité en score de confiance [0, 100] calibré."""

    def calibrate(self, probability: float) -> float:
        confidence = probability * 100
        if confidence >= 75:
            confidence *= 0.95  # Légère déflation pour éviter la sur-confiance
        return round(confidence, 2)


confidence_engine = ConfidenceEngine()

# ─────────────────────────────────────────────────────────────────────────────
# EV ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class EVEngine:
    """Calcule l'Expected Value : EV = prob × cote − 1."""

    def calculate_ev(self, probability: float, odds: float) -> float:
        return (probability * odds) - 1


ev_engine = EVEngine()

# ─────────────────────────────────────────────────────────────────────────────
# CLV TRACKER
# ─────────────────────────────────────────────────────────────────────────────

class CLVTracker:
    """Closing Line Value — mesure si on a battu la cote de fermeture."""

    def calculate_clv(self, sent_line: float, closing_line: float) -> float:
        return closing_line - sent_line

    def is_positive_clv(self, clv: float) -> bool:
        return clv > 0

    def log(self, matchup: str, sent_line: float, closing_line: float) -> None:
        clv = self.calculate_clv(sent_line, closing_line)
        emoji = "✅" if self.is_positive_clv(clv) else "❌"
        logger.info(f"{emoji} CLV [{matchup}]: {sent_line:.2f} → {closing_line:.2f} (Δ {clv:+.2f})")


clv_tracker = CLVTracker()

# ─────────────────────────────────────────────────────────────────────────────
# KELLY ENGINE — half-Kelly, protégé contre division par zéro
# ─────────────────────────────────────────────────────────────────────────────

class KellyEngine:
    """
    Calcule la mise optimale (half-Kelly).
    Retourne 0 si les cotes valent exactement 1.0 (pas de bénéfice possible).
    """

    def calculate_stake(self, probability: float, odds: float, bankroll: float) -> float:
        b = odds - 1
        if b <= 0:
            return 0.0  # Cote ≤ 1 = pas de valeur
        q = 1 - probability
        kelly = ((b * probability) - q) / b
        half_kelly = max(0.0, kelly * 0.5)
        return bankroll * half_kelly


kelly_engine = KellyEngine()

# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC CACHE TTL
# ─────────────────────────────────────────────────────────────────────────────

class DynamicTTL:
    """TTL plus court à l'approche du match (cotes qui bougent plus vite)."""

    def get_ttl(self, starts_at: datetime) -> int:
        delta = (starts_at - datetime.utcnow()).total_seconds()
        if delta <= 7_200:    # < 2h
            return 300        # 5 min
        if delta <= 21_600:   # < 6h
            return 1_800      # 30 min
        return 7_200          # 2h


cache_ttl = DynamicTTL()

# ─────────────────────────────────────────────────────────────────────────────
# FINGERPRINT — SHA-256 (MD5 retiré pour éviter les collisions)
# ─────────────────────────────────────────────────────────────────────────────

class PickFingerprint:
    """
    Génère un hash unique pour chaque pick afin d'éviter les doublons.
    SHA-256 utilisé à la place de MD5 (meilleure résistance aux collisions).
    """

    def generate(self, sport: str, matchup: str, pick_type: str, line: float, odds: float) -> str:
        raw = f"{sport}_{matchup}_{pick_type}_{line}_{odds}"
        return hashlib.sha256(raw.encode()).hexdigest()


fingerprint_engine = PickFingerprint()

# ─────────────────────────────────────────────────────────────────────────────
# ESPN CLIENT — semaphore par instance, circuit breaker, session réutilisable
# ─────────────────────────────────────────────────────────────────────────────

class ESPNClient:
    """
    Client async ESPN avec :
      - Semaphore par INSTANCE (pas classe) pour éviter les conflits d'event loop
      - Session aiohttp réutilisée (pas recréée à chaque requête)
      - Circuit breaker : après 5 échecs consécutifs, pause 60s
    """

    _CIRCUIT_OPEN_DURATION = 60  # secondes

    def __init__(self, max_concurrent: int = 5) -> None:
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._max_concurrent = max_concurrent
        self._session: Optional[aiohttp.ClientSession] = None
        self._failure_count = 0
        self._circuit_open_until: Optional[datetime] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Crée le semaphore lazily dans le bon event loop."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _is_circuit_open(self) -> bool:
        if self._circuit_open_until and datetime.utcnow() < self._circuit_open_until:
            return True
        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
    async def get_json(self, url: str) -> dict:
        if self._is_circuit_open():
            raise RuntimeError("Circuit breaker ouvert — ESPN API temporairement indisponible")

        async with self._get_semaphore():
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    self._failure_count += 1
                    if self._failure_count >= 5:
                        self._circuit_open_until = datetime.utcnow() + timedelta(
                            seconds=self._CIRCUIT_OPEN_DURATION
                        )
                        logger.error(
                            f"🔴 Circuit breaker ESPN ouvert pour {self._CIRCUIT_OPEN_DURATION}s "
                            f"(5 échecs consécutifs)"
                        )
                    raise RuntimeError(f"ESPN API HTTP {response.status}")
                self._failure_count = 0  # Reset sur succès
                return await response.json()


espn_client = ESPNClient()

# ─────────────────────────────────────────────────────────────────────────────
# SHARP MONEY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SharpMoneyEngine:
    """Détecte le mouvement de cote causé par l'argent sharp."""

    def detect_sharp_action(self, opening_odds: float, current_odds: float) -> float:
        movement = abs(current_odds - opening_odds)
        if movement >= 0.15:
            return 0.75  # Fort signal sharp
        if movement >= 0.08:
            return 0.60  # Signal modéré
        return 0.50       # Pas de signal


sharp_engine = SharpMoneyEngine()

# ─────────────────────────────────────────────────────────────────────────────
# ODDS CACHE — utilise _odds_store pour ne pas conflicatuer avec le nom de classe
# ─────────────────────────────────────────────────────────────────────────────

class OddsCache:
    """Cache avec TTL manuel pour les cotes (indépendant de TTLCache)."""

    def get(self, key: str) -> Optional[dict]:
        entry = _odds_store.get(key)
        if entry is None:
            return None
        if datetime.utcnow() > entry["expires_at"]:
            del _odds_store[key]
            return None
        return entry["value"]

    def set(self, key: str, value, ttl_seconds: int) -> None:
        _odds_store[key] = {
            "value": value,
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl_seconds),
        }


odds_cache_engine = OddsCache()

# ─────────────────────────────────────────────────────────────────────────────
# PICK ENGINE — utilise maintenant le ModelRegistry si disponible
# ─────────────────────────────────────────────────────────────────────────────

class PickEngine:
    """
    Génère un pick complet en combinant tous les moteurs.
    Si un modèle ML est disponible dans le registry, il enrichit la probabilité.
    """

    def generate_pick(self, game: Game) -> Optional[Dict]:
        # Ajustement ML si modèle disponible
        model_prob = game.model_prob_home
        nba_model = model_registry.get(game.sport.lower())
        if nba_model is not None:
            try:
                features = feature_store.build_features(game)
                model_prob = float(nba_model.predict_proba(features)[0][1])
            except Exception as exc:
                logger.warning(f"⚠️ Inférence ML échouée, fallback sur model_prob_home: {exc}")

        probability = probability_engine.calculate_probability(
            model_probability=model_prob,
            market_probability=game.market_prob_home,
            sharp_signal=game.sharp_signal,
            injury_factor=game.injury_factor,
            schedule_factor=game.schedule_factor,
        )

        confidence = confidence_engine.calibrate(probability)
        ev = ev_engine.calculate_ev(probability, game.odds_home)
        stake = kelly_engine.calculate_stake(probability, game.odds_home, bankroll=10_000)

        matchup = f"{game.away_team} @ {game.home_team}"
        fingerprint = fingerprint_engine.generate(
            game.sport, matchup, "moneyline", game.odds_home, game.odds_home
        )

        if fingerprint in pick_cache:
            logger.info(f"⏭️ Pick doublon bloqué: {matchup}")
            return None

        pick_cache[fingerprint] = True

        return {
            "sport":       game.sport,
            "matchup":     matchup,
            "selection":   game.home_team,
            "probability": round(probability, 4),
            "confidence":  confidence,
            "ev":          round(ev * 100, 2),
            "stake":       round(stake, 2),
            "odds":        game.odds_home,
            "fingerprint": fingerprint,
            "created_at":  datetime.utcnow().isoformat(),
        }


pick_engine = PickEngine()

# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM FORMATTER — protégé contre les clés manquantes
# ─────────────────────────────────────────────────────────────────────────────

class TelegramFormatter:
    """Formate un pick pour l'envoi Telegram."""

    def format_pick(self, pick: Dict) -> str:
        ev = pick.get("ev", 0)
        ev_str = f"+{ev:.2f}%" if ev >= 0 else f"{ev:.2f}%"
        return (
            "🏀 ULTRON V7\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 {pick.get('matchup', 'N/A')}\n\n"
            f"✅ PICK: {pick.get('selection', 'N/A')} ML\n"
            f"💵 Odds: {pick.get('odds', 'N/A')}\n"
            f"📈 EV: {ev_str}\n"
            f"🔥 Confidence: {pick.get('confidence', 0)}/100\n"
            f"💰 Suggested Stake: ${pick.get('stake', 0):.2f}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )


formatter = TelegramFormatter()

# ─────────────────────────────────────────────────────────────────────────────
# BACKTESTING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class BacktestingEngine:
    """Évalue les performances d'une liste de picks gradés."""

    def evaluate(self, picks: List[Dict]) -> Dict:
        wins   = sum(1 for p in picks if p.get("result") == "WIN")
        losses = sum(1 for p in picks if p.get("result") == "LOSS")
        total  = wins + losses

        if total == 0:
            return {"wins": 0, "losses": 0, "winrate": 0.0}

        return {
            "wins":    wins,
            "losses":  losses,
            "winrate": round(wins / total * 100, 2),
        }


backtesting_engine = BacktestingEngine()

# ─────────────────────────────────────────────────────────────────────────────
# LIVE DEMO
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    sharp_signal = sharp_engine.detect_sharp_action(
        opening_odds=1.80,
        current_odds=1.65,
    )

    game = Game(
        sport="NBA",
        home_team="Celtics",
        away_team="Heat",
        odds_home=1.90,
        odds_away=2.10,
        market_prob_home=0.53,
        model_prob_home=0.59,
        injury_factor=0.60,
        sharp_signal=sharp_signal,
        schedule_factor=0.55,
        starts_at=datetime.utcnow() + timedelta(hours=2),
    )

    pick = pick_engine.generate_pick(game)

    if pick:
        print(formatter.format_pick(pick))
        clv_tracker.log(game.away_team + " @ " + game.home_team, game.odds_home, 1.85)
        logger.info("✅ Pick généré avec succès")

    await espn_client.close()


if __name__ == "__main__":
    asyncio.run(main())
