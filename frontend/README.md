# Text-to-SQL Frontend

Chatbot UI for the text-to-sql backend. Built with Next.js 16, Tailwind CSS, and shadcn/ui.

## Setup

Requires the backend running on port 8000.

```bash
npm install
npm run dev       # http://localhost:3000
```

## Features

- **SSE streaming** — Real-time pipeline step visualization as the backend processes queries
- **Multi-turn sessions** — Conversation sidebar with localStorage persistence
- **SQL display** — Syntax-highlighted SQL in collapsible accordions (shiki, github-light theme)
- **Data tables** — Sortable, paginated results via TanStack React Table
- **Markdown answers** — LLM responses rendered with react-markdown
- **SQL approval** — Review, edit, and approve/reject queries flagged by validation
- **Health indicator** — Live backend connection status dot

## Architecture

All API calls proxy through Next.js rewrites (`/api/*` -> `localhost:8000/api/*`). No backend changes required.

The frontend consumes the backend's SSE protocol directly via three custom hooks:

- `use-sse-stream` — Opens EventSource, listens to 24 named event types, builds pipeline steps
- `use-chat` — Manages message array, wires streaming updates into assistant messages
- `use-session` — CRUD for conversation sessions backed by localStorage

## Tech Stack

- Next.js 16 (App Router)
- Tailwind CSS v4 + shadcn/ui (New York style, zinc palette)
- TanStack React Table v8
- shiki (SQL syntax highlighting)
- react-markdown
- lucide-react (icons)
