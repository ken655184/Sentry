"""filesystem 資源存取層。對外暴露 loader 模組。"""

from app.repositories.filesystem import loader  # noqa: F401

__all__ = ["loader"]
