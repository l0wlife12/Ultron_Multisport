#!/usr/bin/env python3
"""
ULTRON Multisports Bot Entry Point
Flask app for Railway + Telegram Bot
Uses Gunicorn in production (see Procfile/railway.toml)
"""
import sys
import os
import threading
import logging

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# SECURITY: Validate required environment variables
# NOTE: Don't log ALL environment variables (security risk!)
# ============================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('telegram_token')
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN not configured in Railway environment")
    logger.error("ℹ️  Please set TELEGRAM_TOKEN in Railway dashboard")
    sys.exit(1)

logger.info("✅ Environment validation passed")

# ============================================================
# FLASK APP for Railway healthchecks + Gunicorn
# ============================================================
from flask import Flask

health_app = Flask(__name__)

@health_app.route('/')
def health():
    """Health check endpoint"""
    return '🤖 ULTRON Multisports Bot active', 200

@health_app.route('/health')
def healthcheck():
    """Structured health check for Railway"""
    return {'status': 'ok', 'bot': 'ULTRON v6.0', 'version': '6.0'}, 200

# ============================================================
# BOT PATH VALIDATION (Fix #5: Fragile imports)
# ============================================================
bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Ultron_MultiSport')

if not os.path.exists(bot_path):
    logger.critical(f"❌ Bot folder not found: {bot_path}")
    logger.critical("   Expected: Ultron_MultiSport/ directory in same folder as main.py")
    sys.exit(1)

logger.info(f"✅ Bot path validated: {bot_path}")
sys.path.insert(0, bot_path)

# ============================================================
# BOT STARTUP with crash handling (Fix #3: No crash handling)
# ============================================================
def start_bot():
    """
    Start the Telegram bot with proper error handling
    Runs in a daemon thread when using Gunicorn
    Runs in main thread when called directly
    """
    try:
        logger.info("🚀 Starting ULTRON Multisports Bot v6.0...")
        from ultron_multisports_v6_0 import main
        
        # ── Bot runs here (blocking) ──
        main()
        
    except KeyboardInterrupt:
        logger.info("⏹️  Bot interrupted by user")
        sys.exit(0)
    
    except ImportError as e:
        logger.critical(f"💀 Import error - ultron_multisports_v6_0 not found: {e}")
        logger.critical("   Check that Ultron_MultiSport/ultron_multisports_v6_0.py exists")
        sys.exit(1)
    
    except Exception as e:
        logger.critical(f"💀 Fatal bot crash: {e}", exc_info=True)
        logger.critical("   Railway will auto-restart container...")
        import time
        time.sleep(10)
        sys.exit(1)

# ============================================================
# START BOT IN DAEMON THREAD
# This is executed when:
# - main.py is run directly
# - main.py is imported by Gunicorn (for production deployment)
# ============================================================
logger.info("🌐 ULTRON Multisports Bot initialized")
logger.info("   Flask app: Ready for Gunicorn")
logger.info("   Telegram bot: Starting in daemon thread...")

bot_thread = threading.Thread(target=start_bot, daemon=True, name="TelegramBot")
bot_thread.start()

# ============================================================
# EXECUTION (for direct invocation, e.g., development)
# ============================================================
if __name__ == '__main__':
    # When run directly: $ python main.py
    # Keep the main thread alive to let daemon bot run
    logger.info("🔄 Main thread waiting for bot...")
    
    try:
        bot_thread.join()  # Wait for bot thread
    except KeyboardInterrupt:
        logger.info("⏹️  Shutdown requested")
        sys.exit(0)
