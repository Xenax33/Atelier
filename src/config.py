"""Typed settings loaded from .env (see .env.example for every key).

Import `get_settings()` rather than instantiating Settings directly so the whole app
shares one validated instance.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Discord control plane
    discord_bot_token: str
    discord_guild_id: int
    discord_control_channel_id: int

    # Model gateway (OpenAI-compatible; llama-server for now)
    model_gateway_base_url: str = "http://127.0.0.1:8080/v1"
    model_gateway_api_key: str = "local-not-secret"
    primary_model: str = "qwen3-4b-instruct-2507"

    # ComfyUI (TASK-002)
    comfyui_base_url: str = "http://127.0.0.1:8188"

    # SearXNG (TASK-009; local instance in WSL, optional until deployed)
    searxng_base_url: str = "http://127.0.0.1:8888"

    # NASA ADS (R&D 4.6): free token from ui.adsabs.harvard.edu/user/settings/token.
    # Optional - the ads_search adapter stays dormant while this is empty.
    ads_api_token: str = ""

    # Paths
    state_dir: str = "./state"
    db_path: str = "./atelier.db"
    models_dir: str = "./models"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
