# API Reference

Issue Hunter exposes a REST API via FastAPI, deployed as Vercel Serverless Functions.

All endpoints (except `/api/login` and `/api/webhook/github`) require authentication via `Authorization: Bearer <token>` header.

## Authentication

### `POST /api/login`
Authenticates with the admin password.
- **Body:** `{ "password": "your_admin_password" }`
- **Returns:** `{ "token": "<token>" }`

## Hunt Endpoints

### `POST /api/hunt`
Starts a new hunt workflow. Returns an **SSE stream** of real-time agent logs.
- **Body:**
  ```json
  {
    "repo_url": "https://github.com/owner/repo",
    "issues": [123],
    "provider": "gemini",
    "model": "gemini-3.5-pro",
    "api_key": "your_llm_key",
    "github_token": "ghp_...",
    "base_url": "https://optional-custom-endpoint.com/v1"
  }
  ```
- **Response:** `text/event-stream` — each line is `data: <message>\n\n`
- **Special signals:** `__APPROVAL_REQUIRED__:<repo_name>` triggers the approval UI

### `GET /api/hunts`
Retrieves all hunts from Supabase, ordered by creation date.
- **Returns:** Array of hunt objects

### `GET /api/hunts/{hunt_id}/logs`
Retrieves stored logs for a specific hunt.
- **Returns:** Array of log strings

## Approval Endpoints

### `GET /api/approvals`
Fetches all hunts with `pending_approval` status.
- **Returns:** `{ "pending": [{ "hunt_id": "...", "repo_name": "...", "branch": "...", "diff": "..." }] }`

### `POST /api/approve`
Submits approval or rejection for a pending hunt.
- **Body:** `{ "hunt_id": "<UUID>", "action": "approve" | "reject" }`
- **Returns:** `{ "status": "Action approve applied" }`

## Webhook

### `POST /api/webhook/github`
Listens for GitHub issue comments containing `@issue-hunter fix this` to automatically trigger a workflow.
- **Note:** On Vercel, this runs synchronously and may exceed GitHub's webhook timeout, but the function will continue executing.
- **Required env vars:** `AI_API_KEY`, `GITHUB_TOKEN`, `AI_PROVIDER`, `AI_MODEL_NAME`
