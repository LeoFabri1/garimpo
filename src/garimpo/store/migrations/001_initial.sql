-- Migration 001: initial schema (DESIGN §6.2)
-- Applied via PRAGMA user_version

PRAGMA foreign_keys = ON;

CREATE TABLE sources (
    id            INTEGER PRIMARY KEY,
    tg_id         INTEGER NOT NULL UNIQUE,
    username      TEXT,
    title         TEXT,
    parser        TEXT NOT NULL DEFAULT 'generic',
    enabled       INTEGER NOT NULL DEFAULT 1,
    last_msg_id   INTEGER,
    added_at      TEXT NOT NULL,
    last_seen_at  TEXT
);

CREATE TABLE raw_messages (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id),
    tg_msg_id     INTEGER NOT NULL,
    text          TEXT,
    text_hash     TEXT NOT NULL,
    has_media     INTEGER NOT NULL DEFAULT 0,
    received_at   TEXT NOT NULL,
    status        TEXT NOT NULL,
    parser_used   TEXT,
    fail_reason   TEXT,
    UNIQUE (source_id, tg_msg_id)
);
CREATE INDEX idx_raw_status ON raw_messages(status, received_at);
CREATE INDEX idx_raw_hash   ON raw_messages(text_hash, received_at);

CREATE TABLE offers (
    id             INTEGER PRIMARY KEY,
    raw_id         INTEGER NOT NULL REFERENCES raw_messages(id),
    model_key      TEXT    NOT NULL,
    brand          TEXT,
    variant        TEXT,
    condition      TEXT NOT NULL DEFAULT 'new',
    price          REAL    NOT NULL,
    price_listed   REAL,
    price_method   TEXT NOT NULL,
    installments   INTEGER,
    coupon         TEXT,
    store          TEXT,
    url            TEXT,
    url_resolved   TEXT,
    offer_hash     TEXT NOT NULL,
    extracted_by   TEXT NOT NULL,
    confidence     REAL NOT NULL DEFAULT 1.0,
    created_at     TEXT NOT NULL
);
CREATE INDEX idx_offers_model ON offers(model_key, created_at DESC);
CREATE INDEX idx_offers_hash  ON offers(offer_hash, created_at DESC);

CREATE TABLE price_history (
    id           INTEGER PRIMARY KEY,
    model_key    TEXT NOT NULL,
    price        REAL NOT NULL,
    condition    TEXT NOT NULL DEFAULT 'new',
    store        TEXT,
    observed_at  TEXT NOT NULL,
    origin       TEXT NOT NULL,
    offer_id     INTEGER REFERENCES offers(id),
    excluded     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (model_key, price, store, observed_at, origin)
);
CREATE INDEX idx_hist_lookup ON price_history(model_key, condition, observed_at DESC)
    WHERE excluded = 0;

CREATE TABLE alerts (
    id            INTEGER PRIMARY KEY,
    offer_id      INTEGER NOT NULL REFERENCES offers(id),
    rule_name     TEXT,
    level         TEXT NOT NULL,
    percentile    REAL,
    baseline      REAL,
    min_90d       REAL,
    n_samples     INTEGER,
    price_per_pt  REAL,
    reason        TEXT,
    channel       TEXT NOT NULL,
    status        TEXT NOT NULL,
    suppressed_by TEXT,
    sent_at       TEXT
);
CREATE INDEX idx_alerts_time  ON alerts(sent_at DESC);
CREATE INDEX idx_alerts_offer ON alerts(offer_id);

CREATE TABLE enrich_queue (
    id           INTEGER PRIMARY KEY,
    raw_id       INTEGER NOT NULL UNIQUE REFERENCES raw_messages(id),
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    enqueued_at  TEXT NOT NULL,
    next_try_at  TEXT NOT NULL
);
CREATE INDEX idx_queue_ready ON enrich_queue(next_try_at);

CREATE TABLE kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
