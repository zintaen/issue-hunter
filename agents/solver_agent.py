from google.antigravity import Agent, LocalAgentConfig, types
from agents.tools import (
    run_command, create_branch, commit_and_push, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search
)
import asyncio

async def run_solver_agent(repo_dir: str, issue_details: str, branch_name: str, api_key: str, model: str = None, previous_feedback: str = None, log_callback = None) -> tuple[bool, str]:
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
        
    tools = [
        run_command,
        bound_create_branch,
        bound_commit_and_push,
        web_search,
        fetch_webpage,
        e2b_view_file,
        e2b_write_file,
        e2b_grep_search
    ]
    
    denied_tools = [
        types.BuiltinTools.RUN_COMMAND, 
        types.BuiltinTools.VIEW_FILE, 
        types.BuiltinTools.REPLACE_FILE_CONTENT, 
        types.BuiltinTools.MULTI_REPLACE_FILE_CONTENT, 
        types.BuiltinTools.WRITE_TO_FILE, 
        types.BuiltinTools.GREP_SEARCH,
        types.BuiltinTools.FIND_FILE
    ]
    
    system_instructions = (
        "You are an expert autonomous software engineer. Your task is to fix a bug in a codebase based on a GitHub issue. "
        "The repository is mounted at `/workspace` inside a secure E2B Sandbox for command execution.\n\n"
        "STEPS:\n"
        "1. You MUST use `e2b_grep_search` and `run_command('find .')` to find relevant code snippets related to the issue before doing manual searches.\n"
        "2. Use `web_search` and `fetch_webpage` to lookup documentation or stack overflow if you are unsure about a library or API.\n"
        "3. Use `e2b_view_file` to read the relevant code, and `e2b_write_file` to rewrite files with your fixes.\n"
        "4. Create a new branch using `create_branch`.\n"
        "5. Write the fix and write a unit test to verify it.\n"
        "6. Use `run_command` to run the tests and ensure the fix works.\n"
        "7. Commit and push the branch using `commit_and_push(branch_name, commit_message)`.\n\n"
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

        prompt += "\n\nRemember to create the branch first, implement the fix, test it via `run_command`, and finally commit and push."
        
        response = await agent.chat(prompt)
        final_summary = await response.text()
        await log("Solver Agent finished.")
        return True, final_summary
