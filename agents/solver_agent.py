import asyncio
from agents.llm_client import get_client, run_agent_loop
from agents.tools import (
    sandbox_run, create_branch, commit_and_push, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search, e2b_execute_python
)

async def run_solver_agent(repo_dir: str, issue_details: str, branch_name: str, api_key: str, model: str = None, previous_feedback: str = None, log_callback=None, provider: str = "gemini", base_url: str = None) -> tuple[bool, str]:
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
        "The repository is mounted at `/workspace` inside a secure E2B Sandbox for command execution.\n\n"
        "STEPS:\n"
        "1. You MUST use `e2b_grep_search` and `sandbox_run('find .')` to find relevant code snippets related to the issue before doing manual searches.\n"
        "2. Use `web_search` and `fetch_webpage` to lookup documentation or stack overflow if you are unsure about a library or API.\n"
        "3. Use `e2b_view_file` to read the relevant code, and `e2b_write_file` to rewrite files with your fixes.\n"
        "4. Create a new branch using `bound_create_branch`.\n"
        "5. Write the fix and write a unit test to verify it.\n"
        "6. Use `sandbox_run` to run the tests and ensure the fix works.\n"
        "7. Commit and push the branch using `bound_commit_and_push(branch_name, commit_message)`.\n\n"
        "Always explain your reasoning before making changes."
    )

    client = get_client(api_key, provider, base_url)
    tools = [sandbox_run, bound_create_branch, bound_commit_and_push, web_search, fetch_webpage, e2b_view_file, e2b_write_file, e2b_grep_search, e2b_execute_python]

    await log(f"\n--- Starting Solver Agent for branch {branch_name} ---")
    
    prompt = f"Fix the following issue:\n\n{issue_details}\n\nBranch to create: {branch_name}"
    if previous_feedback:
        prompt += f"\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED BY THE REVIEWER. Here is the feedback:\n{previous_feedback}\nPlease try again and fix these issues."
    prompt += "\n\nRemember to create the branch first, implement the fix, test it via `sandbox_run`, and finally commit and push."

    result = await run_agent_loop(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=prompt,
        tools=tools,
        log_callback=log_callback,
    )
    await log("Solver Agent finished.")
    return True, result
