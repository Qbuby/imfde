-- FDE portal knowledge base
-- Canonical DDL. Executed by E:\ai\build_portal_db.py (idempotent rebuild).
-- SQLite 3, UTF-8. Source JSON remains system of record; this DB is the cleaned truth.

PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    slug          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    name_zh       TEXT,
    kind          TEXT NOT NULL CHECK (kind IN ('vendor', 'unknown', 'extra')),
    on_site       INTEGER NOT NULL CHECK (on_site IN (0, 1)),
    interview_url TEXT,
    local_path    TEXT,
    notes         TEXT
);

CREATE TABLE company_aliases (
    alias TEXT PRIMARY KEY,
    slug  TEXT NOT NULL REFERENCES companies(slug)
);

CREATE TABLE customers (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    named    INTEGER NOT NULL CHECK (named IN (0, 1)),
    industry TEXT,
    notes    TEXT
);

CREATE TABLE topics (
    id       TEXT PRIMARY KEY,
    taxonomy TEXT NOT NULL CHECK (taxonomy IN ('aifde', 'fdei')),
    level    TEXT NOT NULL CHECK (level IN ('L1', 'L2', 'category')),
    slug     TEXT NOT NULL,
    name_en  TEXT,
    name_zh  TEXT,
    name_ja  TEXT,
    sort     INTEGER
);

CREATE TABLE topic_crosswalk (
    aifde_id TEXT NOT NULL REFERENCES topics(id),
    fdei_id  TEXT NOT NULL REFERENCES topics(id),
    note     TEXT,
    PRIMARY KEY (aifde_id, fdei_id)
);

CREATE TABLE questions (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL CHECK (kind IN ('open', 'mcq')),
    source         TEXT NOT NULL CHECK (source IN ('fdei', 'aifde')),
    title          TEXT,
    stem           TEXT,
    answer         TEXT,
    difficulty     TEXT,
    locale_default TEXT,
    category_slug  TEXT,
    upvotes        INTEGER,
    created        TEXT,
    modified       TEXT,
    local_path     TEXT,
    canonical_url  TEXT,
    license        TEXT,
    copyright      TEXT
);

CREATE TABLE question_locales (
    question_id  TEXT NOT NULL REFERENCES questions(id),
    locale       TEXT NOT NULL CHECK (locale IN ('zh', 'en', 'ja')),
    stem         TEXT,
    options_json TEXT,
    answer       TEXT,
    conf         TEXT,
    PRIMARY KEY (question_id, locale)
);

CREATE TABLE question_companies (
    question_id  TEXT NOT NULL REFERENCES questions(id),
    company_slug TEXT NOT NULL REFERENCES companies(slug),
    PRIMARY KEY (question_id, company_slug)
);

CREATE TABLE question_topics (
    question_id TEXT NOT NULL REFERENCES questions(id),
    topic_id    TEXT NOT NULL REFERENCES topics(id),
    PRIMARY KEY (question_id, topic_id)
);

CREATE TABLE cases (
    id                  INTEGER PRIMARY KEY,
    source_url          TEXT,
    source_title        TEXT,
    tier                TEXT,
    doc_type            TEXT,
    customer_id         INTEGER REFERENCES customers(id),
    industry            TEXT,
    business_problem    TEXT,
    existing_workflow   TEXT,
    pain_point          TEXT,
    discovery_method    TEXT,
    why_ai              TEXT,
    hero_use_case       TEXT,
    data_sources        TEXT,
    integration         TEXT,
    ai_model            TEXT,
    agent_workflow      TEXT,
    human_in_the_loop   TEXT,
    evaluation          TEXT,
    deployment          TEXT,
    time_to_production  TEXT,
    business_kpi        TEXT,
    measured_outcome    TEXT,
    failure_iteration   TEXT,
    productization      TEXT,
    customer_handoff    TEXT,
    fde_role            TEXT,
    quote               TEXT,
    evidence_quality    TEXT,
    evidence_note       TEXT,
    raw_company_text    TEXT,
    product             TEXT,
    kpi_scope           TEXT CHECK (kpi_scope IS NULL OR kpi_scope IN (
                          'narrative', 'hero_only', 'goal', 'projected', 'system_scale_not_kpi'))
);

CREATE TABLE case_companies (
    case_id      INTEGER NOT NULL REFERENCES cases(id),
    company_slug TEXT NOT NULL REFERENCES companies(slug),
    role         TEXT NOT NULL CHECK (role IN ('vendor', 'mentioned')),
    PRIMARY KEY (case_id, company_slug)
);

CREATE TABLE sources (
    id         TEXT PRIMARY KEY,
    url        TEXT,
    host       TEXT,
    tier       TEXT,
    doc_type   TEXT,
    title      TEXT,
    local_raw  TEXT,
    local_text TEXT,
    chars      INTEGER,
    bytes      INTEGER,
    is_pdf     INTEGER,
    status     INTEGER
);

CREATE TABLE unresolved (
    entity         TEXT NOT NULL CHECK (entity IN ('company', 'customer', 'industry', 'other')),
    raw_text       TEXT NOT NULL,
    count          INTEGER NOT NULL DEFAULT 1,
    suggested_slug TEXT,
    reason         TEXT NOT NULL,
    PRIMARY KEY (entity, raw_text, reason)
);


CREATE TABLE clean_flags (
    case_id INTEGER NOT NULL REFERENCES cases(id),
    flag    TEXT NOT NULL CHECK (flag IN (
              'narrative', 'hero_only', 'goal', 'projected', 'system_scale_not_kpi',
              'leftover_template', 'hub_kpi_not_on_page')),
    reason  TEXT NOT NULL,
    PRIMARY KEY (case_id, flag)
);

CREATE INDEX idx_company_aliases_slug ON company_aliases(slug);
CREATE INDEX idx_qc_company ON question_companies(company_slug);
CREATE INDEX idx_qt_topic ON question_topics(topic_id);
CREATE INDEX idx_cc_company ON case_companies(company_slug);
CREATE INDEX idx_cases_customer ON cases(customer_id);
CREATE INDEX idx_cases_doc_type ON cases(doc_type);
CREATE INDEX idx_clean_flags_case ON clean_flags(case_id);
CREATE INDEX idx_questions_kind ON questions(kind);
CREATE INDEX idx_questions_source ON questions(source);
