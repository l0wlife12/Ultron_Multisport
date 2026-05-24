#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON ELITE - SPECIFIC INTEGRATION SNIPPETS
For main.py and ultron_multisports_v6_0.py
Ready to copy/paste!
"""

# ============================================================
# 🎯 INTEGRATION SNIPPET #1: main.py
# ============================================================

MAIN_PY_INTEGRATION = """
# Add these imports at the top of main.py:
import asyncio
from ultron_elite_integration import EliteSystemManager, enhance_prediction
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# In your TelegramBot class / __init__ method:
# ─────────────────────────────────────────────────────────

class TelegramBot(telegram.ext.Application):
    def __init__(self, ...):
        # Your existing initialization
        super().__init__(...)
        
        # ✨ ADD THIS:
        self.elite_manager = EliteSystemManager(enable_elite=True)
        logger.info("✅ ULTRON ELITE initialized in main.py")

# ─────────────────────────────────────────────────────────
# In your auto_send_pronostics job:
# ─────────────────────────────────────────────────────────

async def auto_send_pronostics(self):
    '''
    Scheduled job (usually runs every 30 minutes)
    Now enhanced with ULTRON ELITE analysis
    '''
    try:
        picks = await self.get_all_picks()  # Your existing function
        
        if not picks:
            logger.info("No picks to send")
            return
            
        for pick in picks:
            # ✨ ENHANCE WITH ELITE
            enhanced_pick = await enhance_prediction(pick, self.elite_manager)
            
            # Use enhanced confidence
            confidence = enhanced_pick.get('confidence', 0)
            
            # Check ELITE threshold
            if self.elite_manager.elite_system.threshold_engine.should_send_pick(
                pick.get('sport', 'NBA'),
                confidence
            ):
                # ✨ Build message with ELITE data
                if 'elite' in enhanced_pick:
                    elite_data = enhanced_pick['elite']
                    
                    # Build enhanced message
                    message = f"""
🟢 ULTRON PICK
━━━━━━━━━━━━━━━━━━━
🎯 {elite_data['selection']} ({elite_data['bet_type']})

📊 CONFIDENCE: {elite_data['confidence']}%
💰 EXPECTED VALUE: +{elite_data['expected_value']}%
🧠 SHARP SCORE: {elite_data['sharp_score']}
🏦 SPORTSBOOK: {elite_data['sportsbook']}

💵 Recommended: {elite_data['recommended_bet_size']}% bankroll

🔍 Analysis:
"""
                    for reason in elite_data['reasoning']:
                        message += f"• {reason}\\n"
                    
                    message += "━━━━━━━━━━━━━━━━━━━"
                else:
                    # Fallback to standard format
                    message = self.format_standard_pick(pick)
                
                # Send to premium channel
                await self.send_telegram_message(
                    message,
                    chat_id=self.PREMIUM_CHAT_ID
                )
                
                # ✨ Optional: Also send to free channel (top pick only)
                if confidence >= 75:  # Only highest confidence
                    await self.send_telegram_message(
                        f"🟢 {elite_data['selection']}\\n",
                        chat_id=self.FREE_CHAT_ID
                    )
                
                logger.info(f"Sent: {elite_data['selection']} ({confidence}%)")
                
    except Exception as e:
        logger.error(f"auto_send_pronostics error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────
# Optional: Add command to check ELITE status
# ─────────────────────────────────────────────────────────

async def cmd_elite_status(update, context):
    '''Show ELITE system status in Telegram'''
    status = self.elite_manager.get_elite_status()
    
    message = f"""
⚡ ULTRON ELITE STATUS
━━━━━━━━━━━━━━━━━
✅ Enabled: {status['enabled']}

📊 Confidence Thresholds:
"""
    for sport, threshold in status.get('thresholds', {}).items():
        message += f"  {sport}: {threshold}%\\n"
    
    message += f"\\n🧠 Learning Weights:\\n"
    for signal, weight in status.get('learning_weights', {}).items():
        message += f"  {signal}: {weight:.2f}x\\n"
    
    message += f"\\n📈 Picks Recorded: {status.get('win_history_count', 0)}"
    
    await update.message.reply_text(message)

# Add to dispatcher:
application.add_handler(CommandHandler("elite", cmd_elite_status))
"""

# ============================================================
# 🎯 INTEGRATION SNIPPET #2: ultron_multisports_v6_0.py
# ============================================================

ULTRON_V6_INTEGRATION = """
# Add these imports at the top of ultron_multisports_v6_0.py:
# (Around line 10-20)

from ultron_elite_integration import EliteSystemManager, enhance_prediction
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# In your main UltronBot class __init__:
# (Around line 200-250)
# ─────────────────────────────────────────────────────────

class UltronBot:
    def __init__(self, ...):
        # ... your existing initialization ...
        
        # ✨ ADD THIS:
        self.elite_manager = EliteSystemManager(enable_elite=True)
        logger.info("✅ ELITE initialized in ultron_multisports_v6_0")

# ─────────────────────────────────────────────────────────
# Enhance your prediction functions (e.g., get_nba_picks):
# ─────────────────────────────────────────────────────────

async def get_nba_picks(self):
    '''
    Enhanced with ULTRON ELITE analysis
    Place this in your existing get_nba_picks function
    '''
    picks = []
    
    for game in self.nba_games:
        try:
            # Your existing prediction logic
            prediction = self.predict_nba_game(game)
            
            # ✨ ENHANCE WITH ELITE
            enhanced = await enhance_prediction({
                "sport": "NBA",
                "selection": prediction['team'],
                "confidence": prediction['confidence'],
                "odds": prediction.get('odds', 1.87),
                "home_team": {
                    "name": game['home']['name'],
                    "wins_last_10": game['home'].get('wins_l10', 5),
                    "ats_wins_last_10": game['home'].get('ats_l10', 5),
                    "points_scored": game['home'].get('ppg', 110),
                    "points_allowed": game['home'].get('pa', 110),
                    "offensive_rating": game['home'].get('ortg', 110),
                    "defensive_rating": game['home'].get('drtg', 110),
                    "pace": game['home'].get('pace', 100),
                    "injuries": len(game['home'].get('injuries', [])),
                    "rest_days": game['home'].get('rest_days', 1)
                },
                "away_team": {
                    "name": game['away']['name'],
                    "wins_last_10": game['away'].get('wins_l10', 5),
                    "ats_wins_last_10": game['away'].get('ats_l10', 5),
                    "points_scored": game['away'].get('ppg', 110),
                    "points_allowed": game['away'].get('pa', 110),
                    "offensive_rating": game['away'].get('ortg', 110),
                    "defensive_rating": game['away'].get('drtg', 110),
                    "pace": game['away'].get('pace', 100),
                    "injuries": len(game['away'].get('injuries', [])),
                    "rest_days": game['away'].get('rest_days', 1)
                },
                "market_type": "MoneyLine"
            }, self.elite_manager)
            
            # Use enhanced confidence
            final_confidence = enhanced.get('confidence', prediction['confidence'])
            
            # ✨ Store ELITE data if available
            if 'elite' in enhanced:
                prediction['elite'] = enhanced['elite']
                prediction['confidence'] = final_confidence
                prediction['sharp_score'] = enhanced['elite']['sharp_score']
                prediction['expected_value'] = enhanced['elite']['expected_value']
            
            picks.append(prediction)
            
        except Exception as e:
            logger.error(f"NBA pick error: {e}")
            continue
    
    return picks


# ─────────────────────────────────────────────────────────
# In auto_send_pronostics (main scheduled job):
# (Around line 4500-4600)
# ─────────────────────────────────────────────────────────

async def auto_send_pronostics(self):
    '''Main scheduled job - 30min intervals'''
    
    # Get all picks
    nba_picks = await self.get_nba_picks()
    nhl_picks = await self.get_nhl_picks()
    mlb_picks = await self.get_mlb_picks()
    
    all_picks = nba_picks + nhl_picks + mlb_picks
    
    for pick in all_picks:
        try:
            # ✨ Check ELITE threshold
            if self.elite_manager.elite_system and \\
               not self.elite_manager.elite_system.threshold_engine.should_send_pick(
                   pick.get('sport', 'NBA'),
                   pick.get('confidence', 60)
               ):
                logger.info(f"Pick filtered by ELITE: {pick.get('selection')}")
                continue
            
            # Build message with ELITE data
            message = self.format_pick_message(pick)
            
            # ✨ ADD ELITE-SPECIFIC DETAILS
            if 'elite' in pick:
                elite = pick['elite']
                message += f"\\n🧠 Sharp: {elite['sharp_score']}\\n"
                message += f"💰 EV: +{elite['expected_value']}%\\n"
                message += f"🎯 Kelly: {elite['recommended_bet_size']}% bankroll"
            
            # Send to channels
            await self.send_telegram(
                f"{message}",
                chat_id=self.PREMIUM_CHAT_ID
            )
            
            if pick.get('confidence', 0) >= 75:
                await self.send_telegram(
                    f"{pick['selection']} ({pick['bet_type']})",
                    chat_id=self.FREE_CHAT_ID
                )
            
        except Exception as e:
            logger.error(f"Pronostic send error: {e}")


# ─────────────────────────────────────────────────────────
# Recording outcomes for ELITE learning:
# (Call this when you verify pick results next day)
# ─────────────────────────────────────────────────────────

async def record_pick_result(self, pick_id, result, roi):
    '''
    Record prediction outcome for ELITE to learn from
    Call this daily with verified results
    '''
    if self.elite_manager.elite_system:
        self.elite_manager.elite_system.learning_engine.record_outcome(
            prediction_id=pick_id,
            result=result,  # True/False for win/loss
            roi=roi         # Actual ROI achieved
        )
        logger.info(f"Recorded outcome for {pick_id}: {result} ({roi}% ROI)")
"""

# ============================================================
# 📋 MINIMAL SETUP (Quick Copy-Paste)
# ============================================================

MINIMAL_SETUP = """
# Minimal setup - Just 3 lines to add!

# 1️⃣ Import
from ultron_elite_integration import EliteSystemManager

# 2️⃣ Initialize (in __init__)
self.elite_manager = EliteSystemManager(enable_elite=True)

# 3️⃣ Use in your prediction loop
enhanced = await enhance_prediction(your_pick, self.elite_manager)
if 'elite' in enhanced:
    print(f"Sharp Score: {enhanced['elite']['sharp_score']}")
    print(f"Confidence: {enhanced['elite']['confidence']}")
"""

# ============================================================
# 🔧 DEBUGGING & TESTING
# ============================================================

DEBUGGING_CODE = """
# Test ELITE locally before full integration

import asyncio
from ultron_elite_integration import EliteSystemManager, enhance_prediction

async def test_elite():
    # Initialize
    manager = EliteSystemManager(enable_elite=True)
    
    # Sample pick
    test_pick = {
        "sport": "NBA",
        "selection": "Lakers",
        "confidence": 55,
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
        }
    }
    
    # Enhance
    enhanced = await enhance_prediction(test_pick, manager)
    
    # Print results
    print("✅ ELITE Analysis Results:")
    if 'elite' in enhanced:
        elite = enhanced['elite']
        print(f"  Confidence: {elite['confidence']}%")
        print(f"  Sharp Score: {elite['sharp_score']}")
        print(f"  EV: +{elite['expected_value']}%")
        print(f"  Bet Size: {elite['recommended_bet_size']}%")
        print(f"  Reasoning: {elite['reasoning']}")
    else:
        print("  No ELITE enhancement (disabled or error)")

