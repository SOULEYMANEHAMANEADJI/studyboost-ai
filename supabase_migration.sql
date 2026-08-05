-- =============================================================
-- StudyBoost AI — Migration Supabase
-- Exécuter DANS L'ORDRE dans Supabase SQL Editor
-- =============================================================

-- 0. Créer la table sessions si elle n'existe pas (première installation)
CREATE TABLE IF NOT EXISTS public.sessions (
    id TEXT PRIMARY KEY,
    pdf_count INTEGER DEFAULT 0,
    chat_count INTEGER DEFAULT 0,
    search_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW()
);

-- 0b. Créer les autres tables si elles n'existent pas
CREATE TABLE IF NOT EXISTS public.admin_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS public.chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.activity_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    action_type TEXT DEFAULT '',
    action_detail TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.feedbacks (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    rating INTEGER DEFAULT 3,
    comment TEXT DEFAULT '',
    feature_request TEXT DEFAULT '',
    other_idea TEXT DEFAULT '',
    email TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1. Ajouter les colonnes manquantes à sessions
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS alias_emoji TEXT DEFAULT '🎓',
  ADD COLUMN IF NOT EXISTS alias_animal TEXT DEFAULT 'Étudiant',
  ADD COLUMN IF NOT EXISTS alias_adjective TEXT DEFAULT 'Anonyme',
  ADD COLUMN IF NOT EXISTS alias_number INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS alias_display TEXT DEFAULT '🎓 Anonyme',
  ADD COLUMN IF NOT EXISTS ai_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS quota_date TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS draft_text TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS preferred_model TEXT DEFAULT '';

-- 2. Ajouter la colonne manquante à feedbacks
ALTER TABLE public.feedbacks
  ADD COLUMN IF NOT EXISTS other_idea TEXT DEFAULT '';

-- 3. Index pour performances
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON public.sessions(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON public.chat_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_session ON public.activity_logs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON public.activity_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created ON public.feedbacks(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_settings_key ON public.admin_settings(key);

-- 4. Nettoyer les anciens modèles (gemma2 et mixtral retirés par Groq)
DELETE FROM public.admin_settings WHERE key LIKE '%gemma2-9b-it%';
DELETE FROM public.admin_settings WHERE key LIKE '%mixtral-8x7b%';
DELETE FROM public.admin_settings WHERE key LIKE '%llama-3.2-11b%';
DELETE FROM public.admin_settings WHERE key LIKE '%llama-3.2-3b%';
DELETE FROM public.admin_settings WHERE key LIKE '%deepseek%';
DELETE FROM public.admin_settings WHERE key LIKE '%qwen-2.5%';
DELETE FROM public.admin_settings WHERE key LIKE '%gemini%';

-- 5. Ajouter les nouveaux modèles
INSERT INTO public.admin_settings (key, value) VALUES
  ('model_enabled_meta-llama/llama-4-scout-17b-16e-instruct', 'true'),
  ('model_quota_meta-llama/llama-4-scout-17b-16e-instruct', '20'),
  ('model_enabled_qwen/qwen3-32b', 'true'),
  ('model_quota_qwen/qwen3-32b', '20')
ON CONFLICT (key) DO NOTHING;

-- 6. S'assurer que quota_ai_per_day existe
INSERT INTO public.admin_settings (key, value) VALUES
  ('quota_ai_per_day', '15')
ON CONFLICT (key) DO NOTHING;

-- 7. Ajouter RLS (recommandé pour sécurité au niveau DB)
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_settings ENABLE ROW LEVEL SECURITY;

-- 8. Politiques RLS : accès via anon key
-- NOTE : la clé anon est UNIQUE pour tous les utilisateurs anonymes,
-- donc RLS ne peut pas isoler par session_id ici.
-- L'isolation est FAITE DANS LE CODE PYTHON (backend) via .eq("session_id", user_id).
-- Pour une isolation RLS complète, migrer vers Supabase Auth (sign-up anonyme).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow anonymous access' AND tablename = 'sessions') THEN
    CREATE POLICY "Allow anonymous access" ON public.sessions FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow anonymous access' AND tablename = 'chat_history') THEN
    CREATE POLICY "Allow anonymous access" ON public.chat_history FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow anonymous access' AND tablename = 'activity_logs') THEN
    CREATE POLICY "Allow anonymous access" ON public.activity_logs FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow anonymous access' AND tablename = 'feedbacks') THEN
    CREATE POLICY "Allow anonymous access" ON public.feedbacks FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow anonymous access' AND tablename = 'admin_settings') THEN
    CREATE POLICY "Allow anonymous access" ON public.admin_settings FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

-- 10. Fonction RPC pour incrément atomique des quotas
-- Évite les race conditions: un seul appel PostgreSQL = une seule transaction
CREATE OR REPLACE FUNCTION increment_quota_rpc(_user_id TEXT, _col_name TEXT)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF _col_name NOT IN ('pdf_count', 'chat_count', 'search_count', 'ai_count') THEN
    RAISE EXCEPTION 'Invalid quota column: %', _col_name;
  END IF;
  EXECUTE format(
    'UPDATE sessions SET %I = COALESCE(%I, 0) + 1, quota_date = %L, last_active = NOW() WHERE id = %L',
    _col_name, _col_name, to_char(NOW(), 'YYYY-MM-DD'), _user_id
  );
END;
$$;

-- 11. Vérification : colonnes sessions
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'sessions'
ORDER BY ordinal_position;
