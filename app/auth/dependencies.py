"""FastAPI 相依注入:目前使用者、權限檢查"""
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.database import get_auth_db
from app.auth.models import User
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_auth_db),
) -> User:
    if not token:
        raise AuthenticationError(message="未提供認證 token")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError(message="Token 類型錯誤")

    username: str | None = payload.get("sub")
    if not username:
        raise AuthenticationError(message="Token 無效")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError(message="使用者不存在或已停用")

    # 把 user 塞進 request.state 方便稽核日誌取用
    request.state.current_user = user
    return user


def require_permission(permission: str):
    """用法:
        @router.post(...)
        async def ep(user = Depends(require_permission("test:create"))):
            ...
    """

    async def _checker(user: User = Depends(get_current_user)) -> User:
        user_perms = {p.code for p in user.role.permissions}
        if permission not in user_perms:
            raise PermissionDeniedError(
                message=f"缺少權限: {permission}",
            )
        return user

    return _checker


def require_any_permission(*permissions: str):
    """任一 permission 通過即可"""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        user_perms = {p.code for p in user.role.permissions}
        if not any(p in user_perms for p in permissions):
            raise PermissionDeniedError(
                message=f"需要以下任一權限: {', '.join(permissions)}",
            )
        return user

    return _checker
