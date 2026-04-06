# Chapter 2: AI Engineering with Library Management Data

This chapter demonstrates modern AI engineering patterns using a Library Management dataset. The content follows the book structure: **RAG** → **MCP** → **Agentic AI**.

---

## Architecture Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4A90D9', 'primaryTextColor': '#fff', 'lineColor': '#5C6BC0', 'secondaryColor': '#E8EAF6', 'tertiaryColor': '#F5F5F5'}}}%%

flowchart TB
    subgraph DATA["<b>Data Layer</b>"]
        direction LR
        CSV_B["library_dataset_random.csv<br/><i>200 books</i>"]
        CSV_L["lending_data.csv<br/><i>750 loans</i>"]
        CSV_R["replenish_data.csv<br/><i>500 replenishments</i>"]
    end

    subgraph SCRIPTS["<b>Scripts</b>"]
        GEN_L["generate_lending_data.py"]
        GEN_R["generate_replenish_data.py"]
        LOADER["load_library_csv_to_duckdb.py"]
    end

    subgraph DB["<b>DuckDB — chapter2.db</b>"]
        direction LR
        T_BOOKS["library.books"]
        T_LENDING["library.lending"]
        T_REPLENISH["library.replenish"]
        T_EMB_B["library.book_embeddings"]
        T_EMB_L["library.lending_embeddings"]
        T_EMB_R["library.replenish_embeddings"]
    end

    subgraph DOMAIN["<b>Domain &amp; Repository Layer</b>"]
        direction LR
        D_BOOK["Book<br/>BookStatus, Category, Location"]
        D_LOAN["Loan<br/>PatronSegment, Region, Channel"]
        D_REPL["Replenishment<br/>Supplier, ReplenishType, Priority"]
        R_BOOK["BookRepository"]
        R_LEND["LendingRepository"]
        R_REPL["ReplenishRepository"]
    end

    subgraph TOOLS["<b>Tool Layer — src/agentic/library/tools.py</b>"]
        direction LR
        T1["search_books<br/>get_book_details<br/>check_availability<br/>locate_book"]
        T2["search_lending<br/>get_most_lent_books<br/>get_lending_stats"]
        T3["search_replenish<br/>get_most_replenished_books<br/>get_replenish_stats"]
    end

    subgraph RAG["<b>Section 1 — RAG</b>"]
        direction TB
        EMB["EmbeddingGenerator<br/><i>all-MiniLM-L6-v2 (384-dim)</i>"]
        VS["Vector Store<br/><i>BookVectorStore</i><br/><i>LendingVectorStore</i><br/><i>ReplenishVectorStore</i>"]
        SEM["Semantic Search<br/><i>Cosine Similarity</i>"]
        EMB --> VS --> SEM
    end

    subgraph MCP["<b>Section 2 — MCP</b>"]
        direction TB
        SRV["FastMCP Server<br/><i>18 tools, 5 resources</i><br/><i>2 prompt templates</i>"]
        CLI["MCP Client<br/><i>Settings Menu</i><br/><i>Code Execution toggle</i>"]
        CE["Code Execution Mode<br/><i>~48% token reduction (8 tools)</i><br/><i>~80% token reduction (100 tools)</i>"]
        SRV --- CLI
        CLI --- CE
    end

    subgraph AGENTS["<b>Section 3 — Agentic AI</b>"]
        direction TB
        subgraph SINGLE["Single Agents"]
            direction LR
            PA["PatronAgent<br/><i>8 tools — inventory &amp; shelf</i>"]
            CA["CoordinationAgent<br/><i>14 tools — revenue &amp; replenishment</i>"]
        end
        ORCH["Orchestrator Agent<br/><i>LLM-based planning</i>"]
        subgraph WORKERS["Multi-Agent Workers"]
            direction LR
            SA["SearchAgent<br/><i>6 tools</i>"]
            AA["AnalyticsAgent<br/><i>catalog + lending + replenish</i>"]
            RA["RecommendationAgent<br/><i>5 tools</i>"]
        end
        ORCH --> WORKERS
    end

    subgraph PLUGIN["<b>Section 4 — Two Claude Code Plugins</b>"]
        direction LR
        subgraph PP["patron-plugin"]
            direction TB
            SK1["patron-agent<br/><i>library.books only</i>"]
            SK3["query-library<br/><i>library.books only</i>"]
            HOOK1["enforce-patron-readonly.py<br/><i>blocks lending/replenish access</i>"]
            SK1 --- HOOK1
            SK3 --- HOOK1
        end
        subgraph CP["coordinator-plugin"]
            direction TB
            SK2["coordination-agent<br/><i>all 3 tables</i>"]
            SK4["analyze-library<br/><i>all 3 tables</i>"]
            HOOK2["enforce-readonly-queries.py<br/><i>write-only block</i>"]
            SK2 --- HOOK2
            SK4 --- HOOK2
        end
    end

    subgraph USER["<b>User Entry Points</b>"]
        direction LR
        M1["make llm / make llm-rag"]
        M2["make mcp-assistant"]
        M3["make patron-agent / make coordination-agent<br/>make multi-agent"]
        M4["/patron-agent /query-library<br/>/coordination-agent /analyze-library"]
    end

    %% Data flow
    GEN_L --> CSV_L
    GEN_R --> CSV_R
    CSV_B & CSV_L & CSV_R --> LOADER
    LOADER --> T_BOOKS & T_LENDING & T_REPLENISH

    T_BOOKS --> R_BOOK
    T_LENDING --> R_LEND
    T_REPLENISH --> R_REPL
    R_BOOK -.- D_BOOK
    R_LEND -.- D_LOAN
    R_REPL -.- D_REPL

    R_BOOK & R_LEND & R_REPL --> TOOLS

    %% Tools fan out to consumers
    TOOLS --> RAG
    TOOLS --> MCP
    TOOLS --> AGENTS
    TOOLS --> PLUGIN

    %% Embeddings flow
    T_BOOKS & T_LENDING & T_REPLENISH --> EMB
    EMB --> T_EMB_B & T_EMB_L & T_EMB_R

    %% RAG feeds into agents and MCP
    SEM -.->|"enable_rag=True"| CLI
    SEM -.->|"semantic search"| SA

    %% User entry points
    M1 --> RAG
    M2 --> MCP
    M3 --> AGENTS
    M4 --> PLUGIN

    %% Styling
    style DATA fill:#E3F2FD,stroke:#1565C0,color:#000
    style DB fill:#E8F5E9,stroke:#2E7D32,color:#000
    style DOMAIN fill:#FFF3E0,stroke:#E65100,color:#000
    style TOOLS fill:#F3E5F5,stroke:#6A1B9A,color:#000
    style RAG fill:#E0F7FA,stroke:#00695C,color:#000
    style MCP fill:#FCE4EC,stroke:#AD1457,color:#000
    style AGENTS fill:#FFF8E1,stroke:#F57F17,color:#000
    style PLUGIN fill:#F1F8E9,stroke:#558B2F,color:#000
    style USER fill:#ECEFF1,stroke:#37474F,color:#000
    style SCRIPTS fill:#E8EAF6,stroke:#283593,color:#000
    style WORKERS fill:#FFF8E1,stroke:#F57F17,color:#000
