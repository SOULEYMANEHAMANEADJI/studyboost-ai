"""Groq-based AI helpers for StudyBoost AI — multi-modèles."""
from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
import streamlit as st
from groq import Groq

load_dotenv()

AVAILABLE_MODELS = {
    "⚡ Llama 3.1 8B (Rapide)": "llama-3.1-8b-instant",
    "🧠 Llama 3.3 70B (Puissant)": "llama-3.3-70b-versatile",
    "💎 Gemma 2 9B (Google)": "gemma2-9b-it",
    "🔬 Mixtral 8x7B (Expert)": "mixtral-8x7b-32768",
    "🚀 Llama 3.2 11B (Équilibré)": "llama-3.2-11b-text-preview",
}

DEFAULT_MODEL = "llama-3.1-8b-instant"

STYLE_PROMPTS = {
    "resume": (
        "Résume le texte suivant de manière claire et structurée en français. "
        "Utilise des paragraphes et des listes à puces si pertinent."
    ),
    "simplify": (
        "Simplifie le texte suivant pour qu'il soit compréhensible par un enfant de 12 ans. "
        "Utilise un vocabulaire simple, des phrases courtes et des exemples concrets. Réponds en français."
    ),
    "fiche": (
        "Transforme le texte suivant en une fiche de révision complète en français. "
        "Inclus : définitions importantes, idées clés, formules ou dates si pertinent, et une checklist finale."
    ),
    "academic": (
        "Réécrit le texte suivant dans un style académique rigoureux en français. "
        "Structure l'argumentation, utilise un vocabulaire soutenu, et conserve les idées essentielles."
    ),
    "bullet_points": (
        "Extrais les points clés du texte suivant sous forme de liste à puces en français. "
        "Sois concis et hiérarchise les informations."
    ),
    "quiz": (
        "Crée un quiz de révision à partir du texte suivant. "
        "Propose 5 questions avec leurs réponses en français, au format Markdown (Q1, R1, etc.)."
    ),
}


def _get_client() -> Groq:
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY manquant.")
    return Groq(api_key=api_key)


def _call_groq(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def format_text(
    text: str,
    style: Literal["resume", "simplify", "fiche", "academic", "bullet_points", "quiz"],
    model: str = DEFAULT_MODEL,
) -> str:
    system = (
        "Tu es un assistant pédagogique expert. Tu réponds toujours en français "
        "avec un format Markdown propre et structuré."
    )
    prompt = f"{STYLE_PROMPTS[style]}\n\n---\n\n{text}"
    return _call_groq(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.3,
    )


def chat_response(
    context: str,
    question: str,
    history: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
) -> str:
    system = (
        "Tu es StudyBoost AI, un tuteur pédagogique bienveillant. Tu réponds "
        "toujours en français avec du Markdown. Base ta réponse uniquement sur "
        "le cours fourni par l'utilisateur. Si le contexte est insuffisant, "
        "dis-le clairement et demande des précisions."
    )
    messages = [
        {"role": "system", "content": system},
    ]
    if context.strip():
        messages.append({
            "role": "user",
            "content": f"Voici mon cours (contexte) :\n\n{context[:8000]}",
        })
    else:
        messages.append({
            "role": "system",
            "content": "Tu réponds comme assistant général sans contexte spécifique.",
        })
    for msg in history[-10:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    messages.append({"role": "user", "content": question})
    return _call_groq(messages, model=model, temperature=0.4)


def chat_with_search(
    question: str,
    search_results: list[dict[str, str]],
    context: str,
    model: str = DEFAULT_MODEL,
) -> str:
    system = (
        "Tu es StudyBoost AI. Tu réponds en français avec du Markdown. "
        "Utilise les résultats de recherche web fournis pour répondre de façon "
        "précise. Mentionne les sources si possible."
    )
    formatted = _fmt_results(search_results)
    content = (
        f"Question : {question}\n\n"
        f"Résultats de recherche web :\n{formatted}\n\n"
    )
    if context.strip():
        content += f"Contexte du cours de l'utilisateur :\n{context[:4000]}"
    return _call_groq(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        model=model,
        temperature=0.4,
    )


def _fmt_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "Aucun résultat trouvé."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', 'Sans titre')}\n   {r.get('body', '')[:300]}")
    return "\n\n".join(lines)
