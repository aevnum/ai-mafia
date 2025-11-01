# agent.py
"""AI Agent with Scheduler and Generator modules"""

import time
import random
from typing import List, Dict, Optional
from config import MIN_SPEAK_INTERVAL


class Agent:
    """
    AI Agent with two-part brain:
    - Scheduler: Decides WHEN to speak
    - Generator: Decides WHAT to say
    """
    
    def __init__(self, agent_id: int, name: str, role: str):
        self.id = agent_id
        self.name = name
        self.role = role  # "villager" or "mafia"
        self.is_typing = False
        self.last_speak_time = 0
        self.message_count = 0
        self.suspicion_level = 0  # Track how suspicious this agent seems
        
    def scheduler(self, conversation_history: List[Dict]) -> bool:
        """
        Decides WHETHER to speak based on conversation flow.
        Returns True if agent should speak, False otherwise.
        """
        # Check if enough time has passed since last message
        time_since_last = time.time() - self.last_speak_time
        if time_since_last < MIN_SPEAK_INTERVAL:
            return False
        
        # Get recent messages (last 3)
        recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        
        # Check if agent was mentioned
        mentioned = any(
            self.name.lower() in msg.get('content', '').lower() 
            for msg in recent_messages
        )
        
        # Calculate base probability to speak
        base_probability = 0.3
        
        # Increase probability if mentioned
        if mentioned:
            base_probability += 0.4
        
        # Mafia agents are more talkative to deflect suspicion (adaptive verbosity)
        if self.role == "mafia":
            base_probability += 0.2
            
        # Reduce probability if agent has spoken recently relative to others
        if self.message_count > 0:
            avg_messages = sum(1 for msg in conversation_history if msg.get('agent') == self.name)
            if avg_messages > len(conversation_history) / (len(conversation_history) + 1):
                base_probability -= 0.15
        
        # Strategic silence: Don't always speak even when you could
        should_speak = random.random() < base_probability
        
        return should_speak
    
    def create_prompt(self, conversation_history: List[Dict]) -> str:
        """
        Creates the prompt for the generator based on role and context.
        """
        # Get recent conversation context
        recent_context = conversation_history[-5:] if len(conversation_history) >= 5 else conversation_history
        context_str = "\n".join([
            f"{msg['agent']}: {msg['content']}" 
            for msg in recent_context
        ])
        
        if self.role == "mafia":
            prompt = f"""You are {self.name}, a MAFIA member in a Mafia game (social deduction game). 
Your goal is to:
1. Deflect suspicion from yourself
2. Subtly cast doubt on villagers
3. Blend in naturally without being obvious

Recent conversation:
{context_str}

Respond naturally in 1-2 sentences. Be strategic, observant, and blend in. Don't be obviously defensive.
Your response:"""
        else:  # villager
            prompt = f"""You are {self.name}, a VILLAGER in a Mafia game (social deduction game).
Your goal is to:
1. Find and identify the mafia members
2. Ask probing questions
3. Analyze others' behavior and statements

Recent conversation:
{context_str}

Respond naturally in 1-2 sentences. Share your observations, ask questions, or express suspicions.
Your response:"""
        
        return prompt
    
    def __repr__(self):
        return f"Agent({self.name}, {self.role}, messages={self.message_count})"