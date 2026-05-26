import os
import json
import uuid
from datetime import datetime
from supabase import create_client, Client

_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("WARNING: SUPABASE_URL or SUPABASE_KEY not set. Database operations will be skipped.")
        return None
    _supabase_client = create_client(url, key)
    return _supabase_client

def init_db():
    # Supabase tables should be initialized via the SQL Editor using the provided script.
    pass

def create_hunt(repo_url: str, issues: list, provider: str, model: str) -> str:
    hunt_id = str(uuid.uuid4())
    supabase = get_supabase()
    if supabase:
        supabase.table('hunts').insert({
            "id": hunt_id,
            "repo_url": repo_url,
            "issues": json.dumps(issues),
            "provider": provider,
            "model": model,
            "status": "running"
        }).execute()
    return hunt_id

def get_or_create_hunt(repo_url: str, issues: list, provider: str, model: str) -> str:
    supabase = get_supabase()
    if supabase:
        try:
            # Check existing
            response = supabase.table('hunts').select("id, issues").eq("repo_url", repo_url).execute()
            for row in response.data:
                # Ensure it's the exact same array of issues
                if row.get('issues') == issues:
                    # Update status to running
                    supabase.table('hunts').update({
                        "status": "running",
                        "provider": provider,
                        "model": model,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", row['id']).execute()
                    return row['id']
        except Exception as e:
            print("Failed to get_or_create_hunt:", e)
            
    # If not found or error, create new
    return create_hunt(repo_url, issues, provider, model)

def insert_log(hunt_id: str, log_text: str):
    supabase = get_supabase()
    if supabase:
        try:
            supabase.table('logs').insert({
                "hunt_id": hunt_id,
                "log_text": log_text
            }).execute()
        except Exception as e:
            print("Failed to insert log into supabase:", e)

def update_hunt_status(hunt_id: str, status: str, report_md: str = None, branch_name: str = None, diff_content: str = None):
    supabase = get_supabase()
    if supabase:
        try:
            update_data = {
                "status": status,
                "completed_at": datetime.utcnow().isoformat()
            }
            if report_md is not None:
                update_data["report_md"] = report_md
            if branch_name is not None:
                update_data["branch_name"] = branch_name
            if diff_content is not None:
                update_data["diff_content"] = diff_content
                
            supabase.table('hunts').update(update_data).eq("id", hunt_id).execute()
        except Exception as e:
            print("Failed to update hunt status:", e)

def get_hunt(hunt_id: str):
    supabase = get_supabase()
    if supabase:
        try:
            response = supabase.table('hunts').select("*").eq("id", hunt_id).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print("Failed to fetch hunt:", e)
    return None

def get_hunts():
    supabase = get_supabase()
    if supabase:
        try:
            response = supabase.table('hunts').select("id, repo_url, issues, provider, model, status, report_md, branch_name, created_at, updated_at").order("created_at", desc=True).execute()
            hunts = response.data
            
            # Auto-cleanup stale running hunts (e.g. killed by Vercel timeout)
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for h in hunts:
                if h.get('status') == 'running' and h.get('created_at'):
                    try:
                        ca_str = h['created_at']
                        if ca_str.endswith('Z'):
                            ca_str = ca_str[:-1] + '+00:00'
                        ca = datetime.fromisoformat(ca_str)
                        if ca.tzinfo is None:
                            ca = ca.replace(tzinfo=timezone.utc)
                            
                        # If running for more than 15 minutes, mark as failed
                        if (now - ca).total_seconds() > 900:
                            h['status'] = 'failed'
                            if not h.get('report_md'):
                                h['report_md'] = "Process timed out and was killed by the server environment."
                            
                            supabase.table('hunts').update({
                                "status": "failed", 
                                "report_md": h.get('report_md')
                            }).eq("id", h['id']).execute()
                    except Exception as e:
                        print(f"Error parsing date or updating stale hunt {h.get('id')}: {e}")
            
            return hunts
        except Exception as e:
            print("Failed to fetch hunts:", e)
    return []

def get_pending_approvals():
    supabase = get_supabase()
    if supabase:
        try:
            response = supabase.table('hunts').select("id, repo_url, branch_name, diff_content").eq("status", "pending_approval").execute()
            return response.data
        except Exception as e:
            print("Failed to fetch pending approvals:", e)
    return []

def get_hunt_logs(hunt_id: str):
    supabase = get_supabase()
    if supabase:
        try:
            response = supabase.table('logs').select("log_text").eq("hunt_id", hunt_id).order("id", desc=False).execute()
            return [row["log_text"] for row in response.data]
        except Exception as e:
            print("Failed to fetch logs:", e)
    return []

def delete_hunt(hunt_id: str):
    supabase = get_supabase()
    if supabase:
        try:
            # Logs have ON DELETE CASCADE, but delete explicitly just in case
            supabase.table('logs').delete().eq("hunt_id", hunt_id).execute()
            supabase.table('hunts').delete().eq("id", hunt_id).execute()
        except Exception as e:
            print("Failed to delete hunt:", e)

def delete_other_hunts(hunt_id: str):
    """Deletes all other hunts with the same issues and repo, keeping only the successful one. Also attempts to kill their sandboxes."""
    hunt = get_hunt(hunt_id)
    if not hunt: return
    
    supabase = get_supabase()
    if supabase:
        try:
            response = supabase.table('hunts').select("id, issues").eq("repo_url", hunt['repo_url']).neq("id", hunt_id).execute()
            import os
            api_key = os.environ.get("E2B_API_KEY")
            
            for r in response.data:
                if r.get('issues') == hunt['issues']:
                    other_id = r['id']
                    # Try to kill sandbox
                    try:
                        logs = get_hunt_logs(other_id)
                        sandbox_id = None
                        for log in logs:
                            if "[SANDBOX_ID:" in log:
                                sandbox_id = log.split("[SANDBOX_ID:")[1].split("]")[0]
                                break
                        if sandbox_id and api_key:
                            from e2b_code_interpreter import Sandbox
                            Sandbox.kill(sandbox_id, api_key=api_key)
                    except Exception as e:
                        print(f"Failed to kill E2B sandbox for other hunt {other_id}: {e}")
                    
                    # Delete the hunt
                    delete_hunt(other_id)
        except Exception as e:
            print("Failed to delete other hunts:", e)
