# ArXiv Research Agent

Enter a topic → arXiv search (LLM-expanded queries) → cross-encoder + LLM
reranking → structured insight extraction → LLM-built research map rendered
as an interactive D3 force-directed graph.

## Pipeline

1. **Find papers** — LLM expands the topic into several arXiv search queries
   (arXiv search is keyword-based, so this improves recall), results are
   deduplicated.
2. **Rank papers** — a local cross-encoder (`sentence-transformers`) scores
   topic-vs-abstract relevance for all candidates; the shortlist then gets a
   finer LLM relevance score (0-100) + one-line justification via Groq.
3. **Extract insights** — each paper's abstract is sent to the LLM with a
   fixed schema (problem, method, key results, datasets, limitations).
4. **Map research** — the structured extractions are sent to the LLM, which
   clusters papers thematically and outputs a graph (nodes, edges, clusters,
   open problems) rendered in the frontend.

Stages stream to the frontend via Server-Sent Events so the UI shows live
progress instead of one long blocking spinner.

## Project structure

```
arxiv-research-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # env-based settings
│   │   ├── pipeline.py          # orchestrates all 4 stages (sync helper)
│   │   ├── models/schemas.py    # Pydantic models shared across stages
│   │   ├── routers/research.py  # /api/research and /api/research/stream
│   │   └── services/
│   │       ├── groq_client.py   # Groq chat/JSON wrapper
│   │       ├── arxiv_search.py  # Stage 1
│   │       ├── reranker.py      # Stage 2
│   │       ├── extraction.py    # Stage 3
│   │       └── synthesis.py     # Stage 4
│   ├── requirements.txt
│   ├── render.yaml              # Render deployment config
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/page.tsx              # main page, wires stages + UI
    │   ├── components/
    │   │   ├── ResearchGraph.tsx     # D3 force-directed graph
    │   │   ├── StageProgress.tsx     # pipeline progress pills
    │   │   └── PaperList.tsx
    │   ├── lib/api.ts                # SSE streaming client
    │   └── types/research.ts         # TS types mirroring backend schemas
    └── .env.local.example
```

## Local setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Edit `.env` and set `GROQ_API_KEY` (get one free at https://console.groq.com).

```bash
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. Check `http://localhost:8000/health`.

> First request will be slow — the cross-encoder model downloads on first use
> (~100MB, cached afterward).

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux
npm run dev
```

Frontend runs at `http://localhost:3000`.

## Deployment

### Backend on Render

1. Push this repo to GitHub (see below).
2. In Render: New → Web Service → connect repo → it should auto-detect
   `backend/render.yaml`. If not, set manually:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add environment variable `GROQ_API_KEY` (and `FRONTEND_ORIGIN` once you
   know your Vercel URL).
4. Deploy. Note the resulting URL, e.g. `https://your-app.onrender.com`.

### Backend on Railway (alternative)

1. New Project → Deploy from GitHub repo.
2. Set root directory to `backend`.
3. Railway auto-detects Python; set the start command to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add `GROQ_API_KEY` as an environment variable.

### Frontend on Vercel

1. Push to GitHub.
2. In Vercel: New Project → import repo → set **Root Directory** to `frontend`.
3. Add environment variable `NEXT_PUBLIC_API_URL` = your Render/Railway backend URL.
4. Deploy.
5. Go back to your backend's env vars and set `FRONTEND_ORIGIN` to your Vercel
   URL (e.g. `https://your-app.vercel.app`), then redeploy the backend so CORS
   allows requests from production frontend.

## Pushing to GitHub

```bash
cd D:\Projects\arxiv-research-agent
git init
git add .
git commit -m "Initial commit: arxiv research agent"
git branch -M main
git remote add origin https://github.com/<your-username>/arxiv-research-agent.git
git push -u origin main
```

## Roadmap / possible improvements

- Full-text extraction using ar5iv HTML instead of abstract-only (better
  fidelity, more engineering — `ar5iv_url` is already included per paper).
- Cache cross-encoder scores and LLM extractions per `(topic, arxiv_id)` /
  `arxiv_id` to cut latency and cost on repeated topics.
- Persist past research runs (e.g. SQLite/Postgres) so users can revisit a
  topic's map without re-running the pipeline.
- Edge-type filtering/legend in the graph UI (toggle "shares_dataset" edges
  on/off, etc).
