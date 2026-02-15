-- SignalBoard V2 subscription schema
-- Global signal results remain in JSON cache. SQLite stores only user preferences.

CREATE TABLE users (
    username TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE subscriptions (
    username TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (username, signal_id),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);
