# Architecture Overview

Issue Hunter is a full-stack agentic application deployed on Vercel with external services for persistence and code execution.

## System Components

### Frontend (React / Vite)
A glassmorphism-styled dashboard that provides:
- Hunt configuration (repo URL, issue numbers, LLM settings)
- Live terminal streaming via Server-Sent Events (SSE)
- Interactive diff viewer for human-in-the-loop approval
- Hunt history and benchmark management

Deployed as static assets on Vercel.

### Backend (FastAPI / Vercel Serverless)
Serverless Python functions that expose REST API endpoints. Key constraints:
- **Read-only filesystem** — all state persists in Supabase
- **300s max execution** (Vercel Pro) — long-running hunts stream via SSE within this window
- **No WebSockets** — replaced with SSE for real-time communication
- **No Docker daemon** — code execution delegated to E2B cloud sandboxes

### Agent Orchestrator (Antigravity SDK)
The core engine in `agents/orchestrator.py` that coordinates the multi-agent workflow:
1. **Setup Agent** — Analyzes the repository structure and verifies the build system
2. **Solver Agent** — Locates relevant code and implements the fix
3. **Reviewer Agent** — Critiques the git diff; rejects trigger retry loops (max 3)
4. **Approval Gate** — Streams `__APPROVAL_REQUIRED__` signal; polls Supabase for user decision
5. **PR Creation** — Pushes the branch and creates the Pull Request via the Git provider

### External Services

| Service | Purpose |
|---|---|
| **Supabase** | PostgreSQL database for hunt tracking, logs, and approval state |
| **E2B** | Secure, ephemeral cloud Linux sandboxes for executing git, npm, pytest, etc. |
| **LLM Providers** | Gemini, OpenAI, or Anthropic — routed natively via Antigravity SDK |

## Git Provider Abstraction
`agents/git_provider.py` implements a strategy pattern supporting GitHub (via PyGithub), GitLab (via python-gitlab), and Bitbucket (via atlassian-python-api).

## Data Flow
```
User → Frontend → POST /api/hunt → SSE Stream
                                      │
                                      ├─ Orchestrator starts E2B sandbox
                                      ├─ Clones repo into sandbox
                                      ├─ Runs Setup → Solver → Reviewer loop
                                      ├─ Streams logs to frontend via SSE
                                      ├─ On approval needed: writes to Supabase, polls
                                      ├─ On approval: pushes branch, creates PR
                                      └─ Returns final report
```
