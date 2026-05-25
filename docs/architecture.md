# Architecture Overview

Issue Hunter operates as a robust agentic application separated into frontend, backend, and agent logic.

## 1. System Components
- **Frontend (React / Vite):** Presents a clean Glassmorphism interface. Manages state for Hunt Configuration, Live Terminal streaming via WebSockets, History parsing, and the interactive Diff Viewer.
- **Backend (FastAPI):** Exposes REST API endpoints and WebSockets for real-time Agent communication. Manages the SQLite database for persistence.
- **Agent Orchestrator (Antigravity SDK):** The core engine residing in `agents/orchestrator.py`. Handles the multi-step workflows of cloning repositories, setting up Docker sandboxes, initializing RAG embeddings, and dispatching tasks to specific sub-agents. It natively routes prompts to any underlying LLM (OpenAI, Anthropic, Gemini) by managing API keys directly in the environment, making the SDK model-agnostic.

## 2. Multi-Agent Workflow
1. **Setup Agent:** Inspects the repository structure and ensures the issue can be reproduced within the Docker container.
2. **Solver Agent:** Equipped with the `semantic_search` tool, it queries ChromaDB for relevant AST nodes and rewrites source files to fix the issue.
3. **Reviewer Agent:** Critiques the generated git diff. If the fix fails criteria, it kicks the context back to the Solver Agent (max 3 retries).
4. **Approval Block:** Emits an `[APPROVAL_REQUIRED]` socket event. Pauses execution entirely while the frontend displays the diff viewer.
5. **Committer:** Once the human approves, pushes the branch and creates the Pull Request using the abstract `GitProvider`.

## 3. Git Provider Abstraction
To support GitHub, GitLab, and Bitbucket uniformly, `agents/git_provider.py` enforces a unified `GitProvider` interface with abstract methods:
- `get_issue_details(repo, issue_id)`
- `create_pull_request(repo, title, body, head_branch, base_branch)`

`GitHubProvider` wraps `PyGithub`, while `GitLabProvider` and `BitbucketProvider` are structured mock interfaces ready for API implementations.

## 4. RAG Implementation (Retrieval-Augmented Generation)
`agents/indexer.py` handles the chunking.
- It parses Python source code into an Abstract Syntax Tree (`ast`).
- It maps unique `file_path::node_name::index` IDs for every Class and Function to prevent ChromaDB collisions.
- It embeds the source code using `sentence-transformers` and upserts it into the local `chromadb` instance.
