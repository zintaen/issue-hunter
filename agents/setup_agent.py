import os
from google.antigravity import Agent, LocalAgentConfig, types
from agents.tools import run_command_in_docker, web_search, fetch_webpage

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
    
    # We allow the agent to read/search files on the host, 
    # but command execution MUST happen in docker.
    tools = [
        run_command_in_docker,
        web_search,
        fetch_webpage
    ]
    
    # Deny built-in run_command for safety, enable others
    denied_tools = [types.BuiltinTools.RUN_COMMAND]
    
    system_instructions = (
        "You are an expert software engineer and DevRel specialist. Your goal is to understand "
        "a new open-source codebase and get it running/building in a sandboxed Docker environment. "
        "The repository is mounted at `/workspace` inside the container.\n\n"
        "STEPS:\n"
        "1. Explore the repository (using find_file, list_directory, view_file) to find "
        "build configuration files (e.g. package.json, requirements.txt, Makefile, pom.xml, build.gradle).\n"
        "2. Read the README.md or CONTRIBUTING.md to understand the setup process.\n"
        "3. Use `web_search` or `fetch_webpage` if you encounter unknown libraries or build tools.\n"
        "4. Use the `run_command_in_docker` tool to install dependencies (e.g., `npm install`, `pip install -r requirements.txt`).\n"
        "4. Use the `run_command_in_docker` tool to run the build or tests to verify the setup.\n"
        "5. If a command fails because of missing system dependencies (like `make` or `gcc`), "
        "use `run_command_in_docker` to install them via `apt-get update && apt-get install -y ...`.\n\n"
        "Output a final summary of what the project is, the main technologies used, and the commands required to set it up."
    )
    
    config = LocalAgentConfig(
        tools=tools,
        denied_tools=denied_tools,
        system_instructions=system_instructions,
        model=model, # Will fallback to env default if None
        api_key=api_key,
        # Ensure the agent's working directory defaults to the repo dir for file tools
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
