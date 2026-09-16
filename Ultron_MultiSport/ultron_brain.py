#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON Brain — ultron_brain.py
═══════════════════════════════════════════════════════════════════════════════
Moteur d'auto-analyse et d'optimisation du ROI.

Ce module analyse l'historique des picks stockés dans pick_memory.py et :
  1. Calcule le ROI réel par sport / tranche de confiance / type / cote
  2. Identifie les configurations les plus rentables
  3. Met à jour automatiquement les seuils d'envoi (learned_thresholds.json)
  4. Filtre les picks futurs selon ces seuils — Ultron apprend de lui-même

Fichiers produits :
  • learned_thresholds.json  ← seuils optimaux sauvegardés
  • brain_analysis.json      ← dernière analyse complète (debug)

Appelé :
  • Chaque soir à 23h30 Québec (après le récap de 23h00)
  • Via /analyse (commande Telegram)
  • Via run_analysis() en import
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Chemins (fallback JSON local si pas de DB) ────────────────────────────────
_BASE = "/data" if os.path.isdir("/data") else "."
THRESHOLDS_FILE = os.path.join(_BASE, "learned_thresholds.json")
ANALYSIS_FILE   = os.path.join(_BASE, "brain_analysis.json")

# ── PostgreSQL (Railway DATABASE_URL) — même pattern que pick_memory.py ───────
_DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _db_connect():
    """Ouvre une connexion psycopg2 si DATABASE_URL est défini."""
    if not _DATABASE_URL:
        return None
    try:
        import psycopg2
        # Railway injecte 'postgres://' mais psycopg2 requiert 'postgresql://'
        url = _DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    except Exception as e:
        logger.error(f"❌ brain DB connexion: {e}")
        return None


def _db_init():
    """Crée la table brain_store si elle n'existe pas encore."""
    if not _DATABASE_URL:
        logger.info("ℹ️  brain: DATABASE_URL absent — stockage JSON local uniquement")
        return
    conn = _db_connect()
    if not conn:
        logger.warning("⚠️  brain: DATABASE_URL présent mais connexion échouée — fallback JSON")
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS brain_store (
                        key  TEXT PRIMARY KEY,
                        data JSONB NOT NULL
                    )
                """)
        logger.info("✅ brain: table brain_store prête (PostgreSQL)")
    except Exception as e:
        logger.error(f"❌ brain DB init: {e}")
    finally:
        conn.close()


def _db_load(key: str):
    """Charge un blob JSON depuis brain_store, ou None si absent/échec/pas de DB."""
    conn = _db_connect()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM brain_store WHERE key = %s", (key,))
                row = cur.fetchone()
                if row:
                    return row[0]  # psycopg2 désérialise JSONB automatiquement
    except Exception as e:
        logger.error(f"❌ brain DB load ({key}): {e}")
    finally:
        conn.close()
    return None


def _db_save(key: str, data: dict) -> bool:
    """Sauvegarde un blob JSON dans brain_store. Retourne True si succès DB."""
    conn = _db_connect()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO brain_store (key, data) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data
                    """,
                    (key, json.dumps(data, ensure_ascii=False)),
                )
        return True
    except Exception as e:
        logger.error(f"❌ brain DB save ({key}): {e}")
        return False
    finally:
        conn.close()


_db_init()

