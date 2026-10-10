import pytest
from app.database import Base, engine
from app import models

@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Ensure database schema is created before running any test session."""
    Base.metadata.create_all(bind=engine)
    yield
