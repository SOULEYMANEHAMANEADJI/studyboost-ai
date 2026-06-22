"""Groq-based AI helpers for StudyBoost AI."""
from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
import streamlit as st
from groq import Groq

load_dotenv()

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
    """Build a Groq client from secrets or environment."""
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
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> str:
    """Call Groq with the given messages and return the assistant message."""
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def format_text(text: str, style: Literal[
    "resume", "simplify", "fiche", "academic", "bullet_points", "quiz"
]) -> str:
    """Transform a user text into the requested style."""
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
        temperature=0.3,
    )


def chat_response(
    context: str, question: str, history: list[dict[str, str]]
) -> str:
    """Answer a question using the provided course context."""
    system = (
        "Tu es StudyBoost AI, un tuteur pédagogique bienveillant. Tu réponds "
        "toujours en français avec du Markdown. Base ta réponse uniquement sur "
        "le cours fourni par l'utilisateur. Si le contexte est insuffisant, "
        "dis-le clairement et demande des précisions."
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Voici mon cours :\n\n{context[:8000]}\n\nMerci de l'avoir lu. Réponds maintenant aux questions suivantes.",
        },
    ]
    for msg in history[-10:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    messages.append({"role": "user", "content": question})
    return _call_groq(messages, temperature=0.4)


def chat_with_search(
    question: str, search_results: str, context: str
) -> str:
    """Synthesize web search results to answer a question."""
    system = (
        "Tu es StudyBoost AI. Tu réponds en français avec du Markdown. "
        "Utilise les résultats de recherche web fournis pour répondre de façon "
        "précise. Mentionne les sources si possible."
    )
    content = (
        f"Question : {question}\n\n"
        f"Résultats de recherche web :\n{search_results}\n\n"
        f"Contexte du cours de l'utilisateur (si utile) :\n{context[:4000]}"
    )
    return _call_groq(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        temperature=0.4,
    )
