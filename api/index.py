import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback
import_error = None
try:
    from agents.orchestrator import run_orchestrator
    from backend.db import init_db, create_hunt, get_or_create_hunt, insert_log, update_hunt_status, get_hunts, get_hunt_logs, get_hunt, get_pending_approvals
except Exception as e:
    import_error = traceback.format_exc()

app = FastAPI(title="Issue Hunter API")

@app.get("/api/debug")
def debug_info():
    import os, sys
    return {
        "import_error": import_error,
        "sys_path": sys.path,
        "cwd": os.getcwd(),
        "files_in_cwd": os.listdir("."),
        "files_in_var_task": os.listdir("/var/task") if os.path.exists("/var/task") else []
    }

@app.on_event("startup")
def on_startup():
    if import_error is None:
        init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class ApproveRequest(BaseModel):
    hunt_id: str
    action: str # "approve" or "reject"

@app.get("/api/approvals")
def get_pending_approvals_endpoint(token: str = Depends(verify_token)):
    pending = get_pending_approvals()
    res = []
    for hunt in pending:
        repo_name = hunt['repo_url'].split('/')[-1]
        res.append({
            "hunt_id": hunt['id'],
            "repo_name": repo_name,
            "branch": hunt['branch_name'],
            "diff": hunt['diff_content']
        })
    return {"pending": res}

@app.post("/api/approve")
async def approve_action(request: ApproveRequest, token: str = Depends(verify_token)):
    hunt = get_hunt(request.hunt_id)
    if hunt and hunt['status'] == "pending_approval":
        new_status = "approved" if request.action == "approve" else "rejected"
        update_hunt_status(request.hunt_id, new_status)
        return {"status": f"Action {request.action} applied"}
    return {"status": "No pending approval for this hunt"}

@app.post("/api/hunt")
async def start_hunt(request: HuntRequest, token: str = Depends(verify_token)):
    hunt_id = get_or_create_hunt(
        repo_url=request.repo_url,
        issues=request.issues,
        provider=request.provider,
        model=request.model
    )
    
    # We use a generator to stream logs via SSE so Vercel keeps the function alive
    async def event_generator():
        log_queue = asyncio.Queue()
        
        # Pre-populate with existing logs if any
        existing_logs = get_hunt_logs(hunt_id)
        if existing_logs:
            for msg in existing_logs:
                # We don't put it in the queue, we just yield it immediately in the main stream loop
                pass 
            
        async def log_with_db(msg: str):
            insert_log(hunt_id, msg)
            await log_queue.put(msg)
            
        async def wait_for_approval(branch, diff):
            await log_with_db(f"[APPROVAL_REQUIRED] Branch '{branch}' is ready.")
            update_hunt_status(hunt_id, "pending_approval", branch_name=branch, diff_content=diff)
            await log_queue.put(f"__APPROVAL_REQUIRED__:{request.repo_url.split('/')[-1]}")
            
            # Stateless polling of Supabase
            while True:
                hunt = get_hunt(hunt_id)
                if hunt and hunt['status'] in ['approved', 'rejected']:
                    return hunt['status'] == 'approved'
                await asyncio.sleep(3)

        # Start workflow in a background task so we can stream its logs
        workflow_task = asyncio.create_task(
            run_orchestrator(
                target_repo=request.repo_url,
                issue_numbers=request.issues,
                model=request.model,
                provider=request.provider,
                base_url=request.base_url,
                api_key=request.api_key,
                github_token=request.github_token,
                workspace_base_dir="/tmp",
                log_callback=log_with_db,
                approval_callback=wait_for_approval
            )
        )
        
        yield f"data: Workflow queued. Hunt ID: {hunt_id}\n\n"
        
        if existing_logs:
            yield f"data: --- Resuming previous hunt logs ---\n\n"
            for msg in existing_logs:
                safe_msg = msg.replace('\n', '__NEWLINE__')
                yield f"data: {safe_msg}\n\n"
        
        while not workflow_task.done():
            try:
                msg = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                # Replace newlines so SSE doesn't break
                safe_msg = msg.replace('\n', '__NEWLINE__')
                yield f"data: {safe_msg}\n\n"
            except asyncio.TimeoutError:
                # Keep connection alive
                yield ": keepalive\n\n"
                
        # Drain remaining logs
        while not log_queue.empty():
            msg = log_queue.get_nowait()
            safe_msg = msg.replace('\n', '__NEWLINE__')
            yield f"data: {safe_msg}\n\n"
            
        try:
            report_md = workflow_task.result()
            update_hunt_status(hunt_id, "completed", report_md=report_md)
            yield f"data: Workflow completed successfully.\n\n"
        except Exception as e:
            update_hunt_status(hunt_id, "failed")
            yield f"data: Workflow failed: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/hunts")
