# Issue Hunter

**Issue Hunter** is an autonomous AI agent that resolves open-source bugs. It connects to your GitHub repository, analyzes issues, generates fixes in a secure cloud sandbox, and opens Pull Requests — all with human-in-the-loop approval.

Built with **React + Vite** frontend, **FastAPI** backend, and the **Google Antigravity SDK** for multi-agent orchestration. Deployed on **Vercel** with **Supabase** for persistence and **E2B** for secure code execution.

## Features

- **Multi-Agent Workflow** — Setup, Solver, and Reviewer agents collaborate with retry loops to produce high-quality fixes
- **Multi-LLM Support** — Native routing for Google Gemini, OpenAI, and Anthropic models
- **Multi-Git Provider** — Extensible architecture supporting GitHub, GitLab, and Bitbucket
- **Cloud Sandboxing (E2B)** — Secure, ephemeral Linux environments for code execution — no Docker required
- **Human-in-the-Loop** — Interactive diff viewer for reviewing and approving changes before PR creation
- **Real-time Streaming** — Server-Sent Events (SSE) for live agent terminal output
- **GitHub Action** — Run headlessly in CI/CD pipelines via `action.yml`
- **Agent Web Browsing** — Agents can search the web and fetch documentation while solving issues

## Architecture

```
┌─────────────────────┐     SSE Stream      ┌──────────────────────┐
│   React Frontend    │◄────────────────────►│  FastAPI (Vercel)    │
│   (Vite + Vercel)   │     REST API         │  Serverless Funcs    │
└─────────────────────┘                      └──────────┬───────────┘
                                                        │
                                    ┌───────────────────┼───────────────────┐
                                    │                   │                   │
                              ┌─────▼─────┐     ┌──────▼──────┐    ┌───────▼───────┐
                              │ Supabase  │     │ E2B Sandbox │    │ Antigravity   │
                              │ (DB/Logs) │     │ (Execution) │    │ SDK (Agents)  │
                              └───────────┘     └─────────────┘    └───────────────┘
```

## Getting Started

### Prerequisites
- Node.js (v24+)
- Python (3.12+)
- A [Supabase](https://supabase.com) project
- An [E2B](https://e2b.dev) API key
- An LLM API key (Gemini, OpenAI, or Anthropic)

### 1. Set Up Supabase
Create a Supabase project and run `supabase_schema.sql` in the SQL Editor to create the required tables.

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Local Development
```bash
# Backend
pip install -r requirements.txt
cd backend && uvicorn server:app --port 8000 --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. Deploy to Vercel
```bash
npx vercel --prod
```
Set the following environment variables in your Vercel dashboard:
- `SUPABASE_URL`, `SUPABASE_KEY`
- `E2B_API_KEY`
- `ADMIN_PASSWORD`

## CLI Usage
```bash
python main.py \
  --repo owner/repo \
  --issues 123,124 \
  --provider gemini \
  --api-key YOUR_KEY
```

## GitHub Action
```yaml
- uses: your-username/issue-hunter@main
  with:
    api-key: ${{ secrets.GEMINI_API_KEY }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    e2b-api-key: ${{ secrets.E2B_API_KEY }}
    supabase-url: ${{ secrets.SUPABASE_URL }}
    supabase-key: ${{ secrets.SUPABASE_KEY }}
    issue-number: '123'
```

## Agent Workflow
1. **Setup Phase** — Clones the repository into an E2B cloud sandbox and analyzes the build system
2. **Solving Phase** — Uses code search and web browsing to locate and fix the bug
3. **Review Phase** — A secondary agent reviews the code changes (up to 3 retry loops)
4. **Approval Phase** — Pauses for human approval via the UI diff viewer
5. **PR Phase** — Pushes the branch and opens a Pull Request

## License
MIT
