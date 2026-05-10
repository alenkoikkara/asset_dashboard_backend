from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.models.holding import Holding


class BaseLoader(ABC):
    @abstractmethod
    def load(self, holdings: list[Holding]) -> None: ...
