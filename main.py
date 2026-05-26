import os
import argparse
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from agents.orchestrator import run_orchestrator

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Issue Hunter - Autonomous GitHub Issue Solver")
    parser.add_argument("--repo", type=str, required=True, help="Target repository (e.g. 'owner/repo')")
    parser.add_argument("--issues", type=str, required=True, help="Comma-separated list of issue numbers (e.g. '123,124')")
    parser.add_argument("--model", type=str, default=None, help="Model to use (overrides .env)")
    parser.add_argument("--provider", type=str, default="gemini", help="LLM Provider (gemini, openai, anthropic)")
    parser.add_argument("--api-key", type=str, default=None, help="API Key for the provider")
    parser.add_argument("--workspace", type=str, default="./workspace", help="Directory to clone repositories into")
    parser.add_argument("--dry-run", action="store_true", help="Skip actually creating the Pull Request on GitHub")
    parser.add_argument("--base-url", type=str, default=None, help="Custom base URL for the LLM provider")
    return parser.parse_args()

async def main():
    load_dotenv()
    args = parse_args()
    
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        try:
            import subprocess
            github_token = subprocess.check_output(["gh", "auth", "token"]).decode("utf-8").strip()
            console.print("[green]Successfully retrieved GitHub token from gh CLI.[/green]")
        except Exception as e:
            console.print(f"[yellow]Failed to get token from gh CLI: {e}[/yellow]")
            
    if not github_token:
        console.print("[red]Error: GITHUB_TOKEN not found in environment and gh cli auth failed.[/red]")
        return
        
    model = args.model or os.getenv("LLM_MODEL") or "gemini-3.5-pro"
    provider = args.provider
    if provider == 'openai':
        api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    elif provider == 'anthropic':
        api_key = args.api_key or os.getenv('ANTHROPIC_API_KEY')
    else:
        api_key = args.api_key or os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        console.print("[red]Error: API Key not provided.[/red]")
        return
        
    console.print(f"[green]Using provider: {provider}, model: {model}[/green]")
    
    issue_numbers = [int(i.strip()) for i in args.issues.split(",") if i.strip().isdigit()]
    if not issue_numbers:
        console.print("[red]Error: No valid issue numbers provided.[/red]")
        return
        
    # Ensure workspace exists
    workspace_dir = os.path.abspath(args.workspace)
    os.makedirs(workspace_dir, exist_ok=True)
    
    try:
        await run_orchestrator(
            target_repo=args.repo,
            issue_numbers=issue_numbers,
            github_token=github_token,
            workspace_base_dir=workspace_dir,
            api_key=api_key,
            model=model,
            provider=provider,
            dry_run=args.dry_run,
            base_url=args.base_url
        )
    except KeyboardInterrupt:
        console.print("[yellow]\nWorkflow interrupted by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Workflow failed with error: {e}[/red]")
        raise

if __name__ == "__main__":
    asyncio.run(main())
