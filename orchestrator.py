# orchestrator.py
"""Orchestrator that decides WHO should speak WHEN"""

import time
from typing import List, Dict, Optional

class Orchestrator:
    """
    Central conversation manager that decides speaking order based on:
    - Direct mentions/accusations (defense priority)
    - Patience threshold (give quiet agents a turn)
    - Conversation flow (avoid echo chamber)
    """
    
    def __init__(self, api_handler):
        self.agent_patience = {}  # Track messages since last speak
        self.patience_threshold = 8  # After 8 messages without speaking, force a turn
        self.api_handler = api_handler  # Shared API handler for LLM calls
        self.question_queue = {}  # agent_name -> list of questioners
        
    def select_next_speaker(self, agents: List, conversation_history: List[Dict], 
                           eliminated_agents: List[str]) -> Optional[object]:
        """
        Decide which agent should speak next based on conversation context.
        Returns: Agent object or None
        """
        active_agents = [a for a in agents if a.name not in eliminated_agents]
        if not active_agents:
            return None
        # Update patience tracking
        self._update_patience(active_agents, conversation_history)
        # Get last few messages (context window)
        recent_messages = [m for m in conversation_history[-10:] if not m.get('is_system')]
        if not recent_messages:
            return self._pick_random(active_agents)
        # RULE 0: Detect ping-pong and inject mediator
        pingpong_agents = self._detect_pingpong(recent_messages, active_agents)
        if pingpong_agents:
            mediator = self._pick_mediator(active_agents, pingpong_agents)
            if mediator:
                print(f"[ORCHESTRATOR] Ping-pong detected between {pingpong_agents[0].name} and {pingpong_agents[1].name} - injecting mediator {mediator.name}")
                return mediator
        # Update question queue from last message
        if recent_messages:
            last_message = recent_messages[-1]
            self._update_question_queue(last_message, active_agents)
        last_speaker = recent_messages[-1].get('agent')
        last_content = recent_messages[-1].get('content', '')
        # RULE 1: If someone was directly accused/mentioned, let them defend
        accused = self._find_accused(last_content, active_agents)
        if accused and accused.name != last_speaker:
            self._clear_question_queue(accused.name)
            print(f"[ORCHESTRATOR] {accused.name} was accused - giving them defense priority")
            return accused
        # NEW RULE 1.5: Check question queue
        agent_with_questions = self._get_agent_with_pending_questions(active_agents)
        if agent_with_questions and agent_with_questions.name != last_speaker:
            self._clear_question_queue(agent_with_questions.name)
            print(f"[ORCHESTRATOR] {agent_with_questions.name} has unanswered questions - giving them priority")
            return agent_with_questions
        # RULE 2: Check for patience overflow (agent hasn't spoken in too long)
        impatient = self._find_impatient_agent(active_agents)
        if impatient:
            print(f"[ORCHESTRATOR] {impatient.name} ran out of patience ({self.agent_patience[impatient.name]} messages)")
            return impatient
        # RULE 3: Avoid immediate echo (don't let same person speak twice in a row)
        available = [a for a in active_agents if a.name != last_speaker]
        # RULE 4: Check if conversation is stuck (everyone saying same thing)
        if self._is_echo_chamber(recent_messages, active_agents):
            quiet_agents = self._get_quiet_agents(available, recent_messages)
            if quiet_agents:
                print(f"[ORCHESTRATOR] Echo chamber detected - picking quiet agent")
                return self._pick_by_patience(quiet_agents)
        # RULE 5: Default - pick based on patience (who's been waiting longest)
        return self._pick_by_patience(available)

    def _detect_pingpong(self, recent_messages: List[Dict], active_agents: List) -> Optional[List]:
        """
        Detect if same 2 agents are alternating back and forth (ping-pong pattern).
        Returns [agent1, agent2] if detected, None otherwise.
        """
        if len(recent_messages) < 6:
            return None
        speakers = [m['agent'] for m in recent_messages[-8:]]
        unique_speakers = set(speakers)
        if len(unique_speakers) == 2:
            agents_list = list(unique_speakers)
            speaker_counts = {agent: speakers.count(agent) for agent in agents_list}
            if all(count >= 3 for count in speaker_counts.values()):
                agent_objs = [a for a in active_agents if a.name in agents_list]
                if len(agent_objs) == 2:
                    return agent_objs
        return None

    def _pick_mediator(self, active_agents: List, pingpong_agents: List) -> Optional[object]:
        """Pick a random agent who is NOT part of the ping-pong loop"""
        available_mediators = [a for a in active_agents if a not in pingpong_agents]
        if not available_mediators:
            return None
        import random
        return random.choice(available_mediators)

    def is_mediator_turn(self, agent_name: str, conversation_history: List[Dict]) -> bool:
        """Check if this agent was selected as a mediator to break a loop"""
        recent_messages = [m for m in conversation_history[-10:] if not m.get('is_system')]
        if len(recent_messages) < 6:
            return False
        speakers = [m['agent'] for m in recent_messages[-8:]]
        unique_speakers = set(speakers)
        return len(unique_speakers) == 2 and agent_name not in unique_speakers

    def _extract_questions(self, message_content: str, active_agents: List) -> List[str]:
        """
        Detect which agents are being asked questions in this message.
        Returns list of agent names who were questioned.
        """
        agent_names_str = ", ".join([a.name for a in active_agents])
        prompt = f"""Analyze this message from a Mafia game:

MESSAGE: \"{message_content}\"

ACTIVE PLAYERS: {agent_names_str}

Question: Which players (if any) are being directly ASKED A QUESTION in this message?

Examples:
- \"Navya, why did you vote that way?\" → Return: Navya
- \"Yatharth, can you explain? Also Khushi, what's your take?\" → Return: Yatharth, Khushi
- \"I think Jay is suspicious\" → Return: none
- \"Everyone is being evasive\" → Return: none

Return ONLY the names of players being questioned, separated by commas, or \"none\" if no one is being questioned.

Your answer (names or \"none\"):"""
        try:
            response = self.api_handler.generate_response(prompt)
            if response:
                response = response.strip().lower()
                if response == "none":
                    return []
                questioned = []
                for agent in active_agents:
                    if agent.name.lower() in response:
                        questioned.append(agent.name)
                return questioned
        except Exception as e:
            print(f"[ORCHESTRATOR] Error extracting questions: {e}")
        return []

    def _update_question_queue(self, message: Dict, active_agents: List):
        """Update question queue when someone asks questions"""
        speaker = message.get('agent')
        content = message.get('content', '')
        questioned = self._extract_questions(content, active_agents)
        for target in questioned:
            if target not in self.question_queue:
                self.question_queue[target] = []
            if speaker not in self.question_queue[target]:
                self.question_queue[target].append(speaker)
                print(f"[ORCHESTRATOR] Added to queue: {speaker} questioned {target}")

    def _get_agent_with_pending_questions(self, active_agents: List) -> Optional[object]:
        """Get agent who has unanswered questions in queue"""
        for agent in active_agents:
            if agent.name in self.question_queue and self.question_queue[agent.name]:
                print(f"[ORCHESTRATOR] {agent.name} has pending questions from {self.question_queue[agent.name]}")
                return agent
        return None

    def _clear_question_queue(self, agent_name: str):
        """Clear questions for an agent after they speak"""
        if agent_name in self.question_queue:
            self.question_queue[agent_name] = []
    
    def _update_patience(self, active_agents: List, conversation_history: List[Dict]):
        """Update patience counter for each agent"""
        # Initialize new agents
        for agent in active_agents:
            if agent.name not in self.agent_patience:
                self.agent_patience[agent.name] = 0
        
        # Get last non-system message
        recent_messages = [m for m in conversation_history if not m.get('is_system')]
        if not recent_messages:
            return
        
        last_speaker = recent_messages[-1].get('agent')
        
        # Increment patience for everyone except last speaker
        for agent in active_agents:
            if agent.name == last_speaker:
                self.agent_patience[agent.name] = 0  # Reset
            else:
                self.agent_patience[agent.name] += 1
    
    def _find_accused(self, message_content: str, active_agents: List) -> Optional[object]:
        """Find if someone was directly accused/questioned in the message using LLM"""
        
        # FAST PATH: Check if message mentions any agent names
        agent_names = [a.name.lower() for a in active_agents]
        message_lower = message_content.lower()
        
        mentions_agent = any(name in message_lower for name in agent_names)
        
        if not mentions_agent:
            return None  # No agent mentioned, skip LLM call
        
        # SLOW PATH: Use LLM to accurately determine who is being addressed
        agent_names_str = ", ".join([a.name for a in active_agents])
        
        prompt = f"""Analyze this message from a Mafia game conversation:

MESSAGE: "{message_content}"

ACTIVE PLAYERS: {agent_names_str}

Question: Is this message DIRECTLY addressing, accusing, or questioning a specific player?

Rules:
- Only return a name if the message is CLEARLY directed AT that person
- Questions like "Aryan, why did you..." → return "Aryan"
- Accusations like "I think Jay is lying" → return "Jay"  
- General discussion like "I agree with what Jay said" → return "none"
- Mentions in passing → return "none"

Respond with ONLY the player's name, or "none" if not directly addressing anyone.

Your answer (just the name or "none"):"""

        try:
            response = self.api_handler.generate_response(prompt)
            
            if response:
                response = response.strip().strip('"').strip("'").lower()
                
                # Find matching agent
                for agent in active_agents:
                    if agent.name.lower() == response:
                        return agent
                        
        except Exception as e:
            print(f"[ORCHESTRATOR] Error in LLM accusation detection: {e}")
        
        return None
    
    def _find_impatient_agent(self, active_agents: List) -> Optional[object]:
        """Find agent who has waited too long (patience overflow)"""
        for agent in active_agents:
            if self.agent_patience.get(agent.name, 0) >= self.patience_threshold:
                return agent
        return None
    
    def _is_echo_chamber(self, recent_messages: List[Dict], active_agents: List) -> bool:
        """Detect if everyone is repeating the same point using LLM"""
        if len(recent_messages) < 4:
            return False
        messages_text = "\n".join([
            f"{msg['agent']}: {msg['content']}"
            for msg in recent_messages[-4:]
        ])
        prompt = f"""Analyze these recent messages from a Mafia game:

{messages_text}

Question: Is this an echo chamber or unproductive loop?

ECHO CHAMBER TYPES TO DETECT:
1. **Bilateral Loop**: Same 2 people arguing in circles, repeating themselves
   - "You're deflecting" → "No, YOU'RE deflecting" → "You're still deflecting"
   
2. **Group Repetition**: Multiple people saying the same thing
   - Everyone agreeing without new evidence
   - Same keywords/phrases repeated

3. **Circular Questioning**: Asking same questions over and over
   - "Why are you suspicious?" asked 3+ times
   - No new answers provided

HEALTHY CONVERSATION SIGNS:
- New evidence being introduced
- Different perspectives being shared
- Discussion is moving forward
- Questions are being answered

CRITICAL: If the SAME 2 AGENTS are dominating and just repeating variations of the same argument, respond "yes".

Respond with ONLY "yes" if this is an echo chamber/loop, or "no" if productive.

Your answer (just "yes" or "no"):"""
        try:
            response = self.api_handler.generate_response(prompt)
            if response:
                response = response.strip().lower()
                return response == "yes"
        except Exception as e:
            print(f"[ORCHESTRATOR] Error in LLM echo chamber detection: {e}")
            return self._simple_echo_detection(recent_messages)
        return False
    
    def _simple_echo_detection(self, recent_messages: List[Dict]) -> bool:
        """Fallback simple echo chamber detection if LLM fails"""
        if len(recent_messages) < 4:
            return False
        
        contents = [m['content'].lower() for m in recent_messages[-4:]]
        common_words = ['consensus', 'deflecting', 'suspicious', 'evasive', 'agree']
        
        overlap_count = 0
        for word in common_words:
            if sum(1 for content in contents if word in content) >= 3:
                overlap_count += 1
        
        return overlap_count >= 2
    
    def _get_quiet_agents(self, agents: List, recent_messages: List[Dict]) -> List:
        """Get agents who haven't spoken in recent messages"""
        recent_speakers = set(m['agent'] for m in recent_messages[-5:])
        return [a for a in agents if a.name not in recent_speakers]
    
    def _pick_by_patience(self, agents: List) -> Optional[object]:
        """Pick agent with highest patience (waited longest)"""
        if not agents:
            return None
        
        return max(agents, key=lambda a: self.agent_patience.get(a.name, 0))
    
    def _pick_random(self, agents: List) -> Optional[object]:
        """Pick random agent"""
        import random
        return random.choice(agents) if agents else None
    
    def is_impatient_turn(self, agent_name: str) -> bool:
        """Check if this agent's turn was triggered by patience overflow"""
        return self.agent_patience.get(agent_name, 0) >= self.patience_threshold