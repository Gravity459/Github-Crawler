# GitHub GraphQL Crawler

A production-quality GitHub crawler that fetches star counts for 100,000+ repositories using the GraphQL API and stores them in PostgreSQL.

## Features
- **Clean Architecture**: Modular design for maintainability.
- **Efficient Crawling**: Uses GitHub GraphQL API with cursor-based pagination.
- **Smart Sharding**: recursive date-based splitting to bypass the 1,000 result search limit.
- **Robustness**: Handles rate limits (429/403) and network errors.
- **Persistence**: Async PostgreSQL storage with UPSERT support.
- **CI/CD**: Fully automated via GitHub Actions.

## Setup
### Prerequisites
- Python 3.11+
- PostgreSQL 15+

### Installation
1. Clone the repo
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
Create a `.env` file:
```env
GITHUB_TOKEN=your_token_here
DATABASE_URL=postgresql://user:password@localhost:5432/github_data
TARGET_REPO_COUNT=100000
LOG_LEVEL=INFO
```

### Running Locally
1. Run migrations:
   ```bash
   psql -d github_data -f migrations/001_initial_schema.sql
   ```
2. Run the crawler:
   ```bash
   python -m app.main
   ```

## Architecture
- `app/domain`: Core entities (`Repository`) and interfaces.
- `app/usecases`: Business logic (`RecursiveCrawler`).
- `app/infrastructure`: External adapters (`GitHubGraphQLClient`, `PostgresRepositoryPersistence`).
