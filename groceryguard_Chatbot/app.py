"""This is the entry point for running the GroceryGuard ChatBot server."""
import sys
from pathlib import Path

# I need to add the project root to the path so I can import from src/
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now I import the FastAPI app from the main guard_server module
from src.groceryguard_core.guard_server import app

if __name__ == "__main__":
    import uvicorn
    # I start the server on localhost:8001 so I can test the chat interface locally
    uvicorn.run(app, host="127.0.0.1", port=8001)
