#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON Pick Memory — pick_memory.py

Mémoire persistante des picks envoyés.
Ultron se note lui-même à chaque jour :
  • Sauvegarde chaque pick au moment de l'envoi
  • Vérifie les résultats via ESPN après la fin des matchs
  • Calcule win rate, ROI et série en cours
  • Génère un rapport de performance journalier/hebdomadaire

Storage: picks_history.json (local)

⚠️  Sur Railway, le filesystem est éphémère entre les déploiements.
    Pour persister : ajouter un Volume Railway (Settings → Volumes)
    Mount Path : /data
    Puis changer : HISTORY_FILE = "/data/picks_history.json"
"""

import io
import os
import json
import uuid
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Chemins des fichiers ─────────────────────────────────────────────────────
# Utilise /data si un Volume Railway est monté, sinon dossier courant
_BASE = "/data" if os.path.isdir("/data") else "."
HISTORY_FILE = os.path.join(_BASE, "picks_history.json")
BACKUP_META_FILE = os.path.join(_BASE, "backup_meta.json")

# ── PostgreSQL (Railway DATABASE_URL) ────────────────────────────────────────
_DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _db_connect():
    """Ouvre une connexion psycopg2 si DATABASE_URL est défini."""
    if not _DATABASE_URL:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(_DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        logger.error(f"❌ pick_memory DB connexion: {e}")
        return None


def _db_init():
    """Crée la table pick_store si elle n'existe pas encore."""
    conn = _db_connect()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pick_store (
                        id   INTEGER PRIMARY KEY DEFAULT 1,
                        data JSONB NOT NULL
                    )
                """)
        logger.info("✅ pick_memory: table pick_store prête (PostgreSQL)")
    except Exception as e:
        logger.error(f"❌ pick_memory DB init: {e}")
    finally:
        conn.close()


_db_init()

SPORT_PATHS = {
    "NBA": "basketball/nba",
    "NHL": "icehockey/nhl",
    "NFL": "americanfootball/nfl",
}


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE / ÉCRITURE
# ─────────────────────────────────────────────────────────────────────────────

def _empty_stats() -> dict:
    return {
        "total_sent":   0,
        "wins":         0,
        "losses":       0,
        "pending":      0,
        "win_rate":     0.0,
        "last_updated": None,
    }


def load_history() -> dict:
    # Essai PostgreSQL en priorité
    conn = _db_connect()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM pick_store WHERE id = 1")
                    row = cur.fetchone()
                    if row:
                        return row[0]  # psycopg2 désérialise JSONB automatiquement
        except Exception as e:
            logger.error(f"❌ pick_memory DB load: {e}")
        finally:
            conn.close()
    # Fallback fichier JSON local
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"❌ pick_memory: erreur lecture {HISTORY_FILE}: {e}")
    return {"picks": [], "stats": _empty_stats()}


def _save_history(history: dict):
    # Sauvegarder dans PostgreSQL si disponible
    conn = _db_connect()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pick_store (id, data) VALUES (1, %s)
                        ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
                        """,
                        (json.dumps(history, ensure_ascii=False),),
                    )
            return  # succès DB, pas besoin d'écrire le fichier
        except Exception as e:
            logger.error(f"❌ pick_memory DB save: {e}")
        finally:
            conn.close()
    # Fallback fichier JSON local
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error(f"❌ pick_memory: erreur écriture {HISTORY_FILE}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ENREGISTREMENT D'UN PICK
# ─────────────────────────────────────────────────────────────────────────────

def save_pick(
    sport: str,
    away_team: str,
    home_team: str,
    pick_type: str,        # "ML" | "SPREAD" | "OU"
    pick_team: str,        # équipe ou direction choisie (ex: "Boston Celtics")
    odds: str,
    confidence: int,
    ev_pct: str = "",
    game_date: str = "",   # "YYYY-MM-DD", déduit de today si vide
    pick_line: float = None,  # ex: -3.5 pour SPREAD, 225.5 pour OU
) -> str:
    """
    Enregistre un pick envoyé et retourne son ID unique.
    Appelé immédiatement après l'envoi Telegram.
    """
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")

    history  = load_history()
    pick_id  = str(uuid.uuid4())[:8]

    history["picks"].append({
        "id":          pick_id,
        "date":        game_date,
        "sent_at":     datetime.now().isoformat(),
        "sport":       sport.upper(),
        "away_team":   away_team,
        "home_team":   home_team,
        "pick_type":   pick_type.upper(),
        "pick_team":   pick_team,
        "pick_line":   pick_line,
        "odds":        str(odds),
        "confidence":  confidence,
        "ev_pct":      ev_pct,
        "result":      None,   # "WIN" | "LOSS" | "PUSH" | None (en attente)
        "score":       None,   # ex: "Boston 112 - 98 Miami"
        "checked_at":  None,
    })

    _recalculate_stats(history)
    _save_history(history)
    logger.info(f"💾 Pick mémorisé [{pick_id}]: {pick_type} {pick_team} @ {odds} ({sport})")
    return pick_id


# ─────────────────────────────────────────────────────────────────────────────
# VÉRIFICATION DES RÉSULTATS ESPN
# ─────────────────────────────────────────────────────────────────────────────

def _fuzzy_match_teams(pick_away: str, pick_home: str,
                        espn_away: str, espn_home: str) -> bool:
    """Retourne True si les deux équipes correspondent (fuzzy match)."""
    def parts(name): return [w for w in name.lower().split() if len(w) > 3]

    away_ok = any(p in espn_away.lower() for p in parts(pick_away))
    home_ok = any(p in espn_home.lower() for p in parts(pick_home))
    return away_ok and home_ok


def _check_ml_result(pick: dict, home_name: str, home_won: bool) -> bool:
    pick_team_l = pick["pick_team"].lower()
    home_parts  = [w for w in home_name.lower().split() if len(w) > 3]
    is_home     = any(p in pick_team_l for p in home_parts)
    return is_home == home_won


def _check_spread_result(pick: dict, home_score: int, away_score: int,
                          home_name: str) -> bool:
    line        = pick.get("pick_line") or 0
    pick_team_l = pick["pick_team"].lower()
    home_parts  = [w for w in home_name.lower().split() if len(w) > 3]
    is_home     = any(p in pick_team_l for p in home_parts)
    if is_home:
        return (home_score + line) > away_score
    return (away_score + abs(line)) > home_score


def _check_ou_result(pick: dict, home_score: int, away_score: int) -> bool:
    total = home_score + away_score
    line  = pick.get("pick_line") or 0
    return total > line if "OVER" in pick["pick_team"].upper() else total < line


def check_and_update_results() -> list:
    """
    Parcourt les picks en attente, interroge ESPN et met à jour les résultats.
    Retourne la liste des picks dont le résultat vient d'être déterminé.
    """
    history = load_history()
    pending = [p for p in history["picks"] if p["result"] is None]
    if not pending:
        return []

    # Regroupe par (sport, date) pour minimiser les appels ESPN
    by_sport_date: dict = {}
    for pick in pending:
        key = (pick["sport"], pick["date"])
        by_sport_date.setdefault(key, []).append(pick)

    updated = []

    for (sport, date_str), picks_group in by_sport_date.items():
        path = SPORT_PATHS.get(sport)
        if not path:
            continue

        date_key = date_str.replace("-", "")
        try:
            url  = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={date_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception as e:
            logger.warning(f"⚠️ pick_memory ESPN {sport} {date_str}: {e}")
            continue

        for event in data.get("events", []):
            status = event.get("status", {}).get("type", {}).get("name", "")
            if status not in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                continue  # match pas encore terminé

            comp        = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home_c = next((c for c in competitors if c["homeAway"] == "home"), None)
            away_c = next((c for c in competitors if c["homeAway"] == "away"), None)
            if not home_c or not away_c:
                continue

            home_name  = home_c["team"]["displayName"]
            away_name  = away_c["team"]["displayName"]
            home_score = int(float(home_c.get("score", 0)))
            away_score = int(float(away_c.get("score", 0)))
            home_won   = home_score > away_score
            score_str  = f"{away_name} {away_score}  –  {home_score} {home_name}"

            for pick in picks_group:
                if pick["result"] is not None:
                    continue  # déjà gradé

                if not _fuzzy_match_teams(pick["away_team"], pick["home_team"],
                                          away_name, home_name):
                    continue

                pt = pick["pick_type"]
                if pt == "ML":
                    won = _check_ml_result(pick, home_name, home_won)
                elif pt == "SPREAD":
                    won = _check_spread_result(pick, home_score, away_score, home_name)
                elif pt == "OU":
                    won = _check_ou_result(pick, home_score, away_score)
                else:
                    continue

                pick["result"]     = "WIN" if won else "LOSS"
                pick["score"]      = score_str
                pick["checked_at"] = datetime.now().isoformat()
                updated.append(dict(pick))
                logger.info(
                    f"{'✅' if won else '❌'} Résultat [{pick['id']}] "
                    f"{pick['sport']} {pick['pick_team']}: {pick['result']} | {score_str}"
                )

    if updated:
        _recalculate_stats(history)
        _save_history(history)

    return updated


# ─────────────────────────────────────────────────────────────────────────────
# STATISTIQUES
# ─────────────────────────────────────────────────────────────────────────────

def _recalculate_stats(history: dict):
    picks      = history["picks"]
    wins       = sum(1 for p in picks if p["result"] == "WIN")
    losses     = sum(1 for p in picks if p["result"] == "LOSS")
    pending    = sum(1 for p in picks if p["result"] is None)
    total_grad = wins + losses

    history["stats"] = {
        "total_sent":   len(picks),
        "wins":         wins,
        "losses":       losses,
        "pending":      pending,
        "win_rate":     round(wins / total_grad, 4) if total_grad > 0 else 0.0,
        "last_updated": datetime.now().isoformat(),
    }


def get_stats() -> dict:
    return load_history()["stats"]


def _current_streak(picks: list) -> str:
    """Retourne la série actuelle ex: 'W5' ou 'L2'"""
    graded = [p for p in picks if p["result"] in ("WIN", "LOSS")]
    if not graded:
        return "—"
    last   = graded[-1]["result"]
    count  = 0
    for p in reversed(graded):
        if p["result"] == last:
            count += 1
        else:
            break
    return f"{'W' if last == 'WIN' else 'L'}{count}"


# ─────────────────────────────────────────────────────────────────────────────
# FORMATAGE DES RAPPORTS TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def format_today_recap() -> str:
    """
    Résumé de fin de journée : tous les picks envoyés aujourd'hui
    avec leur résultat (WIN / LOSS / en attente).
    Envoyé automatiquement à 23h00 heure Québec.
    Retourne toujours un message — même s'il n'y a pas eu de picks.
    """
    history  = load_history()
    picks    = history["picks"]
    today    = datetime.now().strftime("%Y-%m-%d")
    today_ps = [p for p in picks if p.get("date") == today]
    stats    = history["stats"]
    s_wins   = stats.get("wins", 0)
    s_loss   = stats.get("losses", 0)
    s_tot    = s_wins + s_loss
    s_wr     = s_wins / s_tot if s_tot > 0 else 0.0
    streak   = _current_streak(picks)

    date_fr  = datetime.now().strftime("%A %d %B %Y").upper()

    if not today_ps:
        msg  = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📋  U L T R O N  —  R É C A P  D U  J O U R\n"
        msg += f"     {date_fr}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "📭  Aucun pick envoyé aujourd'hui.\n"
        msg += "     (Aucun match dans la fenêtre 1h avant début)\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📈  Saison   :  {s_wins}W–{s_loss}L"
        if s_tot > 0:
            msg += f"  ({s_wr:.1%} WR)"
        msg += f"  •  Série {streak}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return msg

    wins    = sum(1 for p in today_ps if p["result"] == "WIN")
    losses  = sum(1 for p in today_ps if p["result"] == "LOSS")
    pending = sum(1 for p in today_ps if p["result"] is None)
    total_g = wins + losses
    wr      = wins / total_g if total_g > 0 else 0.0

    if wins > losses:
        bilan_icon = "🟢"
    elif wins == losses:
        bilan_icon = "🟡"
    else:
        bilan_icon = "🔴"

    msg  = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📋  U L T R O N  —  R É C A P  D U  J O U R\n"
    msg += f"     {datetime.now().strftime('%A %d %B %Y').upper()}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    for p in today_ps:
        sport_e = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(p["sport"], "🎯")
        if p["result"] == "WIN":
            res_icon = "✅"
        elif p["result"] == "LOSS":
            res_icon = "❌"
        else:
            res_icon = "⏳"

        msg += f"\n{res_icon}  {sport_e}  {p['pick_team']}"
        if p.get("pick_type") and p["pick_type"] != "ML":
            msg += f"  ({p['pick_type']})"
        msg += f"\n      Cote {p['odds']}  •  conf. {p['confidence']}%\n"
        if p.get("score"):
            msg += f"      📍 {p['score']}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{bilan_icon}  Aujourd'hui :  {wins}W  –  {losses}L"
    if total_g > 0:
        msg += f"  ({wr:.1%} WR)"
    if pending:
        msg += f"  •  {pending} en attente"
    msg += "\n"

    # Bilan global saison
    stats  = history["stats"]
    s_wins = stats.get("wins", 0)
    s_loss = stats.get("losses", 0)
    s_tot  = s_wins + s_loss
    s_wr   = s_wins / s_tot if s_tot > 0 else 0.0
    streak = _current_streak(picks)
    msg   += f"📈  Saison   :  {s_wins}W–{s_loss}L"
    if s_tot > 0:
        msg += f"  ({s_wr:.1%})"
    msg += f"  •  Série {streak}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    return msg


def format_daily_report(days: int = 7) -> str:
    """
    Génère un rapport de performance Telegram.
    days=1 → résultats d'hier | days=7 → semaine | days=30 → mois
    """
    history = load_history()
    picks   = history["picks"]
    stats   = history["stats"]

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [p for p in picks if p.get("date", "") >= cutoff]

    r_wins    = sum(1 for p in recent if p["result"] == "WIN")
    r_losses  = sum(1 for p in recent if p["result"] == "LOSS")
    r_pending = sum(1 for p in recent if p["result"] is None)
    r_total   = r_wins + r_losses
    r_wr      = r_wins / r_total if r_total > 0 else 0.0

    period_label = {1: "24 dernières heures", 7: "7 derniers jours", 30: "30 derniers jours"}.get(days, f"{days} jours")

    streak = _current_streak(picks)

    msg  = "📊  U L T R O N  —  P E R F O R M A N C E\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📅  {period_label}\n\n"
    msg += f"✅  Wins       :  {r_wins}\n"
    msg += f"❌  Losses     :  {r_losses}\n"
    msg += f"⏳  En attente :  {r_pending}\n"
    msg += f"🎯  Win Rate   :  {r_wr:.1%}\n"
    msg += f"🔥  Série      :  {streak}\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Saison complète
    s_wins   = stats.get("wins", 0)
    s_losses = stats.get("losses", 0)
    s_total  = s_wins + s_losses
    s_wr     = s_wins / s_total if s_total > 0 else 0.0
    msg += f"\n📈  Saison totale :  {s_wins}W  –  {s_losses}L"
    if s_total > 0:
        msg += f"  ({s_wr:.1%})"
    msg += "\n"

    # Derniers 5 résultats gradés
    graded = [p for p in picks if p["result"] is not None][-5:]
    if graded:
        msg += "\n🕐  DERNIERS RÉSULTATS\n"
        for p in reversed(graded):
            icon  = "✅" if p["result"] == "WIN" else "❌"
            sport_e = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(p["sport"], "🎯")
            msg  += f"\n  {icon}  {sport_e}  {p['pick_type']} — {p['pick_team']}  @ {p['odds']}\n"
            if p.get("score"):
                msg += f"       {p['score']}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🤖  Ultron se note lui-même — données ESPN"
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# SAUVEGARDE / RESTAURATION TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

async def backup_to_telegram(bot, chat_id: str) -> bool:
    """
    Envoie l'historique comme document Telegram.
    Fonctionne avec DB (export en mémoire) ou fichier JSON local.
    Retourne True si succès.
    """
    history = load_history()
    picks_count = len(history.get("picks", []))
    if picks_count == 0:
        logger.info("backup_to_telegram: aucun pick à sauvegarder")
        return False

    wins   = history.get("stats", {}).get("wins", 0)
    losses = history.get("stats", {}).get("losses", 0)
    wr     = history.get("stats", {}).get("win_rate", 0.0)

    caption = (
        f"🔒 ULTRON — Backup mémoire\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"📊 {picks_count} picks  •  {wins}W–{losses}L  •  {wr:.1%} WR"
    )

    try:
        # Export history vers un buffer mémoire (fonctionne avec ou sans fichier local)
        buf = io.BytesIO(json.dumps(history, indent=2, ensure_ascii=False).encode("utf-8"))
        buf.name = "picks_history.json"
        msg = await bot.send_document(
            chat_id=chat_id,
            document=buf,
            filename="picks_history.json",
            caption=caption,
        )
        logger.info(f"✅ Backup Telegram OK — {picks_count} picks sauvegardés")
        return True
    except Exception as e:
        logger.error(f"❌ backup_to_telegram: {e}")
        return False


async def restore_from_telegram(bot, chat_id: str) -> bool:
    """
    Si DATABASE_URL est défini, les données persistent déjà en DB — rien à restaurer.
    Sinon, télécharge le dernier backup Telegram vers le fichier local.
    Retourne True si une restauration a eu lieu.
    """
    if _DATABASE_URL:
        return False  # DB persistante, pas besoin de restaurer

    if not os.path.exists(BACKUP_META_FILE):
        logger.info("restore_from_telegram: aucun backup_meta.json trouvé")
        return False

    try:
        with open(BACKUP_META_FILE, "r", encoding="utf-8") as mf:
            meta = json.load(mf)
        file_id = meta.get("file_id")
        if not file_id:
            return False

        tg_file = await bot.get_file(file_id)
        await tg_file.download_to_drive(HISTORY_FILE)

        picks_count = meta.get("picks_count", "?")
        backed_at   = meta.get("backed_up_at", "?")[:16]
        logger.info(f"✅ Historique restauré depuis Telegram ({picks_count} picks, backup du {backed_at})")

        # Notifie l'admin
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"♻️  ULTRON — Mémoire restaurée\n"
                    f"📅  Backup du {backed_at}\n"
                    f"📊  {picks_count} picks récupérés"
                ),
            )
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error(f"❌ restore_from_telegram: {e}")
        return False


def format_result_notification(updated_picks: list) -> str:
    """
    Génère un message de notification pour les picks qui viennent d'être gradés.
    Envoyé automatiquement après check_and_update_results().
    """
    if not updated_picks:
        return ""

    wins   = sum(1 for p in updated_picks if p["result"] == "WIN")
    losses = sum(1 for p in updated_picks if p["result"] == "LOSS")

    msg  = "🔔  R É S U L T A T S  —  ULTRON\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for p in updated_picks:
        icon    = "✅" if p["result"] == "WIN" else "❌"
        sport_e = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}.get(p["sport"], "🎯")
        msg    += f"{icon}  {sport_e}  {p['pick_type']} — {p['pick_team']}\n"
        msg    += f"     Cote  {p['odds']}  •  conf. {p['confidence']}%\n"
        if p.get("score"):
            msg += f"     {p['score']}\n"
        msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"✅ {wins} win(s)   ❌ {losses} loss(es)  ce soir\n\n"

    # Mise à jour stats globales
    stats = get_stats()
    s_wr  = stats.get("win_rate", 0.0)
    msg  += f"📈  Win Rate global :  {s_wr:.1%}  ({stats['wins']}W–{stats['losses']}L)"
    return msg
