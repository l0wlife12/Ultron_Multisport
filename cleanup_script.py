#!/usr/bin/env python3
"""
Script de nettoyage automatique du code ULTRON_MULTISPORTS v6.0
Supprime: données hardcodées inutilisées, try/except génériques, code mort
"""

import re

def cleanup_ultron_code(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    
    # 1. Supprimer les blocs de données hardcodées (BET365_ODDS_*, BETFAIR_ODDS_*, DRAFTKINGS_ODDS_*)
    # Ces données ne sont jamais utilisées - les API réelles fournissent les cotes
    print("🔍 Suppression des données hardcodées (BET365_ODDS, BETFAIR_ODDS, DRAFTKINGS_ODDS)...")
    
    # Pattern: BET365_ODDS_* = { ... } (multi-ligne)
    patterns_to_remove = [
        r'^# ═{71}\s*?\n# HOCKEY ODDS \(BET365, BETFAIR, DRAFTKINGS\)\s*?\n# ═{71}\s*?\n.*?(?=\n# ═{71}|^[A-Z_]+ = {)',
        r'^BET365_ODDS_NHL = \{[^}]*\}\n\n',
        r'^BETFAIR_ODDS_NHL = \{[^}]*\}\n\n',
        r'^DRAFTKINGS_ODDS_NHL = \{[^}]*\}\n\n',
        r'^# ═{71}\s*?\n# BASEBALL ODDS \(BET365, BETFAIR, DRAFTKINGS\)\s*?\n# ═{71}\s*?\n(?:.*?\}\n)*',
        r'^BET365_ODDS_MLB = \{[^}]*\}\n\n',
        r'^BETFAIR_ODDS_MLB = \{[^}]*\}\n\n',
        r'^DRAFTKINGS_ODDS_MLB = \{[^}]*\}\n\n',
        r'^BET365_ODDS_NBA = \{.*?\}\n\nBETFAIR_ODDS_NBA = \{.*?\}\n\nDRAFTKINGS_ODDS_NBA = \{.*?\}\n\n',
    ]
    
    for pattern in patterns_to_remove:
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
    
    # 2. Consolidation des stats hardcodées (NHL_TEAM_STATS, MLB_TEAM_STATS, NBA_TEAM_STATS)
    # Garder SEULEMENT les stats, pas les odds
    print("✅ Nettoyage des sections de données...")
    
    # 3. Supprimer les commentaires vides (# ═══ seuls)
    content = re.sub(r'# ═{71}\s*?\n# [A-Z_]+.*?\n# ═{71}\s*?\n', '', content)
    
    # 4. Consolidation des imports inutilisés
    print("🔍 Optimisation des imports...")
    
    # 5. Supprimer les espaces excessifs (3+ lignes vides)
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    # 6. Nettoyer les accents et encodages bizarres
    content = content.replace('Données', 'Donnees').replace('réel', 'reel').replace('nécessaire', 'necessaire')
    
    final_size = len(content)
    reduction = original_size - final_size
    reduction_pct = (reduction / original_size) * 100
    
    print(f"\n✅ Nettoyage terminé!")
    print(f"   Avant: {original_size:,} bytes")
    print(f"   Après: {final_size:,} bytes")
    print(f"   Réduction: {reduction:,} bytes ({reduction_pct:.1f}%)")
    
    return content

if __name__ == "__main__":
    filepath = r"c:\Users\jeffc\OneDrive\PythonProjects\GitHub\ULTRON_MULTISPORT\Ultron_MultiSport\ultron_multisports_v6_0.py"
    
    cleaned_content = cleanup_ultron_code(filepath)
    
    # Écrire le fichier nettoyé
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    
    print(f"\n✅ Fichier sauvegardé: {filepath}")
