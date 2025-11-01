# app.py
"""Streamlit frontend for AI Mafia Game"""

import streamlit as st
import time
from game_engine import MafiaGame
from config import API_PROVIDER, DEFAULT_NUM_AGENTS, DEFAULT_NUM_MAFIA

# Page config
st.set_page_config(
    page_title="AI Mafia Game",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    .message-box {
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .villager-msg {
        background-color: rgba(110, 181, 255, 0.1);
        border-left-color: #6eb5ff;
    }
    .mafia-msg {
        background-color: rgba(255, 107, 107, 0.1);
        border-left-color: #ff6b6b;
    }
    .system-msg {
        background-color: rgba(255, 217, 61, 0.1);
        border-left-color: #ffd93d;
    }
    .agent-card {
        padding: 10px;
        border-radius: 8px;
        margin: 8px 0;
        background-color: rgba(255, 255, 255, 0.05);
        border: 2px solid transparent;
    }
    .agent-card.typing {
        border-color: #6eb5ff;
        background-color: rgba(110, 181, 255, 0.15);
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    h1, h2, h3 {
        color: #ff6b6b !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'game' not in st.session_state:
    st.session_state.game = None
if 'game_running' not in st.session_state:
    st.session_state.game_running = False
if 'round_count' not in st.session_state:
    st.session_state.round_count = 0
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()

# Header
st.title("🎭 AI Mafia Game")
st.markdown("### Watch AI agents learn **when** to speak, not just **what** to say")

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Provider
    api_provider = st.selectbox(
        "API Provider",
        ["gemini", "grok"],
        index=0 if API_PROVIDER == "gemini" else 1,
        help="Select which AI provider to use"
    )
    
    # API Key input (optional - only if not in .env)
    from config import GEMINI_CONFIG, GROK_CONFIG
    existing_key = GEMINI_CONFIG['api_key'] if api_provider == "gemini" else GROK_CONFIG['api_key']
    
    api_key_label = "Gemini API Key" if api_provider == "gemini" else "Grok API Key"
    api_key_help = f"{'✅ Loaded from .env' if existing_key else '⚠️ Not found in .env'} | Get your key from: " + (
        "https://aistudio.google.com/app/apikey" if api_provider == "gemini"
        else "https://console.x.ai/"
    )
    
    api_key = st.text_input(
        api_key_label,
        value="",
        placeholder="Leave empty if using .env" if existing_key else "Enter your API key",
        type="password",
        help=api_key_help
    )
    
    # Use .env key if no key is entered
    api_key = api_key or existing_key
    
    st.divider()
    
    # Game settings
    num_agents = st.slider("Number of Agents", 3, 10, DEFAULT_NUM_AGENTS)
    num_mafia = st.slider("Number of Mafia", 1, min(3, num_agents-1), DEFAULT_NUM_MAFIA)
    
    st.divider()
    
    # Game controls
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🎮 Start Game", disabled=st.session_state.game_running, use_container_width=True):
            if not api_key:
                st.error("Please enter your API key or add it to .env file!")
            else:
                try:
                    # Only update config if user provided a key (and it's different from .env)
                    user_entered_key = st.session_state.get('api_key_input', '')
                    if user_entered_key and user_entered_key != existing_key:
                        if api_provider == "gemini":
                            GEMINI_CONFIG['api_key'] = api_key
                        else:
                            GROK_CONFIG['api_key'] = api_key
                    
                    # Initialize game
                    st.session_state.game = MafiaGame(
                        num_agents=num_agents,
                        num_mafia=num_mafia,
                        api_provider=api_provider
                    )
                    st.session_state.game.start()
                    st.session_state.game_running = True
                    st.session_state.round_count = 0
                    st.success("Game started!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error starting game: {e}")
    
    with col2:
        if st.button("⏹️ Stop Game", disabled=not st.session_state.game_running, use_container_width=True):
            if st.session_state.game:
                st.session_state.game.stop()
                st.session_state.game_running = False
                st.info("Game stopped.")
                st.rerun()
    
    # Info box
    st.divider()
    st.info("""
    **How it works:**
    
    1. **Scheduler Module**: Decides *when* each agent should speak
    2. **Generator Module**: Decides *what* to say
    3. Agents interrupt, stay silent, and adapt their behavior
    4. Mafia agents become more talkative to deflect suspicion
    """)
    
    # Display stats if game is running
    if st.session_state.game:
        st.divider()
        st.subheader("📊 Statistics")
        stats = st.session_state.game.get_statistics()
        st.metric("Total Messages", stats['total_messages'])
        st.metric("Rounds Completed", st.session_state.round_count)

# Main content area
if not st.session_state.game:
    # Welcome screen
    st.info("👈 Configure settings in the sidebar and click **Start Game** to begin!")
    
    st.markdown("""
    ## About This Project
    
    This is an implementation of the "Time to Talk" paper concept, where AI agents learn:
    
    - ⏰ **When to speak**: Strategic timing based on conversation flow
    - 💬 **What to say**: Context-aware responses based on their role
    - 🤫 **When to stay silent**: Strategic silence as a tactic
    - 🎯 **Adaptive behavior**: Mafia agents deflect, villagers investigate
    
    ### The Two-Part Brain
    
    Each agent has:
    1. **Scheduler**: Analyzes conversation flow and decides if now is the right time to speak
    2. **Generator**: Crafts appropriate responses based on role and context
    
    This creates natural, human-like conversations where agents interrupt, build on each other's points,
    and engage in realistic social deduction gameplay!
    """)

else:
    # Game is active - show conversation and agents
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("💬 Conversation")
        
        # Auto-run rounds
        if st.session_state.game_running:
            with st.spinner("Agents thinking..."):
                try:
                    # Run a round
                    round_messages = st.session_state.game.run_round()
                    if round_messages:
                        st.session_state.round_count += 1
                except Exception as e:
                    st.warning(f"⚠️ Rate limit or API error. Game will retry automatically.")
                    print(f"Error in game round: {e}")
            
            # Small delay before rerun
            time.sleep(1)
            st.rerun()
        
        # Display conversation
        conversation_container = st.container(height=600)
        with conversation_container:
            for msg in st.session_state.game.conversation_history:
                if msg.get('is_system'):
                    st.markdown(
                        f'<div class="message-box system-msg">🔔 <strong>System:</strong> {msg["content"]}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    # Get agent role
                    agent = next((a for a in st.session_state.game.agents if a.name == msg['agent']), None)
                    role_class = "mafia-msg" if agent and agent.role == "mafia" else "villager-msg"
                    role_badge = "🔴 MAFIA" if agent and agent.role == "mafia" else "🔵 VILLAGER"
                    
                    st.markdown(
                        f'<div class="message-box {role_class}">'
                        f'<strong>{msg["agent"]}</strong> <small>({role_badge})</small><br>'
                        f'{msg["content"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
    
    with col2:
        st.subheader("👥 Agents")
        
        agent_states = st.session_state.game.get_agent_states()
        
        for agent_state in agent_states:
            role_emoji = "🔴" if agent_state['role'] == "mafia" else "🔵"
            typing_class = "typing" if agent_state['is_typing'] else ""
            typing_indicator = " ✍️ typing..." if agent_state['is_typing'] else ""
            
            st.markdown(
                f'<div class="agent-card {typing_class}">'
                f'{role_emoji} <strong>{agent_state["name"]}</strong>{typing_indicator}<br>'
                f'<small>Messages: {agent_state["message_count"]}</small>'
                f'</div>',
                unsafe_allow_html=True
            )

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #888; padding: 20px;'>
    <p>Based on the "Time to Talk" paper | Built with Streamlit</p>
    <p>Toggle API providers in <code>config.py</code></p>
</div>
""", unsafe_allow_html=True)