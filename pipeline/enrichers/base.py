from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.models.holding import Holding


class BaseEnricher(ABC):
    """Receives the full holdings list, returns an enriched copy."""

    @abstractmethod
    def enrich(self, holdings: list[Holding]) -> list[Holding]: ...
