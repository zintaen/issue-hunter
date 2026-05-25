import os
import json
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

def start_docker_container(repo_dir: str, image: str = "ubuntu:24.04") -> str:
    global active_sandbox
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        print("WARNING: E2B_API_KEY not found. Operations requiring execution will fail.")
        return "Failed"
    active_sandbox = Sandbox(api_key=api_key)
    # Ensure git is installed in standard E2B environments
    active_sandbox.commands.run("sudo apt-get update && sudo apt-get install -y git")
    return "E2B Cloud Sandbox started successfully."

def cleanup_docker_container() -> str:
    global active_sandbox
    if active_sandbox:
        active_sandbox.kill()
        active_sandbox = None
    return "E2B Sandbox cleaned up."

def fork_and_clone_repo(repo_full_name: str, target_dir: str) -> str:
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

def run_command_in_docker(command: str) -> str:
    global active_sandbox, active_container_dir
    if not active_sandbox:
        return "Error: No active E2B sandbox."
    res = active_sandbox.commands.run(command, cwd=active_container_dir)
    return f"Exit Code: {res.exit_code}\nOutput:\n{res.stdout}\n{res.stderr}"

def e2b_view_file(filepath: str) -> str:
    global active_sandbox, active_container_dir
    res = active_sandbox.commands.run(f"cat {filepath}", cwd=active_container_dir)
    return res.stdout if res.exit_code == 0 else res.stderr

def e2b_write_file(filepath: str, content: str) -> str:
    global active_sandbox, active_container_dir
    full_path = os.path.join(active_container_dir, filepath)
    try:
        active_sandbox.files.write(full_path, content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file: {e}"
        
def e2b_grep_search(query: str) -> str:
    # Use grep to search codebase
    res = run_command_in_docker(f"grep -rnw . -e '{query}'")
    return res

def fetch_issue_details(repo_full_name: str, issue_number: int) -> str:
    repo = github_client.get_repo(repo_full_name)
    issue = repo.get_issue(issue_number)
    return f"Title: {issue.title}\n\nBody:\n{issue.body}"

def create_branch(repo_dir: str, branch_name: str) -> str:
    return run_command_in_docker(f"git checkout -b {branch_name}")

def commit_and_push(repo_dir: str, branch_name: str, commit_message: str) -> str:
    run_command_in_docker("git add -A")
    run_command_in_docker(f"git commit -m '{commit_message}'")
    res = run_command_in_docker(f"git push -u origin {branch_name}")
    return res

def get_git_diff(repo_dir: str, branch_name: str) -> str:
    res = run_command_in_docker(f"git diff origin/main...{branch_name}")
    if not res or "fatal" in res:
        res = run_command_in_docker(f"git diff origin/master...{branch_name}")
    return res

def create_pull_request(repo_full_name: str, branch_name: str, title: str, body: str) -> str:
    upstream_repo = github_client.get_repo(repo_full_name)
    user = github_client.get_user()
    head = f"{user.login}:{branch_name}"
    pr = upstream_repo.create_pull(
        title=title,
        body=body,
        head=head,
        base=upstream_repo.default_branch
    )
    return f"Created PR: {pr.html_url}"

def web_search(query: str, num_results: int = 5) -> str:
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
