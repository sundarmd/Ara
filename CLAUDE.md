# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Challenge Overview

This repository is a solution to the **Agentic AI - Technical Challenge**:

**Objective**: Build a minimal agent-based AI assistant that can summarize and extract key recommendations from sell-side cross-asset research reports (from investment banks like Goldman Sachs, JP Morgan, UBS, etc.). The assistant should use agentic architecture to intelligently extract and compare recommendations across different reports.

**Core Capabilities Required**:
- Upload and index sell-side research reports for semantic search (store in a DB)
- Chat with the assistant to ask questions about cross-asset recommendations (equity, fixed income, multi-asset)
- Search for internal knowledge (historical recommendations, analyst tracking, etc.) using agent-chosen tool-calling (Mock)

**Technical Requirements**:
- Use any open-source agentic framework to orchestrate the agents
- Include a router or planner agent to determine which agent(s) to call based on the user query

**Tech Stack**:
- Backend: Python + FastAPI with agentic pipeline (`/query` or `/chat` endpoint)
- Frontend: React + TypeScript with streaming responses (agent thoughts and final answer)

**Deliverables**:
- GitHub repository with the solution ✅
- 10-minute video demonstration ⏳
- Design concepts & app architecture ✅
- Timebox: 7 days

## Project Overview

This is an **Agentic AI Research Assistant** for sell-side financial research report analysis. It's a multi-agent RAG (Retrieval-Augmented Generation) system built with FastAPI (backend) and React + Vite (frontend) that allows users to upload PDF research reports, extract structured recommendations, and query them using natural language.

## Implementation Status

### ✅ Completed Features

**Core Requirements:**
- ✅ Upload and index PDF research reports with Mistral OCR
- ✅ Semantic search using ChromaDB vector store (persisted)
- ✅ Multi-turn chat interface with streaming responses
- ✅ Agent orchestration using LangChain's AgentExecutor (open-source framework)
- ✅ Tool-calling architecture with 4 agent tools
- ✅ FastAPI backend with `/chat/stream` endpoint (SSE streaming)
- ✅ React + TypeScript frontend with real-time agent thoughts display

**Agent Tools (Router/Planner via LangChain):**
- ✅ `search_knowledge_base`: RAG search over uploaded research reports
- ✅ `query_internal_views`: Mock internal Ara house views (SQLite-backed)
- ✅ `get_analyst_intelligence`: Mock analyst profiles and track records
- ✅ `web_search`: Live web search via Tavily API

**Data Pipeline:**
- ✅ PDF → Mistral OCR → Segments (text/tables/figures)
- ✅ Smart segment-aware chunking with metadata preservation
- ✅ Vector embeddings (Mistral embeddings via LangChain)
- ✅ Structured recommendation extraction with LLM
- ✅ Metadata auto-extraction (bank, asset class, report date)

**UI/UX:**
- ✅ Real-time streaming thoughts panel (agent reasoning transparency)
- ✅ Message history with collapsible thoughts
- ✅ Multi-file upload with progress tracking (SSE)
- ✅ Document library sidebar with filters
- ✅ Source citations with deep links to PDF pages
- ✅ Responsive design with Tailwind CSS

**Architecture:**
- ✅ Service-oriented backend architecture
- ✅ Singleton pattern for stores and clients
- ✅ SQLite for metadata, recommendations, and analysts
- ✅ Docker Compose setup for easy deployment
- ✅ Structured logging (JSON format)

### ⏳ Pending / In Progress

**Deliverables:**
- ⏳ 10-minute video demonstration (required for challenge completion)
- 📝 Consider creating architecture diagrams for video/docs

**Known Gaps / Future Enhancements:**
- 🔧 `backend/services/llm_client.py` is untracked - needs to be committed
- 🔧 No formal test suite (consider adding pytest tests)
- 🔧 PDF serving endpoint (`/files/{doc_id}.pdf#page={page}`) may need implementation
- 🔧 Error handling edge cases (e.g., corrupted PDFs, API timeouts)
- 🔧 Rate limiting / authentication (if deploying publicly)
- 🔧 Recommendation comparison UI (side-by-side bank views)

**Clarification Needed:**
- ❓ Challenge asks for "router or planner agent" - current implementation uses LangChain's AgentExecutor which handles routing implicitly via tool selection. Does this satisfy the requirement, or is an explicit router agent expected?

### 📋 Next Steps

To complete the challenge:
1. **Record 10-minute demo video** showing:
   - Upload of sample research reports (2-3 PDFs from different banks)
   - Chat queries demonstrating cross-asset recommendation extraction
   - Agent tool selection and reasoning (thoughts panel)
   - Comparison of recommendations across reports
   - Internal knowledge search (mock analyst data)

