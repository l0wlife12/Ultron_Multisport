#!/usr/bin/env python3
import requests
import datetime

print("="*60)
print("CHECKING CURRENT NBA MATCHES ON ESPN API")
print("="*60)
print(f"Time: {datetime.datetime.now()}\n")

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
response = requests.get(url, timeout=10)
data = response.json()

events = data.get('events', [])
print(f"Total events returned: {len(events)}\n")

if events:
    print("Current NBA Matches:")
    for i, event in enumerate(events[:10], 1):
        comp = event.get('competitions', [{}])[0]
        competitors = comp.get('competitors', [])
        if len(competitors) >= 2:
            away = competitors[0].get('team', {}).get('name', 'N/A')
            home = competitors[1].get('team', {}).get('name', 'N/A')
            status = event.get('status', {}).get('type', {}).get('description', 'N/A')
            date = event.get('date', 'N/A')
            print(f"{i}. {away} @ {home}")
            print(f"   Status: {status}")
            print(f"   Date: {date}\n")
else:
    print("No matches found!")