```

**Data Lifecycle:** Replenish (books IN) → Books (inventory) → Lending (books OUT)

---

## Section 1: RAG (Retrieval-Augmented Generation)

RAG enables LLMs to answer questions about private data they've never seen during training. This section demonstrates the core RAG pattern: **Retrieve** → **Augment** → **Generate**.

### Quick Start

```bash
# 1. Setup environment
make dev-setup

# 2. Configure LLM API
cp .env.example .env
# Edit .env and set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL
```

### Step 1: Try the LLM Without RAG

```bash
make llm
```

Ask: **"Who wrote 'The Quantum Garden'?"**

The LLM will likely hallucinate an answer or say it doesn't know - because this is a fictional book that doesn't exist in its training data.

### Step 2: Try the LLM With RAG

```bash
make llm-rag
```

Ask the same question: **"Who wrote 'The Quantum Garden'?"**

Now the LLM correctly answers: **"Dr. Elena Voss"** - because RAG retrieved the book data and added it to the prompt.

### What's Happening?

| Mode | What the LLM Sees | Result |
|------|-------------------|--------|
| `make llm` | Just your question | Hallucination or "I don't know" |
| `make llm-rag` | Your question + retrieved book data | Accurate answer |

This is the core RAG pattern:
1. **Retrieve**: Find relevant documents (our 5 fictional books)
2. **Augment**: Add retrieved data to the LLM prompt
3. **Generate**: LLM answers using the provided context

### Production RAG with DuckDB VSS

For the full library dataset (200 books), we use vector embeddings and semantic search.
This requires database setup:

### Prerequisites (Database Setup)

RAG LLM, MCP and Agentic sections require the library database so if you set this now you don't need to repeat again:

```bash
# Load 200 books + 750 loans + 500 replenishments into DuckDB
make load-data
make verify-data    # Expected: ✓ Found 200 books
```

```bash
# Generate embeddings (after load-data)
make generate-embeddings

