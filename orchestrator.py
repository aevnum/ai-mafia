# orchestrator.py
"""Orchestrator that decides WHO should speak WHEN"""

import time
from typing import List, Dict, Optional
from config import MIN_SPEAK_INTERVAL

class Orchestrator:
    """
    Central conversation manager that decides speaking order based on:
    - Direct mentions/accusations (defense priority)
    - Patience threshold (give quiet agents a turn)
    - Conversation flow (avoid echo chamber)
    """
    
    def __init__(self):
        self.agent_patience = {}  # Track messages since last speak
        self.patience_threshold = 8  # After 8 messages without speaking, force a turn
        
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
        recent_messages = [m for m in conversation_history[-5:] if not m.get('is_system')]
        
        if not recent_messages:
            # Game start - pick random agent
            return self._pick_random(active_agents)
        
        last_message = recent_messages[-1]
        last_speaker = last_message.get('agent')
        last_content = last_message.get('content', '').lower()
        
        # RULE 1: If someone was directly accused/mentioned, let them defend
        accused = self._find_accused(last_content, active_agents)
        if accused and accused.name != last_speaker:
            print(f"[ORCHESTRATOR] {accused.name} was accused - giving them defense priority")
            return accused
        
        # RULE 2: Check for patience overflow (agent hasn't spoken in too long)
        impatient = self._find_impatient_agent(active_agents)
        if impatient:
            print(f"[ORCHESTRATOR] {impatient.name} ran out of patience ({self.agent_patience[impatient.name]} messages)")
            return impatient
        
        # RULE 3: Avoid immediate echo (don't let same person speak twice in a row)
        available = [a for a in active_agents if a.name != last_speaker]
        
        # RULE 4: Check if conversation is stuck (everyone saying same thing)
        if self._is_echo_chamber(recent_messages):
            # Pick someone who HASN'T spoken recently to break the loop
            quiet_agents = self._get_quiet_agents(available, recent_messages)
            if quiet_agents:
                print(f"[ORCHESTRATOR] Echo chamber detected - picking quiet agent")
                return self._pick_by_patience(quiet_agents)
        
        # RULE 5: Default - pick based on patience (who's been waiting longest)
        return self._pick_by_patience(available)
    
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
        """Find if someone was directly accused in the message"""
        accusation_keywords = ['vote for', 'suspect', 'accuse', 'mafia', 'lying', 'deflecting']
        
        # Check if message contains accusation
        has_accusation = any(keyword in message_content for keyword in accusation_keywords)
        if not has_accusation:
            return None
        
        # Find which agent was named
        for agent in active_agents:
            if agent.name.lower() in message_content:
                return agent
        
        return None
    
    def _find_impatient_agent(self, active_agents: List) -> Optional[object]:
        """Find agent who has waited too long (patience overflow)"""
        for agent in active_agents:
            if self.agent_patience.get(agent.name, 0) >= self.patience_threshold:
                return agent
        return None
    
    def _is_echo_chamber(self, recent_messages: List[Dict]) -> bool:
        """Detect if everyone is repeating the same point"""
        if len(recent_messages) < 4:
            return False
        
        # Check if last 4 messages share common keywords
        contents = [m['content'].lower() for m in recent_messages[-4:]]
        
        # Simple heuristic: if 3+ messages share 2+ words, it's an echo
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
