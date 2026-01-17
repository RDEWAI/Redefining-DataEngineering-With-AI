# Data Model: Chapter 2 - AI Engineering with Library Management Data

**Branch**: `003-chapter2-ai-engineering` | **Date**: 2025-12-14

## Overview

This document defines the data model for the Library Management AI Engineering system. The model supports book inventory management, RFID tracking, and AI-powered search and analytics.

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          LIBRARY SCHEMA                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐         ┌─────────────────────────┐           │
│  │     books       │         │    book_embeddings      │           │
│  ├─────────────────┤         ├─────────────────────────┤           │
│  │ PK book_id      │────────▶│ PK book_id              │           │
│  │    title        │         │    title                │           │
│  │    author       │         │    author               │           │
│  │    category     │         │    category             │           │
│  │    cabinet      │         │    embedding FLOAT[384] │           │
│  │    rack         │         └─────────────────────────┘           │
│  │    row          │                                               │
│  │    signal_str   │         ┌─────────────────────────┐           │
│  │    timestamp    │         │    tool_registry        │           │
│  │    status       │         ├─────────────────────────┤           │
│  └─────────────────┘         │ PK tool_name            │           │
│                              │    description          │           │
│                              │    input_schema (JSON)  │           │
│                              │    capabilities[]       │           │
│                              │    embedding FLOAT[384] │           │
│                              └─────────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Entities

### 1. Book

The primary entity representing a library book with RFID tracking data.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `book_id` | VARCHAR | PRIMARY KEY | Unique identifier (e.g., "B001") |
| `title` | VARCHAR | NOT NULL | Book title |
| `author` | VARCHAR | NOT NULL | Author name |
| `description` | VARCHAR | NOT NULL | Book description/summary (50-100 words for RAG embeddings) |
| `category` | VARCHAR | NOT NULL | Category (Programming, History, Science, Fiction, Thriller) |
| `cabinet` | INTEGER | NOT NULL, >= 1 | Cabinet number |
| `rack` | INTEGER | NOT NULL, >= 1 | Rack number within cabinet |
| `row` | INTEGER | NOT NULL, >= 1 | Row number within rack |
| `signal_strength` | FLOAT | NOT NULL | RFID signal strength in dBm (typically -30 to -90) |
| `timestamp` | TIMESTAMP | NOT NULL | Last RFID scan timestamp |
| `status` | VARCHAR | NOT NULL | Availability status |

**Status Values (Enum)**:
- `Present` - Book is on shelf and detectable
- `Missing` - Book cannot be located or not seen for >30 minutes
- `Checked Out` - Book is borrowed by a patron

**Domain Invariants**:
- **Weak Signal**: `signal_strength < -55` dBm indicates RFID maintenance needed
- **Missing Book**: `status = 'Missing'` OR last seen > 30 minutes ago
- **Location Anomaly**: Same `book_id` in different `cabinet` within 5-minute window

**SQL Definition**:
```sql
CREATE TABLE library.books (
    book_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    category VARCHAR NOT NULL CHECK (category IN ('Programming', 'History', 'Science', 'Fiction', 'Thriller')),
    cabinet INTEGER NOT NULL CHECK (cabinet >= 1),
    rack INTEGER NOT NULL CHECK (rack >= 1),
    row INTEGER NOT NULL CHECK (row >= 1),
    signal_strength FLOAT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('Present', 'Missing', 'Checked Out'))
);
```

---

### 2. BookEmbedding

Vector embeddings for semantic search over book metadata.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `book_id` | VARCHAR | PRIMARY KEY, FK → books | Reference to book |
| `title` | VARCHAR | NOT NULL | Denormalized for search display |
| `author` | VARCHAR | NOT NULL | Denormalized for search display |
| `description` | VARCHAR | NOT NULL | Primary content for embedding (50-100 words) |
| `category` | VARCHAR | NOT NULL | Denormalized for search display |
| `embedding` | FLOAT[384] | NOT NULL | 384-dimensional embedding vector |

**Embedding Scope**:
- **Primary embedded field**: description (rich textual content for semantic search)
- **Secondary embedded fields**: title, author, category (concatenated with description)
- **Non-embedded fields**: status, location, signal_strength (handled by structured queries)