# Interactive semantic search
make semantic-search

# Assistant with RAG enabled
make assistant-rag
```

**Example Semantic Queries:**
- "books about time travel adventures"
- "something about Python programming"
- "mystery novels with detective stories"

### RAG Make Commands

| Command | Description |
|---------|-------------|
| `make llm` | Chat with plain LLM (no RAG) - see hallucinations |
| `make llm-rag` | Chat with LLM + RAG - see accurate answers |
| `make generate-embeddings` | Generate book embeddings (requires DB) |
| `make semantic-search` | Interactive semantic search (requires DB) |
| `make assistant-rag` | Library Assistant with RAG (requires DB) |

---

## Section 2: MCP (Model Context Protocol)

MCP exposes your tools to AI applications like MCP Client and MCP host. This section shows how MCP tools work and how to deploy an MCP server.

* Make sure to finish [prerequisites](#prerequisites-database-setup) if not already done, while executing RAG section

### Configure MCP Settings

```bash
make mcp-client
```

This opens an interactive settings menu where you can toggle:
- **Code Execution** - ON by default (token efficient mode)
- **RAG** - Semantic search functionality
- **Dummy Tools** - 100 enterprise tools for scale testing
- **Show Tool Calls** - Display generated code during execution

Settings are persisted to `.mcp_config.json` and shared with `mcp-assistant`.

### MCP Assistant (Interactive Chat)

```bash
make mcp-assistant
```

Chat with an AI assistant that uses MCP tools to answer library questions. Code execution mode is enabled by default for token efficiency.

```bash
# With RAG enabled
make mcp-assistant ARGS="--rag"

# Traditional JSON tools (disable code execution)
make mcp-assistant ARGS="--no-code-execution"
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_books` | Search by title, author, or keyword |
| `get_book_details` | Get complete book information |
| `check_availability` | Check if a book is available |
| `list_by_category` | List books in a category |
| `list_by_status` | List books by status (Present/Missing/Checked Out) |
| `locate_book` | Get physical location (Cabinet/Rack/Row) |
| `find_books_in_cabinet` | List books in a cabinet location |
| `get_weak_signal_books` | Find books needing RFID maintenance |

### 2.1 Code Execution Pattern

The MCP assistant uses sandboxed Python execution by default for token efficiency:

```bash
# Compare Traditional vs Code Execution modes
make mcp-compare-modes

# Run MCP token benchmark
make mcp-benchmark
```

**Why Code Execution?**

Traditional tool calling sends full JSON schemas for every tool in every request. Code execution sends tools once, then executes Python code—dramatically reducing tokens.

**Expected Results:**
- Traditional: ~4,000 tokens
- Code Execution: ~2,100 tokens
- **Reduction: ~48%**

### 2.2 Enterprise Scale (100+ Tools)

At enterprise scale with many tools, the difference is dramatic:

```bash
# Interactive demo with 100 tools
make mcp-compare-modes-enterprise

