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
- **Backend** : Python 3.11+
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
