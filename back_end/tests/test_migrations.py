"""Migrations must create a complete schema and preserve existing application data."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
import pytest
from fastapi.testclient import TestClient
from test_admin_notifications import load_module


def migrate(database_url):
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    engine = create_engine(database_url)
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    return engine


def test_fresh_database_is_created_and_upgrade_is_repeatable(tmp_path):
    url = f'sqlite:///{tmp_path / "fresh.db"}'
    engine = migrate(url)
    tables = set(inspect(engine).get_table_names())
    assert {'users', 'user_sessions', 'payments', 'contact_submissions',
            'membership_applications', 'membership_application_profiles',
            'membership_application_consents', 'alembic_version'} <= tables
    migrate(url)


def test_legacy_user_and_application_are_preserved(tmp_path):
    url = f'sqlite:///{tmp_path / "legacy.db"}'
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, '
            'first_name VARCHAR(100) NOT NULL, last_name VARCHAR(100) NOT NULL, '
            'email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL, '
            'email_verified BOOLEAN NOT NULL)'))
        connection.execute(text("INSERT INTO users VALUES (1, 'Existing', 'User', 'existing@example.com', 'hash', 1)"))
    migrate(url)
    with engine.connect() as connection:
        row = connection.execute(text('SELECT first_name, is_admin FROM users')).one()
        assert tuple(row) == ('Existing', 0)
    assert 'membership_application_consents' in inspect(engine).get_table_names()


def test_api_refuses_unmigrated_database(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch, DATABASE_URL=f'sqlite:///{tmp_path / "unmigrated.db"}')
    with pytest.raises(RuntimeError, match='migrat'):
        with TestClient(module.app):
            pass


def test_api_starts_after_migrations(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path / "ready.db"}'
    module = load_module(tmp_path, monkeypatch, DATABASE_URL=url)
    migrate(url)
    with TestClient(module.app) as client:
        assert client.get('/health').status_code == 200
