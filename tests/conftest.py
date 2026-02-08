"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set test environment before importing app
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENCRYPTION_KEY"] = "test-key-for-encryption-only-32b="  # Test key

from app.main import app
from app.db.database import Base, get_db
from app.models.organization import ProviderType


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create test database and session."""
    # Use SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_org_id():
    """Generate a sample organization ID."""
    return uuid4()


@pytest.fixture
def sample_provider_credentials():
    """Sample provider credentials for testing."""
    return {
        "datadog": {
            "api_key": "test-api-key",
            "app_key": "test-app-key",
            "site": "datadoghq.com",
        },
        "prometheus": {
            "url": "http://localhost:9090",
            "username": "test-user",
            "password": "test-pass",
        },
        "grafana": {
            "url": "http://localhost:3000",
            "api_key": "test-grafana-key",
        },
    }