# Run test
if __name__ == "__main__":
    asyncio.run(test_elite())
"""

# ============================================================
# 📊 MONITORING & LOGGING
# ============================================================

LOGGING_SETUP = """
# Add to your logging configuration

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get ELITE logger
elite_logger = logging.getLogger('ultron_elite')

# Set to DEBUG for detailed output
elite_logger.setLevel(logging.DEBUG)

# Now ELITE errors/info will show in your logs:
# [2026-05-24 18:30:45] ultron_elite - INFO - ✅ ULTRON ELITE module loaded
# [2026-05-24 18:30:50] ultron_elite - INFO - Updated NBA threshold to 63
# [2026-05-24 18:31:00] ultron_elite - INFO - Elite prediction: Lakers @ 68%
"""

# ============================================================
# 🚀 QUICK START CHECKLIST
# ============================================================

CHECKLIST = """
✅ ULTRA ELITE INTEGRATION CHECKLIST

□ Step 1: Copy files created
  ✅ ultron_elite.py (850 lines) - in Ultron_MultiSport/
  ✅ ultron_elite_integration.py - in Ultron_MultiSport/
  ✅ ultron_elite_examples.py - (optional, for learning)
  ✅ ULTRON_ELITE_INTEGRATION.md - documentation

□ Step 2: Update imports
  Add to main.py or ultron_multisports_v6_0.py:
  from ultron_elite_integration import EliteSystemManager

□ Step 3: Initialize ELITE
  In __init__:
  self.elite_manager = EliteSystemManager(enable_elite=True)

□ Step 4: Enhance predictions
  In your pick loop:
  enhanced = await enhance_prediction(pick, self.elite_manager)

□ Step 5: Test
  python ultron_elite_examples.py

□ Step 6: Deploy
  Just run as normal! ELITE will be active.

□ Step 7: Monitor
  Check logs for ELITE entries
  Verify thresholds being applied

🎉 You're now powered by ULTRON ELITE!
"""

if __name__ == "__main__":
    print("="*80)
    print("ULTRON ELITE - INTEGRATION SNIPPETS")
    print("="*80)
    print()
    print(CHECKLIST)
    print()
    print("="*80)
    print("For main.py integration, copy from MAIN_PY_INTEGRATION")
    print("For ultron_multisports_v6_0.py, copy from ULTRON_V6_INTEGRATION")
    print("="*80)
