# GroceryGuard Chatbot

GroceryGuard is an AI-powered FastAPI chatbot designed to help users understand food ingredient labels, identify potential allergens, and provide ingredient safety information. It uses OpenAI's GPT models, a local knowledge base, and ChromaDB for long-term memory.

## What does it do?
- Scans ingredient lists for watchlist items (like allergens or additives)
- Looks up ingredient risks and provides explanations
- Answers questions about food safety and ingredients
- Remembers facts from previous conversations to improve future answers
- Redacts sensitive information and enforces safety policies

## How does it work?
- The backend is built with FastAPI and streams responses to users
- Integrates with OpenAI's API for natural language understanding and tool use
- Uses ChromaDB to store and recall facts across sessions
- Includes rate limiting and safety checks to protect users
- Can run in offline mode using a local knowledge base if the API is unavailable

## How do I use it?
1. **Install dependencies:**
	```sh
	pip install -r requirements.txt
	```
2. **Set your OpenAI API key:**
	- Create a `.env` file in the project root with:
	  ```env
	  OPENAI_API_KEY=sk-...
	  ```
3. **Run the server:**
	```sh
	python -m src.groceryguard_core.guard_server
	```
4. **Access the UI:**
	- Open your browser to [http://localhost:8000/ui](http://localhost:8000/ui)

## How do I run tests?
1. Make sure all dependencies are installed (see above).
2. Run the test suite:
	```sh
	pytest
	```

## API Endpoints
- `POST /chat` — streamed assistant text (core chat endpoint).
- `POST /chat_structured` — schema-enforced JSON response with fields:
	- `answer`
	- `risk_level` (`low|medium|high|unknown`)
	- `flagged_ingredients` (array)
	- `recommended_action`
- `GET /health` — service health and long-term memory stats.

## How do I build for production?
1. Run the build script:
	```sh
	python build.py
	```
2. The build output will be in the `build/` directory, including code, data, and requirements.

## Deployment
- Deploy the contents of the `build/` directory to your server or cloud environment.
- Make sure to set your `.env` and install dependencies with `pip install -r requirements.txt` in the build folder.

## Evaluation Protocol & Outputs
Run the 20-prompt evaluation suite:

```sh
python scripts/run_guard_eval.py
```

Expected outputs:
- `results/metrics.json` — task success, latency, token, and cost metrics.
- `results/transcripts/` — per-test transcripts and parsed per-turn metrics.
- `var/eval_results.json` — raw evaluation summary.

## Project Structure
- `src/groceryguard_core/` — Core backend modules (memory, tools, server, safety)
- `web/` — Frontend files for the UI (served at `/ui`)
- `data/` — Knowledge base and watchlist data (CSV, Markdown)
- `build/` — Production build output
- `tests/` — Automated test suite (in `src/tests/`)

## Why use GroceryGuard?
GroceryGuard helps you make safer, more informed food choices by explaining ingredients in plain language and flagging potential risks. It remembers what it has learned, so it gets smarter over time.

---

*This project was built to make food label information more accessible and understandable for everyone, and as a final project thesis.*
