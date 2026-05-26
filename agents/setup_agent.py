import asyncio
from agents.llm_client import get_client, run_agent_loop
from agents.tools import (
    sandbox_run, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search
)

async def run_setup_agent(repo_dir: str, api_key: str, model: str = None, log_callback=None, provider: str = "gemini", base_url: str = None) -> str:
    """Runs the Setup Agent to analyze the repository and verify it builds."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)

    system_prompt = (
        "You are an expert software engineer and DevRel specialist. Your goal is to understand "
        "a new open-source codebase and get it running/building in a sandboxed E2B environment. "
        "The repository is mounted at `/workspace` inside the sandbox.\n\n"
        "STEPS:\n"
        "1. Explore the repository (using e2b_grep_search and sandbox_run('ls')) to find "
        "build configuration files (e.g. package.json, requirements.txt, Makefile, pom.xml, build.gradle).\n"
        "2. Read the README.md or CONTRIBUTING.md (using e2b_view_file) to understand the setup process.\n"
        "3. Use `web_search` or `fetch_webpage` if you encounter unknown libraries or build tools.\n"
        "4. Use the `sandbox_run` tool to install dependencies (e.g., `npm install`, `pip install -r requirements.txt`).\n"
        "5. Use the `sandbox_run` tool to run the build or tests to verify the setup.\n"
        "6. If a command fails because of missing system dependencies (like `make` or `gcc`), "
        "use `sandbox_run` to install them via `apt-get update && apt-get install -y ...`.\n\n"
        "Output a final summary of what the project is, the main technologies used, and the commands required to set it up."
    )

    client = get_client(api_key, provider, base_url)
    tools = [sandbox_run, web_search, fetch_webpage, e2b_view_file, e2b_write_file, e2b_grep_search]

    await log("\n--- Starting Setup & Analysis Agent ---")
    result = await run_agent_loop(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt="Analyze this repository, install its dependencies, and verify that it can be built or its tests can be run. Report your findings.",
        tools=tools,
        log_callback=log_callback,
    )
    await log(result)
    return result
