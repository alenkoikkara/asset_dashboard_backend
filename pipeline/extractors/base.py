from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pipeline.models.holding import AssetClass, BrokerName, Holding


class BaseExtractor(ABC):
    """One subclass per data source (broker, asset class, file format)."""

    @property
    @abstractmethod
    def broker(self) -> BrokerName: ...

    @property
    @abstractmethod
    def asset_class(self) -> AssetClass: ...

    @abstractmethod
    def extract(self) -> list[Holding]:
        """Return a list of Holding objects populated with position-level fields only.
        Enrichment fields (current_price, sector, ai_commentary, etc.) are left None."""
        ...

    def is_available(self) -> bool:
        """Return False if the data source file/credentials are missing."""
        return True
