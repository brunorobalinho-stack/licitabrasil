from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

RoleEnum = SAEnum("ADMIN", "ANALYST", "USER", name="Role", create_type=False)


class Usuario(Base):
    __tablename__ = "Usuario"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    senha: Mapped[str] = mapped_column(String(255))
    empresa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cnpj: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(RoleEnum, server_default="USER")

    resetToken: Mapped[Optional[str]] = mapped_column(
        "resetToken", String(255), unique=True, nullable=True
    )
    resetTokenExpiry: Mapped[Optional[datetime]] = mapped_column(
        "resetTokenExpiry", DateTime, nullable=True
    )
    criadoEm: Mapped[datetime] = mapped_column(
        "criadoEm", server_default=func.now()
    )
    atualizadoEm: Mapped[datetime] = mapped_column(
        "atualizadoEm", server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    @property
    def hashed_password(self) -> str:
        return self.senha

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self.senha = value

    @property
    def reset_token(self) -> Optional[str]:
        return self.resetToken

    @reset_token.setter
    def reset_token(self, value: Optional[str]) -> None:
        self.resetToken = value

    @property
    def reset_token_expiry(self) -> Optional[datetime]:
        return self.resetTokenExpiry

    @reset_token_expiry.setter
    def reset_token_expiry(self, value: Optional[datetime]) -> None:
        self.resetTokenExpiry = value
