# Issue Hunter

**Issue Hunter** is an autonomous AI agent designed to resolve open-source bugs. Built with a React frontend and a FastAPI backend using the Google Antigravity SDK, it connects to your code repository, reproduces issues, generates fixes, and requests human approval before opening a pull request.

## Features

### 1. Multi-Git Provider Architecture (GitHub, GitLab, Bitbucket)
Issue Hunter supports an extensible `GitProvider` strategy pattern, allowing it to seamlessly interface with major platforms natively via API SDKs (`python-gitlab`, `httpx`). The orchestrator dynamically routes operations to the correct provider based on the repository URL.

### 2. Multi-Language Codebase Search (Tree-sitter & RAG)
To prevent agents from getting lost in massive codebases, Issue Hunter employs a local vector database (`ChromaDB`).
- **Tree-sitter Chunking:** Deep structural AST parsing for Python, TypeScript, JavaScript, and Go ensures semantic integrity when indexing.
- **Semantic Search Tool:** The `semantic_search` tool allows agents to query the codebase using natural language to retrieve exact logic chunks.

### 3. Native Multi-LLM Provider Support
Issue Hunter maps API keys directly to the native Google Antigravity SDK environment variables, allowing seamless use of `gemini`, `openai`, and `anthropic` providers without the need for proxy middlewares.

### 4. Agent Web Browsing
The agents are equipped with `web_search` and `fetch_webpage` tools, giving them the ability to look up Stack Overflow discussions or external documentation while solving issues.

### 5. Human-in-the-Loop Diff Viewer
Before submitting a pull request, Issue Hunter requires human approval. A custom-built, lightweight React diff component provides a visual representation of proposed changes. Approving authorizes the agent to push the branch and open a PR.

### 6. GitHub Action Headless Mode
Issue Hunter can be executed headlessly within your CI/CD pipelines via the provided `action.yml` package.

## Getting Started

### Prerequisites
- Node.js (v24+)
- Python (3.12+)

### Local Setup

1. **Start the Backend:**
   ```bash
   pip install -r requirements.txt
   cd backend
   uvicorn server:app --port 8000 --reload
   ```

2. **Start the Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Configure the Hunt:**
   Open `http://localhost:5175` in your browser. Enter your target repository, the issue number, your Git Provider token, and your LLM API Key to start a hunt!

## Agent Workflow
1. **Setup Phase:** Clones the repository, sets up the environment, and indexes the codebase.
2. **Reproduction Phase:** Attempts to reproduce the issue using context or by writing test cases.
3. **Solving Phase:** Uses semantic search and web browsing to locate and solve the bug.
4. **Review Phase:** A secondary agent reviews the code changes.
5. **Approval Phase:** Pauses and waits for user approval via the UI Diff Viewer.
6. **PR Phase:** The fix is pushed and a Pull Request is automatically generated.
