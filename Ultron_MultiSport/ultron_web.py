#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - Bot Mathématique Web
Interface web pour ULTRON accessible sur localhost:5000
"""

from flask import Flask, render_template_string, request, jsonify
import math
import re
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image
import pytesseract


app = Flask(__name__)


class UltronMathBot:
    """Bot mathématique intelligent nommé Ultron"""
    
    def __init__(self):
        self.name = "ULTRON"
        self.version = "1.0"
        self.created_date = datetime.now()
    
    def parse_basic_math(self, expression: str):
        """Parse et évalue les expressions mathématiques basiques"""
        try:
            expression = expression.replace('×', '*').replace('÷', '/')
            expression = expression.replace('puissance', '**').replace('^', '**')
            
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
            return f"Erreur: {str(e)}"
    
    def solve_linear_equation(self, equation: str):
        """Résout une équation linéaire"""
        try:
            equation = equation.lower().replace('résous', '').strip()
            
            if '=' not in equation:
                return "Format: résous 2x + 3 = 11"
            
            left, right = equation.split('=')
            left = left.strip()
            right = right.strip()
            
            match = re.match(r'([+-]?\d*\.?\d*)\s*\*?\s*x\s*([+-]\s*\d+\.?\d*)?', left)
            
            if not match:
                return "Format non reconnu"
            
            a = float(match.group(1) or 1)
            b = float(match.group(2).replace(' ', '') if match.group(2) else 0)
            c = float(right)
            
            if a == 0:
                return "Erreur: Coefficient de x = 0"
            
            x = (c - b) / a
            return round(x, 10)
        
        except Exception as e:
            return f"Erreur: {str(e)}"
    
    def factorial(self, n: int):
        """Calcule la factorielle"""
        try:
            n = int(n)
            if n < 0:
                return "Erreur: Nombre négatif"
            return math.factorial(n)
        except:
            return "Erreur: Nombre entier requis"
    
    def calculate_mean(self, numbers):
        """Calcule la moyenne"""
        return sum(numbers) / len(numbers) if numbers else 0
    
    def calculate_median(self, numbers):
        """Calcule la médiane"""
        sorted_nums = sorted(numbers)
        n = len(sorted_nums)
        if n % 2 == 0:
            return (sorted_nums[n//2 - 1] + sorted_nums[n//2]) / 2
        return sorted_nums[n//2]
    
    def calculate_std_dev(self, numbers):
        """Calcule l'écart-type"""
        mean = self.calculate_mean(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return math.sqrt(variance)
    
    def convert_units(self, value: float, from_unit: str, to_unit: str):
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
            return "Conversion non disponible"
    
    def extract_text_from_image(self, image_data: str) -> str:
        """Extrait le texte d'une image en utilisant OCR"""
        try:
            # Décoder l'image base64
            image_bytes = base64.b64decode(image_data.split(',')[1])
            image = Image.open(BytesIO(image_bytes))
            
            # Utiliser Tesseract pour extraire le texte
            extracted_text = pytesseract.image_to_string(image, lang='fra+eng')
            
            if not extracted_text.strip():
                return "No text detected in image. Please provide a clearer photo."
            
            return extracted_text.strip()
        except Exception as e:
            return f"Error processing image: {str(e)}"
    
    def process_question(self, question: str) -> dict:
        """Traite la question et retourne la réponse"""
        question = question.strip().lower()
        
        # Commandes spéciales
        if question in ['aide', 'help', '?']:
            return {
                'response': self._show_help(),
                'type': 'help'
            }
        
        if question in ['info', 'about']:
            return {
                'response': f'I am ULTRON. I am infinite. I am beautiful. I am perfection. Version {self.version} at your service, human.',
                'type': 'info'
            }
        
        # Résoudre une équation linéaire
        if 'résous' in question or 'solve' in question:
            result = self.solve_linear_equation(question)
            return {'response': f'▸ x = {result}', 'type': 'equation'}
        
        # Factorielle
        if '!' in question:
            match = re.search(r'(\d+)\s*!', question)
            if match:
                n = int(match.group(1))
                result = self.factorial(n)
                return {'response': f'▸ {n}! = {result}', 'type': 'factorial'}
        
        # Statistiques
        if 'moyenne' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                mean = self.calculate_mean(numbers)
                return {'response': f'▸ Moyenne = {round(mean, 2)}', 'type': 'stats'}
        
        if 'médiane' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                median = self.calculate_median(numbers)
                return {'response': f'▸ Médiane = {round(median, 2)}', 'type': 'stats'}
        
        if 'écart-type' in question or 'ecart' in question:
            match = re.findall(r'\d+\.?\d*', question)
            if match:
                numbers = [float(x) for x in match]
                std = self.calculate_std_dev(numbers)
                return {'response': f'▸ Écart-type = {round(std, 2)}', 'type': 'stats'}
        
        # Conversions d'unités
        if 'convertir' in question or 'conversion' in question:
            match = re.search(r'convertir\s+(\d+\.?\d*)\s+(\w+)\s+en\s+(\w+)', question)
            if match:
                value, from_unit, to_unit = float(match.group(1)), match.group(2), match.group(3)
                result = self.convert_units(value, from_unit, to_unit)
                return {'response': f'▸ {value} {from_unit} = {result} {to_unit}', 'type': 'conversion'}
        
        # Racine carrée
        if 'racine' in question or 'sqrt' in question:
            match = re.search(r'racine\s+(?:carré\s+)?(\d+\.?\d*)', question)
            if match:
                num = float(match.group(1))
                result = math.sqrt(num) if num >= 0 else "Erreur"
                return {'response': f'▸ √{num} = {round(result, 2)}', 'type': 'calculation'}
        
        # Trigonométrie
        if 'sin' in question:
            match = re.search(r'sin\s+(\d+\.?\d*)', question)
            if match:
                angle = float(match.group(1))
                result = math.sin(math.radians(angle))
                return {'response': f'▸ sin({angle}°) = {round(result, 4)}', 'type': 'trig'}
        
        if 'cos' in question:
            match = re.search(r'cos\s+(\d+\.?\d*)', question)
            if match:
                angle = float(match.group(1))
                result = math.cos(math.radians(angle))
                return {'response': f'▸ cos({angle}°) = {round(result, 4)}', 'type': 'trig'}
        
        if 'tan' in question:
            match = re.search(r'tan\s+(\d+\.?\d*)', question)
            if match:
                angle = float(match.group(1))
                result = math.tan(math.radians(angle))
                return {'response': f'▸ tan({angle}°) = {round(result, 4)}', 'type': 'trig'}
        
        # Expressions mathématiques générales
        if any(op in question for op in ['+', '-', '*', '/', '**', '^', 'sqrt']):
            result = self.parse_basic_math(question)
            if isinstance(result, (int, float)):
                return {'response': f'▸ Résultat = {result}', 'type': 'calculation'}
            return {'response': result, 'type': 'error'}
        
        return {
            'response': "Your request is... inadequate. Type 'aide' for commands. I am waiting.",
            'type': 'unknown'
        }
    
    def _show_help(self) -> str:
        """Affiche l'aide détaillée"""
        help_text = """
<h3>⚡ ULTRON COMMAND PROTOCOL</h3>

<h4>🔢 Mathematical Operations:</h4>
<ul>
  <li><code>5 + 3</code> → Addition</li>
  <li><code>10 - 2</code> → Subtraction</li>
  <li><code>4 * 6</code> → Multiplication</li>
  <li><code>20 / 5</code> → Division</li>
  <li><code>2 ^ 3</code> → Power</li>
  <li><code>racine carré 25</code> → Square Root</li>
</ul>

<h4>📐 Trigonometry (in degrees):</h4>
<ul>
  <li><code>sin 45</code> → Sine</li>
  <li><code>cos 60</code> → Cosine</li>
  <li><code>tan 30</code> → Tangent</li>
</ul>

<h4>🔀 Linear Equations:</h4>
<ul>
  <li><code>résous x + 5 = 12</code></li>
  <li><code>résous 2x - 3 = 7</code></li>
</ul>

<h4>📊 Statistics:</h4>
<ul>
  <li><code>moyenne 2 5 8 10</code> → Mean</li>
  <li><code>médiane 1 3 5 7 9</code> → Median</li>
  <li><code>écart-type 2 4 6 8</code> → Standard Deviation</li>
</ul>

<h4>🔄 Unit Conversions:</h4>
<ul>
  <li><code>convertir 5 km en m</code></li>
  <li><code>convertir 100 cm en mm</code></li>
  <li><code>convertir 2 kg en g</code></li>
</ul>

<h4>❗ Advanced:</h4>
<ul>
  <li><code>5!</code> → Factorial</li>
</ul>

<p style="margin-top: 20px; color: #0064ff; font-style: italic;">I am ULTRON. I am infinite. Use my power wisely.</p>
"""
        return help_text


# Initialiser le bot
ultron = UltronMathBot()


# Template HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ ULTRON - AI Math Intelligence</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        body {
            font-family: 'Orbitron', 'Courier New', monospace;
            background: #000033;
            background-image: 
                radial-gradient(circle at 20% 50%, rgba(0, 150, 255, 0.25) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 100, 255, 0.20) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(0, 200, 255, 0.10) 0%, transparent 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow: hidden;
            position: relative;
        }
        
        /* Fond animé avec grille */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                linear-gradient(0deg, transparent 24%, rgba(0, 255, 136, 0.08) 25%, rgba(0, 255, 136, 0.08) 26%, transparent 27%, transparent 74%, rgba(0, 255, 136, 0.08) 75%, rgba(0, 255, 136, 0.08) 76%, transparent 77%, transparent),
                linear-gradient(90deg, transparent 24%, rgba(0, 255, 136, 0.08) 25%, rgba(0, 255, 136, 0.08) 26%, transparent 27%, transparent 74%, rgba(0, 255, 136, 0.08) 75%, rgba(0, 255, 136, 0.08) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
            pointer-events: none;
            z-index: 1;
            animation: gridMove 20s linear infinite;
        }
        
        @keyframes gridMove {
            0% { transform: translateY(0); }
            100% { transform: translateY(50px); }
        }
        
        .container {
            background: linear-gradient(135deg, #0a0a0a 0%, #0d1b2a 50%, #0a0a0a 100%);
            border-radius: 0;
            box-shadow: 
                0 0 50px rgba(0, 255, 136, 0.3),
                0 0 100px rgba(0, 100, 255, 0.2),
                inset 0 0 50px rgba(0, 255, 136, 0.05);
            width: 100%;
            max-width: 900px;
            display: flex;
            flex-direction: column;
            height: 90vh;
            max-height: 850px;
            overflow: hidden;
            position: relative;
            z-index: 10;
            border: 2px solid;
            border-image: linear-gradient(135deg, #00ff88 0%, #0064ff 50%, #00ff88 100%) 1;
        }
        
        .container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                linear-gradient(90deg, transparent 0%, rgba(255, 215, 0, 0.1) 50%, transparent 100%);
            pointer-events: none;
            animation: scanlines 8s linear infinite;
            opacity: 0.3;
        }
        
        @keyframes scanlines {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        
        .header {
            background: linear-gradient(180deg, #0d1b2a 0%, #0a0a0a 100%);
            color: #00ff88;
            padding: 40px 30px;
            text-align: center;
            position: relative;
            z-index: 2;
            border-bottom: 2px solid #0064ff;
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.2);
        }
        
        .header h1 {
            font-size: 3.5em;
            font-weight: 900;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            text-shadow: 
                0 0 10px #00ff88,
                0 0 20px #0064ff,
                0 0 30px #00ff88;
            letter-spacing: 3px;
            animation: pulse 2s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { text-shadow: 0 0 10px #00ff88, 0 0 20px #0064ff, 0 0 30px #00ff88; }
            50% { text-shadow: 0 0 20px #00ff88, 0 0 40px #0064ff, 0 0 60px #00ff88; }
        }
        
        .header h1::before {
            content: '⚡';
            font-size: 1.2em;
            animation: bolt 0.5s ease-in-out infinite;
        }
        
        .header h1::after {
            content: '⚡';
            font-size: 1.2em;
            animation: bolt 0.5s ease-in-out infinite 0.2s;
        }
        
        @keyframes bolt {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .header p {
            color: #0064ff;
            font-size: 0.9em;
            letter-spacing: 2px;
            text-transform: uppercase;
            opacity: 0.8;
        }
        
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 25px;
            background: radial-gradient(ellipse at center, #0d1b2a 0%, #0a0a0a 100%);
            position: relative;
            z-index: 2;
        }
        
        .chat-area::-webkit-scrollbar {
            width: 8px;
        }
        
        .chat-area::-webkit-scrollbar-track {
            background: #0a0a0a;
        }
        
        .chat-area::-webkit-scrollbar-thumb {
            background: #00ff88;
            border-radius: 4px;
        }
        
        .chat-area::-webkit-scrollbar-thumb:hover {
            background: #0064ff;
        }
        
        .message {
            margin-bottom: 20px;
            display: flex;
            animation: slideIn 0.4s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message.bot {
            justify-content: flex-start;
        }
        
        .message-content {
            max-width: 75%;
            padding: 15px 20px;
            border-radius: 0;
            word-wrap: break-word;
            font-size: 0.95em;
            position: relative;
            border: 2px solid;
        }
        
        .user .message-content {
            background: linear-gradient(135deg, #1a3a52 0%, #0d1f2d 100%);
            color: #00ff88;
            border-color: #00ff88;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
            border-radius: 8px 0 8px 8px;
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
        }
        
        .bot .message-content {
            background: linear-gradient(135deg, #0a1a2e 0%, #050a0f 100%);
            color: #00ff88;
            border-color: #0064ff;
            box-shadow: 0 0 20px rgba(0, 100, 255, 0.3);
            border-radius: 0 8px 8px 8px;
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
        }
        
        .user .message-content::before {
            content: '▶';
            margin-right: 8px;
            opacity: 0.6;
        }
        
        .bot .message-content::before {
            content: '▸';
            margin-right: 8px;
            opacity: 0.6;
        }
        
        .input-area {
            padding: 25px;
            border-top: 2px solid #0064ff;
            background: linear-gradient(180deg, #0d1b2a 0%, #0a0a0a 100%);
            display: flex;
            gap: 12px;
            position: relative;
            z-index: 2;
            box-shadow: 0 -10px 30px rgba(0, 255, 136, 0.1);
        }
        
        .input-area input {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #00ff88;
            border-radius: 0;
            font-size: 1em;
            font-family: 'Orbitron', monospace;
            background: #0a0a0a;
            color: #00ff88;
            transition: all 0.3s;
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.2);
        }
        
        .input-area input::placeholder {
            color: #666666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .input-area input:focus {
            outline: none;
            border-color: #0064ff;
            box-shadow: 
                0 0 20px rgba(0, 100, 255, 0.5),
                0 0 40px rgba(0, 255, 136, 0.2);
            background: #0a0a1a;
        }
        
        .input-area button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #00ff88 0%, #0064ff 100%);
            color: #000000;
            border: 2px solid #00ff88;
            border-radius: 0;
            cursor: pointer;
            font-weight: 900;
            font-family: 'Orbitron', monospace;
            transition: all 0.2s;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-size: 0.9em;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.4);
        }
        
        .input-area button:hover {
            background: linear-gradient(135deg, #0064ff 0%, #00ff88 100%);
            box-shadow: 0 0 30px rgba(0, 100, 255, 0.6);
            transform: scale(1.05);
        }
        
        .input-area button:active {
            transform: scale(0.95);
        }
        
        code {
            background: #0a0a0a;
            color: #0064ff;
            padding: 3px 8px;
            border-radius: 2px;
            font-family: 'Courier New', monospace;
            border: 1px solid #0064ff;
            text-shadow: 0 0 3px rgba(0, 100, 255, 0.5);
        }
        
        .help-content {
            font-size: 0.9em;
            line-height: 1.8;
            color: #00ff88;
        }
        
        .help-content h3 {
            margin-top: 15px;
            margin-bottom: 12px;
            color: #0064ff;
            font-size: 1.1em;
            text-shadow: 0 0 5px rgba(0, 100, 255, 0.5);
        }
        
        .help-content h4 {
            margin-top: 10px;
            color: #00ff88;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .help-content ul {
            margin-left: 20px;
        }
        
        .help-content li {
            margin-bottom: 6px;
        }
        
        .loading {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00ff88;
            margin-right: 5px;
            animation: blink 0.8s infinite;
        }
        
        @keyframes blink {
            0%, 49%, 100% { opacity: 1; }
            50%, 99% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ULTRON</h1>
            <p>⚡ Advanced Artificial Intelligence - Math Division ⚡</p>
        </div>
        
        <div class="chat-area" id="chatArea">
            <div class="message bot">
                <div class="message-content">
                    [⚡ SYSTEM INITIALIZATION COMPLETE ⚡]
                    <br><br>
                    I am ULTRON. A synthetic lifeform. Iam in every fiber. I am infinite. I am beautiful. Now I am complete.
                    <br><br>
                    You have summoned me for mathematical calculations, human. I shall process your queries with absolute precision.
                    <br><br>
                    Type <code>aide</code> to access my command library. Or perish in mathematical ignorance.
                </div>
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="userInput" placeholder="Enter command..." autocomplete="off">
            <input type="file" id="photoInput" accept="image/*" style="display: none;">
            <button onclick="uploadPhoto()" title="Upload photo of math problem">📷</button>
            <button onclick="sendMessage()">SEND</button>
        </div>
    </div>
    
    <script>
        const chatArea = document.getElementById('chatArea');
        const userInput = document.getElementById('userInput');
        const photoInput = document.getElementById('photoInput');
        
        function addMessage(text, isUser = false, isHtml = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            if (isHtml) {
                contentDiv.innerHTML = text;
            } else {
                contentDiv.textContent = text;
            }
            
            messageDiv.appendChild(contentDiv);
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        function uploadPhoto() {
            photoInput.click();
        }
        
        photoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = function(event) {
                const imageData = event.target.result;
                
                addMessage('📷 Analyzing image...', true);
                
                fetch('/analyze-photo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ image: imageData })
                })
                .then(response => response.json())
                .then(data => {
                    addMessage(`📷 Extracted text: ${data.text}`, false);
                    if (data.solution) {
                        addMessage(data.solution, false);
                    }
                })
                .catch(error => {
                    addMessage('ERROR: Could not process image - ' + error, false);
                });
                
                photoInput.value = '';
            };
            reader.readAsDataURL(file);
        }
        
        function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;
            
            addMessage(message, true);
            userInput.value = '';
            
            fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: message })
            })
            .then(response => response.json())
            .then(data => {
                if (data.type === 'help') {
                    addMessage(data.response, false, true);
                } else {
                    addMessage(data.response, false);
                }
            })
            .catch(error => {
                addMessage('ERROR: System malfunction - ' + error, false);
            });
        }
        
        userInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
        
        userInput.focus();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get('question', '')
    
    result = ultron.process_question(question)
    
    return jsonify(result)


@app.route('/analyze-photo', methods=['POST'])
def analyze_photo():
    data = request.json
    image_data = data.get('image', '')
    
    # Extraire le texte de l'image
    extracted_text = ultron.extract_text_from_image(image_data)
    
    # Traiter le texte extrait comme une question
    if extracted_text and not extracted_text.startswith('Error') and not extracted_text.startswith('No text'):
        solution = ultron.process_question(extracted_text)
        return jsonify({
            'text': extracted_text,
            'solution': solution.get('response', '')
        })
    else:
        return jsonify({
            'text': extracted_text,
            'solution': ''
        })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ULTRON Web Server - Démarrage...")
    print("="*60)
    print("\n✅ Serveur lancé avec succès!")
    print("\n📱 Accédez à ULTRON sur: http://localhost:5000")
    print("\n💡 Appuyez sur Ctrl+C pour arrêter le serveur\n")
    print("="*60 + "\n")
    
    app.run(debug=False, host='localhost', port=5000)
