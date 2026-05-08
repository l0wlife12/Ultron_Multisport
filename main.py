#!/usr/bin/env python3
import sys
import os

# Force charger SEULEMENT les env vars de Railway - PAS config.env
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN not set in Railway environment variables")
    sys.exit(1)

print(f"✅ Token loaded from environment: {'*' * 20}...{TELEGRAM_TOKEN[-10:]}")

# Maintenant ajouter le chemin et importer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Ultron_MultiSport'))

# IMPORTANT: Remplacer le token dans l'environnement AVANT d'importer
os.environ['TELEGRAM_TOKEN'] = TELEGRAM_TOKEN

# Importer et lancer
from ultron_multisports_v6_0 import main
main()
