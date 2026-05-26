import asyncio
from agents.llm_client import get_client, run_agent_loop
from agents.tools import sandbox_run, web_search, fetch_webpage, get_git_diff, e2b_execute_python

async def run_reviewer_agent(repo_dir: str, issue_details: str, branch_name: str, api_key: str, model: str = None, log_callback=None, provider: str = "gemini", base_url: str = None):
    """Runs the Reviewer Agent to analyze git diffs and provide feedback."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)

    await log("\n[REVIEWER AGENT] Starting code review...")

    # Fetch git diff using E2B
    diff_output = get_git_diff(repo_dir, branch_name)

    if not diff_output or not diff_output.strip():
        await log("[REVIEWER AGENT] No code changes detected. Rejecting.")
        return False, "No code changes detected in the branch."

    system_prompt = """You are the Reviewer Agent. Your job is to review the code changes made by the Solver Agent.
You will be provided with the original issue description and the `git diff` of the changes.
Critique the code for:
1. Syntax errors or obvious bugs.
2. Does it completely address the issue?
3. Are there any edge cases missed?

You must output exactly one of two decisions at the end of your response:
[APPROVED] - If the code is perfect and ready to merge.
[REJECTED] - If the code has issues. You must provide detailed feedback above this tag for the Solver Agent to fix it.
"""

    client = get_client(api_key, provider, base_url)
    prompt = f"Issue Details:\n{issue_details}\n\nGit Diff:\n{diff_output}\n\nPlease review these changes."

    await log("[REVIEWER AGENT] Analyzing diff...")
    review_text = await run_agent_loop(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=prompt,
        tools=[sandbox_run, web_search, fetch_webpage, e2b_execute_python],
        log_callback=log_callback,
    )
    await log(f"[REVIEWER AGENT] Feedback:\n{review_text}")

    if "[APPROVED]" in review_text:
        await log("[REVIEWER AGENT] ✅ Code changes approved.")
        return True, ""
    else:
        await log("[REVIEWER AGENT] ❌ Code changes rejected. Sending feedback back to solver.")
        return False, review_text
