import os

import tempfile
from urllib.parse import urlsplit

_test_root = tempfile.TemporaryDirectory(prefix="release-audit-tests-")
test_url = os.getenv("TEST_DATABASE_URL")
if test_url:
    if not urlsplit(test_url).path.rstrip("/").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must name a dedicated database ending in _test")
else:
    test_url = "sqlite:///" + _test_root.name + "/release_test.db"
os.environ["DATABASE_URL"] = test_url
os.environ["APP_MODE"] = "DEMO"
import pytest  # noqa: E402 - configure the disposable database before importing application modules
from fastapi.testclient import TestClient  # noqa: E402
from release_lab.models import Base, engine  # noqa: E402
from release_lab.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    # Windows cannot remove the temporary SQLite file while pooled handles remain open.
    engine.dispose()


@pytest.fixture
def client():
    from release_lab.limits import _attempts

    _attempts.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def operator(client):
    assert (
        client.post("/api/auth/login", json={"username": "operator", "password": "demo-release"}).status_code
        == 200
    )
    return client
