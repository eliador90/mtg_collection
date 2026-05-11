from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from deck_generation import DeckGenerationResult, build_ai_prompt, generate_local_deck_draft


@dataclass
class DeckDraftRequest:
    collection_path: str
    commander_name: str
    target_size: int = 100
    land_count: int | None = None
    theme: str = ""
    model: str = ""


class DeckDraftProvider(ABC):
    name: str
    requires_api_key: bool = False

    @abstractmethod
    def draft_deck(self, request: DeckDraftRequest) -> DeckGenerationResult:
        raise NotImplementedError


class LocalHeuristicProvider(DeckDraftProvider):
    name = "local"
    requires_api_key = False

    def draft_deck(self, request: DeckDraftRequest) -> DeckGenerationResult:
        return generate_local_deck_draft(
            collection_path=request.collection_path,
            commander_name=request.commander_name,
            target_size=request.target_size,
            land_count=request.land_count,
            theme=request.theme,
        )


class OpenAIProvider(DeckDraftProvider):
    name = "openai"
    requires_api_key = True
    endpoint = "https://api.openai.com/v1/responses"
    default_model = "gpt-5.2"

    def draft_deck(self, request: DeckDraftRequest) -> DeckGenerationResult:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Create an OpenAI API key and set it before using --provider openai.")

        local_result = generate_local_deck_draft(
            collection_path=request.collection_path,
            commander_name=request.commander_name,
            target_size=request.target_size,
            land_count=request.land_count,
            theme=request.theme,
        )
        prompt = build_openai_prompt(local_result, collection_path=request.collection_path)
        model = request.model or os.environ.get("OPENAI_MODEL", "").strip() or self.default_model

        print(f"Using OpenAI provider with model {model}. This may create API charges on your OpenAI account.")
        response_text = call_openai_responses_api(self.endpoint, api_key, model, prompt)
        deck = parse_deck_json_response(response_text)
        deck = normalize_ai_deck(deck, local_result.deck, model)
        return DeckGenerationResult(
            deck=deck,
            selected_cards=local_result.selected_cards,
            maybeboard=local_result.maybeboard,
            candidate_pool=local_result.candidate_pool,
        )


class ApiProviderNotImplemented(DeckDraftProvider):
    requires_api_key = True

    def draft_deck(self, request: DeckDraftRequest) -> DeckGenerationResult:
        raise NotImplementedError(
            f"The '{self.name}' provider is a planned extension point, but API-based deck generation is not implemented yet. "
            "Use the local provider, OpenAI provider, or AI prompt export for manual refinement."
        )


class AnthropicProvider(ApiProviderNotImplemented):
    name = "anthropic"


class OpenRouterProvider(ApiProviderNotImplemented):
    name = "openrouter"


class OllamaProvider(ApiProviderNotImplemented):
    name = "ollama"
    requires_api_key = False


PROVIDERS: dict[str, type[DeckDraftProvider]] = {
    "local": LocalHeuristicProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def create_provider(name: str) -> DeckDraftProvider:
    normalized = name.strip().lower()
    if normalized not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown deck draft provider '{name}'. Known providers: {known}")
    return PROVIDERS[normalized]()


def provider_names() -> list[str]:
    return sorted(PROVIDERS)


def build_openai_prompt(local_result: DeckGenerationResult, collection_path: str = "") -> str:
    return (
        build_ai_prompt(local_result, collection_path=collection_path)
        + "\n\n"
        + "OpenAI provider instructions:\n"
        + "- Return only a single valid JSON object.\n"
        + "- Do not wrap the JSON in Markdown fences.\n"
        + "- Keep the same deck JSON shape: name, commander, generation, refinement, cards.\n"
        + "- Keep the requested deck size and Commander color identity legal.\n"
        + "- Prefer cards from the candidate pool. Put outside-card ideas only in refinement.upgrade_suggestions.\n"
    )


def call_openai_responses_api(endpoint: str, api_key: str, model: str, prompt: str) -> str:
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "instructions": (
                "You are a careful Magic: The Gathering Commander deckbuilding assistant. "
                "Return only valid JSON matching the requested deck format."
            ),
            "input": prompt,
            "max_output_tokens": 12000,
        },
        timeout=120,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI API request failed with HTTP {response.status_code}: {response.text[:500]}")
    payload = response.json()
    text = extract_response_text(payload)
    if not text:
        raise RuntimeError("OpenAI API response did not contain text output.")
    return text


def extract_response_text(payload: dict) -> str:
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def parse_deck_json_response(response_text: str) -> dict:
    cleaned = response_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    elif not cleaned.startswith("{"):
        object_match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if object_match:
            cleaned = object_match.group(1)

    try:
        deck = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI response was not valid deck JSON: {exc}") from exc
    if not isinstance(deck, dict):
        raise RuntimeError("OpenAI response must be a JSON object.")
    if not isinstance(deck.get("commander"), dict) or not isinstance(deck.get("cards"), list):
        raise RuntimeError("OpenAI response must include commander and cards fields.")
    return deck


def normalize_ai_deck(deck: dict, local_deck: dict, model: str) -> dict:
    updated = dict(deck)
    updated.setdefault("name", f"{local_deck['commander']['name']} - OpenAI Draft")
    updated.setdefault("commander", local_deck["commander"])
    updated.setdefault("cards", [])

    generation = dict(local_deck.get("generation", {}))
    generation.update(dict(updated.get("generation", {})))
    generation["method"] = "openai_api"
    generation["provider"] = "openai"
    generation["model"] = model
    notes = list(generation.get("notes", []))
    notes.append("Generated through the OpenAI API from a filtered local candidate pool. API usage may cost money.")
    generation["notes"] = list(dict.fromkeys(notes))
    updated["generation"] = generation

    refinement = dict(updated.get("refinement", {}))
    refinement.setdefault("maybeboard", local_deck.get("refinement", {}).get("maybeboard", []))
    refinement.setdefault("cut_candidates", [])
    refinement.setdefault("upgrade_suggestions", [])
    updated["refinement"] = refinement
    return updated
