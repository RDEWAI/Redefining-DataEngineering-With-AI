# Research: Chapter 3 - AI Engineering with Library Management Data

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-14

## Executive Summary

This document consolidates research findings for implementing Chapter 3's AI Engineering features. All technical unknowns have been resolved with clear decisions and rationales.

---

## 1. MCP Server Implementation (FastMCP)

### Decision
Use **FastMCP** as the MCP server SDK for Python.

### Rationale
- Pythonic API with decorators for tools, resources, and prompts
- Automatic JSON schema generation from type hints
- Built-in Claude Desktop integration via `fastmcp install`
- Active development and community support
- Compatible with UV package manager

### Alternatives Considered
- **mcp-python-sdk (official)**: Lower-level, more boilerplate
- **Custom implementation**: Too much effort for learning purposes

### Key Implementation Pattern

```python
from fastmcp import FastMCP, Context

mcp = FastMCP("LibraryServer")

@mcp.tool
def search_books(query: str, category: str = None) -> list[dict]:
    """Search books by title, author, or category.

    Args:
        query: Search query string
        category: Optional category filter
    """
    # Implementation using repository layer
    pass

@mcp.resource("library://stats")
def get_stats() -> str:
    """Get library statistics."""
    pass

@mcp.prompt()
def book_search_prompt(query: str) -> str:
    """Generate a book search prompt."""
    return f"Please search for books matching: {query}"

if __name__ == "__main__":
    mcp.run()
```

### Installation
```bash
uv add fastmcp
```

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "library-server": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "chapter-3/src/mcp_servers/library_server.py"]
    }
  }
}
```

---

## 2. Vector Similarity Search (DuckDB VSS)

### Decision
Use **DuckDB VSS extension** for RAG vector storage and similarity search.

### Rationale
- Keeps all data in single DuckDB database (no external vector DB)
- Sufficient for 200 books (VSS limitations don't apply at this scale)
- Educational value: demonstrates RAG without infrastructure complexity
- HNSW indexing provides fast approximate nearest neighbor search

### Alternatives Considered
- **ChromaDB**: Adds external dependency, overkill for 200 records
- **Pinecone/Weaviate**: Cloud services, inappropriate for local learning
- **FAISS**: Lower-level, requires more code

### Key Limitations (Acceptable for Educational Use)
- Index must fit in RAM (not an issue for 200 books)
- Experimental persistence (fine for learning environment)
- Only supports FLOAT[] arrays

### Implementation Pattern

```python
import duckdb
from sentence_transformers import SentenceTransformer

# Setup
conn = duckdb.connect('chapter-3/data/duckdb/library.db')
conn.execute("INSTALL vss; LOAD vss")
conn.execute("SET hnsw_enable_experimental_persistence = true")

# Create table with embeddings
conn.execute("""
    CREATE TABLE IF NOT EXISTS book_embeddings (
        book_id VARCHAR PRIMARY KEY,
        title VARCHAR,
        author VARCHAR,
        category VARCHAR,
        embedding FLOAT[384]
    )
""")

# Create HNSW index (after data population)
conn.execute("""
    CREATE INDEX IF NOT EXISTS book_embedding_idx
    ON book_embeddings USING HNSW (embedding)
    WITH (metric = 'cosine')
""")

# Semantic search
def semantic_search(query: str, top_k: int = 5):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query).tolist()

    return conn.execute("""
        SELECT book_id, title, author, category,
               array_cosine_distance(embedding, ?::FLOAT[384]) AS distance
        FROM book_embeddings
        ORDER BY distance ASC
        LIMIT ?
    """, [query_embedding, top_k]).fetchall()
