import asyncio
import logging
from datetime import datetime
from typing import List, AsyncIterator, Optional, Any

import aiohttp
from app.domain.interfaces import GitHubSource
from app.domain.models import Repository
from app.config import settings

logger = logging.getLogger(__name__)

SEARCH_QUERY = """
query SearchRepos($query: String!, $cursor: String, $first: Int!) {
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

class GitHubGraphQLClient(GitHubSource):
    BASE_URL = "https://api.github.com/graphql"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Crawler-Bot"
        }
    
    async def _execute_query(self, session: aiohttp.ClientSession, query: str, variables: dict) -> dict:
        while True:
            async with session.post(self.BASE_URL, json={"query": query, "variables": variables}, headers=self.headers) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_at = response.headers.get("X-RateLimit-Reset")
                
                if response.status == 403 or response.status == 429:
                    # Rate limit hit
                    if reset_at:
                        sleep_time = int(reset_at) - int(datetime.now().timestamp()) + 5
                        logger.warning(f"Rate limit hit. Sleeping for {sleep_time} seconds.")
                        await asyncio.sleep(max(sleep_time, 1))
                        continue
                    else:
                        logger.error(f"Request forbidden without reset header: {await response.text()}")
                        response.raise_for_status()

                if response.status != 200:
                    logger.error(f"GraphQL Query failed: {await response.text()}")
                    response.raise_for_status()
                
                data = await response.json()
                if "errors" in data:
                     # Handle potential secondary rate limits in errors
                     first_error = data["errors"][0]
                     if first_error.get("type") == "RATE_LIMITED":
                         logger.warning("GraphQL Rate Limit error in body. Sleeping 60s.")
                         await asyncio.sleep(60)
                         continue
                     logger.error(f"GraphQL Errors: {data['errors']}")
                     raise Exception(f"GraphQL Error: {data['errors']}")
                
                return data

    async def search_repositories(self, query: str, batch_size: int = 100) -> AsyncIterator[List[Repository]]:
        async with aiohttp.ClientSession() as session:
            cursor = None
            has_next = True
            
            while has_next:
                variables = {"query": query, "first": batch_size, "cursor": cursor}
                
                try:
                    data = await self._execute_query(session, SEARCH_QUERY, variables)
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
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Skipping malformed node: {node} - Error: {e}")

                if repositories:
                    yield repositories

                has_next = page_info["hasNextPage"]
                cursor = page_info["endCursor"]
                
                # Manual safety check against infinite loops or weird API behavior
                if has_next and not cursor:
                    break

    async def get_search_count(self, query: str) -> int:
        """
        Returns the total count of repositories matching the query.
        Used for determining if we need to split the date range.
        """
        count_query = """
        query CountRepos($query: String!) {
          search(query: $query, type: REPOSITORY, first: 1) {
            repositoryCount
          }
        }
        """
        async with aiohttp.ClientSession() as session:            
            try:
                data = await self._execute_query(session, count_query, {"query": query})
                return data["data"]["search"]["repositoryCount"]
            except Exception as e:
                logger.error(f"Failed to get search count: {e}")
                raise

