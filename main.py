#!/usr/bin/env python3
"""
ULTRON Multisports Bot Entry Point
Main launcher for Railway + Local development
"""
import sys
import os
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
# ============================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('telegram_token')
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN not configured")
    logger.info("ℹ️  Set TELEGRAM_TOKEN in Railway dashboard or local .env file")
    sys.exit(1)

logger.info("✅ Environment validation passed - TELEGRAM_TOKEN found")

# ============================================================
# BOT PATH VALIDATION
# ============================================================
bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Ultron_MultiSport')

if not os.path.exists(bot_path):
    logger.critical(f"❌ Bot folder not found: {bot_path}")
    logger.critical("   Expected: Ultron_MultiSport/ directory in same folder as main.py")
    sys.exit(1)

logger.info(f"✅ Bot path validated: {bot_path}")
sys.path.insert(0, bot_path)

# ============================================================
# START BOT with comprehensive error handling
# ============================================================
def main():
    try:
        logger.info("🚀 Starting ULTRON Multisports Bot v6.0...")
        from ultron_multisports_v6_0 import main as bot_main
        
        # Run the bot (blocking, runs until interrupted or error)
        bot_main()
        
    except KeyboardInterrupt:
        logger.info("⏹️  Bot interrupted by user (Ctrl+C)")
        sys.exit(0)
    
    except ImportError as e:
        logger.critical(f"💀 Import Error: Cannot load ultron_multisports_v6_0")
        logger.critical(f"   Details: {e}")
        logger.critical("   Check that Ultron_MultiSport/ultron_multisports_v6_0.py exists")
        sys.exit(1)
    
    except Exception as e:
        logger.critical(f"💀 FATAL BOT CRASH")
        logger.critical(f"   Error: {e}", exc_info=True)
        logger.critical("   Railway will auto-restart container...")
        import time
        time.sleep(5)
        sys.exit(1)

# ============================================================
# EXECUTION
# ============================================================
if __name__ == '__main__':
    main()

