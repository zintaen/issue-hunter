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
        "You are an expert autonomous software engineer. Your task is to implement a fix "
        "for a bug based on a detailed analysis from the Setup Agent.\n\n"
        "The repository is cloned inside a secure E2B Sandbox.\n\n"
        "IMPORTANT RULES:\n"
        "- Do NOT try to install dependencies, build the project, or run the full test suite.\n"
        "- Do NOT run `npm install`, `pip install`, `pnpm install`, `make build`, etc.\n"
        "- The environment may not have the right toolchain. That's OK — just write the code fix.\n"
        "- Focus ONLY on reading code, writing the fix, and committing it.\n"
        "- You CAN run simple verification like `node -c <file>` (syntax check) or `python -m py_compile <file>`.\n\n"
        "STEPS:\n"
        "1. Read the Setup Analysis carefully — it tells you exactly which files to modify.\n"
        "2. Use `e2b_view_file` to read the current content of files you need to change.\n"
        "3. Create a new branch using `bound_create_branch`.\n"
        "4. Use `e2b_write_file` to write each modified file with your fix applied.\n"
        "5. Optionally run a quick syntax check to make sure you didn't break anything.\n"
        "6. Commit and push using `bound_commit_and_push(branch_name, commit_message)`.\n\n"
        "QUALITY:\n"
        "- Write clean, idiomatic code that matches the project's style.\n"
        "- Add code comments explaining your fix if the change is non-obvious.\n"
        "- Make the minimal change needed — don't refactor unrelated code.\n"
        "- Always explain your reasoning before writing code."
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
        max_iterations=30,
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
