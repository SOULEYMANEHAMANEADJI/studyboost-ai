"""Groq-based AI helpers for StudyBoost AI."""
from __future__ import annotations

import os
import time
from typing import Literal

from dotenv import load_dotenv
from groq import RateLimitError, APITimeoutError, APIConnectionError, AuthenticationError, BadRequestError
import streamlit as st

from services.logger import get_logger

load_dotenv()

logger = get_logger("ai")


class StudyBoostAIError(RuntimeError):
    """Erreur métier liée à l'IA avec code catégorie."""
    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.code = code

AVAILABLE_MODELS = {
    "⚡ Llama 3.1 8B (Rapide - Recommandé)": "llama-3.1-8b-instant",
    "🧠 Llama 3.3 70B (Puissant)": "llama-3.3-70b-versatile",
    "🦙 Llama 4 Scout 17B (Polyvalent)": "meta-llama/llama-4-scout-17b-16e-instruct",
    "🔬 Qwen 3 32B (Long texte)": "qwen/qwen3-32b",
}

DEFAULT_MODEL = "llama-3.1-8b-instant"

STYLE_PROMPTS = {
    "resume": (
        "Résume STRICTEMENT le texte ci-dessous. "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
    "simplify": (
        "Simplifie STRICTEMENT le texte ci-dessous pour qu'il soit compréhensible par un enfant de 12 ans. "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
    "fiche": (
        "Transforme STRICTEMENT le texte ci-dessous en une fiche de révision complète en français. "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
    "academic": (
        "Réécris STRICTEMENT le texte ci-dessous dans un style académique rigoureux en français. "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
    "bullet_points": (
        "Extrais STRICTEMENT les points clés du texte ci-dessous sous forme de liste à puces en français. "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
    "quiz": (
        "Crée STRICTEMENT un quiz de révision à partir du texte ci-dessous. "
        "Propose 5 questions avec leurs réponses en français, au format Markdown (Q1, R1, etc.). "
        "Ne génère AUCUNE information qui n'est pas dans le texte. "
        "Si le texte est insuffisant ou incompréhensible, réponds exactement : "
        '"⚠️ Le texte fourni est trop court ou incompréhensible pour cette action."'
    ),
}


def _get_key(name: str) -> str:
    try:
        key = st.secrets.get(name)
    except Exception as e:
        logger.warning("_get_key: échec st.secrets pour %s, fallback os.environ", name, exc_info=e)
        key = None
    if not key:
        key = os.environ.get(name)
    if not key:
        raise RuntimeError(f"{name} manquant.")
    return key


@st.cache_resource
def get_groq_client():
    from groq import Groq
    return Groq(api_key=_get_key("GROQ_API_KEY"))


def _call_groq(messages, model=DEFAULT_MODEL, temperature=0.3, max_tokens=3000, max_retries=2):
    client = get_groq_client()

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
                timeout=60,
            )
            return response.choices[0].message.content.strip()

        except RateLimitError:
            if attempt < max_retries:
                wait = 3
                logger.warning("_call_groq: RateLimitError modèle=%s, tentative %d/%d, attente %ds",
                               model, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise StudyBoostAIError("⏳ Trop de demandes. Attends 30 secondes et réessaie.", "rate_limit")

        except APITimeoutError:
            if attempt < max_retries:
                wait = 2
                logger.warning("_call_groq: APITimeoutError modèle=%s, tentative %d/%d, attente %ds",
                               model, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise StudyBoostAIError("⏱️ L'IA met trop de temps à répondre. Réessaie avec un texte plus court.", "timeout")

        except APIConnectionError:
            if attempt < max_retries:
                wait = 2
                logger.warning("_call_groq: APIConnectionError modèle=%s, tentative %d/%d, attente %ds",
                               model, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise StudyBoostAIError("📡 Vérifie ta connexion internet.", "network")

        except AuthenticationError:
            raise StudyBoostAIError("🔑 Erreur d'authentification. Contacte le support.", "auth")

        except BadRequestError:
            raise StudyBoostAIError("⚠️ Requête invalide. Le texte est peut-être trop long pour ce modèle.", "bad_request")

        except Exception:
            logger.error("_call_groq: échec inattendu modèle=%s (tentative %d/%d)", model, attempt + 1, max_retries, exc_info=True)
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise StudyBoostAIError("❌ Une erreur inattendue s'est produite. Réessaie.", "unknown")


def format_text(
    text: str,
    style: Literal["resume", "simplify", "fiche", "academic", "bullet_points", "quiz"],
    model: str = DEFAULT_MODEL,
) -> str:
    system = "Tu es un assistant pédagogique expert. Tu réponds toujours en français avec un format Markdown propre et structuré."
    prompt = f"{STYLE_PROMPTS[style]}\n\n---\n\n{text}"
    result = _call_groq(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        model=model, temperature=0.3,
    )
    if not result.strip():
        raise StudyBoostAIError("🤔 L'IA n'a pas pu générer de réponse. Reformule ton texte.", "empty")
    return result


def chat_response(context: str, question: str, history: list, model: str = DEFAULT_MODEL) -> str:
    system = (
        "Tu es StudyBoost AI, un tuteur pédagogique bienveillant.\n\n"
        "## Règles de formatage OBLIGATOIRES :\n"
        "- Utilise TOUJOURS un Markdown riche et structuré.\n"
        "- Commence par un **résumé en 1-2 lignes** en gras.\n"
        "- Utilise des **titres (##, ###)** pour organiser ta réponse en sections.\n"
        "- Utilise des **listes à puces (-)** pour les points clés.\n"
        "- Utilise le **gras (**) pour les termes importants**.\n"
        "- Si pertinent, ajoute un **exemple concret** ou une **analogie**.\n"
        "- Termine par un **résumé / takeaway** en 1-2 lignes.\n"
        "- Ne génère JAMAIS de bloc de texte brut sans mise en forme.\n"
        "- Base ta réponse uniquement sur le cours fourni. Si le contexte est insuffisant, dis-le clairement.\n"
        "- Réponds toujours en français."
    )
    messages = [{"role": "system", "content": system}]
    if context.strip():
        messages.append({"role": "user", "content": f"Voici mon cours (contexte) :\n\n{context[:8000]}"})
    else:
        messages.append({"role": "system", "content": "Tu réponds comme assistant général sans contexte spécifique."})
    for msg in history[-10:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": question})
    return _call_groq(messages, model=model, temperature=0.4)


def chat_with_search(question: str, search_results: list, context: str = "", model: str = DEFAULT_MODEL) -> str:
    system = (
        "Tu es StudyBoost AI. Tu réponds en français.\n\n"
        "## Règles de formatage OBLIGATOIRES :\n"
        "- Utilise TOUJOURS un Markdown riche et structuré.\n"
        "- Commence par un **résumé en 1-2 lignes** en gras.\n"
        "- Utilise des **titres (##, ###)** pour organiser ta réponse en sections.\n"
        "- Utilise des **listes à puces (-)** pour les points clés.\n"
        "- Utilise le **gras (**) pour les termes importants**.\n"
        "- Si pertinent, ajoute un **exemple concret** ou une **analogie**.\n"
        "- Cite les **sources** avec des liens si possible.\n"
        "- Termine par un **résumé / takeaway** en 1-2 lignes.\n"
        "- Ne génère JAMAIS de bloc de texte brut sans mise en forme.\n"
        "- Base ta réponse sur les résultats de recherche web fournis."
    )
    formatted = _fmt_results(search_results)
    content = f"Question : {question}\n\nRésultats de recherche web :\n{formatted}\n\n"
    if context.strip():
        content += f"Contexte du cours de l'utilisateur :\n{context[:4000]}"
    return _call_groq(
        [{"role": "system", "content": system}, {"role": "user", "content": content}],
        model=model, temperature=0.4,
    )


def _fmt_results(results):
    if not results:
        return "Aucun résultat trouvé."
    return "\n\n".join(
        f"{i}. {r.get('title', 'Sans titre')}\n   {r.get('body', '')[:300]}"
        for i, r in enumerate(results, 1)
    )
