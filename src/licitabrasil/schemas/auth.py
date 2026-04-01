"""Schemas de autenticação."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginForm(BaseModel):
    email: EmailStr
    password: str


class TokenData(BaseModel):
    user_id: str
    email: str
