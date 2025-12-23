# 01 - Data Infrastructure

**Sub-feature**: 003a - Library Data Infrastructure
**GitHub Issue**: #16

## Overview

This document covers the library data infrastructure setup, including:
- DuckDB database creation
- CSV data loading
- Domain model implementation
- Repository pattern for queries

## Quick Start

```bash
# From chapter-3 directory
cd chapter-3

# Install dependencies
make dev-setup

# Load library data into DuckDB
make load-data

# Verify data loaded correctly
make verify-data
```

## Data Model

### Library Schema

The library data uses DuckDB with a `library` schema containing the `books` table:

```sql
CREATE TABLE library.books (
    book_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    description VARCHAR NOT NULL,  -- 50-100 word book summary for RAG
    category VARCHAR NOT NULL,
    cabinet INTEGER NOT NULL,
    rack INTEGER NOT NULL,
    row INTEGER NOT NULL,
    signal_strength FLOAT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL
);
```

### Domain Classes

The domain layer provides Python dataclasses for type-safe book handling:

```python
from src.agentic.library import Book, BookStatus, Category, Location

# Create a book
book = Book(
    book_id="B001",
    title="Python Programming",
    author="John Smith",
    description="Master Python programming through this comprehensive guide covering data structures, algorithms, and best practices.",
    category=Category.PROGRAMMING,
    location=Location(cabinet=3, rack=2, row=5),
    signal_strength=-45.2,
    timestamp=datetime.now(),
    status=BookStatus.PRESENT,
)

# Check properties
print(book.has_weak_signal)  # False (signal > -55)
print(book.is_available)     # True (status is Present)
```

### Enumerations

**BookStatus**:
- `PRESENT` - Book is on shelf and detectable
- `MISSING` - Book cannot be located
- `CHECKED_OUT` - Book is borrowed

**Category**:
- `PROGRAMMING`
- `HISTORY`
- `SCIENCE`
- `FICTION`
- `THRILLER`

### Domain Invariants

| Invariant | Condition | Description |
|-----------|-----------|-------------|
| Weak Signal | `signal_strength < -55` | RFID maintenance needed |
| Missing Book | `status = 'Missing'` | Book cannot be located |
| Available | `status = 'Present'` | Book can be checked out |

## Repository Pattern

The `BookRepository` class provides all database operations:

```python
from src.agentic.library import BookRepository, Category, BookStatus

# Create repository
repo = BookRepository(db_path="data/duckdb/library.db")

# Search books
books = repo.search_books("Python", category=Category.PROGRAMMING)

# Get specific book
book = repo.get_book_by_id("B001")

# List by category or status
programming_books = repo.list_by_category(Category.PROGRAMMING)
missing_books = repo.list_by_status(BookStatus.MISSING)

# Get books with weak RFID signal
weak_signal = repo.get_weak_signal_books(threshold=-55)

# Find books by location
cabinet_3_books = repo.find_books_in_cabinet(cabinet=3, rack=2)

# Get library statistics
stats = repo.get_library_stats()
```

### Repository Methods

| Method | Description |
|--------|-------------|
| `search_books(query, category, limit)` | Search by title/author |
| `get_book_by_id(book_id)` | Get specific book |
| `list_by_category(category, status)` | List by category |
| `list_by_status(status, category)` | List by status |
| `get_weak_signal_books(threshold)` | Find weak RFID signals |
| `find_books_in_cabinet(cabinet, rack)` | Find by location |
| `get_library_stats()` | Get aggregate statistics |

## Tool Functions

The `tools.py` module wraps repository methods for LLM tool calling:

```python
from src.agentic.library import search_books, get_book_details, check_availability

# All functions return structured dictionaries
result = search_books("Python", category="Programming")
# {
#   "success": True,
#   "count": 3,
#   "books": [...],
#   "message": "Found 3 book(s) matching 'Python' in Programming"
# }

details = get_book_details("B001")
# {
#   "success": True,
#   "book": {...},
#   "message": "Found book: Python Programming by John Smith"
# }

availability = check_availability("B001")
# {
#   "success": True,
#   "available": True,
#   "status": "Present",
#   "location": "Cabinet 3, Rack 2, Row 5",
#   "message": "'Python Programming' is available at Cabinet 3, Rack 2, Row 5"
# }
```

### Available Tools

| Tool | Description |
|------|-------------|
| `search_books` | Search by title/author |
| `get_book_details` | Get complete book details |
| `check_availability` | Check if book is available |
| `list_by_category` | List books in category |
| `list_by_status` | List books by status |
| `locate_book` | Get book location |
| `find_books_in_cabinet` | Find books by cabinet |
| `get_weak_signal_books` | Find weak RFID signals |
| `get_library_stats` | Get library statistics |

## Data Loading

### CSV Format

The source CSV file (`data/raw/library/library_dataset_random.csv`) has the following columns:

| Column | Type | Description |
|--------|------|-------------|
| Book_ID | string | Unique identifier (B001, B002, ...) |
| Title | string | Book title |
| Author | string | Author name |
| Description | string | Book summary (50-100 words for RAG embeddings) |
| Category | string | One of: Programming, History, Science, Fiction, Thriller |
| Cabinet | int | Cabinet number (≥1) |
| Rack | int | Rack within cabinet (≥1) |
| Row | int | Row within rack (≥1) |
| Signal_Strength | float | RFID signal in dBm |
| Timestamp | datetime | Last RFID scan time |
| Status | string | Present, Missing, or Checked Out |

### Loading Script

```bash
# Load with default paths
python scripts/load_library_csv_to_duckdb.py

# Custom paths
python scripts/load_library_csv_to_duckdb.py \
    --db-path data/duckdb/custom.db \
    --csv-path /path/to/custom.csv
```

The script:
1. Creates the `library` schema
2. Creates the `books` table with constraints
3. Loads CSV data with column mapping
4. Creates indexes for common queries
5. Validates data integrity
6. Prints summary statistics

## Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration
```

### Test Coverage

- **Unit tests** (`tests/unit/`):
  - `test_domain.py` - Domain class tests
  - `test_repository.py` - Repository tests with in-memory DB

- **Integration tests** (`tests/integration/`):
  - `test_data_load.py` - End-to-end CSV loading tests

## File Structure

```
chapter-3/
├── data/
│   ├── raw/library/
│   │   └── library_dataset_random.csv
│   └── duckdb/
│       └── library.db
├── src/library/
│   ├── __init__.py
│   ├── domain.py      # Domain classes
│   ├── repository.py  # DuckDB repository
│   └── tools.py       # Tool functions
├── scripts/
│   └── load_library_csv_to_duckdb.py
└── tests/
    ├── unit/
    │   ├── test_domain.py
    │   └── test_repository.py
    └── integration/
        └── test_data_load.py
```

## Next Steps

After completing the data infrastructure setup:

1. **MCP Server** (003b) - Expose tools as MCP endpoints
2. **Library Assistant** (003c) - Build traditional tool-calling agent
3. **Code Execution** (003d) - Add sandboxed analytics
4. **RAG** (003e) - Semantic search over books
5. **Multi-Agent** (003f) - Orchestrated agent system
