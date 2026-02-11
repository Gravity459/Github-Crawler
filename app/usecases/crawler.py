import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from app.domain.interfaces import RepositoryPersistence
from app.infrastructure.github_client import GitHubGraphQLClient
from app.config import settings

logger = logging.getLogger(__name__)

class RecursiveCrawler:
    def __init__(self, github_client: GitHubGraphQLClient, persistence: RepositoryPersistence):
        self.github = github_client
        self.persistence = persistence
        self.crawled_count = 0
        self.target_count = settings.target_repo_count

    async def crawl(self):
        """
        Main entry point for crawling.
        """
        # We start from 2008 (GitHub launch) to now.
        start_date = datetime(2008, 1, 1, tzinfo=timezone.utc)
        end_date = datetime.now(timezone.utc)
        
        logger.info(f"Starting crawl from {start_date} to {end_date}")
        
        base_query = "is:public sort:stars-desc stars:>10" 
        
        # To avoid noise (millions of empty repos), maybe "stars:>=1".
        base_query = "is:public stars:>=5" 

        await self._recurse_date_range(base_query, start_date, end_date)
        logger.info(f"Crawl completed. Total repositories crawled: {self.crawled_count}")

    async def _recurse_date_range(self, base_query: str, start_date: datetime, end_date: datetime):
        if self.crawled_count >= self.target_count:
            return

        date_str = f"created:{start_date.isoformat()}..{end_date.isoformat()}"
        full_query = f"{base_query} {date_str}"
        
        try:
            count = await self.github.get_search_count(full_query)
        except Exception:
            # If count fails (timeout?), strict split might be safer
            count = 1001

        logger.info(f"Checking range {date_str}: {count} repos")

        if count == 0:
            return

        if count <= 1000:
            # Fetch all
            async for batch in self.github.search_repositories(full_query):
                self.crawled_count += len(batch)
                logger.info(f"Crawled {len(batch)} repos from {date_str}. Total: {self.crawled_count}")
                await self.persistence.upsert_repositories(batch)
                if self.crawled_count >= self.target_count:
                    break
        else:
            # Split
            time_diff = end_date - start_date
            if time_diff < timedelta(minutes=1): 
                # Safety break to avoid infinite recursion on very dense periods (unlikely with stars>=5)
                logger.warning(f"Time range too small {time_diff} for {count} repos. Fetching first 1000.")
                async for batch in self.github.search_repositories(full_query): # will only get first 1000
                     self.crawled_count += len(batch)
                     await self.persistence.upsert_repositories(batch)
                     break
                return

            mid_point = start_date + (time_diff / 2)
            
            await self._recurse_date_range(base_query, start_date, mid_point)
            await self._recurse_date_range(base_query, mid_point, end_date)
