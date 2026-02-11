from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column, BigInteger, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, TEXT

class PublicRepo(SQLModel, table=True):
    __tablename__ = "public_repos"
    __table_args__ = (
        Index("idx_repo_owner_name", "owner", "name"),
        Index("idx_repo_created_at", "created_at"),
    )
    
    id: int = Field(sa_column=Column(BigInteger, primary_key=True))
    owner: str = Field(sa_column=Column(TEXT, nullable=False))
    name: str = Field(sa_column=Column(TEXT, nullable=False))
    url: str = Field(sa_column=Column(TEXT, nullable=False))
    stargazers_count: int
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    last_crawled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
