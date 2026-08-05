-- =============================================================
-- StudyBoost AI — Migration Neon PostgreSQL
-- Exécuter dans le SQL Editor de Neon (ou via psql)
-- =============================================================

-- 1. Sessions (utilisateurs anonymes)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    pdf_count INTEGER DEFAULT 0,
    chat_count INTEGER DEFAULT 0,
    search_count INTEGER DEFAULT 0,
    ai_count INTEGER DEFAULT 0,
    alias_emoji TEXT DEFAULT '🎓',
    alias_animal TEXT DEFAULT 'Étudiant',
    alias_adjective TEXT DEFAULT 'Anonyme',
    alias_number INTEGER DEFAULT 0,
    alias_display TEXT DEFAULT '🎓 Anonyme',
    quota_date TEXT DEFAULT '',
    draft_text TEXT DEFAULT '',
    preferred_model TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Paramètres administrateur
CREATE TABLE IF NOT EXISTS admin_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- 3. Historique du chat
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Logs d'activité
CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    action_type TEXT DEFAULT '',
    action_detail TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Feedbacks utilisateurs
CREATE TABLE IF NOT EXISTS feedbacks (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    rating INTEGER DEFAULT 3,
    comment TEXT DEFAULT '',
    feature_request TEXT DEFAULT '',
    other_idea TEXT DEFAULT '',
    email TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Index pour performances
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON sessions(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_session ON activity_logs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON activity_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created ON feedbacks(created_at DESC);

-- 7. Paramètres par défaut
INSERT INTO admin_settings (key, value) VALUES
    ('feature_chat_enabled', 'true'),
    ('feature_search_enabled', 'true'),
    ('feature_pdf_enabled', 'true'),
    ('feature_md_enabled', 'true'),
    ('auto_cleanup_enabled', 'true'),
    ('maintenance_mode', 'false'),
    ('quota_pdf_per_day', '10'),
    ('quota_chat_per_day', '20'),
    ('quota_search_per_day', '10'),
    ('quota_ai_per_day', '15'),
    ('retention_days', '7')
ON CONFLICT (key) DO NOTHING;
