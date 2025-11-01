# game_engine.py
"""Main game engine that orchestrates the Mafia game"""

import time
import random
import threading
from typing import List, Dict, Optional
from agent import Agent
from api_handler import APIHandler
from config import DEFAULT_NUM_AGENTS, DEFAULT_NUM_MAFIA, CONVERSATION_CONTEXT_SIZE, VOTING_MESSAGE_THRESHOLD, OPENING_HINTS, VOTING_CONTEXT_SIZE


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
        self.vote_history: List[Dict] = []  # ✅ NEW: Track voting patterns
        self.api_handler = APIHandler(api_provider)
        self.is_running = False
        self.lock = threading.Lock()  # Protect shared conversation context
        self.in_voting = False
        self.eliminated_agents = []
        self.last_voting_message_count = 0  # Track when last voting occurred
        self.agents_spoken_this_round = set()  # Track who has spoken in current round
        
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Create agents with random role assignments"""
        agent_names = [
            "Aryan", "Jay", "Kshitij", "Laavanya", 
            "Anushka", "Navya", "Khushi", "Yatharth"
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
        
        # Have each agent review their scratchpad and formulate strategy
        for agent in self.agents:
            agent.formulate_game_strategy()
        
        # Generate subtle hint about one of the mafia members
        mafia_agents = [a for a in self.agents if a.role == "mafia"]
        opening_hint = self._generate_opening_hint(mafia_agents, self.agents)
        
        self.add_message("System", 
            f"🎭 OPENING HINT: {opening_hint}", 
            is_system=True)
        
        self.add_message("System", 
            f"💭 Someone among the {self.num_agents} players is not who they claim to be...", 
            is_system=True)
        
        self.add_message("System", 
            f"Players: {', '.join([a.name for a in self.agents])}", 
            is_system=True)
    
    def _generate_opening_hint(self, mafia_agents: List[Agent], all_agents: List[Agent]) -> str:
        """Generate a subtle but legitimate hint about one of the mafia members"""
        if not mafia_agents:
            return "Trust is a luxury none can afford tonight."
        
        # Pick one random mafia member to hint at
        target_mafia = random.choice(mafia_agents)
        personality = target_mafia.personality
        traits = personality.get("traits", [])
        
        # Create subtle hints based on personality traits
        hint_templates = {
            "aggressive": [
                f"The loudest voice often hides the darkest secrets.",
                f"Beware those who speak with too much certainty.",
                f"One among you strikes first, asks questions later."
            ],
            "analytical": [
                f"The one who calculates every word may be calculating against you.",
                f"Logic can be a weapon as sharp as any blade.",
                f"Someone here thinks three steps ahead - but toward what end?"
            ],
            "charismatic": [
                f"Charm is often a mask worn by those with something to hide.",
                f"The most persuasive tongue may speak the sweetest lies.",
                f"One of you could sell water to the ocean - question their motives."
            ],
            "cautious": [
                f"Silence and caution are twins - one is wisdom, one is guilt.",
                f"The one who watches most carefully may be hiding most zealously.",
                f"Someone's restraint is not virtue, but strategy."
            ],
            "unpredictable": [
                f"Chaos and misdirection walk hand in hand tonight.",
                f"One of you dances to a rhythm only they can hear.",
                f"Randomness is the perfect disguise for calculated moves."
            ],
            "intuitive": [
                f"One among you trusts their instincts too much - perhaps to deflect from facts.",
                f"Gut feelings can lead you astray when planted by another.",
                f"Someone reads the room too well - as if they wrote the script."
            ],
            "defensive": [
                f"The quickest to defend may have the most to defend against.",
                f"One of you builds walls before accusations are even made.",
                f"Protection and paranoia wear the same face."
            ],
            "skeptical": [
                f"The one who doubts everyone may be doubting themselves.",
                f"Perpetual suspicion is the mafia's best camouflage.",
                f"Someone questions everything except their own motives."
            ]
        }
        
        # Find matching hints for target mafia's traits
        possible_hints = []
        for trait in traits:
            if trait in hint_templates:
                possible_hints.extend(hint_templates[trait])
        
        # Fallback generic hints if no specific trait matches
        if not possible_hints:
            possible_hints = [
                f"One among you wears two faces tonight.",
                f"The truth is known to some, hidden by others.",
                f"Someone's words will betray them before the night is through."
            ]
        
        return random.choice(possible_hints)
    
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
            # GENERATOR: Create what to say, now pass vote_history for pattern detection
            prompt = agent.create_prompt(conversation, self.vote_history)
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
        Ensures each agent speaks once before any agent speaks twice (round-robin).
        Returns list of messages from this round.
        """
        round_messages = []
        
        # Don't run if game is stopped
        if not self.is_running:
            return round_messages
        
        # Check if we need to trigger voting
        non_system_messages = [m for m in self.conversation_history if not m.get('is_system')]
        messages_since_last_vote = len(non_system_messages) - self.last_voting_message_count
        
        if messages_since_last_vote >= VOTING_MESSAGE_THRESHOLD and not self.in_voting:
            self.trigger_voting()
            return round_messages
        
        # Get active agents (not eliminated)
        active_agents = [a for a in self.agents if a.name not in self.eliminated_agents]
        
        # Reset round tracker if all active agents have spoken
        if self.agents_spoken_this_round and len(self.agents_spoken_this_round) >= len(active_agents):
            self.agents_spoken_this_round.clear()
        
        # Get agents who haven't spoken this round
        agents_to_speak = [a for a in active_agents if a.name not in self.agents_spoken_this_round]
        
        # If all have spoken, reset and use all active agents
        if not agents_to_speak:
            self.agents_spoken_this_round.clear()
            agents_to_speak = active_agents
        
        # Shuffle for variety while maintaining fairness
        random.shuffle(agents_to_speak)
        
        # Each agent gets ONE chance to speak this round
        for agent in agents_to_speak:
            if not self.is_running:
                break
            
            # Add delay between API calls to avoid rate limits (especially for free tier)
            time.sleep(2)  # 2 second delay between agent turns
            
            # Process agent turn (they decide whether to speak via scheduler)
            message = self.process_agent_turn(agent)
            if message:
                round_messages.append(message)
                # Mark this agent as having spoken this round
                self.agents_spoken_this_round.add(agent.name)
        
        return round_messages
    
    def trigger_voting(self):
        """Trigger a voting round"""
        # Prevent multiple voting triggers
        if self.in_voting:
            return
            
        self.in_voting = True
        self.add_message("System", "🗳️ VOTING TIME! After 20 messages, it's time to vote someone out!", is_system=True)
        
        # Reset round tracker for fresh start after voting
        self.agents_spoken_this_round.clear()
        
        # Conduct voting
        votes = self.conduct_voting()
        
        # Determine who gets eliminated
        if votes:
            eliminated = max(votes, key=votes.get)
            eliminated_agent = next((a for a in self.agents if a.name == eliminated), None)
            
            if eliminated_agent:
                self.eliminated_agents.append(eliminated)
                role_reveal = "a MAFIA member" if eliminated_agent.role == "mafia" else "a VILLAGER"
                
                self.add_message("System", 
                    f"📊 Voting Results: {', '.join([f'{name}: {count} votes' for name, count in votes.items()])}", 
                    is_system=True)
                self.add_message("System", 
                    f"❌ {eliminated} has been eliminated! They were {role_reveal}.", 
                    is_system=True)
                
                # NEW: If villager dies, generate will and let mafia edit it
                if eliminated_agent.role == "villager":
                    original_will = self.generate_death_will(eliminated_agent)
                    self.add_message("System", 
                        f"📜 {eliminated}'s LAST WILL: \"{original_will}\"", 
                        is_system=True)
                    
                    # Get remaining mafia to edit the will
                    remaining_mafia = [a for a in self.agents 
                                     if a.role == "mafia" and a.name not in self.eliminated_agents]
                    
                    if remaining_mafia:
                        edited_will = self.conduct_will_editing(original_will, remaining_mafia)
                        if edited_will != original_will:
                            self.add_message("System", 
                                f"✏️ WILL EDITED (mafia removed 1 word): \"{edited_will}\"", 
                                is_system=True)
                
                # Check win conditions
                remaining_agents = [a for a in self.agents if a.name not in self.eliminated_agents]
                mafia_count = sum(1 for a in remaining_agents if a.role == "mafia")
                villager_count = len(remaining_agents) - mafia_count
                
                if mafia_count == 0:
                    self.add_message("System", "🎉 VILLAGERS WIN! All mafia have been eliminated!", is_system=True)
                    self.stop(winner="villagers")
                elif mafia_count >= villager_count:
                    self.add_message("System", "💀 MAFIA WINS! They equal or outnumber the villagers!", is_system=True)
                    self.stop(winner="mafia")
                else:
                    # Continue game - announce new discussion round
                    remaining_agents = [a for a in self.agents if a.name not in self.eliminated_agents]
                    self.add_message("System", 
                        f"💬 New discussion round begins! Remaining players: {', '.join([a.name for a in remaining_agents])}", 
                        is_system=True)
                    
                    # Update the voting counter so next vote happens after 20 more messages
                    non_system_messages = [m for m in self.conversation_history if not m.get('is_system')]
                    self.last_voting_message_count = len(non_system_messages)
        
        self.in_voting = False
    
    def conduct_voting(self) -> Dict[str, int]:
        """Have each agent vote for someone to eliminate, using scratchpad observations and track all votes"""
        votes = {}
        round_votes = []  # ✅ NEW: Track this round's votes
        active_agents = [a for a in self.agents if a.name not in self.eliminated_agents]
        
        for agent in active_agents:
            # Create voting prompt
            candidates = [a.name for a in active_agents if a.name != agent.name]
            conversation = self.get_conversation_snapshot()
            
            # Get agent's observations from scratchpad for this game
            observations = "\n".join([f"- {obs['observation']}" for obs in agent.current_game_observations[-5:]]) if agent.current_game_observations else "No observations recorded yet."
            
            voting_prompt = f"""You are {agent.name}, a {agent.role} in a Mafia game.
Based on the conversation so far, vote for ONE person to eliminate and explain why.

CRITICAL: Speak in FIRST PERSON ONLY. Use "I", "me", "my" when expressing your thoughts.
Example: "I vote for Jay because I noticed..." NOT "{agent.name} votes for Jay because he noticed..."
Example: "I think Navya is suspicious" NOT "This player thinks Navya is suspicious"

Available candidates: {', '.join(candidates)}

YOUR OBSERVATIONS THIS GAME:
{observations}

Recent conversation:
{self._format_conversation(conversation[-VOTING_CONTEXT_SIZE:])}

Respond in this format (in FIRST PERSON):
VOTE: [name]
REASON: [your reasoning in one sentence using "I"]"""

            vote_name = None
            reason = "No reason given"
            try:
                time.sleep(2)  # Rate limit protection
                response = self.api_handler.generate_response(voting_prompt)
                
                if response:
                    # Parse vote and reason
                    vote_name = None
                    reason = "No reason given"
                    # Extract vote
                    if "VOTE:" in response:
                        vote_line = response.split("VOTE:")[1].split("\n")[0].strip()
                        vote_name = vote_line.strip().strip('"').strip("'").strip('.')
                    # Extract reason
                    if "REASON:" in response:
                        reason = response.split("REASON:")[1].strip().split("\n")[0].strip()
                    # Find matching candidate
                    if vote_name:
                        for candidate in candidates:
                            if candidate.lower() in vote_name.lower():
                                votes[candidate] = votes.get(candidate, 0) + 1
                                self.add_message("System", 
                                    f"🗳️ {agent.name} voted for {candidate}. Reason: {reason}", 
                                    is_system=True)
                                vote_name = candidate  # Normalize to candidate name
                                break
                    else:
                        # Fallback: try to find any candidate name in response
                        for candidate in candidates:
                            if candidate.lower() in response.lower():
                                votes[candidate] = votes.get(candidate, 0) + 1
                                self.add_message("System", 
                                    f"🗳️ {agent.name} voted for {candidate}. Reason: {reason}", 
                                    is_system=True)
                                vote_name = candidate
                                break
            except Exception as e:
                print(f"Error in voting for {agent.name}: {e}")
            # ✅ NEW: After each vote, store it
            round_votes.append({
                "voter": agent.name,
                "target": vote_name,
                "reason": reason,
                "round": len(self.vote_history) + 1
            })
        # ✅ NEW: Save this round (eliminated will be filled in trigger_voting)
        # We'll update eliminated after voting in trigger_voting
        self.vote_history.append({
            "round": len(self.vote_history) + 1,
            "votes": round_votes,
            "eliminated": None  # Will be updated after elimination
        })
        return votes
    
    def _format_conversation(self, messages: List[Dict]) -> str:
        """Format conversation for prompts"""
        return "\n".join([
            f"{msg['agent']}: {msg['content']}"
            for msg in messages
            if not msg.get('is_system')
        ])
    
    def generate_death_will(self, eliminated_agent: Agent) -> str:
        """Generate cryptic will from eliminated villager"""
        conversation = self.get_conversation_snapshot()
        recent_context = self._format_conversation(conversation[-15:])
        
        will_prompt = f"""You are {eliminated_agent.name}, a VILLAGER who was just killed by the MAFIA.

Before you die, you leave a cryptic will with a HINT about who killed you.
Based on the conversation, who do you suspect? What was the MAFIA doing?

CRITICAL: Write in FIRST PERSON. Use "I saw...", "I noticed...", "I believe..."
Example: "I saw the pattern in Jay's deflections" NOT "The pattern in Jay's deflections was clear"

Recent conversation:
{recent_context}

Write a 1-sentence cryptic will that hints at the mafia members WITHOUT naming them directly.
Use FIRST PERSON perspective in your will.

Example formats:
- "I noticed the one who asked about X was hiding something about Y"
- "I watched the pattern in someone's speech - they're synchronizing with another"
- "I felt the silence before a certain message was deafening"
- "I counted the questions asked by those who should be answering"

Your will (ONE cryptic sentence in FIRST PERSON):"""

        try:
            time.sleep(2)  # Rate limit protection
            will_text = self.api_handler.generate_response(will_prompt)
            return will_text or "A secret was kept. A secret will die with me."
        except Exception as e:
            print(f"Error generating will for {eliminated_agent.name}: {e}")
            return "A secret was kept. A secret will die with me."
    
    def conduct_will_editing(self, original_will: str, mafia_agents: List[Agent]) -> str:
        """Allow mafia to remove one word from the will to obfuscate it"""
        editing_prompt = f"""You are a MAFIA member who just killed someone.

The victim left this cryptic will: "{original_will}"

You get to remove ONE word to make the hint less clear. 
Which word should you remove to best protect yourself or your allies?
The removed word should be one that reveals strategy or points fingers.

Respond with ONLY the word you want removed, nothing else."""

        removed_word = None
        for agent in mafia_agents:
            if agent.name not in self.eliminated_agents:
                try:
                    time.sleep(2)  # Rate limit protection
                    response = self.api_handler.generate_response(editing_prompt)
                    if response:
                        removed_word = response.strip().strip('"').strip("'").lower()
                        break
                except Exception as e:
                    print(f"Error in will editing by {agent.name}: {e}")
        
        if removed_word:
            # Remove first occurrence of the word
            words = original_will.lower().split()
            if removed_word in words:
                idx = words.index(removed_word)
                new_will = " ".join(original_will.split()[:idx] + original_will.split()[idx+1:])
                return new_will
        
        return original_will
    
    
    def start(self):
        """Start the game"""
        self.is_running = True
    
    def stop(self, winner: str = None):
        """Stop the game and update agent scratchpads with learnings"""
        self.is_running = False
        self.add_message("System", "Game stopped.", is_system=True)
        
        # Update scratchpads for all agents based on game outcome
        if winner:
            # Get full conversation for analysis
            full_conversation = self.get_conversation_snapshot()
            
            for agent in self.agents:
                won = (winner == "villagers" and agent.role == "villager") or (winner == "mafia" and agent.role == "mafia")
                
                # Let agent analyze the full game and generate their own learnings
                self._generate_agent_learnings(agent, won, full_conversation)
    
    def _generate_agent_learnings(self, agent: Agent, won: bool, full_conversation: List[Dict]) -> None:
        """
        Let agent analyze the full game conversation and generate their own strategic learnings.
        NO player names should be mentioned - only strategies and tactics.
        """
        # Format conversation for analysis
        conversation_text = self._format_conversation(full_conversation)
        
        # Get agent's messages only
        agent_messages = [msg['content'] for msg in full_conversation if msg.get('agent') == agent.name and not msg.get('is_system')]
        
        outcome = "WON" if won else "LOST"
        
        learning_prompt = f"""You are {agent.name}, a {agent.role.upper()} who just {outcome} a Mafia game.

Your personality: {agent.personality.get('description', '')}
You spoke {agent.message_count} times during this game.
Previous games played: {agent.scratchpad.get('games_played', 0)}

FULL GAME CONVERSATION (for your analysis):
{conversation_text[:3000]}  

YOUR MESSAGES DURING THIS GAME:
{chr(10).join(agent_messages[:10])}

Analyze this game and extract strategic learnings for FUTURE games.

CRITICAL RULES FOR YOUR ANALYSIS:
1. DO NOT mention ANY specific player names (no "Jay", "Aryan", etc.)
2. Focus ONLY on strategies, tactics, and behavioral patterns
3. Use generic terms: "my allies", "the villagers", "suspicious players", "the accused"
4. Describe WHAT worked or didn't work, not WHO you interacted with

Generate 3 sections:

STRATEGY_USED: Describe the overall strategy you employed this game (1 sentence, no names)
Example: "Deflected suspicion by questioning others aggressively early in the game"

WHAT_WORKED: What tactics were effective? (1 sentence, no names)
Example: "Creating confusion by rapidly shifting focus between multiple suspects"

WHAT_FAILED: What should you avoid or improve? (1 sentence, no names) 
Example: "Being too quiet in early rounds made me appear suspicious later"

Respond ONLY in this format:
STRATEGY_USED: [your strategy]
WHAT_WORKED: [what worked]
WHAT_FAILED: [what to avoid/improve]"""

        try:
            time.sleep(2)  # Rate limit protection
            response = self.api_handler.generate_response(learning_prompt)
            
            if response:
                # Parse response
                strategy_used = "Standard play"
                what_worked = "No clear successes identified"
                what_failed = "No clear failures identified"
                
                if "STRATEGY_USED:" in response:
                    strategy_used = response.split("STRATEGY_USED:")[1].split("\n")[0].strip()
                if "WHAT_WORKED:" in response:
                    what_worked = response.split("WHAT_WORKED:")[1].split("\n")[0].strip()
                if "WHAT_FAILED:" in response:
                    what_failed = response.split("WHAT_FAILED:")[1].split("\n")[0].strip()
                
                # Create learning summary
                if won:
                    lesson = f"✅ {outcome} as {agent.role}: {what_worked}"
                else:
                    lesson = f"❌ {outcome} as {agent.role}: {what_failed}"
                
                # Update agent's scratchpad with AI-generated learnings
                agent.update_strategy(won, agent.role, strategy_used, lesson)
                
                print(f"[LEARNING] {agent.name}: {lesson[:100]}...")
                
        except Exception as e:
            print(f"Error generating learnings for {agent.name}: {e}")
            # Fallback to simple update
            simple_lesson = f"{'Won' if won else 'Lost'} as {agent.role} - spoke {agent.message_count} times"
            agent.update_strategy(won, agent.role, f"As {agent.role}", simple_lesson)
        
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
    
    def save_transcript(self, filename: str = None) -> str:
        """Save game transcript to a text file"""
        import datetime
        import os
        
        # Create transcripts directory if it doesn't exist
        os.makedirs("transcripts", exist_ok=True)
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcripts/mafia_game_{timestamp}.txt"
        
        # Build transcript
        transcript_lines = []
        transcript_lines.append("="*80)
        transcript_lines.append("AI MAFIA GAME TRANSCRIPT")
        transcript_lines.append("="*80)
        transcript_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        transcript_lines.append(f"Players: {self.num_agents} ({self.num_mafia} Mafia)")
        transcript_lines.append("")
        
        # Add player list with roles
        transcript_lines.append("PLAYERS:")
        transcript_lines.append("-"*80)
        for agent in self.agents:
            role_emoji = "🔴" if agent.role == "mafia" else "🔵"
            eliminated = " (ELIMINATED)" if agent.name in self.eliminated_agents else ""
            transcript_lines.append(f"{role_emoji} {agent.name} - {agent.role.upper()}{eliminated} - Messages: {agent.message_count}")
        transcript_lines.append("")
        
        # Add conversation
        transcript_lines.append("CONVERSATION:")
        transcript_lines.append("="*80)
        for msg in self.conversation_history:
            if msg.get('is_system'):
                transcript_lines.append(f"\n[SYSTEM] {msg['content']}\n")
            else:
                # Find agent to get role
                agent = next((a for a in self.agents if a.name == msg['agent']), None)
                role_label = "(MAFIA)" if agent and agent.role == "mafia" else "(VILLAGER)"
                transcript_lines.append(f"{msg['agent']} {role_label}:")
                transcript_lines.append(f"  {msg['content']}")
                transcript_lines.append("")
        
        transcript_lines.append("="*80)
        transcript_lines.append("END OF TRANSCRIPT")
        transcript_lines.append("="*80)
        
        # Write to file
        transcript_text = "\n".join(transcript_lines)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        
        return filename
