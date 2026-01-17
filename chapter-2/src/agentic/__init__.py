"""Agentic package for AI Engineering with Library Management.

This package contains all components for building intelligent library assistants:
- agents: AI agents for library management
- a2a: Agent-to-Agent communication protocol
- code_execution: Sandboxed code execution
- library: Domain models and repository
- llm: LLM provider abstraction layer
- mcp_servers: Model Context Protocol servers
- rag: RAG components for semantic search
- tools: Tool registry and management
"""

__version__ = "0.1.0"

__all__ = [
    "a2a",
    "agents",
    "code_execution",
    "library",
    "llm",
    "mcp_servers",
    "rag",
    "tools",
    "logging_config",
]
