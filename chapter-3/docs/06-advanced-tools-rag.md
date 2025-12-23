# Advanced Tool Use & RAG

This document explains the implementation of advanced tool patterns and RAG (Retrieval-Augmented Generation) for semantic search in the Library Assistant.

## Overview

Phase 7 introduces two major capabilities:

1. **Tool Registry & Search**: Dynamic tool discovery and execution
2. **RAG with DuckDB VSS**: Semantic search over book descriptions

These features enable more natural interactions:
- Find tools based on what the user wants to do
- Search books using natural language, not just keywords

## RAG Architecture

### What is RAG?

RAG (Retrieval-Augmented Generation) enhances LLM responses by:
1. Converting text to vector embeddings
2. Storing embeddings in a vector database
3. Finding semantically similar content for queries
4. Providing relevant context to the LLM

### RAG Scope Decisions

**Embedded Content** (uses RAG):
- Book descriptions (primary content for semantic search)
- Titles and authors (secondary context)
- Categories (for context only)

**Non-RAG Content** (handled by tools/SQL):
- Status (Present/Missing/Checked Out) - exact match
- Location (Cabinet/Rack/Row) - structured query
- Signal strength - numeric comparison

**Why this split?**
- Descriptions contain natural language ideal for semantic matching
- Status, location, signal are structured data better suited for exact queries
- Combining both gives users flexibility in how they search

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Query                               │
│              "books about time travel"                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               EmbeddingGenerator                             │
│         sentence-transformers (all-MiniLM-L6-v2)            │
│                    384 dimensions                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               DuckDBVectorStore                              │
│           library.book_embeddings table                      │
│         array_cosine_similarity search                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Ranked Results                                  │
│     1. The Time Machine (similarity: 0.85)                   │
│     2. Time Travel in Fiction (similarity: 0.78)             │
│     3. A Brief History of Time (similarity: 0.62)            │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
cd chapter-3
uv sync  # Installs sentence-transformers
```

### 2. Generate Embeddings

```bash
make generate-embeddings
```

This:
1. Loads all 200 books from the database
2. Creates text from title, author, description, category
3. Generates 384-dimensional embeddings
4. Stores embeddings in `library.book_embeddings` table

### 3. Test Semantic Search

```bash
make semantic-search
```

Example queries:
- "books about time travel"
- "programming tutorials for beginners"
- "mystery and detective stories"
- "science and the universe"

## Tool Registry

### Purpose

The Tool Registry provides:
- Dynamic tool registration with metadata
- Capability-based tool filtering
- OpenAI-compatible schema generation
- Direct tool execution

### Usage

```python
from src.agentic.tools import ToolRegistry, Capability

registry = ToolRegistry()

# Register with decorator
@registry.register(
    description="Search books by title or author",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    capabilities=[Capability.SEARCH],
)
def search_books(query: str) -> list:
    return [{"title": f"Found: {query}"}]

# Execute tool
result = registry.execute_tool("search_books", query="Python")

# Get schemas for LLM
schemas = registry.get_all_schemas()
```

### Capabilities

| Capability | Description | Example Tools |
|------------|-------------|---------------|
| SEARCH | Find or lookup | search_books, locate_book |
| ANALYTICS | Statistics/aggregation | get_library_stats |
| MONITORING | Health/status checks | get_weak_signal_books |
| RAG | Semantic search | semantic_search |
| CODE_EXECUTION | Run generated code | execute_analytics |

## Tool Search

### Name-Based Search

```python
from src.agentic.tools import ToolSearch, create_library_tool_registry

registry = create_library_tool_registry()
searcher = ToolSearch(registry)

# Exact or partial match
tools = searcher.search_by_name("search")
# Returns: [search_books, semantic_search]
```

### Semantic Search

```python
# Find tools by description similarity
results = searcher.search_by_description(
    "find books about programming",
    top_k=3
)
for tool, score in results:
    print(f"{tool.name}: {score:.3f}")
```

### Dynamic Tool Selection

```python
# Get relevant tools for a query
tools = searcher.get_tools_for_query(
    "what programming books do you have?",
    threshold=0.3
)
```

## Data Analysis Agent

The Data Analysis Agent combines:
- Semantic search for book discovery
- Code execution for complex analytics
- Tool registry for standard operations

```bash
make data-analysis
```

Example queries:
- "Show library statistics"
- "Top 5 categories by missing books"
- "Books about time travel"
- "Find books with weak signal"

## API Reference

### EmbeddingGenerator

```python
from src.agentic.rag import EmbeddingGenerator

generator = EmbeddingGenerator()

# Single text
embedding = generator.embed_text("Python programming guide")

# Batch
embeddings = generator.embed_texts(["Text 1", "Text 2"])

# Books
embeddings = generator.embed_books(books)
```

### DuckDBVectorStore

```python
from src.agentic.rag import DuckDBVectorStore

store = DuckDBVectorStore(db_path="data/duckdb/chapter3.db")

# Store embeddings
store.store_embeddings(book_ids, embeddings)

# Search
results = store.semantic_search(query_embedding, top_k=5)

# Returns: [{"book_id": "B001", "similarity": 0.85}, ...]
```

### ToolRegistry

```python
from src.agentic.tools import ToolRegistry, ToolMetadata

registry = ToolRegistry()

# Register tool
registry.register_tool(ToolMetadata(
    name="my_tool",
    description="Does something",
    input_schema={"type": "object"},
    capabilities=["search"],
    handler=my_function,
))

# List by capability
search_tools = registry.list_tools(capability="search")

# Execute
result = registry.execute_tool("my_tool", arg="value")
```

## Performance Considerations

### Embedding Generation

- **Model**: all-MiniLM-L6-v2 (fast, 384 dimensions)
- **Batch size**: Process all 200 books at once
- **Time**: ~5-10 seconds for initial embedding generation

### Vector Search

- **Algorithm**: Cosine similarity
- **Index**: HNSW (optional, for larger datasets)
- **Latency**: <10ms for 200 books

### Memory

- Embeddings: ~300KB for 200 books (200 x 384 x 4 bytes)
- Model: ~100MB in memory (loaded on first use)

## Testing

```bash
# Unit tests
uv run pytest tests/unit/test_embeddings.py -v
uv run pytest tests/unit/test_tool_registry.py -v

# Integration tests (requires database)
uv run pytest tests/integration/test_semantic_search.py -v
```

## Troubleshooting

### "No embeddings found"

```bash
make generate-embeddings
```

### "Database not found"

```bash
make load-data
make generate-embeddings
```

### "sentence-transformers not installed"

```bash
uv sync
```

### Slow embedding generation

First-time embedding generation downloads the model (~100MB).
Subsequent runs use the cached model.

## References

- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [sentence-transformers](https://www.sbert.net/)
- [DuckDB Vector Similarity Search](https://duckdb.org/docs/extensions/vss.html)
