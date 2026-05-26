import os
import asyncio
from typing import List
from agents.tools import (
    init_clients,
    fork_and_clone_repo,
    start_sandbox,
    cleanup_sandbox,
    get_git_diff
)
from agents.setup_agent import run_setup_agent
from agents.solver_agent import run_solver_agent
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
    base_url: str = None,
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

    await log(f"Using AI: provider={provider}, model={model}")
    if base_url:
        await log(f"Custom base URL: {base_url}")

    await log(f"Starting Issue Hunter workflow for {target_repo}...")
    
    await log_with_db("Initializing Git Provider...")
    git_provider = get_git_provider(target_repo, github_token)
    
    init_clients(github_token, workspace_base_dir)

    repo_full_name = target_repo.split("github.com/")[-1].replace(".git", "") if "github.com" in target_repo else target_repo.split("/")[-2] + "/" + target_repo.split("/")[-1].replace(".git", "")
    
    await log_with_db(f"Cloning repository {target_repo} into E2B Sandbox...")
    repo_name = repo_full_name.split('/')[-1]
    clone_dir = os.path.join(workspace_base_dir, repo_name)
    
    report_lines = [
        f"# Issue Hunter Report for {target_repo}",
        "",
        "| Issue | Branch | PR Link | Status |",
        "|---|---|---|---|"
    ]
    final_branch_name = None
    
    try:
        # Start E2B Sandbox
        start_sandbox(clone_dir)
        
        # Fork and Clone inside E2B
        fork_and_clone_repo(repo_full_name, clone_dir)
        
        # Fetch issue details early so setup agent can focus
        all_issue_details = {}
        for issue_num in issue_numbers:
            all_issue_details[issue_num] = git_provider.fetch_issue_details(repo_full_name, issue_num)
        
        # Combine issue details for setup context
        combined_issue_context = "\n\n---\n\n".join([
            f"Issue #{num}:\n{details}" for num, details in all_issue_details.items()
        ])
        
        await log("\n--- Phase 1: Setup & Analysis ---")
        setup_summary = await run_setup_agent(clone_dir, combined_issue_context, api_key, model, log_callback, provider=provider, base_url=base_url)
        await log("Setup Phase Complete.\n")
        
        await log(f"\n--- Phase 2: Processing {len(issue_numbers)} Issues ---")
        for issue_num in issue_numbers:
            await log_with_db(f"\n--- Phase 2: Processing Issue #{issue_num} ---")
            
            issue_details = all_issue_details[issue_num]
            await log_with_db(f"Fetched issue details for #{issue_num}.")
            
            branch_name = f"fix-issue-{issue_num}"
            
            max_retries = 3
            success = False
            previous_feedback = None
            solver_summary = ""
            
            for attempt in range(max_retries):
                await log(f"\n[ATTEMPT {attempt + 1}/{max_retries}] Running Solver Agent...")
                solver_result = await run_solver_agent(clone_dir, issue_details, branch_name, setup_summary, api_key, model, previous_feedback, log_callback, provider=provider, base_url=base_url)
                
                if not solver_result:
                    await log("Solver Agent failed to complete its execution.")
                    break
                
                solver_success, solver_summary = solver_result
                    
                await log(f"\n[ATTEMPT {attempt + 1}/{max_retries}] Running Reviewer Agent...")
                reviewer_approved, feedback = await run_reviewer_agent(clone_dir, issue_details, branch_name, api_key, model, log_callback, provider=provider, base_url=base_url)
                
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
                    if not dry_run:
                        await log_with_db("Creating Pull Request...")
                        
                        pr_body = (
                            f"This PR fixes issue #{issue_num}.\n\n"
                            f"It was automatically generated by Issue Hunter. "
                            f"The agent has analyzed the issue and made the necessary code changes.\n\n"
                            f"---\n\n"
                            f"**Summary of changes:**\n\n"
                            f"{solver_summary}"
                        )
                        
                        pr_result = git_provider.create_pull_request(
                            repo_full_name, 
                            branch_name, 
                            f"Fix issue #{issue_num}", 
                            pr_body
                        # Use the PR body as the report output so it saves nicely to the database
                        report_lines.append(f"## Issue #{issue_num}\n\n**Pull Request:** {pr_result}\n\n{pr_body}\n")
                        final_branch_name = branch_name
            else:
                report_lines.append(f"## Issue #{issue_num}\n\n❌ Solver Failed to complete the fix.\n")
                
    finally:
        # 7. Cleanup
        await log("\nCleaning up...")
        cleanup_sandbox()
        
    # 8. Generate Report
    report_content = "\n".join(report_lines)
    
    await log(f"\nWorkflow complete! Report generated.")
    return report_content, final_branch_name
