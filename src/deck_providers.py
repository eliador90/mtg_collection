from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from deck_generation import DeckGenerationResult, generate_local_deck_draft


@dataclass
class DeckDraftRequest:
    collection_path: str
    commander_name: str
    target_size: int = 100
    land_count: int | None = None
    theme: str = ""


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


class ApiProviderNotImplemented(DeckDraftProvider):
    requires_api_key = True

    def draft_deck(self, request: DeckDraftRequest) -> DeckGenerationResult:
        raise NotImplementedError(
            f"The '{self.name}' provider is a planned extension point, but API-based deck generation is not implemented yet. "
            "Use the local provider plus --prompt-output for manual AI refinement."
        )


class OpenAIProvider(ApiProviderNotImplemented):
    name = "openai"


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
