-- =============================================================
-- StudyBoost AI — Migration Supabase
-- Exécuter DANS L'ORDRE dans Supabase SQL Editor
-- =============================================================

-- 1. Ajouter les colonnes manquantes à sessions
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS alias_emoji TEXT DEFAULT '🎓',
  ADD COLUMN IF NOT EXISTS alias_animal TEXT DEFAULT 'Étudiant',
  ADD COLUMN IF NOT EXISTS alias_adjective TEXT DEFAULT 'Anonyme',
  ADD COLUMN IF NOT EXISTS alias_number INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS alias_display TEXT DEFAULT '🎓 Anonyme',
  ADD COLUMN IF NOT EXISTS ai_count INTEGER DEFAULT 0;

-- 2. Ajouter la colonne manquante à feedbacks
ALTER TABLE public.feedbacks
  ADD COLUMN IF NOT EXISTS other_idea TEXT DEFAULT '';

-- 3. Index pour performances
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON public.sessions(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON public.chat_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_session ON public.activity_logs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON public.activity_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created ON public.feedbacks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_settings_key ON public.admin_settings(key);

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

-- 7. Ajouter RLS (optionnel mais recommandé)
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_settings ENABLE ROW LEVEL SECURITY;

-- 8. Politiques RLS : autoriser l'accès anonyme (via anon key)
CREATE POLICY IF NOT EXISTS "Allow anonymous access" ON public.sessions
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow anonymous access" ON public.chat_history
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow anonymous access" ON public.activity_logs
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow anonymous access" ON public.feedbacks
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow anonymous access" ON public.admin_settings
  FOR ALL USING (true) WITH CHECK (true);

-- 9. Vérification : colonnes sessions
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'sessions'
ORDER BY ordinal_position;
