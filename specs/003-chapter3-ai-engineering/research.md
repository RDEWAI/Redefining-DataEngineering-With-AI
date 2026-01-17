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

---

## 8. Phase 5.5: Unified LLM Client & Git Hooks (NEW)

### Decision: OpenAI SDK as Unified Client

**Use OpenAI SDK v1.0+ with custom base_url for all providers (OpenRouter, Ollama, OpenAI).**

**Rationale**:
- Single dependency replaces multiple custom clients
- Type-safe API with excellent IDE support
- Supports custom `base_url` parameter for any OpenAI-compatible API
- Well-documented and actively maintained
- Already supports function calling, streaming, etc.

**Implementation**:
```python
from openai import OpenAI

# OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("LLM_API_KEY")
)

# Ollama (local)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-required"
)

# OpenAI (standard)
client = OpenAI(
    base_url="https://api.openai.com/v1",
    api_key=os.getenv("LLM_API_KEY")
)
```

**Alternatives Considered**:
- Custom httpx-based client: More control but higher maintenance
- Provider-specific SDKs: Inconsistent APIs, more dependencies
- LangChain wrappers: Too heavy for this use case

---

### Decision: OpenRouter Usage Accounting

**Use built-in `usage` parameter in API requests for token tracking.**

**Rationale**:
- Most accurate (uses model's native tokenizer)
- No additional API calls required
- ~200ms overhead acceptable for non-streaming
- Standard OpenAI SDK response format

**Response Format**:
```json
{
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 50,
    "total_tokens": 200
  }
}
```

**Key Findings** (from [OpenRouter Usage Accounting docs](https://openrouter.ai/docs/use-cases/usage-accounting)):
- Add `"usage": true` to request for detailed token counts
- Adds ~200ms latency to final response chunk
- Alternative: GET /api/v1/generation/{id} for async stats
- Credits API: GET /api/v1/key for balance checking

**Alternatives Considered**:
- Generation endpoint: Extra API call, async complexity
- Client-side estimation: Inaccurate, model-dependent
- No tracking: Misses optimization opportunities

---

### Decision: Pre-commit Framework for Git Hooks

**Use pre-commit framework with .pre-commit-config.yaml.**

**Rationale** (from [2025 best practices](https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835)):
- Python ecosystem standard
- Automatic hook installation: `pre-commit install`
- Version-controlled configuration
- Community hook repositories available
- Multi-language support (future-proof)

**Hook Configuration**:
```yaml
repos:
  - repo: local
    hooks:
      # Pre-commit: Fast checks (<5s)
      - id: ruff-check
        entry: uv run ruff check
        language: system
        types: [python]

      - id: mypy
        entry: uv run mypy
        language: system
        types: [python]

      # Pre-push: Tests (<30s)
      - id: pytest-unit
        entry: uv run pytest tests/unit/ -v
        language: system
        stages: [push]
```

**Alternatives Considered**:
- Manual .git/hooks/ scripts: Not version-controlled, hard to maintain
- Husky (Node.js): Overkill for Python projects
- Makefile targets: Requires manual execution

---

### Decision: Ruff for Linting/Formatting

**Use Ruff as single tool for linting, formatting, and import sorting.**

**Rationale**:
- **200x faster** than Flake8 (Rust-based)
- Replaces: Black + Flake8 + isort + pydocstyle + pyupgrade
- Drop-in Black-compatible formatting
- Already configured in pyproject.toml

**Performance Benchmarks**:
- Ruff: ~10ms for 1000 files
- Flake8: ~2000ms for same files

**Alternatives Considered**:
- Black + Flake8 + isort: Traditional but slow, 3+ tools
- Pylint: Slower, overlapping rules
- Blue: Less mature, smaller community

---

### Decision: Pre-push Testing Strategy

**Run unit tests only in pre-push hook (integration tests in CI/CD).**

**Rationale**:
- Fast execution (<30s target for developer experience)
- Catches most regressions (80%+ coverage)
- Doesn't block workflow
- Full suite (integration + E2E) runs in CI/CD

**Configuration**:
```yaml
- id: pytest-unit
  name: "Unit Tests"
  entry: "uv run pytest tests/unit/ -v"
  timeout: 30
  stages: [push]
```

**Alternatives Considered**:
- All tests: Too slow (>1 minute), friction
- No tests: Misses obvious regressions
- Only modified files: Complex, unreliable

---

### Environment Configuration (.env)

**Unified configuration replacing separate provider variables**:

```bash
# Before (Phase 5)
OPENROUTER_API_KEY=sk-or-v1-...
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-4o-mini
OLLAMA_HOST=http://localhost:11434

# After (Phase 5.5)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-...
LLM_MODEL=openai/gpt-4o-mini
LLM_ENABLE_USAGE_TRACKING=true
```

**Benefits**:
- Single pattern for all providers (change base_url to switch)
- Clear relationship between config values
- Usage tracking opt-in via flag
- Backward compatible during migration

---

### Migration Strategy

**Deprecation Path**:
1. Phase 5.5: Introduce UnifiedLLMClient, keep legacy clients
2. Phase 6: Migrate agents to UnifiedLLMClient
3. Phase 7: Remove openrouter_client.py and ollama_client.py

**Backward Compatibility**:
- Legacy clients marked deprecated in docstrings
- All code continues working during migration
- Gradual migration prevents breaking changes

---

## 9. Phase 5.5 Dependencies

**New/Updated Dependencies**:
```toml
dependencies = [
    "openai>=1.0.0",  # Already present
]

[dependency-groups]
dev = [
    "ruff>=0.1.0",        # Already present
    "mypy>=1.0.0",        # Already present
    "pre-commit>=3.0.0",  # NEW
]
```

---

## Sources

- [FastMCP Documentation](https://gofastmcp.com/)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [OpenRouter Usage Accounting](https://openrouter.ai/docs/use-cases/usage-accounting)
- [Google A2A Protocol](https://github.com/google/A2A)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Pre-commit Framework](https://pre-commit.com/)
- [Pre-Commit Hooks Guide 2025](https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835)
- [Git Hooks for Code Quality 2025](https://dev.to/arasosman/git-hooks-for-automated-code-quality-checks-guide-2025-372f)

---

## 10. Phase 7.5: Enterprise Tool Scale Demonstration (NEW)

### Decision: 100 Dummy Tools Across 10 Enterprise Domains

**Add 100 realistic enterprise dummy tools to demonstrate code execution's token efficiency at scale.**

### Rationale

From [Anthropic's Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) engineering blog:

> "The token overhead of tool definitions becomes increasingly significant as the number of tools grows. For enterprises with hundreds of tools across different teams, this can represent a substantial portion of the context budget."

**Key Insights from Anthropic Paper**:
1. Tool definitions in JSON schema format are verbose (~150-200 tokens each)
2. Traditional tool calling requires ALL tool definitions in every request
3. Code execution mode allows on-demand tool discovery
4. At scale (100+ tools), code execution can save 80-95% of tool definition tokens

### Token Impact Analysis

**Traditional Mode with 100+ Tools**:
```
Library tools:     9 tools × 150 tokens =   1,350 tokens
Enterprise tools: 100 tools × 180 tokens = 18,000 tokens
System prompt:                              300 tokens
─────────────────────────────────────────────────────
Total context overhead:                   19,650 tokens
```

**Code Execution Mode with 100+ Tools**:
```
API function stubs:        200 tokens
Discovery functions:       150 tokens
System prompt:             300 tokens
─────────────────────────────────────
Total context overhead:    650 tokens
```

**Expected Reduction: 97% (19,650 → 650 tokens)**

### Enterprise Domain Categories

Based on real-world enterprise tool landscapes:

| Domain | Team | Tool Examples | Real-World Equivalent |
|--------|------|---------------|----------------------|
| Engineering | CI/CD | run_build, check_ci_status | GitHub Actions, Jenkins |
| Data Platform | Analytics | query_warehouse, get_lineage | Snowflake, dbt |
| Security | Compliance | scan_vulnerabilities, audit_logs | Snyk, Splunk |
| HR | People | get_employee_info, submit_pto | Workday, BambooHR |
| Finance | Accounting | get_budget, submit_expense | NetSuite, Expensify |
| Marketing | Campaigns | get_metrics, schedule_post | HubSpot, Hootsuite |
| Sales | CRM | get_lead, update_opportunity | Salesforce |
| Support | Service | create_ticket, search_kb | Zendesk, Confluence |
| Infrastructure | DevOps | check_status, scale_service | AWS, Kubernetes |
| ML Platform | AI/ML | train_model, deploy_model | MLflow, SageMaker |

### Implementation Strategy

**Mock Function Pattern**:
```python
def create_mock_function(domain: str, tool_name: str, description: str):
    """Create a mock function that returns realistic-looking data."""
    def mock_fn(**kwargs) -> dict:
        return {
            "success": True,
            "domain": domain,
            "tool": tool_name,
            "message": f"Mock response from {domain}.{tool_name}",
            "data": {"timestamp": datetime.now().isoformat()},
        }
    mock_fn.__doc__ = description
    return mock_fn
```

**Discovery Function Pattern** (Code Execution Mode):
```python
# Available at runtime in code execution sandbox
def list_available_tools() -> list[str]:
    """List all available tool names across domains."""
    return [t.name for t in get_all_tools()]

def get_tool_info(name: str) -> dict:
    """Get schema and description for a specific tool."""
    tool = find_tool(name)
    return {"name": tool.name, "description": tool.description, "parameters": tool.parameters}

def search_tools(query: str) -> list[str]:
    """Search tools by description similarity."""
    return [t.name for t in find_tools_by_description(query)]
```

### Alternatives Considered

- **50 tools**: Insufficient to demonstrate dramatic difference
- **200 tools**: Diminishing returns, unnecessary complexity
- **Real API integrations**: Too complex for learning, security concerns
- **Single domain**: Doesn't represent real enterprise diversity

### Success Metrics

1. Traditional mode: 15,000+ tokens for tool definitions
2. Code execution mode: < 2,000 tokens for tool definitions
3. Token reduction: 80%+ when dummy tools enabled
4. Query accuracy: Library queries still work correctly with dummy tools present
5. Performance: Tool discovery < 100ms

### References

- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Tool Use Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [MCP: Tool Discovery](https://modelcontextprotocol.io/docs/concepts/tools)

---

## Summary: Phase 7.5 Research Findings

| Question | Decision | Rationale |
|----------|----------|-----------|
| How many dummy tools? | 100 (10 domains × 10 tools) | Sufficient to demonstrate scale impact |
| What domains? | 10 enterprise teams | Realistic enterprise landscape |
| Mock vs real APIs? | Mock implementations | Simplicity, security, focus on token demo |
| How to enable? | CLI flag + make target | User control, easy testing |
| Expected token savings? | 80-95% | Based on Anthropic paper findings |
