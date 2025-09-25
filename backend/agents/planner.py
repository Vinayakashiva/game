# backend/agents/planner.py
import random
import uuid

class PlannerAgent:
    """
    Generates candidate test cases (lighter version for faster execution).
    By default this uses a simple heuristic generator so it works offline.
    Replace generate_candidates with a LangChain + LLM planner if you want smarter tests.
    """

    def __init__(self):
        pass

    def _make_action(self, name, params=None):
        return {"action": name, "params": params or {}}

    def make_test(self, tgt_url, difficulty):
        """
        Build a single test with fewer steps and shorter timeouts for speed.
        """
        steps = []
        # Go to the target URL quickly
        steps.append(self._make_action("goto", {"url": tgt_url}))
        steps.append(self._make_action("wait_for", {"selector": "body", "timeout": 2000}))

        # Try clicking start button if it exists (skip if not)
        steps.append(self._make_action("click_if", {"selector": ".start-button"}))

        # Create fewer random number inputs (1–2)
        inputs = random.randint(1, 2)
        for _ in range(inputs):
            steps.append(self._make_action("type_random_number", {"length": random.randint(1, 2)}))

        # Optionally submit (will skip if no submit button)
        steps.append(self._make_action("submit", {}))

        # Verify existence of a result element or score quickly
        steps.append(self._make_action("check_selector", {"selector": ".score, .result, #result"}))

        return {
            "id": str(uuid.uuid4())[:8],
            "title": f"Auto test (difficulty={difficulty:.2f})",
            "difficulty": difficulty,
            "steps": steps
        }

    def generate_candidates(self, target_url, n=20):
        """
        Generate a batch of candidate tests.
        """
        candidates = []
        for _ in range(n):
            difficulty = random.random()
            candidates.append(self.make_test(target_url, difficulty))

        # Add one very simple deterministic test
        candidates.append({
            "id": str(uuid.uuid4())[:8],
            "title": "Deterministic open-and-check",
            "difficulty": 0.1,
            "steps": [
                self._make_action("goto", {"url": target_url}),
                self._make_action("wait_for", {"selector": "body", "timeout": 2000}),
                self._make_action("check_selector", {"selector": "body"})
            ]
        })
        return candidates
