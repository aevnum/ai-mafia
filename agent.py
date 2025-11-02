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
    AI Agent with Generator module, personalities, and scratchpad memory
    The Orchestrator now decides WHEN to speak instead of the Agent.
    """

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
        self.scratchpad_path = os.path.join("scratchpads", f"{name.lower()}_scratchpad.txt")
        self.scratchpad = self.load_scratchpad()
        self.current_game_observations = []  # Observations from current game
        self.current_game_reasoning = []  # Store reasoning from each turn
        
    def load_scratchpad(self) -> dict:
        """Load agent's persistent scratchpad from YAML-like text file"""
        if os.path.exists(self.scratchpad_path):
            try:
                with open(self.scratchpad_path, 'r') as f:
                    content = f.read()
                    # Parse simple YAML-like format
                    scratchpad = {
                        "strategies": []
                    }
                    current_strategy = None
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('- role:'):
                            if current_strategy:
                                scratchpad["strategies"].append(current_strategy)
                            current_strategy = {"role": line.split('role:')[1].strip()}
                        elif line.startswith('strategy:') and current_strategy:
                            current_strategy["strategy"] = line.split('strategy:', 1)[1].strip()
                    if current_strategy:
                        scratchpad["strategies"].append(current_strategy)
                    return scratchpad
            except Exception as e:
                print(f"Error loading scratchpad for {self.name}: {e}")
        
        # Initialize new scratchpad
        return {"strategies": []}
    
    def save_scratchpad(self):
        """Save agent's scratchpad to simple YAML-like text file"""
        try:
            os.makedirs("scratchpads", exist_ok=True)
            with open(self.scratchpad_path, 'w') as f:
                for strategy in self.scratchpad.get("strategies", []):
                    f.write(f"- role: {strategy['role']}\n")
                    f.write(f"  strategy: {strategy['strategy']}\n")
        except Exception as e:
            print(f"Error saving scratchpad for {self.name}: {e}")
    
    def update_strategy(self, role_was: str, strategy_summary: str):
        """Update scratchpad after a game ends - simplified"""
        self.scratchpad["strategies"].append({
            "role": role_was,
            "strategy": strategy_summary
        })
        
        # Keep only last 5 strategies to avoid bloat
        if len(self.scratchpad["strategies"]) > 5:
            self.scratchpad["strategies"] = self.scratchpad["strategies"][-5:]
        
        self.save_scratchpad()
    
    def add_observation(self, observation: str):
        """Add an observation during the current game"""
        self.current_game_observations.append({
            "time": time.time(),
            "observation": observation
        })
    
    def add_reasoning(self, reasoning: str):
        """Store reasoning from agent's turn"""
        self.current_game_reasoning.append(reasoning)
    
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
        if not self.scratchpad.get("strategies"):
            return "This is your first game. Play smart and learn from every interaction!"
        
        # Get last 3 strategies
        strategies = self.scratchpad["strategies"][-3:]
        
        # Filter by current role if possible
        role_strategies = [s for s in strategies if s["role"] == self.role]
        
        if role_strategies:
            context = f"YOUR PAST EXPERIENCE AS {self.role.upper()}:\n"
            for s in role_strategies:
                context += f"- {s['strategy']}\n"
        else:
            context = f"YOUR PAST EXPERIENCE:\n"
            for s in strategies:
                context += f"- As {s['role']}: {s['strategy']}\n"
        
        return context
        
    

    def create_prompt(self, conversation_history: List[Dict], vote_history: List[Dict] = None, 
                      context_reset_index: int = 0, is_impatient_turn: bool = False,
                      is_mediator_turn: bool = False) -> str:
        """Creates structured prompt requiring evidence-based reasoning"""
        
        # ADD this special instruction for impatient turns:
        impatience_instruction = ""
        if is_impatient_turn:
            impatience_instruction = """
⏰ SPECIAL SITUATION: You haven't spoken in a while.

Give YOUR FRESH PERSPECTIVE on the current situation.
- Don't just agree with what others said
- What do YOU uniquely observe?
- Bring a NEW angle to the discussion

"""

        # Mediator instruction
        mediator_instruction = ""
        if is_mediator_turn:
            mediator_instruction = """
🎯 SPECIAL SITUATION: Two players are arguing in circles.

You need to BREAK THE STALEMATE by:
- Picking a side in their debate (who do you believe?)
- Bringing NEW evidence they haven't mentioned
- Shifting focus to something they're both missing

DO NOT just summarize their argument - add YOUR perspective!

"""

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
            # First round - agents should see EVERYTHING since game just started
            relevant_context = conversation_history  # No truncation in first round
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

        # Extract opening hint for game start
        opening_hint = ""
        if is_game_start:
            for msg in conversation_history:
                if msg.get('is_system') and '🎭 OPENING HINT:' in msg.get('content', ''):
                    opening_hint = msg['content'].replace('🎭 OPENING HINT:', '').strip()
                    break

        # Inject round summary if available
        summary_injection = ""
        if round_summary:
            summary_injection = f"\n{round_summary}\n\nBased on the elimination and will, what do we know now?\n"

        personality_rules = self._get_personality_rules()

        if self.role == "mafia":
            strategy = self.personality.get("mafia_strategy", "")
            if is_game_start:
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game.

PERSONALITY: {personality_desc}
SPEAKING STYLE: {self.personality.get('speaking_style', '')}

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

This is the START of the game. Players are nervous.

🎭 OPENING HINT: "{opening_hint}"

Give a DRAMATIC INTRODUCTORY statement (1-2 sentences) that:
- Sets your personality tone
- Responds to this specific hint
- Establishes yourself as "helpful" (but you're secretly mafia)
- NO accusations yet - there's no conversation to analyze

Speak in FIRST PERSON only. Use "I", "me", "my".

Your response:"""
            else:
                prompt = f"""You are {self.name}, a MAFIA member in a Mafia game.

ACTIVE PLAYERS: {', '.join(active_players)}
ELIMINATED: {', '.join(eliminated_players)}

{summary_injection}

{scratchpad_context}

CURRENT DISCUSSION (post-voting):
{context_str}

===== YOUR TURN =====
{impatience_instruction}{mediator_instruction}
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
- Speak in FIRST PERSON ("I noticed..." not "Jay noticed...")

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

Your formatted response:"""
        else:
            strategy = self.personality.get("villager_strategy", "")
            if is_game_start:
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game.

PERSONALITY: {personality_desc}
SPEAKING STYLE: {self.personality.get('speaking_style', '')}

🎭 PERSONALITY RULES YOU MUST FOLLOW:
{personality_rules}

This is the START of the game. You need to find the mafia.

🎭 OPENING HINT: "{opening_hint}"

Give a DRAMATIC INTRODUCTORY statement (1-2 sentences) that:
- Sets your personality tone
- Shows your investigative mindset
- Responds to this specific hint
- NO accusations yet - there's no conversation to analyze

Speak in FIRST PERSON only. Use "I", "me", "my".

Your response:"""
            else:
                prompt = f"""You are {self.name}, a VILLAGER in a Mafia game.

{scratchpad_context}

CURRENT DISCUSSION (post-voting):
{context_str}

===== YOUR TURN =====
{impatience_instruction}{mediator_instruction}
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