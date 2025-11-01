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

    def _get_personality_rules(self) -> str:
        """Get specific rules for this personality"""
        traits = self.personality.get('traits', [])
        rules = {
            'aggressive': "- Be direct and confrontational\n- Make strong accusations\n- Use forceful language",
            'analytical': "- Cite specific evidence (quote exact words)\n- Build logical arguments\n- Track patterns methodically",
            'cautious': "- Speak less often\n- Only speak when you have strong evidence\n- Defend yourself carefully",
            'charismatic': "- Build alliances naturally\n- Use persuasive language\n- Rally people to your side"
        }
        return "\n".join([rules.get(trait, "") for trait in traits if trait in rules])
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
        """Smarter decision about when to speak"""
        # Time check
        time_since_last = time.time() - self.last_speak_time
        if time_since_last < MIN_SPEAK_INTERVAL:
            return False
        
        recent_messages = conversation_history[-10:]
        
        # ✅ NEW: Speak if directly mentioned
        mentioned = any(self.name.lower() in msg.get('content', '').lower() 
                       for msg in recent_messages)
        if mentioned:
            return True  # Always respond when called out
        
        # ✅ NEW: Speak if someone just made a strong accusation
        strong_accusation = any(
            any(word in msg.get('content', '').lower() 
                for word in ['mafia', 'lying', 'vote for', 'suspect'])
            for msg in recent_messages[-3:]
        )
        
        # ✅ NEW: Don't spam - if you spoke in last 3 messages, be quieter
        recent_speakers = [msg.get('agent') for msg in recent_messages[-3:] 
                           if not msg.get('is_system')]
        spoke_recently = recent_speakers.count(self.name) >= 2
        
        if spoke_recently:
            base_probability = 0.2  # Much quieter
        elif strong_accusation:
            base_probability = 0.6  # Jump in when things heat up
        else:
            base_probability = 0.35
        
        # Personality adjustments
        if "aggressive" in self.personality.get("traits", []):
            base_probability += 0.15
        elif "cautious" in self.personality.get("traits", []):
            base_probability -= 0.1
        
        # Mafia slightly more active to deflect
        if self.role == "mafia":
            base_probability += 0.1
        
        return random.random() < base_probability
    

    def create_prompt(self, conversation_history: List[Dict], vote_history: List[Dict] = None, context_reset_index: int = 0) -> str:
        """Creates structured prompt requiring evidence-based reasoning (NO example analysis text)"""

        # ✅ NEW: Only use conversation AFTER the last voting round
        if context_reset_index > 0:
            # Get only post-voting context
            relevant_context = [msg for msg in conversation_history[context_reset_index:] 
                               if not msg.get('is_system') or 'ROUND SUMMARY' in msg.get('content', '')]
            # Also grab the round summary
            round_summary = None
            for msg in conversation_history[max(0, context_reset_index-5):context_reset_index+5]:
                if msg.get('is_system') and 'ROUND SUMMARY' in msg.get('content', ''):
                    round_summary = msg['content']
                    break
        else:
            # First round - use recent context
            relevant_context = conversation_history[-CONVERSATION_CONTEXT_SIZE:]
            round_summary = None
        context_str = self._format_conversation(relevant_context)
        vote_summary = self._format_vote_history(vote_history) if vote_history else "No votes yet."
        personality_desc = self.personality.get("description", "")
        scratchpad_context = self.get_scratchpad_context()

        # Extract active and eliminated players from conversation history
        active_players = self._extract_active_players(conversation_history)
        eliminated_players = self._extract_eliminated_players(conversation_history)

        # Determine if this is the start of the game (few non-system messages)
        non_system_messages = [m for m in conversation_history if not m.get('is_system')]
        is_game_start = len(non_system_messages) < 3

        # Inject round summary if available
        summary_injection = ""
        if round_summary:
            summary_injection = f"\n{round_summary}\n\nBased on the elimination and will, what do we know now?\n"

        personality_rules = self._get_personality_rules()

        if self.role == "mafia":
            strategy = self.personality.get("mafia_strategy", "")
            if is_game_start:
                # Opening prompt - no reasoning needed yet
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game.