**SQL Definition**:
```sql
CREATE TABLE library.book_embeddings (
    book_id VARCHAR PRIMARY KEY REFERENCES library.books(book_id),
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    embedding FLOAT[384] NOT NULL
);

-- HNSW index for fast similarity search (create after data population)
CREATE INDEX book_embedding_idx ON library.book_embeddings
USING HNSW (embedding) WITH (metric = 'cosine');
```

---

### 3. Tool (Tool Registry)

Metadata for dynamically discoverable tools.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `tool_name` | VARCHAR | PRIMARY KEY | Unique tool identifier |
| `description` | VARCHAR | NOT NULL | Human-readable description |
| `input_schema` | JSON | NOT NULL | JSON Schema for tool parameters |
| `capabilities` | VARCHAR[] | NOT NULL | Capability tags (search, analytics, monitoring) |
| `embedding` | FLOAT[384] | NULL | Optional embedding for similarity search |

**Capability Tags**:
- `search` - Book discovery and lookup
- `analytics` - Statistics and reporting
- `monitoring` - RFID and status tracking

**SQL Definition**:
```sql
CREATE TABLE library.tool_registry (
    tool_name VARCHAR PRIMARY KEY,
    description VARCHAR NOT NULL,
    input_schema JSON NOT NULL,
    capabilities VARCHAR[] NOT NULL,
    embedding FLOAT[384]
);
```

---

## Domain Classes (Python)

### Book Domain Object

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class BookStatus(Enum):
    PRESENT = "Present"
    MISSING = "Missing"
    CHECKED_OUT = "Checked Out"

class Category(Enum):
    PROGRAMMING = "Programming"
    HISTORY = "History"
    SCIENCE = "Science"
    FICTION = "Fiction"
    THRILLER = "Thriller"

@dataclass
class Location:
    cabinet: int
    rack: int
    row: int

    def __str__(self) -> str:
        return f"Cabinet {self.cabinet}, Rack {self.rack}, Row {self.row}"

@dataclass
class Book:
    book_id: str
    title: str
    author: str
    description: str  # 50-100 words for RAG embeddings
    category: Category
    location: Location
    signal_strength: float
    timestamp: datetime
    status: BookStatus

    @property
    def has_weak_signal(self) -> bool:
        """Check if RFID signal is weak (below -55 dBm)."""
        return self.signal_strength < -55

    @property
    def is_available(self) -> bool:
        """Check if book is available for checkout."""
        return self.status == BookStatus.PRESENT

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "category": self.category.value,
            "cabinet": self.location.cabinet,
            "rack": self.location.rack,
            "row": self.location.row,
            "signal_strength": self.signal_strength,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value
        }
```

### Tool Domain Object

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    capabilities: List[str]
    embedding: Optional[List[float]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format for LLM tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }
```

---

## Validation Rules

### Book Validation

| Rule | Field(s) | Validation |
|------|----------|------------|
| Valid Category | category | Must be one of: Programming, History, Science, Fiction, Thriller |
| Valid Status | status | Must be one of: Present, Missing, Checked Out |
| Positive Location | cabinet, rack, row | All must be >= 1 |
| Signal Range | signal_strength | Typically -30 to -90 dBm (warning if outside range) |
| Non-empty Text | title, author | Must not be empty or whitespace-only |
| Valid Book ID | book_id | Must match pattern: B followed by digits (e.g., B001) |
| Description Length | description | Must be 50-500 characters (optimal for RAG embeddings) |

### Tool Validation

| Rule | Field(s) | Validation |
|------|----------|------------|
| Valid Name | tool_name | Must be snake_case identifier |
| Valid Schema | input_schema | Must be valid JSON Schema |
| Valid Capabilities | capabilities | Each must be: search, analytics, or monitoring |

---

## State Transitions

### Book Status Lifecycle

```
                    ┌─────────────┐
                    │   Present   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Missing   │ │ Checked Out │ │   Present   │
    └──────┬──────┘ └──────┬──────┘ └─────────────┘
           │               │               ▲
           │               │               │
           └───────────────┴───────────────┘
                    (Return/Found)
```

