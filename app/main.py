"""FastAPI 主進入點"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.v1 import auth, users, tests, reports, dashboard
from app.auth.database import init_auth_db
from app.auth.seed import seed_roles_and_admin
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.websocket.routes import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動/關閉時的初始化"""
    setup_logging()
    await init_auth_db()
    await seed_roles_and_admin()
    yield
    # 關閉清理(如果需要)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 錯誤處理
register_exception_handlers(app)

# Prometheus /metrics
app.mount("/metrics", make_asgi_app())

# REST 路由
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
app.include_router(tests.router, prefix=f"{API_PREFIX}/tests", tags=["tests"])
app.include_router(reports.router, prefix=f"{API_PREFIX}/reports", tags=["reports"])
app.include_router(dashboard.router, prefix=f"{API_PREFIX}/dashboard", tags=["dashboard"])

# WebSocket
app.include_router(ws_router, prefix="/ws")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
