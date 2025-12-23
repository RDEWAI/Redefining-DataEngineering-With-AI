"""Unit tests for embedding generation.

Tests the EmbeddingGenerator class for creating vector embeddings
from book text data using sentence-transformers.
"""

from unittest.mock import MagicMock, patch

import numpy as np


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class."""

    def test_init_with_default_model(self) -> None:
        """Test initialization with default model name."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        # Mock the SentenceTransformer to avoid loading actual model
        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()

            mock_st.assert_called_once_with("all-MiniLM-L6-v2")
            assert generator.model == mock_model
            assert generator.model_name == "all-MiniLM-L6-v2"

    def test_init_with_custom_model(self) -> None:
        """Test initialization with custom model name."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(model_name="paraphrase-MiniLM-L6-v2")

            mock_st.assert_called_once_with("paraphrase-MiniLM-L6-v2")
            assert generator.model_name == "paraphrase-MiniLM-L6-v2"

    def test_embed_text_single_string(self) -> None:
        """Test embedding a single text string."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Return a 384-dimensional vector (all-MiniLM-L6-v2 dimension)
            mock_model.encode.return_value = np.array([0.1] * 384)
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            embedding = generator.embed_text("Hello, world!")

            mock_model.encode.assert_called_once_with(
                "Hello, world!", convert_to_numpy=True, normalize_embeddings=True
            )
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (384,)

    def test_embed_text_empty_string(self) -> None:
        """Test embedding an empty string returns zero vector."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            embedding = generator.embed_text("")

            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (384,)
            assert np.allclose(embedding, np.zeros(384))

    def test_embed_texts_batch(self) -> None:
        """Test batch embedding multiple texts."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Return 3 embeddings for 3 texts
            mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384, [0.3] * 384])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            texts = ["Text 1", "Text 2", "Text 3"]
            embeddings = generator.embed_texts(texts)

            mock_model.encode.assert_called_once_with(
                texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True
            )
            assert isinstance(embeddings, np.ndarray)
            assert embeddings.shape == (3, 384)

    def test_embed_texts_empty_list(self) -> None:
        """Test batch embedding with empty list."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            embeddings = generator.embed_texts([])

            assert isinstance(embeddings, np.ndarray)
            assert embeddings.shape == (0, 384)

    def test_get_embedding_dimension(self) -> None:
        """Test getting embedding dimension."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            dimension = generator.get_embedding_dimension()

            assert dimension == 384


class TestBookEmbeddings:
    """Tests for book-specific embedding functions."""

    def test_create_book_text_for_embedding(self) -> None:
        """Test creating text content for book embedding."""
        from src.agentic.rag.embeddings import create_book_text_for_embedding

        # Test with full book info
        text = create_book_text_for_embedding(
            title="Python Programming",
            author="John Doe",
            description="A comprehensive guide to Python programming.",
            category="Programming",
        )

        assert "Python Programming" in text
        assert "John Doe" in text
        assert "comprehensive guide" in text
        assert "Programming" in text

    def test_create_book_text_minimal(self) -> None:
        """Test creating text with minimal info (no description)."""
        from src.agentic.rag.embeddings import create_book_text_for_embedding

        text = create_book_text_for_embedding(
            title="Mystery Novel",
            author="Jane Smith",
            description="",
            category="Fiction",
        )

        assert "Mystery Novel" in text
        assert "Jane Smith" in text
        assert "Fiction" in text

    def test_embed_book(self) -> None:
        """Test embedding a single book."""
        from datetime import datetime

        from src.agentic.library.domain import Book, BookStatus, Category, Location
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.5] * 384)
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()

            book = Book(
                book_id="B001",
                title="Python Programming",
                author="John Doe",
                description="A comprehensive guide to Python.",
                category=Category.PROGRAMMING,
                location=Location(cabinet=1, rack=2, row=3),
                signal_strength=-45.0,
                timestamp=datetime.now(),
                status=BookStatus.PRESENT,
            )

            embedding = generator.embed_book(book)

            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (384,)

    def test_embed_books_batch(self) -> None:
        """Test embedding multiple books in batch."""
        from datetime import datetime

        from src.agentic.library.domain import Book, BookStatus, Category, Location
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.5] * 384, [0.6] * 384])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()

            books = [
                Book(
                    book_id="B001",
                    title="Python Programming",
                    author="John Doe",
                    description="A comprehensive guide to Python.",
                    category=Category.PROGRAMMING,
                    location=Location(cabinet=1, rack=2, row=3),
                    signal_strength=-45.0,
                    timestamp=datetime.now(),
                    status=BookStatus.PRESENT,
                ),
                Book(
                    book_id="B002",
                    title="Time Travel Adventures",
                    author="Jane Smith",
                    description="An exciting story about time travel.",
                    category=Category.FICTION,
                    location=Location(cabinet=2, rack=1, row=1),
                    signal_strength=-50.0,
                    timestamp=datetime.now(),
                    status=BookStatus.PRESENT,
                ),
            ]

            embeddings = generator.embed_books(books)

            assert isinstance(embeddings, np.ndarray)
            assert embeddings.shape == (2, 384)


class TestEmbeddingNormalization:
    """Tests for embedding normalization."""

    def test_embeddings_are_normalized(self) -> None:
        """Test that embeddings are L2-normalized."""
        from src.agentic.rag.embeddings import EmbeddingGenerator

        with patch("src.agentic.rag.embeddings.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Return a normalized vector (L2 norm = 1)
            normalized_vec = np.array([0.5, 0.5, 0.5, 0.5])
            normalized_vec = normalized_vec / np.linalg.norm(normalized_vec)
            mock_model.encode.return_value = np.pad(normalized_vec, (0, 380))
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator()
            _ = generator.embed_text("test")

            # Verify the encoded call requested normalization
            mock_model.encode.assert_called_once()
            call_kwargs = mock_model.encode.call_args[1]
            assert call_kwargs.get("normalize_embeddings") is True


class TestEmbeddingDimension:
    """Tests for embedding dimension constants."""

    def test_default_dimension_constant(self) -> None:
        """Test default embedding dimension is 384."""
        from src.agentic.rag.embeddings import DEFAULT_EMBEDDING_DIM

        assert DEFAULT_EMBEDDING_DIM == 384

    def test_default_model_constant(self) -> None:
        """Test default model name constant."""
        from src.agentic.rag.embeddings import DEFAULT_MODEL_NAME

        assert DEFAULT_MODEL_NAME == "all-MiniLM-L6-v2"
