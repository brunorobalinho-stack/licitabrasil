"""Tests for FastAPI auth routes (/login, /logout)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_page_returns_html(client: AsyncClient):
    res = await client.get("/login")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


@pytest.mark.asyncio
async def test_login_redirects_when_authenticated(auth_client: AsyncClient):
    res = await auth_client.get("/login", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/"


@pytest.mark.asyncio
async def test_login_post_success(client: AsyncClient, test_user):
    res = await client.post(
        "/login",
        data={"email": test_user.email, "password": "test123"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "access_token" in res.cookies


@pytest.mark.asyncio
async def test_login_post_invalid_password(client: AsyncClient, test_user):
    res = await client.post(
        "/login",
        data={"email": test_user.email, "password": "wrong"},
    )
    assert res.status_code == 400
    assert "inválidos" in res.text.lower() or "invalidos" in res.text.lower()


@pytest.mark.asyncio
async def test_login_post_nonexistent_user(client: AsyncClient):
    res = await client.post(
        "/login",
        data={"email": "ghost@test.com", "password": "123456"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_logout_clears_cookie(auth_client: AsyncClient):
    res = await auth_client.get("/logout", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
