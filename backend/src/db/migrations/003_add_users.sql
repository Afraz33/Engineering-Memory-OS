-- users table (Google OAuth accounts)
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub    STRING NOT NULL UNIQUE,
    email         STRING NOT NULL,
    name          STRING,
    avatar_url    STRING,
    created_at    TIMESTAMP DEFAULT now(),
    last_login_at TIMESTAMP DEFAULT now()
);

CREATE INDEX ON users (email);
