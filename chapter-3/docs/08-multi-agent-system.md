# Multi-Agent System with A2A-Inspired Protocol

## Overview

Phase 8 implements a multi-agent system for the library management application. The system uses an A2A-inspired (Agent-to-Agent) in-process message passing protocol to coordinate multiple specialized agents.

## Architecture

```
                            User Query
                                │
                                ▼
                    ┌───────────────────────┐
                    │   OrchestratorAgent   │
                    │   ─────────────────   │
                    │   • Query classification
                    │   • Agent routing      │
                    │   • Result aggregation │
                    └───────────┬───────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │  SearchAgent  │   │ AnalyticsAgent│   │ Recommendation│
    │               │   │               │   │    Agent      │
    │ • Keyword     │   │ • Stats       │   │ • Suggestions │
    │ • Semantic    │   │ • Aggregations│   │ • Quality     │
    │ • Location    │   │ • Code exec   │   │   filtering   │
    └───────────────┘   └───────────────┘   └───────────────┘
```

## Components

### 1. A2A Protocol (`src/a2a/`)

#### QueryType Enum
Classifies user queries for routing:
- `SEARCH`: Book discovery and lookup
- `ANALYTICS`: Statistics, counts, aggregations
- `RECOMMENDATION`: Book suggestions with filters
- `MULTI_STEP`: Complex queries requiring multiple agents

#### AgentMessage Dataclass
Standard message format for agent communication:
```python
@dataclass
class AgentMessage:
    id: str              # Unique message ID
    sender: str          # Sending agent name
    recipient: str       # Receiving agent name
    query_type: QueryType
    content: Any         # Message payload
    context: dict        # Additional context
    status: AgentStatus  # pending/completed/failed
    parent_id: str       # For response chains
```

#### MessageRouter
In-process router for message delivery:
```python
router = MessageRouter()
router.register_agent(search_agent)
router.register_agent(analytics_agent)

response = router.route(message)
```

### 2. Specialized Agents

#### SearchAgent
Handles book discovery using keyword and semantic search.

**Capabilities**:
- `search_books()` - Keyword-based search
- `semantic_search()` - Natural language similarity
- `get_book_details()` - Detailed book info
- `locate_book()` - Physical location

**Auto-detection**: Chooses semantic search for queries with "about", "like", "similar to".

#### AnalyticsAgent
Handles statistics and reporting queries.

**Capabilities**:
- `get_library_stats()` - Overall statistics
- `list_by_category()` - Category breakdown
- `list_by_status()` - Status distribution
- `execute_custom_analytics()` - Code execution for complex queries

#### RecommendationAgent
Provides quality-filtered book suggestions.

**Capabilities**:
- Availability filtering (require Present status)
- Signal strength filtering (avoid weak RFID < -55 dBm)
- Semantic similarity for "similar to" queries
- Recommendation reasons for transparency

### 3. OrchestratorAgent

Central coordinator that:
1. **Classifies queries** using heuristic rules
2. **Routes to agents** based on classification
3. **Handles multi-step** queries by coordinating multiple agents
4. **Aggregates results** into formatted responses

**Classification Rules**:
```python
# Multi-step indicators
"and", "then", "which are", "and tell me"

# Recommendation indicators
"recommend", "suggest", "should I read"

# Analytics indicators
"how many", "statistics", "top N", "average"

# Default: SEARCH
```

## Usage

### CLI
```bash
# Start multi-agent system
make multi-agent

# Run tests
make test-multi-agent
```

### Python API
```python
from src.agentic.agents import OrchestratorAgent

# Initialize
orchestrator = OrchestratorAgent()

# Query
result = orchestrator.query("Find Python books that are available")

# Access results
print(result["response"])
print(result["data"])
```

### Example Queries

**Search Query**: "Find programming books" routes to SearchAgent

**Analytics Query**: "How many books are missing?" routes to AnalyticsAgent

**Recommendation Query**: "Recommend fiction books" routes to RecommendationAgent

**Multi-Step Query**: "Find Python books and show which are available" coordinates SearchAgent then RecommendationAgent

## Testing

```bash
# Run all multi-agent tests
make test-multi-agent

# Run specific test files
uv run pytest tests/unit/test_protocol.py -v
uv run pytest tests/unit/test_agents.py -v
uv run pytest tests/integration/test_multi_agent.py -v
```

## File Structure

```
chapter-3/src/
├── a2a/
│   ├── __init__.py      # Package exports
│   ├── protocol.py      # QueryType, AgentMessage, AgentStatus
│   └── server.py        # MessageRouter
└── agents/
    ├── search_agent.py         # SearchAgent
    ├── analytics_agent.py      # AnalyticsAgent
    ├── recommendation_agent.py # RecommendationAgent
    └── orchestrator_agent.py   # OrchestratorAgent + CLI
```

## Design Decisions

1. **In-Process Communication**: Uses function calls instead of HTTP for simplicity
2. **Heuristic Classification**: Pattern matching for query routing (no LLM required)
3. **Quality Filtering**: RecommendationAgent filters by availability and signal strength
4. **Lazy Initialization**: Embedding models loaded only when needed
5. **Transparent Routing**: Shows routing decisions to help users understand the system