import os
import docker
from github import Github
from github.GithubException import GithubException
from git import Repo
import httpx
from agents.indexer import RepoIndexer

# Global clients (initialized later)
github_client = None
active_container_dir = None
workspace_dir = None

global_github_token = None

def init_clients(github_token: str, workspace: str):
    global github_client, workspace_dir, global_github_token
    global_github_token = github_token
    github_client = Github(github_token)
    workspace_dir = workspace

def fork_and_clone_repo(repo_full_name: str, target_dir: str) -> str:
    """Forks a GitHub repository and clones it locally.
    
    Args:
        repo_full_name: e.g. 'owner/repo'
        target_dir: Absolute path to clone the repository to.
    """
    repo = github_client.get_repo(repo_full_name)
    user = github_client.get_user()
    
    print(f"Forking {repo_full_name}...")
    try:
        fork = user.create_fork(repo)
    except GithubException as e:
        print(f"Could not fork (maybe already forked?): {e}")
        fork = github_client.get_repo(f"{user.login}/{repo.name}")

    print(f"Cloning to {target_dir}...")
    # Clean up if exists
    if os.path.exists(target_dir):
        import shutil
        shutil.rmtree(target_dir)

    # Note: Using HTTPS with PAT for authentication
    clone_url = fork.clone_url.replace("https://", f"https://{github_client.get_user().login}:{global_github_token}@")
    Repo.clone_from(clone_url, target_dir)
    return f"Successfully forked and cloned to {target_dir}"

def fetch_issue_details(repo_full_name: str, issue_number: int) -> str:
    """Fetches details of a specific GitHub issue.
    
    Args:
        repo_full_name: e.g. 'owner/repo'
        issue_number: Issue ID.
    """
    repo = github_client.get_repo(repo_full_name)
    issue = repo.get_issue(issue_number)
    return f"Title: {issue.title}\n\nBody:\n{issue.body}"

def create_branch(repo_dir: str, branch_name: str) -> str:
    """Creates and checks out a new branch in the local repository.
    
    Args:
        repo_dir: Path to the local git repository.
        branch_name: Name of the new branch.
    """
    repo = Repo(repo_dir)
    new_branch = repo.create_head(branch_name)
    new_branch.checkout()
    return f"Created and checked out branch {branch_name}"

def commit_and_push(repo_dir: str, commit_message: str) -> str:
    """Commits all changes and pushes the current branch to origin.
    
    Args:
        repo_dir: Path to the local git repository.
        commit_message: Message for the commit.
    """
    repo = Repo(repo_dir)
    repo.git.add(A=True)
    repo.index.commit(commit_message)
    origin = repo.remote(name='origin')
    current_branch = repo.active_branch.name
    origin.push(current_branch)
    return f"Committed and pushed branch {current_branch} to origin."

def get_git_diff(repo_dir: str, branch_name: str) -> str:
    """Returns the git diff for the specified branch compared to the base branch.
    
    Args:
        repo_dir: Path to the local git repository.
        branch_name: The branch containing the changes.
    """
    repo = Repo(repo_dir)
    # The default branch could be main or master. We can just diff against tracking branch of the active branch,
    # or simple approach: get diff of branch_name against origin's default branch.
    # Usually `git diff origin/HEAD...branch_name` works if we fetched properly.
    # We'll just do `git log -p -1` or diff against `main`/`master`.
    # Let's try to diff the parent of the branch to the branch.
    try:
        diff_output = repo.git.diff(f"origin/HEAD...{branch_name}")
    except Exception:
        try:
            diff_output = repo.git.diff(f"origin/main...{branch_name}")
        except Exception:
            try:
                diff_output = repo.git.diff(f"origin/master...{branch_name}")
            except Exception as e:
                diff_output = f"Could not compute diff: {e}"
    return diff_output

def semantic_search(repo_dir: str, query: str, n_results: int = 5) -> str:
    """Performs a semantic search on the codebase to find relevant code snippets for a given query.
    
    Args:
        repo_dir: The repository directory to search within.
        query: A natural language description of what to find.
        n_results: The number of results to return.
    """
    try:
        indexer = RepoIndexer(persist_dir=os.path.join(repo_dir, ".chroma_db"))
        # We assume it has already been indexed, or we should index it if empty.
        # But for now, we index it during the orchestrator setup.
        return indexer.search(query, n_results)
    except Exception as e:
        return f"Semantic search error: {e}"

def create_pull_request(repo_full_name: str, branch_name: str, title: str, body: str) -> str:
    """Opens a Pull Request from the fork's branch to the upstream repository.
    
    Args:
        repo_full_name: The UPSTREAM repo 'owner/repo'.
        branch_name: The branch name in our fork.
        title: PR title.
        body: PR body description.
    """
    upstream_repo = github_client.get_repo(repo_full_name)
    user = github_client.get_user()
    
    # head format: username:branch
    head = f"{user.login}:{branch_name}"
    
    pr = upstream_repo.create_pull(
        title=title,
        body=body,
        head=head,
        base=upstream_repo.default_branch
    )
    return f"Created PR: {pr.html_url}"

def start_docker_container(repo_dir: str, image: str = "ubuntu:24.04") -> str:
    """Starts a sandboxed Docker container with the repository mounted. (Mocked for local execution)"""
    global active_container_dir
    active_container_dir = os.path.abspath(repo_dir)
    return f"Local sandbox 'started'. Repository mounted at {active_container_dir}."

def run_command_in_docker(command: str) -> str:
    """Executes a bash command locally instead of in Docker.
    
    Args:
        command: The bash command string to execute.
    """
    global active_container_dir
    if not active_container_dir:
        return "Error: No active container directory."
        
    import subprocess
    try:
        result = subprocess.run(f"bash -c 'source ~/.nvm/nvm.sh 2>/dev/null || true; {command}'", 
                                shell=True, capture_output=True, text=True, cwd=active_container_dir)
        return f"Exit Code: {result.returncode}\\nOutput:\\n{result.stdout}\\n{result.stderr}"
    except Exception as e:
        return f"Exit Code: 1\\nOutput:\\n{str(e)}"

def cleanup_docker_container() -> str:
    """Stops and removes the active Docker container. (Mocked)"""
    global active_container_dir
    active_container_dir = None
    return "Local sandbox cleaned up."

def web_search(query: str, num_results: int = 5) -> str:
    """Searches the web using DuckDuckGo and returns a list of result snippets and URLs.
    
    Args:
        query: The search query.
        num_results: Number of results to return.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        if not results:
            return "No results found."
        
        output = []
        for r in results:
            output.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        return "\n".join(output)
    except Exception as e:
        return f"Web search failed: {e}"

def fetch_webpage(url: str) -> str:
    """Fetches the text content of a webpage given its URL.
    
    Args:
        url: The webpage URL.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return text[:10000] # truncate to avoid blowing up context
    except Exception as e:
        return f"Failed to fetch webpage: {e}"
