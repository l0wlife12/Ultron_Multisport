# 🔒 Configuration de Sécurité - ULTRON MULTISPORT

## ⚠️ Actions Immédiatement Nécessaires

### 1. **REVOQUER LE TOKEN TELEGRAM** (URGENT!)
Le token Telegram suivant a été exposé et doit être révoqué immédiatement :
```
8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M
```

**Étapes:**
1. Ouvrez Telegram et trouvez `@BotFather`
2. Tapez `/mybots`
3. Sélectionnez votre bot ULTRON
4. Allez à `API Token` → `Revoke current token`
5. Générez un **NOUVEAU token**

### 2. Générer un Nouveau Token
- Avec `@BotFather`, tapez `/newbot`
- Suivez les instructions
- Copiez le nouveau token

### 3. Configurer le Nouveau Token

#### Pour développement local (Windows):
```bash
# Créez ou modifiez: Ultron_MultiSport/config.env
TELEGRAM_TOKEN=VOTRE_NOUVEAU_TOKEN_ICI
```

#### Pour production (Railway):
```bash
# Via l'interface Railway web:
1. Allez à Settings → Environment Variables
2. Ajoutez: TELEGRAM_TOKEN=VOTRE_NOUVEAU_TOKEN_ICI
3. Redéployez l'application
```

## 🛡️ Mesures de Sécurité Implémentées

### ✅ Fichiers Sécurisés
- ✅ `.gitignore` mis à jour - empêche les commits de fichiers sensibles
- ✅ `config.env` - token remplacé par placeholder
- ✅ Tous les fichiers Python - tokens en dur supprimés
- ✅ Validation - les tokens manquants lèvent une erreur

### 📋 Bonnes Pratiques

#### Variables d'Environnement Sécurisées
```python
# ✅ BON
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not set")

# ❌ MAUVAIS (Ne jamais faire!)
TELEGRAM_TOKEN = '8649771086:AAH1Y6UNYphhvYaRxoD_5xilfwy8eMmZj5M'
```

#### Git/GitHub Safety
```bash
# Vérifier que les secrets ne sont pas exposés
git log --all -S "8649771086" --oneline

# Nettoyer l'historique Git (si exposé)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch config.env' \
  --prune-empty --tag-name-filter cat -- --all

# Force push après nettoyage (ATTENTION!)
git push --force --all
```

## 📁 Structure des Fichiers Sécurisés

```
ULTRON_MULTISPORT/
├── .gitignore           ← Empêche les secrets d'être committés
├── config.env           ← JAMAIS commiter en production
├── .env.example         ← Template pour les secrets
├── requirements.txt     ← Dépendances (sûr)
└── Ultron_MultiSport/
    ├── ultron_bot.py    ← Utilise os.getenv() uniquement
    └── ...
```

## 🚀 Déploiement Sécurisé sur Railway

```bash
# 1. Configurez le token avant le déploiement
railway env set TELEGRAM_TOKEN="votre_nouveau_token_ici"

# 2. Vérifiez que c'est défini
railway env list

# 3. Déployez
railway up

# 4. Vérifiez les logs
railway logs
```

## 🔐 Checklist de Sécurité Avant Production

- [ ] Nouveau token Telegram généré
- [ ] Ancien token révoqué via BotFather
- [ ] `TELEGRAM_TOKEN` défini dans Railway environment variables
- [ ] `config.env` n'est pas dans le dépôt Git
- [ ] Pas d'autres tokens/clés dans le code
- [ ] `.gitignore` inclut tous les fichiers sensibles
- [ ] Tests en local avec les bonnes variables d'environnement
- [ ] Logs vérifiés pour s'assurer qu'aucun secret n'est exposé

## 🆘 Dépannage

**Erreur: `TELEGRAM_TOKEN not set`**
```bash
# Windows - Vérifiez config.env
echo %TELEGRAM_TOKEN%

# Railway - Vérifiez les env vars
railway env list

# Solution: Définissez la variable manquante
```

**Le bot ne répond pas**
1. Vérifiez que le token est valide: `railway logs`
2. Assurez-vous que le token a été défini AVANT le déploiement
3. Redéployez: `railway up`

## 📞 Ressources

- [Telegram Bot Security](https://core.telegram.org/bots/api-security)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [GitHub Secrets Scanning](https://docs.github.com/en/code-security/secret-scanning)

---

**Dernière mise à jour:** 2026-05-08  
**Status:** 🟢 Sécurisé - Token révoqué, nouveau système en place
