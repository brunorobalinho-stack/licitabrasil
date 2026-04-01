from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.usuario import Usuario
from .security import decode_token


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Usuario | None:
    """Retorna o usuário logado ou None se não autenticado."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(
        select(Usuario).where(Usuario.id == user_id)
    )
    return result.scalar_one_or_none()


async def require_admin(user: Usuario | None = Depends(get_current_user)) -> Usuario:
    """Exige que o usuário seja admin."""
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    return user