# Automated full benchmark with 100 tools
make mcp-compare-modes-enterprise-all
```

When you run `make mcp-compare-modes-enterprise`, the LLM first discovers all available tools across connected MCP servers and renders a file tree before running any query:

```
MCP TOOL DISCOVERY
==================
Connecting to MCP servers and discovering available tools...
Connected servers: 12   Total tools: 122

├── library-catalog-server   [10 tools]
│    ├── search_books
│    └── ...
├── library-rag-server       [12 tools]
│    ├── semantic_search
│    └── ...
├── engineering-server       [10 tools]
│    └── engineering_run_build, ...
...
└── ml_platform-server       [10 tools]
     └── ml_train_model, ...
```

This makes the token overhead visible: the traditional mode must serialize all 122 tool schemas as JSON on every request, while code execution only injects compact Python stubs.

**Enterprise Results (100 dummy tools):**
- Traditional: ~131,000 tokens
- Code Execution: ~25,000 tokens
- **Reduction: 80%+**

This demonstrates insights from Anthropic's "Advanced Tool Use" paper.

### MCP Make Commands

| Command | Description |
|---------|-------------|
| `make mcp-client` | Settings menu to configure MCP options |
| `make mcp-assistant` | AI Chat (code execution ON by default) |
| `make mcp-assistant ARGS="--rag"` | Chat with RAG enabled |
| `make mcp-assistant ARGS="--no-code-execution"` | Traditional JSON tools mode |
| `make mcp-compare-modes` | Compare Traditional vs Code Execution |
| `make mcp-benchmark` | Run MCP token comparison benchmark |
| `make mcp-compare-modes-enterprise` | Enterprise scale (100 tools, interactive) |
| `make mcp-compare-modes-enterprise-all` | Enterprise scale (100 tools, automated) |
| `make mcp-server` | Start MCP server (for Claude Desktop) |
| `make mcp-dev` | Start MCP Inspector for debugging |

---

## Section 3: Agentic AI

This section covers multi-agent orchestration and traditional tool-calling patterns.

### 3.1 Role-Separated Single Agents

Two specialized agents with strictly separated tool access — mimicking real-world access control:

```bash
make patron-agent       # Library patron: inventory & shelf location only
make coordination-agent # Operations staff: revenue, replenishment & analytics
```

**PatronAgent** (8 tools — `library.books` only):
- Search books by title, author, keyword
- Check availability, locate by cabinet/rack/row
- List by category or status, RFID signal health

**CoordinationAgent** (14 tools — `library.lending` + `library.replenish` + operational stats):
- Lending revenue: fees, units lent, segment/region/channel breakdown
- Most lent books, monthly trends, fee waivers
- Replenishment: supplier, type, priority, funding source
- Supply gap analysis (lending vs replenishment)

**Tool separation enforced at the API injection level** — each agent's code sandbox only receives the function definitions for its allowed tools. Patron agent never sees lending or replenishment data, even if it tries raw SQL.

### 3.2 Traditional Tool Use

The Library Assistant uses JSON schema-based tool calling with all 22 tools:

```bash
make assistant
```

**In-App Commands:**
- `/help` - Show available commands
- `/tools` - Toggle tool call display
- `/stats` - Show token usage statistics
- `/quit` - Exit

**Example Queries:**
- "What programming books are available?"
- "Show me books by John Smith"
- "Which books are missing?"

### 3.3 Multi-Agent System

LLM-planned orchestration across three specialist agents. All 22 tools distributed — each agent gets only what it needs:

```bash
make multi-agent
```

**Specialist Agents and their tool scope:**
- **SearchAgent** (6 tools) — Book discovery, location, availability, semantic search
- **AnalyticsAgent** (16 tools) — Catalog stats + lending revenue + replenishment reporting
- **RecommendationAgent** (5 tools) — Suggestions filtered by availability and signal quality

**Example Multi-Agent Queries:**
- "Find available programming books and recommend one with good signal"
- "How many books are missing? Show breakdown by category"
- "What's the total lending revenue by region?"
- "Which books have the highest replenishment cost vs lending fees?"

### Agentic Make Commands

| Command | Description |
|---------|-------------|
| `make patron-agent` | Patron-facing agent — inventory & shelf (8 tools, RAG on) |
| `make coordination-agent` | Operations agent — revenue & replenishment (14 tools, RAG on) |
| `make assistant` | Traditional tool-calling assistant (all 22 tools) |
| `make data-analysis` | Start data analysis agent |
| `make multi-agent` | Multi-agent orchestrator (LLM-planned, 3 specialist agents) |

### 3.4 IDE Integrations

**Claude Desktop Configuration:**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/mcp/library_server.py"],
      "cwd": "/path/to/chapter-2"
    }
  }
}
```

