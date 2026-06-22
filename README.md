# StudyBoost AI 🚀

Transforme tes cours en fiches de révision, résumés et quiz avec l'intelligence artificielle.

## Fonctionnalités

- **📝 Éditeur de révision** — Résume, simplifie, crée des fiches et quiz
- **💬 Chat avec ton cours** — Pose des questions et obtiens des réponses contextualisées
- **🔍 Recherche web** — Synthèse IA des résultats web
- **📥 Export PDF/Markdown** — Télécharge tes fiches
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
- **IA** : Groq (Llama 3.1 8B)
- **Base de données** : Supabase (PostgreSQL)
- **Recherche web** : DuckDuckGo
- **PDF** : FPDF2

## Configuration

Copie `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et remplis les clés.

## Licence

MIT
