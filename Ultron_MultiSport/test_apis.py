#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script pour vérifier les APIs NBA
"""
import requests
import json

print("="*60)
print("TEST: ESPN Scoreboard API")
print("="*60)

url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        events = data.get('events', [])
        print(f"Events found: {len(events)}")
        if events:
            print("\nFirst event:")
            print(json.dumps(events[0], indent=2)[:500])
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "="*60)
print("TEST: ESPN Live API")
print("="*60)

url = "https://www.espn.com/api/site/v2/sports/basketball/nba/scoreboard"
try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        events = data.get('events', [])
        print(f"Events found: {len(events)}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "="*60)
print("TEST: BallDontLie API")
print("="*60)

url = "https://api.balldontlie.io/v1/games?per_page=20"
try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        games = data.get('data', [])
        print(f"Games found: {len(games)}")
        if games:
            print("\nFirst game:")
            print(json.dumps(games[0], indent=2)[:500])
except Exception as e:
    print(f"ERROR: {e}")
