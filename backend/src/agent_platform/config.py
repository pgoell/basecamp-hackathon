"""Runtime settings, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where agents/, skills/, teams/ and knowledge/ live. Mount over this in
    # Docker to edit agents without rebuilding the image.
    catalog_dir: Path = _BACKEND_ROOT / "catalog"
    # Where canvases are persisted (mount a volume here in Docker).
    state_dir: Path = _BACKEND_ROOT / ".state"
    # Which agent runtime executes team runs (see agent_platform.agents).
    orchestrator: str = "dummy"
    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
