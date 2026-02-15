"""Long-term memory system that used ChromaDB for persistent fact storage across sessions."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Dict, Any

# Disable Chroma telemetry to avoid noisy runtime telemetry client errors.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_PRODUCT_TELEMETRY_IMPL", "chromadb.telemetry.product.noop.Noop")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "chromadb.telemetry.product.noop.Noop")

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except Exception:
    CHROMADB_AVAILABLE = False

# I had stored facts in a ChromaDB collection that persisted across server restarts
_DB_PATH = Path("var/long_term_memory")
_DB_PATH.mkdir(parents=True, exist_ok=True)

_client = None
_collection = None


def _get_collection():
    """I had initialized the ChromaDB client and collection on first use."""
    global _client, _collection
    if not CHROMADB_AVAILABLE:
        return None
    
    if _collection is None:
        try:
            from chromadb.config import Settings
            _client = chromadb.PersistentClient(
                path=str(_DB_PATH),
                settings=Settings(anonymized_telemetry=False),
            )
        except Exception:
            _client = chromadb.PersistentClient(path=str(_DB_PATH))
        # I had created or gotten a collection for storing facts learned from conversations
        _collection = _client.get_or_create_collection(
            name="groceryguard_facts",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def _extract_facts(text: str) -> List[str]:
    """I had analyzed response text and extracted key facts/statements that were worth remembering."""
    if not text or len(text) < 20:
        return []
    
    facts = []
    
    # I had looked for statements about ingredients and their properties
    ingredient_patterns = [
        r"([A-Za-z0-9\s\-]+(?:additive|dye|preservative|ingredient|e\d+).*?[.!])",
        r"((?:sodium|red|blue|yellow|tartrazine|carmine)[A-Za-z0-9\s\-]*(?:is|causes|linked)[^.!]*[.!])",
        r"([A-Z][a-z]+ number \d+[^.!]*[.!])",
    ]
    
    for pattern in ingredient_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            fact = match.group(1).strip()
            if len(fact) > 15 and len(fact) < 500:
                facts.append(fact)
    
    # I had also extracted direct statements about watchlist items
    if "watchlist" in text.lower():
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if "watchlist" in sentence.lower() and len(sentence) > 15:
                facts.append(sentence.strip())
    
    return facts[:5]  # Return top 5 facts per response


def learn_facts(text: str, source: str = "unknown") -> int:
    """I had extracted and stored facts from assistant responses for future reference."""
    if not CHROMADB_AVAILABLE:
        return 0
    
    collection = _get_collection()
    if not collection:
        return 0
    
    facts = _extract_facts(text)
    if not facts:
        return 0
    
    # I had added each fact to the collection with metadata about when/where it came from
    for i, fact in enumerate(facts):
        try:
            collection.add(
                ids=[f"{source}_fact_{i}_{hash(fact) % 1000000}"],
                documents=[fact],
                metadatas=[{"source": source, "type": "ingredient_fact"}]
            )
        except Exception:
            # I had silently skipped facts that failed to store
            pass
    
    return len(facts)


def recall_relevant_facts(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """I had searched for facts from memory that were relevant to the current query."""
    if not CHROMADB_AVAILABLE:
        return []
    
    collection = _get_collection()
    if not collection:
        return []
    
    try:
        # I search for similar facts using semantic similarity
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"type": "ingredient_fact"}
        )
        
        if not results or not results["documents"] or not results["documents"][0]:
            return []
        
        # I format the facts for inclusion in the conversation
        facts = []
        for i, doc in enumerate(results["documents"][0]):
            distance = results["distances"][0][i] if results.get("distances") else 0
            # I only include facts with reasonable semantic similarity (distance < 1.5)
            if distance < 1.5:
                facts.append({
                    "fact": doc,
                    "similarity": 1 - distance,  # Convert distance to similarity score
                })
        
        return facts
    except Exception:
        # I gracefully handle any ChromaDB errors
        return []


def get_memory_stats() -> Dict[str, Any]:
    """I return statistics about what has been learned in long-term memory"""
    if not CHROMADB_AVAILABLE:
        return {"available": False, "reason": "ChromaDB not installed"}
    
    collection = _get_collection()
    if not collection:
        return {"available": False, "reason": "Collection not initialized"}
    
    try:
        count = collection.count()
        return {
            "available": True,
            "total_facts_stored": count,
            "storage_path": str(_DB_PATH)
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}