```

### Embedding Model Choice
- **all-MiniLM-L6-v2**: 384 dimensions, fast, good quality
- Alternative: **BGE-small-en-v1.5** for slightly better quality

---

## 3. Sandboxed Code Execution

### Decision
Use **subprocess isolation with resource limits** for educational sandbox. Docker optional for production deployment.

### Rationale
- Subprocess provides process isolation without Docker complexity
- Sufficient for educational environment (trusted learner context)
- Demonstrates security concepts without infrastructure overhead
- Can be upgraded to Docker for production

### Alternatives Considered
- **Docker/gVisor**: Best security but adds complexity for learning
- **RestrictedPython**: Not a true sandbox, known bypass vectors
- **exec() with globals**: No isolation, dangerous

### Security Model

```python
import subprocess
import resource
import signal
import sys
from typing import Dict, Any

ALLOWED_IMPORTS = {'pandas', 'duckdb', 'numpy', 'matplotlib', 'seaborn', 'math', 'datetime'}
TIMEOUT_SECONDS = 30
MEMORY_LIMIT_MB = 512

class CodeSandbox:
    def __init__(self, timeout: int = TIMEOUT_SECONDS, memory_mb: int = MEMORY_LIMIT_MB):
        self.timeout = timeout
        self.memory_bytes = memory_mb * 1024 * 1024

    def _set_limits(self):
        """Set resource limits for child process (Unix only)."""
        # Memory limit
        resource.setrlimit(resource.RLIMIT_AS, (self.memory_bytes, self.memory_bytes))
        # CPU time limit
        resource.setrlimit(resource.RLIMIT_CPU, (self.timeout, self.timeout))

    def execute(self, code: str, db_path: str = None) -> Dict[str, Any]:
        """Execute code in isolated subprocess."""
        # Wrap code with imports and setup
        wrapped_code = f'''
import sys
sys.path.insert(0, '.')

# Pre-import allowed modules
import pandas as pd
import numpy as np
import duckdb
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Connect to database if provided
db_path = {repr(db_path)}
if db_path:
    conn = duckdb.connect(db_path, read_only=True)

# User code
{code}
'''

        try:
            result = subprocess.run(
                [sys.executable, '-c', wrapped_code],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                preexec_fn=self._set_limits if sys.platform != 'win32' else None
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timeout': False
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Execution timed out (30 second limit)',
                'timeout': True
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'timeout': False
            }
```

### Import Whitelist
Per clarification session: `pandas, duckdb, numpy, matplotlib, seaborn`

---

## 4. LLM Provider Integration (OpenRouter)

### Decision
Use **OpenRouter** as primary LLM provider with **OpenAI SDK** compatibility.

### Rationale
- Single API for 300+ models (Claude, GPT, Gemini, open-source)
- OpenAI SDK compatible (easy to swap providers)
- Built-in token counting in responses
- No markup on model costs
- Ollama as local alternative

### Alternatives Considered
- **Direct Anthropic API**: Single provider, less flexibility
- **LiteLLM**: Additional abstraction layer, more complexity
- **Ollama only**: Limited to local models

### Implementation Pattern

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        pass

    @abstractmethod
    def count_tokens(self, messages: List[Dict]) -> int:
        pass

class OpenRouterProvider(LLMProvider):
    def __init__(self, model: str = "anthropic/claude-3.5-sonnet"):
        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "http://localhost",
                "X-Title": "LibraryAssistant"
            }
        )
        self._last_usage = None

    def generate(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        params = {
            "model": self.model,
            "messages": messages,
            "extra_body": {"usage": {"include": True}}
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)
        self._last_usage = response.usage

        return {
            "content": response.choices[0].message.content,
            "tool_calls": response.choices[0].message.tool_calls,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

    def count_tokens(self, messages: List[Dict]) -> int:
        # Use last known usage or estimate
        if self._last_usage:
            return self._last_usage.prompt_tokens
        # Rough estimate: 4 chars per token
        return sum(len(str(m)) // 4 for m in messages)

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.2"):
        self.model = model
        self.client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"  # Ollama doesn't require API key
        )

    def generate(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        # Similar implementation for Ollama
        pass

    def count_tokens(self, messages: List[Dict]) -> int:
        # Ollama provides token counts in response
        pass
```

