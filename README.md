# ARA - Agentic Research Assistant

**Tool-Calling Research Assistant for Financial Research Analysis**

A financial research assistant purpose-built for investment analysts. Powered by a single tool-calling orchestrator, document structure preservation, and first-class citation tracking with PDF deep links.

---

## Local Development Quick Start

This Compose setup is for local development and demos. It bind-mounts the
backend and frontend source trees into the containers, so the running app
follows your working tree rather than an immutable production image. Treat it
as a local development setup, not a reproducible production deployment profile.

```bash
cp .env.template .env
# Add MISTRAL_API_KEY (required) and TAVILY_API_KEY (optional)

docker compose build --no-cache
docker compose up -d
```

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### Optional API-Key Gate

Local demos run with `REQUIRE_API_KEY=false` by default. If you enable
`REQUIRE_API_KEY=true`, set the same key for the backend and frontend:

```bash
API_KEY=...
VITE_API_KEY=...
```

The frontend sends `X-API-Key` on API calls and fetches protected PDF source
links before opening them. This is a coarse local/demo gate, not production
identity or RBAC.

---

## Architecture

<img alt="System Architecture" src="https://github.com/user-attachments/assets/89e86ddc-1d71-4712-9623-c5d231098440" />

### Core Capabilities

| Capability | What You Get | Business Impact |
|------------|--------------|-----------------|
| **Inline Citations with PDF Deep Links** | Every claim traced to source: `[1]` opens `/documents/{doc_id}/file#page=7` | Designed for traceable answers in a local reference implementation. Analysts verify AI responses against original documents in one click. |
| **Document Structure Preservation** | Tables, figures, and headings preserved with page and section metadata | Financial tables remain traceable, with oversized tables split into row-bounded chunks that reference the full table artifact. |
| **Structured Recommendation Extraction** | Raw reports parsed into queryable `{asset, stance, confidence, bank, date}` | Enables "Show all Overweight calls on Tech" - queries impossible with standard RAG. |
| **Tool-Calling Orchestration** | One LangChain orchestrator selects specialist tools based on query context | Flexible answers across PDFs, structured recommendations, analyst profiles, and web search. |
| **Real-Time Execution Transparency** | Tool-selection and response-generation traces streamed live via SSE | Designed for traceable answers in a local reference implementation. See which tools were used and why. |

---

This is not an enterprise audit system. A production enterprise deployment would need authentication and RBAC, durable audit logs, stable citation/trace IDs, eval gates in CI, monitoring, rate limiting, and a security review.

---

## Specialist Tools

One tool-calling orchestrator can invoke these domain-focused tools:

| Tool | Domain Expertise | Execution |
|-------|------------------|-----------|
| **Knowledge Base Tool** | Semantic search over research PDFs with page-level citation tracking | Vector similarity with metadata filtering |
| **Internal Views Tool** | House investment stances and recommendations | Structured SQL queries |
| **Analyst Intelligence Tool** | Analyst profiles, coverage areas, track records | Profile lookup with accuracy metrics |
| **Web Research Tool** | Live market data, news, external research | Real-time API integration |

**Execution Patterns:**

```
Compare:    "Compare Goldman's view with ours"
            → Knowledge Base Tool + Internal Views Tool

Sequential: "Who covers companies in this report?"
            → Knowledge Base Tool → entity extraction → Analyst Intelligence Tool

Iterative:  "Latest on German tech"
            → Knowledge Base Tool → insufficient → Web Research Tool → aggregate
```

---

## Document Intelligence

### Structure Preservation

The ingestion pipeline preserves document semantics:

| Segment Type | Processing | Result |
|--------------|------------|--------|
| **Tables** | Small tables stay together; oversized tables are split into row-bounded excerpts with a full table artifact | Financial data remains traceable without oversized vector chunks |
| **Figures** | Extracted with captions | Charts preserved with context |
| **Headings** | Maintained as context anchors | Section hierarchy retained |
| **Body Text** | Chunked with heading context | Semantic coherence preserved |

**Chunking Strategy:**
- Groups sequential non-table segments up to 800 tokens
- Tracks page ranges per chunk for citation accuracy
- Preserves table provenance with row ranges and full table artifact links

### Recommendation Extraction

Raw text automatically parsed into structured investment stances:

```json
{
  "asset_class": "Equities",
  "asset": "US Technology",
  "stance": "Overweight",
  "confidence": "High",
  "rationale": "AI infrastructure demand driving earnings growth",
  "source_bank": "Goldman Sachs",
  "report_date": "2024-08-15",
  "page": 7
}
```

Enables structured queries:
- "Show all Overweight calls on Tech from Q3"
- "Which banks disagree on European equities?"
- "Compare Goldman vs JPMorgan on fixed income"

---

## Citation System

Every specialist tool returns citations with full provenance:

