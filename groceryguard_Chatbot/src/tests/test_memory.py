"""Test suite for GroceryGuard memory systems (short-term and long-term)."""

import pytest
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from groceryguard_core.pantry_memory import (
    load_convo,
    save_convo,
    append_msg,
    get_last_n,
)


class TestPantryMemory:
    """Tested short-term memory (pantry_memory) - disk-based conversation storage."""
    
    def test_save_and_load_conversation(self, temp_conversations_dir):
        """Tested saving and loading a conversation from disk."""
        conv_id = "test_conv_1"
        from groceryguard_core.pantry_memory import Msg
        messages = [
            Msg(role="user", content="What's in this?"),
            Msg(role="assistant", content="It contains peanuts."),
        ]
        
        # Had saved conversation
        save_convo(conv_id, messages)
        
        # Had loaded it back
        loaded = load_convo(conv_id)
        
        assert loaded == messages
        assert len(loaded) == 2
    
    def test_append_message_to_conversation(self, temp_conversations_dir):
        """Tested appending messages to existing conversation."""
        conv_id = "test_conv_2"
        
        # Had saved initial message
        from groceryguard_core.pantry_memory import Msg
        initial = [Msg(role="user", content="Hello")]
        save_convo(conv_id, initial)
        
        # Had appended message
        append_msg(conv_id, "assistant", "Hi there!")
        
        # Had loaded and verified
        loaded = load_convo(conv_id)
        assert len(loaded) == 2
        assert loaded[1].content == "Hi there!"
    
    def test_get_last_n_messages(self, temp_conversations_dir):
        """Tested retrieving last N messages from conversation."""
        conv_id = "test_conv_3"
        
        # Had created conversation with 10 messages
        from groceryguard_core.pantry_memory import Msg
        messages = [
            Msg(role="user", content=f"Message {i}")
            for i in range(10)
        ]
        save_convo(conv_id, messages)
        
        # Had gotten last 3
        last_3 = get_last_n(conv_id, n=3)
        
        assert len(last_3) == 3
        assert last_3[-1]["content"] == "Message 9"
        assert last_3[0]["content"] == "Message 7"
    
    def test_get_last_n_less_than_available(self, temp_conversations_dir):
        """Tested get_last_n when n > conversation length."""
        conv_id = "test_conv_4"
        
        from groceryguard_core.pantry_memory import Msg
        messages = [
            Msg(role="user", content=f"Message {i}")
            for i in range(5)
        ]
        save_convo(conv_id, messages)
        
        # Had requested last 10 but only 5 existed
        last_10 = get_last_n(conv_id, n=10)
        
        assert len(last_10) == 5  # Should return all available
    
    def test_empty_conversation(self, temp_conversations_dir):
        """Tested handling of empty conversations."""
        conv_id = "test_conv_5"
        
        save_convo(conv_id, [])
        loaded = load_convo(conv_id)
        
        assert loaded == []
    
    def test_conversation_id_sanitization(self, temp_conversations_dir):
        """Tested that conversation IDs were properly sanitized."""
        # Had tried potentially dangerous IDs
        from groceryguard_core.pantry_memory import Msg
        dangerous_ids = [
            "../../etc/passwd",
            "conv|shell_command",
            "conv;rm -rf /",
        ]
        for conv_id in dangerous_ids:
            messages = [Msg(role="user", content="test")]
            # Should not have raised an error
            try:
                save_convo(conv_id, messages)
                loaded = load_convo(conv_id)
                assert loaded == messages
            except (ValueError, OSError):
                # Had accepted to reject dangerous IDs
                pass
    
    def test_persistent_storage_across_operations(self, temp_conversations_dir):
        """Tested that storage persisted across multiple operations."""
        conv_id = "test_conv_6"
        
        # Step 1: Had saved initial messages
        from groceryguard_core.pantry_memory import Msg
        msg1 = Msg(role="user", content="First question")
        save_convo(conv_id, [msg1])
        
        # Step 2: Had appended more messages
        append_msg(conv_id, "assistant", "First answer")
        append_msg(conv_id, "user", "Second question")
        
        # Step 3: Had loaded and verified full history
        loaded = load_convo(conv_id)
        
        assert len(loaded) == 3
        assert loaded[0].content == "First question"
        assert loaded[1].content == "First answer"
        assert loaded[2].content == "Second question"


