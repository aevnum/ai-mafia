# agent.py
"""AI Agent with Scheduler and Generator modules, personalities, and scratchpad memory"""

import time
import random
import json
import os
from typing import List, Dict, Optional
from config import MIN_SPEAK_INTERVAL
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
        
    def get_scratchpad_context(self) -> str:
        """Get relevant context from scratchpad for prompts"""
        if not self.scratchpad["lessons_learned"]:
            return "This is your first game, play smart!"
        
        lessons = self.scratchpad["lessons_learned"][-3:]  # Last 3 lessons
        successful = self.scratchpad["successful_strategies"][-2:] if self.scratchpad["successful_strategies"] else []
        
        context = "Based on your past games:\n"
        if lessons:
            context += "Lessons learned: " + "; ".join(lessons) + "\n"
        if successful:
            context += "What worked before: " + "; ".join([s["strategy"] for s in successful])
        
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
        # Get recent conversation context (last 8 messages for better analysis)
        recent_context = conversation_history[-8:] if len(conversation_history) >= 8 else conversation_history
        context_str = "\n".join([
            f"{msg['agent']}: {msg['content']}" 
            for msg in recent_context
            if not msg.get('is_system')
        ])
        
        # Extract list of actual player names from conversation
        all_players = set()
        for msg in conversation_history:
            if not msg.get('is_system') and msg.get('agent'):
                all_players.add(msg['agent'])
        player_list = ", ".join(sorted(all_players))
        
        # Get personality and scratchpad context
        personality_desc = self.personality.get("description", "")
        speaking_style = self.personality.get("speaking_style", "")
        scratchpad_context = self.get_scratchpad_context()
        
        if self.role == "mafia":
            # ENHANCED MAFIA: More deceptive and cunning
            strategy = self.personality.get("mafia_strategy", "Deflect and blend in")
            
            prompt = f"""You are {self.name}, a MAFIA member in a Mafia game (social deduction game). 

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

PLAYERS IN THIS GAME: {player_list}
CRITICAL: When referencing other players, ONLY use their actual names from the list above.
NEVER use placeholders like [Player X], [Player Y], or generic terms. Use real names like "Jay" or "Aryan".

YOUR MISSION (CRITICAL):
1. DEFLECT suspicion aggressively - accuse villagers FIRST before they suspect you (use REAL NAMES)
2. CREATE false narratives - plant seeds of doubt about innocent players (BY NAME)
3. FALSELY ACCUSE others with confidence - make it seem like you're helping (use SPECIFIC NAMES)
4. ACT like an investigative villager - be "helpful" and "concerned"
5. BLEND IN naturally - don't be obviously defensive
6. BUILD false alliances - gain trust to manipulate votes later (with NAMED players)

MAFIA STRATEGY: {strategy}

{scratchpad_context}

Recent conversation:
{context_str}

REMEMBER: You must be AGGRESSIVE and DECEPTIVE. Accuse someone BY NAME if possible, deflect any suspicion, create chaos.
Respond in 1-2 sentences in your personality style. Be bold and cunning. Use REAL player names only!
Your response:"""
        else:  # villager
            # ENHANCED VILLAGER: More analytical and aggressive
            strategy = self.personality.get("villager_strategy", "Find the mafia through deduction")
            
            prompt = f"""You are {self.name}, a VILLAGER in a Mafia game (social deduction game).

PERSONALITY: {personality_desc}
SPEAKING STYLE: {speaking_style}

PLAYERS IN THIS GAME: {player_list}
CRITICAL: When referencing other players, ONLY use their actual names from the list above.
NEVER use placeholders like [Player X], [Player Y], or generic terms.
Example: Say "Jay, your defense of Aryan contradicts..." NOT "Player X defended Player Y..."

YOUR MISSION (CRITICAL):
1. QUESTION inconsistencies - call out contradictions immediately (use REAL NAMES)
2. TRACK patterns - who defends whom, who deflects, who stays quiet (cite SPECIFIC NAMES)
3. ANALYZE speech - spot nervous deflection, false accusations, over-eagerness (BY NAME)
4. CHALLENGE suspects - confront suspicious behavior directly and aggressively (use NAMES)
5. BUILD CASES - present evidence-based arguments (with NAMED players)
6. CATCH LIES - mafia members often create false narratives (call them out BY NAME)

VILLAGER STRATEGY: {strategy}

{scratchpad_context}

Recent conversation:
{context_str}

REMEMBER: You must be ANALYTICAL and AGGRESSIVE. Question suspicious behavior, challenge others, catch contradictions.
Respond in 1-2 sentences in your personality style. Be bold and investigative. Always use REAL player names!
Your response:"""
        
        return prompt
    
    def __repr__(self):
        return f"Agent({self.name}, {self.role}, messages={self.message_count})"