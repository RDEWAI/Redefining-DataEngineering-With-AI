"""Simple RAG Demo - Minimal Retrieval-Augmented Generation Example.

This module demonstrates the fundamental concept of RAG:
- Without context: LLM cannot answer questions about private/specific data
- With context (RAG): LLM can answer accurately using retrieved information

The demo uses a small, fictional library dataset that the LLM has never seen,
proving that the answers come from the retrieved context, not training data.
"""

import os
from dataclasses import dataclass

# =============================================================================
# SAMPLE LIBRARY DATA (Private data the LLM has never seen)
# =============================================================================

LIBRARY_BOOKS = [
    {
        "id": "XYZ-001",
        "title": "The Quantum Garden",
        "author": "Dr. Elena Voss",
        "year": 2023,
        "genre": "Science Fiction",
        "available": True,
        "location": "Shelf A3",
        "summary": "A physicist discovers that her garden exists in multiple quantum states, "
                   "leading to adventures across parallel realities.",
    },
    {
        "id": "XYZ-002",
        "title": "Midnight in Mumbai",
        "author": "Raj Krishnamurthy",
        "year": 2022,
        "genre": "Mystery",
        "available": False,
        "location": "Shelf B7",
        "summary": "Detective Ananya Sharma investigates a series of art thefts that only "
                   "occur during power outages in Mumbai's wealthiest neighborhoods.",
    },
    {
        "id": "XYZ-003",
        "title": "The Last Algorithm",
        "author": "Marcus Chen",
        "year": 2024,
        "genre": "Thriller",
        "available": True,
        "location": "Shelf C2",
        "summary": "A rogue AI researcher must stop his own creation before it rewrites "
                   "the global financial system.",
    },
    {
        "id": "XYZ-004",
        "title": "Echoes of the Silk Road",
        "author": "Dr. Fatima Al-Hassan",
        "year": 2021,
        "genre": "Historical Fiction",
        "available": True,
        "location": "Shelf D5",
        "summary": "Following a young merchant's journey along the ancient Silk Road, "
                   "discovering secrets that connect East and West.",
    },
    {
        "id": "XYZ-005",
        "title": "Bioluminescence",
        "author": "Dr. Yuki Tanaka",
        "year": 2023,
        "genre": "Science",
        "available": False,
        "location": "Shelf E1",
        "summary": "An exploration of organisms that produce their own light, from deep-sea "
                   "creatures to fireflies, with stunning photography.",
    },
]


# =============================================================================
# SIMPLE RAG IMPLEMENTATION
# =============================================================================


@dataclass
class RetrievalResult:
    """Result from retrieving relevant context."""
    query: str
    matched_books: list[dict]
    context: str


class LibraryRAG:
    """Simple RAG system for library book queries.

    This demonstrates the core RAG pattern:
    1. Retrieve: Find relevant documents based on the query
    2. Augment: Add retrieved context to the prompt
    3. Generate: LLM generates answer using the context
    """

    def __init__(self, books: list[dict] | None = None):
        """Initialize with library data.

        Args:
            books: List of book dictionaries. Uses sample data if None.
        """
        self.books = books or LIBRARY_BOOKS
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            from openai import OpenAI

            base_url = os.getenv("LLM_BASE_URL")
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

            if not base_url or not api_key:
                raise ValueError(
                    "Please set LLM_BASE_URL and LLM_API_KEY (or OPENROUTER_API_KEY) "
                    "environment variables. See .env.example for details."
                )

            self._llm_client = OpenAI(base_url=base_url, api_key=api_key)
        return self._llm_client

    def retrieve(self, query: str) -> RetrievalResult:
        """Retrieve relevant books based on query (simple keyword matching).

        In a production system, this would use embeddings and vector search.
        Here we use simple keyword matching for demonstration.

        Args:
            query: User's question

        Returns:
            RetrievalResult with matched books and formatted context
        """
        query_lower = query.lower()
        matched = []

        for book in self.books:
            # Simple relevance check: look for keywords in book fields
            searchable = f"{book['title']} {book['author']} {book['genre']} {book['summary']}".lower()

            # Check if any query words appear in the book
            query_words = query_lower.split()
            if any(word in searchable for word in query_words if len(word) > 2):
                matched.append(book)

        # If no keyword matches, return all books as context
        if not matched:
            matched = self.books

        # Format context for LLM
        context_parts = ["LIBRARY DATABASE:"]
        for book in matched:
            status = "Available" if book["available"] else "Checked Out"
            context_parts.append(
                f"\n- {book['title']} (ID: {book['id']})"
                f"\n  Author: {book['author']}"
                f"\n  Year: {book['year']}, Genre: {book['genre']}"
                f"\n  Status: {status}, Location: {book['location']}"
                f"\n  Summary: {book['summary']}"
            )

        return RetrievalResult(
            query=query,
            matched_books=matched,
            context="\n".join(context_parts)
        )

    def query_without_rag(self, question: str) -> str:
        """Query LLM WITHOUT any context (no RAG).

        This demonstrates what happens when the LLM doesn't have access
        to the private library data.
        """
        client = self._get_llm_client()
        model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful library assistant. Answer questions about books. "
                               "If you don't have specific information, say so clearly."
                },
                {"role": "user", "content": question}
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message.content

    def query_with_rag(self, question: str) -> tuple[str, RetrievalResult]:
        """Query LLM WITH retrieved context (RAG enabled).

        This demonstrates the power of RAG: the LLM can now answer
        questions about the private library data.

        Returns:
            Tuple of (answer, retrieval_result)
        """
        # Step 1: Retrieve relevant context
        retrieval = self.retrieve(question)

        # Step 2: Augment prompt with context
        client = self._get_llm_client()
        model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a helpful library assistant. Use ONLY the following "
                               f"library database to answer questions. If the answer is not in "
                               f"the database, say so.\n\n{retrieval.context}"
                },
                {"role": "user", "content": question}
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message.content, retrieval


