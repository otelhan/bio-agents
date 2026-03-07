# agents.design.bio

A multi-agent AI assistant for biological design — starting with bacterial cellulose. Three specialized AI agents help designers, cultivators, and producers design, grow, and financially model bio-based materials.

Live at **agents.design.bio** · Info at `/info` · Guide at `/guide`

---

## System Overview

The system is a Python/FastAPI web application that serves a chat interface backed by three Claude-powered AI agents. Each agent has its own domain knowledge, tools, and system prompt. A lightweight classifier routes incoming messages to the right agent based on topic — or the user can address an agent directly using `@mention` syntax.

All agent responses stream in real time using Server-Sent Events (SSE). Session history is maintained in-memory per browser session. Persistent settings (knowledge base files, Google Sheets URLs, model config) are stored in a local `data/` directory that maps to a persistent volume on Railway.

---

## Architecture

```
Browser
  │
  │  POST /api/chat  (JSON: message, session_id, image_id)
  ▼
┌─────────────────────────────────────────────────────────┐
│                      FastAPI (main.py)                  │
│                                                         │
│   ┌──────────────────────────────────────────────────┐  │
│   │                  api/chat.py                     │  │
│   │                                                  │  │
│   │  1. Parse @mention  ──→  mention_router.py       │  │
│   │     └─ no mention?  ──→  orchestrator.py         │  │
│   │           (Claude Haiku classifier, max 5 tokens)│  │
│   │                                                  │  │
│   │  2. Load session history  ─→  context_store.py   │  │
│   │                                                  │  │
│   │  3. Dispatch to agent  ─────────────────────┐    │  │
│   └─────────────────────────────────────────────│────┘  │
│                                                 │        │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────┴───┐    │
│   │  @designer   │ │   @farmer    │ │    @cfo       │    │
│   │  designer.py │ │  farmer.py   │ │   cfo.py      │    │
│   └──────┬───────┘ └──────┬───────┘ └──────┬────────┘    │
│          │                │                 │             │
│          └────────────────┴─────────────────┘             │
│                           │                               │
│                    BaseAgent.stream_response()            │
│                    (agents/base.py)                       │
│                    ┌─────────────────┐                    │
│                    │  Claude Opus    │                     │
│                    │  tool_use loop  │                     │
│                    │  (parallel)     │                     │
│                    └────────┬────────┘                    │
│                             │                             │
│              ┌──────────────┼──────────────┐             │
│              ▼              ▼              ▼             │
│        kb_loader      farmer_analytics  cfo_calculator   │
│        replicate      google_sheets     tem_parser       │
│        _client        farmer_schema     settings_store   │
│                                                          │
│   4. Stream SSE chunks  ─────────────────────────────┐   │
│   5. Save to context_store                           │   │
│   6. Generate follow-up questions (Claude Haiku)     │   │
└──────────────────────────────────────────────────────│───┘
                                                       │
                        SSE stream (text/event-stream) │
                        ◄──────────────────────────────┘
Browser
  │
  └── chat.js renders markdown, updates DOM in real time
```

### SSE Event Types

| Event type    | Payload fields                          | Purpose                          |
|---------------|-----------------------------------------|----------------------------------|
| `session_id`  | `session_id`                            | Assigns/confirms session cookie  |
| `agent`       | `agent`, `agent_key`                    | Labels which agent is responding |
| `text`        | `content`                               | Streamed response chunk          |
| `follow_up`   | `agent_key`, `questions` (array of 2)  | Suggested follow-up questions    |
| `error`       | `content`                               | Error message                    |
| `done`        | —                                       | Stream complete                  |

---

## The Three Agents

### @designer — AI Designer
Advises on bacterial cellulose material design: cultivation parameters, post-processing, quality criteria, and design applications.

**Tools:**
- `search_knowledge_base` — searches uploadable `.md` KB files (design criteria, MR-1/2/3 framework, research notes)
- `analyze_bc_image` — runs a Replicate ML model on uploaded BC pellicle images; returns tensile strength, elongation, stiffness, and uniformity estimates

### @farmer — AI Farmer
Analyzes production records to surface patterns, compare recipes, and identify what drives yield and quality. Connects to Google Sheets data.

**Tools:**
- `query_runs` — filters/sorts the production runs dataset
- `query_treatments` — filters/sorts the treatments dataset
- `get_schema` — returns column definitions and dataset coverage

### @cfo — AI CFO
Runs techno-economic scenarios for BC production at any scale.

**Tools:**
- `run_tem_scenario` — full Python TEM engine: computes revenue, EBITDA, net income, profit/kg, 5-year NPV, payback period, and ROI from configurable parameters (capacity, market mix, costs, treatment methods, grade quality)

---

## File Structure

