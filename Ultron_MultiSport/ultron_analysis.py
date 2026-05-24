#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON Analysis Module - Bridge between main.py and ultron_multisports_v6_0
Provides pick analysis, filtering, and formatting functions
"""

import os
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
try:
    from ultron_multisports_v6_0 import (
        TELEGRAM_CHAT_ID,
        TELEGRAM_CHAT_ID_VIP,
        run_ultron_pipeline,
    )
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
except ImportError as e:
    print(f"⚠️ Could not import from ultron_multisports_v6_0: {e}")
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    TELEGRAM_CHAT_ID_VIP = os.getenv('TELEGRAM_CHAT_ID_VIP')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


# Export chat IDs for main.py compatibility
FREE_CHAT_ID = TELEGRAM_CHAT_ID
PREMIUM_CHAT_ID = TELEGRAM_CHAT_ID_VIP


@dataclass
class Pick:
    """Data class for a betting pick"""
    league: str
    team: str
    opponent: str
    bet: str
    odds: float
    confidence: int
    type: str  # 'ML', 'SPREAD', 'RUNLINE', 'PUCKLINE', 'PROPS'
    reasoning: str
    
    def __eq__(self, other):
        if not isinstance(other, Pick):
            return False
        return (self.league == other.league and 
                self.team == other.team and 
                self.bet == other.bet and 
                self.odds == other.odds)
    
    def __hash__(self):
        return hash((self.league, self.team, self.bet, str(self.odds)))


async def send_telegram_async(message: str, is_premium: bool = False) -> bool:
    """
    Send message to Telegram channel
    
    Args:
        message: Message text to send
        is_premium: True for PREMIUM channel, False for FREE channel
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        from telegram import Bot
        
        chat_id = PREMIUM_CHAT_ID if is_premium else FREE_CHAT_ID
        
        if not chat_id or not TELEGRAM_BOT_TOKEN:
            print(f"⚠️ Missing Telegram configuration (chat_id={chat_id}, token={'✓' if TELEGRAM_BOT_TOKEN else '✗'})")
            return False
        
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        return True
        
    except Exception as e:
        print(f"❌ Telegram send error: {e}")
        return False


def send_telegram(message: str, is_premium: bool = False) -> bool:
    """
    Synchronous wrapper for send_telegram_async
    
    Args:
        message: Message text to send
        is_premium: True for PREMIUM channel, False for FREE channel
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(send_telegram_async(message, is_premium))
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        return False


def get_pipeline_results(bankroll: int = 1000) -> List[Pick]:
    """
    Get picks from the ULTRON pipeline
    
    Args:
        bankroll: Starting bankroll for sizing
        
    Returns:
        List of Pick objects
    """
    try:
        # Call the main pipeline from ultron_multisports_v6_0
        from ultron_multisports_v6_0 import run_ultron_pipeline
        
        results = run_ultron_pipeline(bankroll=bankroll)
        
        # Convert results to Pick objects if needed
        if isinstance(results, list) and len(results) > 0:
            if isinstance(results[0], Pick):
                return results
            # Convert dict results to Pick objects
            picks = []
            for result in results:
                if isinstance(result, dict):
                    try:
                        pick = Pick(
                            league=result.get('league', 'UNKNOWN'),
                            team=result.get('team', ''),
                            opponent=result.get('opponent', ''),
                            bet=result.get('bet', ''),
                            odds=float(result.get('odds', 0)),
                            confidence=int(result.get('confidence', 50)),
                            type=result.get('type', 'ML'),
                            reasoning=result.get('reasoning', '')
                        )
                        picks.append(pick)
                    except Exception as e:
                        print(f"⚠️ Could not convert result to Pick: {e}")
                        continue
            return picks
        return []
        
    except Exception as e:
        print(f"❌ Error running pipeline: {e}")
        return []


def has_good_picks(results: List[Any]) -> bool:
    """Check if results contain quality picks"""
    if not results:
        return False
    return len(results) > 0 and any(
        getattr(r, 'confidence', 0) >= 65 or r.get('confidence', 0) >= 65
        for r in results
    )


def is_game_soon(pick: Any, hours: int = 2) -> bool:
    """Check if game is starting within N hours"""
    try:
        from datetime import datetime, timedelta, timezone
        import pytz
        
        quebec_tz = pytz.timezone('America/Toronto')
        now = datetime.now(quebec_tz)
        
        # Simplified check - would need game time from pick object
        return True  # Placeholder
    except Exception:
        return True


def get_pick_type(pick: Any) -> str:
    """Get the type of pick (ML, SPREAD, RUNLINE, PUCKLINE, PROPS)"""
    return getattr(pick, 'type', 'ML') or pick.get('type', 'ML')


def should_send(results: List[Any]) -> bool:
    """Check if picks meet quality threshold for sending"""
    if not results:
        return False
    
    # Need at least one SAFE pick or high EV pick
    for result in results:
        confidence = getattr(result, 'confidence', 0) or result.get('confidence', 0)
        if confidence >= 70:  # SAFE threshold
            return True
    
    return False


def get_best_pick(results: List[Any]) -> Optional[Any]:
    """Get the single best pick from results"""
    if not results:
        return None
    
    # Sort by confidence, return highest
    sorted_results = sorted(
        results,
        key=lambda x: getattr(x, 'confidence', 0) or x.get('confidence', 0),
        reverse=True
    )
    return sorted_results[0] if sorted_results else None


def get_premium_picks(results: List[Any]) -> List[Any]:
    """Get all premium-quality (SAFE) picks"""
    return get_safe_picks(results)


def is_1h_before(pick: Any) -> bool:
    """Check if game starts within 1 hour"""
    return is_game_soon(pick, hours=1)


def is_vip_pick(pick: Any) -> bool:
    """Check if pick is VIP quality"""
    confidence = getattr(pick, 'confidence', 0) or pick.get('confidence', 0)
    return confidence >= 75


def analyze(picks: List[Any]) -> Dict[str, Any]:
    """Analyze picks and return statistics"""
    if not picks:
        return {'total': 0, 'avg_confidence': 0, 'safe_picks': 0}
    
    confidences = [getattr(p, 'confidence', 0) or p.get('confidence', 0) for p in picks]
    safe_count = sum(1 for c in confidences if c >= 70)
    
    return {
        'total': len(picks),
        'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
        'safe_picks': safe_count,
        'highest_confidence': max(confidences) if confidences else 0,
    }


def get_safe_picks(results: List[Any]) -> List[Any]:
    """Get all SAFE picks (confidence >= 70)"""
    return [
        r for r in results 
        if (getattr(r, 'confidence', 0) or r.get('confidence', 0)) >= 70
    ]


def format_free_pick(pick: Any) -> str:
    """Format a pick for FREE channel message"""
    try:
        team = getattr(pick, 'team', '') or pick.get('team', '')
        bet = getattr(pick, 'bet', '') or pick.get('bet', '')
        odds = getattr(pick, 'odds', 0) or pick.get('odds', 0)
        confidence = getattr(pick, 'confidence', 0) or pick.get('confidence', 0)
        reasoning = getattr(pick, 'reasoning', '') or pick.get('reasoning', '')
        league = getattr(pick, 'league', '') or pick.get('league', '')
        
        msg = f"""