**Transitions**:
- `Present → Checked Out`: Book borrowed by patron
- `Present → Missing`: Book not detected for >30 minutes
- `Checked Out → Present`: Book returned
- `Missing → Present`: Book found/returned to shelf

---

## Queries & Access Patterns

### Common Queries

| Query | Access Pattern | Index Support |
|-------|---------------|---------------|
| Search by title/author | LIKE/ILIKE on text | Full-text or B-tree |
| Filter by category | Equality on category | B-tree index |
| Filter by status | Equality on status | B-tree index |
| Find by location | Equality on cabinet/rack/row | Composite index |
| Weak signal books | Range on signal_strength | B-tree index |
| Semantic search | Vector similarity | HNSW index |

### Recommended Indexes

```sql
-- Category and status filters
CREATE INDEX idx_books_category ON library.books(category);
CREATE INDEX idx_books_status ON library.books(status);

-- Location lookups
CREATE INDEX idx_books_location ON library.books(cabinet, rack, row);

-- Weak signal monitoring
CREATE INDEX idx_books_signal ON library.books(signal_strength)
WHERE signal_strength < -55;

-- Semantic search (in book_embeddings)
-- Created via DuckDB VSS extension
```

---

## Data Volume & Scale

| Entity | Expected Count | Growth Rate |
|--------|---------------|-------------|
| Books | 200 | Static (fixed dataset) |
| Book Embeddings | 200 | 1:1 with books |
| Tools | 8-15 | Grows with features |

**Performance Considerations**:
- 200 records fits entirely in memory
- Vector similarity search is fast at this scale
- No partitioning needed
- Single DuckDB file sufficient

---

## Sample Data

### Book Record
```json
{
  "book_id": "B001",
  "title": "Python Programming",
  "author": "John Smith",
  "description": "Master Python programming through this comprehensive guide covering data structures, algorithms, and best practices. Learn problem-solving with step-by-step tutorials and real-world examples for developers of all skill levels.",
  "category": "Programming",
  "cabinet": 3,
  "rack": 2,
  "row": 5,
  "signal_strength": -45.2,
  "timestamp": "2025-01-15T10:30:00",
  "status": "Present"
}
```

### Tool Record
```json
{
  "tool_name": "search_books",
  "description": "Search books by title, author, or category",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search query"},
      "category": {"type": "string", "description": "Optional category filter"}
    },
    "required": ["query"]
  },
  "capabilities": ["search"]
}
```

---

## Phase 5.5 Entities (NEW)

### 4. UnifiedLLMClient

Configuration object for unified LLM provider access.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `base_url` | str | NOT NULL, Valid URL | API endpoint (OpenRouter, Ollama, or OpenAI) |
| `api_key` | str \| None | NULL for Ollama | Authentication key |
| `model` | str | NOT NULL | Model identifier (e.g., "openai/gpt-4o-mini") |
| `enable_usage_tracking` | bool | NOT NULL, Default: True | Enable token usage tracking |

**Provider Types (Inferred from base_url)**:
- `openrouter`: https://openrouter.ai/api/v1
- `ollama`: http://localhost:11434/v1
- `openai`: https://api.openai.com/v1

**Validation Rules**:
- `base_url` must be valid HTTP/HTTPS URL
- `api_key` required if provider is OpenRouter or OpenAI
- `model` must not be empty string
- Usage tracking only functional for OpenRouter provider

**Python Definition**:
```python
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI

@dataclass
class UnifiedLLMClient:
    base_url: str
    api_key: Optional[str]
    model: str
    enable_usage_tracking: bool = True

    def __post_init__(self):
        """Validate configuration and initialize OpenAI client."""
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.model:
            raise ValueError("model is required")

        # Require API key for non-Ollama providers
        if "ollama" not in self.base_url.lower() and not self.api_key:
            raise ValueError("api_key required for OpenRouter and OpenAI")

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "not-required"
        )

    @classmethod
    def from_env(cls) -> "UnifiedLLMClient":
        """Create client from environment variables."""
        import os
        return cls(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL"),
            enable_usage_tracking=os.getenv("LLM_ENABLE_USAGE_TRACKING", "true").lower() == "true"
        )
```

