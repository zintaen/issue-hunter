# Issue Hunter - Backlog & Tasks

## High Priority (Next Up)

1. **Human-in-the-Loop Web Editor (React Diff Viewer)**
   - **Description:** Integrate a code diff viewer (e.g., `react-diff-viewer-continued` or `monaco-editor`) into the web dashboard.
   - **Goal:** Allow users to view the exact changes proposed by the Reviewer Agent and manually tweak code in the browser before approving the merge.

2. **Intelligent Codebase Search (AST / RAG)**
   - **Description:** Replace blind `grep`/`find` searches with semantic code search.
   - **Goal:** Embed the repository files into a local vector database (like ChromaDB or local FAISS) so the Setup Agent can perform semantic queries to locate relevant functions and classes instantly, significantly reducing context window size and API costs.

3. **GitLab & Bitbucket Support**
   - **Description:** Abstract the Git interaction layers.
   - **Goal:** Allow webhooks and API calls to parse issue contexts and push branches to GitLab and Bitbucket, not just GitHub.

## Medium Priority

4. **Cloud-Native Sandboxing (E2B / Modal)**
   - **Description:** Replace local Docker socket mounting with cloud-based sandboxing.
   - **Goal:** Ensure untrusted code from PRs or agent hallucinations is executed in secure, ephemeral microVMs rather than sibling containers on the host.

5. **Deployment Automation**
   - **Description:** Create IaC (Infrastructure as Code) scripts (Terraform/Docker Swarm).
   - **Goal:** One-click deploy the backend, frontend, and DB to AWS EC2, Google Cloud Run, or DigitalOcean.

## Low Priority (Future)

6. **Consensus Agent for Auto-Tuning**
   - **Description:** An agent that analyzes historical benchmark performance and fine-tunes the system prompts of the Solver and Reviewer over time to improve success rates.
