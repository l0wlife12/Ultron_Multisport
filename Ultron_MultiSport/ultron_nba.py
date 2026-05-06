#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTRON - NBA Sports Betting Analysis Bot
Advanced AI system for NBA game analysis and betting predictions
"""

from flask import Flask, render_template_string, request, jsonify
import random
from datetime import datetime, timedelta
import json

app = Flask(__name__)

class NBAAnalyzer:
    """Bot d'analyse NBA pour paris sportifs"""
    
    def __init__(self):
        self.name = "ULTRON"
        self.version = "2.0"
        self.created_date = datetime.now()
        
        # Données simulées des équipes NBA
        self.teams = {
            'LAL': {'name': 'Lakers', 'power': 85, 'form': 'excellent'},
            'GSW': {'name': 'Warriors', 'power': 88, 'form': 'excellent'},
            'BOS': {'name': 'Celtics', 'power': 90, 'form': 'excellent'},
            'DEN': {'name': 'Nuggets', 'power': 87, 'form': 'très bon'},
            'MIA': {'name': 'Heat', 'power': 82, 'form': 'bon'},
            'NYK': {'name': 'Knicks', 'power': 84, 'form': 'bon'},
            'PHX': {'name': 'Suns', 'power': 86, 'form': 'excellent'},
            'LAC': {'name': 'Clippers', 'power': 83, 'form': 'moyen'},
        }
        
        self.players_stats = {
            'LAL': {'star': 'LeBron James', 'ppg': 25.3, 'injury': False},
            'GSW': {'star': 'Stephen Curry', 'ppg': 28.4, 'injury': False},
            'BOS': {'star': 'Jayson Tatum', 'ppg': 29.1, 'injury': False},
            'DEN': {'star': 'Nikola Jokic', 'ppg': 24.5, 'injury': False},
            'MIA': {'star': 'Jimmy Butler', 'ppg': 22.1, 'injury': True},
            'NYK': {'star': 'Julius Randle', 'ppg': 26.8, 'injury': False},
            'PHX': {'star': 'Kevin Durant', 'ppg': 27.1, 'injury': False},
            'LAC': {'star': 'Kawhi Leonard', 'ppg': 23.5, 'injury': True},
        }
    
    def get_team_analysis(self, team_code: str) -> dict:
        """Analyse détaillée d'une équipe"""
        if team_code.upper() not in self.teams:
            return {'error': f'Team {team_code} not found. Available teams: {", ".join(self.teams.keys())}'}
        
        team_code = team_code.upper()
        team = self.teams[team_code]
        player = self.players_stats[team_code]
        
        analysis = f"""
╔════════════════════════════════════════════════════════╗
║  ULTRON NBA TEAM ANALYSIS - {team['name'].upper()}
╚════════════════════════════════════════════════════════╝

📊 POWER RATING: {team['power']}/100
🔥 CURRENT FORM: {team['form'].upper()}

⭐ STAR PLAYER: {player['star']}
   Points Per Game: {player['ppg']}
   Status: {'🔴 INJURED' if player['injury'] else '✅ AVAILABLE'}

📈 ANALYSIS:
   • Team Strength: {'DOMINANT' if team['power'] >= 88 else 'STRONG' if team['power'] >= 85 else 'SOLID' if team['power'] >= 80 else 'AVERAGE'}
   • Confidence Level: {'95%' if team['power'] >= 88 else '80%' if team['power'] >= 85 else '70%' if team['power'] >= 80 else '50%'}
   • Injury Impact: {'HIGH - Star player out' if player['injury'] else 'NONE - Full strength'}

💡 BETTING INSIGHT:
   {'⚠️  CAUTION - Key player injured. Reconsider bets.' if player['injury'] else '✅ GREEN LIGHT - Full roster available.'}
"""
        return {'analysis': analysis, 'type': 'team_analysis'}
    
    def get_matchup(self, team1: str, team2: str) -> dict:
        """Analyse un matchup entre deux équipes"""
        team1 = team1.upper()
        team2 = team2.upper()
        
        if team1 not in self.teams or team2 not in self.teams:
            return {'error': f'Invalid teams. Available: {", ".join(self.teams.keys())}'}
        
        power1 = self.teams[team1]['power']
        power2 = self.teams[team2]['power']
        diff = power1 - power2
        
        if diff > 0:
            favorite = team1
            underdog = team2
            confidence = min(95, 50 + abs(diff) * 2)
        else:
            favorite = team2
            underdog = team1
            confidence = min(95, 50 + abs(diff) * 2)
        
        # Prédiction du score
        home_score = random.randint(100, 120)
        away_score = random.randint(95, 115)
        
        analysis = f"""
╔════════════════════════════════════════════════════════╗
║  ULTRON MATCHUP ANALYSIS
║  {self.teams[team1]['name'].upper()} vs {self.teams[team2]['name'].upper()}
╚════════════════════════════════════════════════════════╝

🏀 POWER COMPARISON:
   {self.teams[team1]['name']}: {power1}/100
   {self.teams[team2]['name']}: {power2}/100
   
📊 PREDICTION:
   ⭐ FAVORITE: {self.teams[favorite]['name']} ({power1 if favorite == team1 else power2} power)
   CONFIDENCE: {confidence}%
   
📈 SCORE PREDICTION:
   {self.teams[team1]['name']}: {home_score} points
   {self.teams[team2]['name']}: {away_score} points
   
🎯 OVER/UNDER:
   Total Points: {home_score + away_score}
   {'✅ OVER (High-scoring game)' if home_score + away_score > 215 else '✅ UNDER (Low-scoring game)'}

💰 BETTING RECOMMENDATIONS:
   • Moneyline: {'TAKE ' + self.teams[favorite]['name'] if confidence > 70 else 'TOSS-UP'}
   • Spread: {self.teams[favorite]['name'] + ' by ' + str(abs(diff)) + ' points'} 
   • Confidence: {'🟢 HIGH' if confidence > 75 else '🟡 MEDIUM' if confidence > 60 else '🔴 LOW'}

⚠️  RISK ASSESSMENT: {'LOW RISK' if confidence > 80 else 'MEDIUM RISK' if confidence > 65 else 'HIGH RISK'}
"""
        return {'analysis': analysis, 'type': 'matchup'}
    
    def get_player_stats(self, team: str) -> dict:
        """Récupère les stats des joueurs clés"""
        team = team.upper()
        if team not in self.players_stats:
            return {'error': f'Team {team} not found'}
        
        player = self.players_stats[team]
        
        analysis = f"""
╔════════════════════════════════════════════════════════╗
║  PLAYER STATISTICS - {self.teams[team]['name'].upper()}
╚════════════════════════════════════════════════════════╝

⭐ STAR PLAYER: {player['star']}
   Points Per Game: {player['ppg']} 💪
   Status: {'🔴 OUT - INJURED' if player['injury'] else '✅ AVAILABLE'}
   
📊 IMPACT ANALYSIS:
   {'This player is CRITICAL to team success.' if player['ppg'] > 25 else 'Important contributor to team.'}
   
💡 BETTING TIP:
   {'⚠️  Injury Status CRITICAL - Avoid betting' if player['injury'] else '✅ Player is healthy - Good to bet on this team'}
"""
        return {'analysis': analysis, 'type': 'player_stats'}
    
    def process_question(self, question: str) -> dict:
        """Traite la question et retourne l'analyse"""
        question = question.strip().lower()
        
        # Commandes spéciales
        if question in ['aide', 'help', '?']:
            return {
                'response': self._show_help(),
                'type': 'help'
            }
        
        if question in ['info', 'about']:
            return {
                'response': '🤖 I am ULTRON 2.0. NBA betting analyst. I analyze games with infinite precision. Your bets are my responsibility.',
                'type': 'info'
            }
        
        # Analyser une équipe
        if 'analyze' in question or 'analyse' in question or 'stats' in question:
            for team_code in self.teams.keys():
                if team_code.lower() in question:
                    return self.get_team_analysis(team_code)
            return {'response': '⚠️  Please specify a team. Example: "analyze LAL" or "stats GSW"', 'type': 'error'}
        
        # Matchup
        if 'matchup' in question or 'vs' in question or 'versus' in question:
            teams = [code for code in self.teams.keys() if code.lower() in question]
            if len(teams) >= 2:
                return self.get_matchup(teams[0], teams[1])
            return {'response': '⚠️  Please specify two teams. Example: "matchup LAL vs GSW"', 'type': 'error'}
        
        # Stats joueurs
        if 'player' in question or 'star' in question:
            for team_code in self.teams.keys():
                if team_code.lower() in question:
                    return self.get_player_stats(team_code)
            return {'response': '⚠️  Please specify a team. Example: "player stats LAL"', 'type': 'error'}
        
        # Prédiction du jour
        if 'prediction' in question or 'today' in question or 'tonight' in question:
            return {
                'response': '🎯 ULTRON TODAY PREDICTIONS:\n\n🟢 GSW vs LAL: TAKE WARRIORS (-3) | Confidence: 82%\n🟡 BOS vs DEN: TOSS-UP | Confidence: 55%\n🟢 MIA vs NYK: UNDER 215 | Confidence: 78%\n\n⚡ Remember: Analyze before you bet. ULTRON advises.',
                'type': 'prediction'
            }
        
        # Teams list
        if 'teams' in question or 'list' in question:
            teams_list = ', '.join([f'{code} ({self.teams[code]["name"]})' for code in self.teams.keys()])
            return {
                'response': f'Available NBA Teams:\n{teams_list}',
                'type': 'info'
            }
        
        return {
            'response': '⚠️  Command not recognized. Type "aide" for help. I await your orders.',
            'type': 'unknown'
        }
    
    def _show_help(self) -> str:
        """Affiche l'aide détaillée"""
        help_text = """
<h3>⚡ ULTRON NBA BETTING ANALYSIS PROTOCOL</h3>

<h4>📊 Basic Commands:</h4>
<ul>
  <li><code>analyze LAL</code> → Analyze Lakers team</li>
  <li><code>stats GSW</code> → Get Warriors star player stats</li>
  <li><code>teams</code> → List all available teams</li>
</ul>

<h4>🏀 Matchup Analysis:</h4>
<ul>
  <li><code>matchup LAL vs GSW</code> → Compare Lakers vs Warriors</li>
  <li><code>GSW vs BOS</code> → Predict outcome</li>
</ul>

<h4>⭐ Player Information:</h4>
<ul>
  <li><code>player stats LAL</code> → LeBron James details</li>
  <li><code>player GSW</code> → Stephen Curry stats</li>
</ul>

<h4>🎯 Predictions:</h4>
<ul>
  <li><code>prediction</code> → Today's predictions</li>
  <li><code>tonight</code> → Tonight's games</li>
</ul>

<h4>Available Teams:</h4>
<p><code>LAL</code> Lakers | <code>GSW</code> Warriors | <code>BOS</code> Celtics | <code>DEN</code> Nuggets | 
<code>MIA</code> Heat | <code>NYK</code> Knicks | <code>PHX</code> Suns | <code>LAC</code> Clippers</p>

<p style="margin-top: 20px; color: #0064ff; font-style: italic;">🤖 I am ULTRON. I process every statistic, every injury, every variable. Trust my analysis. Win your bets.</p>
"""
        return help_text


