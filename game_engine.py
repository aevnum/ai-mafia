# game_engine.py
"""Main game engine that orchestrates the Mafia game"""

import time
import random
import threading
from typing import List, Dict, Optional
from agent import Agent
from api_handler import APIHandler
from config import DEFAULT_NUM_AGENTS, DEFAULT_NUM_MAFIA, CONVERSATION_CONTEXT_SIZE


class MafiaGame:
    """
    Game engine that manages agents, conversation flow, and game state.
    Implements shared conversational space with race condition protection.
    """
    
    def __init__(self, num_agents: int = DEFAULT_NUM_AGENTS, 
                 num_mafia: int = DEFAULT_NUM_MAFIA,
                 api_provider: Optional[str] = None):
        self.num_agents = num_agents
        self.num_mafia = num_mafia
        self.agents: List[Agent] = []
        self.conversation_history: List[Dict] = []
        self.api_handler = APIHandler(api_provider)
        self.is_running = False
        self.lock = threading.Lock()  # Protect shared conversation context
        
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Create agents with random role assignments"""
        agent_names = [
            "Alice", "Bob", "Charlie", "Diana", "Eve", 
            "Frank", "Grace", "Henry", "Iris", "Jack"
        ]
        
        # Shuffle and assign roles
        random.shuffle(agent_names)
        selected_names = agent_names[:self.num_agents]
        
        # Assign mafia roles
        mafia_indices = random.sample(range(self.num_agents), self.num_mafia)
        
        for i, name in enumerate(selected_names):
            role = "mafia" if i in mafia_indices else "villager"
            agent = Agent(i, name, role)
            self.agents.append(agent)
        
        # Add initial system message
        self.add_message("System", 
                        f"Game started! {self.num_agents} players, {self.num_mafia} mafia among us. "
                        f"Players: {', '.join([a.name for a in self.agents])}", 
                        is_system=True)
    
    def add_message(self, agent_name: str, content: str, is_system: bool = False):
        """Thread-safe method to add message to conversation"""
        with self.lock:
            message = {
                "agent": agent_name,
                "content": content,
                "timestamp": time.time(),
                "is_system": is_system
            }
            self.conversation_history.append(message)
    
    def get_conversation_snapshot(self) -> List[Dict]:
        """Thread-safe method to get current conversation state"""
        with self.lock:
            return self.conversation_history.copy()
    
    def process_agent_turn(self, agent: Agent) -> Optional[Dict]:
        """
        Process a single agent's potential turn.
        Returns message dict if agent spoke, None otherwise.
        """
        # Get current conversation state
        conversation = self.get_conversation_snapshot()
        
        # SCHEDULER: Decide if agent should speak
        should_speak = agent.scheduler(conversation)
        
        if not should_speak:
            return None
        
        # Mark agent as typing
        agent.is_typing = True
        
        try:
            # GENERATOR: Create what to say
            prompt = agent.create_prompt(conversation)
            response = self.api_handler.generate_response(prompt)
            
            if response:
                # Add message to shared conversation
                self.add_message(agent.name, response)
                agent.last_speak_time = time.time()
                agent.message_count += 1
                
                return {
                    "agent": agent.name,
                    "content": response,
                    "role": agent.role
                }
        except Exception as e:
            print(f"Error processing {agent.name}: {e}")
        finally:
            agent.is_typing = False
        
        return None
    
    def run_round(self) -> List[Dict]:
        """
        Run one round where each agent gets a chance to speak.
        Returns list of messages from this round.
        """
        round_messages = []
        
        # Shuffle agent order for natural chaos
        agent_order = self.agents.copy()
        random.shuffle(agent_order)
        
        for agent in agent_order:
            if not self.is_running:
                break
            
            # Add delay between API calls to avoid rate limits (especially for free tier)
            time.sleep(2)  # 2 second delay between agent turns
            
            message = self.process_agent_turn(agent)
            if message:
                round_messages.append(message)
        
        return round_messages
    
    def start(self):
        """Start the game"""
        self.is_running = True
    
    def stop(self):
        """Stop the game"""
        self.is_running = False
        self.add_message("System", "Game stopped.", is_system=True)
    
    def get_agent_states(self) -> List[Dict]:
        """Get current state of all agents"""
        return [
            {
                "name": agent.name,
                "role": agent.role,
                "is_typing": agent.is_typing,
                "message_count": agent.message_count
            }
            for agent in self.agents
        ]
    
    def get_statistics(self) -> Dict:
        """Get game statistics"""
        total_messages = len([m for m in self.conversation_history if not m.get('is_system')])
        
        return {
            "total_messages": total_messages,
            "num_agents": self.num_agents,
            "num_mafia": self.num_mafia,
            "agent_messages": {
                agent.name: agent.message_count 
                for agent in self.agents
            }
        }