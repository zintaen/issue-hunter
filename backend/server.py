import asyncio
from fastapi import FastAPI, WebSocket, BackgroundTasks, Depends, HTTPException, status, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

# Add the parent directory to sys.path so we can import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import run_orchestrator
from db import init_db, create_hunt, insert_log, update_hunt_status, get_hunts, get_hunt_logs

app = FastAPI(title="Issue Hunter API")

@app.on_event("startup")
def on_startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global queue to store logs for the websocket
log_queue = asyncio.Queue()

# Store pending approvals for interactive review
pending_approvals = {}

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "hunter2")

def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    token = authorization.split("Bearer ")[1]
    if token != ADMIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return token

class LoginRequest(BaseModel):
    password: str

@app.post("/api/login")
def login(request: LoginRequest):
    if request.password == ADMIN_PASSWORD:
        return {"token": ADMIN_PASSWORD}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

class HuntRequest(BaseModel):
    repo_url: str
    issues: List[int]
    provider: str
    model: str
    api_key: str
    github_token: str
    base_url: Optional[str] = None

class BenchmarkItem(BaseModel):
    repo_url: str
    issues: List[int]

class BenchmarkRequest(BaseModel):
    targets: List[BenchmarkItem]
    provider: str
    model: str
    api_key: str
    github_token: str
    base_url: Optional[str] = None

class ApproveRequest(BaseModel):
    repo_name: str
    action: str # "approve" or "reject"

@app.get("/api/approvals")
def get_pending_approvals(token: str = Depends(verify_token)):
    res = []
    for repo, data in pending_approvals.items():
        res.append({
            "repo_name": repo,
            "branch": data["branch"],
            "diff": data["diff"]
        })
    return {"pending": res}

@app.post("/api/approve")
async def approve_action(request: ApproveRequest, token: str = Depends(verify_token)):
    if request.repo_name in pending_approvals and not pending_approvals[request.repo_name]["future"].done():
        pending_approvals[request.repo_name]["future"].set_result(request.action)
        return {"status": f"Action {request.action} received"}
    return {"status": "No pending approval for this repo"}

@app.post("/api/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    # Process GitHub issue comments
    payload = await request.json()
    if "action" in payload and payload["action"] == "created" and "comment" in payload:
        body = payload["comment"]["body"]
        if "@issue-hunter fix this" in body:
            issue_url = payload["issue"]["html_url"]
            # e.g., https://github.com/owner/repo/issues/123
            parts = issue_url.split('/')
            repo_url = f"https://github.com/{parts[3]}/{parts[4]}"
            issue_num = int(parts[6])
            
            # Since webhooks don't supply config, we must fall back to ENV VARS for API keys
            # Ideally, these are configured for the deployed server.
            api_key = os.getenv("LLM_API_KEY", "")
            github_token = os.getenv("GITHUB_TOKEN", "")
            base_url = os.getenv("LLM_BASE_URL", None)
            provider = os.getenv("LLM_PROVIDER", "gemini")
            model = os.getenv("LLM_MODEL", "gemini-3.5-pro")
            
            if not api_key or not github_token:
                print("Webhook received but missing env vars for execution.")
                return {"status": "ignored: missing keys"}
            
            hunt_id = create_hunt(
                repo_url=repo_url,
                issues=[issue_num],
                provider=provider,
                model=model
            )
            background_tasks.add_task(
                run_workflow,
                hunt_id,
                repo_url,
                [issue_num],
                provider,
                model,
                api_key,
                github_token,
                base_url
            )
            return {"status": "workflow queued via webhook", "hunt_id": hunt_id}
            
    return {"status": "ignored"}

@app.post("/api/hunt")
async def start_hunt(request: HuntRequest, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    hunt_id = create_hunt(
        repo_url=request.repo_url,
        issues=request.issues,
        provider=request.provider,
        model=request.model
    )
    # Enqueue the workflow
    background_tasks.add_task(
        run_workflow,
        hunt_id,
        request.repo_url,
        request.issues,
        request.provider,
        request.model,
        request.api_key,
        request.github_token,
        request.base_url
    )
    return {"status": "workflow queued", "hunt_id": hunt_id}

@app.post("/api/benchmark")
async def start_benchmark(request: BenchmarkRequest, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    hunt_ids = []
    for target in request.targets:
        hunt_id = create_hunt(
            repo_url=target.repo_url,
            issues=target.issues,
            provider=request.provider,
            model=request.model
        )
        hunt_ids.append(hunt_id)
        background_tasks.add_task(
            run_workflow,
            hunt_id,
            target.repo_url,
            target.issues,
            request.provider,
            request.model,
            request.api_key,
            request.github_token,
            request.base_url
        )
    return {"status": "benchmark batch queued", "hunt_ids": hunt_ids}

@app.get("/api/hunts")
def list_hunts(token: str = Depends(verify_token)):
    return get_hunts()

@app.get("/api/hunts/{hunt_id}/logs")
def fetch_hunt_logs(hunt_id: str, token: str = Depends(verify_token)):
    return get_hunt_logs(hunt_id)

async def run_workflow(hunt_id: str, repo_url: str, issues: List[int], provider: str, model: str, api_key: str, github_token: str, base_url: str = None):
    async def log_with_db(msg: str):
        insert_log(hunt_id, msg)
        await log_queue.put(msg)

    await log_with_db(f"Starting workflow for {repo_url} on issues {issues} using {provider} ({model})...")
    try:
        repo_name = repo_url.split('/')[-1]
        workspace = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
        
        async def wait_for_approval(branch, diff):
            await log_with_db(f"[APPROVAL_REQUIRED] Branch '{branch}' is ready.")
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            pending_approvals[repo_name] = {
                "branch": branch,
                "diff": diff,
                "future": future
            }
            # Notify frontend via websocket (optional, but GET handles it too)
            await log_queue.put(f"__APPROVAL_REQUIRED__:{repo_name}")
            
            # Wait for the UI to hit /api/approve
            action = await future
            del pending_approvals[repo_name]
            return action == "approve"

        report_md = await run_orchestrator(
            target_repo=repo_url,
            issue_numbers=issues,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            github_token=github_token,
            workspace_base_dir=workspace,
            log_callback=log_with_db,
            approval_callback=wait_for_approval
        )
        await log_with_db("Workflow completed successfully.")
        update_hunt_status(hunt_id, "completed", report_md)
    except Exception as e:
        await log_with_db(f"Workflow failed with error: {str(e)}")
        update_hunt_status(hunt_id, "failed")

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Wait for a log message
            message = await log_queue.get()
            await websocket.send_text(message)
    except Exception as e:
        print("WebSocket disconnected:", e)

# Mount frontend static files
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(frontend_dist, "index.html"))

