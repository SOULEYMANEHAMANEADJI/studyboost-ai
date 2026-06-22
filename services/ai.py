"""Multi-provider AI helpers for StudyBoost AI — Groq + Google Gemini."""
from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

AVAILABLE_MODELS = {
    "⚡ Llama 3.1 8B (Rapide)": "llama-3.1-8b-instant",
    "🧠 Llama 3.3 70B (Puissant)": "llama-3.3-70b-versatile",
    "💎 Gemma 2 9B (Google)": "gemma2-9b-it",
    "🔬 Mixtral 8x7B (Expert)": "mixtral-8x7b-32768",
    "🚀 Llama 3.2 11B (Équilibré)": "llama-3.2-11b-text-preview",
    "🏃 Llama 3.2 3B (Léger)": "llama-3.2-3b-text-preview",
    "🧮 DeepSeek R1 70B (Raisonnement)": "deepseek-r1-distill-llama-70b",
    "🌐 Qwen 2.5 32B (Général)": "qwen-2.5-32b",
    "🌟 Gemini 1.5 Flash (Google)": "gemini-1.5-flash",
}

MODEL_PROVIDERS: dict[str, str] = {mid: "groq" for mid in AVAILABLE_MODELS.values()}
MODEL_PROVIDERS["gemini-1.5-flash"] = "google"

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


# ---------------------------------------------------------------------------
#  Groq
# ---------------------------------------------------------------------------

def _get_groq_key() -> str:
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if not key:
        key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY manquant.")
    return key


def _call_groq(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> str:
    from groq import Groq

    client = Groq(api_key=_get_groq_key())
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
#  Google Gemini
# ---------------------------------------------------------------------------

def _get_google_key() -> str:
    try:
        key = st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        key = None
    if not key:
        key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY manquant.")
    return key


def _call_gemini(
    messages: list[dict[str, str]],
    model: str = "gemini-1.5-flash",
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> str:
    import google.generativeai as genai

    genai.configure(api_key=_get_google_key())

    system_prompt = ""
    contents: list[dict] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_prompt += content + "\n"
        elif role == "user":
            contents.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [content]})

    if not contents:
        contents = [{"role": "user", "parts": ["Bonjour"]}]

    gen_model = genai.GenerativeModel(
        model,
        system_instruction=system_prompt.strip() or None,
    )
    response = gen_model.generate_content(
        contents,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


# ---------------------------------------------------------------------------
#  Router
# ---------------------------------------------------------------------------

def _call_ai(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> str:
    provider = MODEL_PROVIDERS.get(model, "groq")
    if provider == "google":
        return _call_gemini(messages, model, temperature, max_tokens)
    return _call_groq(messages, model, temperature, max_tokens)


# ---------------------------------------------------------------------------
#  Public helpers
# ---------------------------------------------------------------------------

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
    return _call_ai(
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
    messages: list[dict[str, str]] = [
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
    return _call_ai(messages, model=model, temperature=0.4)


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
    return _call_ai(
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
