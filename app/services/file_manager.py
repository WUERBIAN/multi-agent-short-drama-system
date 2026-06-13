"""生成结果和日志文件管理。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from app.config import settings


def safe_filename(name: str) -> str:
    name = name.strip() or "未命名短剧"
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:80] or "未命名短剧"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_script(title: str, content: str) -> Path:
    filepath = settings.SCRIPTS_DIR / f"{safe_filename(title)}_剧本_{timestamp()}.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def save_log(title: str, content: str) -> Path:
    filepath = settings.LOGS_DIR / f"{safe_filename(title)}_日志_{timestamp()}.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def list_files(directory: Path, suffixes: Iterable[str]) -> List[Path]:
    suffixes = tuple(s.lower() for s in suffixes)
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in suffixes]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def list_scripts() -> List[Path]:
    return list_files(settings.SCRIPTS_DIR, settings.SCRIPT_SUFFIXES)


def list_logs() -> List[Path]:
    return list_files(settings.LOGS_DIR, settings.LOG_SUFFIXES)


def delete_file(path: Path) -> None:
    path = Path(path)
    if path.exists() and path.is_file():
        path.unlink()


def clear_directory(directory: Path, suffixes: Iterable[str]) -> int:
    count = 0
    for path in list_files(directory, suffixes):
        path.unlink()
        count += 1
    return count


def export_file(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    return target


def open_directory(path: Path) -> None:
    path = Path(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
