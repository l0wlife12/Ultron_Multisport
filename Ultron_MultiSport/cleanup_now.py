#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nettoyage automatique - Suppression des sections ODDS inutilisees"""

import re
import sys

def cleanup():
    filepath = r"c:\Users\jeffc\OneDrive\PythonProjects\GitHub\ULTRON_MULTISPORT\Ultron_MultiSport\ultron_multisports_v6_0.py"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    before_size = len(content)
    print(f"[*] Fichier: {before_size:,} caractères")
    
    # Section 1: Supprimer TOUTES les sections ODDS (NEVER USED - appel d'API fourni les vraies cotes)
    print("[*] Suppression: Sections ODDS inutilisees...")
    
    # Pattern pour les sections de commentaires + dictionnaires ODDS
    patterns = [
        # Hockey
        r'\n# ═{71}\s*\n# HOCKEY ODDS.*?(?=\n# ═{71}\s*\n# BASEBALL|$)',
        # Baseball  
        r'\n# ═{71}\s*\n# BASEBALL ODDS.*?(?=\n# ═{71}\s*\n# BASKETBALL|$)',
        # Basketball
        r'\n# ═{71}\s*\n# BASKETBALL ODDS.*?(?=\n# ═{71}\s*\n# [A-Z]|$)',
    ]
    
    for pattern in patterns:
        for _ in range(5):  # Éviter les boucles infinies
            new_content = re.sub(pattern, '\n', content, flags=re.DOTALL)
            if len(new_content) == len(content):
                break
            content = new_content
            print(f"   - {len(new_content):,} caractères (after pattern)")
    
    # Nettoyer les multiples newlines
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    after_size = len(content)
    saved = before_size - after_size
    pct = (saved / before_size) * 100
    
    print(f"\n[✓] Nettoyage termine")
    print(f"    Avant: {before_size:,} caractères")
    print(f"    Après: {after_size:,} caractères")
    print(f"    Supprime: {saved:,} caractères ({pct:.1f}%)\n")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[✓] Fichier sauvegarde: {filepath}")
    return True

if __name__ == "__main__":
    try:
        cleanup()
        sys.exit(0)
    except Exception as e:
        print(f"[!] Erreur: {e}")
        sys.exit(1)