2. **Commit untracked file**: `backend/services/llm_client.py`

3. **Optional polish**:
   - Add README section with video link
   - Create simple architecture diagram
   - Test edge cases (large PDFs, multiple concurrent uploads)

## Development Commands

### Docker (Recommended)
```bash
# Start the full stack (backend + frontend)
docker compose up --build

# Backend will be at http://localhost:8000
# Frontend will be at http://localhost:3000
# API docs at http://localhost:8000/docs
```

### Backend (Manual)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run development server (with auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python main.py
```

### Frontend (Manual)
```bash
cd frontend
npm install

# Development server (with hot reload)
npm run dev

# Production build
npm run build

# Lint TypeScript/TSX files
npm run lint

# Preview production build
npm run preview
```

### Environment Setup
Copy `.env.template` to `.env` and configure:
- `MISTRAL_API_KEY` (required) - For OCR, chat completions, and embeddings
- `TAVILY_API_KEY` (optional) - For web search tool

## Architecture Overview

### Backend Architecture

The backend follows a **service-oriented architecture** with clear separation of concerns:

**Core Pipeline Flow:**
1. **Document Ingestion** (`services/ingestion.py`):
   - PDF → Mistral OCR (`document_reader.py`) → Segments
   - Segments → Smart Chunker (`chunker.py`) → Chunks with metadata
   - Chunks → Vector Store (`database.py` with ChromaDB + LangChain)
   - Parallel: Extract structured recommendations (`metadata_extractor.py`, `recommendations.py`)

2. **Agent Orchestration** (`services/agent_orchestrator.py`):
   - Uses LangChain's `AgentExecutor` with tool-calling
   - Mistral LLM accessed via `langchain-openai` adapter (Mistral API is OpenAI-compatible)
   - Streams Server-Sent Events (SSE) with thought process and tokens
   - Tools defined in `services/tools.py`

3. **Available Agent Tools** (`services/tools.py`):
   - `search_knowledge_base`: RAG semantic search over uploaded PDFs
   - `query_internal_views`: Query Ara house views (SQLite-backed)
   - `get_analyst_intelligence`: Look up analyst profiles and track records
   - `web_search`: Live web search via Tavily API

**Data Stores:**
- **Vector Store**: ChromaDB (persisted to `./data/vector_store`) via LangChain Chroma
- **Document Metadata**: SQLite (`./data/documents.db`) for tracking uploaded files
- **Recommendations**: SQLite (`./data/recommendations.db`) for structured investment stances
- **Analysts**: SQLite tables in `./data/recommendations.db` for internal analyst profiles

**Key Services:**
- `embeddings.py`: Mistral embeddings via LangChain
- `rag.py`: Semantic search wrapper
- `chat.py`: Entry point for streaming chat responses
- `llm_client.py`: Mistral API client wrapper
- `prompt_loader.py`: Loads system prompts from `backend/prompts/*.md`

**Streaming Architecture:**
- FastAPI endpoints return `StreamingResponse` with `media_type="text/event-stream"`
- Agent emits SSE events: `thought`, `token`, `complete`, `error`
- Upload progress also streams via SSE with progress percentages

### Frontend Architecture

React + TypeScript with Vite, using Tailwind CSS v4 beta:

**State Management:**
- `contexts/DocumentsContext.tsx`: Global document list state
- `hooks/useChat.ts`: Chat state and SSE stream handling
- Local component state for UI interactions

**Key Components:**
- `Chat.tsx`: Main chat interface orchestrator
- `MessageList.tsx`: Renders message history with streaming updates
- `ThoughtsPanel.tsx`: Real-time agent reasoning display
- `UploadModal.tsx`: Multi-file upload with progress tracking
- `Sidebar.tsx`: Document library and filters

**SSE Handling:**
- `services/api.ts` provides `parseSSEStream` generator for consuming SSE
- `useChat` hook accumulates thoughts and tokens in real-time
- Thoughts are stored per-message for collapsible history

## Important Implementation Details

### LangChain Integration
- The system uses **LangChain 0.3.x** with pinned versions (see `requirements.txt`)
- Mistral is accessed via `ChatOpenAI` adapter pointing to `https://api.mistral.ai/v1`
- Tools use the `@tool` decorator from `langchain_core.tools`
- Agent uses `create_tool_calling_agent` + `AgentExecutor`

### Chunking Strategy
Smart segment-aware chunking in `services/chunker.py`:
- Groups sequential segments (text, table, figure) up to max tokens
- Preserves context by keeping related segments together
- Adds metadata: page ranges, section headings, segment types
- Uses `tiktoken` for token counting

### Streaming Thought Extraction
In `agent_orchestrator.py`, the agent wraps reasoning in `<thought>` tags:
- Regex-based extraction of content between `<thought>...</thought>`
- Aggressive filtering to prevent thought leakage into visible response
- Emits thought events progressively (on newlines, periods, or buffer length)

### Tool Output Format
All tools return **JSON arrays** of citation objects:
```json
[
  {
    "citation_id": 1,
    "text": "...",
    "metadata": {
      "bank": "...",
      "title": "...",
      "report_date": "...",
      "url": "..."  // Deep link to PDF page or web article
    }
  }
]
```

### PDF Deep Linking
Backend constructs URLs like: `http://localhost:8000/files/{doc_id}.pdf#page={page}`
- Frontend must serve PDFs from `backend/data/reports/` directory
- Deep links allow users to jump to source page in browser

## Common Development Workflows

### Adding a New Agent Tool
1. Define tool function in `services/tools.py` using `@tool` decorator
2. Add to `AVAILABLE_TOOLS` list
3. Update `TOOL_NAMES` mapping in `agent_orchestrator.py` for friendly display
4. Tool should return JSON array format (see above)

### Modifying System Prompts
- Edit markdown files in `backend/prompts/`
- `agent_system.md`: Main agent instructions
- `recommendations_system.md` / `recommendations_user.md`: For structured extraction
- `metadata_extraction.md`: For auto-extracting bank/asset class from PDFs
- Use `{variable}` placeholders, populated via `load_prompt("name", variable="value")`

### Changing Chunking Behavior
- Modify `services/chunker.py`
- Key parameters: `MAX_CHUNK_TOKENS` (currently 512), overlap logic
- Chunks must have: `id, doc_id, text, page_start, page_end, segment_types, metadata`

### Testing RAG Search
Use the debug endpoint:
```bash
curl "http://localhost:8000/debug_search?q=AI+outlook&n_results=3"
```

### Testing Recommendation Extraction
Upload a PDF via UI or use the debug endpoint:
```bash
curl "http://localhost:8000/debug_recommendations?source_type=sell_side"
```

## Data Persistence

All data persists in `./data/` directory:
- `reports/`: Stored PDFs (named as `{doc_id}.pdf`)
- `vector_store/`: ChromaDB embeddings and index
- `documents.db`: SQLite database with the `documents` table for file metadata and upload info
- `recommendations.db`: SQLite database with tables:
  - `recommendations`: Structured investment recommendations
  - `analysts`: Internal analyst profiles

When replacing a document (same filename), the system:
1. Deletes old vector embeddings by `doc_id`
2. Removes old SQLite record
3. Deletes old PDF file
4. Re-ingests new version

## Settings & Configuration

All settings in `backend/config/settings.py` use Pydantic with environment variables:
- Load from `.env` file
- Override with `ENVIRONMENT_VARIABLE` format
- Key settings:
  - `RAG_SEARCH_RESULTS`: Number of chunks to retrieve (default: 8)
  - `RAG_CONTEXT_RECOMMENDATIONS`: Recommendations sent to agent (default: 15)
  - `TIMEOUT_*`: API timeout values
  - `DATA_ROOT`, `REPORTS_DIR`, `VECTOR_DB_DIR`, `DOCUMENTS_DB_PATH`, `RECOMMENDATIONS_DB_PATH`: Storage paths

## Testing & Debugging

No formal test suite exists currently. For debugging:

1. **Check API health**: `curl http://localhost:8000/health`
2. **View API docs**: http://localhost:8000/docs (interactive Swagger UI)
3. **Debug search**: `/debug_search` endpoint
4. **Debug recommendations**: `/debug_recommendations` endpoint
5. **Vector store stats**: `/stats` endpoint
6. **Backend logs**: JSON-formatted structured logging to stdout
7. **LangChain verbose mode**: `AgentExecutor(verbose=True)` in `agent_orchestrator.py`

## Progress Tracking

For detailed task tracking and to-do lists, see **TODO.md** in the repository root.

**CLAUDE.md** (this file) tracks:
- High-level implementation status (what's completed vs pending)
- Architecture and design decisions
- Development workflows

**TODO.md** tracks:
- Granular tasks and checklists
- Open questions and decisions needed
- Known issues and bugs
- Future enhancement ideas

## Git Workflow Notes

Current branch: `knowledge`
Main branch: `main`

Recent work focuses on:
- Knowledge base integration
- Metadata extraction improvements
- Frontend document management
- Streaming chat UX refinements
- Challenge completion preparation

**Action needed**: Commit untracked file `backend/services/llm_client.py` before finalizing the challenge submission.
