from pydantic import BaseModel


class TokenLoginRequest(BaseModel):
    token: str
    role: str = "student"


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    role: str
    nickname: str | None
    student_id: int | None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo


class MeResponse(BaseModel):
    id: int
    role: str
    nickname: str | None
    phone: str
    student_id: int | None

    model_config = {"from_attributes": True}
