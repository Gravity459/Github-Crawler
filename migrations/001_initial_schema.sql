-- Up
CREATE TABLE IF NOT EXISTS public_repos (
    id BIGINT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    stargazers_count INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repo_owner_name ON public_repos(owner, name);
CREATE INDEX IF NOT EXISTS idx_repo_created_at ON public_repos(created_at);

-- Down
DROP TABLE IF EXISTS public_repos;
