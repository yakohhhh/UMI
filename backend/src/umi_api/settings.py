"""Runtime configuration, read from `UMI_*` environment variables."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UMI_", extra="ignore")

    env: Environment = Environment.DEV
    # Resolved against backend/ so `umi-api` behaves the same from any working directory.
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'umi-dev.db'}"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Rider used when a request has no Authorization header (dev and test only).
    dev_default_athlete: str = "laia"
    # City Insights account whose API keys /v1/account/usage reports (dev and test only).
    dev_default_city_account: str = "ajuntament-bcn"
    # Sessions recorded with simulated sensor drivers (header flag `simulated`).
    accept_simulated: bool | None = None
    # Recompute the hourly scores of the streets a ride went through as soon as it is
    # ingested. Cheap (a few segments), but production runs `umi-api aggregate` on a
    # schedule instead, so uploads never contend on the published scores.
    aggregate_on_ingest: bool | None = None
    # Seeded demo data is a snapshot; pinning "now" to it keeps "this week" and
    # "last 7 days" in step with it, exactly like the web mocks' mockNow().
    pin_clock_to_dataset: bool | None = None
    mock_data_dir: Path = REPO_ROOT / "src" / "lib" / "mock" / "data"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _environment_defaults(self) -> Self:
        production = self.env is Environment.PRODUCTION
        if self.accept_simulated is None:
            self.accept_simulated = not production
        if self.aggregate_on_ingest is None:
            self.aggregate_on_ingest = not production
        if self.pin_clock_to_dataset is None:
            self.pin_clock_to_dataset = not production
        return self

    @property
    def is_production(self) -> bool:
        return self.env is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
