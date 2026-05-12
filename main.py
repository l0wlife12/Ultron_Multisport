#!/usr/bin/env python3
import sys
import os
import threading
import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Debug: afficher toutes les variables disponibles (noms seulement, pas les valeurs)
railway_vars = [k for k in os.environ.keys()]
logger.info(f"🔍 Variables disponibles: {sorted(railway_vars)}")

# Valider le token AVANT tout import
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('telegram_token')
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN n'est pas configuré dans les variables d'environnement Railway")
    logger.error(f"Variables présentes: {[k for k in os.environ.keys() if 'TELEGRAM' in k.upper() or 'TOKEN' in k.upper()]}")
    sys.exit(1)

logger.info("✅ TELEGRAM_TOKEN trouvé")

# Serveur HTTP minimal pour Railway (le type 'web' exige un port HTTP ouvert)
from flask import Flask
health_app = Flask(__name__)

@health_app.route('/')
def health():
    return '🤖 ULTRON Multisports Bot actif', 200

@health_app.route('/health')
def healthcheck():
    return {'status': 'ok', 'bot': 'ULTRON v6.0'}, 200

def start_health_server():
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🌐 Serveur santé démarré sur le port {port}")
    health_app.run(host='0.0.0.0', port=port, use_reloader=False)

# Lancer le serveur Flask dans un thread séparé (non-bloquant)
health_thread = threading.Thread(target=start_health_server, daemon=True)
health_thread.start()

# Ajouter le dossier du bot au chemin Python
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Ultron_MultiSport'))

# Lancer le bot Telegram (bloquant - tourne en continu)
logger.info("🚀 Démarrage du bot ULTRON Multisports...")
from ultron_multisports_v6_0 import main
main()
