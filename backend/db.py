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
            response = supabase.table('hunts').select("*").order("created_at", desc=True).execute()
            return response.data
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