def list_hunts(token: str = Depends(verify_token)):
    return get_hunts()

@app.get("/api/hunts/{hunt_id}/logs")
def fetch_hunt_logs(hunt_id: str, token: str = Depends(verify_token)):
    return get_hunt_logs(hunt_id)

@app.delete("/api/hunts/{hunt_id}")
def delete_hunt_endpoint(hunt_id: str, token: str = Depends(verify_token)):
    from backend.db import delete_hunt
    import os
    from e2b_code_interpreter import Sandbox
    
    hunt = get_hunt(hunt_id)
    if hunt and hunt.get('status') == 'running':
        try:
            logs = get_hunt_logs(hunt_id)
            sandbox_id = None
            for log in logs:
                if "[SANDBOX_ID:" in log:
                    sandbox_id = log.split("[SANDBOX_ID:")[1].split("]")[0]
                    break
            if sandbox_id:
                api_key = os.environ.get("E2B_API_KEY")
                if api_key:
                    Sandbox.kill(sandbox_id, api_key=api_key)
                    print(f"Killed sandbox {sandbox_id} for hunt {hunt_id}")
        except Exception as e:
            print(f"Failed to kill E2B sandbox for hunt {hunt_id}: {e}")
            
    delete_hunt(hunt_id)
    return {"status": "deleted"}

@app.post("/api/webhook/github")
async def github_webhook(request: Request):
    # Webhooks on Vercel Serverless will timeout after 10s if we run the workflow synchronously.
    # Therefore, GitHub will mark the delivery as timed out, but the function may continue until maxDuration.
    payload = await request.json()
    if "action" in payload and payload["action"] == "created" and "comment" in payload:
        body = payload["comment"]["body"]
        if "@issue-hunter fix this" in body:
            issue_url = payload["issue"]["html_url"]
            parts = issue_url.split('/')
            repo_url = f"https://github.com/{parts[3]}/{parts[4]}"
            issue_num = int(parts[6])
            
            api_key = os.getenv("AI_API_KEY", "")
            github_token = os.getenv("GITHUB_TOKEN", "")
            base_url = os.getenv("AI_BASE_URL", None)
            provider = os.getenv("AI_PROVIDER", "gemini")
            model = os.getenv("AI_MODEL_NAME", "gemini-3.5-pro")
            
            if not api_key or not github_token:
                return {"status": "ignored: missing keys"}
            
            hunt_id = create_hunt(repo_url=repo_url, issues=[issue_num], provider=provider, model=model)
            
            # Run synchronously (will timeout for GitHub, but execute)
            async def null_log(msg): pass
            
            await run_orchestrator(
                target_repo=repo_url, issue_numbers=[issue_num], model=model, provider=provider,
                base_url=base_url, api_key=api_key, github_token=github_token, workspace_base_dir="/tmp",
                log_callback=null_log
            )
            return {"status": "workflow completed", "hunt_id": hunt_id}
    return {"status": "ignored"}

# Mount frontend static files
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(frontend_dist, "index.html"))

