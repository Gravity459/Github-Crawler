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
        self.semaphore = asyncio.Semaphore(settings.max_concurrency)
        self.count_lock = asyncio.Lock()

    async def crawl(self):
        """
        Main entry point for crawling.
        """
        # We start from 2008 (GitHub launch) to now.
        start_date = datetime(2008, 1, 1, tzinfo=timezone.utc)
        end_date = datetime.now(timezone.utc)
        
        logger.info(f"Starting crawl from {start_date} to {end_date}")
        
        base_query = "is:public stars:>=5 sort:created-asc" 

        await self._recurse_date_range(base_query, start_date, end_date)
        logger.info(f"Crawl completed. Total repositories crawled: {self.crawled_count}")

    async def _recurse_date_range(self, base_query: str, start_date: datetime, end_date: datetime):
        # Quick check without lock optimization
        if self.crawled_count >= self.target_count:
            return

        date_str = f"created:{start_date.isoformat()}..{end_date.isoformat()}"
        full_query = f"{base_query} {date_str}"
        
        # Acquire semaphore for the count check to avoid flooding
        try:
            async with self.semaphore:
                # Re-check count inside semaphore/lock if strictly needed, 
                # but for simply checking API count, it's fine.
                try:
                    count = await self.github.get_search_count(full_query)
                except Exception:
                    # If count fails (timeout?), strict split might be safer
                    count = 1001
        except Exception as e:
            logger.error(f"Error checking count for {date_str}: {e}")
            return

        if count == 0:
            return

        if count <= 1000:
            # Fetch all
            try:
                async with self.semaphore:
                    async for batch in self.github.search_repositories(full_query):
                        async with self.count_lock:
                            if self.crawled_count >= self.target_count:
                                break
                            
                            # Calculate how many we can take
                            remaining = self.target_count - self.crawled_count
                            to_take = batch[:remaining]
                            
                            self.crawled_count += len(to_take)
                            logger.info(f"Crawled {len(to_take)} repos from {date_str}. Total: {self.crawled_count}")
                            await self.persistence.upsert_repositories(to_take)
                            
                        if self.crawled_count >= self.target_count:
                             break

            except Exception as e:
                logger.error(f"Error fetching range {date_str}: {e}")
        else:
            # Split
            time_diff = end_date - start_date
            if time_diff < timedelta(minutes=1): 
                # Safety break to avoid infinite recursion
                logger.warning(f"Time range too small {time_diff} for {count} repos. Fetching first 1000.")
                async with self.semaphore:
                    async for batch in self.github.search_repositories(full_query): # will only get first 1000
                         async with self.count_lock:
                             if self.crawled_count >= self.target_count:
                                 break
                             
                             remaining = self.target_count - self.crawled_count
                             to_take = batch[:remaining]
                             
                             self.crawled_count += len(to_take)
                             await self.persistence.upsert_repositories(to_take)
                         
                         if self.crawled_count >= self.target_count:
                             break
                return

            mid_point = start_date + (time_diff / 2)
            
            # Use TaskGroup for parallelism
            try:
                async with asyncio.TaskGroup() as tg:
                    # Check before spawning
                    if self.crawled_count >= self.target_count:
                        return
                    tg.create_task(self._recurse_date_range(base_query, start_date, mid_point))
                    tg.create_task(self._recurse_date_range(base_query, mid_point, end_date))
            except Exception as e:
                logger.error(f"Error in parallel recursion for {date_str}: {e}")
