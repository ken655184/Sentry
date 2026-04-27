"""
散落在 server 上的檔案資源存取層(留空介面)。

實際實作接入時,請把下列函式改成真實邏輯;目前提供一份「能跑」的
stub 版,對應 Part 1 .env 裡的 FS_LOG_PATH / FS_CONFIG_PATH / FS_ARTIFACT_PATH。
把 pathlib 版本放在這裡,是因為 Celery worker 多是純同步 + 檔案 IO,
不值得用 aiofiles 拉高複雜度。

設計重點:
- scan 不回傳完整檔案清單(可能幾百 MB)—— 回摘要 + 用 reporter 推逐筆
- read_meta 只回 metadata 與前幾行,完整內容請走 FastAPI streaming response
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


# 允許掃描的根目錄白名單 —— 避免使用者用 `../../` 跳到別處
# 實際部署時從 app.config.settings 讀這三個值
ALLOWED_ROOTS: tuple[str, ...] = (
    "/var/log/monitor",
    "/etc/monitor",
    "/data/artifacts",
)


def _assert_path_allowed(path: str) -> Path:
    """
    解析並檢查路徑必須落在白名單 root 下。
    這步不能省 —— 否則前端帶一個 `/etc/passwd` 就能讓 task 去掃。
    """
    p = Path(path).resolve()
    for root in ALLOWED_ROOTS:
        try:
            p.relative_to(Path(root).resolve())
            return p
        except ValueError:
            continue
    raise PermissionError(f"path not under any allowed root: {path}")


def scan(
    *,
    path: str,
    pattern: str = "*",
    recursive: bool = True,
    reporter: Any | None = None,
) -> dict[str, Any]:
    """
    掃描資料夾,回傳摘要:total、total_size、副檔名分布。
    明細逐筆透過 reporter.log 推給前端(10 筆一批)。

    reporter 是 Part 2 的 ProgressReporter,這裡故意只接 Any 避免循環 import。
    """
    p = _assert_path_allowed(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    iterator: Iterable[Path] = p.rglob(pattern) if recursive else p.glob(pattern)

    total = 0
    total_size = 0
    ext_stats: dict[str, int] = {}
    batch: list[str] = []

    for item in iterator:
        if not item.is_file():
            continue
        total += 1
        try:
            total_size += item.stat().st_size
        except OSError:
            # 檔案在掃描途中被刪掉 —— 不讓整個 task 失敗
            pass
        ext = item.suffix.lower() or "(none)"
        ext_stats[ext] = ext_stats.get(ext, 0) + 1

        batch.append(str(item))
        if len(batch) >= 10 and reporter is not None:
            reporter.log(f"已找到 {total} 檔;最新批次: {batch[-5:]}")
            batch.clear()

    return {
        "root": str(p),
        "pattern": pattern,
        "recursive": recursive,
        "total": total,
        "total_size_bytes": total_size,
        "by_extension": ext_stats,
    }


def read_meta(file_path: str, reporter: Any | None = None) -> dict[str, Any]:
    """
    讀取單一檔案的摘要。完整內容不回(避免 Celery result 爆大)。
    """
    p = _assert_path_allowed(file_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(str(p))

    stat = p.stat()
    head_lines: list[str] = []
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fp:
            for i, line in enumerate(fp):
                if i >= 20:
                    break
                head_lines.append(line.rstrip("\n"))
    except OSError as exc:
        if reporter is not None:
            reporter.log(f"讀檔失敗: {exc}", level="warning")

    return {
        "path": str(p),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "head": head_lines,
        "is_binary_guess": _guess_binary(p),
    }


def _guess_binary(p: Path) -> bool:
    """粗略判斷是不是 binary —— 看前 512 bytes 裡有沒有 null byte。"""
    try:
        with p.open("rb") as fp:
            chunk = fp.read(512)
        return b"\x00" in chunk
    except OSError:
        return False
