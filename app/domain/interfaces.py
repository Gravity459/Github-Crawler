from abc import ABC, abstractmethod
from typing import List, AsyncIterator
from app.domain.models import Repository

class RepositoryPersistence(ABC):
    @abstractmethod
    async def upsert_repositories(self, repositories: List[Repository]) -> None:
        pass

class GitHubSource(ABC):
    @abstractmethod
    async def search_repositories(self, query: str, batch_size: int = 100) -> AsyncIterator[List[Repository]]:
        """
        Searches for repositories matching the query.
        Yields batches of repositories found.
        Handles pagination internally.
        """
        pass
