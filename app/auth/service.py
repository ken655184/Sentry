"""認證業務邏輯"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.schemas import LoginResponse, TokenPair, UserCreate, UserOut
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, username: str, password: str) -> User:
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError(message="帳號或密碼錯誤")
        if not user.is_active:
            raise AuthenticationError(message="帳號已停用")
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    def build_login_response(self, user: User) -> LoginResponse:
        permissions = [p.code for p in user.role.permissions]
        tokens = TokenPair(
            access_token=create_access_token(
                subject=user.username,
                extra={
                    "uid": user.id,
                    "role": user.role.name,
                    "permissions": permissions,   # Part 2: WS auth 需要
                },
            ),
            refresh_token=create_refresh_token(subject=user.username),
        )
        return LoginResponse(
            tokens=tokens,
            user=UserOut(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                must_change_password=user.must_change_password,
                role=user.role.name,
                permissions=permissions,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
            ),
        )

    async def create_user(self, data: UserCreate) -> User:
        validate_password_strength(data.password)

        # 檢查帳號是否已存在
        exists = await self.db.execute(select(User).where(User.username == data.username))
        if exists.scalar_one_or_none():
            raise ValidationError(message="使用者名稱已被使用")

        role_res = await self.db.execute(select(Role).where(Role.name == data.role))
        role = role_res.scalar_one_or_none()
        if not role:
            raise NotFoundError(message=f"角色不存在: {data.role}")

        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role_id=role.id,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: User, old: str, new: str) -> None:
        if not verify_password(old, user.hashed_password):
            raise AuthenticationError(message="舊密碼錯誤")
        validate_password_strength(new)
        user.hashed_password = hash_password(new)
        user.must_change_password = False
        await self.db.commit()
