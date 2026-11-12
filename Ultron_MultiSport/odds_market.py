"""
odds_market.py — Vue "marché" à partir de The Odds API
=======================================================

Transforme la réponse brute de The Odds API (liste d'événements avec cotes de
plusieurs bookmakers) en trois informations utilisables par les moteurs Ultron :

1. PROBABILITÉ DE CONSENSUS SANS MARGE (no-vig)
   Pour chaque bookmaker, on retire sa marge (vig) puis on fait la moyenne
   pondérée des probabilités. Pinnacle (le bookmaker de référence du marché,
   marges les plus faibles, limites élevées) pèse 3x, les autres 1x.
   -> c'est la meilleure estimation publique de la "vraie" probabilité.

2. COTE DE RÉFÉRENCE JOUABLE
   Médiane des cotes des bookmakers "récréatifs" (DraftKings, FanDuel, BetMGM,
   BetRivers, Caesars, Fanatics, Bovada). C'est ce qu'un parieur normal peut
   réellement obtenir, donc le bon prix pour calculer l'EV.
   NOTE : bet365 n'est PAS disponible dans The Odds API pour NBA/NHL/MLB/NFL
   (seulement AFL/NRL), la médiane des books récréatifs sert de proxy.

3. LIGNES DE CONSENSUS pour spread et total (ligne la plus offerte, pondérée)
   avec cotes de référence et probabilités sans marge à cette ligne.

Aucune dépendance externe. Fonctions pures, testables hors-ligne.
"""

import re
import statistics
import unicodedata

# 10 bookmakers = 1 "région" de quota (doc The Odds API) : même coût qu'avant.
BOOKMAKERS_PARAM = (
    "pinnacle,draftkings,fanduel,betmgm,betrivers,"
    "williamhill_us,fanatics,bovada,lowvig,betonlineag"
)

# Poids dans le consensus (défaut 1.0)
SHARP_WEIGHTS = {"pinnacle": 3.0, "lowvig": 1.5}

# Books utilisés pour la cote de référence jouable (proxy bet365)
PRICE_BOOKS = frozenset({
    "draftkings", "fanduel", "betmgm", "betrivers",
    "williamhill_us", "fanatics", "bovada",
})


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def devig_pair(odds_a: float, odds_b: float):
    """Retire la marge d'un marché à 2 issues (méthode proportionnelle).
    Retourne (p_a, p_b) ou None si les cotes sont invalides."""
    try:
        if not odds_a or not odds_b or odds_a <= 1.0 or odds_b <= 1.0:
            return None
        ia, ib = 1.0 / odds_a, 1.0 / odds_b
        s = ia + ib
        return ia / s, ib / s
    except (TypeError, ZeroDivisionError):
        return None


def _wmean(pairs):
    """Moyenne pondérée de [(poids, valeur), ...]."""
    tw = sum(w for w, _ in pairs)
    if tw <= 0:
        return None
    return sum(w * v for w, v in pairs) / tw


def _median(values):
    return statistics.median(values) if values else None


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _tokens(name: str) -> set:
    s = _strip_accents((name or "").lower())
    return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) >= 3}


# ─────────────────────────────────────────────────────────────────────────────
# Recherche de l'événement
# ─────────────────────────────────────────────────────────────────────────────

def find_event(events: list, away_team: str, home_team: str):
    """
    Trouve l'événement Odds API correspondant à away @ home.
    Retourne (event, swapped) ou (None, False).
    swapped=True si The Odds API a inversé domicile/visiteur (matchs neutres).
    """
    ta, th = _tokens(away_team), _tokens(home_team)
    if not ta or not th:
        return None, False

    best, best_score, best_swapped = None, 0, False
    for ev in events or []:
        ea, eh = _tokens(ev.get("away_team", "")), _tokens(ev.get("home_team", ""))
        # orientation normale
        if ta & ea and th & eh:
            sc = 2 * len(ta & ea) + 2 * len(th & eh)
            if sc > best_score:
                best, best_score, best_swapped = ev, sc, False
        # orientation inversée (plus faible, départage seulement)
        if ta & eh and th & ea:
            sc = len(ta & eh) + len(th & ea)
            if sc > best_score:
                best, best_score, best_swapped = ev, sc, True
    return best, best_swapped


