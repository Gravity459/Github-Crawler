import unittest
from unittest.mock import MagicMock, AsyncMock, call
import asyncio
from datetime import datetime, timezone, timedelta
from app.domain.models import Repository
from app.usecases.crawler import RecursiveCrawler

class TestRecursiveCrawler(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_persistence = MagicMock()
        self.mock_persistence.upsert_repositories = AsyncMock()
        self.crawler = RecursiveCrawler(self.mock_client, self.mock_persistence)
        # Mock settings target
        self.crawler.target_count = 100

    def test_crawl_small_range(self):
        """Test that if count <= 1000, it fetches directly."""
        async def run_test():
            # Setup
            self.mock_client.get_search_count = AsyncMock(return_value=500)
            
            repo = Repository(1, "o", "n", "u", 10, datetime.now())
            async def mock_search(*args, **kwargs):
                yield [repo]
            
            self.mock_client.search_repositories = mock_search

            # Execute
            await self.crawler.crawl()

            # Verify
            self.mock_client.get_search_count.assert_called()
            self.mock_persistence.upsert_repositories.assert_called_with([repo])
            self.assertEqual(self.crawler.crawled_count, 1)

        asyncio.run(run_test())

    def test_crawl_recursive_split(self):
        """Test that if count > 1000, it splits."""
        async def run_test():
            # Setup
            # First call returns 2000 (split needed)
            # Second call (left half) returns 500 (fetch)
            # Third call (right half) returns 500 (fetch)
            self.mock_client.get_search_count = AsyncMock(side_effect=[2000, 500, 500])
            
            repo1 = Repository(1, "o", "n1", "u", 10, datetime.now())
            repo2 = Repository(2, "o", "n2", "u", 10, datetime.now())
            
            async def mock_search(query, **kwargs):
                # Simple mock: if query has specific date range implying split, return distinct repos
                yield [repo1] 

            self.mock_client.search_repositories = mock_search

            # Execute
            await self.crawler.crawl()

            # Verify:
            # get_search_count called 3 times (initial, left, right)
            self.assertEqual(self.mock_client.get_search_count.call_count, 3)
            # upsert called 2 times (once for left, once for right)
            self.assertEqual(self.mock_persistence.upsert_repositories.call_count, 2)
            
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
