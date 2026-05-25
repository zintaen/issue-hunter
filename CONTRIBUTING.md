# Contributing to Issue Hunter

Thank you for your interest in contributing to Issue Hunter! This guide will help you set up your environment and submit your first Pull Request.

## Architecture Overview

Issue Hunter is composed of three main layers:
1.  **Frontend:** React UI (`/frontend`) utilizing modern glassmorphism design. Communicates via REST APIs and WebSockets.
2.  **Backend:** FastAPI (`/backend/server.py`) serving as a bridge between the UI and the agent orchestrator.
3.  **Agents:** Google Antigravity SDK (`/agents`). The core logic where the setup, solving, and reviewing agents collaborate to fix bugs.

## How to Contribute

1.  **Fork and Clone:** Fork the repository and clone it to your local machine.
2.  **Install Dependencies:**
    *   Backend: `pip install -r requirements.txt`
    *   Frontend: `cd frontend && npm install`
3.  **Make Changes:** Implement your feature or bugfix.
4.  **Test Locally:** Run the frontend and backend servers, open `http://localhost:5175`, and trigger a hunt against a test repository.
5.  **Submit a PR:** Push your changes to your fork and submit a Pull Request describing your implementation.

## Agent System Modifications
If you are modifying the agents (`agents/solver_agent.py`, `agents/reviewer_agent.py`), ensure that any new tools created in `agents/tools.py` are properly exposed in the respective agent configurations.

## Adding new LLM Providers
Issue Hunter dynamically routes providers via `orchestrator.py`. If adding a new provider, ensure the API key environment variable is mapped correctly using the SDK's standard conventions.
