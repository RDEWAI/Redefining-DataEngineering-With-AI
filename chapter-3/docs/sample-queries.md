# Sample Queries for Chapter 3 Sub-Features

This document provides example queries for each sub-feature to help you test and explore the library management AI system.

## 003a: Library Data Infrastructure

Test basic data queries using Python:

```python
import duckdb

conn = duckdb.connect('data/duckdb/chapter3.db')

# Count all books
conn.execute("SELECT COUNT(*) FROM library.books").fetchone()
# Expected: (200,)

# Books by category
conn.execute("""
    SELECT category, COUNT(*) as count
    FROM library.books
    GROUP BY category
""").fetchall()

# Missing books
conn.execute("""
    SELECT title, author, cabinet, rack, row
    FROM library.books
    WHERE status = 'Missing'
""").fetchall()

# Weak signal books (need RFID maintenance)
conn.execute("""
    SELECT title, signal_strength, status
    FROM library.books
    WHERE signal_strength < -55
    ORDER BY signal_strength ASC
""").fetchall()
```

## 003b: MCP Server

After starting the MCP server (`make mcp-server`), test with MCP Inspector (`make mcp-dev`):

**Tool Calls:**
- `search_books(query="Python", category="Programming")`
- `get_book_details(book_id="B001")`
- `check_availability(book_id="B001")`
- `list_by_category(category="Fiction", limit=5)`
- `list_by_status(status="Missing")`
- `locate_book(book_id="B001")`
- `find_books_in_cabinet(cabinet=1, rack=2)`
- `get_weak_signal_books(threshold=-55)`

**Resource URIs:**
- `library://stats`
- `library://missing_books`
- `library://location_map`

## 003c: Traditional Tool Use (Library Assistant)

Start with `make assistant` and try these queries:

### Basic Search Queries
```
> What programming books are available?
> Show me books by John Smith
> Find all Python programming books
> Search for books about data science
```

### Availability Queries
```
> Which books are missing?
> How many books are checked out?
> Show me available fiction books
> What books are present in cabinet 1?
```

### Location Queries
```
> Where is book B001 located?
> Find all books in cabinet 2, rack 3
> Show me books in the first cabinet
```

### Statistics Queries
```
> Get library statistics
> How many books are in each category?
> What's the breakdown by status?
```

### Complex Queries (Multi-Tool)
```
> Show me the available thriller books from the author who has the most books
> Find programming books with weak signal that need maintenance
> Which cabinets have the most missing books?
```

## 003d: Code Execution Mode

Start with `make assistant-enhanced` (defaults to code execution mode):

### Data Analysis Queries
```
> Show top 5 categories by missing books with average signal strength
> Create a bar chart showing book distribution by status
> Analyze the correlation between signal strength and book status
> Calculate the percentage of available books per category
```

### Aggregation Queries
```
> For each category, show count, how many are missing, and average signal
> Find the cabinets with the most books and their status breakdown
> Calculate availability rate by location (cabinet/rack)
```

### Comparison Queries
Compare token usage between modes:
```bash
make compare-modes
```

Try the same query in both modes:
```
> Show the distribution of books by status and calculate percentages
```

Traditional mode: Multiple tool calls
Code execution: Single Python script

## 003e: Semantic Search (RAG)

Enable RAG mode with `make assistant-rag` or start assistant and use `/rag` command:

### Natural Language Queries
```
> that book about time travel
> something about Python programming
> adventure stories in fiction
> books similar to detective mysteries
> technical books for beginners
```

### Conceptual Queries
```
> books about artificial intelligence
> stories set in space
> historical fiction about wars
> self-improvement books
> thriller novels with plot twists
```

### Hybrid Queries (Semantic + Structured)
```
> Find available books about machine learning
> Show me fiction books similar to mystery novels that are present
> Search for programming tutorials that are not checked out
```

## 003f: Multi-Agent System

Start with `make multi-agent`:

### Search Agent Queries
```
> Find all available programming books
> Search for books by popular authors
> Locate the fiction section books
```

### Analytics Agent Queries
```
> How many books are missing? Show breakdown by category
> Generate a report on library health by signal strength
> What's the availability rate across different cabinets?
```

### Recommendation Agent Queries
```
> Recommend a programming book with good signal
> Suggest available fiction books avoiding weak signal ones
> Find the best thriller to read right now
```

### Multi-Step Queries (Orchestrator)
```
> Find available programming books and recommend one with good signal
> Search for fiction books, analyze their availability, and suggest the best option
> How many books are missing? Then recommend some available alternatives from the same category
> Generate a library health report and identify areas needing attention
```

### Complex Analysis Queries
```
> Compare availability rates between programming and fiction categories
> Find patterns in missing books - are they clustered by location?
> Which authors have the most available books and their average signal strength?
```

## Enterprise Scale Demo

Test with 100 enterprise dummy tools enabled:

```bash
# Start traditional mode with dummy tools
make assistant-dummy-tools

# Start code execution mode with dummy tools
make assistant-code-dummy-tools

# Run automated comparison
make compare-modes-enterprise-all
```

The library queries work the same, but you can observe:
- Traditional mode loads 108 tool definitions (8 library + 100 dummy)
- Code execution mode uses compact API stubs
- 80%+ token reduction at enterprise scale

## Tips for Effective Queries

1. **Be specific**: "Find Python programming books" is better than "find books"
2. **Use natural language for RAG**: "books about time travel" leverages semantic search
3. **Combine criteria**: "available thriller books with good signal in cabinet 1"
4. **For analytics, describe the output**: "Show a breakdown by category with counts and percentages"
5. **For multi-agent, state your goal**: "Find and recommend" triggers multiple agents

## Commands Reference

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/settings` | Show current configuration |
| `/tools` | Toggle tool call display |
| `/stats` | Show token usage statistics |
| `/rag` | Toggle RAG/semantic search |
| `/mode` | Switch between traditional/code execution (enhanced mode) |
| `/dummy-tools` | Toggle enterprise dummy tools |
| `/reset` | Clear conversation history |
| `/quit` | Exit assistant |
