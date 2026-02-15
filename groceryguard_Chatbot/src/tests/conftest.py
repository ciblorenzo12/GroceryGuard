"""Pytest configuration and shared fixtures that had been used for GroceryGuard tests."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Had added src to path so we could import groceryguard_core modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def temp_conversations_dir():
    """Created temporary conversations directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_conversation_file(temp_conversations_dir):
    """Created a sample conversation file for testing."""
    conv_id = "test_conv_123"
    conv_path = Path(temp_conversations_dir) / f"{conv_id}.json"
    
    sample_data = [
        {"role": "user", "content": "What's in peanut butter?"},
        {"role": "assistant", "content": "Peanut butter contains peanuts, which are legumes."},
        {"role": "user", "content": "I'm allergic to peanuts!"},
        {"role": "assistant", "content": "Thank you for letting me know. I'll avoid peanut-related recommendations."},
    ]
    
    with open(conv_path, 'w') as f:
        json.dump(sample_data, f)
    
    return conv_path


@pytest.fixture
def sample_ingredients_list():
    """Sample ingredient list for tool testing."""
    return [
        "high fructose corn syrup",
        "artificial sweetener",
        "azodicarbonamide",
        "potassium brominate",
        "eggs",
        "water",
        "salt",
    ]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response structure."""
    return {
        "id": "chatcmpl-8j7k9l",
        "object": "chat.completion",
        "created": 1698765432,
        "model": "gpt-4o-mini",
        "usage": {
            "prompt_tokens": 145,
            "completion_tokens": 89,
            "total_tokens": 234,
        },
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "High fructose corn syrup is on the watchlist due to health concerns.",
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }
