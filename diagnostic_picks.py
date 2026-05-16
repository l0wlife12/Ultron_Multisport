#!/usr/bin/env python3
"""
DIAGNOSTIC — Ultron Pick Memory
Vérifie rapidement :
1. DB PostgreSQL accessible ?
2. Picks dans la DB/JSON ?
3. Matchs d'aujourd'hui selon ESPN ?
4. Picks qui auraient dû être envoyés ?
"""
import os
import sys
import json
from datetime import datetime

# Les variables d'env
sys.path.insert(0, '/app/Ultron_MultiSport')

print("=" * 70)
print("🔍 DIAGNOSTIC ULTRON PICKS")
print("=" * 70)

# ── CHECK 1 : DATABASE ──────────────────────────────────────────
print("\n1️⃣ DATABASE PostgreSQL")
print("-" * 70)

db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    print(f"✅ DATABASE_URL présent")
    url_safe = db_url.replace(db_url.split('@')[0].split('://')[1], '***') if '@' in db_url else db_url
    print(f"   {url_safe[:60]}...")
    
    try:
        import psycopg2
        url_fixed = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url_fixed)
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM pick_store;")
                count = cur.fetchone()[0]
                print(f"✅ Connexion DB OK")
                print(f"   Rows dans pick_store: {count}")
                if count > 0:
                    cur.execute("SELECT data FROM pick_store LIMIT 1;")
                    data = cur.fetchone()[0]
                    picks = data.get('picks', [])
                    print(f"   Picks enregistrés: {len(picks)}")
                    if picks:
                        latest = picks[-1]
                        print(f"   Dernier pick: {latest.get('date')} — {latest.get('pick_team')} @ {latest.get('odds')}")
    except Exception as e:
        print(f"❌ Erreur DB: {e}")
else:
    print(f"❌ DATABASE_URL ABSENT")
    print(f"   Fallback sur JSON local uniquement (ÉPHÉMÈRE sur Railway!)")

# ── CHECK 2 : FICHIER JSON LOCAL ──────────────────────────────
print("\n2️⃣ FICHIER JSON LOCAL")
print("-" * 70)

json_files = [
    "/data/picks_history.json",
    "./Ultron_MultiSport/picks_history.json",
    "./picks_history.json",
]

for json_path in json_files:
    if os.path.exists(json_path):
        print(f"✅ Fichier trouvé: {json_path}")
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                picks = data.get('picks', [])
                stats = data.get('stats', {})
                print(f"   Picks: {len(picks)}")
                print(f"   Stats: {stats.get('wins')}W-{stats.get('losses')}L ({stats.get('win_rate', 0):.1%})")
                if picks:
                    latest = picks[-1]
                    print(f"   Dernier: {latest.get('date')} — {latest.get('pick_team')}")
        except Exception as e:
            print(f"❌ Erreur lecture: {e}")
        break
else:
    print(f"❌ Aucun fichier JSON trouvé")

# ── CHECK 3 : MATCHS ESPN AUJOURD'HUI ──────────────────────────
print("\n3️⃣ MATCHS ESPN AUJOURD'HUI")
print("-" * 70)

try:
    import requests
    sports = [
        ("basketball/nba", "🏀 NBA"),
        ("hockey/nhl", "🏒 NHL"),
        ("football/nfl", "🏈 NFL"),
    ]
    
    today = datetime.utcnow().strftime("%Y%m%d")
    tomorrow = (datetime.utcnow().replace(day=datetime.utcnow().day+1) if datetime.utcnow().day < 28 else datetime.utcnow().replace(day=1)).strftime("%Y%m%d")
    
    for sport_path, label in sports:
        all_matches = 0
        scheduled = 0
        in_progress = 0
        
        for date_str in [today, tomorrow]:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date_str}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    events = resp.json().get('events', [])
                    all_matches += len(events)
                    for evt in events:
                        status = evt.get('status', {}).get('type', {}).get('description', '').lower()
                        if 'scheduled' in status or 'pre' in status:
                            scheduled += 1
                        elif 'progress' in status or 'live' in status or 'in progress' in status:
                            in_progress += 1
            except Exception as e:
                print(f"   Erreur {label}: {e}")
        
        print(f"{label}: {all_matches} total | {scheduled} scheduled | {in_progress} in progress")
except Exception as e:
    print(f"❌ Erreur ESPN: {e}")

# ── CHECK 4 : LOGS RECENT ──────────────────────────────────────
print("\n4️⃣ LOGS RÉCENTS (dernier 1h)")
print("-" * 70)

log_files = [
    "/app/bot_logs.txt",
    "./Ultron_MultiSport/bot_logs.txt",
    "./bot_logs.txt",
]

for log_path in log_files:
    if os.path.exists(log_path):
        print(f"📝 Fichier: {log_path}")
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()
                # Dernières 50 lignes
                relevant = [l for l in lines[-100:] if any(x in l for x in ['pick', 'result', 'error', 'auto_send', 'auto_check', '💾', '🎯', '✅', '❌'])]
                for line in relevant[-20:]:
                    print(f"   {line.strip()}")
        except Exception as e:
            print(f"❌ Erreur lecture: {e}")
        break
else:
    print(f"❌ Aucun fichier log trouvé")

print("\n" + "=" * 70)
print("🔧 RECOMMANDATIONS")
print("=" * 70)

# Analyse finale
print("""
SI PAS DE PICKS ENREGISTRÉS :
  1. DATABASE_URL absent ?
     → Ajoute la var dans Railway: Settings → Variables
     → Referenece du service PostgreSQL

  2. DATABASE_URL présent mais pas de connection ?
     → Vérife PostgreSQL service créé: Railway → + New → Database → PostgreSQL
     → Vérifie pool_connections dans Railway logs

  3. Matchs non trouvés par ESPN ?
     → Lance /pronostics nba|nhl|nfl pour tester
     → Vérife les logs pour "AUCUN match trouvé"

  4. Picks envoyés mais pas enregistrés ?
     → Vérife les logs pour "💾 Pick mémorisé"
     → Si absent = function save_pick() ne s'exécute pas
""")

print("\n📧 Envoie-moi ces logs et le résultat du diagnostic!")
