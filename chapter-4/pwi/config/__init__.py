"""Configuration management for Planning with Intent.

This module provides Pydantic schemas for configuration validation
and YAML configuration loading.
"""

from pwi.config.loader import load_config
from pwi.config.schema import PWIConfig

__all__ = ["PWIConfig", "load_config"]
