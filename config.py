# config.py
"""Configuration file for API providers"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Toggle between providers by commenting/uncommenting
API_PROVIDER = "gemini"  # Options: "gemini" or "grok"
# API_PROVIDER = "grok"

# API Configuration
GEMINI_CONFIG = {
    "api_key": os.getenv("GOOGLE_API_KEY", ""),  # Fetch from environment variable
    "model": "gemini-2.5-flash-lite",
    "temperature": 0.75,
    "max_tokens": 512
}

GROK_CONFIG = {
    "api_key": os.getenv("GROK_API_KEY", ""),  # Fetch from environment variable
    "model": "grok-beta",
    "temperature": 0.75,
    "max_tokens": 512
}

# Game Settings
DEFAULT_NUM_AGENTS = 8
DEFAULT_NUM_MAFIA = 2
MIN_SPEAK_INTERVAL = 3  # Minimum seconds between agent messages
CONVERSATION_CONTEXT_SIZE = 40  # Number of recent messages agents see when speaking
VOTING_CONTEXT_SIZE = 50  # Number of recent messages agents see during voting
VOTING_MESSAGE_THRESHOLD = 20  # Trigger voting after this many messages
MAX_AGENTS = 8  # Maximum number of agents in a game

# Opening Hints - Create initial suspicion and conversation hooks
OPENING_HINTS = [
    "One of you speaks in riddles. One of you never speaks twice in a row.",
    "The eldest among you has already made their choice. The youngest will regret theirs.",
    "Someone here is counting. Someone here is listening. Neither will admit it.",
    "A truth spoken at dawn becomes a lie by dusk.",
    "The quiet ones are never innocent. The loud ones are never alone.",
    "Watch who asks questions but never answers them.",
    "The one who speaks first may not be the first to act.",
    "Someone's silence speaks louder than words. Someone's words hide their silence.",
    "Two of you share a secret. One of you will betray it.",
    "The pattern is already visible. Only the blind will miss it."
]

# Suspicious Behaviors - For agents to reference
SUSPICIOUS_BEHAVIORS = [
    "speaks with certainty",
    "asks too many questions",
    "stays suspiciously silent",
    "repeats others' words",
    "interrupts frequently",
    "deflects accusations quickly",
    "defends others aggressively",
    "changes topics suddenly",
    "overly eager to vote",
    "inconsistent reasoning"
]