"""Embedding generation for RAG semantic search.

This module provides the EmbeddingGenerator class for creating vector embeddings
from text using sentence-transformers models. These embeddings enable semantic
similarity search over book descriptions and lending data.

Example:
    >>> from src.agentic.rag.embeddings import EmbeddingGenerator
    >>> generator = EmbeddingGenerator()
    >>> embedding = generator.embed_text("A book about time travel")
    >>> embeddings = generator.embed_books(books)
    >>> embeddings = generator.embed_loans(loans_with_book_info)
"""

from typing import TYPE_CHECKING

import numpy as np
from sentence_transformers import SentenceTransformer

if TYPE_CHECKING:
    try:
        from library.domain import Book
        from library.lending_domain import Loan
    except ImportError:
        from src.agentic.library.domain import Book
        from src.agentic.library.lending_domain import Loan

# Default model: all-MiniLM-L6-v2
# - 384 dimensions
# - Fast inference
# - Good quality for semantic similarity
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIM = 384


def create_book_text_for_embedding(
    title: str,
    author: str,
    description: str,
    category: str,
) -> str:
    """Create text content for book embedding.

    Combines book metadata into a single text string optimized for
    semantic embedding. The description is the primary content, with
    title, author, and category providing context.

    Args:
        title: Book title
        author: Author name
        description: Book description/summary
        category: Book category

    Returns:
        Combined text string for embedding

    Example:
        >>> text = create_book_text_for_embedding(
        ...     title="Python Programming",
        ...     author="John Doe",
        ...     description="A guide to Python",
        ...     category="Programming"
        ... )
    """
    parts = [f"Title: {title}", f"Author: {author}"]

    if description:
        parts.append(f"Description: {description}")

    parts.append(f"Category: {category}")

    return " | ".join(parts)


def create_lending_text_for_embedding(
    loan: "Loan",
    book_title: str,
    book_author: str,
    book_category: str,
) -> str:
    """Create text content for lending embedding.

    Combines lending transaction data with book metadata into a single text string
    optimized for semantic embedding. This enables queries like "bulk corporate
    loans", "online lending", "waived fee programming books".

    Args:
        loan: Loan instance
        book_title: Title of the book lent
        book_author: Author of the book lent
        book_category: Category of the book lent

    Returns:
        Combined text string for embedding

    Example:
        >>> text = create_lending_text_for_embedding(
        ...     loan=loan,
        ...     book_title="Python Programming",
        ...     book_author="John Doe",
        ...     book_category="Programming"
        ... )
    """
    parts = []

    # Book context (links loan to book content)
    parts.append(f"Loan of '{book_title}' by {book_author}")
    parts.append(f"Book category: {book_category}")

    # Quantity context
    if loan.quantity > 1:
        parts.append(f"Bulk loan: {loan.quantity} copies")
    else:
        parts.append("Single copy loan")

    # Patron context
    parts.append(f"Patron segment: {loan.patron_segment.value}")

    # Geographic context
    parts.append(f"Region: {loan.region.value}")

    # Channel context
    parts.append(f"Channel: {loan.channel.value}")

    # Fee context
    if loan.has_fee_waiver:
        parts.append(f"Waived fee loan: {loan.fee_waiver}% waiver")
    else:
        parts.append("Full fee loan")

    # Temporal context
    month_name = loan.loan_date.strftime("%B %Y")
    parts.append(f"Date: {month_name}")

    return " | ".join(parts)


