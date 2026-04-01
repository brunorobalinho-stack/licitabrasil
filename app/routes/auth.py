import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..auth.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models.usuario import Usuario

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: Usuario | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.senha):
        return templates.TemplateResponse(
            request,
            "login.html",
            context={"error": "Email ou senha inválidos"},
            status_code=400,
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,  # 24h
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/esqueci-senha", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html")


@router.post("/esqueci-senha")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    user = result.scalar_one_or_none()

    if user:
        raw_token = str(uuid.uuid4())
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        user.resetToken = hashed_token
        user.resetTokenExpiry = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()
        # In production, send email with raw_token. For now, log it.

    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        context={"sent": True},
    )


@router.get("/redefinir-senha", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "reset_password.html", context={"token": token})


@router.post("/redefinir-senha")
async def reset_password(
    request: Request,
    token: str = Form(...),
    senha: str = Form(...),
    confirmar: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if senha != confirmar:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            context={"token": token, "error": "As senhas não coincidem"},
            status_code=400,
        )

    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(Usuario).where(
            Usuario.resetToken == hashed_token,
            Usuario.resetTokenExpiry > datetime.now(timezone.utc),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            context={"token": token, "error": "Token inválido ou expirado"},
            status_code=400,
        )

    user.senha = hash_password(senha)
    user.resetToken = None
    user.resetTokenExpiry = None
    await db.commit()

    return templates.TemplateResponse(
        request,
        "reset_password.html",
        context={"token": "", "success": True},
    )
