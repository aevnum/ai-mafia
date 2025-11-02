# game_engine.py
"""Main game engine that orchestrates the Mafia game"""

import time
import random
import threading
from typing import List, Dict, Optional
from agent import Agent
from api_handler import APIHandler
from config import DEFAULT_NUM_AGENTS, DEFAULT_NUM_MAFIA, CONVERSATION_CONTEXT_SIZE, VOTING_MESSAGE_THRESHOLD, OPENING_HINTS, VOTING_CONTEXT_SIZE
from orchestrator import Orchestrator


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
        self.conversation_reset_index = 0  # ✅ NEW: Track where context should reset
        self.orchestrator = Orchestrator(self.api_handler)  # ✅ NEW
        self.current_speaker = None  # Track who is currently speaking
        
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
    
    def process_agent_turn(self, agent: Agent, is_impatient_turn: bool = False, is_mediator_turn: bool = False) -> Optional[Dict]:
        """
        Process agent's turn (orchestrator already decided they should speak).
        Returns message dict.
        """
        # Add delay to avoid rate limits (before API call)
        time.sleep(2)
        
        # Get current conversation state
        conversation = self.get_conversation_snapshot()

        # Mark agent as typing
        agent.is_typing = True

        try:
            # GENERATOR: Create what to say
            prompt = agent.create_prompt(
                conversation, 
                self.vote_history, 
                context_reset_index=self.conversation_reset_index,
                is_impatient_turn=is_impatient_turn,
                is_mediator_turn=is_mediator_turn
            )
            response = self.api_handler.generate_response(prompt)

            if response:
                # ✅ NEW: Parse structured response
                reasoning, actual_message = self._parse_agent_response(response)

                # ✅ Store reasoning for end-game analysis
                if reasoning:
                    agent.add_reasoning(reasoning)

                # ✅ Only the actual message goes to conversation
                if actual_message:
                    self.add_message(agent.name, actual_message)
                    agent.last_speak_time = time.time()
                    agent.message_count += 1

                    return {
                        "agent": agent.name,
                        "content": actual_message,
                        "role": agent.role,
                        "reasoning": reasoning  # For potential analysis
                    }
                else:
                    # If no response tag found, use raw output (fallback for opening statements)
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

    def _parse_agent_response(self, response: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse agent response, handling cases where model ignores structure
        Returns: (reasoning, message)
        """
        import re

        # Try to extract structured format
        reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', response, re.DOTALL | re.IGNORECASE)
        response_match = re.search(r'<response>(.*?)</response>', response, re.DOTALL | re.IGNORECASE)

        reasoning = reasoning_match.group(1).strip() if reasoning_match else None
        message = response_match.group(1).strip() if response_match else None

        # FALLBACK: If tags not found, split on common patterns
        if not reasoning and not message:
            # Check if response contains the opening tags but no closing tags (truncation)
            if '<reasoning>' in response.lower():
                parts = re.split(r'<reasoning>|<response>', response, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    reasoning = parts[1].strip()
                if len(parts) >= 3:
                    message = parts[2].strip()
            else:
                # No structure at all - treat entire response as message
                message = response.strip()

        # Clean up any leaked reasoning indicators from message
        if message and reasoning:
            leak_patterns = [
                r'Step \d+:.*?\n',
                r'EVIDENCE GATHERING.*?\n',
                r'HYPOTHESIS:.*?\n',
                r'MY MOVE:.*?\n'
            ]
            for pattern in leak_patterns:
                message = re.sub(pattern, '', message, flags=re.IGNORECASE)
            message = message.strip()

        return reasoning, message
    
    def run_round(self) -> List[Dict]:
        """
        Run one round where orchestrator picks ONE agent to speak.
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
        
        # If we already have a current speaker, process their turn
        if self.current_speaker:
            next_speaker = next((a for a in self.agents if a.name == self.current_speaker), None)
            if next_speaker:
                # Check if this is an impatient turn
                is_impatient = self.orchestrator.is_impatient_turn(next_speaker.name)
                # Check if this is a mediator turn
                is_mediator = self.orchestrator.is_mediator_turn(next_speaker.name, self.conversation_history)
                
                # Process the selected agent's turn
                message = self.process_agent_turn(
                    next_speaker, 
                    is_impatient_turn=is_impatient,
                    is_mediator_turn=is_mediator
                )
                
                # Clear current speaker after message is processed
                self.current_speaker = None
                
                if message:
                    round_messages.append(message)
                return round_messages
        
        # ✅ ORCHESTRATOR picks next speaker
        next_speaker = self.orchestrator.select_next_speaker(
            self.agents, 
            self.conversation_history,
            self.eliminated_agents
        )
        
        if not next_speaker:
            return round_messages
        
        # Set current speaker for UI to display (will be processed on next call)
        self.current_speaker = next_speaker.name
        
        return round_messages
    
    def trigger_voting(self):
        """Trigger a voting round"""
        # Prevent multiple voting triggers
        if self.in_voting:
            return
        
        # ✅ Log speaking distribution before voting
        recent_speakers = {}
        messages_since_last = [m for m in self.conversation_history[self.last_voting_message_count:] 
                              if not m.get('is_system')]
        for msg in messages_since_last:
            speaker = msg['agent']
            recent_speakers[speaker] = recent_speakers.get(speaker, 0) + 1
        print("\n[ORCHESTRATOR STATS] Speaking distribution this round:")
        for agent in sorted(recent_speakers.keys(), key=lambda x: recent_speakers[x], reverse=True):
            print(f"  {agent}: {recent_speakers[agent]} messages")
        print()
        self.in_voting = True
        self.add_message("System", "🗳️ VOTING TIME! After 20 messages, it's time to vote someone out!", is_system=True)
        
        # Reset round tracker for fresh start after voting
        self.agents_spoken_this_round.clear()
        
        # Conduct voting
        votes = self.conduct_voting()
        
        # Determine who gets eliminated by vote
        voted_out_name = None
        voted_out_agent = None
        if votes:
            voted_out_name = max(votes, key=votes.get)
            voted_out_agent = next((a for a in self.agents if a.name == voted_out_name), None)
            
            if voted_out_agent:
                self.eliminated_agents.append(voted_out_name)
                role_reveal = "a MAFIA member" if voted_out_agent.role == "mafia" else "a VILLAGER"
                
                self.add_message("System", 
                    f"📊 Voting Results: {', '.join([f'{name}: {count} votes' for name, count in votes.items()])}", 
                    is_system=True)
                self.add_message("System", 
                    f"❌ {voted_out_name} has been eliminated by vote! They were {role_reveal}.", 
                    is_system=True)
        
        # ✅ NEW: Night kill phase - Mafia kills someone
        mafia_kill_name = None
        mafia_kill_agent = None
        remaining_mafia = [a for a in self.agents 
                          if a.role == "mafia" and a.name not in self.eliminated_agents]
        
        if remaining_mafia:
            self.add_message("System", "🌙 NIGHT FALLS... The mafia strikes!", is_system=True)
            mafia_kill_name = self.conduct_mafia_kill(remaining_mafia)
            
            if mafia_kill_name:
                mafia_kill_agent = next((a for a in self.agents if a.name == mafia_kill_name), None)
                if mafia_kill_agent:
                    self.eliminated_agents.append(mafia_kill_name)
                    
                    # Generate will for mafia's victim
                    original_will = self.generate_death_will(mafia_kill_agent)
                    self.add_message("System", 
                        f"📜 {mafia_kill_name}'s LAST WILL: \"{original_will}\"", 
                        is_system=True)
                    
                    # Let mafia edit the will
                    edited_will = self.conduct_will_editing(original_will, remaining_mafia)
                    if edited_will != original_will:
                        self.add_message("System", 
                            f"✏️ WILL EDITED (mafia removed 1 word): \"{edited_will}\"", 
                            is_system=True)
        
        # ✅ Create a summary of what just happened
        vote_summary = f"📋 ROUND SUMMARY:\n"
        if voted_out_agent:
            vote_summary += f"- DAY: {voted_out_name} was eliminated by vote ({('a MAFIA member' if voted_out_agent.role == 'mafia' else 'a VILLAGER')})\n"
            vote_summary += f"- Vote distribution: {', '.join([f'{name} ({count})' for name, count in sorted(votes.items(), key=lambda x: x[1], reverse=True)])}\n"
        if mafia_kill_agent:
            vote_summary += f"- NIGHT: {mafia_kill_name} was killed by the mafia! (was a VILLAGER)\n"
            vote_summary += f"- Their will hinted: [analyze the will yourself]\n"
        vote_summary += f"\n🔄 NEW DISCUSSION ROUND - Focus on what we learned!"
        self.add_message("System", vote_summary, is_system=True)
                
        # ✅ NEW: Mark this point as context reset boundary
        self.conversation_reset_index = len(self.conversation_history)
                
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
            # Update voting counter
            non_system_messages = [m for m in self.conversation_history if not m.get('is_system')]
            self.last_voting_message_count = len(non_system_messages)
        
        self.in_voting = False
    
    def conduct_mafia_kill(self, mafia_agents: List[Agent]) -> Optional[str]:
        """Have mafia collectively choose someone to kill during the night phase"""
        active_agents = [a for a in self.agents if a.name not in self.eliminated_agents]
        
        # Mafia can only kill villagers
        candidates = [a.name for a in active_agents if a.role == "villager"]
        
        if not candidates:
            return None
        
        conversation = self.get_conversation_snapshot()
        recent_context = self._format_conversation(conversation[-20:])
        
        # Have the mafia agent(s) decide who to kill
        for mafia_agent in mafia_agents:
            kill_prompt = f"""You are {mafia_agent.name}, a MAFIA member. It's night time and you must kill a villager.

Based on the recent conversation, who is the BIGGEST THREAT to you?
Who is closest to figuring out you're mafia?

ACTIVE VILLAGERS: {', '.join(candidates)}

Recent conversation:
{recent_context}

CRITICAL: Respond with ONLY the name of who you want to kill (one name, nothing else).
Choose someone who suspects you or is leading the investigation.

Your target:"""
            
            try:
                time.sleep(2)  # Rate limit protection
                response = self.api_handler.generate_response(kill_prompt)
                if response:
                    # Extract just the name
                    target = response.strip().strip('"').strip("'")
                    # Validate it's a valid candidate
                    for candidate in candidates:
                        if candidate.lower() in target.lower():
                            return candidate
            except Exception as e:
                print(f"Error in mafia kill decision by {mafia_agent.name}: {e}")
        
        # Fallback: random choice
        return random.choice(candidates) if candidates else None
    
    def conduct_voting(self) -> Dict[str, int]:
        """Have each agent vote for someone to eliminate, using scratchpad observations"""
        votes = {}
        round_votes = []
        active_agents = [a for a in self.agents if a.name not in self.eliminated_agents]

        for agent in active_agents:
            candidates = [a.name for a in active_agents if a.name != agent.name]
            conversation = self.get_conversation_snapshot()

            observations = "\n".join([f"- {obs['observation']}" 
                for obs in agent.current_game_observations[-5:]]) if agent.current_game_observations else "No observations recorded yet."

            # ✅ ENFORCE structured voting response
            voting_prompt = f"""You are {agent.name}, a {agent.role} in a Mafia game.

⚠️ CRITICAL: Do NOT just vote like others. Find YOUR OWN evidence.
Think independently - what did YOU personally observe?

Based on the conversation so far, vote for ONE person to eliminate.

Available candidates: {', '.join(candidates)}

YOUR OBSERVATIONS THIS GAME:
{observations}

Recent conversation:
{self._format_conversation(conversation[-VOTING_CONTEXT_SIZE:])}

You must respond in TWO parts:

PART 1 - ANALYSIS (private reasoning)
<reasoning>
- Who is most suspicious based on evidence?
- What specific patterns did I notice?
- Who voted with whom in past rounds?
</reasoning>

PART 2 - YOUR VOTE (public)
<response>
VOTE: [name]
REASON: [one sentence in FIRST PERSON using "I"]
</response>

CRITICAL: Use "I" in your reason. Example: "I vote for Jay because I noticed..."
NOT "This player votes..." or "Jay is suspicious because..."

Your response:"""

            vote_name = None
            reason = "No reason given"
            try:
                time.sleep(2)  # Rate limit protection
                response = self.api_handler.generate_response(voting_prompt)

                if response:
                    # ✅ Parse structured response
                    reasoning, vote_response = self._parse_agent_response(response)

                    # Store reasoning
                    if reasoning:
                        agent.add_observation(f"[Voting reasoning]: {reasoning}")

                    # Parse vote from response block
                    vote_name = None
                    reason = "No reason given"

                    if vote_response:
                        # Extract vote
                        if "VOTE:" in vote_response:
                            vote_line = vote_response.split("VOTE:")[1].split("\n")[0].strip()
                            vote_name = vote_line.strip().strip('"').strip("'").strip('.')
                        # Extract reason
                        if "REASON:" in vote_response:
                            reason = vote_response.split("REASON:")[1].strip().split("\n")[0].strip()

                    # Find matching candidate
                    if vote_name:
                        for candidate in candidates:
                            if candidate.lower() in vote_name.lower():
                                votes[candidate] = votes.get(candidate, 0) + 1
                                self.add_message("System", 
                                    f"🗳️ {agent.name} voted for {candidate}. Reason: {reason}", 
                                    is_system=True)
                                break
            except Exception as e:
                print(f"Error in voting for {agent.name}: {e}")
            round_votes.append({
                "voter": agent.name,
                "target": vote_name,
                "reason": reason,
                "round": len(self.vote_history) + 1
            })
        self.vote_history.append({
            "round": len(self.vote_history) + 1,
            "votes": round_votes,
            "eliminated": None
        })

        # Show who voted for whom (creates drama!)
        vote_summary = "\n".join([
            f"  • {v['voter']} → {v['target']}: {v['reason']}"
            for v in round_votes
        ])
        self.add_message("System", 
            f"📋 VOTE BREAKDOWN:\n{vote_summary}", 
            is_system=True)
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

Before you die, you leave a will with your SUSPICION about who the mafia is.
Based on the conversation, who do you suspect? What patterns did you notice?

CRITICAL: Write in FIRST PERSON. Use \"I saw...\", \"I noticed...\", \"I believe...\"

Be SPECIFIC - mention names and behaviors that seemed suspicious.
Write ONE sentence (15-25 words) that reveals your suspicion.

GOOD RULES OF THUMB:
- Mention specific actions or statements by other players
- Reference voting patterns or alliances you observed
- Avoid vague statements like "I think someone is suspicious"

Recent conversation:
{recent_context}

Your will (ONE SENTENCE, 15-25 WORDS, BE SPECIFIC):"""

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

The victim left this will: "{original_will}"

You get to remove ONE word to make the accusation less clear.
Which word should you remove to best protect yourself or your allies?

STRATEGY:
- Remove names to hide identity
- Remove specific behaviors that reveal your tactics
- Remove evidence words like "saw", "noticed", "believe" to weaken the claim

Respond with ONLY the word you want removed (just the word, nothing else)."""

        removed_word = None
        for agent in mafia_agents:
            if agent.name not in self.eliminated_agents:
                try:
                    time.sleep(2)  # Rate limit protection
                    response = self.api_handler.generate_response(editing_prompt)
                    if response:
                        removed_word = response.strip().strip('"').strip("'").strip('.,!?').lower()
                        break
                except Exception as e:
                    print(f"Error in will editing by {agent.name}: {e}")
        
        if removed_word:
            # Remove first occurrence of the word (case-insensitive)
            words = original_will.split()
            for i, word in enumerate(words):
                # Clean the word of punctuation for comparison
                clean_word = word.strip('.,!?"\'-').lower()
                if clean_word == removed_word:
                    # Remove the word but keep the punctuation structure
                    new_will = " ".join(words[:i] + words[i+1:])
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
        Analyze agent's reasoning throughout the game and combine with testimonial.
        NO player names should be mentioned - only strategies and tactics.
        """
        # Get agent's reasoning from throughout the game
        reasoning_summary = "\n".join(agent.current_game_reasoning[-10:]) if agent.current_game_reasoning else "No reasoning captured."
        
        # Get agent's public messages
        agent_messages = [msg['content'] for msg in full_conversation if msg.get('agent') == agent.name and not msg.get('is_system')]
        
        outcome = "WON" if won else "LOST"
        
        learning_prompt = f"""You are {agent.name}, a {agent.role.upper()} who just {outcome} a Mafia game.

YOUR INTERNAL REASONING THROUGHOUT THE GAME:
{reasoning_summary}

YOUR PUBLIC MESSAGES:
{chr(10).join(agent_messages[-5:])}

Based on your reasoning and how the game played out, summarize your strategy in ONE sentence.

CRITICAL RULES:
- NO player names (no "Jay", "Aryan", etc.)
- Describe WHAT you did, not WHO you targeted
- Use generic terms: "allies", "suspects", "the accused"
- Focus on tactics: "deflected", "built alliances", "analyzed patterns", etc.

Example: "Deflected suspicion by aggressively questioning others while building consensus with quieter players"

Your strategy summary (ONE SENTENCE):"""

        try:
            time.sleep(2)
            response = self.api_handler.generate_response(learning_prompt)
            
            if response:
                strategy_summary = response.strip()
                
                # Update scratchpad with simple role + strategy
                agent.update_strategy(agent.role, strategy_summary)
                
                print(f"[SCRATCHPAD] {agent.name} ({agent.role}): {strategy_summary}")
                
        except Exception as e:
            print(f"Error generating learnings for {agent.name}: {e}")
            # Fallback
            simple_summary = f"{'Won' if won else 'Lost'} by speaking {agent.message_count} times"
            agent.update_strategy(agent.role, simple_summary)
        
    def get_agent_states(self) -> List[Dict]:
        """Get current state of all agents"""
        return [
            {
                "name": agent.name,
                "role": agent.role,
                "is_typing": agent.name == self.current_speaker,
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
