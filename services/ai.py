"""OpenRouter-based AI helpers for StudyBoost AI."""
from __future__ import annotations

import os
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import time
from typing import Literal

from dotenv import load_dotenv
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
    "🆓 OpenRouter — sélection gratuite automatique": "openrouter/free",
    "🟢 Google Gemma 4 31B — gratuit": "google/gemma-4-31b-it:free",
    "🟢 NVIDIA Nemotron 3.5 Lightning — gratuit": "nvidia/nemotron-3.5-lightning:free",
}

DEFAULT_MODEL = "openrouter/free"

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
    except (FileNotFoundError, KeyError):
        key = None
    if not key:
        key = os.environ.get(name)
    if not isinstance(key, str) or not key.strip():
        raise StudyBoostAIError(
            f"Configure {name} dans les secrets Streamlit Cloud, puis redémarre l'application.",
            "config",
        )
    return key.strip()


def _api_error(status: int) -> StudyBoostAIError:
    errors = {
        400: ("Requête refusée par OpenRouter. Réduis la taille du texte.", "bad_request"),
        401: ("Clé OpenRouter invalide ou révoquée. Vérifie OPENROUTER_API_KEY dans les secrets.", "auth"),
        402: ("OpenRouter refuse la requête pour une limite de crédits ou de compte.", "credits"),
        403: ("Accès refusé par OpenRouter. Vérifie les autorisations et paramètres de confidentialité du compte.", "permission"),
        404: ("Le modèle demandé est indisponible sur OpenRouter.", "model_unavailable"),
        408: ("OpenRouter a mis trop de temps à répondre.", "timeout"),
        429: ("Limite OpenRouter atteinte. Le quota gratuit est partagé par tous les utilisateurs de l'application.", "rate_limit"),
        502: ("Le fournisseur IA est temporairement indisponible.", "unavailable"),
        503: ("Aucun fournisseur IA disponible pour cette requête. Réessaie plus tard.", "unavailable"),
        504: ("Le fournisseur IA a mis trop de temps à répondre.", "timeout"),
    }
    message, code = errors.get(status, ("OpenRouter a rencontré une erreur. Réessaie plus tard.", "unknown"))
    return StudyBoostAIError(message, code)


def _call_openrouter(messages, model=DEFAULT_MODEL, temperature=0.3, max_tokens=3000, max_retries=0):
    key = _get_key("OPENROUTER_API_KEY")
    # Never route to a paid model, including through a stale saved preference.
    if model not in AVAILABLE_MODELS.values():
        raise StudyBoostAIError("Ce modèle n'est plus proposé. Recharge la page et sélectionne OpenRouter gratuit.", "model_unavailable")
    payload = json.dumps({
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens, "stream": False,
    }).encode("utf-8")
    request = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=60) as response:
                data = json.load(response)
            # OpenRouter may report a provider error inside an HTTP 200 response.
            if "error" in data:
                try:
                    status = int(data["error"].get("code", 500))
                except (TypeError, ValueError, AttributeError):
                    status = 500
                logger.error("OpenRouter provider error status=%s model=%s", status, model)
                raise _api_error(status)
            content = data["choices"][0]["message"].get("content")
            if not isinstance(content, str) or not content.strip():
                raise StudyBoostAIError("L'IA n'a pas généré de texte. Réessaie avec une demande plus courte.", "empty")
            return content.strip()
        except HTTPError as e:
            status = e.code
            e.close()
            # Log status only: provider bodies may echo private input or credentials.
            logger.error("OpenRouter HTTP status=%s model=%s attempt=%s", status, model, attempt + 1)
            if status in (502, 503, 504) and attempt < max_retries:
                time.sleep(2)
                continue
            raise _api_error(status) from None
        except (TimeoutError, socket.timeout):
            raise StudyBoostAIError("L'IA a mis trop de temps à répondre. Réessaie plus tard.", "timeout") from None
        except URLError:
            logger.warning("OpenRouter connection failed model=%s", model)
            raise StudyBoostAIError("Impossible de joindre OpenRouter. Réessaie plus tard.", "network") from None
        except StudyBoostAIError:
            raise
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            logger.error("OpenRouter invalid response model=%s", model)
            raise StudyBoostAIError("Réponse OpenRouter invalide. Réessaie plus tard.", "unknown") from None


def format_text(
    text: str,
    style: Literal["resume", "simplify", "fiche", "academic", "bullet_points", "quiz"],
    model: str = DEFAULT_MODEL,
) -> str:
    system = "Tu es un assistant pédagogique expert. Tu réponds toujours en français avec un format Markdown propre et structuré."
    prompt = f"{STYLE_PROMPTS[style]}\n\n---\n\n{text}"
    result = _call_openrouter(
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
    prior = history[:-1] if history and history[-1].get("role") == "user" and history[-1].get("content") == question else history
    for msg in prior[-10:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": question})
    return _call_openrouter(messages, model=model, temperature=0.4)


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
    return _call_openrouter(
        [{"role": "system", "content": system}, {"role": "user", "content": content}],
        model=model, temperature=0.4,
    )


def _fmt_results(results):
    if not results:
        return "Aucun résultat trouvé."
    return "\n\n".join(
        f"{i}. {r.get('title', 'Sans titre')}\n   URL : {r.get('href', '')}\n   {r.get('body', '')[:300]}"
        for i, r in enumerate(results, 1)
    )
