# backend/agents/ranker.py
import random

class RankerAgent:
    """
    Rank candidate tests. Replace with an LLM-based ranker if desired.
    This simple ranker prefers higher 'difficulty' and variety.
    """

    def __init__(self):
        pass

    def rank_candidates(self, candidates):
        # simple score = difficulty + randomness bias to break ties
        for c in candidates:
            c["_score"] = c.get("difficulty", 0) + random.random() * 0.1
        ranked = sorted(candidates, key=lambda x: x["_score"], reverse=True)
        # return top N with metadata
        return ranked
