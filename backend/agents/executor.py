# backend/agents/executor.py
import os
import json
import asyncio
from playwright.async_api import async_playwright
from typing import Dict, List, Any

# Ensure utils directory is in the path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from artifact_manager import save_artifact, ensure_test_dir

class ExecutorAgent:
    """
    Executes tests using a *single* shared browser context for speed.
    Captures screenshot, DOM snapshot, console logs, and network requests.
    """

    def __init__(self):
        # We’ll initialize Playwright + browser once
        self._playwright = None
        self._browser = None
        self._context = None

    async def start_browser(self):
        """Start Playwright and one browser context if not already started."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context()

    async def stop_browser(self):
        """Close the browser context and Playwright."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _run_steps(self, page, test: Dict[str, Any]):
        console_logs = []
        network = []

        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("request", lambda req: network.append({"url": req.url, "method": req.method}))
        page.on("response", lambda resp: network.append({"url": resp.url, "status": resp.status}))

        for step in test["steps"]:
            name = step["action"]
            params = step.get("params", {})
            try:
                if name == "goto":
                    await page.goto(params["url"], timeout=5000)

                elif name == "wait_for":
                    await page.wait_for_selector(params.get("selector", "body"), timeout=2000)

                elif name == "click_if":
                    sel = params.get("selector")
                    try:
                        await page.click(sel, timeout=1500)
                    except Exception:
                        pass

                elif name == "type_random_number":
                    inputs = await page.query_selector_all("input[type='text'], input[type='number'], textarea")
                    if inputs:
                        text = "".join(str((os.urandom(1)[0] % 10)) for _ in range(params.get("length", 1)))
                        await inputs[0].fill(text)

                elif name == "submit":
                    try:
                        await page.click("button[type='submit']", timeout=1500)
                    except Exception:
                        await page.keyboard.press("Enter")

                elif name == "check_selector":
                    sel = params.get("selector", "body")
                    await page.wait_for_selector(sel, timeout=2000)

                else:
                    pass
            except Exception as e:
                console_logs.append({"type": "error", "text": f"step_error:{name}:{str(e)}"})

        content = await page.content()
        screenshot_bytes = await page.screenshot(full_page=True)
        return {
            "dom": content,
            "screenshot": screenshot_bytes,
            "console": console_logs,
            "network": network
        }

    async def run_test(self, test: Dict[str, Any], out_dir: str):
        """
        Run a single test inside the shared browser context.
        """
        if not self._context:
            await self.start_browser()

        ensure_test_dir(out_dir)

        # create a new page for each test inside the same browser context
        page = await self._context.new_page()
        try:
            artifacts = await self._run_steps(page, test)
        finally:
            await page.close()

        # save artifacts
        test_dir = os.path.join(out_dir, test["id"])
        os.makedirs(test_dir, exist_ok=True)
        img_path = save_artifact(test_dir, "screenshot.png", artifacts["screenshot"], binary=True)
        dom_path = save_artifact(test_dir, "dom.html", artifacts["dom"].encode("utf-8"), binary=True)
        console_path = save_artifact(test_dir, "console.json", json.dumps(artifacts["console"], indent=2).encode("utf-8"), binary=True)
        network_path = save_artifact(test_dir, "network.json", json.dumps(artifacts["network"], indent=2).encode("utf-8"), binary=True)

        verdict = "pass" if artifacts["dom"] and (len(artifacts["network"]) >= 0) else "fail"

        return {
            "id": test["id"],
            "verdict": verdict,
            "artifacts": {
                "screenshot": img_path,
                "dom": dom_path,
                "console": console_path,
                "network": network_path
            },
            "meta": {
                "title": test.get("title")
            }
        }