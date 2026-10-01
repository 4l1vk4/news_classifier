from abc import ABC, abstractmethod
from typing import List
from src.models import NewsItem, detect_lang


class BaseIngestor(ABC):
    source_name: str = "base"

    @abstractmethod
    def fetch(self, limit: int = 20) -> List[NewsItem]:
        raise NotImplementedError

