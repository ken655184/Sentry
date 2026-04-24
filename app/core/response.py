"""統一 API 回應格式"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None


def ok(data: Any = None, message: str | None = None) -> dict:
    return {"success": True, "data": data, "message": message}
