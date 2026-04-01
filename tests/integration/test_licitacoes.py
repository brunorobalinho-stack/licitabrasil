"""Tests for FastAPI licitacoes routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_licitacoes_redirects_unauthenticated(client: AsyncClient):
    res = await client.get("/licitacoes", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]


@pytest.mark.asyncio
async def test_licitacoes_returns_html(auth_client: AsyncClient):
    res = await auth_client.get("/licitacoes")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


@pytest.mark.asyncio
async def test_licitacoes_htmx_partial(auth_client: AsyncClient):
    res = await auth_client.get(
        "/licitacoes",
        headers={"HX-Request": "true"},
    )
    assert res.status_code == 200
    # Partial should NOT contain full html/head structure
    assert "<!DOCTYPE" not in res.text


@pytest.mark.asyncio
async def test_licitacoes_detail_not_found(auth_client: AsyncClient):
    res = await auth_client.get("/licitacoes/999999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_export_redirects_unauthenticated(client: AsyncClient):
    res = await client.get("/licitacoes/export", follow_redirects=False)
    assert res.status_code == 303


@pytest.mark.asyncio
async def test_export_returns_csv(auth_client: AsyncClient):
    res = await auth_client.get("/licitacoes/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "ID" in res.text  # CSV header row