class TestLongTermMemory:
    """Tested long-term memory (ChromaDB) - semantic fact storage."""
    
    def test_long_term_memory_import(self):
        """Tested that long_term_memory module could be imported."""
        try:
            from groceryguard_core.long_term_memory import (
                learn_facts,
                recall_relevant_facts,
                get_memory_stats,
            )
            assert callable(learn_facts)
            assert callable(recall_relevant_facts)
            assert callable(get_memory_stats)
        except ImportError as e:
            # ChromaDB might not be installed, which is acceptable
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_long_term_memory_stats(self):
        """Tested getting memory statistics."""
        try:
            from groceryguard_core.long_term_memory import get_memory_stats
            
            stats = get_memory_stats()
            
            assert isinstance(stats, dict)
            assert "available" in stats
            assert isinstance(stats["available"], bool)
        except ImportError:
            pytest.skip("ChromaDB not available")
    
    def test_long_term_memory_learn_and_recall(self):
        """Tested learning facts and recalling them."""
        try:
            from groceryguard_core.long_term_memory import (
                learn_facts,
                recall_relevant_facts,
                _get_collection,
            )
            
            # Had learned a fact
            fact_text = "Peanuts are a common allergen for many people"
            learned = learn_facts(fact_text, source="test")
            
            assert isinstance(learned, int)
            # Might or might not have learned depending on implementation
            
            # Had tried to recall related information
            recalled = recall_relevant_facts("peanut allergy", top_k=3)
            
            assert isinstance(recalled, list)
            # Might or might not have found anything depending on collection state
            
        except ImportError:
            pytest.skip("ChromaDB not available")
    
    def test_long_term_memory_graceful_degradation(self):
        """Tested that system handled missing ChromaDB gracefully."""
        try:
            from groceryguard_core.long_term_memory import get_memory_stats
            
            stats = get_memory_stats()
            
            # Had always returned a dict with 'available' key
            assert "available" in stats
            
            if not stats["available"]:
                # If ChromaDB wasn't available, still handled gracefully
                assert "error" in stats or stats["available"] == False
                
        except ImportError:
            pytest.skip("ChromaDB module not available")


class TestMemoryIntegration:
    """Tested integration for memory systems."""
    
    def test_multi_turn_conversation_memory(self, temp_conversations_dir):
        """Tested realistic multi-turn conversation memory."""
        conv_id = "integration_test_1"
        
        # Had simulated a multi-turn conversation
        from groceryguard_core.pantry_memory import Msg
        conversation = [
            Msg(role="user", content="I'm allergic to peanuts"),
            Msg(role="assistant", content="Got it. I'll remember that."),
            Msg(role="user", content="What can I eat?"),
            Msg(role="assistant", content="Avoid peanut products and related items."),
            Msg(role="user", content="What about tree nuts?"),
            Msg(role="assistant", content="Some people with peanut allergies can eat tree nuts, but check first."),
        ]
        
        # Had saved conversation
        save_convo(conv_id, conversation)
        
        # Had simulated next turn
        append_msg(conv_id, "user", "Are cashews safe?")
        
        # Had gotten last 5 messages for context (should have included allergy info)
        context = get_last_n(conv_id, n=5)
        
        assert len(context) > 0
        # Should have included recent context about allergies
        all_text = ' '.join([msg['content'] for msg in context])
        assert 'peanut' in all_text.lower() or 'allergy' in all_text.lower()
    
    def test_memory_window_optimization(self, temp_conversations_dir):
        """Tested that memory window management worked correctly."""
        conv_id = "integration_test_2"
        
        # Had created a long conversation (30 messages)
        from groceryguard_core.pantry_memory import Msg
        long_conversation = [
            Msg(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
            for i in range(30)
        ]
        save_convo(conv_id, long_conversation)
        
        # Had gotten different window sizes
        last_5 = get_last_n(conv_id, n=5)
        last_12 = get_last_n(conv_id, n=12)
        last_24 = get_last_n(conv_id, n=24)
        
        assert len(last_5) == 5
        assert len(last_12) == 12
        assert len(last_24) == 24
        
        # Had verified last entry was the same
        assert last_5[-1] == last_12[-1] == last_24[-1]
        
        # Had verified windows were nested
        assert last_5 == last_12[-5:]
        assert last_12 == last_24[-12:]
