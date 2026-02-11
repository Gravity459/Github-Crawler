import logging
import asyncio
from datetime import datetime, timedelta
from typing import AsyncIterator, List

from app.domain.interfaces import GitHubSource
from app.domain.models import Repository
from app.infrastructure.github_client import GitHubGraphQLClient

logger = logging.getLogger(__name__)


class RecursiveSearchIterator:
    def __init__(self, client: GitHubGraphQLClient):
        self.client = client

    async def search_date_range(
        self, base_query: str, start_date: datetime, end_date: datetime
    ) -> AsyncIterator[List[Repository]]:
        """
        Recursively splits the date range until the count is < 1000.
        """
        # Format: created:2020-01-01..2020-02-01
        date_filter = f"created:{start_date.isoformat()}..{end_date.isoformat()}"
        full_query = f"{base_query} {date_filter}"

        count = await self.client.get_search_count(full_query)

        if count <= 1000:
            logger.info(f"Range {date_filter} has {count} repos. Fetching...")
            async for batch in self.client.search_repositories(full_query):
                yield batch
        else:
            logger.info(f"Range {date_filter} has {count} repos (>1000). Splitting...")
            mid_point = start_date + (end_date - start_date) / 2

            # Recurse left
            async for batch in self.search_date_range(
                base_query, start_date, mid_point
            ):
                yield batch

            async for batch in self.search_date_range(base_query, mid_point, end_date):
                yield batch
