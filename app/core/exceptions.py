"""統一例外與全域錯誤處理"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """業務層例外基類"""

    status_code: int = 400
    code: str = "app_error"
    message: str = "Application error"

    def __init__(self, message: str | None = None, code: str | None = None):
        if message:
            self.message = message
        if code:
            self.code = code
        super().__init__(self.message)


class NotFoundError(AppException):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class PermissionDeniedError(AppException):
    status_code = 403
    code = "permission_denied"
    message = "Permission denied"


class AuthenticationError(AppException):
    status_code = 401
    code = "authentication_failed"
    message = "Authentication failed"


class ValidationError(AppException):
    status_code = 422
    code = "validation_error"
    message = "Validation error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _handle_app_exc(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": exc.code, "message": exc.message},
            },
        )
