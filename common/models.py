from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkRecord:
    chunk_id: str
    article_id: str
    title: str
    url: str
    heading_path: str
    text: str
    token_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "article_id": self.article_id,
            "title": self.title,
            "url": self.url,
            "heading_path": self.heading_path,
            "text": self.text,
            "token_count": self.token_count,
        }
