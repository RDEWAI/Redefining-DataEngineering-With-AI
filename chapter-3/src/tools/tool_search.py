"""Tool search for dynamic tool discovery.

This module provides the ToolSearch class for finding tools using
name-based lookup or embedding-based semantic similarity search.

Example:
    >>> from src.tools.tool_search import ToolSearch
    >>> from src.tools.tool_registry import create_library_tool_registry
    >>> registry = create_library_tool_registry()
    >>> searcher = ToolSearch(registry)
    >>> tools = searcher.search_by_description("find books about programming")
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.rag.embeddings import EmbeddingGenerator
    from src.tools.tool_registry import ToolMetadata, ToolRegistry


class ToolSearch:
    """Search for tools using name or semantic similarity.

    Provides two search modes:
    1. Name-based: Exact or fuzzy matching on tool names
    2. Description-based: Semantic similarity using embeddings

    Args:
        registry: ToolRegistry to search within
        use_embeddings: Whether to enable embedding-based search

    Attributes:
        registry: The tool registry being searched
        embeddings: Dict mapping tool names to embedding vectors
    """

    def __init__(
        self,
        registry: "ToolRegistry",
        use_embeddings: bool = True,
    ) -> None:
        """Initialize tool search.

        Args:
            registry: ToolRegistry to search within
            use_embeddings: If True, generate embeddings for semantic search
        """
        self.registry = registry
        self.embeddings: dict[str, np.ndarray] = {}
        self._embedding_generator: EmbeddingGenerator | None = None

        if use_embeddings:
            self._initialize_embeddings()

    def _initialize_embeddings(self) -> None:
        """Generate embeddings for all tool descriptions."""
        try:
            from src.rag.embeddings import EmbeddingGenerator

            self._embedding_generator = EmbeddingGenerator()

            for tool in self.registry.list_tools():
                # Combine name and description for embedding
                text = f"{tool.name}: {tool.description}"
                embedding = self._embedding_generator.embed_text(text)
                self.embeddings[tool.name] = embedding

        except ImportError:
            # sentence-transformers not available
            pass

    def search_by_name(self, query: str) -> list["ToolMetadata"]:
        """Search tools by name (exact or partial match).

        Args:
            query: Search query for tool name

        Returns:
            List of matching ToolMetadata, sorted by match quality
        """
        query_lower = query.lower()
        matches: list[tuple[float, ToolMetadata]] = []

        for tool in self.registry.list_tools():
            name_lower = tool.name.lower()

            # Exact match gets highest score
            if name_lower == query_lower:
                matches.append((1.0, tool))
            # Prefix match
            elif name_lower.startswith(query_lower):
                matches.append((0.8, tool))
            # Contains match
            elif query_lower in name_lower:
                matches.append((0.6, tool))
            # Word overlap
            else:
                query_words = set(query_lower.split("_"))
                name_words = set(name_lower.split("_"))
                overlap = len(query_words & name_words)
                if overlap > 0:
                    score = 0.4 * (overlap / max(len(query_words), len(name_words)))
                    matches.append((score, tool))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches]

    def search_by_description(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple["ToolMetadata", float]]:
        """Search tools by semantic similarity to query.

        Uses embedding-based search to find tools whose descriptions
        are semantically similar to the query.

        Args:
            query: Natural language query
            top_k: Maximum number of results

        Returns:
            List of (ToolMetadata, similarity_score) tuples,
            sorted by similarity descending

        Raises:
            RuntimeError: If embeddings are not initialized
        """
        if not self.embeddings or self._embedding_generator is None:
            raise RuntimeError(
                "Embedding-based search not available. "
                "Ensure sentence-transformers is installed."
            )

        # Generate query embedding
        query_embedding = self._embedding_generator.embed_text(query)

        # Compute similarities
        similarities: list[tuple[str, float]] = []
        for tool_name, tool_embedding in self.embeddings.items():
            # Cosine similarity (embeddings are normalized)
            similarity = float(np.dot(query_embedding, tool_embedding))
            similarities.append((tool_name, similarity))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top_k results with metadata
        results: list[tuple[ToolMetadata, float]] = []
        for tool_name, score in similarities[:top_k]:
            tool = self.registry.get_tool(tool_name)
            if tool:
                results.append((tool, score))

        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_semantic: bool = True,
    ) -> list["ToolMetadata"]:
        """Search tools using combined name and semantic matching.

        Combines name-based and semantic search for best results.

        Args:
            query: Search query
            top_k: Maximum number of results
            use_semantic: Whether to use semantic search

        Returns:
            List of matching ToolMetadata
        """
        # Try name-based search first
        name_results = self.search_by_name(query)

        # If we have exact or good name matches, return those
        if name_results:
            return name_results[:top_k]

        # Fall back to semantic search
        if use_semantic and self.embeddings:
            try:
                semantic_results = self.search_by_description(query, top_k)
                return [tool for tool, _ in semantic_results]
            except RuntimeError:
                pass

        return []

    def get_tools_for_query(
        self,
        query: str,
        threshold: float = 0.3,
    ) -> list["ToolMetadata"]:
        """Get tools relevant to a natural language query.

        Useful for dynamic tool selection based on user queries.

        Args:
            query: User's natural language query
            threshold: Minimum similarity score to include

        Returns:
            List of relevant tools
        """
        if not self.embeddings:
            # Fall back to all tools
            return self.registry.list_tools()

        try:
            results = self.search_by_description(query, top_k=10)
            return [tool for tool, score in results if score >= threshold]
        except RuntimeError:
            return self.registry.list_tools()


def create_tool_search() -> ToolSearch:
    """Create a ToolSearch with the default library registry.

    Returns:
        ToolSearch configured with library tools
    """
    from src.tools.tool_registry import create_library_tool_registry

    registry = create_library_tool_registry()
    return ToolSearch(registry)
