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
    "temperature": 0.9,
    "max_tokens": 150
}

GROK_CONFIG = {
    "api_key": os.getenv("GROK_API_KEY", ""),  # Fetch from environment variable
    "model": "grok-beta",
    "temperature": 0.9,
    "max_tokens": 150
}

# Game Settings
DEFAULT_NUM_AGENTS = 5
DEFAULT_NUM_MAFIA = 2
MIN_SPEAK_INTERVAL = 3  # Minimum seconds between agent messages
CONVERSATION_CONTEXT_SIZE = 5  # Number of recent messages to consider
VOTING_MESSAGE_THRESHOLD = 20  # Trigger voting after this many messages