---

## Section 4: Plugins

Two separate Claude Code plugins mirror the agent role separation from Section 3.
Each plugin has its own skills, hooks, and hook scripts scoped to its access level.

### How to Use the Plugins

#### Option A — Local development (no marketplace needed)

Pass `--plugin-dir` when launching Claude Code. Each plugin must be launched separately:

```bash
# Patron plugin
claude --plugin-dir ./chapter-2/patron-plugin

# Coordinator plugin
claude --plugin-dir ./chapter-2/coordinator-plugin
```

Skills are namespaced by plugin name:

```
/patron-plugin:patron-agent find me available Python books
/patron-plugin:patron-agent where is book B042?
/patron-plugin:query-library list all missing fiction books

/coordinator-plugin:coordination-agent show total lending revenue by region
/coordinator-plugin:coordination-agent supply gap analysis by category
/coordinator-plugin:analyze-library which books are most replenished?
```

#### Option B — Marketplace install (persistent)

1. Register a marketplace (one-time setup):
   ```
   /plugin marketplace add ./chapter-2
   ```

2. Install the plugins:
   ```
   /plugin install patron-plugin@rdewai-plugins
   /plugin install coordinator-plugin@rdewai-plugins
   ```

3. Invoke skills using the namespaced format:
   ```
   /patron-plugin:patron-agent find Python books
   /coordinator-plugin:coordination-agent show lending revenue
   ```

**What happens when you invoke a skill:**
1. Claude Code loads the skill's `SKILL.md` as the system prompt
2. The plugin's `.mcp.json` starts the `library` MCP server automatically
3. The skill calls `mcp__library__*` tools to answer your question
4. The `PreToolUse` hook intercepts any raw Bash commands and blocks writes (the patron hook also blocks access to lending/replenishment tables)

**Scope enforcement — what each plugin can and cannot answer:**

| Question | Use | Plugin |
|----------|-----|--------|
| "Where is book B001?" | `:patron-agent` | patron-plugin |
| "Is 'Clean Code' available?" | `:patron-agent` | patron-plugin |
| "List all Programming books present" | `:patron-agent` | patron-plugin |
| "Which books have weak RFID signal?" | `:patron-agent` | patron-plugin |
| "What's our total lending revenue?" | `:coordination-agent` | coordinator-plugin |
| "Which books are most borrowed?" | `:coordination-agent` | coordinator-plugin |
| "Show replenishment by supplier" | `:coordination-agent` | coordinator-plugin |
| "Supply gap analysis by category" | `:coordination-agent` | coordinator-plugin |

If you ask the patron plugin about revenue or replenishment, it will redirect you:
> *"That's handled by the Coordinator Plugin (`:coordination-agent`). I only have access to book inventory and shelf locations."*

---

### Plugin Structure

Both plugins connect to the same **library MCP server** (`src/mcp/library_server.py`) which exposes 18 tools, 5 resources, and 2 prompts. The MCP server is declared in each plugin's `.mcp.json` (auto-discovered by Claude Code — no reference needed in `plugin.json`):

