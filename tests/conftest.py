import pytest
from app.domain.models import db_state


@pytest.fixture(autouse=True)
def ensure_baseline():
    """Make sure baseline data is seeded before each test."""
    if not db_state.is_ready():
        db_state.seed_baseline()