🔥 <b>FREE PICK</b>

<b>League:</b> {league}
<b>Team:</b> {team}
<b>Bet:</b> {bet}
<b>Odds:</b> {odds}
<b>Confidence:</b> {confidence}%

<b>Reasoning:</b>
{reasoning}

#ULTRON #FREEPICK
"""
        return msg.strip()
    except Exception as e:
        print(f"❌ Error formatting free pick: {e}")
        return f"📊 PICK: {getattr(pick, 'team', 'UNKNOWN')} {getattr(pick, 'bet', '')}"


def format_premium(picks: List[Any]) -> str:
    """Format multiple picks for PREMIUM channel message"""
    try:
        if not picks:
            return "❌ No premium picks available"
        
        msg = f"""
💎 <b>PREMIUM PICKS</b> ({len(picks)} SAFE picks)

"""
        for i, pick in enumerate(picks, 1):
            team = getattr(pick, 'team', '') or pick.get('team', '')
            bet = getattr(pick, 'bet', '') or pick.get('bet', '')
            odds = getattr(pick, 'odds', 0) or pick.get('odds', 0)
            confidence = getattr(pick, 'confidence', 0) or pick.get('confidence', 0)
            
            msg += f"{i}. <b>{team}</b> - {bet} @ {odds} ({confidence}%)\n"
        
        msg += "\n#ULTRON #PREMIUM #VIP"
        return msg.strip()
    except Exception as e:
        print(f"❌ Error formatting premium picks: {e}")
        return f"💎 PREMIUM: {len(picks)} picks"


def already_sent(pick: Any) -> str:
    """Generate a unique key for a pick to track duplicates"""
    try:
        team = getattr(pick, 'team', '') or pick.get('team', '')
        bet = getattr(pick, 'bet', '') or pick.get('bet', '')
        league = getattr(pick, 'league', '') or pick.get('league', '')
        return f"{league}:{team}:{bet}"
    except Exception:
        return str(pick)


# Additional analysis functions
def get_confidence_distribution(results: List[Any]) -> Dict[str, int]:
    """Get distribution of confidence levels"""
    distribution = {'vip': 0, 'safe': 0, 'good': 0, 'fair': 0, 'poor': 0}
    
    for result in results:
        confidence = getattr(result, 'confidence', 0) or result.get('confidence', 0)
        if confidence >= 85:
            distribution['vip'] += 1
        elif confidence >= 75:
            distribution['safe'] += 1
        elif confidence >= 65:
            distribution['good'] += 1
        elif confidence >= 55:
            distribution['fair'] += 1
        else:
            distribution['poor'] += 1
    
    return distribution


def filter_by_league(results: List[Any], league: str) -> List[Any]:
    """Filter picks by league (NBA, NHL, MLB)"""
    return [
        r for r in results 
        if (getattr(r, 'league', '').upper() == league.upper() or 
            r.get('league', '').upper() == league.upper())
    ]


if __name__ == '__main__':
    print("✅ ULTRON Analysis Module loaded successfully")
    print(f"   FREE_CHAT_ID: {FREE_CHAT_ID}")
    print(f"   PREMIUM_CHAT_ID: {PREMIUM_CHAT_ID}")
