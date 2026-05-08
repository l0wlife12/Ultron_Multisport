# ✅ CHECKLIST DÉPLOIEMENT RAILWAY - ULTRON

## 🎯 AVANT DE DÉPLOYER

### 1️⃣ Token Telegram Sécurisé
- [ ] Ancien token `8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M` **RÉVOQUÉ** via BotFather
- [ ] Nouveau token généré et testé localement
- [ ] Nouveau token **NON** présent dans le code source (seulement dans Railway env vars)

**Vérifier:**
```bash
# Le token NE doit PAS être dans config.env:
cat Ultron_MultiSport/config.env
# Output: TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE  ✅

# Le token NE doit PAS être dans les fichiers Python:
grep -r "8649771086" .  # Should return nothing ✅
grep -r "AAH1Y6UN" .    # Should return nothing ✅
```

### 2️⃣ Fichiers Correctement Configurés
- [ ] ✅ `Procfile` = `web: python -u main.py` (PAS "worker")
- [ ] ✅ `main.py` version améliorée avec logging (vérifié)
- [ ] ✅ `requirements.txt` contient `python-dotenv` (vérifié)
- [ ] ✅ `railway.json` configuré (vérifié)
- [ ] ✅ `.gitignore` protège `config.env` (vérifié)

**Vérifier:**
```bash
type Procfile
# Output: web: python -u main.py  ✅
```

### 3️⃣ Git & Dépôt
- [ ] Changements commitées localement en Git
- [ ] Aucune erreur Git staging
- [ ] Repository connecté à Railway

**Étapes:**
```bash
git status        # Vérifier qu'il n'y a pas d'erreurs
git add .
git commit -m "fix: Deployment ready - Procfile updated, logging improved"
git push origin main  # Si vous utilisez GitHub
```

---

## 🚀 DÉPLOIEMENT SUR RAILWAY

### Option A: Via Script Automatique (RECOMMANDÉ)
```bash
deploy-railway.bat
# Suit les étapes automatiquement
```

### Option B: Via Railway CLI (Manuel)
```bash
# 1. Vérifier la connexion
railway status

# 2. Configurer le token (SI CE N'EST PAS DÉJÀ FAIT)
railway env set TELEGRAM_TOKEN="PAS_TON_VRAI_TOKEN_ENCORE"
# Remplace "PAS_TON_VRAI_TOKEN_ENCORE" par ton vrai token!

# 3. Vérifier la configuration
railway env list
# Output should show TELEGRAM_TOKEN=...

# 4. Redéployer
railway up

# 5. Voir les logs en direct
railway logs -f
```

### Option C: Via GitHub (Auto Deploy)
```bash
# Juste commiter et pusher
git push origin main
# Railway déploiera automatiquement si configuré
```

---

## ✔️ APRÈS DÉPLOIEMENT - VÉRIFICATIONS

### 1. Vérifier que le bot démarre

```bash
railway logs -f
```

**Output attendu:**
```
2026-05-08 14:30:25 - INFO - ============================================================
2026-05-08 14:30:25 - INFO - 🤖 ULTRON BOT - DÉMARRAGE
2026-05-08 14:30:25 - INFO - ============================================================
2026-05-08 14:30:26 - INFO - 📥 Chargement des modules...
2026-05-08 14:30:27 - INFO - ✅ Modules chargés avec succès
2026-05-08 14:30:27 - INFO - 🚀 Lancement du bot...
```

### 2. Vérifier les variables d'environnement Rails

```bash
railway env list
```

**Output:**
```
TELEGRAM_TOKEN=8649771086:AAH1...  ✅
```

### 3. Tester le Bot Telegram

Envoyer un message au bot sur Telegram et vérifier qu'il répond.

---

## 🆘 TROUBLESHOOTING

### ❌ Erreur: "TELEGRAM_TOKEN not set"

**Solution:**
```bash
railway env set TELEGRAM_TOKEN="YOUR_NEW_TOKEN_HERE"
railway redeploy
railway logs -f
```

### ❌ Erreur: "No module named 'ultron_multisports_v6_0'"

**Cause:** Fichier manquant ou chemin incorrect

**Solution:**
- Vérifier que `Ultron_MultiSport/ultron_multisports_v6_0.py` existe
- Vérifier que le chemin dans `main.py` est correct

```bash
ls Ultron_MultiSport/ultron_multisports_v6_0.py
# Si not found, error!
```

### ❌ Erreur: "ModuleNotFoundError: No module named 'xxxx'"

**Cause:** Dépendance Python manquante

**Solution:** Ajouter à `requirements.txt` et redéployer
```bash
echo nouvelle-dependance >> requirements.txt
git add requirements.txt
git commit -m "build: Add missing dependency"
git push origin main  # ou railway up
```

### ❌ Bot s'arrête après quelques secondes

**Cause:** Erreur dans le code d'initialisation

**Solution:**
```bash
railroad logs -f  # Voir le message d'erreur exact
# Corriger le code
# Redéployer
```

---

## 📊 STATUS CHECK RAPIDE

```bash
# Tout en une commande
echo "=== STATUS RAILWAY ===" && \
railway status && \
echo -e "\n=== ENVIRONMENT VARS ===" && \
railway env list && \
echo -e "\n=== DERNIERS LOGS ===" && \
railway logs --lines 20
```

---

## 🔐 RAPPELS DE SÉCURITÉ

✅ OBLIGATOIRE:
- Token Telegram JAMAIS dans le code source
- Token JAMAIS commité en Git
- `.gitignore` protège tous les `.env`

❌ JAMAIS:
```python
TELEGRAM_TOKEN = "8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M"  # NEVER!
```

✅ CORRECT:
```python
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Load from env vars
```

---

## 📞 QUESTIONS?

Consultez:
1. [DEPLOYMENT_RAILWAY.md](./DEPLOYMENT_RAILWAY.md) - Guide détaillé
2. [SECURITY.md](./SECURITY.md) - Sécurité des secrets
3. `railway logs -f` - Logs en direct
4. `railway env list` - Variables d'environnement

---

**Prêt à déployer? Exécute:**
```bash
deploy-railway.bat
```

**OU manuellement:**
```bash
railway env set TELEGRAM_TOKEN="TON_NEW_TOKEN_ICI"
railway up
railway logs -f
```

**TU ES PRÊT! 🚀**

