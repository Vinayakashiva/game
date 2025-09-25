# backend/agents/orchestrator.py
import os
import asyncio
import sys
from typing import List, Dict, Any
from backend.agents.executor import ExecutorAgent
from backend.agents.analyzer import AnalyzerAgent

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "artifacts")


class OrchestratorAgent:
    def __init__(self):
        self.executor = ExecutorAgent()
        self.analyzer = AnalyzerAgent()
        # Fix for Windows: Ensure the correct event loop policy is set for subprocesses.
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def _run_one(self, test: Dict[str, Any]):
        # ensure per-test directory
        out_dir = os.path.join(ARTIFACTS_DIR)
        result = await self.executor.run_test(test, out_dir)
        # run analyzer repeatability checks (re-run small quick check)
        analysis = await self.analyzer.analyze(test, result)
        result["analysis"] = analysis
        return result

    async def run(self, selected_tests: List[Dict[str, Any]]):
        # Start browser once before the test run
        await self.executor.start_browser()

        # run tests concurrently with a reasonable concurrency limit
        concurrency = 5  # or even 10
        semaphore = asyncio.Semaphore(concurrency)
        results = []

        async def sem_run(t: Dict[str, Any]):
            async with semaphore:
                return await self._run_one(t)

        tasks = [asyncio.create_task(sem_run(t)) for t in selected_tests]
        for t in tasks:
            results.append(await t)

        # produce final report JSON
        report = {
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r["verdict"] == "pass"),
                "failed": sum(1 for r in results if r["verdict"] != "pass")
            },
            "tests": results
        }

        # Stop browser once after the test run
        await self.executor.stop_browser()

        return report