```
bio-agents/
├── main.py                    # FastAPI app: routes, middleware, static mount
├── config.py                  # Pydantic settings (env vars: API keys, admin password)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Production container (python:3.12-slim)
├── railway.json               # Railway deployment config
├── .env.example               # Environment variable template
│
├── agents/
│   ├── base.py                # BaseAgent: Claude streaming + tool_use loop (parallel)
│   ├── designer.py            # DesignerAgent: system prompt + KB + image tools
│   ├── farmer.py              # FarmerAgent: system prompt + data query tools
│   └── cfo.py                 # CFOAgent: system prompt + TEM calculator tool
│
├── router/
│   ├── mention_router.py      # Parses @designer/@farmer/@cfo from message text
│   └── orchestrator.py        # Claude Haiku classifier (no @mention fallback)
│
├── session/
│   └── context_store.py       # In-memory session store (max 50 messages, pruned)
│
├── api/
│   ├── chat.py                # POST /api/chat, GET /api/suggested, DELETE /api/session
│   ├── settings.py            # Settings CRUD: HMAC auth, KB upload, agent config
│   └── upload.py              # POST /api/upload/image (stores in data/uploads/)
│
├── tools/
│   ├── kb_loader.py           # Reads .md files from data/kb/ for knowledge base search
│   ├── replicate_client.py    # Calls Replicate API for BC image analysis
│   ├── google_sheets.py       # Fetches Google Sheets as CSV (public share links)
│   ├── farmer_analytics.py    # Pandas analytics: filter, rank, trend, feature importance
│   ├── farmer_schema.py       # Dataset schema and coverage metadata
│   ├── cfo_calculator.py      # TEM engine: revenue, costs, NPV, payback, ROI
│   ├── tem_parser.py          # Parses YAML frontmatter from CFO config .md files
│   └── settings_store.py      # Reads/writes data/settings.json
│
├── static/
│   ├── index.html             # Main chat UI
│   ├── settings.html          # Settings panel (password-protected)
│   ├── chat.js                # Frontend: SSE streaming, markdown renderer, @mention UI
│   ├── style.css              # UI styles
│   ├── info/
│   │   └── index.html         # About page (/info)
│   ├── guide/
│   │   └── index.html         # Study guide / getting started (/guide)
│   └── assets/
│       ├── screenshot-*.png   # UI screenshots used in /info
│       └── test_images.zip    # Sample BC pellicle images for @designer testing
│
└── data/                      # Runtime data (gitignored; persisted via Railway volume)
    ├── settings.json          # Agent configuration (KB files, Sheets URLs, model version)
    ├── kb/                    # Uploaded knowledge base .md files for @designer
    └── uploads/               # Uploaded BC pellicle images
```

---

## Technology Stack

| Layer         | Technology                                    |
|---------------|-----------------------------------------------|
| Backend       | Python 3.12, FastAPI, Uvicorn                 |
| AI Models     | Claude Opus 4.6 (agents), Claude Haiku 4.5 (classifier + follow-ups) |
| Streaming     | Server-Sent Events via `sse-starlette`        |
| Image ML      | Replicate (custom BC pellicle regression model) |
| Data          | Google Sheets (public CSV export), Pandas     |
| Frontend      | Vanilla JS, plain CSS (no build step)         |
| Deployment    | Railway (Docker, persistent volume)           |
| Auth          | HMAC-based stateless token for settings panel |

---

## Environment Variables

| Variable               | Required | Description                                      |
|------------------------|----------|--------------------------------------------------|
| `ANTHROPIC_API_KEY`    | Yes      | Anthropic API key for all Claude calls           |
| `REPLICATE_API_TOKEN`  | Yes      | Replicate token for BC image analysis            |
| `ADMIN_PASSWORD`       | No       | Settings panel password (default: `admin`)       |

Copy `.env.example` to `.env` and fill in values for local development.

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Start the server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`.

---

## Deployment (Railway)

The app uses two git branches:

```
main    ← active development
deploy  ← production (Railway watches this branch)
```

To release: `git merge main deploy && git push origin deploy`

Railway builds from the `Dockerfile` and injects `$PORT` at runtime. Attach a persistent volume at `/app/data` to preserve settings, knowledge base files, and uploaded images across redeploys.

**Per-instance environment variables** (set in Railway dashboard):
- `ANTHROPIC_API_KEY`
- `REPLICATE_API_TOKEN`
- `ADMIN_PASSWORD` (unique per client)

See `/info` on any deployed instance for full setup instructions.

---

## Multi-Client Deployment

Each client gets an isolated Railway project pointed at the same `deploy` branch:

```
GitHub repo  (shared, deploy branch)
    ├── Railway Project: Client A
    │     ├── ADMIN_PASSWORD=client_a_secret
    │     ├── Volume: /app/data   (A's KB, settings, uploads)
    │     └── Domain: bio-agents-a.up.railway.app
    │
    └── Railway Project: Client B
          ├── ADMIN_PASSWORD=client_b_secret
          ├── Volume: /app/data   (B's KB, settings, uploads)
          └── Domain: bio-agents-b.up.railway.app
```

Pushing to `deploy` auto-redeploys all client instances simultaneously.

---

© 2026 Orkan Telhan · [design.bio](http://design.bio)