```json
// patron-plugin/.mcp.json  (and coordinator-plugin/.mcp.json)
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/mcp/library_server.py"],
      "cwd": ".."
    }
  }
}
```

Skills call `mcp__library__<tool_name>` directly — no raw DuckDB CLI commands needed. The hooks serve as a safety net blocking any direct write attempts if they occur.

---

### patron-plugin

Patron-facing plugin. Catalog MCP tools only — 8 tools scoped to `library.books`.

```
patron-plugin/
├── .claude-plugin/plugin.json         ← name, version, keywords
├── .mcp.json                          ← library MCP server config (auto-discovered)
├── skills/
│   ├── patron-agent/SKILL.md          ← primary skill (8 MCP tools)
│   └── query-library/SKILL.md         ← legacy equivalent
├── hooks/hooks.json
└── scripts/enforce-patron-readonly.py ← blocks lending/replenish access + writes
```

**MCP tools available** (catalog only):
`search_books`, `get_book_details`, `check_availability`, `list_by_category`,
`list_by_status`, `locate_book`, `find_books_in_cabinet`, `get_weak_signal_books`

**MCP resources**: `library://stats`, `library://missing_books`, `library://location_map`

**Hook**: `enforce-patron-readonly.py` blocks writes AND any access to `library.lending` or `library.replenish` at the Bash level.

**Installing:**
```bash
/plugin install patron-plugin@rdewai-plugins
```

**Skills:**
- `/patron-agent` — Primary: search, availability, shelf location, RFID signal
- `/query-library` — Legacy equivalent (same tools, same hook)

**Example queries:**
```
/patron-plugin:patron-agent find Python books that are available
/patron-plugin:patron-agent is book B001 available and where is it?
/patron-plugin:patron-agent show all books in Cabinet 3 Rack 2
/patron-plugin:patron-agent which books have weak RFID signal?
/patron-plugin:patron-agent list all missing fiction books
```

---

### coordinator-plugin

Operations staff plugin. All 18 MCP tools across catalog, lending, and replenishment.

```
coordinator-plugin/
├── .claude-plugin/plugin.json          ← name, version, keywords
├── .mcp.json                           ← library MCP server config (auto-discovered)
├── skills/
│   ├── coordination-agent/SKILL.md     ← primary skill (15 MCP tools)
│   └── analyze-library/SKILL.md        ← legacy equivalent
├── hooks/hooks.json
└── scripts/enforce-readonly-queries.py ← blocks writes only
```

**MCP tools available** (all 18):
- Catalog (5): `list_by_category`, `list_by_status`, `get_weak_signal_books`, `search_books`, `get_book_details`
- Lending (5): `get_lending_stats`, `get_most_lent_books`, `search_lending`, `get_book_lending`, `get_lending_by_month`
- Replenishment (5): `get_replenish_stats`, `get_most_replenished_books`, `search_replenish`, `get_book_replenish`, `get_replenish_by_month`

**MCP resources**: `library://stats`, `library://lending_stats`, `library://replenish_stats`

**Hook**: `enforce-readonly-queries.py` blocks writes. All tables are readable.

**Installing:**
```bash
/plugin install coordinator-plugin@rdewai-plugins
```

**Skills:**
- `/coordination-agent` — Primary: lending revenue, replenishment, supply gap, monthly trends
- `/analyze-library` — Legacy equivalent (same tools, same hook)

**Example queries:**
```
/coordinator-plugin:coordination-agent what is the total lending revenue by patron segment?
/coordinator-plugin:coordination-agent which books are most borrowed?
/coordinator-plugin:coordination-agent show replenishment trends by supplier
/coordinator-plugin:coordination-agent supply gap analysis — which categories are understocked?
/coordinator-plugin:coordination-agent show monthly lending and replenishment trends
/coordinator-plugin:coordination-agent which books have the highest fee waivers?
```

---

### Skill Summary

