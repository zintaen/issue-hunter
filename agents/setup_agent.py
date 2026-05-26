import asyncio
from agents.llm_client import run_agent_loop
from agents.tools import (
    sandbox_run, web_search, fetch_webpage,
    e2b_view_file, e2b_write_file, e2b_grep_search
)

async def run_setup_agent(repo_dir: str, issue_details: str, api_key: str, model: str = None, log_callback=None, provider: str = "gemini", base_url: str = None) -> str:
    """Runs the Setup Agent to deeply scan the codebase and produce a fix plan."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)

    system_prompt = (
        "You are an expert software engineer. Your goal is to deeply scan a codebase "
        "and produce a detailed analysis that enables a Solver Agent to write the correct fix.\n\n"
        "The repository is cloned at the path provided in the user prompt.\n\n"
        "RULES:\n"
        "- Do NOT install dependencies, build the project, or run any tests.\n"
        "- Do NOT run `npm install`, `pip install`, `pnpm install`, `make`, or any build/test command.\n"
        "- ONLY use `sandbox_run` for `ls`, `find`, `cat`, `head`, `tail`, `wc` — read-only commands.\n"
        "- Focus on understanding the code deeply, not on setting up the environment.\n\n"
        "STEPS:\n"
        "1. `ls` the repo root to see top-level structure.\n"
        "2. Read README.md or CONTRIBUTING.md (use `sandbox_run('head -100 <path>')`) for project overview.\n"
        "3. Identify if it's a monorepo. If so, list packages and identify the relevant one for the issue.\n"
        "4. Use `e2b_grep_search` with keywords from the issue to find the exact files and functions involved.\n"
        "5. Read the relevant source files thoroughly using `e2b_view_file`.\n"
        "6. Trace the code path: find where the bug originates, what functions call it, what the expected behavior should be.\n"
        "7. Read any related test files to understand expected behavior.\n\n"
        "OUTPUT FORMAT (you MUST follow this exactly):\n"
        "```\n"
        "PROJECT: <name>\n"
        "TYPE: <monorepo|single-package>\n"
        "LANGUAGES: <comma-separated>\n"
        "RELEVANT_PACKAGE: <path to the most relevant package/directory>\n"
        "BUILD_SYSTEM: <npm|pnpm|yarn|pip|poetry|make|cargo|etc>\n"
        "\n"
        "ROOT_CAUSE: <detailed explanation of what causes the bug>\n"
        "FIX_STRATEGY: <step-by-step description of what code changes are needed>\n"
        "\n"
        "FILES_TO_MODIFY:\n"
        "- <full/path/to/file1.ts>: <what to change and why>\n"
        "- <full/path/to/file2.ts>: <what to change and why>\n"
        "\n"
        "FILES_FOR_REFERENCE (read-only context):\n"
        "- <full/path/to/related_file.ts>: <why it's relevant>\n"
        "\n"
        "CODE_SNIPPETS:\n"
        "<paste the exact current code that needs to change, with line context>\n"
        "```"
    )

    tools = [sandbox_run, web_search, fetch_webpage, e2b_view_file, e2b_grep_search]

    await log("\n--- Starting Setup & Analysis Agent ---")
    result = await run_agent_loop(
        client=None,
        model=model,
        system_prompt=system_prompt,
        user_prompt=f"Analyze this repository (cloned at {repo_dir}) in the context of this issue:\n\n{issue_details}\n\nScan the codebase deeply. Find the root cause and produce a detailed fix plan.",
        tools=tools,
        max_iterations=25,
        log_callback=log_callback,
        provider=provider,
        base_url=base_url,
        api_key=api_key
    )
    await log(result)
    return result
