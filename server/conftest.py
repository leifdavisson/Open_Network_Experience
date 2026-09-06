import pytest

@pytest.fixture(autouse=True)
def isolate_database(tmp_path, monkeypatch):
    """Cleanly isolates SQLite database files into tmp_path across all tests."""
    db_file = tmp_path / "test_cmp.db"
    monkeypatch.setattr('server.db.connection.DB_PATH', str(db_file))
    # We must also re-initialize the database for tests
    from server.db import init_db
    init_db()
    yield
