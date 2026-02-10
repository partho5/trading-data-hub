# src/app/data_sources/__init__.py
"""Data source registry."""

from typing import Type
from .base import BaseDataSource

# Registry: source_name -> source_class
_registry: dict[str, Type[BaseDataSource]] = {}


def register_source(source_class: Type[BaseDataSource]) -> Type[BaseDataSource]:
    """Decorator to register a data source."""
    _registry[source_class.name] = source_class
    return source_class


def get_source(name: str) -> BaseDataSource | None:
    """Get an instance of a registered source by name."""
    source_class = _registry.get(name)
    if source_class:
        return source_class()
    return None


def list_sources() -> list[str]:
    """List all registered source names."""
    return list(_registry.keys())


def get_source_info(name: str) -> dict | None:
    """Get info about a source (name and supported data types)."""
    source_class = _registry.get(name)
    if source_class:
        return {
            "name": source_class.name,
            "supported_data_types": source_class.supported_data_types,
        }
    return None


# Import sources to trigger registration
from . import yahoo_finance  # noqa: E402, F401
from . import finviz  # noqa: E402, F401
from . import alpha_vantage  # noqa: E402, F401
from . import cnn_sentiment  # noqa: E402, F401
from . import sec_edgar  # noqa: E402, F401
from . import reddit  # noqa: E402, F401
from . import benzinga  # noqa: E402, F401