# ─────────────────────────────────────────────────────────────────────────────
# Vue marché d'un événement
# ─────────────────────────────────────────────────────────────────────────────

def _price_ref(rows, idx):
    """Médiane de la cote en position idx parmi les books récréatifs.
    Repli : médiane de tous les books si aucun récréatif n'a la ligne."""
    soft = [r["prices"][idx] for r in rows if r["soft"]]
    if soft:
        return _median(soft)
    return _median([r["prices"][idx] for r in rows])


def _market_view_raw(event: dict) -> dict:
    ev_home, ev_away = event.get("home_team"), event.get("away_team")

    ml_rows = []                 # {w, soft, p:(home,away), prices:(home,away)}
    spread_by_pt = {}            # point domicile -> rows
    total_by_pt = {}             # point -> rows (p/prices = (over, under))
    pin_p_home = None

    for bk in event.get("bookmakers", []) or []:
        key = bk.get("key", "")
        w = SHARP_WEIGHTS.get(key, 1.0)
        soft = key in PRICE_BOOKS

        for m in bk.get("markets", []) or []:
            outs = m.get("outcomes", []) or []
            mk = m.get("key")

            if mk == "h2h":
                oh = next((o for o in outs if o.get("name") == ev_home), None)
                oa = next((o for o in outs if o.get("name") == ev_away), None)
                if not oh or not oa:
                    continue
                dv = devig_pair(oh.get("price"), oa.get("price"))
                if not dv:
                    continue
                ml_rows.append({"w": w, "soft": soft, "p": dv,
                                "prices": (oh["price"], oa["price"])})
                if key == "pinnacle":
                    pin_p_home = dv[0]

            elif mk == "spreads":
                oh = next((o for o in outs if o.get("name") == ev_home), None)
                oa = next((o for o in outs if o.get("name") == ev_away), None)
                if not oh or not oa:
                    continue
                ph, pa = oh.get("point"), oa.get("point")
                if ph is None or pa is None or abs(ph + pa) > 1e-9:
                    continue
                dv = devig_pair(oh.get("price"), oa.get("price"))
                if not dv:
                    continue
                spread_by_pt.setdefault(float(ph), []).append(
                    {"w": w, "soft": soft, "p": dv,
                     "prices": (oh["price"], oa["price"])})

            elif mk == "totals":
                ov = next((o for o in outs if o.get("name") == "Over"), None)
                un = next((o for o in outs if o.get("name") == "Under"), None)
                if not ov or not un:
                    continue
                po, pu = ov.get("point"), un.get("point")
                if po is None or pu is None or abs(po - pu) > 1e-9:
                    continue
                dv = devig_pair(ov.get("price"), un.get("price"))
                if not dv:
                    continue
                total_by_pt.setdefault(float(po), []).append(
                    {"w": w, "soft": soft, "p": dv,
                     "prices": (ov["price"], un["price"])})

    result = {"ml": None, "spread": None, "total": None}

    # ── Moneyline ─────────────────────────────────────────────────────────
    if len(ml_rows) >= 2:
        p_home = _wmean([(r["w"], r["p"][0]) for r in ml_rows])
        spread_p = (max(r["p"][0] for r in ml_rows) - min(r["p"][0] for r in ml_rows))
        result["ml"] = {
            "p_home": p_home,
            "p_away": 1.0 - p_home,
            "price_home": _price_ref(ml_rows, 0),
            "price_away": _price_ref(ml_rows, 1),
            "best_home": max(r["prices"][0] for r in ml_rows),
            "best_away": max(r["prices"][1] for r in ml_rows),
            "n_books": len(ml_rows),
            "pinnacle_p_home": pin_p_home,
            "disagreement": round(spread_p, 4),   # écart max entre books
        }

    # ── Spread : ligne de consensus (poids total le plus élevé) ───────────
    def _pick_point(by_pt):
        if not by_pt:
            return None
        pts = sorted(by_pt)
        med = _median([p for p, rows in by_pt.items() for _ in rows])
        return max(pts, key=lambda p: (sum(r["w"] for r in by_pt[p]), -abs(p - med)))

    pt = _pick_point(spread_by_pt)
    if pt is not None and len(spread_by_pt[pt]) >= 2:
        rows = spread_by_pt[pt]
        p_home = _wmean([(r["w"], r["p"][0]) for r in rows])
        result["spread"] = {
            "home_line": pt,
            "p_home_cover": p_home,
            "p_away_cover": 1.0 - p_home,
            "price_home": _price_ref(rows, 0),
            "price_away": _price_ref(rows, 1),
            "n_books": len(rows),
        }

    # ── Total ─────────────────────────────────────────────────────────────
    pt = _pick_point(total_by_pt)
    if pt is not None and len(total_by_pt[pt]) >= 2:
        rows = total_by_pt[pt]
        p_over = _wmean([(r["w"], r["p"][0]) for r in rows])
        result["total"] = {
            "line": pt,
            "p_over": p_over,
            "p_under": 1.0 - p_over,
            "price_over": _price_ref(rows, 0),
            "price_under": _price_ref(rows, 1),
            "n_books": len(rows),
        }

    return result


