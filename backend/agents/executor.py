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
    Executes tests using a *single* shared browser context.
    Includes multi-resolution support, correctness checks (check_value), and
    playability verification (check_element_change).
    """

    def __init__(self):
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
        # Flag to indicate a critical failure (like a failed assertion)
        test_failed_on_step = False

        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("request", lambda req: network.append({"url": req.url, "method": req.method}))
        page.on("response", lambda resp: network.append({"url": resp.url, "status": resp.status}))

        for step in test["steps"]:
            # If a previous step failed a critical assertion, skip the rest
            if test_failed_on_step:
                console_logs.append(
                    {"type": "info", "text": f"step_skipped:{step['action']}:previous_assertion_failure"})
                continue

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

                # New Action: Type specific value (used for summation tests)
                elif name == "type_value":
                    inputs = await page.query_selector_all("input[type='text'], input[type='number'], textarea")
                    if inputs:
                        # Assumes the first found input is the target
                        await inputs[0].fill(str(params.get("value", "")))


                elif name == "submit":
                    try:
                        await page.click("button[type='submit']", timeout=1500)
                    except Exception:
                        await page.keyboard.press("Enter")

                elif name == "check_selector":
                    sel = params.get("selector", "body")
                    # Simply checks if element appears
                    await page.wait_for_selector(sel, timeout=2000)

                # New Action: Check Value (for correctness, e.g., summation)
                elif name == "check_value":
                    sel = params.get("selector")
                    expected = str(params.get("expected_value"))

                    element = await page.wait_for_selector(sel, timeout=2000)
                    actual = await element.inner_text()

                    if actual.strip() != expected.strip():
                        error_msg = f"Assertion failed: Selector '{sel}' had value '{actual.strip()}', expected '{expected.strip()}'."
                        console_logs.append({"type": "assertion_error", "text": error_msg})
                        test_failed_on_step = True
                    else:
                        console_logs.append(
                            {"type": "assertion_success", "text": f"Assertion passed: Value was '{expected.strip()}'."})

                # New Action: Check Element Change (for playability/flow)
                elif name == "check_element_change":
                    sel = params.get("selector_to_check")
                    timeout = params.get("timeout", 3000)
                    desc = params.get("description", "Checking UI element change.")

                    try:
                        # Asserts that the element becomes visible
                        await page.wait_for_selector(sel, state="visible", timeout=timeout)
                        console_logs.append({"type": "playability_success",
                                             "text": f"Playability check passed: {desc} Element '{sel}' is now visible."})
                    except Exception:
                        error_msg = f"Playability check failed: {desc} Element '{sel}' did not become visible within {timeout}ms."
                        console_logs.append({"type": "playability_error", "text": error_msg})
                        test_failed_on_step = True

                else:
                    pass
            except Exception as e:
                console_logs.append({"type": "error", "text": f"step_error:{name}:{str(e)}"})
                # Mark as critical failure if essential actions fail
                if name in ("goto", "check_selector", "check_value", "check_element_change"):
                    test_failed_on_step = True

        content = await page.content()
        screenshot_bytes = await page.screenshot(full_page=True)
        return {
            "dom": content,
            "screenshot": screenshot_bytes,
            "console": console_logs,
            "network": network,
            "critical_failure": test_failed_on_step  # Returns the final status of assertions
        }

    async def run_test(self, test: Dict[str, Any], out_dir: str):
        """
        Run a single test inside the shared browser context with the specified resolution.
        """
        if not self._context:
            await self.start_browser()

        ensure_test_dir(out_dir)

        # Get viewport size from test, default to desktop if not present
        viewport = test.get("viewport", {"width": 1280, "height": 720})

        page = await self._context.new_page()

        # Set the viewport size for multi-resolution testing
        await page.set_viewport_size(viewport)

        try:
            artifacts = await self._run_steps(page, test)
        finally:
            await page.close()

        # save artifacts
        test_dir = os.path.join(out_dir, test["id"])
        os.makedirs(test_dir, exist_ok=True)
        img_path = save_artifact(test_dir, "screenshot.png", artifacts["screenshot"], binary=True)
        dom_path = save_artifact(test_dir, "dom.html", artifacts["dom"].encode("utf-8"), binary=True)
        console_path = save_artifact(test_dir, "console.json",
                                     json.dumps(artifacts["console"], indent=2).encode("utf-8"), binary=True)
        network_path = save_artifact(test_dir, "network.json",
                                     json.dumps(artifacts["network"], indent=2).encode("utf-8"), binary=True)

        # UPDATED VERDICT LOGIC:
        # 1. Fail if a critical assertion (check_value, check_element_change) failed.
        if artifacts.get("critical_failure", False):
            verdict = "fail"
        # 2. Otherwise, pass if the structural data was successfully captured.
        elif artifacts["dom"] and (len(artifacts["network"]) >= 0):
            verdict = "pass"
        else:
            verdict = "fail"

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
                "title": test.get("title"),
                "viewport": viewport
            }
        }
