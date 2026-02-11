from dataclasses import dataclass
from datetime import datetime

@dataclass
class Repository:
    id: int
    owner: str
    name: str
    url: str
    stargazers_count: int
    created_at: datetime
    last_crawled_at: datetime | None = None
