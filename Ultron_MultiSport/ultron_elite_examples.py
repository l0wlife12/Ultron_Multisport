#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON ELITE INTEGRATION GUIDE & EXAMPLES
Shows how to use ULTRON ELITE in your existing code
"""

import asyncio
import logging
from datetime import datetime
from ultron_elite import (
    TeamStats,
    OddsData,
    Match,
    UltronEliteSystem,
    Prediction
)
from ultron_elite_integration import (
    EliteSystemManager,
    EliteMessageBuilder,
    ELITE_CONFIG,
    enhance_prediction
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# EXAMPLE 1: STANDALONE ELITE ANALYSIS
# ============================================================

async def example_standalone_analysis():
    """
    Use ULTRON ELITE standalone
    Good for testing or batch processing
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Standalone ELITE Analysis")
    print("="*60 + "\n")

    # Initialize system
    elite = UltronEliteSystem()

    # Create team data
    home_team = TeamStats(
        name="Lakers",
        wins_last_10=8,
        ats_wins_last_10=7,
        points_scored=118,
        points_allowed=110,
        offensive_rating=117,
        defensive_rating=109,
        pace=101,
        injuries=1,
        rest_days=2
    )

    away_team = TeamStats(
        name="Celtics",
        wins_last_10=5,
        ats_wins_last_10=4,
        points_scored=111,
        points_allowed=108,
        offensive_rating=112,
        defensive_rating=107,
        pace=99,
        injuries=3,
        rest_days=1
    )

    # Odds data
    odds = OddsData(
        sportsbook="DraftKings",
        opening_line=-5.5,
        current_line=-3.5,
        opening_odds=1.91,
        current_odds=1.87,
        public_bets_pct=78,
        public_money_pct=44
    )

    # Create match
    match = Match(
        sport="NBA",
        home_team=home_team,
        away_team=away_team,
        odds=odds,
        market_type="MoneyLine",
        game_time=datetime.now()
    )

    # Generate prediction
    prediction = await elite.process_match(match)

    if prediction:
        print(f"✅ Prediction: {prediction.selection}")
        print(f"   Confidence: {prediction.confidence}%")
        print(f"   Expected Value: +{prediction.expected_value}%")
        print(f"   Sharp Score: {prediction.sharp_score}")
        print(f"   Recommended Bet: {prediction.recommended_bet_size}%")
        print(f"\nMessage Preview:")
        print(elite.telegram_formatter.format_pick(prediction))


# ============================================================
# EXAMPLE 2: INTEGRATION WITH EXISTING CODE
# ============================================================

async def example_integrated_with_existing():
    """
    Integrate ELITE with your existing ULTRON system
    Usage in ultron_multisports_v6_0.py main pipeline
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Integration with Existing Code")
    print("="*60 + "\n")

    # Initialize manager
    elite_manager = EliteSystemManager(enable_elite=True)

    # Sample prediction from existing system
    existing_prediction = {
        "sport": "NBA",
        "selection": "Lakers",
        "bet_type": "MoneyLine",
        "confidence": 55,
        "odds": 1.87,
        "home_team": {
            "name": "Lakers",
            "wins_last_10": 8,
            "ats_wins_last_10": 7,
            "points_scored": 118,
            "points_allowed": 110,
            "offensive_rating": 117,
            "defensive_rating": 109,
            "pace": 101,
            "injuries": 1,
            "rest_days": 2
        },
        "away_team": {
            "name": "Celtics",
            "wins_last_10": 5,
            "ats_wins_last_10": 4,
            "points_scored": 111,
            "points_allowed": 108,
            "offensive_rating": 112,
            "defensive_rating": 107,
            "pace": 99,
            "injuries": 3,
            "rest_days": 1
        },
        "odds": {
            "sportsbook": "DraftKings",
            "opening_line": -5.5,
            "current_line": -3.5,
            "opening_odds": 1.91,
            "current_odds": 1.87,
            "public_bets_pct": 78,
            "public_money_pct": 44
        },
        "market_type": "MoneyLine"
    }

    # Enhance with ELITE analysis
    enhanced = await enhance_prediction(existing_prediction, elite_manager)

    print("Original Confidence:", existing_prediction["confidence"])
    
    if "elite" in enhanced:
        elite_data = enhanced["elite"]
        print("ELITE Confidence:", elite_data["confidence"])
        print("ELITE Sharp Score:", elite_data["sharp_score"])
        print("ELITE EV:", f"+{elite_data['expected_value']}%")
        print("ELITE Recommendation:", f"{elite_data['recommended_bet_size']}% bankroll")
        print("\nELITE Reasoning:")
        for reason in elite_data["reasoning"]:
            print(f"  • {reason}")


# ============================================================
# EXAMPLE 3: LIVE GAME ANALYSIS
# ============================================================

async def example_live_game():
    """
    Use ELITE for live game analysis
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Live Game Analysis")
    print("="*60 + "\n")

    elite = UltronEliteSystem()

    # Analyze live game
    live_signal = await elite.process_live_game(
        current_total=212,
        projected_total=228,
        pace=108
    )

    if live_signal:
        print(f"✅ Live Betting Signal Found!")
        print(f"   Bet: {live_signal['bet']}")
        print(f"   Confidence: {live_signal['confidence']}%")
        print(f"   Edge: {live_signal['edge']} points")
    else:
        print("❌ No live betting signals at this time")


