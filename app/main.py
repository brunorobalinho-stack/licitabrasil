from contextlib import asynccontextmanager

from .lib.sentry import init_sentry

init_sentry()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import engine
from .middleware import ErrorHandlerMiddleware
from .routes import admin, auth, dashboard, licitacoes
from .lib.audit import enable_audit_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria apenas tabelas SQLAlchemy-only (scraper_runs); Prisma gerencia as demais
    from .models.licitacao import ScraperRun
    async with engine.begin() as conn:
        await conn.run_sync(ScraperRun.__table__.create, checkfirst=True)
    # Habilitar audit logging via SQLAlchemy events
    enable_audit_logging()
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(ErrorHandlerMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(licitacoes.router)
app.include_router(admin.router)
