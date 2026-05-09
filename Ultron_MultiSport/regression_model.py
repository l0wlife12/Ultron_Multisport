#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression Model — regression_model.py

Détecte les équipes en anomalie de performance et prédit
le retour à la moyenne.

C'est l'un des edges les plus exploitables car le public
sur-réagit aux séries (hot/cold streaks).

Intégration avec ultron_picks.py :
    from regression_model import calculate_regression_signal, apply_regression_to_pick

    regression = calculate_regression_signal(espn_game, analysis)
    analysis   = apply_regression_to_pick(analysis, regression, bankroll)
"""

from ultron_picks import _compute_ev


def calculate_regression_signal(espn_game: dict,
                                 analysis: dict) -> dict:
    """
    Détecte les équipes en anomalie de performance
    et prédit le retour à la moyenne.

    C'est l'un des edges les plus exploitables
    car le public sur-réagit aux séries.
    """

    home_form   = espn_game.get('home_form', 0.5)
    away_form   = espn_game.get('away_form', 0.5)
    home_winpct = espn_game.get('home_win_pct', 0.5)
    away_winpct = espn_game.get('away_win_pct', 0.5)

    signals = []

    # ── Signal 1 : Série chaude VS moyenne saison ──
    # Équipe en série chaude mais win% moyen
    # → public la survalore → valeur sur l'adversaire
    home_overperforming = (
        home_form > 0.70          # 7+ victoires sur 10
        and home_winpct < 0.52    # mais win% saison moyen
    )
    away_overperforming = (
        away_form > 0.70
        and away_winpct < 0.52
    )

    if home_overperforming:
        signals.append({
            'type':      'HOT_STREAK_REGRESSION',
            'team':      espn_game['home_team'],
            'signal':    'CONTRE',
            'strength':  'FORT',
            'reasoning': (
                f"{espn_game['home_team']} en série chaude "
                f"({home_form:.0%} last 10) mais win% "
                f"saison faible ({home_winpct:.0%}). "
                f"Régression probable — valeur sur "
                f"{espn_game['away_team']}"
            )
        })

    if away_overperforming:
        signals.append({
            'type':      'HOT_STREAK_REGRESSION',
            'team':      espn_game['away_team'],
            'signal':    'CONTRE',
            'strength':  'FORT',
            'reasoning': (
                f"{espn_game['away_team']} en série chaude "
                f"({away_form:.0%} last 10) mais win% "
                f"saison faible ({away_winpct:.0%}). "
                f"Régression probable"
            )
        })

    # ── Signal 2 : Série froide VS bonne équipe ──
    # Bonne équipe en mauvaise passe
    # → public la sous-value → valeur sur elle
    home_underperforming = (
        home_form < 0.30          # 3 victoires ou moins sur 10
        and home_winpct > 0.55    # mais vraiment bonne équipe
    )
    away_underperforming = (
        away_form < 0.30
        and away_winpct > 0.55
    )

    if home_underperforming:
        signals.append({
            'type':      'COLD_STREAK_BOUNCE',
            'team':      espn_game['home_team'],
            'signal':    'POUR',
            'strength':  'FORT',
            'reasoning': (
                f"{espn_game['home_team']} en mauvaise passe "
                f"({home_form:.0%} last 10) mais solide "
                f"en saison ({home_winpct:.0%}). "
                f"Rebond probable — valeur sur eux"
            )
        })

    if away_underperforming:
        signals.append({
            'type':      'COLD_STREAK_BOUNCE',
            'team':      espn_game['away_team'],
            'signal':    'POUR',
            'strength':  'FORT',
            'reasoning': (
                f"{espn_game['away_team']} en mauvaise passe "
                f"({away_form:.0%} last 10) mais solide "
                f"({away_winpct:.0%}). Rebond attendu"
            )
        })

    # ── Signal 3 : Situation de revanche ──
    # Impact psychologique — souvent sous-estimé
    home_streak = espn_game.get('home_streak', 0)
    away_streak = espn_game.get('away_streak', 0)  # noqa: F841 — disponible pour extensions futures

    if home_streak <= -4:
        signals.append({
            'type':      'DESPERATION_BOUNCE',
            'team':      espn_game['home_team'],
            'signal':    'POUR',
            'strength':  'MODÉRÉ',
            'reasoning': (
                f"{espn_game['home_team']} sur une série "
                f"de {abs(home_streak)} défaites — "
                f"équipe dos au mur à domicile"
            )
        })

    # ── Score global de régression ──
    regression_score = 0
    for s in signals:
        regression_score += (
            3 if s['strength'] == 'FORT' else 1
        )

    return {
        'signals':          signals,
        'has_signal':       len(signals) > 0,
        'regression_score': regression_score,
        'best_signal':      signals[0] if signals else None,
    }


def apply_regression_to_pick(analysis: dict,
                               regression: dict,
                               bankroll: float) -> dict:
    """
    Intègre le signal de régression dans le pick final.
    Peut renverser le pick favori si signal fort.

    Note: `analysis` suit la structure de ultron_picks.analyze_game()
          → clé 'fav_team' (et non 'favorite').
    """
    if not regression.get('has_signal'):
        return analysis

    best = regression['best_signal']

    # Si le signal de régression va à l'encontre du favori
    # → augmente la confiance sur l'underdog
    if (best['signal'] == 'CONTRE'
            and best['team'] == analysis['fav_team']
            and regression['regression_score'] >= 3):

        # Ajuste vers l'underdog
        analysis['regression_alert']    = True
        analysis['regression_reasoning'] = best['reasoning']

        # Réduit la prob du favori
        analysis['fav_prob'] = round(
            analysis['fav_prob'] - 0.05, 4
        )
        analysis['dog_prob'] = round(
            1 - analysis['fav_prob'], 4
        )

        # Recalcule EV underdog avec la nouvelle probabilité
        analysis['dog_ev'] = _compute_ev(
            analysis['dog_prob'],
            analysis['best_dog_odds']['odds']
        )

    # Si signal confirme le favori → boost confiance
    elif (best['signal'] == 'POUR'
              and best['team'] == analysis['fav_team']
              and regression['regression_score'] >= 3):

        analysis['confidence'] = min(
            analysis['confidence'] + 10, 100
        )
        analysis['regression_confirms'] = True
        analysis['regression_reasoning'] = best['reasoning']

    return analysis