---

### 5. UsageMetrics

Token usage and cost tracking for LLM requests.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `prompt_tokens` | int | >= 0 | Input tokens consumed |
| `completion_tokens` | int | >= 0 | Output tokens generated |
| `total_tokens` | int | >= 0 | Sum of prompt + completion |
| `model` | str | NOT NULL | Model used for request |

**Validation Rules**:
- All token counts must be non-negative integers
- `total_tokens` = `prompt_tokens` + `completion_tokens`
- Returned from OpenAI SDK response.usage

**Python Definition**:
```python
from dataclasses import dataclass

@dataclass
class UsageMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str

    def __post_init__(self):
        """Validate token counts."""
        if self.prompt_tokens < 0 or self.completion_tokens < 0:
            raise ValueError("Token counts must be non-negative")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")

    @classmethod
    def from_openai_usage(cls, usage_obj, model: str) -> "UsageMetrics":
        """Create from OpenAI SDK usage object."""
        return cls(
            prompt_tokens=usage_obj.prompt_tokens,
            completion_tokens=usage_obj.completion_tokens,
            total_tokens=usage_obj.total_tokens,
            model=model
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model
        }
```

**Sample Data**:
```json
{
  "prompt_tokens": 150,
  "completion_tokens": 50,
  "total_tokens": 200,
  "model": "openai/gpt-4o-mini"
}
```

---

### 6. GitHookConfig

Configuration for pre-commit and pre-push hooks (stored in .pre-commit-config.yaml).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `hook_id` | str | NOT NULL | Unique hook identifier |
| `name` | str | NOT NULL | Display name |
| `entry` | str | NOT NULL | Command to execute |
| `language` | str | NOT NULL | Hook language (system, python, etc.) |
| `types` | str[] | NOT NULL | File types to trigger on |
| `stages` | str[] | NULL | Git stages (commit, push) |
| `pass_filenames` | bool | NOT NULL, Default: True | Pass filenames to hook |

**Hook Types**:
- `pre-commit`: Run before git commit (linting, formatting)
- `pre-push`: Run before git push (testing)

**YAML Definition** (.pre-commit-config.yaml):
```yaml
repos:
  - repo: local
    hooks:
      # Pre-commit: Fast checks
      - id: ruff-check
        name: "Ruff Linter"
        entry: "uv run ruff check"
        language: system
        types: [python]
        pass_filenames: true

      - id: ruff-format
        name: "Ruff Formatter"
        entry: "uv run ruff format --check"
        language: system
        types: [python]
        pass_filenames: true

      - id: mypy
        name: "Type Checker"
        entry: "uv run mypy"
        language: system
        types: [python]
        pass_filenames: false

      # Pre-push: Tests
      - id: pytest-unit
        name: "Unit Tests"
        entry: "uv run pytest tests/unit/ -v"
        language: system
        pass_filenames: false
        stages: [push]
```

---

## Phase 7.5 Entities (Enterprise Tool Scale)

### 7. DummyTool

Enterprise dummy tool definition for demonstrating code execution token efficiency at scale.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | str | NOT NULL, Unique | Tool identifier (e.g., "engineering_run_build") |
| `domain` | str | NOT NULL | Enterprise domain (10 domains total) |
| `description` | str | NOT NULL | Detailed tool description (50-100 words) |
| `input_schema` | dict | NOT NULL | JSON Schema for parameters |
| `is_mock` | bool | NOT NULL, Default: True | Always True for dummy tools |

**Domain Values (Enum)**:
- `engineering` - CI/CD and code operations
- `data_platform` - Data warehouse and analytics
- `security` - Compliance and access control
- `hr` - Employee data and requests
- `finance` - Budget and expense management
- `marketing` - Campaign and content operations
- `sales` - CRM and pipeline management
- `support` - Customer service operations
- `infrastructure` - DevOps and monitoring
- `ml_platform` - ML/AI model operations

