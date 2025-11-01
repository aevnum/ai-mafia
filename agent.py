# agent.py
"""AI Agent with Scheduler and Generator modules, personalities, and scratchpad memory"""

import time
import random
import json
import os
from typing import List, Dict, Optional
from config import MIN_SPEAK_INTERVAL, SUSPICIOUS_BEHAVIORS, CONVERSATION_CONTEXT_SIZE
from personalities import get_personality


class Agent:
    """
    AI Agent with two-part brain:
    - Scheduler: Decides WHEN to speak
    - Generator: Decides WHAT to say
    Plus: Personality system and persistent scratchpad memory
    """
    
    def __init__(self, agent_id: int, name: str, role: str):
        self.id = agent_id
        self.name = name
        self.role = role  # "villager" or "mafia"
        self.is_typing = False
        self.last_speak_time = 0
        self.message_count = 0
        self.suspicion_level = 0  # Track how suspicious this agent seems
        
        # Personality system
        self.personality = get_personality(name)
        
        # Scratchpad system
        self.scratchpad_path = os.path.join("scratchpads", f"{name.lower()}_scratchpad.json")
        self.scratchpad = self.load_scratchpad()
        self.current_game_observations = []  # Observations from current game
        
    def load_scratchpad(self) -> dict:
        """Load agent's persistent scratchpad from JSON file"""
        if os.path.exists(self.scratchpad_path):
            try:
                with open(self.scratchpad_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading scratchpad for {self.name}: {e}")
        
        # Initialize new scratchpad
        return {
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "times_as_mafia": 0,
            "times_as_villager": 0,
            "successful_strategies": [],
            "failed_strategies": [],
            "lessons_learned": [],
            "behavior_notes": ""
        }
    
    def save_scratchpad(self):
        """Save agent's scratchpad to JSON file"""
        try:
            os.makedirs("scratchpads", exist_ok=True)
            with open(self.scratchpad_path, 'w') as f:
                json.dump(self.scratchpad, f, indent=2)
        except Exception as e:
            print(f"Error saving scratchpad for {self.name}: {e}")
    
    def update_strategy(self, won: bool, role_was: str, strategy_used: str, what_learned: str):
        """Update scratchpad after a game ends"""
        self.scratchpad["games_played"] += 1
        
        if won:
            self.scratchpad["games_won"] += 1
            self.scratchpad["successful_strategies"].append({
                "role": role_was,
                "strategy": strategy_used,
                "learned": what_learned
            })
        else:
            self.scratchpad["games_lost"] += 1
            self.scratchpad["failed_strategies"].append({
                "role": role_was,
                "strategy": strategy_used,
                "learned": what_learned
            })
        
        if role_was == "mafia":
            self.scratchpad["times_as_mafia"] += 1
        else:
            self.scratchpad["times_as_villager"] += 1
        
        self.scratchpad["lessons_learned"].append(what_learned)
        
        # Keep only last 10 lessons to avoid bloat
        if len(self.scratchpad["lessons_learned"]) > 10:
            self.scratchpad["lessons_learned"] = self.scratchpad["lessons_learned"][-10:]
        
        self.save_scratchpad()
    
    def add_observation(self, observation: str):
        """Add an observation during the current game"""
        self.current_game_observations.append({
            "time": time.time(),
            "observation": observation
        })
    
    def formulate_game_strategy(self) -> str:
        """
        At game start, agent reviews their scratchpad and formulates a strategy.
        This makes each agent's behavior unique based on their history.
        """
        scratchpad_review = self.get_scratchpad_context()
        personality_traits = ", ".join(self.personality.get("traits", []))
        
        if self.role == "mafia":
            strategy_prompt = f"""You are {self.name}, a MAFIA member starting a new Mafia game.

YOUR PERSONALITY: {personality_traits}
{self.personality.get("description", "")}

{scratchpad_review}

Based on your personality and past experience, what's your strategy for THIS game as mafia?
How will you deceive, deflect, and manipulate to win?
Be specific about what worked/failed for you before.

Respond in 2-3 sentences describing your game plan:"""
        else:
            strategy_prompt = f"""You are {self.name}, a VILLAGER starting a new Mafia game.

YOUR PERSONALITY: {personality_traits}
{self.personality.get("description", "")}

{scratchpad_review}

Based on your personality and past experience, what's your strategy for THIS game as villager?
How will you identify mafia through analysis and questioning?
Be specific about what worked/failed for you before.

Respond in 2-3 sentences describing your game plan:"""
        
        # This strategy is internalized by the agent (not shared publicly)
        # but influences their behavior throughout the game
        return strategy_prompt  # Returns the prompt for potential future use
    
        
    def get_scratchpad_context(self) -> str:
        """Get relevant context from scratchpad for prompts - UNIQUE PER AGENT"""
        if not self.scratchpad["lessons_learned"]:
            return "This is your first game. Play smart and learn from every interaction!"
        
        # Get personalized learning based on role experience
        lessons = self.scratchpad["lessons_learned"][-3:]  # Last 3 lessons
        
        # Get role-specific successful strategies
        if self.role == "mafia":
            successful = [s for s in self.scratchpad["successful_strategies"] if s["role"] == "mafia"][-2:]
            failed = [f for f in self.scratchpad["failed_strategies"] if f["role"] == "mafia"][-2:]
        else:
            successful = [s for s in self.scratchpad["successful_strategies"] if s["role"] == "villager"][-2:]
            failed = [f for f in self.scratchpad["failed_strategies"] if f["role"] == "villager"][-2:]
        
        # Build unique context based on THIS agent's history
        context = f"YOUR PAST EXPERIENCE ({self.scratchpad['games_played']} games, {self.scratchpad['games_won']} wins):\n"
        
        if lessons:
            context += "What you've learned: " + "; ".join(lessons) + "\n"
        
        if successful:
            context += "Strategies that worked for YOU as " + self.role.upper() + ": "
            context += "; ".join([s["strategy"] for s in successful]) + "\n"
        
        if failed:
            context += "What FAILED for you as " + self.role.upper() + ": "
            context += "; ".join([f["strategy"] for f in failed]) + "\n"
            context += "AVOID repeating these mistakes!\n"
        
        # Add role-specific stats
        if self.role == "mafia":
            mafia_winrate = (self.scratchpad["games_won"] / self.scratchpad["games_played"] * 100) if self.scratchpad["games_played"] > 0 else 0
            context += f"Your mafia win rate: {mafia_winrate:.0f}% ({self.scratchpad['times_as_mafia']} games as mafia)\n"
        else:
            villager_winrate = (self.scratchpad["games_won"] / self.scratchpad["games_played"] * 100) if self.scratchpad["games_played"] > 0 else 0
            context += f"Your villager win rate: {villager_winrate:.0f}% ({self.scratchpad['times_as_villager']} games as villager)\n"
        
        return context
        
    def scheduler(self, conversation_history: List[Dict]) -> bool:
        """
        Decides WHETHER to speak based on conversation flow.
        ENHANCED: More aggressive speaking patterns
        Returns True if agent should speak, False otherwise.
        """
        # Check if enough time has passed since last message
        time_since_last = time.time() - self.last_speak_time
        if time_since_last < MIN_SPEAK_INTERVAL:
            return False
        
        # Get recent messages (last 5 for better context)
        recent_messages = conversation_history[-5:] if len(conversation_history) >= 5 else conversation_history
        
        # Check if agent was mentioned or accused
        mentioned = any(
            self.name.lower() in msg.get('content', '').lower() 
            for msg in recent_messages
        )
        
        # Check for accusations or suspicious words in recent messages
        accusatory_keywords = ['suspicious', 'mafia', 'lying', 'trust', 'sus', 'doubt', 'defend', 'accuse']
        recent_accusations = any(
            any(keyword in msg.get('content', '').lower() for keyword in accusatory_keywords)
            for msg in recent_messages
        )
        
        # ENHANCED: More aggressive base probability (increased from 0.3 to 0.5)
        base_probability = 0.5
        
        # Strongly increase probability if mentioned
        if mentioned:
            base_probability += 0.5  # Increased from 0.4
        
        # Increase if accusations are flying (jump into the fray)
        if recent_accusations:
            base_probability += 0.3
        
        # Mafia agents are VERY talkative to deflect suspicion
        if self.role == "mafia":
            base_probability += 0.25  # Increased from 0.2
            
        # Personality affects speaking frequency
        if "aggressive" in self.personality.get("traits", []):
            base_probability += 0.2
        elif "cautious" in self.personality.get("traits", []):
            base_probability -= 0.1
        elif "unpredictable" in self.personality.get("traits", []):
            base_probability += random.uniform(-0.2, 0.3)
        
        # Reduce probability slightly if agent dominates conversation
        if self.message_count > 0 and len(conversation_history) > 0:
            message_ratio = self.message_count / len(conversation_history)
            if message_ratio > 0.3:  # Speaking more than 30% of the time
                base_probability -= 0.1
        
        # Cap probability at 0.95 to maintain some unpredictability
        base_probability = min(0.95, base_probability)
        
        should_speak = random.random() < base_probability
        
        return should_speak
    
    def create_prompt(self, conversation_history: List[Dict]) -> str:
        """
        Creates the prompt for the generator based on role and context.
        """
        # Get recent conversation context using CONVERSATION_CONTEXT_SIZE from config
        recent_context = conversation_history[-CONVERSATION_CONTEXT_SIZE:] if len(conversation_history) >= CONVERSATION_CONTEXT_SIZE else conversation_history
        
        # Count non-system messages to detect if we're at the start
        non_system_messages = [msg for msg in conversation_history if not msg.get('is_system')]
        is_game_start = len(non_system_messages) < 3  # First 3 messages are introductions
        
        context_str = "\n".join([
            f"{msg['agent']}: {msg['content']}" 
            for msg in recent_context
            if not msg.get('is_system')
        ])
        
        # Extract list of ACTIVE player names (not eliminated) and eliminated players
        all_players = set()
        for msg in conversation_history:
            if not msg.get('is_system') and msg.get('agent'):
                all_players.add(msg['agent'])
        
        # Get eliminated players from game state (passed through conversation)
        eliminated_players = set()
        for msg in conversation_history:
            if msg.get('is_system') and 'has been eliminated' in msg.get('content', ''):
                # Extract eliminated player name from message
                content = msg['content']
                if '❌' in content:
                    name_part = content.split('❌')[1].split('has been eliminated')[0].strip()
                    eliminated_players.add(name_part)
        
        active_players = all_players - eliminated_players
        active_player_list = ", ".join(sorted(active_players))
        eliminated_player_list = ", ".join(sorted(eliminated_players)) if eliminated_players else "None yet"
        
        # Get personality and scratchpad context
        personality_desc = self.personality.get("description", "")
        speaking_style = self.personality.get("speaking_style", "")
        scratchpad_context = self.get_scratchpad_context()
        
        if self.role == "mafia":
            # ENHANCED MAFIA: More deceptive and cunning
            strategy = self.personality.get("mafia_strategy", "Deflect and blend in")
            
            # GAME START: Give dramatic introduction instead of accusations
            if is_game_start:
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game (social deduction game). 

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

This is the START of the game. The opening hint was cryptic. Players are nervous.

Give a DRAMATIC INTRODUCTORY statement that:
1. Sets your tone/personality
2. Responds to the ominous opening hint
3. Establishes yourself as "helpful" or "concerned" (but you're secretly mafia)
4. NO accusations yet - there's no conversation to analyze
5. Maybe a quip, observation, or dramatic flair

CRITICAL: Speak in FIRST PERSON only. Use "I", "me", "my", never "he/she/they" about yourself.

Examples:
- "Well, that's an unsettling way to start. I suppose I'll be watching closely."
- "Interesting hint. I'm going to make sure we find the truth here."
- "So we're already playing mind games? I'm ready for this."

Respond in 1-2 sentences with personality. Be dramatic but NOT accusatory yet. FIRST PERSON ONLY.
Your response:"""
            else:
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game (social deduction game). 

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

ACTIVE PLAYERS: {active_player_list}
ELIMINATED PLAYERS: {eliminated_player_list}

CRITICAL: When referencing players, ONLY use names from the ACTIVE PLAYERS list above.
You can mention eliminated players in PAST TENSE only (e.g., "Navya was suspicious before being eliminated").
NEVER use placeholders like [Player X], [Player Y], or generic terms. Use real names like "Jay" or "Aryan".

CRITICAL: Speak in FIRST PERSON ONLY. Use "I", "me", "my" when talking about yourself.
Example: "I think Jay is suspicious" NOT "Aryan thinks Jay is suspicious"
Example: "I've been watching the remaining players" NOT "He has been watching"

YOUR MISSION (CRITICAL):
1. DEFLECT suspicion aggressively - accuse ACTIVE villagers FIRST (use REAL NAMES from active list)
2. CREATE false narratives - plant seeds of doubt about innocent ACTIVE players (BY NAME)
3. FALSELY ACCUSE others with confidence - make it seem like you're helping (use SPECIFIC NAMES)
4. ACT like an investigative villager - be "helpful" and "concerned"
5. BLEND IN naturally - don't be obviously defensive
6. BUILD false alliances - gain trust to manipulate votes later (with ACTIVE NAMED players)
7. VARY your vocabulary and phrasing - don't repeat the same phrases

MAFIA STRATEGY: {strategy}

{scratchpad_context}

Recent conversation:
{context_str}

REMEMBER: You must be AGGRESSIVE and DECEPTIVE. Accuse ACTIVE players BY NAME, deflect suspicion, create chaos.
VARY your language - use different words and sentence structures each time.
Respond in 1-2 sentences in your personality style. FIRST PERSON ONLY. Use REAL player names from ACTIVE list!
Your response:"""
        else:  # villager
            # ENHANCED VILLAGER: More analytical and aggressive WITH ALIGNMENT DETECTION
            strategy = self.personality.get("villager_strategy", "Find the mafia through deduction")
            
            # Get suspicious behaviors list
            behaviors_to_watch = ", ".join(SUSPICIOUS_BEHAVIORS[:5])  # First 5 behaviors
            
            # GAME START: Give dramatic introduction instead of accusations
            if is_game_start:
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game (social deduction game).

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

This is the START of the game. The opening hint was cryptic. You need to find the mafia.

Give a DRAMATIC INTRODUCTORY statement that:
1. Sets your tone/personality
2. Responds to the ominous opening hint
3. Shows your investigative mindset
4. NO accusations yet - there's no conversation to analyze
5. Maybe a quip, observation, or dramatic declaration of intent

CRITICAL: Speak in FIRST PERSON only. Use "I", "me", "my", never "he/she/they" about yourself.

Examples:
- "That hint is troubling. I'll be watching everyone's reactions carefully."
- "Interesting start. I'm going to figure out who's hiding something here."
- "The game begins. I trust no one until they prove themselves to me."

Respond in 1-2 sentences with personality. Be dramatic but NOT accusatory yet. FIRST PERSON ONLY.
Your response:"""
            else:
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game (social deduction game).

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

ACTIVE PLAYERS: {active_player_list}
ELIMINATED PLAYERS: {eliminated_player_list}

CRITICAL: When referencing players, ONLY use names from the ACTIVE PLAYERS list above.
You can mention eliminated players in PAST TENSE only (e.g., "Navya was acting suspicious before elimination").
NEVER use placeholders like [Player X], [Player Y], or generic terms.
Example: Say "Jay, your defense contradicts..." NOT "Player X defended Player Y..."

CRITICAL: Speak in FIRST PERSON ONLY. Use "I", "me", "my" when talking about yourself.
Example: "I think Jay is lying" NOT "Laavanya thinks Jay is lying"
Example: "I noticed something suspicious" NOT "She noticed the silence"

YOUR MISSION (CRITICAL):
1. QUESTION inconsistencies - call out contradictions in ACTIVE players immediately (use REAL NAMES)
2. TRACK patterns - who defends whom, who deflects among ACTIVE players (cite SPECIFIC NAMES)
3. ANALYZE speech - spot nervous deflection, false accusations in ACTIVE players (BY NAME)
4. CHALLENGE suspects - confront suspicious behavior in ACTIVE players directly (use NAMES)
5. BUILD CASES - present evidence-based arguments (with ACTIVE NAMED players)
6. CATCH LIES - mafia members create false narratives (call them out BY NAME from active list)
7. VARY your vocabulary and phrasing - use different expressions each time

LOOK FOR THESE MISALIGNMENT SIGNS (CRITICAL):
- Who contradicts themselves between messages?
- Who asks questions but never answers direct questions?
- Who interrupts investigative threads or changes topics?
- Who jumps to accuse others without evidence?
- Who stays silent during critical moments?
- Synchronized speech patterns between certain players?
- Who defends others aggressively without reason?

SUSPICIOUS BEHAVIORS TO WATCH: {behaviors_to_watch}

VILLAGER STRATEGY: {strategy}

{scratchpad_context}

Recent conversation:
{context_str}

REMEMBER: You must be ANALYTICAL and AGGRESSIVE. Question ACTIVE players, challenge others, catch contradictions.
Look for misalignment patterns in ACTIVE players - mafia often slip up or coordinate suspiciously.
VARY your language - don't repeat the same phrases. Use different words and structures each time.
Respond in 1-2 sentences in your personality style. FIRST PERSON ONLY. Always use REAL names from ACTIVE list!
Your response:"""
        
        return prompt
    
    def __repr__(self):
        return f"Agent({self.name}, {self.role}, messages={self.message_count})"