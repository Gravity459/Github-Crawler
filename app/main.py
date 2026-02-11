import asyncio
import logging
import sys

from app.config import settings
from app.infrastructure.github_client import GitHubGraphQLClient
from app.infrastructure.persistence import PostgresRepositoryPersistence
from app.usecases.crawler import RecursiveCrawler

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting GitHub Crawler...")
    
    # Initialize infrastructure
    from app.infrastructure.database import init_db
    await init_db()
    
    github_client = GitHubGraphQLClient()
    persistence = PostgresRepositoryPersistence()
    
    # Initialize use case
    crawler = RecursiveCrawler(github_client, persistence)
    
    # Execute
    try:
        await crawler.crawl()
    except Exception as e:
        logger.exception("Crawler failed with unhandled exception")
        sys.exit(1)
    
    logger.info("Crawler finished successfully.")

if __name__ == "__main__":
    asyncio.run(main())
