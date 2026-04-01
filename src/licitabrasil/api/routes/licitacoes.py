import csv
import io
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth.deps import get_current_user
from ..database import get_db
from ..middleware import is_htmx
from ..models.licitacao import Licitacao
from ..models.usuario import Usuario

router = APIRouter(tags=["licitacoes"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

# Colunas usadas na listagem — labels preservam nomes p/ templates
LIST_COLUMNS = [
    Licitacao.id,
    Licitacao.numeroProcesso.label("numero_processo"),
    Licitacao.objeto,
    Licitacao.orgao,
    Licitacao.uf,
    Licitacao.modalidade,
    Licitacao.status,
    Licitacao.valorEstimado.label("valor_estimado"),
    Licitacao.fonteOrigem.label("fonte"),
    Licitacao.dataPublicacao.label("data_publicacao"),
    Licitacao.dataAbertura.label("data_abertura"),
]


def _apply_filters(stmt, q, modalidade, uf, orgao, fonte, status, valor_min, valor_max, data_inicio, data_fim):
    if q:
        stmt = stmt.where(Licitacao.objeto.ilike(f"%{q}%"))
    if modalidade:
        stmt = stmt.where(Licitacao.modalidade == modalidade)
    if uf:
        stmt = stmt.where(Licitacao.uf == uf)
    if orgao:
        stmt = stmt.where(Licitacao.orgao.ilike(f"%{orgao}%"))
    if fonte:
        stmt = stmt.where(Licitacao.fonteOrigem == fonte)
    if status:
        stmt = stmt.where(Licitacao.status == status)
    if valor_min is not None:
        stmt = stmt.where(Licitacao.valorEstimado >= valor_min)
    if valor_max is not None:
        stmt = stmt.where(Licitacao.valorEstimado <= valor_max)
    if data_inicio:
        stmt = stmt.where(Licitacao.dataPublicacao >= data_inicio)
    if data_fim:
        stmt = stmt.where(Licitacao.dataPublicacao <= data_fim)
    return stmt


async def _get_filter_options(db: AsyncSession) -> dict:
    modalidades = (await db.execute(
        select(Licitacao.modalidade)
        .where(Licitacao.modalidade.isnot(None))
        .distinct().order_by(Licitacao.modalidade)
    )).scalars().all()

    ufs = (await db.execute(
        select(Licitacao.uf)
        .where(Licitacao.uf.isnot(None), Licitacao.uf != "")
        .distinct().order_by(Licitacao.uf)
    )).scalars().all()

    fontes = (await db.execute(
        select(Licitacao.fonteOrigem).distinct().order_by(Licitacao.fonteOrigem)
    )).scalars().all()

    statuses = (await db.execute(
        select(Licitacao.status)
        .where(Licitacao.status.isnot(None))
        .distinct().order_by(Licitacao.status)
    )).scalars().all()

    return {
        "modalidades": modalidades,
        "ufs": ufs,
        "fontes": fontes,
        "statuses": statuses,
    }


@router.get("/licitacoes/export")
async def export_csv(
    request: Request,
    q: str | None = None,
    modalidade: str | None = None,
    uf: str | None = None,
    orgao: str | None = None,
    fonte: str | None = None,
    status: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    user: Usuario | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stmt = select(*LIST_COLUMNS)
    stmt = _apply_filters(stmt, q, modalidade, uf, orgao, fonte, status, valor_min, valor_max, data_inicio, data_fim)
    stmt = stmt.order_by(Licitacao.criadoEm.desc()).limit(10_000)

    rows = (await db.execute(stmt)).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "Numero", "Objeto", "Orgao", "UF", "Modalidade", "Status", "Valor Estimado", "Fonte", "Data Publicacao", "Data Abertura"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for r in rows:
            writer.writerow([r.id, r.numero_processo, r.objeto, r.orgao, r.uf, r.modalidade, r.status, r.valor_estimado, r.fonte, r.data_publicacao, r.data_abertura])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=licitacoes.csv"},
    )


@router.get("/licitacoes/{licitacao_id}", response_class=HTMLResponse)
async def detail_licitacao(
    request: Request,
    licitacao_id: str,
    user: Usuario | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    result = await db.execute(
        select(Licitacao)
        .where(Licitacao.id == licitacao_id)
        .options(selectinload(Licitacao.documentos))
    )
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")

    return templates.TemplateResponse(
        request,
        "licitacao_detail.html",
        context={"user": user, "lic": lic},
    )


@router.get("/licitacoes", response_class=HTMLResponse)
async def list_licitacoes(
    request: Request,
    q: str | None = None,
    modalidade: str | None = None,
    uf: str | None = None,
    orgao: str | None = None,
    fonte: str | None = None,
    status: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
    user: Usuario | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stmt = select(*LIST_COLUMNS)
    stmt = _apply_filters(stmt, q, modalidade, uf, orgao, fonte, status, valor_min, valor_max, data_inicio, data_fim)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Licitacao.criadoEm.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(stmt)).all()

    has_next = page * per_page < total

    ctx = {
        "licitacoes": rows,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_next": has_next,
        "q": q or "",
        "sel_modalidade": modalidade or "",
        "sel_uf": uf or "",
        "sel_orgao": orgao or "",
        "sel_fonte": fonte or "",
        "sel_status": status or "",
        "valor_min": valor_min if valor_min is not None else "",
        "valor_max": valor_max if valor_max is not None else "",
        "data_inicio": data_inicio or "",
        "data_fim": data_fim or "",
    }

    if is_htmx(request):
        return templates.TemplateResponse(request, "partials/licitacoes_rows.html", context=ctx)

    filter_opts = await _get_filter_options(db)
    ctx.update(filter_opts)
    ctx["user"] = user

    return templates.TemplateResponse(request, "licitacoes.html", context=ctx)
