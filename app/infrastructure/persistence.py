from datetime import datetime, timezone
import logging
from typing import List
from sqlalchemy.dialects.postgresql import insert
from app.domain.interfaces import RepositoryPersistence
from app.domain.models import Repository
from app.infrastructure.database import async_session_factory
from app.infrastructure.tables import PublicRepo

logger = logging.getLogger(__name__)

class PostgresRepositoryPersistence(RepositoryPersistence):
    async def upsert_repositories(self, repositories: List[Repository]) -> None:
        if not repositories:
            return

        logger.info(f"Persisting {len(repositories)} repositories...")
        
        async with async_session_factory() as session:
            try:
                # Prepare data for bulk upsert
                values = []
                for r in repositories:
                    val = {
                        "id": r.id,
                        "owner": r.owner,
                        "name": r.name,
                        "url": r.url,
                        "stargazers_count": r.stargazers_count,
                        "created_at": r.created_at,
                        "last_crawled_at": r.last_crawled_at or datetime.now(timezone.utc)
                    }
                    values.append(val)

                stmt = insert(PublicRepo).values(values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[PublicRepo.id],
                    set_={
                        "stargazers_count": stmt.excluded.stargazers_count,
                        "last_crawled_at": stmt.excluded.last_crawled_at,
                        "url": stmt.excluded.url,
                        "owner": stmt.excluded.owner,
                        "name": stmt.excluded.name,
                    }
                )
                
                result = await session.execute(stmt)
                await session.commit()
                logger.info(f"Successfully upserted {len(repositories)} repositories.")
            except Exception as e:
                logger.error(f"Failed to upsert batch: {e}")
                await session.rollback()
                raise
