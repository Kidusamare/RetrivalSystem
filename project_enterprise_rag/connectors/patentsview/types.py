from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PatentsViewQuery:
    keywords: List[str]
    max_records: int = 200


@dataclass
class PatentRecord:
    patent_id: str
    title: str
    abstract: str
    date: str
    source_url: str

    def to_document(self) -> Dict:
        content = "\n\n".join(
            [
                f"Patent ID: {self.patent_id}",
                f"Title: {self.title}",
                f"Date: {self.date}",
                f"Abstract: {self.abstract}",
            ]
        )
        return {
            "text": content,
            "metadata": {
                "patent_id": self.patent_id,
                "patent_date": self.date,
                "source": "patentsview",
                "source_url": self.source_url,
                "file_name": f"US{self.patent_id}.md",
            },
        }
