#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Main Entry Point
Lance le bot Telegram ULTRON avec tous les modules intégrés
"""

import sys
import os
import time

# Ensure UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

if __name__ == '__main__':
    # Import after encoding setup
    print("Initialisation ULTRON...\n")
    
    try:
        from ultron_multisports_v6_0 import run_ultron_pipeline, send_telegram, FREE_CHAT_ID, PREMIUM_CHAT_ID, get_pipeline_results
        from ultron_analysis import has_good_picks, is_game_soon, get_pick_type, should_send, get_best_pick, get_premium_picks, is_1h_before, is_vip_pick, analyze, get_safe_picks, format_free_pick, format_premium, already_sent
        print("✅ Modules chargés avec succès\n")
    except Exception as e:
        print(f"❌ ERREUR lors du chargement des modules: {e}\n")
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    import datetime
    from pytz import timezone
    
    QUEBEC_TZ = timezone('America/Toronto')
    
    # Variables pour éviter les doublons
    last_sent_free = None      # Pick FREE envoyé
    last_sent_premium = None   # Message PREMIUM envoyé
    
    def is_free_already_sent(best):
        """Vérifie si ce pick FREE a déjà été envoyé"""
        global last_sent_free
        
        pick_key = already_sent(best)
        if pick_key == last_sent_free:
            return True
        
        last_sent_free = pick_key
        return False
    
    def is_premium_already_sent(premium_msg):
        """Vérifie si ce message PREMIUM a déjà été envoyé"""
        global last_sent_premium
        
        if premium_msg == last_sent_premium:
            return True
        
        last_sent_premium = premium_msg
        return False
    
    # Variable pour le message de motivation quotidien
    last_motivation_day = None
    
    def send_daily_motivation():
        """Envoie un message de motivation à 9:00 AM chaque jour"""
        global last_motivation_day
        
        now = datetime.datetime.now(QUEBEC_TZ)
        current_day = now.date()
        current_hour = now.hour
        current_minute = now.minute
        
        # Vérifie si c'est 9:00 AM et qu'on n'a pas encore envoyé le message aujourd'hui
        if current_hour == 9 and current_minute < 5 and last_motivation_day != current_day:
            motivations = [
                "💪 Bonne journée! Restez discipliné, les profits suivent les bonnes décisions!",
                "🎯 C'est une nouvelle journée pour de nouvelles opportunités. Analysez, décidez, gagnez!",
                "🚀 9:00 AM à Montréal! Commencez fort, finissez plus fort. Bon trading!",
                "📈 Les meilleurs paris sont ceux qui tournent en votre faveur. Soyez patient, soyez smart!",
                "⚡ Nouvelle journée, nouvelles chances. ULTRON vous a préparé les meilleures picks!",
                "🏆 Champion, c'est l'heure de montrer votre potentiel. Bonne chance aujourd'hui!",
                "💎 La constance gagne toujours. Restez focus sur la stratégie. You got this!",
                "🎲 Bon matin! Les picks sont prêts, à vous de jouer intelligemment. BON TRADING!"
            ]
            
            # Sélectionner un message aléatoire
            import random
            motivation_msg = random.choice(motivations)
            
            # Envoyer à TOUS les utilisateurs (BOTH channels)
            try:
                # Envoyer au canal FREE
                if send_telegram(motivation_msg, False):
                    print("✅ Message de motivation envoyé au canal FREE")
                
                # Envoyer au canal PREMIUM
                if send_telegram(motivation_msg, True):
                    print("✅ Message de motivation envoyé au canal PREMIUM")
                
                # Mettre à jour le dernier jour
                last_motivation_day = current_day
                
                return True
            except Exception as e:
                print(f"⚠️  Erreur lors de l'envoi du message de motivation: {e}")
                return False
        
        return False
    
    print("="*60)
    print("🤖 ULTRON BOT - PIPELINE MULTI-CHANNEL")
    print("="*60)
    print(f"⏰ Timezone: America/Toronto")
    print(f"🔥 FREE Channel: {FREE_CHAT_ID}")
    print(f"💎 PREMIUM Channel: {PREMIUM_CHAT_ID}")
    print(f"💪 Motivation Message: 9:00 AM (Montréal) - CHAQUE JOUR")
    print("="*60 + "\n")
    
    def run_once():
        """Pipeline complet: FREE pick + PREMIUM picks"""
        try:
            now = datetime.datetime.now(QUEBEC_TZ).strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n{'='*60}")
            print(f"🚀 EXÉCUTION PIPELINE | {now}")
            print(f"{'='*60}")
            
            # 1️⃣  Récupère les results analysés
            print("📊 Génération et analyse des picks...")
            results = get_pipeline_results(bankroll=1000)
            
            if not results:
                print("❌ Aucun pick disponible cette heure")
                return
            
            print(f"✅ {len(results)} picks générés")
            
            # 2️⃣  Filtre qualité
            print("🔍 Filtrage qualité...")
            if not should_send(results):
                print("⛔ Qualité insuffisante (pas de SAFE ou VALUE EV>=12%)")
                return
            
            print(f"✅ Picks de qualité détectés")
            
            # 3️⃣  🔥 FREE PICK
            print("\n🔥 FREE PICK CHANNEL")
            best = get_best_pick(results)
            
            if best and not is_free_already_sent(best):
                free_msg = format_free_pick(best)
                if send_telegram(free_msg, False):  # False = main channel
                    print(f"✅ FREE PICK envoyé: {best.team} {best.bet}")
                else:
                    print(f"⚠️  Erreur envoi FREE PICK")
            else:
                if not best:
                    print("⛔ Pas de pick de qualité")
                else:
                    print("⛔ Même pick (déjà envoyé)")
            
            # 4️⃣  💎 PREMIUM PICKS
            print("\n💎 PREMIUM PICKS CHANNEL")
            premium = get_safe_picks(results)  # Tous les SAFE picks
            
            if premium:
                premium_msg = format_premium(premium)
                if not is_premium_already_sent(premium_msg):
                    if send_telegram(premium_msg, True):  # True = VIP channel
                        print(f"✅ PREMIUM PICKS envoyés: {len(premium)} picks SAFE")
                    else:
                        print(f"⚠️  Erreur envoi PREMIUM PICKS")
                else:
                    print("⛔ Même PREMIUM PICKS (pas de changement)")
            else:
                print("⛔ Aucun pick SAFE pour PREMIUM")
                
        except Exception as e:
            print(f"❌ ERREUR: {e}\n")
            import traceback
            traceback.print_exc()
    
    # Boucle infinie: envoie les picks toutes les heures + motivation à 9:00 AM
    try:
        while True:
            now = datetime.datetime.now(QUEBEC_TZ)
            
            # Vérifier et envoyer le message de motivation à 9:00 AM
            if now.hour == 9 and now.minute < 5:
                print(f"\n{'='*60}")
                print(f"💪 CHECK MOTIVATION | {now.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                send_daily_motivation()
            
            # Exécuter le pipeline des picks
            run_once()
            
            now = datetime.datetime.now(QUEBEC_TZ).strftime("%H:%M:%S")
            print(f"\n⏳ Prochain check dans 1 minute ({now})")
            print("-"*60)
            
            # Vérifier chaque minute au lieu de chaque heure pour ne pas rater le message de motivation
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n\n⛔ Bot arrêté par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR CRITIQUE: {e}\n")
        import traceback
        traceback.print_exc()
        input("Appuyez sur Entrée pour quitter...")