# =============================================================================
# DEMO RUNNER
# =============================================================================


def run_demo():
    """Run the RAG demonstration.

    Shows the difference between querying with and without RAG.
    """
    print("=" * 70)
    print("SIMPLE RAG DEMO: Library Book Assistant")
    print("=" * 70)
    print()
    print("This demo shows how RAG (Retrieval-Augmented Generation) enables")
    print("an LLM to answer questions about PRIVATE data it has never seen.")
    print()
    print("We have a small library with 5 fictional books that don't exist")
    print("in the LLM's training data. Watch how RAG makes the difference!")
    print()

    # Initialize RAG system
    rag = LibraryRAG()

    # Demo questions that require knowledge of our private library data
    questions = [
        "Who wrote 'The Quantum Garden' and what is it about?",
        "Which books are currently available in the library?",
        "Tell me about the book by Marcus Chen.",
    ]

    for i, question in enumerate(questions, 1):
        print("=" * 70)
        print(f"QUESTION {i}: {question}")
        print("=" * 70)

        # WITHOUT RAG
        print("\n[WITHOUT RAG] - LLM has no access to library data:")
        print("-" * 50)
        try:
            answer_no_rag = rag.query_without_rag(question)
            print(answer_no_rag)
        except Exception as e:
            print(f"Error: {e}")

        # WITH RAG
        print("\n[WITH RAG] - LLM uses retrieved library context:")
        print("-" * 50)
        try:
            answer_with_rag, retrieval = rag.query_with_rag(question)
            print(f"Retrieved {len(retrieval.matched_books)} relevant book(s)")
            print()
            print(answer_with_rag)
        except Exception as e:
            print(f"Error: {e}")

        print()

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("1. WITHOUT RAG: LLM cannot answer about private/unknown data")
    print("2. WITH RAG: LLM accurately answers using retrieved context")
    print("3. RAG = Retrieve relevant docs + Augment prompt + Generate answer")
    print()


def interactive_mode():
    """Run interactive Q&A mode."""
    print("=" * 70)
    print("INTERACTIVE RAG DEMO")
    print("=" * 70)
    print()
    print("Available books in our library:")
    for book in LIBRARY_BOOKS:
        status = "Available" if book["available"] else "Checked Out"
        print(f"  - {book['title']} by {book['author']} [{status}]")
    print()
    print("Ask questions about these books! Type 'quit' to exit.")
    print("Use '/norag' prefix to query without RAG context.")
    print()

    rag = LibraryRAG()

    while True:
        try:
            question = input("You: ").strip()
            if not question:
                continue
            if question.lower() in ('quit', 'exit', '/quit'):
                print("Goodbye!")
                break

            use_rag = True
            if question.startswith('/norag '):
                use_rag = False
                question = question[7:]

            if use_rag:
                answer, retrieval = rag.query_with_rag(question)
                print(f"\n[RAG: Retrieved {len(retrieval.matched_books)} book(s)]")
            else:
                answer = rag.query_without_rag(question)
                print("\n[NO RAG: No context provided]")

            print(f"Assistant: {answer}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run_demo()
