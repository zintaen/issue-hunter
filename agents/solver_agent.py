import os
from google.antigravity import Agent, LocalAgentConfig, types
from agents.tools import run_command_in_docker, create_branch, commit_and_push, semantic_search, web_search, fetch_webpage

import asyncio

async def run_solver_agent(repo_dir: str, issue_details: str, branch_name: str, api_key: str, model: str = None, previous_feedback: str = None, log_callback = None) -> tuple[bool, str]:
    """Runs the Solver Agent to investigate an issue, fix it, and push the branch."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)
    
    def bound_create_branch(branch_name: str) -> str:
        return create_branch(repo_dir, branch_name)

    def bound_commit_and_push(branch_name: str, commit_message: str) -> str:
        return commit_and_push(repo_dir, branch_name, commit_message)
        
    def bound_semantic_search(query: str, n_results: int = 5) -> str:
        return semantic_search(repo_dir, query, n_results)
    
    # Tools available to the solver agent
    tools = [
        run_command_in_docker,
        bound_create_branch,
        bound_commit_and_push,
        bound_semantic_search,
        web_search,
        fetch_webpage
    ]
    
    denied_tools = [types.BuiltinTools.RUN_COMMAND]
    
    system_instructions = (
        "You are an expert autonomous software engineer. Your task is to fix a bug in a codebase based on a GitHub issue. "
        "The repository is mounted at `/workspace` inside a secure Docker container for command execution.\n\n"
        "STEPS:\n"
        "1. You MUST use `semantic_search` to find relevant code snippets related to the issue before doing manual searches. It searches an AST-chunked index of the repository.\n"
        "2. If `semantic_search` doesn't find everything, use `grep_search` and `find_file` to locate the buggy files.\n"
        "3. Use `web_search` and `fetch_webpage` to lookup documentation or stack overflow if you are unsure about a library or API.\n"
        "4. Use `view_file` to read the relevant code, and `multi_replace_file_content` to edit files.\n"
        "5. Create a new branch using `create_branch`.\n"
        "6. Write the fix and write a unit test to verify it.\n"
        "7. Use `run_command_in_docker` to run the tests and ensure the fix works.\n"
        "8. Commit and push the branch using `commit_and_push(branch_name, commit_message)`.\n\n"
        "Always explain your reasoning before making changes."
    )
    
    config = LocalAgentConfig(
        tools=tools,
        denied_tools=denied_tools,
        system_instructions=system_instructions,
        model=model,
        api_key=api_key,
        cwd=repo_dir
    )
    
    await log(f"\n--- Starting Solver Agent for branch {branch_name} ---")
    async with Agent(config) as agent:
        prompt = f"Fix the following issue:\n\n{issue_details}\n\nBranch to create: {branch_name}"
    
        if previous_feedback:
            prompt += f"\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED BY THE REVIEWER. Here is the feedback:\n{previous_feedback}\nPlease try again and fix these issues."

        prompt += "\n\nRemember to create the branch first, implement the fix, test it via `run_command_in_docker`, and finally commit and push."
        
        response = await agent.chat(prompt)
        final_summary = await response.text()
        await log("Solver Agent finished.")
        # Determine success heuristically or ask the agent to return structured output.
        # For this PoC, we assume success if it didn't crash.
        return True, final_summary
