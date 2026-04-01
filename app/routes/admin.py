from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_admin
from ..database import get_db
from ..models.licitacao import ScraperRun
from ..models.usuario import Usuario

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/scrapers", response_class=HTMLResponse)
async def scraper_status_page(
    request: Request,
    user: Usuario = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScraperRun).order_by(ScraperRun.started_at.desc()).limit(50)
    )
    runs = result.scalars().all()

    # Agrupar por fonte para pegar stats
    fontes: dict[str, dict] = {}
    for run in runs:
        if run.fonte not in fontes:
            fontes[run.fonte] = {
                "nome": run.fonte,
                "ultimo_run": run,
                "total_success": 0,
                "total_error": 0,
                "total_new": 0,
            }
        stats = fontes[run.fonte]
        if run.status == "success":
            stats["total_success"] += 1
        elif run.status == "error":
            stats["total_error"] += 1
        stats["total_new"] += run.total_new

    return templates.TemplateResponse(
        request,
        "admin_scrapers.html",
        context={
            "user": user,
            "fontes": fontes.values(),
            "runs": runs[:20],
            "active_page": "scrapers",
        },
    )