### Recommended Models for Tool Use
- **anthropic/claude-3.5-sonnet**: Best overall for tool calling
- **deepseek/deepseek-chat**: Cost-effective alternative
- **meta-llama/llama-3.1-70b-instruct**: Open-source option

---

## 5. Multi-Agent Architecture (A2A-inspired)

### Decision
Use **in-process message passing** with simple protocol inspired by Google A2A.

### Rationale
- Simpler than full A2A HTTP implementation
- Demonstrates multi-agent concepts without network complexity
- Easy to test and debug
- Can be upgraded to HTTP/A2A later if needed

### Alternatives Considered
- **Full A2A Protocol**: Too complex for learning purposes
- **LangGraph**: Adds heavy dependency
- **AutoGen**: Microsoft-specific patterns

### Implementation Pattern

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import uuid

class QueryType(Enum):
    SEARCH = "search"
    ANALYTICS = "analytics"
    RECOMMENDATION = "recommendation"
    MULTI_STEP = "multi_step"

@dataclass
class AgentMessage:
    id: str
    sender: str
    recipient: str
    query_type: QueryType
    content: Any
    context: Dict = None

    @classmethod
    def create(cls, sender: str, recipient: str, query_type: QueryType, content: Any):
        return cls(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            query_type=query_type,
            content=content,
            context={}
        )

class Agent:
    def __init__(self, name: str, capabilities: list[QueryType]):
        self.name = name
        self.capabilities = capabilities

    def can_handle(self, query_type: QueryType) -> bool:
        return query_type in self.capabilities

    def process(self, message: AgentMessage) -> AgentMessage:
        raise NotImplementedError

class OrchestratorAgent(Agent):
    def __init__(self, agents: Dict[str, Agent]):
        super().__init__("orchestrator", [qt for qt in QueryType])
        self.agents = agents

    def classify_query(self, query: str) -> QueryType:
        """Classify user query into type using LLM."""
        # Use LLM to classify
        pass

    def route(self, message: AgentMessage) -> list[AgentMessage]:
        """Route message to appropriate agent(s)."""
        results = []
        for agent in self.agents.values():
            if agent.can_handle(message.query_type):
                result = agent.process(message)
                results.append(result)
        return results

    def aggregate(self, results: list[AgentMessage]) -> str:
        """Aggregate results from multiple agents."""
        pass
```

---

## 6. Dependencies Summary

### New Dependencies for chapter-3/pyproject.toml

```toml
[project]
name = "chapter-3-ai-engineering"
version = "0.1.0"
requires-python = ">=3.10,<3.13"
dependencies = [
    # Data & Database
    "duckdb>=1.1.3",
    "pandas>=2.0.0",
    "numpy>=1.24.0",

    # Visualization (sandbox whitelist)
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",

    # MCP Server
    "fastmcp>=0.4.0",

    # LLM Integration
    "openai>=1.0.0",  # OpenAI SDK for OpenRouter

    # Embeddings
    "sentence-transformers>=2.2.0",

    # Testing
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
]

[dependency-groups]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

---

## 7. Resolved Technical Unknowns

| Unknown | Resolution | Source |
|---------|------------|--------|
| MCP SDK choice | FastMCP | Research: active, Pythonic, UV-compatible |
| Vector DB for RAG | DuckDB VSS | Research: integrated, sufficient for scale |
| Sandbox approach | Subprocess + resource limits | Research: balanced security/simplicity |
| LLM provider | OpenRouter (primary), Ollama (local) | Research: flexibility, OpenAI-compatible |
| Embedding model | all-MiniLM-L6-v2 (384d) | Research: fast, good quality |
| Multi-agent protocol | In-process A2A-inspired | Research: simplicity for learning |
| Import whitelist | pandas, duckdb, numpy, matplotlib, seaborn | Clarification session |
| Error handling | User-friendly messages | Clarification session |

---

## Sources

- [FastMCP Documentation](https://gofastmcp.com/)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [Google A2A Protocol](https://github.com/google/A2A)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
