import asyncio
import sys
import json
import os
import time
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Correctly import agent classes from their respective modules
from backend.agents.planner import PlannerAgent
from backend.agents.ranker import RankerAgent
from backend.agents.orchestrator import OrchestratorAgent
from backend.agents.analyzer import AnalyzerAgent

# Set the event loop policy for Windows to fix subprocess issues with Playwright
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="Multi-Agent Game Tester POC")

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/ui", StaticFiles(directory=frontend_dir), name="ui")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize the agents as singletons
planner = PlannerAgent()
ranker = RankerAgent()
orchestrator = OrchestratorAgent()
analyzer = AnalyzerAgent()

class GenerateRequest(BaseModel):
    target_url: str = "https://play.ezygamers.com/"

class ExecuteRequest(BaseModel):
    top_k: int = 10
    quick: bool = False  # if true, execute top 3 for quick demo

@app.post("/generate_plan")
async def generate_plan(req: GenerateRequest):
    """Generates a list of candidate test cases."""
    candidates = planner.generate_candidates(req.target_url, n=24)
    out = {"candidates": candidates}
    with open(os.path.join(DATA_DIR, "candidates.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out

@app.post("/rank_plan")
async def rank_plan():
    """Ranks the generated test cases and selects the top 10."""
    candidates_path = os.path.join(DATA_DIR, "candidates.json")
    if not os.path.exists(candidates_path):
        raise HTTPException(status_code=400, detail="Run /generate_plan first")
    with open(candidates_path) as f:
        candidates = json.load(f)["candidates"]
    ranked = ranker.rank_candidates(candidates)
    with open(os.path.join(DATA_DIR, "ranked.json"), "w") as f:
        json.dump({"ranked": ranked}, f, indent=2)
    return {"ranked": ranked}

@app.post("/execute_tests")
async def execute_tests(req: ExecuteRequest):
    """
    Executes the selected test cases and generates a final report.
    This runs the full orchestration pipeline.
    """
    ranked_path = os.path.join(DATA_DIR, "ranked.json")
    if not os.path.exists(ranked_path):
        raise HTTPException(status_code=400, detail="Run /rank_plan first")
    with open(ranked_path) as f:
        ranked = json.load(f)["ranked"]

    top_k = min(req.top_k, len(ranked))
    selected = ranked[:top_k] if not req.quick else ranked[:min(3, top_k)]

    # measure time
    start_time = time.time()

    report = await orchestrator.run(selected)

    elapsed = time.time() - start_time
    report["summary"]["elapsed_seconds"] = round(elapsed, 2)

    report_path = os.path.join(DATA_DIR, "final_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report

@app.get("/report")
async def get_report():
    """Retrieves the final JSON report."""
    path = os.path.join(DATA_DIR, "final_report.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No report found yet; run /execute_tests")
    return FileResponse(path, media_type="application/json", filename="final_report.json")

@app.get("/artifact/{test_id}/{name}")
async def get_artifact(test_id: str, name: str):
    """Retrieves a specific artifact file."""
    path = os.path.join(DATA_DIR, test_id, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)

@app.get("/")
async def root():
    """Redirects to the frontend UI."""
    return RedirectResponse(url="/ui/index.html")

if __name__ == "__main__":
    import uvicorn
    # This ensures the server starts correctly and the event loop policy is applied
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
