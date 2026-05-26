import asyncio
from agents.llm_client import run_agent_loop
from agents.tools import (
    sandbox_run, create_branch, commit_and_push, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search, e2b_execute_python
)

async def run_solver_agent(repo_dir: str, issue_details: str, branch_name: str, setup_summary: str, api_key: str, model: str = None, previous_feedback: str = None, log_callback=None, provider: str = "gemini", base_url: str = None) -> tuple[bool, str]:
    """Runs the Solver Agent to fix an issue in the codebase."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)

    # Create bound closures for git operations
    def bound_create_branch(branch_name: str) -> str:
        """Create a new git branch in the E2B sandbox."""
        return create_branch(repo_dir, branch_name)

    def bound_commit_and_push(branch_name: str, commit_message: str) -> str:
        """Commit all changes and push the branch in the E2B sandbox."""
        return commit_and_push(repo_dir, branch_name, commit_message)

    system_prompt = (
        "You are an expert autonomous software engineer. Your task is to fix a bug in a codebase based on a GitHub issue. "
        "The repository is cloned inside a secure E2B Sandbox.\n\n"
        "IMPORTANT RULES:\n"
        "- The repository path is provided in the user prompt. Use that path for all file operations.\n"
        "- Do NOT run full test suites or build the entire project. Only run tests relevant to your fix.\n"
        "- Keep commands short and targeted. Use `| head -50` or `| tail -20` to limit output.\n\n"
        "STEPS:\n"
        "1. Read the Setup Analysis summary to understand where to focus.\n"
        "2. Use `e2b_grep_search` and `e2b_view_file` to find the specific code that needs changing.\n"
        "3. Create a new branch using `bound_create_branch`.\n"
        "4. Use `e2b_write_file` to write your fix.\n"
        "5. If feasible, write a simple test or run a targeted test to verify the fix.\n"
        "6. Commit and push the branch using `bound_commit_and_push(branch_name, commit_message)`.\n\n"
        "Always explain your reasoning before making changes."
    )

    tools = [sandbox_run, bound_create_branch, bound_commit_and_push, web_search, fetch_webpage, e2b_view_file, e2b_write_file, e2b_grep_search, e2b_execute_python]
    
    user_prompt = (
        f"Fix the following issue:\n\n{issue_details}\n\n"
        f"Branch to create: {branch_name}\n\n"
        f"--- SETUP ANALYSIS (from Phase 1) ---\n{setup_summary}"
    )
    if previous_feedback:
        user_prompt += f"\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED BY THE REVIEWER. Here is the feedback:\n{previous_feedback}\nPlease try again and fix these issues."

    await log(f"\n--- Starting Solver Agent for branch {branch_name} ---")
    
    result = await run_agent_loop(
        client=None,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        max_iterations=40,
        log_callback=log_callback,
        provider=provider,
        base_url=base_url,
        api_key=api_key
    )
    
    await log("Solver Agent finished.")
    
    # Check if the branch exists and has changes
    diff = sandbox_run("git diff --name-only HEAD")
    status = sandbox_run("git status --porcelain")
    has_changes = bool(diff.strip()) or bool(status.strip())
    
    return has_changes, result
