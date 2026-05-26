import os
import shlex
from github import Github
from e2b_code_interpreter import Sandbox

active_sandbox = None
github_client = None
global_github_token = None
active_container_dir = "/workspace"

def init_clients(github_token: str, workspace: str):
    global github_client, global_github_token
    global_github_token = github_token
    github_client = Github(github_token)

def start_sandbox(repo_dir: str) -> str:
    """Start an E2B cloud sandbox for secure code execution."""
    global active_sandbox
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        print("WARNING: E2B_API_KEY not found. Operations requiring execution will fail.")
        return "Failed"
    active_sandbox = Sandbox.create()
    active_sandbox.commands.run("sudo apt-get update && sudo apt-get install -y git")
    return "E2B Cloud Sandbox started successfully."

def cleanup_sandbox() -> str:
    """Kill the active E2B sandbox."""
    global active_sandbox
    if active_sandbox:
        active_sandbox.kill()
        active_sandbox = None
    return "E2B Sandbox cleaned up."

def fork_and_clone_repo(repo_full_name: str, target_dir: str) -> str:
    """Fork and clone a repository into the E2B sandbox."""
    repo = github_client.get_repo(repo_full_name)
    user = github_client.get_user()
    try:
        fork = user.create_fork(repo)
    except Exception:
        fork = github_client.get_repo(f"{user.login}/{repo.name}")
    
    clone_url = fork.clone_url.replace("https://", f"https://{user.login}:{global_github_token}@")
    
    global active_sandbox, active_container_dir
    active_container_dir = f"/workspace/{repo.name}"
    
    if not active_sandbox:
        return "Sandbox not running."
        
    cmd = f"git clone {clone_url} {active_container_dir}"
    res = active_sandbox.commands.run(cmd)
    
    active_sandbox.commands.run("git config --global user.email 'bot@issuehunter.dev'")
    active_sandbox.commands.run("git config --global user.name 'Issue Hunter'")
    
    return f"Cloned into E2B: {res.stdout}"

def sandbox_run(command: str) -> str:
    """Run a command inside the E2B sandbox."""
    global active_sandbox, active_container_dir
    if not active_sandbox:
        return "Error: No active E2B sandbox."
    res = active_sandbox.commands.run(command, cwd=active_container_dir)
    return f"Exit Code: {res.exit_code}\nOutput:\n{res.stdout}\n{res.stderr}"

def e2b_execute_python(code: str) -> str:
    """Execute python code in a Jupyter notebook cell and return result."""
    global active_sandbox
    if not active_sandbox:
        return "Error: No active E2B sandbox."
    try:
        execution = active_sandbox.run_code(code)
        return execution.text
    except Exception as e:
        return f"Error executing Python code: {e}"

def e2b_view_file(filepath: str) -> str:
    """View a file inside the E2B sandbox."""
    global active_sandbox, active_container_dir
    if not active_sandbox:
        return "Error: No active E2B sandbox."
    res = active_sandbox.commands.run(f"cat {filepath}", cwd=active_container_dir)
    return res.stdout if res.exit_code == 0 else res.stderr

def e2b_write_file(filepath: str, content: str) -> str:
    """Write content to a file inside the E2B sandbox."""
    global active_sandbox, active_container_dir
    if not active_sandbox:
        return "Error: No active E2B sandbox."
    full_path = os.path.join(active_container_dir, filepath)
    try:
        active_sandbox.files.write(full_path, content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file: {e}"
        
def e2b_grep_search(query: str) -> str:
    """Search the codebase using grep inside the E2B sandbox."""
    res = sandbox_run(f"grep -rnw . -e {shlex.quote(query)}")
    return res

def create_branch(repo_dir: str, branch_name: str) -> str:
    """Create a new git branch in the E2B sandbox."""
    return sandbox_run(f"git checkout -b {branch_name}")

def commit_and_push(repo_dir: str, branch_name: str, commit_message: str) -> str:
    """Commit all changes and push the branch in the E2B sandbox."""
    sandbox_run("git add -A")
    sandbox_run(f"git commit -m {shlex.quote(commit_message)}")
    res = sandbox_run(f"git push -u origin {branch_name}")
    return res

def get_git_diff(repo_dir: str, branch_name: str) -> str:
    """Get the git diff between the branch and origin/main."""
    res = sandbox_run(f"git diff origin/main...{branch_name}")
    if not res or "fatal" in res:
        res = sandbox_run(f"git diff origin/master...{branch_name}")
    return res

def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        if not results:
            return "No results found."
        output = [f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n" for r in results]
        return "\n".join(output)
    except Exception as e:
        return f"Web search failed: {e}"

def fetch_webpage(url: str) -> str:
    """Fetch and extract text from a webpage."""
    try:
        import httpx
        from bs4 import BeautifulSoup
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return text[:10000]
    except Exception as e:
        return f"Failed to fetch webpage: {e}"