**Python Definition**:
```python
from dataclasses import dataclass
from enum import Enum
from typing import Any

class EnterpriseDomain(Enum):
    ENGINEERING = "engineering"
    DATA_PLATFORM = "data_platform"
    SECURITY = "security"
    HR = "hr"
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    SUPPORT = "support"
    INFRASTRUCTURE = "infrastructure"
    ML_PLATFORM = "ml_platform"

@dataclass
class DummyTool:
    name: str
    domain: EnterpriseDomain
    description: str
    input_schema: dict[str, Any]
    is_mock: bool = True

    def to_tool_definition(self) -> "ToolDefinition":
        """Convert to ToolDefinition for LLM tool calling."""
        from llm.base import ToolDefinition
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.input_schema
        )

    def execute(self, **kwargs) -> dict[str, Any]:
        """Execute mock tool (returns simulated response)."""
        return {
            "success": True,
            "domain": self.domain.value,
            "tool": self.name,
            "message": f"Mock response from {self.domain.value}.{self.name}",
            "input": kwargs,
            "data": {"mock": True}
        }
```

**Sample Tools by Domain**:

```json
{
  "engineering": [
    {"name": "engineering_run_build", "description": "Trigger CI/CD build pipeline..."},
    {"name": "engineering_check_ci_status", "description": "Check current CI status..."},
    {"name": "engineering_trigger_deployment", "description": "Deploy to environment..."}
  ],
  "data_platform": [
    {"name": "data_query_warehouse", "description": "Execute SQL against warehouse..."},
    {"name": "data_get_lineage", "description": "Get data lineage graph..."},
    {"name": "data_validate_schema", "description": "Validate schema changes..."}
  ]
}
```

---

### 8. DummyToolConfig

Configuration for enabling/disabling dummy tools in the assistant.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `enabled` | bool | NOT NULL, Default: False | Whether dummy tools are active |
| `tool_count` | int | >= 0, Default: 100 | Number of dummy tools loaded |
| `domains` | list[str] | NULL (all if None) | Filter to specific domains |

**Python Definition**:
```python
from dataclasses import dataclass, field

@dataclass
class DummyToolConfig:
    enabled: bool = False
    tool_count: int = 100
    domains: list[str] | None = None  # None = all domains

    def get_active_tools(self) -> list["DummyTool"]:
        """Get list of active dummy tools based on config."""
        if not self.enabled:
            return []

        all_tools = generate_all_dummy_tools()

        if self.domains:
            all_tools = [t for t in all_tools if t.domain.value in self.domains]

        return all_tools[:self.tool_count]
```

**Token Impact (Key Metrics)**:

| Configuration | Tool Count | Traditional Tokens | Code Exec Tokens | Reduction |
|---------------|------------|-------------------|------------------|-----------|
| Library only | 9 | ~1,350 | ~300 | 78% |
| + 50 dummy | 59 | ~10,200 | ~400 | 96% |
| + 100 dummy | 109 | ~19,650 | ~650 | 97% |

---

## Updated Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          LIBRARY SCHEMA                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐         ┌─────────────────────────┐           │
│  │     books       │         │    book_embeddings      │           │
│  ├─────────────────┤         ├─────────────────────────┤           │
│  │ PK book_id      │────────▶│ PK book_id              │           │
│  │    title        │         │    title                │           │
│  │    author       │         │    author               │           │
│  │    description  │         │    description          │           │
│  │    category     │         │    category             │           │
│  │    cabinet      │         │    embedding FLOAT[384] │           │
│  │    rack         │         └─────────────────────────┘           │
│  │    row          │                                               │
│  │    signal_str   │         ┌─────────────────────────┐           │
│  │    timestamp    │         │    tool_registry        │           │
│  │    status       │         ├─────────────────────────┤           │
│  └─────────────────┘         │ PK tool_name            │           │
│                              │    description          │           │
│                              │    input_schema (JSON)  │           │
│                              │    capabilities[]       │           │
│                              │    embedding FLOAT[384] │           │
│                              │    domain (Phase 7.5)   │           │
│                              │    is_mock (Phase 7.5)  │           │
│                              └─────────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
