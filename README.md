# StudyBoost AI 🚀

Transforme tes cours en fiches de révision, résumés et quiz avec l'intelligence artificielle.

## Fonctionnalités

- **📝 Éditeur de révision** — Résume, simplifie, crée des fiches et quiz
- **💬 Chat avec ton cours** — Pose des questions et obtiens des réponses contextualisées
- **🔍 Recherche web** — Synthèse IA des résultats web
- **📥 Export PDF/Markdown** — Télécharge tes fiches (supporte emojis 🎓, accents français, markdown)
- **🔒 100% anonyme** — Aucune inscription requise
- **🗑️ Nettoyage automatique** — Données supprimées après 7 jours

## Installation locale

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
streamlit run app.py
```

## Tech Stack

- **Frontend** : Streamlit
- **Backend** : Python 3.12
- **IA** : OpenRouter (`openrouter/free`)
- **Base de données** : Neon (PostgreSQL)
- **Recherche web** : DuckDuckGo
- **PDF** : ReportLab (Noto Sans + Noto Emoji pour support Unicode complet)

## Configuration

En local, copie `.env.template` vers `.env` et remplis les valeurs.

Sur Streamlit Community Cloud, ouvre **Manage app → Settings → Secrets** et configure les clés au premier niveau :

```toml
DATABASE_URL = "postgresql://..."
OPENROUTER_API_KEY = "ta_cle_openrouter"
ADMIN_PASSWORD = "ton_mot_de_passe_admin"
```

Conserve tes valeurs de base de données et d'administration existantes. La clé Groq n'est plus utilisée. Enregistre les secrets puis redémarre l'application après le déploiement du nouveau code. Ne mets jamais de vraie clé dans GitHub.

Le menu du chat et de l’éditeur permet de choisir Google Gemma 4 31B, NVIDIA Nemotron 3.5 Lightning (variantes `:free`) ou la sélection automatique `openrouter/free`. Le modèle sélectionné est envoyé à OpenRouter pour les prochaines demandes. Le quota OpenRouter est partagé entre tous les utilisateurs et reste distinct des quotas affichés dans l'application. La disponibilité et les limites gratuites dépendent d'OpenRouter. Les erreurs techniques apparaissent aussi dans les logs Streamlit Cloud.

## Licence

MIT

## Identité et persistance

Chaque navigateur conserve un jeton aléatoire privé dans son stockage local. La base ne conserve que son empreinte SHA-256. Les URL et anciens paramètres `sid` ne donnent aucun accès aux historiques. Les onglets du même profil de navigateur partagent le même espace ; un autre navigateur ou profil reçoit un autre espace. Effacer le stockage du site ou utiliser « Nouvelle identité » crée un nouvel espace. Sans compte, cet espace ne peut pas être récupéré sur un autre appareil.

Les anciens espaces basés sur `sid` ne sont pas restaurés par cette version, afin de fermer l'accès par lien partagé. Aucune migration SQL n'est nécessaire. Configure explicitement `DATABASE_URL` avec la chaîne PostgreSQL Neon : l'ancienne variable `SUPABASE_URL` n'est plus acceptée. Dans le tableau de bord administrateur, le bouton de vérification contrôle la connexion et le schéma sans lire de conversations.

## Vérification du lot de stabilité (branche de prévisualisation)

La version `16-review` doit être validée séparément de `main` avant déploiement. Utiliser Python 3.12 et `pip install -r requirements.lock`, puis exécuter :

```bash
python -B -m unittest discover -s tests -v
node tests/test_browser_identity.cjs
```

Les tests Streamlit utilisent de vrais widgets avec une base et une IA simulées. Les tests de quotas concurrents utilisent un double transactionnel : une validation PostgreSQL sur une branche Neon de test reste nécessaire avant fusion. Ne pas utiliser de conversations réelles pour les essais.

Les réservations de quotas utilisent les tables existantes, sans migration SQL. Un plafond commun protège les appels IA même après un changement d'identité : 50 tentatives par jour, 20 par minute pour l'application, 3 par minute et par espace par défaut. Ces plafonds sont réglables dans l'administration. Ils ne remplacent pas les limites propres au compte OpenRouter. Les tentatives échouées comptent ; il n'y a plus de nouvelle tentative automatique dans les parcours de production. Les droits par modèle sont vérifiés au moment de chaque réservation. Sans accès à la base, les appels sont bloqués.

Le quota PDF compte les imports confirmés et les préparations de fichiers. Télécharger de nouveau le même fichier déjà préparé ne lance pas une nouvelle génération. Les imports sont limités à 5 Mo, 50 pages et 15 000 caractères extraits. L'aperçu ignore les images et le HTML actif ; le PDF échappe le HTML fourni. Les requêtes web et les extraits de questions ne sont plus enregistrés dans les détails d'activité.

Avant fusion : vérifier la connexion sur une base de test, deux profils de navigateur, la rotation d'identité, des réservations simultanées, un PDF invalide et deux fichiers de même nom, un export PDF/Word, l'expiration des données et les modes clair/sombre sur mobile et ordinateur. Les identifiants et clés restent uniquement dans les secrets de l'application de test.

## Dernières corrections (16-review)

La nouvelle présentation est intégrée à la branche de revue. L'effacement de conversation demande confirmation et ne vide l'écran qu'après succès en base. Les statistiques d'avis portent sur la période choisie ; leurs totaux ne dépendent pas des listes de détails limitées à 100 lignes.

Le titre du brouillon est conservé dans `sessions.draft_title`. L'éditeur initialise cette colonne par un `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` idempotent. Si le rôle PostgreSQL n'a pas le droit ALTER, un administrateur peut exécuter la dernière commande de `neon_migration.sql`. Aucune conversation n'est transférée ou réattribuée.

Le nettoyage est vérifié sur toutes les pages, au plus toutes les cinq minutes et exécuté au plus toutes les six heures. La date n'est mise à jour qu'après validation de toutes les suppressions. L'application inactive n'exécute pas de tâche : pour une échéance stricte, un planificateur externe peut appeler `python scripts/cleanup.py` avec `DATABASE_URL` dans son environnement. Aucun planificateur distant n'est configuré par le dépôt.

Les échecs de connexion administrateur sont comptés en base entre navigateurs ; cinq échecs verrouillent l'accès cinq minutes. Une authentification réussie expire après trente minutes.
