import os
import re
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
UPLOAD_DIR = ROOT_DIR / "uploads"


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([A-Z0-9_]+)(?::-(.*?))?\}")

        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            return os.getenv(name, default or "")

        return pattern.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return _expand_env(yaml.safe_load(file) or {})


CONFIG = _load_config()

PROJECT_NAME = str(CONFIG.get("project", "telega_hub"))

BOT_CONFIG = CONFIG.get("bot", {})
BOT_TOKEN = str(os.getenv("BOT_TOKEN") or BOT_CONFIG.get("token", "")).strip()
BOT_TITLE = str(BOT_CONFIG.get("title", "Telega HUB"))
SUPPORT = str(BOT_CONFIG.get("support", "@support"))

raw_admins = os.getenv("BOT_ADMINS")
if raw_admins:
    BOT_ADMINS = [int(item.strip()) for item in raw_admins.split(",") if item.strip().isdigit()]
else:
    BOT_ADMINS = [int(admin_id) for admin_id in BOT_CONFIG.get("admins", [])]

SERVER_CONFIG = CONFIG.get("server", {})
SERVER_HOST = str(SERVER_CONFIG.get("host", "0.0.0.0"))
SERVER_PORT = int(os.getenv("PORT") or SERVER_CONFIG.get("port", 5080))
PUBLIC_URL = str(os.getenv("PUBLIC_URL") or SERVER_CONFIG.get("public_url", "")).rstrip("/")
WEBAPP_URL = str(os.getenv("WEBAPP_URL") or SERVER_CONFIG.get("webapp_url", "")).rstrip("/")
CORS_ORIGINS = [str(origin).rstrip("/") for origin in SERVER_CONFIG.get("cors_origins", [])]

DATABASE_URL = str(
    os.getenv("DATABASE_URL")
    or CONFIG.get("db")
    or "postgres://postgres:root@localhost/telega_hub"
)

PRODUCT_CONFIG = CONFIG.get("product", {})
COMMISSION_PERCENT = int(PRODUCT_CONFIG.get("commission_percent", 15))
TRIAL_VIDEO_MAX_SECONDS = int(PRODUCT_CONFIG.get("trial_video_max_seconds", 5))
MAX_UPLOAD_MB = int(PRODUCT_CONFIG.get("max_upload_mb", 200))
DEFAULT_SUBSCRIPTION_STARS = int(PRODUCT_CONFIG.get("default_subscription_stars", 250))
MIN_CUSTOM_ORDER_STARS = int(PRODUCT_CONFIG.get("min_custom_order_stars", 100))
CUSTOM_ORDER_HOURS = int(PRODUCT_CONFIG.get("custom_order_hours", 48))
STARS_USD_RATE = float(PRODUCT_CONFIG.get("stars_usd_rate", 0.013))
DEV_AUTH_ENABLED = bool(PRODUCT_CONFIG.get("dev_auth_enabled", False))

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
