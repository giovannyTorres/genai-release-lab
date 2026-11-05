import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/release-tests.db")
import pytest
from fastapi.testclient import TestClient
from release_lab.models import Base, engine
from release_lab.main import app


@pytest.fixture
def client():
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
