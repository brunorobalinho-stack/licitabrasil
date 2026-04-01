from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models.licitacao import Documento, Licitacao
from ..models.usuario import Usuario

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: Usuario | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    total = (await db.execute(select(func.count(Licitacao.id)))).scalar() or 0
    total_docs = (await db.execute(select(func.count(Documento.id)))).scalar() or 0

    total_valor = (await db.execute(
        select(func.sum(Licitacao.valorEstimado))
        .where(Licitacao.valorEstimado.isnot(None))
    )).scalar() or 0

    por_fonte = dict((await db.execute(
        select(Licitacao.fonteOrigem, func.count(Licitacao.id))
        .group_by(Licitacao.fonteOrigem)
        .order_by(func.count(Licitacao.id).desc())
    )).all())

    por_modalidade = dict((await db.execute(
        select(Licitacao.modalidade, func.count(Licitacao.id))
        .where(Licitacao.modalidade.isnot(None))
        .group_by(Licitacao.modalidade)
        .order_by(func.count(Licitacao.id).desc())
        .limit(10)
    )).all())

    por_status = dict((await db.execute(
        select(Licitacao.status, func.count(Licitacao.id))
        .where(Licitacao.status.isnot(None))
        .group_by(Licitacao.status)
        .order_by(func.count(Licitacao.id).desc())
        .limit(8)
    )).all())

    recentes = (await db.execute(
        select(
            Licitacao.id,
            Licitacao.numeroProcesso.label("numero_processo"),
            Licitacao.objeto,
            Licitacao.orgao,
            Licitacao.modalidade,
            Licitacao.fonteOrigem.label("fonte"),
        ).order_by(Licitacao.criadoEm.desc()).limit(20)
    )).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "user": user,
            "total": total,
            "total_docs": total_docs,
            "total_valor": total_valor,
            "total_fontes": len(por_fonte),
            "por_fonte": por_fonte,
            "por_modalidade": por_modalidade,
            "por_status": por_status,
            "recentes": recentes,
        },
    )