```json
{
  "citation_id": 1,
  "text": "We maintain our Overweight stance on US Technology...",
  "metadata": {
    "bank": "Goldman Sachs",
    "title": "Global Strategy Weekly",
    "report_date": "2024-08-15",
    "url": "http://localhost:8000/documents/abc123/file#page=7"
  }
}
```

**PDF Deep Links:** Click any `[1]` reference to open the source page directly.

**Hover Preview:** See source metadata (bank, title, date) before clicking through.

**Cross-Tool Aggregation:** Citations from multiple tools merged with unique IDs.

---

## Real-Time Streaming

Agent reasoning streamed via Server-Sent Events:

| Event | Content | Display |
|-------|---------|---------|
| `thought` | Code-owned execution trace | Trace panel (collapsible) |
| `token` | Response tokens | Main chat area |
| `complete` | Final answer + citations | Message with source links |

The trace panel shows tool execution and synthesis progress for local traceability during development and demos.

---

## Data Storage

```
./data/
├── documents.db                    # Document metadata & deduplication
├── recommendations.db              # Recommendations & Analysts
├── reports/
│   └── {doc_id}.pdf                # Original PDF files
├── images/{doc_id}/                # Extracted figures
├── tables/{doc_id}/                # Full markdown table artifacts
└── vector_store/                   # ChromaDB persistence
```

### Schema

**Documents:** PDF metadata with SHA256 deduplication

| Column | Type | Description |
|--------|------|-------------|
| `doc_id` | TEXT | UUID identifier |
| `file_hash` | TEXT | SHA256 for deduplication |
| `bank` | TEXT | Source institution |
| `asset_class` | TEXT | equity, fixed_income, multi_asset |
| `report_date` | TEXT | ISO date |
| `chunk_count` | INT | Indexed chunks |

**Recommendations:** Structured investment stances

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | UUID identifier |
| `doc_id` | TEXT | Source document link |
| `stance` | TEXT | OW, UW, Neutral, Long, Short |
| `confidence` | TEXT | High, Medium, Low |
| `rationale` | TEXT | Investment thesis |

**Analysts:** Internal analyst profiles with accuracy tracking

**Vector Store:** ChromaDB collection with metadata: `doc_id`, `bank`, `asset_class`, `page_start`, `page_end`, `segment_types`

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Agent Framework | LangChain 0.3.x | Tool-calling orchestration with specialist tools |
| LLM | Mistral Large | Query analysis, planning, synthesis |
| Vector Store | ChromaDB | Semantic search with metadata filtering |
| Structured Store | SQLite | Recommendations, analysts, documents |
| OCR | Mistral OCR API | Structure-preserving PDF extraction |
| Frontend | React + Vite + Tailwind + shadcn/ui | Streaming UI with citation hover |
| Local Dev Runtime | Docker Compose | One-command local development setup with source bind mounts |

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Document Structure Preservation** | Figures, headings, and table provenance are preserved. Oversized tables are chunked by row with full artifacts retained. |
| **Verifiable AI Responses** | Page-level citations let analysts verify every claim against source documents. |
| **Hybrid Retrieval** | Vector search for semantics, SQL for structured filters. Both needed for financial queries. |
| **LangChain Tool Calling** | Tool-calling agent with structured specialist tools and inspectable execution traces. |
| **One-Command Local Development** | Docker Compose starts the app with local source bind mounts. Requires configured API keys and is not a production deployment profile. |

---

## Project Structure

```
├── backend/
│   ├── services/
│   │   ├── agent_orchestrator.py  # Tool-calling orchestration
│   │   ├── tools.py               # Specialist tool implementations
│   │   ├── chunker.py             # Structure-preserving chunking
│   │   ├── document_reader.py     # OCR with segment classification
│   │   ├── recommendations.py     # Structured extraction
│   │   └── database.py            # ChromaDB + SQLite
│   └── prompts/                   # Agent system prompts
├── frontend/
│   ├── src/components/
│   │   ├── Message.tsx            # Citation hover previews
│   │   ├── ThoughtsPanel.tsx      # Agent reasoning display
│   │   └── Sidebar.tsx            # Document library
│   ├── src/hooks/useChat.ts       # SSE stream handling
│   ├── Dockerfile                 # Production static build served by Nginx
│   └── Dockerfile.dev             # Local Vite dev server image
└── docker-compose.yml                  # Local development/demo Compose file
```

---

<details>
<summary><strong>Future Roadmap</strong></summary>

- Hybrid Search + Reranking (BM25 + cross-encoder)
- User Memory Layer (persistent context)
- Recommendation Backtesting (track bank accuracy)
- Multi-Modal Chart Analysis (vision models)
- Knowledge Graph (Neo4j entity relationships)
- Observability (LangSmith tracing)

</details>
