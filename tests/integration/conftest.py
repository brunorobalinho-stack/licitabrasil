"""Shared fixtures for FastAPI tests."""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.security import create_access_token, hash_password
from app.database import get_db
from app.main import app
from app.models.usuario import Usuario

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil",
)
TEST_EMAIL = "testuser_pytest@licitabrasil.com"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh engine + session per test to avoid event-loop conflicts."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Cleanup test user if any was created
    async with session_factory() as cleanup:
        await cleanup.execute(delete(Usuario).where(Usuario.email == TEST_EMAIL))
        await cleanup.commit()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with overridden DB dependency."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> Usuario:
    """Create a test user in the DB."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = Usuario(
        id=f"test_{uuid.uuid4().hex[:16]}",
        email=TEST_EMAIL,
        nome="Test User",
        senha=hash_password("test123"),
        role="USER",
        criadoEm=now,
        atualizadoEm=now,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_cookies(test_user: Usuario) -> dict[str, str]:
    """Return cookies dict with a valid access_token for the test user."""
    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return {"access_token": token}


@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession, test_user: Usuario) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with auth cookies pre-set (avoids httpx per-request cookies deprecation)."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": token},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
