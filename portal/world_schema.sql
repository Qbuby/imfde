-- Additive world-dynamics layer. Does not alter cases / companies / questions.
-- Homepage still reads `cases` until ingest + worldview switch.
--
-- Apply (idempotent):
--   sqlite3 portal/fde.db < portal/world_schema.sql
--
-- Do NOT fold this into portal/schema.sql. `build_portal_db.py` deletes
-- fde.db and recreates it from schema.sql; re-apply this file after a rebuild.
-- Catalog of feeds/seeds lives in portal/world_sources.json (system of record
-- for *what to watch*). These tables are the runtime read model.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS world_info_kinds (
    id          TEXT PRIMARY KEY,
    lane        TEXT NOT NULL CHECK (lane IN ('company', 'people', 'method', 'deploy')),
    name_zh     TEXT NOT NULL,
    name_en     TEXT,
    accept_note TEXT,
    reject_note TEXT
);

CREATE TABLE IF NOT EXISTS world_entities (
    slug    TEXT PRIMARY KEY,
    kind    TEXT NOT NULL CHECK (kind IN ('org', 'person', 'publication', 'community')),
    name    TEXT NOT NULL,
    name_zh TEXT,
    host    TEXT,
    notes   TEXT
);

CREATE TABLE IF NOT EXISTS world_sources (
    id          TEXT PRIMARY KEY,
    role        TEXT NOT NULL CHECK (role IN ('feed', 'seed', 'exclude')),
    url         TEXT NOT NULL UNIQUE,
    host        TEXT,
    lane        TEXT CHECK (lane IS NULL OR lane IN ('company', 'people', 'method', 'deploy')),
    info_kind   TEXT,
    fetch_mode  TEXT NOT NULL CHECK (fetch_mode IN (
                    'list_index', 'single_page', 'ats_api', 'rss',
                    'youtube', 'json_api', 'manual')),
    status      TEXT NOT NULL CHECK (status IN (
                    'in_db', 'missing', 'watch', 'skip', 'blocked')),
    priority    INTEGER NOT NULL DEFAULT 3,
    entity_slug TEXT REFERENCES world_entities(slug),
    date_hint   TEXT,
    notes       TEXT
);

-- Splits date kinds. Axis events use published or modified only.
-- sitemap_lastmod is stored for diagnostics and must never become day.
CREATE TABLE IF NOT EXISTS source_dates (
    url              TEXT PRIMARY KEY,
    published        TEXT,
    modified         TEXT,
    collected        TEXT,
    sitemap_lastmod  TEXT,
    best             TEXT,
    best_kind        TEXT CHECK (
                         best_kind IS NULL OR best_kind IN (
                             'published', 'modified', 'collected', 'sitemap_lastmod')),
    case_id          INTEGER,
    raw_file         TEXT,
    extracted_at     TEXT
);

CREATE TABLE IF NOT EXISTS world_events (
    id              INTEGER PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    lane            TEXT NOT NULL CHECK (lane IN ('company', 'people', 'method', 'deploy')),
    info_kind       TEXT NOT NULL,
    title           TEXT,
    title_zh        TEXT,
    day             TEXT,
    date_kind       TEXT CHECK (date_kind IN ('published', 'modified', 'collected')),
    collected_on    TEXT,
    host            TEXT,
    entity_slug     TEXT REFERENCES world_entities(slug),
    signal          TEXT NOT NULL DEFAULT 'hard' CHECK (signal IN ('hard', 'weak')),
    happened_zh     TEXT,
    why_zh          TEXT,
    enterprise_zh   TEXT,
    practitioner_zh TEXT,
    evidence        TEXT,
    source_case_id  INTEGER,
    ingest_note     TEXT
);

CREATE TABLE IF NOT EXISTS world_event_entities (
    event_id    INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    entity_slug TEXT NOT NULL REFERENCES world_entities(slug),
    role        TEXT NOT NULL CHECK (role IN ('actor', 'author', 'mentioned', 'publisher')),
    PRIMARY KEY (event_id, entity_slug, role)
);

-- Visual association is not causality. basis=editorial is the only
-- allowed way to draw a chain the UI currently treats as "变化".
CREATE TABLE IF NOT EXISTS world_links (
    id      INTEGER PRIMARY KEY,
    from_id INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    to_id   INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    kind    TEXT NOT NULL CHECK (kind IN ('direct', 'indirect')),
    basis   TEXT NOT NULL CHECK (basis IN ('same_org', 'same_person', 'cites', 'editorial')),
    note    TEXT,
    UNIQUE (from_id, to_id, basis),
    CHECK (from_id != to_id)
);

-- Per snapshot × window. Written at ingest, not derived in GET /.
CREATE TABLE IF NOT EXISTS world_changes (
    id            INTEGER PRIMARY KEY,
    snapshot      TEXT NOT NULL,
    window_days   INTEGER NOT NULL,
    title_zh      TEXT NOT NULL,
    body_zh       TEXT,
    from_event_id INTEGER REFERENCES world_events(id),
    to_event_id   INTEGER REFERENCES world_events(id),
    editorial     INTEGER NOT NULL DEFAULT 1 CHECK (editorial IN (0, 1)),
    UNIQUE (snapshot, window_days, title_zh)
);

-- Overflow from a single ingest run. Not shown on the axis until accepted.
CREATE TABLE IF NOT EXISTS world_review (
    id          INTEGER PRIMARY KEY,
    url         TEXT NOT NULL,
    title       TEXT,
    day         TEXT,
    lane        TEXT,
    info_kind   TEXT,
    reason      TEXT,
    seen_at     TEXT,
    UNIQUE (url, day)
);

CREATE TABLE IF NOT EXISTS world_ingest_runs (
    id           INTEGER PRIMARY KEY,
    started_at   TEXT,
    snapshot     TEXT,
    since_day    TEXT,
    scanned      INTEGER,
    fde_hits     INTEGER,
    already      INTEGER,
    stale        INTEGER,
    added_axis   INTEGER,
    review       INTEGER,
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_world_events_lane_day ON world_events(lane, day);
CREATE INDEX IF NOT EXISTS idx_world_events_kind ON world_events(info_kind);
CREATE INDEX IF NOT EXISTS idx_world_events_entity ON world_events(entity_slug);
CREATE INDEX IF NOT EXISTS idx_world_sources_status ON world_sources(status, priority);
CREATE INDEX IF NOT EXISTS idx_world_links_from ON world_links(from_id);
CREATE INDEX IF NOT EXISTS idx_world_links_to ON world_links(to_id);
CREATE INDEX IF NOT EXISTS idx_world_changes_snap ON world_changes(snapshot, window_days);
CREATE INDEX IF NOT EXISTS idx_source_dates_best ON source_dates(best_kind, best);
