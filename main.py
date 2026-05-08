#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Entry Point Simplifié
Lancement du bot sur Railway
"""

import sys
import os
import time

# Ensure UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Ultron_MultiSport'))

print("="*60)
print("🤖 ULTRON BOT - DÉMARRAGE")
print("="*60 + "\n")

try:
    print("📥 Chargement des modules...")
    from ultron_multisports_v6_0 import run_ultron_pipeline
    print("✅ Modules chargés avec succès\n")
    print("🚀 Lancement du bot...\n")
    
    # Boucle simple: lance le pipeline toutes les minutes
    while True:
        try:
            run_ultron_pipeline(bankroll=1000)
            time.sleep(60)  # Attendre 60 secondes avant le prochain check
        except KeyboardInterrupt:
            print("\n⛔ Bot arrêté")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️  Erreur dans le pipeline: {e}")
            time.sleep(30)
    
except Exception as e:
    print(f"❌ ERREUR au démarrage: {e}")
    import traceback
    traceback.print_exc()
    time.sleep(30)
    sys.exit(1)