# ============================================================
# EXAMPLE 4: PARLAY BUILDING
# ============================================================

async def example_parlay_building():
    """
    Build uncorrelated parlays using ELITE
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Smart Parlay Building")
    print("="*60 + "\n")

    elite = UltronEliteSystem()

    # Create multiple predictions
    picks = []
    for i in range(3):
        for j in range(2):
            prediction = Prediction(
                bet_type="MoneyLine" if i % 2 == 0 else "Spread",
                selection=f"Team {i}-{j}",
                confidence=65 + (j * 5),
                edge=2.5,
                expected_value=2.5,
                sharp_score=15 + (i * 5),
                clv_projection=1.5,
                recommended_bet_size=2.5 + (i * 0.5),
                sportsbook="DraftKings",
                reasoning=[f"Reason {i}-{j}"]
            )
            picks.append(prediction)

    # Build parlays
    parlays = elite.parlay_engine.build_parlays(picks[:3])

    print(f"✅ Built {len(parlays)} parlays from {len(picks[:3])} picks")
    for i, parlay in enumerate(parlays[:3]):
        print(f"\n   Parlay {i+1}:")
        for pick in parlay:
            print(f"      • {pick.selection} ({pick.confidence}% confidence)")


# ============================================================
# EXAMPLE 5: BACKTEST RESULTS
# ============================================================

async def example_backtesting():
    """
    Backtest your predictions
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Backtesting Strategy")
    print("="*60 + "\n")

    elite = UltronEliteSystem()

    # Create sample predictions
    predictions = []
    for i in range(20):
        prediction = Prediction(
            bet_type="MoneyLine",
            selection=f"Team {i}",
            confidence=60 + (i % 20),
            edge=2.0,
            expected_value=2.0,
            sharp_score=15,
            clv_projection=1.5,
            recommended_bet_size=2.0,
            sportsbook="DraftKings",
            reasoning=["Strong form", "Sharp money"]
        )
        predictions.append(prediction)

    # Run backtest
    results = elite.backtester.simulate(predictions)

    print(f"Initial Bankroll: $1000")
    print(f"Final Bankroll: ${results['final_bankroll']}")
    print(f"ROI: {results['roi']}%")
    print(f"Max Drawdown: ${results['max_drawdown']}")


# ============================================================
# EXAMPLE 6: HOW TO USE IN MAIN.PY
# ============================================================

integration_code_example = """
# In your main.py, add these imports:
from ultron_elite_integration import EliteSystemManager, enhance_prediction

# In your initialization:
elite_manager = EliteSystemManager(enable_elite=True)

# In your auto_send_pronostics function:
async def auto_send_pronostics():
    '''Main scheduled job - now with ELITE analysis'''
    
    picks = get_all_picks()  # Your existing function
    
    for pick in picks:
        # Enhance with ELITE
        enhanced_pick = await enhance_prediction(pick, elite_manager)
        
        # Check threshold
        if elite_manager.elite_system.threshold_engine.should_send_pick(
            pick['sport'],
            enhanced_pick['confidence']
        ):
            # Build message with ELITE data
            if 'elite' in enhanced_pick:
                emoji = "🟢" if enhanced_pick['confidence'] > 70 else "🟡"
                message = f"{emoji} {enhanced_pick['selection']}\\n"
                message += f"Confidence: {enhanced_pick['confidence']}%\\n"
                message += f"EV: +{enhanced_pick['elite']['expected_value']}%"
            else:
                message = format_standard_pick(pick)
            
            # Send to Telegram
            await send_telegram(message, chat_id=PREMIUM_CHAT_ID)
"""

