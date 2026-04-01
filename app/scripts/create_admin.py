"""Cria um usuário admin no PostgreSQL.

Uso:
    python -m app.scripts.create_admin --email admin@licitabrasil.com --password senha123
    python -m app.scripts.create_admin --email admin@licitabrasil.com --password senha123 --nome "Admin"
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.security import hash_password
from app.config import settings
from app.database import Base
from app.models.usuario import Usuario


async def create_admin(email: str, password: str, nome: str):
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        existing = await session.execute(select(Usuario).where(Usuario.email == email))
        if existing.scalar_one_or_none():
            print(f"Usuário {email} já existe.")
            await engine.dispose()
            return

        user = Usuario(
            email=email,
            nome=nome,
            hashed_password=hash_password(password),
            is_active=True,
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        print(f"Admin criado: {email}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Criar usuário admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--nome", default="Admin")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.password, args.nome))


if __name__ == "__main__":
    main()