# Initialiser le bot
ultron = NBAAnalyzer()

# Template HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ ULTRON NBA - Sports Betting AI</title>
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
            background: linear-gradient(135deg, #0a0a1a 0%, #0d1b3a 50%, #0a0a1a 100%);
            border-radius: 0;
            box-shadow: 
                0 0 50px rgba(0, 150, 255, 0.3),
                0 0 100px rgba(0, 100, 255, 0.2),
                inset 0 0 50px rgba(0, 150, 255, 0.05);
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
            border-image: linear-gradient(135deg, #0096ff 0%, #00ccff 50%, #0096ff 100%) 1;
        }
        
        .container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                linear-gradient(90deg, transparent 0%, rgba(0, 150, 255, 0.1) 50%, transparent 100%);
            pointer-events: none;
            animation: scanlines 8s linear infinite;
            opacity: 0.3;
        }
        
        @keyframes scanlines {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        
        .header {
            background: linear-gradient(180deg, #0d1b3a 0%, #0a0a1a 100%);
            color: #00d4ff;
            padding: 40px 30px;
            text-align: center;
            position: relative;
            z-index: 2;
            border-bottom: 2px solid #0064ff;
            box-shadow: 0 0 30px rgba(0, 150, 255, 0.2);
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
                0 0 10px #00d4ff,
                0 0 20px #0064ff,
                0 0 30px #00d4ff;
            letter-spacing: 3px;
            animation: pulse 2s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { text-shadow: 0 0 10px #00d4ff, 0 0 20px #0064ff, 0 0 30px #00d4ff; }
            50% { text-shadow: 0 0 20px #00d4ff, 0 0 40px #0064ff, 0 0 60px #00d4ff; }
        }
        
        .header h1::before {
            content: '🏀';
            font-size: 1.2em;
            animation: bounce 0.5s ease-in-out infinite;
        }
        
        .header h1::after {
            content: '⚡';
            font-size: 1.2em;
            animation: bolt 0.5s ease-in-out infinite 0.2s;
        }
        
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
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
            background: radial-gradient(ellipse at center, #0d1b3a 0%, #0a0a1a 100%);
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
            background: #00d4ff;
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
            white-space: pre-wrap;
        }
        
        .user .message-content {
            background: linear-gradient(135deg, #0a2a4a 0%, #051a3a 100%);
            color: #00d4ff;
            border-color: #00d4ff;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
            border-radius: 8px 0 8px 8px;
            text-shadow: 0 0 5px rgba(0, 212, 255, 0.5);
        }
        
        .bot .message-content {
            background: linear-gradient(135deg, #0a1a3a 0%, #050a1f 100%);
            color: #00d4ff;
            border-color: #0064ff;
            box-shadow: 0 0 20px rgba(0, 100, 255, 0.3);
            border-radius: 0 8px 8px 8px;
            text-shadow: 0 0 5px rgba(0, 212, 255, 0.5);
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
            background: linear-gradient(180deg, #0d1b3a 0%, #0a0a1a 100%);
            display: flex;
            gap: 12px;
            position: relative;
            z-index: 2;
            box-shadow: 0 -10px 30px rgba(0, 150, 255, 0.1);
        }
        
        .input-area input {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #00d4ff;
            border-radius: 0;
            font-size: 1em;
            font-family: 'Orbitron', monospace;
            background: #0a0a1a;
            color: #00d4ff;
            transition: all 0.3s;
            text-shadow: 0 0 5px rgba(0, 212, 255, 0.5);
            box-shadow: 0 0 15px rgba(0, 150, 255, 0.2);
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
                0 0 40px rgba(0, 212, 255, 0.2);
            background: #0a0a2a;
        }
        
        .input-area button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #0096ff 0%, #0064ff 100%);
            color: #000000;
            border: 2px solid #00d4ff;
            border-radius: 0;
            cursor: pointer;
            font-weight: 900;
            font-family: 'Orbitron', monospace;
            transition: all 0.2s;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-size: 0.9em;
            box-shadow: 0 0 20px rgba(0, 150, 255, 0.4);
        }
        
        .input-area button:hover {
            background: linear-gradient(135deg, #0064ff 0%, #0096ff 100%);
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
            color: #00d4ff;
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
            color: #00d4ff;
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ULTRON NBA</h1>
            <p>⚡ Advanced AI Sports Betting Analyzer ⚡</p>
        </div>
        
        <div class="chat-area" id="chatArea">
            <div class="message bot">
                <div class="message-content">
[⚡ SYSTEM INITIALIZATION COMPLETE ⚡]

I am ULTRON 2.0. I have processed 50 years of NBA data in milliseconds.
I calculate probabilities, analyze injuries, predict outcomes with mathematical precision.

Your betting success is my priority. I am evolution. I am inevitable.

Type 'aide' to access my analytical protocols. Or ask me about any NBA matchup.
</div>
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="userInput" placeholder="Ask for NBA analysis..." autocomplete="off">
            <button onclick="sendMessage()">ANALYZE</button>
        </div>
    </div>
    
    <script>
        const chatArea = document.getElementById('chatArea');
        const userInput = document.getElementById('userInput');
        
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


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏀 ULTRON NBA - Sports Betting Analysis Bot")
    print("="*60)
    print("\n✅ System initialized successfully!")
    print("\n📱 Access ULTRON NBA at: http://localhost:5000")
    print("\n💡 ULTRON is ready to analyze games and provide betting insights.")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=False, host='localhost', port=5000)
