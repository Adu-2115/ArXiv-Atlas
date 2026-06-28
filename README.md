# ArXiv Atlas

An AI research agent that turns a topic into a visual map of its research
landscape — it searches arXiv, ranks papers by relevance (textual +
citation-based + recency), extracts structured insights from full paper
text, and synthesizes everything into an interactive graph of clusters,
relationships, open problems, and research gaps.

![Topic input](docs/screenshot-input.png)

![Research landscape graph](docs/screenshot-graph.png)

![Ranked papers and extracted insights](docs/screenshot-papers.png)

## Why this exists

Most "AI research assistant" demos are a thin wrapper: one prompt, one
summary. That's fast to build and not very useful — it gives you a
paragraph, not an understanding of a field. ArXiv Atlas is an attempt at
something closer to how an actual literature review works: find a wide net
of candidates, narrow them down with several different relevance signals,
pull out comparable structured facts per paper from the actual paper text,
then look across all of them to find the actual shape of the field — what
approaches exist, how they relate, what's contested, and what's still
unsolved.

## How it works

```
topic
  │
  ▼
1. Find papers      LLM expands the topic into several arXiv search queries
                     (arXiv's search is keyword-based, so a single query
                     misses a lot), results deduplicated into a candidate pool.
  │
  ▼
2. Rank papers       Local cross-encoder scores topic-vs-abstract relevance for
                     every candidate → shortlist. LLM scores relevance (0-100)
                     on that shortlist. Citation counts (Semantic Scholar) and
                     recency are blended in. MMR diversity reranking then
                     reorders the list so the final set spans different
                     sub-approaches instead of one phrasing of the topic.
                     Papers below a relevance floor are dropped entirely.
  │
  ▼
3. Extract insights   Each paper is sent to the LLM with full-text excerpts
                     pulled from ar5iv (method/results/limitations sections),
                     falling back to the abstract if that fails. Papers that
                     fail extraction are dropped and backfilled from further
                     down the ranked list — never retried.
  │
  ▼
4. Map research      Structured extractions are sent to the LLM, which clusters
                     papers thematically and outputs a graph: nodes, typed
                     edges (builds_on / contradicts / shares_method /
                     shares_dataset / related) with specific technical
                     justifications, clusters, and open problems.
  │
  ▼
5. Find gaps          One more LLM call over the same extractions surfaces
                     underexplored directions, conflicting findings, missing
                     benchmarks, and concrete future-work ideas — grounded
                     only in the papers actually retrieved.
  │
  ▼
interactive D3 graph + ranked list + insight cards + gap analysis
```

All five stages stream to the frontend via Server-Sent Events, so the UI
shows live per-stage progress. Every completed run is saved to SQLite, so
past searches can be reloaded instantly without re-running the pipeline.

## Design decisions worth noting

- **Two-pass ranking, not one.** A cross-encoder alone is fast but shallow;
  an LLM alone over dozens of candidates is slow and expensive. Running the
  cheap model first to cut the pool, then the LLM only on the shortlist,
  gets most of the quality at a fraction of the cost.
- **Citation + recency blending, not pure relevance.** Textual relevance
  alone can rank an obscure-but-similarly-worded paper above a well-cited
  foundational one. The final score blends LLM relevance, normalized
  citation count (Semantic Scholar), and recency — configurable weights.
- **MMR diversity reranking.** Both the cross-encoder and LLM reward
  similarity to the topic, which can produce a final set that's all
  near-duplicates of one angle. MMR balances relevance against diversity
  from already-selected papers.
- **A relevance floor, not just a target count.** Backfill exists to keep
  the result set at full size when a paper fails extraction — but it never
  pads the list with papers the LLM itself scored as irrelevant. A niche
  topic returning fewer than the target count is more honest than padding
  with noise.
- **Skip-and-backfill instead of retry.** If extraction fails on a paper
  (rate limit, transient error), retrying the same call rarely helps.
  Pulling the next-ranked paper instead keeps the set at full size without
  hammering a call likely to fail again.
- **Full-text extraction with a graceful fallback.** ar5iv's HTML rendering
  is far easier to parse reliably than raw PDF. When it's unavailable or
  fails to parse, extraction silently falls back to the abstract rather
  than failing the paper outright.
