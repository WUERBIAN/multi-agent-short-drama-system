"""系统配置：统一管理路径、DeepSeek 参数和默认生成参数。"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# app/config/settings.py -> app/config -> app -> project_root
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
LOGS_DIR = DATA_DIR / "logs"

for directory in (DATA_DIR, SCRIPTS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-e4f4664b3cfe4b6a8e6e569556c8afbf").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "20000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "180"))

SCRIPT_SUFFIXES = (".txt", ".md")
LOG_SUFFIXES = (".txt", ".log")
