# 🚀 Deployment Guide - ULTRON to Railway

## ✅ Pre-Deployment Checklist

Before deploying to Railway, ensure:

- [ ] New Telegram token generated (old one revoked)
- [ ] `TELEGRAM_TOKEN` configured in Railway environment variables
- [ ] `.gitignore` prevents sensitive files from being committed
- [ ] `Procfile` set to `web` (not `worker`)
- [ ] `requirements.txt` has all dependencies
- [ ] No Python syntax errors in main files
- [ ] Committed changes to Git

## 🔧 Configuration Steps

### Step 1: Set Up Environment Variables in Railway

```bash
# Via Railway CLI
railway env set TELEGRAM_TOKEN="your_new_token_here"
railway env set PORT="8000"

# OR via Railway Web Dashboard:
# 1. Go to Your Project → Settings → Environment Variables
# 2. Add TELEGRAM_TOKEN=your_new_token_here
# 3. Click Deploy
```

### Step 2: Verify Procfile

Your `Procfile` should contain:
```
web: python -u main.py
```

NOT:
```
worker: python -u main.py    ❌ WRONG - doesn't exist on Railway
```

### Step 3: Update requirements.txt

Ensure all dependencies are listed (no versions needed for Railway):
```
requests
python-dotenv
python-telegram-bot
beautifulsoup4
pytz
numpy
apscheduler
nba-api
sportsreference
scikit-learn
pandas
xgboost
hockey-scraper
flask
Pillow
pytesseract
```

### Step 4: Deploy

```bash
# From your project directory
cd c:\Users\jeffc\OneDrive\PythonProjects\GitHub\ULTRON_MULTISPORT

# Option A: Using Railway CLI
railway up

# Option B: Via Git push
git add .
git commit -m "deploy: Ready for Railway"
git push origin main

# Option C: Via Railway Web Dashboard
# 1. Connect your GitHub repository
# 2. Select branch to deploy
# 3. Railway auto-deploys on push
```

## 🔍 Troubleshooting

### Problem: "No module named 'ultron_multisports_v6_0'"

**Solution:** Ensure the file exists and is in `Ultron_MultiSport/` folder

### Problem: "TELEGRAM_TOKEN not set"

**Solution:** 
```bash
railway env set TELEGRAM_TOKEN="your_token_here"
railway redeploy
```

### Problem: "ModuleNotFoundError: No module named 'dotenv'"

**Solution:** Add missing package to `requirements.txt`:
```
python-dotenv
```

### Check Logs

```bash
# View Railway logs in real-time
railway logs -f

# View last 100 lines
railway logs --lines 100
```

## 📊 Deployment Status Monitoring

```bash
# Check if bot is running
railway logs

# Expected output on startup:
# 2026-05-08 14:30:25 - INFO - ============================================================
# 2026-05-08 14:30:25 - INFO - 🤖 ULTRON BOT - DÉMARRAGE
# 2026-05-08 14:30:25 - INFO - ============================================================
# 2026-05-08 14:30:26 - INFO - 📥 Chargement des modules...
# 2026-05-08 14:30:27 - INFO - ✅ Modules chargés avec succès
```

## 🎯 Quick Redeploy

If you need to redeploy after changes:

```bash
# Commit your changes
git add .
git commit -m "fix: description of changes"
git push origin main

# Railway will auto-deploy if connected to GitHub
# OR manually:
railway redeploy
```

## 🔐 Security Reminders

- ✅ Never commit `config.env` with real tokens
- ✅ Always use environment variables
- ✅ Rotate tokens if they're ever exposed
- ✅ Use `.gitignore` to protect secrets

## 📞 Support

If deployment still fails:
1. Check `railway logs -f` for error messages
2. Verify `TELEGRAM_TOKEN` is set: `railway env list`
3. Ensure `Procfile` says `web:` (not `worker:`)
4. Confirm `python-dotenv` is in `requirements.txt`

---

**Last Updated:** 2026-05-08  
**Status:** Ready for production deployment