- **Caching at every LLM call site.** Query expansion, relevance scoring,
  extraction, synthesis, and gap detection are all cached — extraction
  permanently per `arxiv_id` (an abstract/paper text doesn't change), the
  rest per exact input set with a TTL. Re-running the same topic costs
  close to zero extra API calls.
- **Retry where it helps, fail fast where it doesn't.** Semantic Scholar's
  rate limit clears in seconds, so citation lookups retry with backoff on
  `429`. Groq's daily token quota takes an hour to reset, so the LLM client
  doesn't retry blindly — it fails gracefully instead, returning whatever
  already succeeded rather than crashing the whole run.
- **Structured JSON logging with per-stage timing**, not print statements —
  every pipeline stage logs its start, duration, and outcome, which is what
  actually made several of the bugs above debuggable in the first place.

## Tech stack

**Backend:** FastAPI (fully async), Groq API (`llama-3.3-70b-versatile` for
ranking/synthesis/gap-detection, `llama-3.1-8b-instant` for the
high-volume query-expansion/extraction calls), `sentence-transformers`
(cross-encoder for reranking, embedding model for MMR), BeautifulSoup
(ar5iv parsing), Semantic Scholar API (citations), SQLite (search history),
`arxiv` (search), pytest.

**Frontend:** Next.js, Tailwind CSS, D3.js (force-directed graph with
relation-type filters, edge tooltips, click-to-highlight), `lucide-react`.

**Infra:** Docker + docker-compose (CPU-only torch to keep the image size
sane), structured JSON logging.

## Project structure

```
arxiv-research-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint + logging setup
│   │   ├── config.py                # env-based settings (models, weights, thresholds)
│   │   ├── logging_config.py        # structured JSON logging
│   │   ├── pipeline.py              # standalone async orchestrator (non-streaming)
│   │   ├── models/schemas.py        # Pydantic models shared across stages
│   │   ├── routers/
│   │   │   ├── research.py          # /api/research and /api/research/stream (SSE)
│   │   │   └── history.py           # /api/history — past run persistence
│   │   └── services/
│   │       ├── groq_client.py       # sync + async Groq wrappers
│   │       ├── cache.py             # disk-based cache for LLM/API calls
│   │       ├── arxiv_search.py      # stage 1
│   │       ├── reranker.py          # stage 2: cross-encoder + LLM + citations + MMR
│   │       ├── citations.py         # Semantic Scholar lookup, retry-on-429
│   │       ├── diversity.py         # MMR diversity reranking
│   │       ├── fulltext.py          # ar5iv HTML parsing for full-text extraction
│   │       ├── extraction.py        # stage 3: async extraction + skip-and-backfill
│   │       ├── synthesis.py         # stage 4: graph synthesis
│   │       ├── gap_detector.py      # stage 5: research gap detection
│   │       └── history.py           # SQLite search history
│   ├── tests/                       # pytest — cache, extraction, reranker, citations, history
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    └── src/
        ├── app/page.tsx              # main page, wires all stages + UI
        ├── components/
        │   ├── ResearchGraph.tsx     # D3 graph: relation filters, tooltips, highlight-on-click
        │   ├── ResearchGaps.tsx      # gap detection display
        │   ├── HistoryPanel.tsx      # past-search dropdown
        │   ├── StageProgress.tsx, Skeletons.tsx, JumpNav.tsx, CollapsibleCard.tsx
        │   └── PaperList.tsx / InsightsList.tsx
        ├── lib/api.ts                # SSE client + history fetch
        └── types/research.ts        # TS types mirroring backend schemas
```

## Running locally

**Backend:**
```bash
cd backend
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env   # then set GROQ_API_KEY (free at console.groq.com)
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`. First backend request is slower than usual —
the cross-encoder and embedding models download on first use (~150-200MB
combined, cached after).

**Tests:**
```bash
cd backend
pytest tests/ -v
```

## Running with Docker

```bash
cp .env.example .env   # set GROQ_API_KEY at the project root
docker compose up --build
```

Open `http://localhost:3000`. The backend image installs CPU-only torch
explicitly (sentence-transformers otherwise pulls the full CUDA build,
which is both unnecessary in a container with no GPU and much larger) and
pre-downloads the cross-encoder/embedding models at build time.

## Known limitations

- Ranking and extraction quality both depend on Groq's free-tier daily
  token quota, which a handful of test runs can exhaust (resets after ~1
  hour).
- Semantic Scholar's unauthenticated tier has a tight, globally-shared rate
  limit; citation lookups retry with backoff but can still occasionally
  return 0 for papers that are recent enough not to be indexed yet.
- ar5iv full-text parsing depends on the paper having a working ar5iv
  rendering and a fairly standard section-heading structure; some papers
  fall back to abstract-only extraction.
- Single-user/local-first: search history is a local SQLite file, not
  designed for multi-user or hosted deployment as-is.

## Roadmap

- Deploy to a real host (Render/Railway + Vercel) — currently local +
  Docker only by design.
- "Chat with the graph" — answer questions like "why are these papers
  connected?" using the structured extractions already on hand, no RAG
  needed.
- Compare two topics side-by-side (shared papers, divergent clusters,
  common datasets).
- GitHub Actions CI running the test suite on push.
