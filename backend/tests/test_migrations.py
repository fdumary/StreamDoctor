import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect

from app.core.config import Settings


def test_migration_matches_models_and_reverses(client):
    config = Config("alembic.ini")
    command.check(config)
    command.downgrade(config, "base")
    assert "users" not in inspect(client.app.state.engine).get_table_names()
    assert client.get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    assert client.get("/health/ready").status_code == 200


def test_postgresql_url_normalization():
    settings = Settings(_env_file=None, database_url="postgresql://user:pass@localhost/test")
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_production_requires_postgres():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", database_url="sqlite:///test.db")