# ============================================================
# EXAMPLE 7: HOW TO USE IN ULTRON_MULTISPORTS_V6_0
# ============================================================

integration_advmulti_example = """
# In ultron_multisports_v6_0.py, add at top:
from ultron_elite_integration import EliteSystemManager

# In __init__ or startup:
self.elite_manager = EliteSystemManager(enable_elite=True)

# In your prediction function, e.g., get_nba_picks():
async def get_nba_picks(self):
    picks = []
    
    for game in self.games:
        prediction = self.predict_game(game)  # Your existing logic
        
        # Enhance with ELITE
        enhanced = await enhance_prediction({
            "sport": "NBA",
            "selection": prediction['team'],
            "confidence": prediction['confidence'],
            # ... add other game data
        }, self.elite_manager)
        
        # Use enhanced confidence
        if enhanced.get('confidence', 0) >= 62:
            picks.append(enhanced)
    
    return picks
"""

# ============================================================
# QUICK START GUIDE
# ============================================================

print("""
╔════════════════════════════════════════════════════════════════╗
║           ULTRON ELITE - INTEGRATION QUICK START               ║
╚════════════════════════════════════════════════════════════════╝

🚀 STEP 1: Initialize ELITE System
─────────────────────────────────────
    from ultron_elite_integration import EliteSystemManager
    elite_manager = EliteSystemManager(enable_elite=True)


🎯 STEP 2: Enhance Your Predictions
─────────────────────────────────────
    enhanced = await enhance_prediction(prediction, elite_manager)
    
    Now you have:
    • enhanced['elite']['confidence'] - ELITE confidence score
    • enhanced['elite']['sharp_score'] - Sharp money signals (0-50)
    • enhanced['elite']['expected_value'] - EV projection
    • enhanced['elite']['recommended_bet_size'] - Kelly sizing


📊 STEP 3: Use Adaptive Thresholds
─────────────────────────────────────
    if elite_manager.elite_system.threshold_engine.should_send_pick(
        "NBA", 
        prediction['confidence']
    ):
        send_pick(prediction)


💡 STEP 4: Monitor Learning
─────────────────────────────────────
    # ELITE learns from outcomes!
    elite_manager.elite_system.learning_engine.update_weights(
        result="WIN",
        signal="form"
    )


🔧 KEY FEATURES
─────────────────────────────────────
✓ Sharp Money Detection (reverse line movement, steam moves)
✓ Closing Line Value (CLV) Tracking
✓ Kelly Criterion Bankroll Management
✓ Reinforcement Learning (adaptive weights)
✓ Smart Parlay Building (low correlation filters)
✓ Live Game Analysis
✓ Sportsbook Performance Analytics
✓ Adaptive Threshold Learning


📁 FILES CREATED
─────────────────────────────────────
• ultron_elite.py - Core ELITE system (850 lines)
• ultron_elite_integration.py - Integration layer
• ultron_elite_examples.py - This file


💾 CONFIGURATION
─────────────────────────────────────
See ELITE_CONFIG in ultron_elite_integration.py:
• Thresholds per sport
• Kelly fraction (0.5 = half-kelly)
• Sharp money sensitivity
• Message inclusion flags


❓ QUESTIONS?
─────────────────────────────────────
All docstrings included in code. Refer to function signatures
for parameter details and return types.

""")


# ============================================================
# MAIN
# ============================================================

async def main():
    """Run all examples"""
    
    await example_standalone_analysis()
    await example_integrated_with_existing()
    await example_live_game()
    await example_parlay_building()
    await example_backtesting()

    print("\n" + "="*60)
    print("INTEGRATION CODE EXAMPLES")
    print("="*60)
    print("\nHow to use in main.py:")
    print(integration_code_example)
    
    print("\n" + "="*60)
    print("\nHow to use in ultron_multisports_v6_0.py:")
    print(integration_advmulti_example)

    print("\n" + "="*60)
    print("✅ All examples completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
