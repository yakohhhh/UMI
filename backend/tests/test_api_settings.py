"""Configuration from UMI_* environment variables."""

import pytest
from umi_api.db.migrate import sync_url
from umi_api.settings import BACKEND_DIR, Environment, Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("UMI_ENV", "UMI_DATABASE_URL", "UMI_CORS_ORIGINS", "UMI_ACCEPT_SIMULATED", "UMI_AGGREGATE_ON_INGEST"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.env is Environment.DEV
    assert settings.database_url == f"sqlite+aiosqlite:///{BACKEND_DIR / 'umi-dev.db'}"
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.dev_default_athlete == "laia"
    assert settings.accept_simulated is True
    assert settings.aggregate_on_ingest is True
    assert settings.pin_clock_to_dataset is True
    assert (settings.mock_data_dir / "activities.json").is_file()


def test_production_refuses_simulated_clips_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMI_ENV", "production")
    monkeypatch.delenv("UMI_ACCEPT_SIMULATED", raising=False)
    monkeypatch.delenv("UMI_AGGREGATE_ON_INGEST", raising=False)
    settings = Settings()
    assert settings.is_production
    assert settings.accept_simulated is False
    # Scores are aggregated on a schedule, not by each upload.
    assert settings.aggregate_on_ingest is False
    assert settings.pin_clock_to_dataset is False


def test_cors_origins_from_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMI_CORS_ORIGINS", "http://localhost:3000, https://umi.example")
    assert Settings().cors_origins == ["http://localhost:3000", "https://umi.example"]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite+aiosqlite:////tmp/umi.db", "sqlite:////tmp/umi.db"),
        ("postgresql+psycopg://umi:p%40ss@db:5432/umi", "postgresql+psycopg://umi:p%40ss@db:5432/umi"),
        ("postgresql://umi@db/umi", "postgresql+psycopg://umi@db/umi"),
    ],
)
def test_migrations_use_the_synchronous_driver(url: str, expected: str) -> None:
    assert sync_url(url) == expected
