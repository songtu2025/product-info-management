import pytest

from app.main import app


@pytest.fixture(autouse=True)
def disable_auth_for_existing_route_tests():
    app.state.disable_auth = True
    yield
    app.state.disable_auth = False