def market_view(events: list, away_team: str, home_team: str):
    """
    Point d'entrée : retourne la vue marché orientée selon NOS équipes
    (away_team @ home_team), ou None si l'événement est introuvable ou si
    le moneyline n'a pas assez de bookmakers (< 2).

    {
      "ml":     {p_home, p_away, price_home, price_away, best_home, best_away,
                 n_books, pinnacle_p_home, disagreement},
      "spread": {home_line, p_home_cover, p_away_cover, price_home, price_away, n_books} | None,
      "total":  {line, p_over, p_under, price_over, price_under, n_books} | None,
      "event_id", "commence_time"
    }
    """
    event, swapped = find_event(events, away_team, home_team)
    if not event:
        return None

    raw = _market_view_raw(event)
    if not raw["ml"]:
        return None

    if swapped:   # notre domicile = leur visiteur
        ml = raw["ml"]
        ml = dict(ml, p_home=ml["p_away"], p_away=ml["p_home"],
                  price_home=ml["price_away"], price_away=ml["price_home"],
                  best_home=ml["best_away"], best_away=ml["best_home"],
                  pinnacle_p_home=(None if ml["pinnacle_p_home"] is None
                                   else 1.0 - ml["pinnacle_p_home"]))
        raw["ml"] = ml
        sp = raw["spread"]
        if sp:
            raw["spread"] = dict(sp, home_line=-sp["home_line"],
                                 p_home_cover=sp["p_away_cover"],
                                 p_away_cover=sp["p_home_cover"],
                                 price_home=sp["price_away"],
                                 price_away=sp["price_home"])

    raw["event_id"] = event.get("id")
    raw["commence_time"] = event.get("commence_time")
    return raw


def spread_price_for(view: dict, team_is_home: bool, point: float):
    """Cote de référence pour 'équipe à tel handicap' (ex: puck line ±1.5),
    seulement si cette ligne est la ligne de consensus du marché. Sinon None."""
    sp = (view or {}).get("spread")
    if not sp:
        return None
    if team_is_home and abs(sp["home_line"] - point) < 1e-9:
        return sp["price_home"]
    if (not team_is_home) and abs(-sp["home_line"] - point) < 1e-9:
        return sp["price_away"]
    return None
