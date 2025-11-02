# app.py
"""Streamlit frontend for AI Mafia Game"""

import streamlit as st
import time
from game_engine import MafiaGame
from config import API_PROVIDER, DEFAULT_NUM_AGENTS, DEFAULT_NUM_MAFIA, MAX_AGENTS

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
    .hint-msg {
        background-color: rgba(138, 43, 226, 0.15);
        border-left-color: #8a2be2;
        font-weight: bold;
        font-size: 1.1em;
        box-shadow: 0 4px 6px rgba(138, 43, 226, 0.3);
    }
    .will-msg {
        background-color: rgba(255, 140, 0, 0.15);
        border-left-color: #ff8c00;
        font-weight: bold;
        font-size: 1.05em;
        box-shadow: 0 4px 6px rgba(255, 140, 0, 0.3);
    }
    .edited-will-msg {
        background-color: rgba(220, 20, 60, 0.15);
        border-left-color: #dc143c;
        font-style: italic;
        box-shadow: 0 4px 6px rgba(220, 20, 60, 0.3);
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
    num_agents = st.slider("Number of Agents", 3, MAX_AGENTS, DEFAULT_NUM_AGENTS)
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
    
    st.divider()
    
    # Save transcript button
    if st.session_state.game:
        if st.button("💾 Save Transcript", use_container_width=True):
            try:
                filename = st.session_state.game.save_transcript()
                st.success(f"✅ Transcript saved to: `{filename}`")
            except Exception as e:
                st.error(f"Error saving transcript: {e}")
    
    # Info box
    st.divider()
    st.info("""
    **How it works:**
    
    1. **Orchestrator**: A smart manager decides *who* should speak next, based on conversation flow, accusations, and fairness.
    2. **Generator Module**: Decides *what* to say, using context and agent personality.
    3. **Personalities**: Each agent has unique traits and strategies.
    4. **Scratchpad Memory**: Agents learn from past games.
    5. Mafia agents are cunning deceivers, Villagers are analytical detectives.
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
    ## 🕵️‍♂️ About This Project

    **🤖 AI Mafia** uses a central **🎛️ Orchestrator** to manage the flow of conversation.
    Instead of each agent deciding when to speak, the Orchestrator:

    * 🛡️ Gives **defense priority** to accused agents
    * 💬 Forces **quiet agents** to speak if they've been silent too long
    * 🔁 Detects **echo chambers** and breaks repetitive loops
    * 🚫 Prevents the **same agent** from speaking twice in a row

    This leads to more **realistic, dynamic, and unpredictable** conversations — just like a real Mafia game! 🎭

    Each agent has:

    1. 🧠 **Orchestrator** - Decides *who* speaks next, based on context and fairness
    2. 💬 **Generator** - Crafts **context-aware, evidence-based** responses
    3. 😎 **Personality & Memory** - Unique traits and learning from past games

    Agents **interrupt**, **defend**, **accuse**, and **strategize** in a lifelike social deduction simulation. 🔍🕵️‍♀️
                """)

else:
    # Game is active - show conversation and agents side by side, always visible
    col1, col2 = st.columns([2, 1])

    # Conversation column
    with col1:
        st.subheader("💬 Conversation")
        conversation_container = st.container(height=600)
        with conversation_container:
            for msg in st.session_state.game.conversation_history:
                if msg.get('is_system'):
                    content = msg["content"]
                    msg_class = "system-msg"
                    if "OPENING HINT:" in content:
                        msg_class = "hint-msg"
                    elif "LAST WILL:" in content:
                        msg_class = "will-msg"
                    elif "WILL EDITED" in content:
                        msg_class = "edited-will-msg"
                    st.markdown(
                        f'<div class="message-box {msg_class}">🔔 <strong>System:</strong> {content}</div>',
                        unsafe_allow_html=True
                    )
                else:
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

    # Agents column (always visible, rendered before spinner)
    with col2:
        st.subheader("👥 Agents")
        agent_states = st.session_state.game.get_agent_states()
        eliminated = st.session_state.game.eliminated_agents
        for agent_state in agent_states:
            role_emoji = "🔴" if agent_state['role'] == "mafia" else "🔵"
            typing_class = "typing" if agent_state['is_typing'] else ""
            typing_indicator = " ✍️ typing..." if agent_state['is_typing'] else ""
            is_eliminated = agent_state['name'] in eliminated
            eliminated_style = "opacity: 0.4; text-decoration: line-through;" if is_eliminated else ""
            eliminated_badge = " ❌ ELIMINATED" if is_eliminated else ""
            st.markdown(
                f'<div class="agent-card {typing_class}" style="{eliminated_style}">' 
                f'{role_emoji} <strong>{agent_state["name"]}</strong>{typing_indicator}{eliminated_badge}<br>'
                f'<small>Messages: {agent_state["message_count"]}</small>'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # Auto-run rounds AFTER both columns are rendered
    if st.session_state.game_running and st.session_state.game.is_running:
        try:
            round_messages = st.session_state.game.run_round()
            if round_messages:
                st.session_state.round_count += 1
            if not st.session_state.game.is_running:
                st.session_state.game_running = False
                st.success("🎮 Game ended! Check the conversation for results.")
                st.rerun()
        except Exception as e:
            st.warning(f"⚠️ Rate limit or API error. Game will retry automatically.")
            print(f"Error in game round: {e}")
        time.sleep(0.5)
        st.rerun()

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #888; padding: 20px;'>
    <p>Powered by a smart Orchestrator for realistic AI conversation | Built with Streamlit</p>
    <p>Toggle API providers in <code>config.py</code></p>
</div>
""", unsafe_allow_html=True)