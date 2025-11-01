# AI Mafia

AI Mafia is an advanced simulation of the classic social deduction game "Mafia," where AI agents play as villagers and mafia members, each with unique personalities, memory, and evolving strategies. The game is designed for research, experimentation, and entertainment, showcasing multi-agent reasoning, deception, and emergent behavior.

## Features

- **AI Agents with Personalities:** Each agent has a unique personality profile (aggressive, analytical, charismatic, etc.) that influences their speech and strategy.
- **Persistent Memory:** Agents maintain a scratchpad of past games, learning from wins and losses to adapt their tactics.
- **Dynamic Conversation:** Agents converse in a shared chat, analyze conversation context, and decide when and how to speak.
- **Voting & Elimination:** After a set number of messages, agents vote to eliminate a suspect. Voting history is tracked for pattern analysis.
- **Death Wills & Mafia Editing:** Eliminated villagers leave cryptic wills. Mafia can edit these to obscure clues.
- **Win Condition Detection:** The game automatically detects and announces when villagers or mafia win.
- **Transcript Saving:** Full game transcripts are saved for review and analysis.
- **API-Driven Language Models:** Supports OpenAI and Google Generative AI for agent dialogue generation.
- **Thread-Safe Engine:** Uses locks to ensure safe concurrent access to shared conversation state.

## Installation

1. **Clone the repository:**

   ```sh
   git clone https://github.com/aevnum/ai-mafia.git
   cd ai-mafia
   ```

2. **Install dependencies:**

   Ensure you have Python 3.8+ installed. Then run:

   ```sh
   pip install -r requirements.txt
   ```

3. **Set up API keys:**

   - For OpenAI: Set the `OPENAI_API_KEY` environment variable.
   - For Google Generative AI: Set the `GOOGLE_API_KEY` environment variable.
   - You can use a `.env` file for convenience.

4. **Run the game:**

   ```sh
   python app.py
   ```

   (Or use Streamlit if a UI is provided: `streamlit run app.py`)

## File Structure

- `agent.py` — Defines the AI agent, personality, memory, and decision logic.
- `game_engine.py` — Orchestrates the game, conversation, voting, and win conditions.
- `api_handler.py` — Handles API calls to language models.
- `config.py` — Game and agent configuration.
- `personalities.py` — Defines agent personality templates.
- `scratchpads/` — Persistent memory for each agent.
- `transcripts/` — Saved game transcripts.
- `requirements.txt` — Python dependencies.

## Customization

- Add or modify personalities in `personalities.py`.
- Adjust game parameters in `config.py`.
- Plug in different language models via `api_handler.py`.

## License

MIT License. See `LICENSE` for details.

## Acknowledgments

- Inspired by classic Mafia/Werewolf games and AI research in multi-agent systems.
- Uses OpenAI and Google Generative AI APIs for natural language generation.
