from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    data: T


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: PaginatedData[T]
