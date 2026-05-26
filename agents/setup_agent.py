import asyncio
from agents.llm_client import run_agent_loop
from agents.tools import (
    sandbox_run, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search
)

async def run_setup_agent(repo_dir: str, issue_details: str, api_key: str, model: str = None, log_callback=None, provider: str = "gemini", base_url: str = None) -> str:
    """Runs the Setup Agent to analyze the repository structure and map it to the issue."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)

    system_prompt = (
        "You are an expert software engineer. Your ONLY goal is to quickly analyze "
        "a repository and produce a concise summary that helps a Solver Agent fix a specific issue.\n\n"
        "The repository is cloned at the path provided in the user prompt.\n\n"
        "RULES:\n"
        "- Do NOT install dependencies, build the project, or run tests. That is the Solver Agent's job.\n"
        "- Do NOT run `npm install`, `pip install`, `pnpm install`, `make`, or any build/test command.\n"
        "- Keep your exploration focused: max 10-12 tool calls.\n\n"
        "STEPS:\n"
        "1. Run `ls` on the repo root to see the top-level structure.\n"
        "2. Read README.md (first 200 lines) to understand what the project is.\n"
        "3. Identify the project type: monorepo (look for workspaces in package.json, pnpm-workspace.yaml, lerna.json) or single package.\n"
        "4. For a monorepo, list the packages/modules. Identify which package is most relevant to the issue.\n"
        "5. Use `e2b_grep_search` to find files/code related to keywords from the issue.\n"
        "6. Read 1-2 key files that are most relevant to the issue.\n\n"
        "OUTPUT FORMAT (you MUST follow this exactly):\n"
        "```\n"
        "PROJECT: <name>\n"
        "TYPE: <monorepo|single-package>\n"
        "LANGUAGES: <comma-separated>\n"
        "RELEVANT_PACKAGE: <path to the most relevant package/directory for the issue>\n"
        "BUILD_SYSTEM: <npm|pnpm|yarn|pip|poetry|make|cargo|etc>\n"
        "KEY_FILES: <comma-separated list of files most relevant to the issue>\n"
        "ANALYSIS: <2-3 sentences about what needs to change to fix the issue>\n"
        "```"
    )

    tools = [sandbox_run, web_search, fetch_webpage, e2b_view_file, e2b_grep_search]

    await log("\n--- Starting Setup & Analysis Agent ---")
    result = await run_agent_loop(
        client=None,
        model=model,
        system_prompt=system_prompt,
        user_prompt=f"Analyze this repository (cloned at {repo_dir}) in the context of this issue:\n\n{issue_details}\n\nProduce a focused analysis summary.",
        tools=tools,
        max_iterations=15,
        log_callback=log_callback,
        provider=provider,
        base_url=base_url,
        api_key=api_key
    )
    await log(result)
    return result
