#!/usr/bin/env bash
# ============================================================================
# cleanup_ultron.sh
# Archive (ne supprime PAS directement) tous les fichiers inutilisés
# identifiés par analyse de dépendances depuis main.py.
#
# Usage:
#   1. Place ce script à la racine de ton repo Ultron_Multisport
#   2. chmod +x cleanup_ultron.sh
#   3. ./cleanup_ultron.sh
#   4. Vérifie que le bot tourne toujours bien en local (python main.py)
#   5. Si tout va bien après quelques jours: rm -rf _archive_pre_cleanup/
#   6. git add -A && git commit -m "Nettoyage: archivage fichiers inutilisés"
#      git push
# ============================================================================

set -e
ARCHIVE="_archive_pre_cleanup"
mkdir -p "$ARCHIVE/Ultron_MultiSport"

echo "📦 Archivage des anciennes versions du bot..."
cd Ultron_MultiSport 2>/dev/null || { echo "❌ Dossier Ultron_MultiSport introuvable"; exit 1; }

OLD_BOT_VERSIONS=(
  ultron_bot.py ultron_bot_v2.py ultron_bot_clean.py ultron_bot_enhanced.py
  ultron_bot_fixed.py ultron_bot_fixed_backup.py ultron_bot_windows.py
  ultron_final.py ultron_final_v5_5.py ultron_5_5_final.py ultron_live.py
  ultron_multisport_bot.py ultron_math_bot.py ultron_nba.py ultron_picks.py
  ultron_precision_v5_6.py "ultron_precision_v5_6_BACKUP_20260418_154314.py"
  ultron_simple.py ultron_telegram_bot.py ultron_v7_core.py ultron_web.py
  ultron_working.py ultron.py
)

ORPHAN_MODULES=(
  ultron_elite.py ultron_elite_examples.py ultron_elite_integration.py
  ULTRON_ELITE_SNIPPETS.py regression_model.py ultron_props_analyzer.py
  check_matches.py get_matches.py cleanup_now.py cleanup_webhook.py
  reset_webhook.py fix_syntax.py test_apis.py test_fix.py test_pronostics.py
  send_test_picks.py server.py
)

UNRELATED_FILES=(
  "SLot machine.py" project1_PIG.py crypto_exchange.html
)

LOGS_AND_SCRIPTS=(
  bot.log bot_debug.log bot_error.log ultron.log ultron_error.log bot_logs.txt
  start_server.bat start_server.ps1 start_ultron.bat send_test_picks.ps1
)

ALL_FILES=("${OLD_BOT_VERSIONS[@]}" "${ORPHAN_MODULES[@]}" "${UNRELATED_FILES[@]}" "${LOGS_AND_SCRIPTS[@]}")

MOVED=0
SKIPPED=0
for f in "${ALL_FILES[@]}"; do
  if [ -f "$f" ]; then
    mv "$f" "../$ARCHIVE/Ultron_MultiSport/"
    MOVED=$((MOVED+1))
  else
    SKIPPED=$((SKIPPED+1))
  fi
done

cd ..

# Fichier à la racine du repo (script de déploiement Windows)
if [ -f "deploy-railway.bat" ]; then
  mv "deploy-railway.bat" "$ARCHIVE/"
  MOVED=$((MOVED+1))
fi

echo ""
echo "✅ $MOVED fichiers déplacés vers $ARCHIVE/"
echo "ℹ️  $SKIPPED fichiers de la liste n'existaient pas (déjà supprimés ou renommés)"
echo ""
echo "⚠️  IMPORTANT: reste dans le repo, non touchés automatiquement:"
echo "   - ultron_analysis.py (utilisé par la chaîne de dépendances — gardé)"
echo "   - config.env (vérifie qu'il est bien dans .gitignore, ne le commit jamais)"
echo "   - les fichiers .md de documentation historique (à toi de juger, sans risque de casse)"
echo "   - __init__.py (inutilisé mais inoffensif)"
echo ""
echo "👉 Prochaine étape: lance le bot en local pour confirmer que tout fonctionne encore,"
echo "   PUIS seulement commit + push."
