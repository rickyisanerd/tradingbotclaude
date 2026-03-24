"""Base class for signal sources."""

from abc import ABC, abstractmethod


class SignalSource(ABC):
    name: str = "base"
    ttl_hours: int = 4

    @abstractmethod
    def fetch(self, symbol: str | None = None) -> dict:
        """Fetch signal data. If symbol is None, fetch global data."""
        ...

    @abstractmethod
    def cache_key(self, symbol: str | None = None) -> str:
        """Return the cache key for this signal/symbol combo."""
        ...
