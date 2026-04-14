from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelConfig:
    id: str
    label: str
    api_key: str
    base_url: str
    model_name: str
    protocol: str


@dataclass(frozen=True)
class Settings:
    models: list[ModelConfig]

    def get_model(self, model_id: str) -> ModelConfig:
        for model in self.models:
            if model.id == model_id:
                return model
        raise KeyError(f"Unknown model: {model_id}")


def _build_model(
    prefix: str, model_id: str, label: str, protocol: str
) -> ModelConfig | None:
    api_key = os.getenv(f"{prefix}_API_KEY", "").strip()
    base_url = os.getenv(f"{prefix}_BASE_URL", "").strip()
    model_name = os.getenv(f"{prefix}_MODEL", "").strip()
    if not (api_key and base_url and model_name):
        return None
    return ModelConfig(
        id=model_id,
        label=label,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        protocol=protocol,
    )


def load_settings(load_env: bool = True) -> Settings:
    if load_env:
        load_dotenv()
    models = [
        model
        for model in (
            _build_model("LLM_GLM", "glm", "GLM", "anthropic"),
            _build_model("LLM_OPENAI", "openai", "OpenAI Compatible", "openai"),
        )
        if model is not None
    ]
    if not models:
        raise RuntimeError(
            "No LLM models configured. Set LLM_GLM_* or LLM_OPENAI_* env vars."
        )
    return Settings(models=models)


def load_conversation_config(load_env: bool = True) -> dict[str, int]:
    if load_env:
        load_dotenv()
    return {
        "max_messages": int(os.getenv("CONV_MAX_MESSAGES", "50")),
        "ttl_seconds": int(os.getenv("CONV_TTL_SECONDS", "3600")),
        "max_conversations": int(os.getenv("CONV_MAX_CONVERSATIONS", "1000")),
    }