# ── Seuils par défaut (avant apprentissage) ───────────────────────────────────
DEFAULT_THRESHOLDS = {
    "min_confidence": {
        "NBA": 52,
        "NHL": 52,
        "NFL": 52,
        "default": 52,
    },
    "min_ev_pct": {
        "NBA": 0.0,
        "NHL": 0.0,
        "NFL": 0.0,
        "default": 0.0,
    },
    "best_pick_types": {    # types autorisés par sport (appris)
        "NBA": ["ML"],
        "NHL": ["ML"],
        "NFL": ["ML"],
        "default": ["ML"],
    },
    # Paramètres du modèle de prédiction (appris automatiquement)
    "model_adjustments": {
        # model_weight     : poids de notre modèle ML vs. cote du marché (0.0=marché pur, 1.0=modèle pur)
        # confidence_scale : facteur de calibration (1.0=neutre, <1=on était trop confiant)
        # home_advantage_delta : correction supplémentaire vers l'équipe domicile (prob)
        "NBA": {"model_weight": 0.60, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
        "NHL": {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
        "NFL": {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
    },
    "sample_size": 0,
    "updated_at":  None,
    "roi_overall": 0.0,
    "win_rate_overall": 0.0,
}

# Taille minimale de l'échantillon pour faire confiance aux stats
MIN_SAMPLE = 10


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def _parse_odds(odds_str: str) -> float:
    """Convertit une cote américaine (str) en profit net par unité misée."""
    try:
        odds = float(str(odds_str).replace(",", ".").strip())
        if odds >= 100:
            return odds / 100.0
        elif odds <= -100:
            return 100.0 / abs(odds)
        else:
            return 0.0
    except (ValueError, TypeError):
        return 0.9   # cote neutre si inconnu


def _roi(wins: int, losses: int, avg_payout: float) -> float:
    """ROI en % : (gains - mises) / mises * 100. Mise = 1 unité par pick."""
    total = wins + losses
    if total == 0:
        return 0.0
    gain = wins * avg_payout - losses
    return round(gain / total * 100, 2)


def _bucket_confidence(conf: int) -> str:
    """Regroupe une confiance en tranche de 10%."""
    if conf < 50:   return "<50%"
    if conf < 60:   return "50-59%"
    if conf < 70:   return "60-69%"
    if conf < 80:   return "70-79%"
    return "80%+"


def _bucket_odds(odds_str: str) -> str:
    """Regroupe des cotes américaines en catégorie."""
    try:
        o = float(str(odds_str).replace(",", ".").strip())
        if o <= -200:   return "Gros favori (≤-200)"
        if o <= -150:   return "Favori fort (-150 à -200)"
        if o <= -110:   return "Favori modéré (-110 à -150)"
        if o <= 105:    return "Pick'em (-110 à +105)"
        if o <= 150:    return "Léger outsider (+105 à +150)"
        return "Outsider (+150+)"
    except (ValueError, TypeError):
        return "Inconnu"


def _merge_defaults(data: dict) -> dict:
    """Fusion avec les défauts pour les nouvelles clés."""
    for k, v in DEFAULT_THRESHOLDS.items():
        if k not in data:
            data[k] = v
    return data


def load_thresholds() -> dict:
    # Essai PostgreSQL en priorité
    data = _db_load("learned_thresholds")
    if data is not None:
        return _merge_defaults(data)

    # Fallback fichier JSON local
    if os.path.exists(THRESHOLDS_FILE):
        try:
            with open(THRESHOLDS_FILE, "r", encoding="utf-8") as f:
                return _merge_defaults(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_THRESHOLDS)


def _save_thresholds(t: dict):
    # Sauvegarder dans PostgreSQL si disponible
    if _db_save("learned_thresholds", t):
        return  # succès DB, pas besoin d'écrire le fichier

    # Fallback fichier JSON local
    try:
        with open(THRESHOLDS_FILE, "w", encoding="utf-8") as f:
            json.dump(t, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error(f"❌ brain: erreur écriture seuils: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE DES PICKS
# ─────────────────────────────────────────────────────────────────────────────

def _analyse_segment(picks: list) -> dict:
    """
    Calcule W/L/ROI/WR pour un segment de picks.
    Retourne {} si échantillon insuffisant.
    """
    graded = [p for p in picks if p.get("result") in ("WIN", "LOSS")]
    wins   = [p for p in graded if p["result"] == "WIN"]
    losses = [p for p in graded if p["result"] == "LOSS"]
    n      = len(graded)
    if n == 0:
        return {}

    # Payout moyen
    payouts = [_parse_odds(p.get("odds", "-110")) for p in graded]
    avg_pay = sum(payouts) / len(payouts)

    return {
        "n":        n,
        "wins":     len(wins),
        "losses":   len(losses),
        "win_rate": round(len(wins) / n, 4),
        "roi":      _roi(len(wins), len(losses), avg_pay),
        "avg_odds": avg_pay,
    }


def run_analysis(picks_history: dict = None) -> dict:
    """
    Analyse complète de l'historique.
    Si picks_history est None, charge depuis pick_memory.
    Retourne le rapport d'analyse (dict).
    """
    if picks_history is None:
        try:
            from pick_memory import load_history
            picks_history = load_history()
        except ImportError:
            logger.error("❌ brain: impossible de charger pick_memory")
            return {}

    all_picks = picks_history.get("picks", [])
    graded    = [p for p in all_picks if p.get("result") in ("WIN", "LOSS")]
    n_total   = len(graded)

    analysis = {
        "generated_at": datetime.now().isoformat(),
        "total_graded": n_total,
        "overall":      _analyse_segment(graded),
        "by_sport":     {},
        "by_confidence_bracket": {},
        "by_odds_bucket":        {},
        "by_pick_type":          {},
        "by_day_of_week":        {},
        "optimal_confidence":    {},   # meilleur seuil min par sport
    }

    # ── Par sport ─────────────────────────────────────────────────────────
    by_sport: dict = defaultdict(list)
    for p in graded:
        by_sport[p.get("sport", "?")].append(p)
    for sport, ps in by_sport.items():
        seg = _analyse_segment(ps)
        if seg:
            analysis["by_sport"][sport] = seg

    # ── Par tranche de confiance ──────────────────────────────────────────
    by_conf: dict = defaultdict(list)
    for p in graded:
        by_conf[_bucket_confidence(int(p.get("confidence", 50)))].append(p)
    for bucket, ps in by_conf.items():
        seg = _analyse_segment(ps)
        if seg:
            analysis["by_confidence_bracket"][bucket] = seg

    # ── Par plage de cotes ────────────────────────────────────────────────
    by_odds: dict = defaultdict(list)
    for p in graded:
        by_odds[_bucket_odds(p.get("odds", ""))].append(p)
    for bucket, ps in by_odds.items():
        seg = _analyse_segment(ps)
        if seg:
            analysis["by_odds_bucket"][bucket] = seg

    # ── Par type de pick ──────────────────────────────────────────────────
    by_type: dict = defaultdict(list)
    for p in graded:
        by_type[p.get("pick_type", "ML")].append(p)
    for pt, ps in by_type.items():
        seg = _analyse_segment(ps)
        if seg:
            analysis["by_pick_type"][pt] = seg

    # ── Par jour de la semaine ────────────────────────────────────────────
    by_dow: dict = defaultdict(list)
    for p in graded:
        try:
            dow = datetime.strptime(p["date"], "%Y-%m-%d").strftime("%A")
        except (ValueError, KeyError):
            dow = "Unknown"
        by_dow[dow].append(p)
    for dow, ps in by_dow.items():
        seg = _analyse_segment(ps)
        if seg:
            analysis["by_day_of_week"][dow] = seg

    # ── Calcul du seuil de confiance optimal par sport ────────────────────
    # On teste les seuils de 50 à 80 par tranche de 5
    # et on cherche celui qui maximise le ROI sur l'échantillon disponible
    for sport in ("NBA", "NHL", "NFL"):
        sport_picks = by_sport.get(sport, [])
        if not sport_picks:
            continue
        best_thresh = DEFAULT_THRESHOLDS["min_confidence"][sport]
        best_roi    = -999.0
        best_wr     = 0.0
        for thresh in range(50, 85, 5):
            subset = [p for p in sport_picks if int(p.get("confidence", 0)) >= thresh]
            seg = _analyse_segment(subset)
            if not seg or seg["n"] < MIN_SAMPLE:
                continue
            # On optimise sur le ROI, mais win_rate doit dépasser 50%
            if seg["win_rate"] >= 0.50 and seg["roi"] > best_roi:
                best_roi    = seg["roi"]
                best_wr     = seg["win_rate"]
                best_thresh = thresh
        analysis["optimal_confidence"][sport] = {
            "threshold": best_thresh,
            "roi":       round(best_roi, 2) if best_roi != -999.0 else 0.0,
            "win_rate":  round(best_wr, 4),
        }

    # ── Sauvegarde du rapport brut (PostgreSQL en priorité, JSON en secours) ─
    if not _db_save("brain_analysis", analysis):
        try:
            with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    # ── Mise à jour des seuils appris ─────────────────────────────────────
    _update_thresholds(analysis, n_total)

    return analysis


def _is_home_pick(pick: dict) -> bool:
    """Retourne True si le pick est sur l'équipe domicile."""
    pick_team = pick.get("pick_team", "").lower()
    home_team  = pick.get("home_team", "").lower()
    if not home_team:
        return False
    home_parts = [w for w in home_team.split() if len(w) > 3]
    return any(p in pick_team for p in home_parts)


def _update_thresholds(analysis: dict, n_total: int):
    """
    Met à jour learned_thresholds.json selon les résultats de l'analyse.
    N'applique les changements que si l'échantillon est suffisant (≥ MIN_SAMPLE).
    Utilise une mise à jour progressive (EWMA) pour éviter les sur-ajustements.
    """
    thresholds = load_thresholds()

    overall = analysis.get("overall", {})
    if overall:
        thresholds["roi_overall"]      = overall.get("roi", 0.0)
        thresholds["win_rate_overall"] = overall.get("win_rate", 0.0)

    thresholds["sample_size"] = n_total
    thresholds["updated_at"]  = datetime.now().isoformat()

    opt = analysis.get("optimal_confidence", {})
    for sport in ("NBA", "NHL", "NFL"):
        if sport in opt:
            new_thresh = opt[sport]["threshold"]
            old_thresh = thresholds["min_confidence"].get(sport,
                         DEFAULT_THRESHOLDS["min_confidence"]["default"])
            # EWMA (80% ancien, 20% nouveau) si échantillon trop petit
            n_sport = analysis.get("by_sport", {}).get(sport, {}).get("n", 0)
            if n_sport >= MIN_SAMPLE * 2:
                # Assez de data → mise à jour complète
                thresholds["min_confidence"][sport] = new_thresh
            elif n_sport >= MIN_SAMPLE:
                # Mise à jour progressive
                blended = int(round(0.7 * old_thresh + 0.3 * new_thresh))
                thresholds["min_confidence"][sport] = blended

    # Meilleur type de pick par sport (si échantillon suffisant)
    by_type = analysis.get("by_pick_type", {})
    try:
        from pick_memory import load_history as _lh
        all_graded_picks = [p for p in _lh()["picks"] if p.get("result") in ("WIN", "LOSS")]
    except ImportError:
        all_graded_picks = []

    for sport in ("NBA", "NHL", "NFL"):
        sport_graded = [p for p in all_graded_picks if p.get("sport") == sport]

        # Best pick types
        sport_picks_by_type: dict = defaultdict(list)
        for p in sport_graded:
            sport_picks_by_type[p.get("pick_type", "ML")].append(p)
        best_types = []
        for pt, ps in sport_picks_by_type.items():
            seg = _analyse_segment(ps)
            if seg and seg["n"] >= MIN_SAMPLE and seg["win_rate"] >= 0.50:
                best_types.append(pt)
        if best_types:
            thresholds["best_pick_types"][sport] = best_types

        # ── Auto-calibration du modèle de prédiction ────────────────────
        # Ne tourne que si on a suffisamment de picks gradés pour ce sport
        n_sport = len(sport_graded)
        if n_sport < MIN_SAMPLE:
            continue

        # Defaults par sport
        default_mw = {"NBA": 0.60, "NHL": 0.50, "NFL": 0.50}.get(sport, 0.50)
        if "model_adjustments" not in thresholds:
            thresholds["model_adjustments"] = {}
        cur = thresholds["model_adjustments"].get(sport, {
            "model_weight":         default_mw,
            "confidence_scale":     1.0,
            "home_advantage_delta": 0.0,
        })

        # 1. Calibration de la confiance
        #    Si Ultron dit 70% en moyenne mais gagne à 55% → scale = 0.786
        avg_conf  = sum(p.get("confidence", 65) for p in sport_graded) / n_sport / 100.0
        actual_wr = sum(1 for p in sport_graded if p["result"] == "WIN") / n_sport
        if avg_conf > 0.01:
            raw_scale = max(0.70, min(1.30, actual_wr / avg_conf))
            # Mise à jour progressive (EWMA 80/20)
            cur["confidence_scale"] = round(
                0.80 * cur.get("confidence_scale", 1.0) + 0.20 * raw_scale, 4
            )

        # 2. Poids modèle vs marché
        #    Overconfiant (+7%) → faire davantage confiance au marché
        #    Underconfiant (−7%) → faire davantage confiance au modèle
        gap = actual_wr - avg_conf
        old_mw = cur.get("model_weight", default_mw)
        if gap < -0.07:          # modèle systématiquement trop optimiste
            new_mw = max(0.30, old_mw - 0.03)
        elif gap > 0.07:         # modèle systématiquement sous-estime la force
            new_mw = min(0.75, old_mw + 0.03)
        else:
            new_mw = old_mw      # dans la marge → pas de changement
        cur["model_weight"] = round(new_mw, 4)

        # 3. Correction de l'avantage domicile
        #    Si les picks domicile gagnent bien plus que les picks visiteurs
        #    → le modèle sous-estime l'avantage terrain → on additionne un delta
        home_ps = [p for p in sport_graded if _is_home_pick(p)]
        away_ps = [p for p in sport_graded if not _is_home_pick(p)]
        if len(home_ps) >= 5 and len(away_ps) >= 5:
            home_wr = sum(1 for p in home_ps if p["result"] == "WIN") / len(home_ps)
            away_wr = sum(1 for p in away_ps if p["result"] == "WIN") / len(away_ps)
            # Delta brut: home surpasse away → ajouter un bonus probabilité domicile
            raw_delta = (home_wr - away_wr) * 0.12   # facteur d'amortissement
            raw_delta = max(-0.05, min(0.05, raw_delta))
            cur["home_advantage_delta"] = round(
                0.80 * cur.get("home_advantage_delta", 0.0) + 0.20 * raw_delta, 4
            )

        thresholds["model_adjustments"][sport] = cur
        logger.info(
            f"🧠 Brain [{sport}]  mw={cur['model_weight']:.2f}  "
            f"cal={cur['confidence_scale']:.3f}  "
            f"home_δ={cur['home_advantage_delta']:+.3f}  "
            f"WR={actual_wr:.1%}  n={n_sport}"
        )

    _save_thresholds(thresholds)
    logger.info(
        f"🧠 Brain: seuils mis à jour — "
        f"ROI {overall.get('roi', 0):.1f}%  WR {overall.get('win_rate', 0):.1%}  "
        f"n={n_total}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# API PUBLIQUE : FILTRAGE + PARAMÈTRES APPRIS
# ─────────────────────────────────────────────────────────────────────────────

def get_model_adjustments(sport: str) -> dict:
    """
    Retourne les paramètres appris du modèle de prédiction pour un sport.
    Utilisé dans generate_prediction_nba/nhl/nfl() pour auto-calibrer.

    Clés retournées:
      model_weight         (float 0.30–0.75)  : poids modèle vs. marché
      confidence_scale     (float 0.70–1.30)  : facteur de calibration confiance
      home_advantage_delta (float -0.05–0.05) : correction probabilité domicile
    """
    defaults = {
        "NBA": {"model_weight": 0.60, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
        "NHL": {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
        "NFL": {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0},
    }
    t = load_thresholds()
    if t.get("sample_size", 0) < MIN_SAMPLE:
        return defaults.get(sport, {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0})
    return t.get("model_adjustments", {}).get(
        sport, defaults.get(sport, {"model_weight": 0.50, "confidence_scale": 1.0, "home_advantage_delta": 0.0})
    )


def should_send_pick(sport: str, confidence: int, pick_type: str = "ML") -> bool:
    """
    Retourne True si ce pick doit être envoyé selon les seuils appris.
    Utilisé dans auto_send_pronostics pour filtrer les picks faibles.
    """
    t = load_thresholds()
    # Pas assez de données → ne pas filtrer, tout envoyer
    if t.get("sample_size", 0) < MIN_SAMPLE:
        return True
    min_conf = t["min_confidence"].get(sport, t["min_confidence"].get("default", 58))
    return confidence >= min_conf


# ─────────────────────────────────────────────────────────────────────────────
# RAPPORT TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def format_brain_report(analysis: dict = None) -> str:
    """
    Génère le rapport d'auto-analyse Ultron.
    Si analysis est None, recharge depuis brain_analysis.json ou relance run_analysis().
    """
    if analysis is None:
        analysis = _db_load("brain_analysis")  # PostgreSQL en priorité
        if analysis is None and os.path.exists(ANALYSIS_FILE):
            try:
                with open(ANALYSIS_FILE, "r", encoding="utf-8") as f:
                    analysis = json.load(f)
            except (json.JSONDecodeError, OSError):
                analysis = None
        if analysis is None:
            analysis = run_analysis()

    if not analysis:
        return "🧠 Brain: aucune donnée disponible pour l'analyse."

    overall  = analysis.get("overall", {})
    n_total  = analysis.get("total_graded", 0)
    by_sport = analysis.get("by_sport", {})
    by_conf  = analysis.get("by_confidence_bracket", {})
    by_type  = analysis.get("by_pick_type", {})
    by_odds  = analysis.get("by_odds_bucket", {})
    opt_conf = analysis.get("optimal_confidence", {})
    t        = load_thresholds()

    msg  = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🧠  U L T R O N  —  A U T O - A N A L Y S E\n"
    msg += f"     {datetime.now().strftime('%Y-%m-%d  %H:%M')}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if n_total == 0:
        msg += "📭 Aucun pick gradé disponible.\n"
        msg += "     L'analyse sera disponible après les premiers résultats ESPN.\n"
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return msg

    # ── Résumé global ──────────────────────────────────────────────────────
    wr   = overall.get("win_rate", 0)
    roi  = overall.get("roi", 0)
    wins = overall.get("wins", 0)
    loss = overall.get("losses", 0)

    roi_icon = "🟢" if roi > 0 else ("🟡" if roi == 0 else "🔴")
    msg += f"📊  GLOBAL  ({n_total} picks gradés)\n"
    msg += f"   🎯  Win Rate  :  {wr:.1%}  ({wins}W – {loss}L)\n"
    msg += f"   {roi_icon}  ROI        :  {roi:+.1f}% / unité\n\n"

    # ── Par sport ──────────────────────────────────────────────────────────
    sport_emoji = {"NBA": "🏀", "NHL": "🏒", "NFL": "🏈"}
    if by_sport:
        msg += "─── PAR SPORT ───────────────────────\n"
        for sport in ("NBA", "NHL", "NFL"):
            s = by_sport.get(sport)
            if not s:
                continue
            e = sport_emoji.get(sport, "🎯")
            s_roi  = s.get("roi", 0)
            s_icon = "🟢" if s_roi > 0 else ("🟡" if s_roi == 0 else "🔴")
            msg += (
                f"   {e}  {sport:<4}  {s['win_rate']:.0%} WR  "
                f"{s_icon} {s_roi:+.1f}% ROI  "
                f"({s['wins']}W–{s['losses']}L  n={s['n']})\n"
            )
        msg += "\n"

    # ── Par tranche de confiance ───────────────────────────────────────────
    if by_conf:
        msg += "─── PAR CONFIANCE ───────────────────\n"
        order = ["<50%", "50-59%", "60-69%", "70-79%", "80%+"]
        for b in order:
            s = by_conf.get(b)
            if not s:
                continue
            s_roi  = s.get("roi", 0)
            s_icon = "🟢" if s_roi > 0 else ("🟡" if s_roi == 0 else "🔴")
            msg += (
                f"   {b:<8}  {s['win_rate']:.0%} WR  "
                f"{s_icon} {s_roi:+.1f}% ROI  (n={s['n']})\n"
            )
        msg += "\n"

    # ── Par type de pick ───────────────────────────────────────────────────
    if by_type:
        msg += "─── PAR TYPE ────────────────────────\n"
        for pt, s in by_type.items():
            s_roi  = s.get("roi", 0)
            s_icon = "🟢" if s_roi > 0 else ("🟡" if s_roi == 0 else "🔴")
            msg += (
                f"   {pt:<6}  {s['win_rate']:.0%} WR  "
                f"{s_icon} {s_roi:+.1f}% ROI  (n={s['n']})\n"
            )
        msg += "\n"

    # ── Par plage de cotes ─────────────────────────────────────────────────
    if by_odds:
        msg += "─── PAR COTE ────────────────────────\n"
        for bucket, s in sorted(by_odds.items(), key=lambda x: -x[1].get("roi", 0)):
            s_roi  = s.get("roi", 0)
            s_icon = "🟢" if s_roi > 0 else "🔴"
            msg += (
                f"   {bucket[:22]:<22}  "
                f"{s_icon} {s_roi:+.1f}%  (n={s['n']})\n"
            )
        msg += "\n"

    # ── Seuils appris & recommandations ───────────────────────────────────
    msg += "─── SEUILS APPRIS ───────────────────\n"
    model_adj = t.get("model_adjustments", {})
    for sport in ("NBA", "NHL", "NFL"):
        thresh = t["min_confidence"].get(sport, "—")
        opt    = opt_conf.get(sport, {})
        adj    = model_adj.get(sport, {})
        if opt:
            o_roi = opt.get("roi", 0)
            o_wr  = opt.get("win_rate", 0)
            msg += (
                f"   {sport_emoji.get(sport,'')} {sport}  min conf = {thresh}%  "
                f"→  {o_wr:.0%} WR  {o_roi:+.1f}% ROI attendu\n"
            )
        else:
            msg += f"   {sport_emoji.get(sport,'')} {sport}  min conf = {thresh}%  (données insuffisantes)\n"
    msg += "\n"

    # ── Paramètres du modèle (calibration auto) ────────────────────────────
    msg += "─── CALIBRATION MODÈLE ──────────────\n"
    for sport in ("NBA", "NHL", "NFL"):
        adj = model_adj.get(sport)
        if not adj:
            continue
        mw   = adj.get("model_weight", 0.50)
        cal  = adj.get("confidence_scale", 1.0)
        hdel = adj.get("home_advantage_delta", 0.0)
        cal_icon = "🟢" if 0.95 <= cal <= 1.05 else ("🟡" if 0.85 <= cal <= 1.15 else "🔴")
        msg += (
            f"   {sport_emoji.get(sport,'')} {sport}  "
            f"modèle {mw:.0%} / marché {1-mw:.0%}  "
            f"{cal_icon} cal={cal:.3f}  "
            f"dom={hdel:+.3f}\n"
        )
    if not any(s in model_adj for s in ("NBA","NHL","NFL")):
        msg += "   ⏳ En attente de données suffisantes\n"
    msg += "\n"

    # ── Verdict & conseil ─────────────────────────────────────────────────
    msg += "─── VERDICT ─────────────────────────\n"
    if n_total < MIN_SAMPLE:
        msg += f"⚠️  Seulement {n_total} picks gradés.\n"
        msg += f"     Optimisation complète à partir de {MIN_SAMPLE} picks.\n"
    else:
        if roi > 5:
            msg += "🟢  Excellente rentabilité — Ultron performe bien!\n"
        elif roi > 0:
            msg += "🟡  Légèrement rentable — optimisation en cours.\n"
        elif roi > -5:
            msg += "🟠  ROI légèrement négatif — ajustements appliqués.\n"
        else:
            msg += "🔴  ROI négatif — seuils rehaussés automatiquement.\n"

        # Plus grande force
        best_sport = max(by_sport.items(), key=lambda x: x[1].get("roi", -999), default=None) if by_sport else None
        if best_sport and by_sport[best_sport[0]].get("roi", 0) > 0:
            msg += f"💪  Meilleur sport : {best_sport[0]} ({by_sport[best_sport[0]]['roi']:+.1f}% ROI)\n"

        best_conf = max(by_conf.items(), key=lambda x: x[1].get("roi", -999), default=None) if by_conf else None
        if best_conf and by_conf[best_conf[0]].get("roi", 0) > 0:
            msg += f"🎯  Meilleure confiance : {best_conf[0]} ({by_conf[best_conf[0]]['roi']:+.1f}% ROI)\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🤖  Ultron Brain — auto-apprentissage ESPN"
    return msg
