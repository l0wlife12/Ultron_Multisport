#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Bot Mathématique Intelligent
Bot conversationnel pour résoudre vos problèmes mathématiques personnalisés
"""

import math
import re
from datetime import datetime
from typing import Union, List, Tuple, Dict, Any


class UltronMathBot:
    """Bot mathématique intelligent nommé Ultron"""
    
    def __init__(self):
        self.name = "ULTRON"
        self.version = "1.0"
        self.created_date = datetime.now()
        self.conversation_history = []
        self.math_operations = {
            'add': lambda a, b: a + b,
            'subtract': lambda a, b: a - b,
            'multiply': lambda a, b: a * b,
            'divide': lambda a, b: a / b if b != 0 else "Erreur: Division par zéro",
            'power': lambda a, b: a ** b,
            'sqrt': lambda a: math.sqrt(a) if a >= 0 else "Erreur: Racine d'un nombre négatif",
            'log': lambda a: math.log(a) if a > 0 else "Erreur: Log d'un nombre négatif ou zéro",
            'sin': lambda a: math.sin(math.radians(a)),
            'cos': lambda a: math.cos(math.radians(a)),
            'tan': lambda a: math.tan(math.radians(a)),
        }
    
    def greet(self):
        """Message de bienvenue d'Ultron"""
        greeting = f"""
╔════════════════════════════════════════════════════════════════╗
║                    🤖 BIENVENUE DANS ULTRON 🤖                ║
║                  Bot Mathématique Intelligent                  ║
║                                                                ║
║  Je suis ULTRON, votre assistant mathématique personnel.      ║
║  Je peux résoudre pratiquement tous vos problèmes de math!    ║
╚════════════════════════════════════════════════════════════════╝

📚 FONCTIONNALITÉS DISPONIBLES:
  ✓ Opérations de base (+, -, ×, ÷)
  ✓ Puissances et racines carrées
  ✓ Trigonométrie (sin, cos, tan)
  ✓ Logarithmes
  ✓ Résolution d'équations linéaires
  ✓ Calcul de factorielles
  ✓ Calculs statistiques
  ✓ Calcul de distances et aires
  ✓ Conversion d'unités
  ✓ Et bien plus encore!

💡 EXEMPLES DE COMMANDES:
  • "2 + 3"
  • "résous x + 5 = 12"
  • "sin 45"
  • "racine carré 16"
  • "5!"
  • "moyenne 2 5 8 10"
  • "aide" - Afficher l'aide complète
  • "quitter" - Arrêter le bot

Tapez votre question ou votre calcul ci-dessous:
"""
        return greeting
    
    def parse_basic_math(self, expression: str) -> Union[float, str]:
        """Parse et évalue les expressions mathématiques basiques"""
        try:
            # Remplacer les opérateurs français par des opérateurs Python
            expression = expression.replace('×', '*').replace('÷', '/')
            expression = expression.replace('puissance', '**').replace('^', '**')
            
            # Évaluer l'expression
            result = eval(expression, {
                "__builtins__": {},
                "sqrt": math.sqrt,
                "sin": lambda x: math.sin(math.radians(x)),
                "cos": lambda x: math.cos(math.radians(x)),
                "tan": lambda x: math.tan(math.radians(x)),
                "log": math.log,
                "log10": math.log10,
                "pi": math.pi,
                "e": math.e
            })
            
            return round(result, 10)
        except Exception as e:
            return f"❌ Erreur dans l'expression: {str(e)}"
    
    def solve_linear_equation(self, equation: str) -> Union[float, str]:
        """Résout une équation linéaire du type ax + b = c"""
        try:
            # Format: "résous x + 5 = 12"
            equation = equation.lower().replace('résous', '').strip()
            
            if '=' not in equation:
                return "❌ Veuillez utiliser le format: résous 2x + 3 = 11"
            
            left, right = equation.split('=')
            left = left.strip()
            right = right.strip()
            
            # Extraire le coefficient et la constante de gauche
            # Format simplifié: ax + b
            match = re.match(r'([+-]?\d*\.?\d*)\s*\*?\s*x\s*([+-]\s*\d+\.?\d*)?', left)
            
            if not match:
                return "❌ Format non reconnu. Utilisez: 2x + 3 = 11"
            
            a = float(match.group(1) or 1)
            b = float(match.group(2).replace(' ', '') if match.group(2) else 0)
            c = float(right)
            
            if a == 0:
                return "❌ Erreur: Le coefficient de x ne peut pas être 0"
            
            x = (c - b) / a
            return round(x, 10)
        
        except Exception as e:
            return f"❌ Erreur: {str(e)}"
    
    def factorial(self, n: int) -> Union[int, str]:
        """Calcule la factorielle"""
        try:
            n = int(n)
            if n < 0:
                return "❌ La factorielle n'existe pas pour les nombres négatifs"
            return math.factorial(n)
        except:
            return "❌ Veuillez entrer un nombre entier"
    
    def calculate_mean(self, numbers: List[float]) -> float:
        """Calcule la moyenne"""
        return sum(numbers) / len(numbers) if numbers else 0
    
    def calculate_median(self, numbers: List[float]) -> float:
        """Calcule la médiane"""
        sorted_nums = sorted(numbers)
        n = len(sorted_nums)
        if n % 2 == 0:
            return (sorted_nums[n//2 - 1] + sorted_nums[n//2]) / 2
        return sorted_nums[n//2]
    
    def calculate_std_dev(self, numbers: List[float]) -> float:
        """Calcule l'écart-type"""
        mean = self.calculate_mean(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return math.sqrt(variance)
    
    def convert_units(self, value: float, from_unit: str, to_unit: str) -> Union[float, str]:
        """Convertit entre différentes unités"""
        conversions = {
            ('km', 'm'): 1000,
            ('m', 'cm'): 100,
            ('cm', 'mm'): 10,
            ('kg', 'g'): 1000,
            ('h', 'min'): 60,
            ('min', 's'): 60,
        }
        
        key = (from_unit.lower(), to_unit.lower())
        reverse_key = (to_unit.lower(), from_unit.lower())
        
        if key in conversions:
            return value * conversions[key]
        elif reverse_key in conversions:
            return value / conversions[reverse_key]
        else:
            return "❌ Conversion non disponible"
    
    def process_question(self, question: str) -> str:
        """Traite la question et retourne la réponse"""
        question = question.strip().lower()
        self.conversation_history.append(question)
        
        # Commandes spéciales
        if question in ['aide', 'help', '?']:
            return self._show_help()
        
        if question in ['quitter', 'exit', 'quit', 'bye']:
            return "👋 Au revoir! Merci d'avoir utilisé ULTRON!"
        
        if question in ['info', 'about']:
            return f"🤖 Je suis ULTRON v{self.version}, créé pour vous aider en mathématiques!"
        
        # Résoudre une équation linéaire
        if 'résous' in question or 'solve' in question:
            result = self.solve_linear_equation(question)
            return f"✅ x = {result}"
        
        # Factorielle
        if '!' in question:
            match = re.search(r'(\d+)\s*!', question)
            if match:
                n = int(match.group(1))
                result = self.factorial(n)
                return f"✅ {n}! = {result}"
        
        # Statistiques
        if 'moyenne' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                mean = self.calculate_mean(numbers)
                return f"✅ Moyenne = {round(mean, 2)}"
        
        if 'médiane' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                median = self.calculate_median(numbers)
                return f"✅ Médiane = {round(median, 2)}"
        
        if 'écart-type' in question or 'ecart' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                std = self.calculate_std_dev(numbers)
                return f"✅ Écart-type = {round(std, 2)}"
        
        # Conversions d'unités
        if 'convertir' in question or 'conversion' in question:
            # Format: convertir 100 km en m
            match = re.search(r'convertir\s+(\d+\.?\d*)\s+(\w+)\s+en\s+(\w+)', question)
            if match:
                value, from_unit, to_unit = float(match.group(1)), match.group(2), match.group(3)
                result = self.convert_units(value, from_unit, to_unit)
                return f"✅ {value} {from_unit} = {result} {to_unit}"
        
        # Racine carrée
        if 'racine' in question or 'sqrt' in question:
            match = re.search(r'racine\s+(?:carré\s+)?(\d+\.?\d*)', question)
            if match:
                num = float(match.group(1))
                result = math.sqrt(num) if num >= 0 else "Erreur"
                return f"✅ √{num} = {round(result, 2)}"
        
        # Trigonométrie
        if any(func in question for func in ['sin', 'cos', 'tan']):
            if 'sin' in question:
                match = re.search(r'sin\s+(\d+\.?\d*)', question)
                if match:
                    angle = float(match.group(1))
                    result = math.sin(math.radians(angle))
                    return f"✅ sin({angle}°) = {round(result, 4)}"
            
            if 'cos' in question:
                match = re.search(r'cos\s+(\d+\.?\d*)', question)
                if match:
                    angle = float(match.group(1))
                    result = math.cos(math.radians(angle))
                    return f"✅ cos({angle}°) = {round(result, 4)}"
            
            if 'tan' in question:
                match = re.search(r'tan\s+(\d+\.?\d*)', question)
                if match:
                    angle = float(match.group(1))
                    result = math.tan(math.radians(angle))
                    return f"✅ tan({angle}°) = {round(result, 4)}"
        
        # Expressions mathématiques générales
        # Vérifie s'il y a des opérateurs mathématiques
        if any(op in question for op in ['+', '-', '*', '/', '**', '^', 'sqrt']):
            result = self.parse_basic_math(question)
            if isinstance(result, (int, float)):
                return f"✅ Résultat = {result}"
            return result
        
        # Question non reconnue
        return "❓ Je n'ai pas compris la question. Tapez 'aide' pour voir les commandes disponibles."
    
    def _show_help(self) -> str:
        """Affiche l'aide détaillée"""
        help_text = """
╔════════════════════════════════════════════════════════════════╗
║                       📖 AIDE ULTRON 📖                        ║
╚════════════════════════════════════════════════════════════════╝

🔢 OPÉRATIONS MATHÉMATIQUES:
  • "5 + 3"          → Addition
  • "10 - 2"         → Soustraction
  • "4 * 6"          → Multiplication
  • "20 / 5"         → Division
  • "2 ^ 3" ou "2 ** 3"  → Puissance
  • "racine carré 25" → Racine carrée

📐 TRIGONOMÉTRIE (en degrés):
  • "sin 45"         → Sinus de 45°
  • "cos 60"         → Cosinus de 60°
  • "tan 30"         → Tangente de 30°

🔀 ÉQUATIONS LINÉAIRES:
  • "résous x + 5 = 12"
  • "résous 2x - 3 = 7"

📊 STATISTIQUES (tapez les nombres séparés par des espaces):
  • "moyenne 2 5 8 10"
  • "médiane 1 3 5 7 9"
  • "écart-type 2 4 6 8"

🔄 CONVERSIONS D'UNITÉS:
  • "convertir 5 km en m"
  • "convertir 100 cm en mm"
  • "convertir 2 kg en g"

❗ AUTRES:
  • "5!"             → Factorielle (5 × 4 × 3 × 2 × 1 = 120)
  • "aide"           → Afficher cette aide
  • "quitter"        → Arrêter le bot

💡 CONSTANTES DISPONIBLES:
  • pi (π)           → 3.14159...
  • e                → 2.71828...
"""
        return help_text
    
    def run(self):
        """Boucle principale du bot"""
        print(self.greet())
        
        while True:
            try:
                user_input = input("\n👤 Vous: ").strip()
                
                if not user_input:
                    continue
                
                response = self.process_question(user_input)
                print(f"\n🤖 ULTRON: {response}")
                
                if user_input.lower() in ['quitter', 'exit', 'quit', 'bye']:
                    break
            
            except KeyboardInterrupt:
                print("\n\n👋 ULTRON s'arrête... Au revoir!")
                break
            except Exception as e:
                print(f"\n❌ Erreur inattendue: {str(e)}")


def main():
    """Fonction principale"""
    ultron = UltronMathBot()
    ultron.run()


if __name__ == "__main__":
    main()
