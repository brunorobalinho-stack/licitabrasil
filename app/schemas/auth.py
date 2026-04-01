from pydantic import BaseModel


class LoginForm(BaseModel):
    email: str
    password: str


class TokenData(BaseModel):
    user_id: int
    email: str