| Invocation | Plugin | MCP Tools | Data Access |
|------------|--------|-----------|-------------|
| `/patron-plugin:patron-agent` | `patron-plugin` | 8 catalog tools | `library.books` only |
| `/patron-plugin:query-library` | `patron-plugin` | 8 catalog tools | `library.books` only |
| `/coordinator-plugin:coordination-agent` | `coordinator-plugin` | 15 tools (catalog + lending + replenish) | All three tables |
| `/coordinator-plugin:analyze-library` | `coordinator-plugin` | 15 tools (catalog + lending + replenish) | All three tables |

> **Note**: The MCP server starts automatically via `.mcp.json` when a skill is invoked — you do not need to run `make mcp-server` separately when using the plugins.

---

## All Make Commands (End of Chapter 2 excercise. From here it is for debugging or extra help)

### Setup

| Command | Description |
|---------|-------------|
| `make help` | Show all available targets |
| `make dev-setup` | Install dependencies (uv sync) |
| `make clean` | Clean generated files |

### Data (Required for Prouduction setup of RAG & MCP & Agentic)

| Command | Description |
|---------|-------------|
| `make load-data` | Load 200 books into DuckDB |
| `make verify-data` | Verify data loaded correctly |

### Testing & Quality

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make test-multi-agent` | Run multi-agent system tests |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_BASE_URL` | LLM API base URL | `https://openrouter.ai/api/v1` |
| `LLM_API_KEY` | API key (required for OpenRouter/OpenAI) | Required |
| `LLM_MODEL` | Model identifier | `openai/gpt-4o-mini` |
| `LLM_ENABLE_USAGE_TRACKING` | Enable token usage tracking | `true` |
| `DB_PATH` | DuckDB database path | `data/duckdb/chapter2.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

**Supported LLM Providers:**
| Provider | `LLM_BASE_URL` | API Key |
|----------|----------------|---------|
| OpenRouter | `https://openrouter.ai/api/v1` | Required |
| OpenAI | `https://api.openai.com/v1` | Required |
| Ollama | `http://localhost:11434/v1` | Not needed |

---

## Project Structure

```
chapter-2/
├── src/
│   ├── rag/                     # Section 1: Simple RAG demo
│   │   └── simple_rag.py        # Minimal RAG implementation
│   ├── mcp/                     # Section 2: MCP server & client
│   │   ├── library_server.py    # FastMCP server with tools/resources
│   │   └── client.py            # MCP settings menu and assistant
│   └── agentic/                 # Section 3: Agentic AI
│       ├── rag/                 # Production RAG (embeddings, vector store)
│       ├── library/             # Data layer (domain, repository)
│       ├── llm/                 # LLM abstraction (OpenRouter, Ollama)
│       ├── agents/              # All agents and assistants
│       ├── code_execution/      # Sandbox for code execution
│       ├── tools/               # Tool registry and search
│       └── a2a/                 # Agent-to-Agent protocol
├── data/
│   ├── raw/library/             # Source CSV files
│   └── duckdb/                  # DuckDB database
├── scripts/                     # Utility scripts
├── benchmarks/                  # Performance benchmarks
├── docs/                        # Detailed documentation
└── tests/                       # Unit and integration tests
```

---

## Troubleshooting

### "LLM_API_KEY not set" or "API key required"
```bash
# Add to .env file
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=openai/gpt-4o-mini
```

### "Database not found"
```bash
make load-data
```

### "No module named 'fastmcp'"
```bash
uv sync
```

### "Embeddings table empty"
```bash
make generate-embeddings
```

### "Could not set lock on file" (DuckDB)
```bash
# Close other terminals running chapter-2 commands
lsof data/duckdb/chapter2.db
# Kill orphaned processes if needed
```

### "MCP server not connecting"
1. Check server is running: `make mcp-server`
2. Verify config path in Claude Desktop settings
3. Restart Claude Desktop completely

---

## Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [OpenRouter API](https://openrouter.ai/docs)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

---

## License

Part of the "Redefining Data Engineering with AI" project.
