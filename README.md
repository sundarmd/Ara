# ARA - Agentic Research Assistant

**Multi-Agent System for Financial Research Analysis**

A financial research assistant purpose-built for investment analysts. Powered by autonomous agent coordination, document structure preservation, and first-class citation tracking with PDF deep links.

---

## Quick Start

```bash
cp .env.template .env
# Add MISTRAL_API_KEY (required) and TAVILY_API_KEY (optional)

docker compose build --no-cache
docker compose up -d
```

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## Architecture

<img alt="System Architecture" src="https://github.com/user-attachments/assets/89e86ddc-1d71-4712-9623-c5d231098440" />

### Core Capabilities

| Capability | What You Get | Business Impact |
|------------|--------------|-----------------|
| **Inline Citations with PDF Deep Links** | Every claim traced to source: `[1]` opens `report.pdf#page=7` | Full auditability. Analysts verify AI responses against original documents in one click. |
| **Document Structure Preservation** | Tables, figures, and headings kept intact during processing | Zero data loss. Financial tables render correctly. No broken charts or split rows. |
| **Structured Recommendation Extraction** | Raw reports parsed into queryable `{asset, stance, confidence, bank, date}` | Enables "Show all Overweight calls on Tech" - queries impossible with standard RAG. |
| **Autonomous Agent Coordination** | Four specialist agents orchestrated in parallel or sequence based on query complexity | Faster responses. Comparison queries run simultaneously. Dependent queries chain intelligently. |
| **Real-Time Reasoning Transparency** | Agent decision-making streamed live via SSE | Enterprise-grade auditability. See exactly which agents fired and why. |

---

## Specialist Agents

Four domain-expert agents, autonomously coordinated:

| Agent | Domain Expertise | Execution |
|-------|------------------|-----------|
| **Knowledge Base Agent** | Semantic search over research PDFs with page-level citation tracking | Vector similarity with metadata filtering |
| **Internal Views Agent** | House investment stances and recommendations | Structured SQL queries |
| **Analyst Intelligence Agent** | Analyst profiles, coverage areas, track records | Profile lookup with accuracy metrics |
| **Web Research Agent** | Live market data, news, external research | Real-time API integration |

**Execution Patterns:**

```
Parallel:   "Compare Goldman's view with ours"
            → Knowledge Base Agent + Internal Views Agent (simultaneous)

Sequential: "Who covers companies in this report?"
            → Knowledge Base Agent → entity extraction → Analyst Intelligence Agent

Iterative:  "Latest on German tech"
            → Knowledge Base Agent → insufficient → Web Research Agent → aggregate
```

---

## Document Intelligence

### Structure Preservation

The ingestion pipeline preserves document semantics:

| Segment Type | Processing | Result |
|--------------|------------|--------|
| **Tables** | Kept intact, never split | Financial data renders correctly |
| **Figures** | Extracted with captions | Charts preserved with context |
| **Headings** | Maintained as context anchors | Section hierarchy retained |
| **Body Text** | Chunked with heading context | Semantic coherence preserved |

**Chunking Strategy:**
- Groups sequential segments up to 512 tokens
- Tracks page ranges per chunk for citation accuracy
- Preserves table integrity across page breaks

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

Every agent returns citations with full provenance:

```json
{
  "citation_id": 1,
  "text": "We maintain our Overweight stance on US Technology...",
  "metadata": {
    "bank": "Goldman Sachs",
    "title": "Global Strategy Weekly",
    "report_date": "2024-08-15",
    "url": "http://localhost:8000/files/abc123.pdf#page=7"
  }
}
```

**PDF Deep Links:** Click any `[1]` reference to open the source page directly.

**Hover Preview:** See source metadata (bank, title, date) before clicking through.

**Cross-Agent Aggregation:** Citations from multiple agents merged with unique IDs.

---

## Real-Time Streaming

Agent reasoning streamed via Server-Sent Events:

| Event | Content | Display |
|-------|---------|---------|
| `thought` | Agent reasoning process | Thoughts Panel (collapsible) |
| `token` | Response tokens | Main chat area |
| `complete` | Final answer + citations | Message with source links |

The Thoughts Panel provides full visibility into agent decision-making for enterprise auditability requirements.

---

## Data Storage

```
./data/
├── documents.db                    # Document metadata & deduplication
├── recommendations.db              # Recommendations & Analysts
├── reports/
│   └── {doc_id}.pdf                # Original PDF files
├── images/{doc_id}/                # Extracted figures
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
| Agent Framework | LangChain 0.3.x | ReAct pattern with autonomous coordination |
| LLM | Mistral Large | Query analysis, planning, synthesis |
| Vector Store | ChromaDB | Semantic search with metadata filtering |
| Structured Store | SQLite | Recommendations, analysts, documents |
| OCR | Mistral OCR API | Structure-preserving PDF extraction |
| Frontend | React + Vite + Tailwind + shadcn/ui | Streaming UI with citation hover |
| Deployment | Docker Compose | One-command reproducible setup |

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Document Structure Preservation** | Tables and figures kept intact. Financial reports have structure that matters. |
| **Verifiable AI Responses** | Page-level citations let analysts verify every claim against source documents. |
| **Hybrid Retrieval** | Vector search for semantics, SQL for structured filters. Both needed for financial queries. |
| **ReAct Reasoning** | Industry-standard agentic pattern (Yao et al., 2022) with explicit, auditable decision traces. |
| **One-Command Deployment** | Docker Compose packages everything. No manual setup steps. |

---

## Project Structure

```
├── backend/
│   ├── services/
│   │   ├── agent_orchestrator.py  # Autonomous agent coordination
│   │   ├── tools.py               # Specialist agent implementations
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
│   └── src/hooks/useChat.ts       # SSE stream handling
└── docker-compose.yml
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
