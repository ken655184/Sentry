"""首次啟動時建立角色、權限、預設 admin"""
from sqlalchemy import select

from app.auth.database import AsyncSessionLocal
from app.auth.models import Permission, Role, User
from app.auth.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password

logger = get_logger(__name__)


async def seed_roles_and_admin() -> None:
    async with AsyncSessionLocal() as db:
        # 1. 建立所有 Permission
        existing_perms = await db.execute(select(Permission))
        existing_codes = {p.code for p in existing_perms.scalars().all()}
        for code in ALL_PERMISSIONS:
            if code not in existing_codes:
                db.add(Permission(code=code, description=code))
        await db.commit()

        # 載入完整 permission 物件
        perm_rows = await db.execute(select(Permission))
        perm_map = {p.code: p for p in perm_rows.scalars().all()}

        # 2. 建立角色 + 綁權限
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role_res = await db.execute(select(Role).where(Role.name == role_name))
            role = role_res.scalar_one_or_none()
            if not role:
                role = Role(name=role_name, description=f"{role_name} 角色")
                db.add(role)
                await db.flush()

            role.permissions = [perm_map[c] for c in perm_codes if c in perm_map]
        await db.commit()

        # 3. 建立預設 admin
        admin_res = await db.execute(
            select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        if admin_res.scalar_one_or_none():
            logger.info("預設 admin 已存在,略過建立")
            return

        admin_role_res = await db.execute(select(Role).where(Role.name == "admin"))
        admin_role = admin_role_res.scalar_one()
        admin = User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            email=settings.DEFAULT_ADMIN_EMAIL,
            full_name="System Administrator",
            hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role_id=admin_role.id,
            must_change_password=True,  # 強制首次登入改密碼
        )
        db.add(admin)
        await db.commit()
        logger.warning(
            "已建立預設 admin 帳號,帳號=%s,請立即登入並更改密碼",
            settings.DEFAULT_ADMIN_USERNAME,
        )
