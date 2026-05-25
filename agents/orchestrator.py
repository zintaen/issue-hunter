import os
import asyncio
import re
from typing import List
from agents.tools import (
    init_clients,
    fork_and_clone_repo,
    start_docker_container,
    cleanup_docker_container,
    get_git_diff
)
from agents.setup_agent import run_setup_agent
from agents.solver_agent import run_solver_agent
from agents.indexer import RepoIndexer
from agents.reviewer_agent import run_reviewer_agent
from agents.git_provider import get_git_provider

async def run_orchestrator(
    target_repo: str,
    issue_numbers: List[int],
    github_token: str,
    workspace_base_dir: str,
    api_key: str,
    model: str = None,
    provider: str = "gemini",
    dry_run: bool = False,
    log_callback = None,
    approval_callback = None
):
    """Orchestrates the entire Issue Hunter workflow."""
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)
        else:
            print(msg)
            
    async def log_with_db(msg: str):
        await log(msg)

    # Natively route OpenAI and Anthropic models by setting their respective environment variables
    # The Antigravity SDK will pick these up automatically based on the model provided.
    if provider == "openai":
        os.environ["OPENAI_API_KEY"] = api_key
        await log(f"Native routing for OpenAI model: {model}")
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
        await log(f"Native routing for Anthropic model: {model}")
    else:
        os.environ["GEMINI_API_KEY"] = api_key
        await log(f"Native routing for Gemini model: {model}")

    if "GEMINI_API_BASE" in os.environ:
        del os.environ["GEMINI_API_BASE"]

    await log(f"Starting Issue Hunter workflow for {target_repo}...")
    
    # 1. Setup GitHub/GitLab/Bitbucket Provider
    await log_with_db("Initializing Git Provider...")
    git_provider = get_git_provider(target_repo, github_token)
    
    init_clients(github_token, workspace_base_dir)

    repo_full_name = target_repo.split("github.com/")[-1].replace(".git", "") if "github.com" in target_repo else target_repo.split("/")[-2] + "/" + target_repo.split("/")[-1].replace(".git", "")
    
    # 2. Clone Repository
    await log_with_db(f"Cloning repository {target_repo}...")
    repo_name = repo_full_name.split('/')[-1]
    clone_dir = os.path.join(workspace_base_dir, repo_name)
    fork_and_clone_repo(repo_full_name, clone_dir)
    
    repo_name = target_repo.split('/')[-1]
    
    report_lines = [
        f"# Issue Hunter Report for {target_repo}",
        "",
        "| Issue | Branch | PR Link | Status |",
        "|---|---|---|---|"
    ]
    
    try:
        # 3. Start Docker Sandbox
        start_docker_container(clone_dir)
        
        # Index the repository for Semantic Search
        await log("Indexing repository for semantic search...")
        try:
            indexer = RepoIndexer(persist_dir=os.path.join(clone_dir, ".chroma_db"))
            indexer.index_repo(clone_dir)
            await log("Repository indexing complete.")
        except Exception as e:
            await log(f"Repository indexing failed: {e}")
        
        # 4. Run Setup Agent
        await log("\n--- Phase 1: Setup & Analysis ---")
        setup_summary = await run_setup_agent(clone_dir, api_key, model, log_callback)
        await log("Setup Phase Complete.\n")
        
        # 5. Process Issues
        await log(f"\n--- Phase 2: Processing {len(issue_numbers)} Issues ---")
        for issue_num in issue_numbers:
            await log_with_db(f"\n--- Phase 2: Processing Issue #{issue_num} ---")
            
            issue_details = git_provider.fetch_issue_details(repo_full_name, issue_num)
            await log_with_db(f"Fetched issue details for #{issue_num}.")
            
            branch_name = f"fix-issue-{issue_num}"
            
            # Retry Loop for Solver + Reviewer
            max_retries = 3
            success = False
            previous_feedback = None
            solver_summary = ""
            
            for attempt in range(max_retries):
                await log(f"\n[ATTEMPT {attempt + 1}/{max_retries}] Running Solver Agent...")
                solver_result = await run_solver_agent(clone_dir, issue_details, branch_name, api_key, model, previous_feedback, log_callback)
                
                if not solver_result:
                    await log("Solver Agent failed to complete its execution.")
                    break
                
                solver_success, solver_summary = solver_result
                    
                # Run Reviewer Agent
                await log(f"\n[ATTEMPT {attempt + 1}/{max_retries}] Running Reviewer Agent...")
                reviewer_approved, feedback = await run_reviewer_agent(clone_dir, issue_details, api_key, model, log_callback)
                
                if reviewer_approved:
                    success = True
                    break
                else:
                    previous_feedback = feedback
                    await log("Reviewer rejected the changes. Looping back to Solver...")
            
            if success:
                # 6. Create PR
                if dry_run:
                    await log(f"DRY RUN: Would have created PR from branch '{branch_name}'")
                    report_lines.append(f"| #{issue_num} | `{branch_name}` | N/A (Dry Run) | ⚠️ Skipped PR |")
                else:
                    approved = True
                    if approval_callback:
                        await log(f"Waiting for manual approval before creating PR...")
                        diff_content = get_git_diff(clone_dir, branch_name)
                        approved = await approval_callback(branch_name, diff_content)
                    
                    if not approved:
                        await log(f"PR Creation rejected by user for branch '{branch_name}'")
                        report_lines.append(f"| #{issue_num} | `{branch_name}` | N/A | ❌ Rejected |")
                    if not dry_run:
                        await log_with_db("Creating Pull Request...")
                        pr_result = git_provider.create_pull_request(
                            repo_full_name, 
                            branch_name, 
                            f"Fix issue #{issue_num}", 
                            f"This PR fixes issue #{issue_num} automatically via Issue Hunter.\n\n### Agent Summary\n{solver_summary}"
                        )
                        await log_with_db(pr_result)
                        report_lines.append(f"| #{issue_num} | `{branch_name}` | {pr_result} | ✅ Created |")
            else:
                report_lines.append(f"| #{issue_num} | `{branch_name}` | N/A | ❌ Solver Failed |")
                
    finally:
        # 7. Cleanup
        await log("\nCleaning up...")
        cleanup_docker_container()
        
    # 8. Generate Report
    report_content = "\n".join(report_lines)
    report_path = os.path.join(workspace_base_dir, f"report_{repo_name}.md")
    with open(report_path, "w") as f:
        f.write(report_content)
    
    await log(f"\nWorkflow complete! Report generated at: {report_path}")
    return report_content
