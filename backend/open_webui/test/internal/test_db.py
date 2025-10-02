import importlib
import sys

import pytest
from peewee import OperationalError


class DummyDB:
    def __init__(self):
        self._closed = False

    def close(self):
        self._closed = True

    def is_closed(self):
        return self._closed


class DummyRouter:
    def __init__(self, db, logger, migrate_dir):
        self.db = db
        self.logger = logger
        self.migrate_dir = migrate_dir

    def run(self):
        return None


def test_handle_peewee_migration_propagates_operational_error(monkeypatch):
    """Ensure peewee migration failures re-raise the original OperationalError."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    if "open_webui.internal.db" in sys.modules:
        del sys.modules["open_webui.internal.db"]

    db_module = importlib.import_module("open_webui.internal.db")

    def failing_register_connection(_):
        raise OperationalError("bad connection")

    monkeypatch.setattr(db_module, "register_connection", failing_register_connection)

    with pytest.raises(OperationalError) as excinfo:
        db_module.handle_peewee_migration("postgresql://user:pass@localhost/db")

    assert "bad connection" in str(excinfo.value)


@pytest.mark.parametrize(
    "input_url,expected_url",
    [
        (
            "postgresql://user:pass@localhost:5432/db?sslmode=require",
            "postgres://user:pass@localhost:5432/db?sslmode=require",
        ),
        (
            "postgresql+psycopg2://user:pass@localhost/db",
            "postgres://user:pass@localhost/db",
        ),
    ],
)
def test_handle_peewee_migration_normalizes_postgres_variants(
    monkeypatch, input_url, expected_url
):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Ensure a fresh import so the patched dependencies are used.
    if "open_webui.internal.db" in sys.modules:
        del sys.modules["open_webui.internal.db"]

    captured_urls = []

    def fake_register_connection(url):
        captured_urls.append(url)
        return DummyDB()

    monkeypatch.setattr(
        "open_webui.internal.wrappers.register_connection", fake_register_connection
    )
    monkeypatch.setattr("peewee_migrate.Router", DummyRouter)

    db_module = importlib.import_module("open_webui.internal.db")

    # Ignore the import-time initialization call.
    captured_urls.clear()

    monkeypatch.setattr(db_module, "Router", DummyRouter)
    monkeypatch.setattr(db_module, "register_connection", fake_register_connection)

    db_module.handle_peewee_migration(input_url)

    assert captured_urls == [expected_url]
