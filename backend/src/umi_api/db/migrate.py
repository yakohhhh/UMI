"""Alembic, driven from code (`umi-api migrate`, tests) and from backend/alembic.ini."""

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from umi_api.settings import BACKEND_DIR

MIGRATIONS_DIR = BACKEND_DIR / "migrations"

# Migrations run on the synchronous driver of the same database: no event loop
# to manage, and the same code path from the CLI, the tests and plain `alembic`.
_SYNC_DRIVERS = {"sqlite": "sqlite", "postgresql": "postgresql+psycopg"}


def sync_url(database_url: str) -> str:
    url = make_url(database_url)
    return url.set(drivername=_SYNC_DRIVERS.get(url.get_backend_name(), url.drivername)).render_as_string(
        hide_password=False
    )


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # ConfigParser interpolates "%": URL-encoded passwords must be escaped.
    config.set_main_option("sqlalchemy.url", sync_url(database_url).replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)
