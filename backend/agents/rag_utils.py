# backend/agents/rag_utils.py
import json
import os
from typing import Dict, List

# Simulate a knowledge base (KB) file location
KB_FILE_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")

def load_knowledge_base() -> Dict[str, str]:
    """
    Loads a simulated knowledge base from a JSON file.
    In a real RAG system, this would be the vector store's index.
    """
    try:
        if not os.path.exists(KB_FILE_PATH):
             # Create a dummy KB if it doesn't exist
            print(f"INFO: Creating dummy knowledge base at {KB_FILE_PATH}")
            dummy_kb = {
                "common_bugs": "If a game uses WebGL, check for context loss on tab switch. Common game breaking bugs involve rapid input sequences. The 'start' button often has the ID '#game-start'.",
                "target_url_details": "The target game often has input fields with class '.game-input', the final score is usually in a div with ID 'final-score', and the summation result is in '#result-value'.",
                "optimization_tips": "Prioritize tests that focus on user input boundary conditions (e.g., very long or very short numbers) for game testing."
            }
            with open(KB_FILE_PATH, 'w') as f:
                json.dump(dummy_kb, f, indent=2)

        with open(KB_FILE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return {}

class RAGSystem:
    def __init__(self):
        self.knowledge_base = load_knowledge_base()
        print(f"INFO: RAG System loaded with {len(self.knowledge_base)} knowledge chunks.")

    def retrieve(self, query: str) -> str:
        """
        Simulates retrieval by finding relevant knowledge chunks based on
        keywords in the query.
        """
        query = query.lower()
        retrieved_context = []

        if "bug" in query or "error" in query or "issue" in query:
            retrieved_context.append(f"Common Bugs/Issues: {self.knowledge_base.get('common_bugs', '')}")
        if "target" in query or "url" in query or "game" in query:
            retrieved_context.append(f"Target Details: {self.knowledge_base.get('target_url_details', '')}")
        if "test case" in query or "generation" in query or "plan" in query:
            retrieved_context.append(f"Planning Tips: {self.knowledge_base.get('optimization_tips', '')}")

        return "\n".join(retrieved_context)