PERSONALITY: {personality_desc}
SPEAKING STYLE: {self.personality.get('speaking_style', '')}

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

This is the START of the game. The opening hint was cryptic. Players are nervous.

Give a DRAMATIC INTRODUCTORY statement (1-2 sentences) that:
- Sets your personality tone
- Responds to the ominous hint
- Establishes yourself as "helpful" (but you're secretly mafia)
- NO accusations yet - there's no conversation to analyze

Speak in FIRST PERSON only. Use "I", "me", "my".

Your response:"""
            else:
                # Mid-game - Use simplified, explicit structured format
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game.

ACTIVE PLAYERS: {', '.join(active_players)}
ELIMINATED: {', '.join(eliminated_players)}

{summary_injection}  # ✅ NEW: Inject summary instead of full history

{scratchpad_context}

CURRENT DISCUSSION (post-voting):
{context_str}

===== YOUR TURN =====

INSTRUCTION: Respond in this EXACT format. Do not deviate:

<reasoning>
Step 1: Who suspects me? [brief analysis]
Step 2: What's my move? [deflect/defend/chaos]
Step 3: Evidence to cite: [specific quote from conversation]
</reasoning>

<response>
[Your 1-2 sentence public message, using FIRST PERSON]
</response>

CRITICAL RULES:
- Everything inside <reasoning> is PRIVATE (not shown to others)
- Everything inside <response> is PUBLIC (what others hear)
- Use ONLY active player names: {', '.join(active_players)}
- Cite SPECIFIC evidence from conversation above
- Speak in FIRST PERSON ("I noticed..." not "Jay noticed...")

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

Your formatted response:"""
        else:
            strategy = self.personality.get("villager_strategy", "")
            if is_game_start:
                # Opening prompt - no reasoning needed yet
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game.

PERSONALITY: {personality_desc}
SPEAKING STYLE: {self.personality.get('speaking_style', '')}

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

This is the START of the game. The opening hint was cryptic. You need to find the mafia.

Give a DRAMATIC INTRODUCTORY statement (1-2 sentences) that:
- Sets your personality tone
- Shows your investigative mindset
- Responds to the hint
- NO accusations yet - there's no conversation to analyze

Speak in FIRST PERSON only. Use "I", "me", "my".

Your response:"""
            else:
                # Mid-game - Use simplified, explicit structured format
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game.

ACTIVE PLAYERS: {', '.join(active_players)}
ELIMINATED: {', '.join(eliminated_players)}

{summary_injection}  # ✅ NEW: Inject summary instead of full history

{scratchpad_context}

CURRENT DISCUSSION (post-voting):
{context_str}

===== YOUR TURN =====

INSTRUCTION: Respond in this EXACT format. Do not deviate:

<reasoning>
Step 1: Who looks suspicious? [brief analysis]
Step 2: What's my move? [accuse/defend/question]
Step 3: Evidence to cite: [specific quote from conversation]
</reasoning>

<response>
[Your 1-2 sentence public message, using FIRST PERSON]
</response>

CRITICAL RULES:
- Everything inside <reasoning> is PRIVATE (not shown to others)
- Everything inside <response> is PUBLIC (what others hear)
- Use ONLY active player names: {', '.join(active_players)}
- Cite SPECIFIC evidence from conversation above
- Speak in FIRST PERSON ("I noticed..." not "Jay noticed...")

Your formatted response:"""
        return prompt

    def _extract_active_players(self, conversation_history: List[Dict]) -> List[str]:
        """Extract active (non-eliminated) players from conversation history"""
        all_players = set()
        eliminated = set()
        for msg in conversation_history:
            if not msg.get('is_system') and msg.get('agent'):
                all_players.add(msg['agent'])
            if msg.get('is_system') and '❌' in msg.get('content', ''):
                content = msg['content']
                try:
                    name = content.split('❌')[1].split('has been eliminated')[0].strip()
                    eliminated.add(name)
                except Exception:
                    pass
        return sorted(list(all_players - eliminated))

    def _extract_eliminated_players(self, conversation_history: List[Dict]) -> List[str]:
        """Extract eliminated players from conversation history"""
        eliminated = []
        for msg in conversation_history:
            if msg.get('is_system') and '❌' in msg.get('content', ''):
                try:
                    name = msg['content'].split('❌')[1].split('has been eliminated')[0].strip()
                    if name not in eliminated:
                        eliminated.append(name)
                except Exception:
                    pass
        return eliminated


    # ✅ NEW: Helper functions for structured prompts
    def _format_vote_history(self, vote_history: List[Dict]) -> str:
        """Format voting history for pattern detection"""
        if not vote_history:
            return "No votes yet."
        
        lines = []
        for round_data in vote_history[-3:]:  # Last 3 rounds
            round_num = round_data['round']
            votes = round_data['votes']
            eliminated = round_data.get('eliminated', 'Unknown')
            
            lines.append(f"Round {round_num}: {eliminated} was eliminated")
            for vote in votes:
                lines.append(f"  - {vote['voter']} → {vote['target']}")
        
        return "\n".join(lines)


    def _analyze_mentions(self, messages: List[Dict]) -> str:
        """Track who mentions whom - reveals alliances"""
        mention_map = {}
        
        # First, extract all unique agent names from the messages
        all_agent_names = set()
        for msg in messages:
            if not msg.get('is_system'):
                all_agent_names.add(msg['agent'])
        
        # Now analyze mentions
        for msg in messages:
            if msg.get('is_system'):
                continue
            
            speaker = msg['agent']
            content = msg['content'].lower()
            
            # Find mentions of other agents by checking if their names appear in the message
            for agent_name in all_agent_names:
                if agent_name != speaker and agent_name.lower() in content:
                    key = f"{speaker}→{agent_name}"
                    mention_map[key] = mention_map.get(key, 0) + 1
        
        # Format as string
        if not mention_map:
            return "No clear mention patterns yet."
        
        # Sort by frequency
        sorted_mentions = sorted(mention_map.items(), key=lambda x: x[1], reverse=True)
        lines = [f"{k}: {v} times" for k, v in sorted_mentions[:8]]  # Top 8
        return "\n".join(lines)


    def _get_active_players(self, conversation_history: List[Dict]) -> List[str]:
        """Get list of active (non-eliminated) players"""
        all_players = set()
        eliminated = set()
        
        for msg in conversation_history:
            if not msg.get('is_system'):
                all_players.add(msg['agent'])
            elif 'has been eliminated' in msg.get('content', ''):
                # Extract name from elimination message
                content = msg['content']
                if '❌' in content:
                    name = content.split('❌')[1].split('has been eliminated')[0].strip()
                    eliminated.add(name)
        
        return list(all_players - eliminated)


    def _get_eliminated_players(self, conversation_history: List[Dict]) -> List[str]:
        """Get list of eliminated players"""
        eliminated = []
        
        for msg in conversation_history:
            if msg.get('is_system') and 'has been eliminated' in msg.get('content', ''):
                content = msg['content']
                if '❌' in content:
                    name = content.split('❌')[1].split('has been eliminated')[0].strip()
                    if name not in eliminated:
                        eliminated.append(name)
        
        return eliminated
    
    def _format_conversation(self, messages: List[Dict]) -> str:
        """Format conversation for prompts (agent-local version)"""
        return "\n".join([
            f"{msg['agent']}: {msg['content']}"
            for msg in messages
            if not msg.get('is_system')
        ])