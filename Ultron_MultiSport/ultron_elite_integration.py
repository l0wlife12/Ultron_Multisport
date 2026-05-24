#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON ELITE INTEGRATION MODULE
Bridges Elite System with existing ULTRON v6.0
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from ultron_elite import (
    UltronEliteSystem,
    Match,
    TeamStats,
    OddsData,
    Prediction,
    AdaptiveThresholdEngine
)

logger = logging.getLogger(__name__)

# ============================================================
# ELITE SYSTEM MANAGER
# ============================================================

class EliteSystemManager:
    """Manages ULTRON ELITE integration"""

    def __init__(self, enable_elite: bool = True):
        self.elite_enabled = enable_elite
        
        if enable_elite:
            self.elite_system = UltronEliteSystem()
            logger.info("✅ ULTRON ELITE module initialized")
        else:
            self.elite_system = None
            logger.info("⚠️ ULTRON ELITE module disabled")

    def convert_to_team_stats(self, team_data: Dict) -> TeamStats:
        """Convert external team data to TeamStats"""
        return TeamStats(
            name=team_data.get("name", "Unknown"),
            wins_last_10=team_data.get("wins_last_10", 5),
            ats_wins_last_10=team_data.get("ats_wins_last_10", 5),
            points_scored=team_data.get("points_scored", 110),
            points_allowed=team_data.get("points_allowed", 110),
            offensive_rating=team_data.get("offensive_rating", 110),
            defensive_rating=team_data.get("defensive_rating", 110),
            pace=team_data.get("pace", 100),
            injuries=team_data.get("injuries", 0),
            rest_days=team_data.get("rest_days", 1)
        )

    def convert_to_odds_data(self, odds_data: Dict) -> OddsData:
        """Convert external odds data to OddsData"""
        return OddsData(
            sportsbook=odds_data.get("sportsbook", "Unknown"),
            opening_line=odds_data.get("opening_line", -3.0),
            current_line=odds_data.get("current_line", -3.0),
            opening_odds=odds_data.get("opening_odds", 1.91),
            current_odds=odds_data.get("current_odds", 1.91),
            public_bets_pct=odds_data.get("public_bets_pct", 50),
            public_money_pct=odds_data.get("public_money_pct", 50)
        )

    async def analyze_game(self, game_data: Dict) -> Optional[Dict]:
        """
        Analyze game using ULTRON ELITE
        
        Args:
            game_data: {
                "sport": "NBA",
                "home_team": {...},
                "away_team": {...},
                "odds": {...},
                "market_type": "MoneyLine"
            }
        """
        if not self.elite_enabled or self.elite_system is None:
            return None

        try:
            home_team = self.convert_to_team_stats(game_data.get("home_team", {}))
            away_team = self.convert_to_team_stats(game_data.get("away_team", {}))
            odds = self.convert_to_odds_data(game_data.get("odds", {}))

            match = Match(
                sport=game_data.get("sport", "NBA"),
                home_team=home_team,
                away_team=away_team,
                odds=odds,
                market_type=game_data.get("market_type", "MoneyLine"),
                game_time=datetime.now()
            )

            prediction = await self.elite_system.process_match(match)
            
            if prediction:
                return {
                    "elite_enabled": True,
                    "selection": prediction.selection,
                    "bet_type": prediction.bet_type,
                    "confidence": prediction.confidence,
                    "expected_value": prediction.expected_value,
                    "sharp_score": prediction.sharp_score,
                    "clv_projection": prediction.clv_projection,
                    "recommended_bet_size": prediction.recommended_bet_size,
                    "sportsbook": prediction.sportsbook,
                    "reasoning": prediction.reasoning,
                    "message": self.elite_system.telegram_formatter.format_pick(prediction)
                }
            
            return None

        except Exception as e:
            logger.error(f"Elite analysis error: {e}")
            return None

    async def analyze_live_game(self, current_total: float, 
                               projected_total: float,
                               pace: float) -> Optional[Dict]:
        """Analyze live game scenario"""
        if not self.elite_enabled or self.elite_system is None:
            return None

        return await self.elite_system.process_live_game(current_total, projected_total, pace)

    def get_elite_status(self) -> Dict:
        """Get ULTRON ELITE status"""
        if not self.elite_system:
            return {"enabled": False, "message": "ULTRON ELITE disabled"}

        return {
            "enabled": True,
            "thresholds": self.elite_system.threshold_engine.thresholds,
            "learning_weights": dict(self.elite_system.learning_engine.weights),
            "win_history_count": len(self.elite_system.learning_engine.win_history)
        }


# ============================================================
# TELEGRAM MESSAGE BUILDER
# ============================================================

class EliteMessageBuilder:
    """Builds enhanced Telegram messages with ELITE data"""

    @staticmethod
    def build_elite_message(prediction: Dict, include_elite: bool = True) -> str:
        """Build formatted Telegram message"""
        
        if not include_elite or "message" not in prediction:
            # Fallback to basic message
            return f"Pick: {prediction.get('selection')} {prediction.get('bet_type')}"

        return prediction["message"]

    @staticmethod
    def build_elite_summary(games: List[Dict]) -> str:
        """Build summary of all elite picks"""
        
        elite_picks = [g for g in games if g.get("elite_enabled")]
        
        if not elite_picks:
            return "No ELITE picks for today"

        avg_confidence = sum(p["confidence"] for p in elite_picks) / len(elite_picks)
        avg_ev = sum(p["expected_value"] for p in elite_picks) / len(elite_picks)

        summary = f"""
📊 ULTRON ELITE SUMMARY
━━━━━━━━━━━━━━━━━━━
📈 Total Picks: {len(elite_picks)}
🎯 Avg Confidence: {avg_confidence:.1f}%
💰 Avg EV: +{avg_ev:.2f}%
🧠 Sharp: {sum(1 for p in elite_picks if p['sharp_score'] > 20)}
━━━━━━━━━━━━━━━━━━━
"""
        return summary


# ============================================================
# CONFIG
# ============================================================

ELITE_CONFIG = {
    # Enable/disable ELITE features
    "enabled": True,
    
    # Elite thresholds per sport
    "thresholds": {
        "NBA": 62,
        "NHL": 64,
        "MLB": 63,
        "NFL": 65
    },
    
    # Bet sizing
    "kelly_fraction": 0.5,  # Half-kelly for conservative sizing
    "max_bet_size": 0.25,   # Max 25% of bankroll
    
    # Sharp money sensitivity
    "sharp_threshold": 30,
    
    # Messages
    "include_elite_in_free": True,
    "include_elite_in_premium": True,
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def enhance_prediction(prediction_dict: Dict, 
                            elite_manager: Optional[EliteSystemManager] = None) -> Dict:
    """
    Enhance existing prediction with ELITE analysis
    
    Usage in existing code:
        enhanced = await enhance_prediction(existing_pick, elite_manager)
    """
    
    if not elite_manager or not elite_manager.elite_enabled:
        return prediction_dict

    try:
        elite_analysis = await elite_manager.analyze_game(prediction_dict)
        
        if elite_analysis:
            # Merge ELITE data with existing prediction
            prediction_dict["elite"] = elite_analysis
            prediction_dict["confidence"] = max(
                prediction_dict.get("confidence", 0),
                elite_analysis["confidence"]
            )
            prediction_dict["reasoning"] = (
                prediction_dict.get("reasoning", []) + elite_analysis["reasoning"]
            )
        
        return prediction_dict
    
    except Exception as e:
        logger.error(f"Enhancement error: {e}")
        return prediction_dict


if __name__ == "__main__":
    logger.info("✅ ULTRON ELITE Integration module loaded")
