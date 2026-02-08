# src/app/data_sources/base.py
"""Base class for all data sources."""

from abc import ABC, abstractmethod
from typing import Any


class BaseDataSource(ABC):
    """Base class that all data sources must inherit."""

    name: str = ""
    supported_data_types: list[str] = []

    @abstractmethod
    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """
        Fetch data from the source.

        Args:
            data_type: Type of data to fetch (e.g., 'quote', 'chart')
            ticker: Single ticker or list of tickers
            params: Additional parameters specific to data type
            request: FastAPI Request object (optional, for context like base_url)

        Returns:
            Dict with 'success', 'data', and optionally 'errors'
        """
        pass

    def supports(self, data_type: str) -> bool:
        """Check if this source supports the given data type."""
        return data_type in self.supported_data_types
