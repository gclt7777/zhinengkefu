import importlib
import sys

import pytest
from peewee import OperationalError


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
