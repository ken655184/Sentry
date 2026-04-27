"""
Unit tests: repositories.filesystem.loader

用 tmp_path fixture 建立真實的暫存檔案夾,不需要 mock filesystem。
"""

from __future__ import annotations

import pytest

from app.repositories.filesystem.loader import _assert_path_allowed, scan, read_meta, ALLOWED_ROOTS


# ── _assert_path_allowed ──────────────────────────────────────────────────

def test_path_not_in_allowed_roots_raises(tmp_path):
    with pytest.raises(PermissionError, match="not under any allowed root"):
        _assert_path_allowed(str(tmp_path / "secret"))


def test_path_traversal_blocked(tmp_path):
    """/../ 跳出 root 應被擋下。"""
    with pytest.raises(PermissionError):
        _assert_path_allowed("/var/log/monitor/../../etc/passwd")


# ── scan ──────────────────────────────────────────────────────────────────

def test_scan_counts_files(tmp_path, monkeypatch):
    # 暫時把 ALLOWED_ROOTS 改成 tmp_path,讓測試不依賴真實路徑
    monkeypatch.setattr(
        "app.repositories.filesystem.loader.ALLOWED_ROOTS",
        (str(tmp_path),),
    )
    (tmp_path / "a.log").write_text("line1\nline2\n")
    (tmp_path / "b.log").write_text("data")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.log").write_text("x")

    result = scan(path=str(tmp_path), pattern="*.log", recursive=True)
    assert result["total"] == 3
    assert ".log" in result["by_extension"]
    assert result["by_extension"][".log"] == 3


def test_scan_nonexistent_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.repositories.filesystem.loader.ALLOWED_ROOTS",
        (str(tmp_path),),
    )
    with pytest.raises(FileNotFoundError):
        scan(path=str(tmp_path / "doesnotexist"))


# ── read_meta ─────────────────────────────────────────────────────────────

def test_read_meta_returns_head(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.filesystem.loader.ALLOWED_ROOTS",
        (str(tmp_path),),
    )
    f = tmp_path / "test.txt"
    lines = [f"line {i}" for i in range(30)]
    f.write_text("\n".join(lines))

    meta = read_meta(str(f))
    assert meta["size"] > 0
    assert len(meta["head"]) == 20       # 最多 20 行
    assert meta["head"][0] == "line 0"
    assert meta["is_binary_guess"] is False


def test_read_meta_binary_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.filesystem.loader.ALLOWED_ROOTS",
        (str(tmp_path),),
    )
    f = tmp_path / "bin.dat"
    f.write_bytes(b"\x00\x01\x02\x03" * 100)
    meta = read_meta(str(f))
    assert meta["is_binary_guess"] is True
