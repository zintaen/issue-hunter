import os
from google.antigravity import Agent, LocalAgentConfig, types
from agents.tools import (
    run_command_in_docker, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search
)
import asyncio

async def run_setup_agent(repo_dir: str, api_key: str, model: str = None, log_callback = None) -> str:
    """Runs the Setup Agent to analyze the repository and verify it builds."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)
    
    tools = [
        run_command_in_docker,
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
        "You are an expert software engineer and DevRel specialist. Your goal is to understand "
        "a new open-source codebase and get it running/building in a sandboxed E2B environment. "
        "The repository is mounted at `/workspace` inside the container.\n\n"
        "STEPS:\n"
        "1. Explore the repository (using e2b_grep_search and run_command_in_docker('ls')) to find "
        "build configuration files (e.g. package.json, requirements.txt, Makefile, pom.xml, build.gradle).\n"
        "2. Read the README.md or CONTRIBUTING.md (using e2b_view_file) to understand the setup process.\n"
        "3. Use `web_search` or `fetch_webpage` if you encounter unknown libraries or build tools.\n"
        "4. Use the `run_command_in_docker` tool to install dependencies (e.g., `npm install`, `pip install -r requirements.txt`).\n"
        "5. Use the `run_command_in_docker` tool to run the build or tests to verify the setup.\n"
        "6. If a command fails because of missing system dependencies (like `make` or `gcc`), "
        "use `run_command_in_docker` to install them via `apt-get update && apt-get install -y ...`.\n\n"
        "Output a final summary of what the project is, the main technologies used, and the commands required to set it up."
    )
    
    config = LocalAgentConfig(
        tools=tools,
        denied_tools=denied_tools,
        system_instructions=system_instructions,
        model=model,
        api_key=api_key,
        cwd=repo_dir
    )
    
    await log("\n--- Starting Setup & Analysis Agent ---")
    async with Agent(config) as agent:
        response = await agent.chat(
            "Analyze this repository, install its dependencies, and verify that it can be built or its tests can be run. "
            "Report your findings."
        )
        final_summary = await response.text()
        await log(final_summary)
        return final_summary
