from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.api import auth, dashboard, agents, clients, contracts, alerts, emails, transactions

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic in production)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Back office dashboard com agentes inteligentes para gestão empresarial",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(contracts.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(emails.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backoffice"}
