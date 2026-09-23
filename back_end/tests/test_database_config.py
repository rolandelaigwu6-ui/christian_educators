"""Database-URL configuration tests.

`DATABASE_URL` was a hardcoded literal, so a deployment had no way to point the app at a
managed database without editing source. It is now read from the environment like every
other setting.

Half of this file guards a trap that only appears once a non-SQLite URL is actually used:
`check_same_thread` is a SQLite-only connect argument, and `create_engine` raises
`TypeError` when it is handed to any other driver. Getting that wrong turns a one-line
configuration change into a startup crash in the environment least convenient to debug.

`back_end.py` captures its configuration at import time, so these tests control the
environment and reimport the module (same pattern as test_env_loading.py).
"""

import importlib
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

BACK_END_DIR = Path(__file__).resolve().parents[1]
if str(BACK_END_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_END_DIR))

DEFAULT_DATABASE_URL = "sqlite:///./christian_educators.db"
PRODUCTION_DATABASE_URL = "sqlite:////srv/cegnp/production.db"


def load_module(tmp_path, monkeypatch, database_url=None):
    """Import back_end against a throwaway .env, never the developer's real one."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "" if database_url is None else f"DATABASE_URL={database_url}\n",
        encoding="utf-8",
    )

    # Nothing may leak in from the ambient environment.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_file))

    import back_end

    return importlib.reload(back_end)


def test_database_url_comes_from_configuration(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch, database_url=PRODUCTION_DATABASE_URL)

    assert module.DATABASE_URL == PRODUCTION_DATABASE_URL


def test_the_engine_is_built_from_the_configured_url(tmp_path, monkeypatch):
    """Reading the setting is not the same as using it.

    Compared as URL objects rather than rendered strings, so the assertion does not
    depend on how SQLAlchemy chooses to spell a path back out.
    """
    module = load_module(tmp_path, monkeypatch, database_url=PRODUCTION_DATABASE_URL)

    assert module.engine.url == make_url(PRODUCTION_DATABASE_URL)


def test_database_url_falls_back_to_the_sqlite_default(tmp_path, monkeypatch):
    """A deployment that configures nothing must still start against local SQLite."""
    module = load_module(tmp_path, monkeypatch)

    assert module.DATABASE_URL == DEFAULT_DATABASE_URL
    assert module.engine.url == make_url(DEFAULT_DATABASE_URL)


def test_sqlite_only_connect_argument_is_not_passed_to_other_drivers(
    tmp_path, monkeypatch
):
    """`check_same_thread` must reach SQLite and must not reach anything else.

    Asserted through `engine_options` rather than through `create_engine`, because
    building a PostgreSQL engine would need a driver this project deliberately does not
    install. That is the whole reason the rule lives in its own function.
    """
    module = load_module(tmp_path, monkeypatch)

    expected = {"connect_args": {"check_same_thread": False}}

    assert module.engine_options("sqlite:///./local.db") == expected
    # The sqlite+pysqlite spelling must be recognised too.
    assert module.engine_options("sqlite+pysqlite:///./local.db") == expected

    assert module.engine_options("postgresql+psycopg://user:pw@host/db") == {}
