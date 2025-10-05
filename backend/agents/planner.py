# backend/agents/planner.py
import random
import uuid
# Import RAG system for contextual planning
from .rag_utils import RAGSystem


class PlannerAgent:
    """
    Generates candidate test cases (lighter version for faster execution).
    Includes multi-resolution support, RAG-informed steps, and playability/correctness checks.
    """

    # Define standard target resolutions for multi-resolution support
    TARGET_RESOLUTIONS = [
        {"name": "Mobile", "width": 375, "height": 667},
        {"name": "Tablet", "width": 768, "height": 1024},
        {"name": "Desktop", "width": 1280, "height": 720},
        {"name": "Large Desktop", "width": 1920, "height": 1080},
    ]

    def __init__(self):
        # Initialize RAG System for contextual knowledge
        self.rag_system = RAGSystem()

    def _make_action(self, name, params=None):
        return {"action": name, "params": params or {}}

    def make_test(self, tgt_url, difficulty, knowledge_context=""):
        """
        Build a single test, incorporating RAG knowledge, resolution, and playability steps.
        """

        # Select a random viewport for this specific test
        resolution_data = random.choice(self.TARGET_RESOLUTIONS)
        viewport = {"width": resolution_data["width"], "height": resolution_data["height"]}
        resolution_name = resolution_data["name"]

        steps = []
        # Go to the target URL quickly
        steps.append(self._make_action("goto", {"url": tgt_url}))
        steps.append(self._make_action("wait_for", {"selector": "body", "timeout": 2000}))

        # RAG-Informed selectors (These are pulled from the simulated KB in rag_utils)
        specific_input_selector = ".game-input" if ".game-input" in knowledge_context else "input[type='text'], input[type='number']"
        start_selector = "#game-start" if "#game-start" in knowledge_context else ".play-btn, #start-button, button:contains('Start')"
        specific_score_selector = "#final-score" if "#final-score" in knowledge_context else ".score, .result, #result"

        # --- PLAYABILITY CHECK SCENARIO: Start Game Flow ---
        # 1. Try clicking the "Start" button
        steps.append(self._make_action("click_if", {"selector": start_selector}))

        # 2. CRITICAL PLAYABILITY VERIFICATION: Wait for the game input to appear
        steps.append(self._make_action("check_element_change", {
            "selector_to_check": specific_input_selector,
            "timeout": 3000,
            "description": "Verify game started by waiting for main input field to appear."
        }))
        # ------------------------------------------------

        # --- CORRECTNESS CHECK SCENARIO: Summation Verification ---
        inputs = random.randint(1, 2)
        random_inputs = []

        # 1. Input values (we must record them to calculate the expected sum)
        for _ in range(inputs):
            random_num = random.randint(1, 99)
            random_inputs.append(random_num)

            # Use the new action 'type_value'
            steps.append(self._make_action("type_value",
                                           {"selector": specific_input_selector,
                                            "value": str(random_num)}))

        # 2. Submit the form/trigger the calculation
        steps.append(self._make_action("submit", {}))

        # 3. Calculate the expected result locally
        expected_sum = sum(random_inputs)

        # 4. Use the new action 'check_value' to assert the output is correct
        steps.append(self._make_action("check_value", {
            "selector": "#result-value",  # Assumes the game's output is in this selector
            "expected_value": str(expected_sum)
        }))
        # ------------------------------------------------

        # Final structural check
        steps.append(self._make_action("check_selector", {"selector": specific_score_selector}))

        return {
            "id": str(uuid.uuid4())[:8],
            "title": f"Playability/Value Test ({resolution_name} / D={difficulty:.2f})",
            "difficulty": difficulty,
            "steps": steps,
            "context": knowledge_context,
            "viewport": viewport
        }

    def generate_candidates(self, target_url, n=20):
        """
        Generate a batch of candidate tests, enhanced with RAG and multiple resolutions.
        """
        candidates = []

        # 1. Retrieve knowledge using a general query (RAG step)
        knowledge = self.rag_system.retrieve(f"test case generation plan for game at {target_url}")

        for i in range(n):
            difficulty = random.random()
            # 2. Generate tests using the retrieved context
            candidates.append(self.make_test(target_url, difficulty, knowledge_context=knowledge))

        # Add one very simple deterministic test
        candidates.append({
            "id": str(uuid.uuid4())[:8],
            "title": "Deterministic open-and-check (Default Desktop)",
            "difficulty": 0.1,
            "steps": [
                self._make_action("goto", {"url": target_url}),
                self._make_action("wait_for", {"selector": "body", "timeout": 2000}),
                self._make_action("check_selector", {"selector": "body"})
            ],
            "context": "",
            "viewport": self.TARGET_RESOLUTIONS[2]  # Desktop
        })
        return candidates
