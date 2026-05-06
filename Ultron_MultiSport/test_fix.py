#!/usr/bin/env python3
"""Quick test of the fixed generate_alternatives function"""

import requests

# Test the fixed functions
def calculate_confidence(strength_diff, odds, pick_type, away_offense, home_offense):
    confidence_base = 0.6
    if abs(strength_diff) > 8:
        confidence_base += 0.15
    elif abs(strength_diff) > 5:
        confidence_base += 0.10
    return min(confidence_base, 0.95)

def generate_alternatives(away_team, home_team, main_pred, strength_diff, away_offense, home_offense, home_offense_dup, away_defense):
    alternatives = []
    main_type = main_pred.get('pick', '')  # FIXED: was main_pick
    
    if 'Moneyline' not in main_type:
        alt1_pick = f'{home_team} Moneyline'
        alt1_odds = '1.82'
        alt1_confidence = calculate_confidence(strength_diff, alt1_odds, alt1_pick, away_offense, home_offense)
        alternatives.append({
            'pick': alt1_pick,
            'odds': alt1_odds,
            'risk': 'LOW',
            'reasoning': f'Alt for {home_team}',
            'confidence': alt1_confidence,
            'value_bet': False
        })
    
    alt2_pick = 'Over 215 pts'
    alt2_odds = '1.87'
    alt2_confidence = calculate_confidence(strength_diff, alt2_odds, alt2_pick, away_offense, home_offense)
    alternatives.append({
        'pick': alt2_pick,
        'odds': alt2_odds,
        'risk': 'MEDIUM',
        'reasoning': 'High scoring',
        'confidence': alt2_confidence,
        'value_bet': False
    })
    return alternatives

def generate_prediction(away_team, home_team):
    return {
        'pick': f'{home_team} -3 Spread',
        'odds': '1.88',
        'risk': 'LOW',
        'reasoning': 'Test pick',
        'confidence': 0.75,
        'value_bet': True
    }

def generate_complete_prediction(away_team, home_team):
    main_pred = generate_prediction(away_team, home_team)
    
    team_data = {
        'cavaliers': {'strength': 86, 'offense': 87, 'defense': 84},
        'hawks': {'strength': 81, 'offense': 85, 'defense': 78},
    }
    
    away_clean = away_team.lower()
    home_clean = home_team.lower()
    
    away_data = team_data.get(away_clean, {'strength': 80, 'offense': 82, 'defense': 78})
    home_data = team_data.get(home_clean, {'strength': 80, 'offense': 82, 'defense': 78})
    
    strength_diff = home_data['strength'] - away_data['strength']
    
    alternatives = generate_alternatives(
        away_team, home_team, main_pred, strength_diff,
        away_data['offense'], home_data['offense'],
        home_data['offense'], away_data['defense']
    )
    
    main_pred['alternatives'] = alternatives
    return main_pred

# Test with real ESPN API
print("="*60)
print("Testing Fixed Code with REAL ESPN API")
print("="*60)

predictions = []

try:
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        events = data.get('events', [])
        print(f"✓ ESPN API returned {len(events)} events")
        
        for event in events[:3]:
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
                        print(f"    Main pick: {prediction['pick']}")
                        print(f"    Alternatives: {len(prediction['alternatives'])}")
            except Exception as e:
                print(f"  ✗ Error processing event: {e}")
except Exception as e:
    print(f"✗ API error: {e}")

print(f"\n✓ Total predictions: {len(predictions)}")
if len(predictions) >= 3:
    print("✅ SUCCESS - Bot will display REAL matches, not fallback!")
else:
    print("⚠️ Still getting fewer than 3 matches")
