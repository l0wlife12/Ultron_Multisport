#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test et validation du MLB 5-pick limiter
Simulate le comportement du limiter pour 8 picks de MLB dans une même journée
"""

import datetime

# Simuler le compteur global
_mlb_picks_sent_today = {"date": None, "count": 0}
MLB_PICKS_MAX_PER_DAY = 5

def test_mlb_limiter():
    """Test le limiter avec 8 picks simulés"""
    print("="*60)
    print("TEST: MLB 5-Pick Daily Limiter")
    print("="*60)
    
    global _mlb_picks_sent_today
    
    # Simuler 8 matchs de MLB dans une même journée
    test_matches = [
        ("Braves", "Orioles"),
        ("Yankess", "Red Sox"),
        ("Dodgers", "Padres"),
        ("Brewers", "Pirates"),
        ("Astros", "Rangers"),
        ("Rockies", "Diamondbacks"),
        ("Royals", "Twins"),
        ("Cardinals", "Cubs"),
    ]
    
    date_key = datetime.datetime.now().strftime("%Y%m%d")
    picks_sent = []
    picks_blocked = []
    
    print(f"\nDate: {date_key}")
    print(f"Max picks per day: {MLB_PICKS_MAX_PER_DAY}")
    print("-" * 60)
    
    for i, (away, home) in enumerate(test_matches, 1):
        # Simule le check et increment du limiter
        global _mlb_picks_sent_today
        
        # Reset compteur si nouveau jour
        if _mlb_picks_sent_today["date"] != date_key:
            _mlb_picks_sent_today["date"] = date_key
            _mlb_picks_sent_today["count"] = 0
            print(f"🔄 Counter reset for {date_key}\n")
        
        # CHECK: Avant de générer le pick
        if _mlb_picks_sent_today["count"] >= MLB_PICKS_MAX_PER_DAY:
            picks_blocked.append((i, away, home))
            print(f"❌ Pick #{i} BLOCKED: {away} @ {home}")
            print(f"   Reason: Daily limit reached ({MLB_PICKS_MAX_PER_DAY} max)")
            continue
        
        # INCREMENT: Après ajout du pick
        _mlb_picks_sent_today["count"] += 1
        picks_sent.append((i, away, home))
        print(f"✅ Pick #{i} SENT: {away} @ {home}")
        print(f"   Status: {_mlb_picks_sent_today['count']}/{MLB_PICKS_MAX_PER_DAY}")
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"✅ Picks SENT:    {len(picks_sent)}")
    print(f"❌ Picks BLOCKED: {len(picks_blocked)}")
    print(f"📊 Total matches: {len(test_matches)}")
    
    if picks_blocked:
        print(f"\nBlocked picks:")
        for idx, away, home in picks_blocked:
            print(f"  - Pick #{idx}: {away} @ {home}")
    
    # Validation
    print("\n" + "="*60)
    print("VALIDATION")
    print("="*60)
    
    if len(picks_sent) == MLB_PICKS_MAX_PER_DAY:
        print("✅ PASS: Exactly 5 picks sent (correct!)")
        return True
    else:
        print(f"❌ FAIL: Expected {MLB_PICKS_MAX_PER_DAY}, got {len(picks_sent)}")
        return False

if __name__ == "__main__":
    success = test_mlb_limiter()
    exit(0 if success else 1)