class EmbeddingGenerator:
    """Generate vector embeddings from text using sentence-transformers.

    This class wraps a sentence-transformers model to generate embeddings
    for books and queries. Embeddings are normalized for cosine similarity.

    Args:
        model_name: Name of sentence-transformers model to use.
            Defaults to "all-MiniLM-L6-v2" (384 dimensions).

    Attributes:
        model: The loaded SentenceTransformer model
        model_name: Name of the loaded model

    Example:
        >>> generator = EmbeddingGenerator()
        >>> embedding = generator.embed_text("Python programming guide")
        >>> print(embedding.shape)  # (384,)
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        """Initialize the embedding generator with a sentence-transformers model.

        Args:
            model_name: Name of the sentence-transformers model to load.
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model.

        Returns:
            Integer dimension of embedding vectors
        """
        dim = self.model.get_sentence_embedding_dimension()
        return int(dim) if dim is not None else DEFAULT_EMBEDDING_DIM

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text string.

        Args:
            text: Text to embed. If empty, returns zero vector.

        Returns:
            Numpy array of shape (dimension,) with normalized embedding
        """
        if not text:
            return np.zeros(DEFAULT_EMBEDDING_DIM, dtype=np.float32)

        embedding: np.ndarray = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple texts in batch.

        More efficient than calling embed_text() multiple times.

        Args:
            texts: List of texts to embed

        Returns:
            Numpy array of shape (len(texts), dimension) with normalized embeddings
        """
        if not texts:
            return np.zeros((0, DEFAULT_EMBEDDING_DIM), dtype=np.float32)

        embeddings: np.ndarray = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings

    def embed_book(self, book: "Book") -> np.ndarray:
        """Generate embedding for a single book.

        Uses the book's title, author, description, and category
        to create a combined text for embedding.

        Args:
            book: Book instance to embed

        Returns:
            Numpy array of shape (dimension,) with normalized embedding
        """
        text = create_book_text_for_embedding(
            title=book.title,
            author=book.author,
            description=book.description,
            category=book.category.value,
        )
        return self.embed_text(text)

    def embed_books(self, books: list["Book"]) -> np.ndarray:
        """Generate embeddings for multiple books in batch.

        Args:
            books: List of Book instances to embed

        Returns:
            Numpy array of shape (len(books), dimension) with normalized embeddings
        """
        texts = [
            create_book_text_for_embedding(
                title=book.title,
                author=book.author,
                description=book.description,
                category=book.category.value,
            )
            for book in books
        ]
        return self.embed_texts(texts)

    def embed_loan(
        self,
        loan: "Loan",
        book_title: str,
        book_author: str,
        book_category: str,
    ) -> np.ndarray:
        """Generate embedding for a single loan.

        Uses the loan's transaction data combined with book metadata
        to create a combined text for embedding.

        Args:
            loan: Loan instance to embed
            book_title: Title of the book lent
            book_author: Author of the book lent
            book_category: Category of the book lent

        Returns:
            Numpy array of shape (dimension,) with normalized embedding
        """
        text = create_lending_text_for_embedding(
            loan=loan,
            book_title=book_title,
            book_author=book_author,
            book_category=book_category,
        )
        return self.embed_text(text)

    def embed_loans(
        self,
        loans_with_book_info: list[tuple["Loan", str, str, str]],
    ) -> np.ndarray:
        """Generate embeddings for multiple loans in batch.

        Args:
            loans_with_book_info: List of tuples (Loan, book_title, book_author, book_category)

        Returns:
            Numpy array of shape (len(loans), dimension) with normalized embeddings
        """
        texts = [
            create_lending_text_for_embedding(
                loan=loan,
                book_title=title,
                book_author=author,
                book_category=category,
            )
            for loan, title, author, category in loans_with_book_info
        ]
        return self.embed_texts(texts)


def generate_all_embeddings() -> None:
    """Generate embeddings for all books in the library database.

    This is a CLI utility function called by `make generate-embeddings`.
    It loads all books from the database, generates embeddings, and
    stores them in the vector store.

    Raises:
        RuntimeError: If database is not accessible or no books found
    """
    from pathlib import Path

    from src.agentic.library.repository import BookRepository
    from src.agentic.rag.vector_store import DuckDBVectorStore

    # Paths relative to chapter-2/
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"

    if not db_path.exists():
        raise RuntimeError(f"Database not found at {db_path}. Run 'make load-data' first.")

    import duckdb

    # Use a single write connection for both reading and writing
    print("Loading books from database...")
    conn = duckdb.connect(str(db_path), read_only=False)
    repo = BookRepository(connection=conn)

    # Get all books (search with empty query)
    books = repo.search_books("", limit=1000)

    if not books:
        conn.close()
        raise RuntimeError("No books found in database. Run 'make load-data' first.")

    print(f"Found {len(books)} books")

    print("Initializing embedding generator...")
    generator = EmbeddingGenerator()

    print("Generating embeddings (this may take a moment)...")
    embeddings = generator.embed_books(books)

    print("Storing embeddings in vector store...")
    store = DuckDBVectorStore(connection=conn)
    book_ids = [book.book_id for book in books]
    store.store_embeddings(book_ids, embeddings)
    conn.close()

    print(f"Successfully generated and stored {len(books)} embeddings")


def generate_lending_embeddings() -> None:
    """Generate embeddings for all loans in the library database.

    This is a CLI utility function called by `make generate-lending-embeddings`.
    It loads all loans with their book info from the database, generates embeddings,
    and stores them in the lending vector store.

    Raises:
        RuntimeError: If database is not accessible or no loans found
    """
    from pathlib import Path

    from src.agentic.library.lending_repository import LendingRepository
    from src.agentic.library.repository import BookRepository
    from src.agentic.rag.vector_store import LendingVectorStore

    # Paths relative to chapter-2/
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"

    if not db_path.exists():
        raise RuntimeError(f"Database not found at {db_path}. Run 'make load-data' first.")

    import duckdb

    # Use a single write connection for both reading and writing
    print("Loading loans from database...")
    conn = duckdb.connect(str(db_path), read_only=False)
    book_repo = BookRepository(connection=conn)
    lending_repo = LendingRepository(connection=conn)

    # Get all loans
    loans = lending_repo.search_lending(limit=10000)

    if not loans:
        conn.close()
        raise RuntimeError(
            "No loans found in database. Run 'make load-data --include-lending' first."
        )

    print(f"Found {len(loans)} loans")

    # Build book info lookup
    print("Loading book information...")
    books = book_repo.search_books("", limit=1000)
    book_info = {book.book_id: (book.title, book.author, book.category.value) for book in books}

    # Prepare loans with book info
    loans_with_book_info = []
    for loan in loans:
        if loan.book_id in book_info:
            title, author, category = book_info[loan.book_id]
            loans_with_book_info.append((loan, title, author, category))

    print(f"Matched {len(loans_with_book_info)} loans with book information")

    print("Initializing embedding generator...")
    generator = EmbeddingGenerator()

    print("Generating lending embeddings (this may take a moment)...")
    embeddings = generator.embed_loans(loans_with_book_info)

    print("Storing lending embeddings in vector store...")
    store = LendingVectorStore(connection=conn)
    loan_ids = [loan.loan_id for loan, _, _, _ in loans_with_book_info]
    store.store_embeddings(loan_ids, embeddings)
    conn.close()

    print(f"Successfully generated and stored {len(loans_with_book_info)} lending embeddings")
