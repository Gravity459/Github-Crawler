# Scaling to 500 Million Repositories & Schema Evolution Plan

## What I Would Do Differently for 500 Million Repositories

1. **Adopt a Distributed Crawling Architecture**  
   Replace the single crawler with multiple distributed workers. Each worker would process a deterministic shard (e.g., by repository ID hash or creation date range) to enable horizontal scaling.

2. **Use Multiple GitHub App Installations / Token Pooling**  
   A single GitHub token would not provide sufficient rate limits. I would distribute API calls across multiple installations or tokens to increase total throughput.

3. **Introduce a Message Queue Between Crawlers and Storage**  
   Instead of writing directly to the database, crawlers would publish repository events to a queue (e.g., Kafka or SQS). Separate consumers would batch-write to storage.  
   This improves scalability, fault tolerance, and backpressure handling.

4. **Partition the Database**  
   - Partition large tables by `repo_id` (hash partitioning) for even data distribution.  
   - Partition time-series tables (e.g., star snapshots) by date for efficient pruning and archival.  
   This improves write throughput and long-term maintainability.

5. **Prefer Append-Only Writes**  
   Avoid heavy `UPDATE` operations. Insert new records instead of modifying existing rows to reduce lock contention and improve performance.

6. **Separate Transactional Storage from Analytics**  
   Use Postgres for ingestion and transactional consistency.  
   Use a data warehouse (e.g., ClickHouse or BigQuery) for large-scale analytics queries.

7. **Add Checkpointing and Idempotency**  
   Track crawl state per shard to allow safe retries and recovery without reprocessing large datasets.

---

## How the Schema Would Evolve for Additional Metadata

To support future metadata such as issues, pull requests, comments, reviews, commits, and CI checks:

1. **One Entity Per Table (Normalized Schema Design)**  
   Create separate tables for:
   - `repositories`
   - `issues`
   - `pull_requests`
   - `issue_comments`
   - `pr_comments`
   - `pr_reviews`
   - `pr_commits`
   - `ci_checks`

   This prevents wide, mutable rows and isolates growth per entity.

2. **Use Append-Only Records for Growing Data**  
   If a PR has 10 comments today and 20 tomorrow:
   - Insert 10 new rows into `pr_comments`
   - Do not update existing rows  
   This ensures minimal rows affected and efficient incremental updates.

3. **Use GitHub IDs as Primary Keys**  
   Store GitHub’s unique IDs as primary keys to support idempotent writes and safe upserts.

4. **Avoid Aggregated Counters in Parent Tables**  
   Do not store derived values like total comment counts in repository or PR rows.  
   Compute these via queries or materialized views to avoid unnecessary row updates.

5. **Partition High-Growth Tables**  
   Partition large tables (e.g., comments, CI checks, star snapshots) by date or `repo_id` to maintain performance at scale.

---

## Design Principles

- Horizontal scalability  
- Append-heavy, minimal-mutation writes  
- Partitioned storage  
- Idempotent ingestion  
- Clean schema extensibility  
- Separation of ingestion and analytics workloads  

At 500 million repositories, the system evolves from a simple crawler into a distributed, horizontally scalable data ingestion pipeline with append-only modeling and partitioned storage.
