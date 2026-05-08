#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Entry Point Principal
Lancement du bot sur Railway avec gestion robuste des imports
"""

import sys
import os
import time
import logging

# ============================================================================
# SETUP INITIAL
# ============================================================================

# Ensure UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging AVANT tout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ultron_startup.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*70)
logger.info("🤖 ULTRON BOT - DÉMARRAGE")
logger.info("="*70)

# ============================================================================
# CHEMIN D'ACCÈS AUX MODULES
# ============================================================================

# Déterminer le répertoire de base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ULTRON_DIR = os.path.join(BASE_DIR, 'Ultron_MultiSport')

logger.info(f"📂 Répertoire de base: {BASE_DIR}")
logger.info(f"📂 Répertoire Ultron: {ULTRON_DIR}")

# Vérifier que le répertoire existe
if not os.path.exists(ULTRON_DIR):
    logger.error(f"❌ RÉPERTOIRE MANQUANT: {ULTRON_DIR}")
    logger.error("Le dossier Ultron_MultiSport n'existe pas!")
    sys.exit(1)

# Ajouter au chemin Python si pas déjà présent
if ULTRON_DIR not in sys.path:
    sys.path.insert(0, ULTRON_DIR)
    logger.info(f"✅ Chemin Python ajouté: {ULTRON_DIR}")

# Vérifier que le module existe
MODULE_PATH = os.path.join(ULTRON_DIR, 'ultron_multisports_v6_0.py')
if not os.path.exists(MODULE_PATH):
    logger.error(f"❌ MODULE MANQUANT: {MODULE_PATH}")
    logger.error("Le fichier ultron_multisports_v6_0.py n'existe pas!")
    sys.exit(1)

logger.info(f"✅ Module trouvé: {MODULE_PATH}")

# ============================================================================
# CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
# ============================================================================

from dotenv import load_dotenv

# Charger config.env du répertoire Ultron_MultiSport
config_env_path = os.path.join(ULTRON_DIR, 'config.env')
logger.info(f"📋 Chargement de config.env: {config_env_path}")
load_dotenv(config_env_path)

# Charger .env à la racine si possible
root_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(root_env_path):
    logger.info(f"📋 Chargement de .env: {root_env_path}")
    load_dotenv(root_env_path)

# ============================================================================
# VALIDATION DES CREDENTIALS
# ============================================================================

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

logger.info(f"🔐 Vérification des credentials...")
if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
    logger.error("❌ TELEGRAM_TOKEN non configuré!")
    logger.error("Action requise:")
    logger.error("  1. Sur Railway: Settings → Environment Variables")
    logger.error("  2. Ajoutez: TELEGRAM_TOKEN=votre_token_ici")
    logger.error("  3. Redéployez l'application")
    sys.exit(1)

logger.info("✅ TELEGRAM_TOKEN trouvé et configuré")

# ============================================================================
# CHARGEMENT DU MODULE PRINCIPAL
# ============================================================================

try:
    logger.info("📥 Chargement du module ultron_multisports_v6_0...")
    
    # TRY 1: Import direct (après sys.path.insert)
    try:
        from ultron_multisports_v6_0 import run_ultron_pipeline
        logger.info("✅ Import direct réussi")
    except ImportError as e:
        logger.warning(f"⚠️ Import direct échoué: {e}")
        
        # TRY 2: Import avec chemin complet
        logger.info("Tentative d'import avec chemin complet...")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ultron_multisports_v6_0", 
            MODULE_PATH
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules['ultron_multisports_v6_0'] = module
        spec.loader.exec_module(module)
        run_ultron_pipeline = module.run_ultron_pipeline
        logger.info("✅ Import avec chemin complet réussi")
    
    logger.info("✅ Module chargé avec succès")
    
except Exception as e:
    logger.error(f"❌ ERREUR D'IMPORT: {e}", exc_info=True)
    logger.error("Dépannage:")
    logger.error(f"  - Vérifier que {MODULE_PATH} existe")
    logger.error(f"  - Vérifier la syntaxe Python du module")
    logger.error(f"  - Vérifier les dépendances (requirements.txt)")
    time.sleep(5)
    sys.exit(1)

# ============================================================================
# BOUCLE PRINCIPALE
# ============================================================================

logger.info("🚀 Lancement du bot...")
logger.info("="*70)

iteration = 0
consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 10

while True:
    try:
        iteration += 1
        logger.info(f"[Itération {iteration}] Exécution du pipeline...")
        
        # Exécuter le pipeline
        run_ultron_pipeline(bankroll=1000)
        
        logger.info(f"[Itération {iteration}] Pipeline complété avec succès")
        consecutive_errors = 0  # Reset error counter on success
        
        # Attendre avant la prochaine itération
        logger.info("⏳ Attente 60 secondes avant la prochaine itération...")
        time.sleep(60)
        
    except KeyboardInterrupt:
        logger.info("⛔ Bot arrêté par l'utilisateur (Ctrl+C)")
        sys.exit(0)
        
    except Exception as e:
        consecutive_errors += 1
        logger.error(f"⚠️ Erreur dans le pipeline (#{consecutive_errors}): {e}", exc_info=True)
        
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.error(f"❌ Trop d'erreurs consécutives ({MAX_CONSECUTIVE_ERRORS}). Arrêt du bot.")
            sys.exit(1)
        
        logger.info(f"🔄 Nouvelle tentative dans 30 secondes ({MAX_CONSECUTIVE_ERRORS - consecutive_errors} tentatives restantes)...")
        time.sleep(30)
