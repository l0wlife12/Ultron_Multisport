import requests
import datetime

date_str = datetime.datetime.now().strftime("%Y%m%d")
print(f"\n{'='*60}")
print(f"NBA Matches for {date_str}")
print(f"{'='*60}\n")

url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
try:
    resp = requests.get(url, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        events = data.get('events', [])
        print(f"✅ Found {len(events)} events\n")
        
        for i, event in enumerate(events[:20], 1):
            try:
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                status = event.get('status', {}).get('type', {}).get('description', 'Unknown')
                
                if len(competitors) >= 2:
                    away = competitors[0].get('team', {}).get('name', 'Team')
                    home = competitors[1].get('team', {}).get('name', 'Team')
                    
                    print(f"{i:2}. {away:25} @ {home:25} | {status}")
            except:
                pass
    else:
        print(f"❌ API returned {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n{'='*60}\n")
