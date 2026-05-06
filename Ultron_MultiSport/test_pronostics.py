#!/usr/bin/env python3
"""Test pronostics function output"""

import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_prediction(away_team, home_team):
    """Base prediction generator (simplified for testing)"""
    return {
        "pick": f"{home_team} -3 Spread",
        "odds": "1.88",
        "risk": "LOW",
        "reasoning": "Test prediction",
        "confidence": 0.75,
        "value_bet": True
    }

def calculate_confidence(strength_diff, odds, pick_type, away_offense, home_offense):
    """Calculate confidence score"""
    confidence_base = 0.6
    if abs(strength_diff) > 8:
        confidence_base += 0.15
    elif abs(strength_diff) > 5:
        confidence_base += 0.10
    return min(confidence_base, 0.95)

def generate_alternatives(away_team, home_team, main_pred, strength_diff, away_offense, home_offense, home_offense_dup, away_defense):
    """Generate alternatives"""
    return [
        {"pick": f"Over 215 pts", "odds": "1.87", "confidence": 0.72, "risk": "MEDIUM", "reasoning": "High scoring", "value_bet": False},
        {"pick": f"Under 210 pts", "odds": "1.85", "confidence": 0.70, "risk": "MEDIUM", "reasoning": "Low scoring", "value_bet": False}
    ]

def generate_complete_prediction(away_team, home_team):
    """Generate full prediction with alternatives"""
    main_pred = generate_prediction(away_team, home_team)
    
    team_data = {
        "hawks": {"strength": 81, "offense": 85, "defense": 78},
        "cavaliers": {"strength": 86, "offense": 87, "defense": 84},
    }
    
    away_clean = away_team.lower()
    home_clean = home_team.lower()
    
    away_data = team_data.get(away_clean, {"strength": 80, "offense": 82, "defense": 78})
    home_data = team_data.get(home_clean, {"strength": 80, "offense": 82, "defense": 78})
    
    strength_diff = home_data['strength'] - away_data['strength']
    
    alternatives = generate_alternatives(
        away_team, home_team, main_pred, strength_diff,
        away_data['offense'], home_data['offense'],
        home_data['offense'], away_data['defense']
    )
    
    main_pred['alternatives'] = alternatives
    return main_pred

# Test pronostics logic
print("="*60)
print("Testing Pronostics Logic")
print("="*60)

predictions = []

# METHODE 1: ESPN Scoreboard
print("\nMETHODE 1: ESPN Scoreboard API")
try:
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        events = data.get('events', [])
        print(f"✓ ESPN returned {len(events)} events")
        
        for event in events[:3]:  # Get first 3
            try:
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                if len(competitors) >= 2:
                    away = competitors[0].get('team', {}).get('name', '').strip()
                    home = competitors[1].get('team', {}).get('name', '').strip()
                    
                    if away and home:
                        prediction = generate_complete_prediction(away, home)
                        predictions.append((away, home, prediction))
                        print(f"  ✓ Added: {away} @ {home}")
            except Exception as e:
                print(f"  Error: {e}")
    else:
        print(f"✗ ESPN API response: {response.status_code}")
except Exception as e:
    print(f"✗ ESPN API error: {e}")

print(f"\n✓ Total predictions found: {len(predictions)}")

if predictions:
    print("\n" + "="*60)
    print(f"✅ {len(predictions)} matchs NBA EN DIRECT")
else:
    print("\n" + "="*60)
    print("⚠️ No live matches found - would show fallback")

print("="*60)
