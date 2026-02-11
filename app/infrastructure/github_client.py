import asyncio
import logging
import time
from datetime import datetime
from typing import List, AsyncIterator, Optional, Any

import aiohttp
from app.domain.interfaces import GitHubSource
from app.domain.models import Repository
from app.config import settings

logger = logging.getLogger(__name__)

SEARCH_QUERY = """
query SearchRepos($query: String!, $cursor: String, $first: Int!) {
  rateLimit {
    cost
    remaining
    resetAt
  }
  search(query: $query, type: REPOSITORY, first: $first, after: $cursor) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        databaseId
        nameWithOwner
        url
        stargazers {
          totalCount
        }
        createdAt
      }
    }
  }
}
"""

class RateLimiter:
    """
    Manages GitHub GraphQL API rate limits.
    """
    def __init__(self):
        self.remaining = 5000
        self.reset_at = None
        self._lock = asyncio.Lock()

    async def accumulate(self, cost: int, remaining: int, reset_at_iso: str):
        async with self._lock:
            self.remaining = remaining
            # Parse reset_at if needed, but we mostly care about remaining
            if reset_at_iso:
                try:
                    self.reset_at = datetime.fromisoformat(reset_at_iso.replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            # Simple check: if we are dangerously low, log it.
            if self.remaining < 100:
                logger.warning(f"Rate limit running low: {self.remaining} remaining.")

    async def wait_if_needed(self):
        async with self._lock:
             if self.remaining < 50: # Safety buffer
                 now = datetime.now(self.reset_at.tzinfo if self.reset_at else None)
                 if self.reset_at and self.reset_at > now:
                     sleep_time = (self.reset_at - now).total_seconds() + 2
                     logger.warning(f"Rate limit exhausted ({self.remaining}). Sleeping for {sleep_time:.2f}s until {self.reset_at}")
                     await asyncio.sleep(sleep_time)

class GitHubGraphQLClient(GitHubSource):
    BASE_URL = "https://api.github.com/graphql"

    def __init__(self, session: aiohttp.ClientSession):
        """
        :param session: Shared aiohttp ClientSession. 
                        The caller is responsible for lifecycle management.
        """
        self.session = session
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Crawler-Bot"
        }
        self.rate_limiter = RateLimiter()
    
    async def _execute_query(self, query: str, variables: dict) -> dict:
        await self.rate_limiter.wait_if_needed()
        
        while True:
            try:
                async with self.session.post(self.BASE_URL, json={"query": query, "variables": variables}, headers=self.headers) as response:
                    # Check HTTP headers for rate limits as backup
                    try:
                        remaining_header = response.headers.get("X-RateLimit-Remaining")
                        reset_header = response.headers.get("X-RateLimit-Reset")
                        
                        if response.status == 403 or response.status == 429:
                           if reset_header:
                               sleep_time = int(reset_header) - int(datetime.now().timestamp()) + 5
                               logger.warning(f"Secondary Rate limit hit (HTTP {response.status}). Sleeping for {sleep_time} seconds.")
                               await asyncio.sleep(max(sleep_time, 1))
                               continue
                           else:
                               logger.error(f"Request forbidden without reset header: {await response.text()}")
                               response.raise_for_status()

                        if response.status != 200:
                            logger.error(f"GraphQL Query failed: {await response.text()}")
                            response.raise_for_status()
                        
                        data = await response.json()
                        
                        # Check for GraphQL errors
                        if "errors" in data:
                            first_error = data["errors"][0]
                            if first_error.get("type") == "RATE_LIMITED":
                                logger.warning("GraphQL Rate Limit error in body. Sleeping 60s.")
                                await asyncio.sleep(60)
                                continue
                            
                            # Log but don't crash on partial errors if data exists? 
                            # Usually separate task. treating as error for now.
                            logger.error(f"GraphQL Errors: {data['errors']}")
                            raise Exception(f"GraphQL Error: {data['errors']}")
                        
                        if "data" in data and "rateLimit" in data["data"]:
                            rl = data["data"]["rateLimit"]
                            if rl:
                                await self.rate_limiter.accumulate(rl.get("cost", 1), rl.get("remaining", 0), rl.get("resetAt"))

                        return data
                        
                    except aiohttp.ClientError as e:
                        logger.error(f"Network error: {e}. Retrying in 5s...")
                        await asyncio.sleep(5)
                        continue
                        
            except Exception as e:
                 logger.error(f"Unexpected error in _execute_query: {e}")
                 raise

    async def search_repositories(self, query: str, batch_size: int = 100) -> AsyncIterator[List[Repository]]:
        cursor = None
        has_next = True
        
        while has_next:
            variables = {"query": query, "first": batch_size, "cursor": cursor}
            
            try:
                data = await self._execute_query(SEARCH_QUERY, variables)
            except Exception as e:
                logger.error(f"Failed to execute query: {e}")
                raise

            search_data = data["data"]["search"]
            nodes = search_data["nodes"]
            page_info = search_data["pageInfo"]
            
            repositories = []
            for node in nodes:
                if not node: continue
                try:
                    repo = Repository(
                        id=node["databaseId"],
                        owner=node["nameWithOwner"].split("/")[0],
                        name=node["nameWithOwner"].split("/")[1],
                        url=node["url"],
                        stargazers_count=node["stargazers"]["totalCount"],
                        created_at=datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00"))
                    )
                    repositories.append(repo)
                except (KeyError, ValueError, IndexError) as e:
                    logger.warning(f"Skipping malformed node: {node} - Error: {e}")

            if repositories:
                yield repositories

            has_next = page_info["hasNextPage"]
            cursor = page_info["endCursor"]
            
            if has_next and not cursor:
                break

    async def get_search_count(self, query: str) -> int:
        """
        Returns the total count of repositories matching the query.
        """
        # Minimal query, reusing the main query structure but asking for 0 nodes or just count
        # To avoid complex query mismatch, we can use a simpler query string 
        # BUT we want to capture rate limits.
        
        # We can use a dedicated count query that also requests rateLimit
        count_query = """
        query CountRepos($query: String!) {
          rateLimit {
            cost
            remaining
            resetAt
          }
          search(query: $query, type: REPOSITORY, first: 1) {
            repositoryCount
          }
        }
        """
        
        try:
            data = await self._execute_query(count_query, {"query": query})
            return data["data"]["search"]["repositoryCount"]
        except Exception as e:
            logger.error(f"Failed to get search count: {e}")
            raise

