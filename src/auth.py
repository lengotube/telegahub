import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, Request

from . import config
from .models import User


def _verify_init_data(init_data: str) -> dict:
    if not config.BOT_TOKEN:
        raise HTTPException(503, "Bot token is not configured")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise HTTPException(401, "Telegram initData hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", config.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(401, "Telegram initData is invalid")

    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(401, "Telegram user is missing")
    return json.loads(user_raw)


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_telegram_init_data: str | None = Header(default=None),
    x_debug_user_id: str | None = Header(default=None),
) -> User:
    init_data = x_telegram_init_data
    if authorization and authorization.lower().startswith("tma "):
        init_data = authorization[4:].strip()

    if init_data:
        tg_user = _verify_init_data(init_data)
        user_id = int(tg_user["id"])
        defaults = {
            "username": tg_user.get("username"),
            "full_name": " ".join(
                part for part in [tg_user.get("first_name"), tg_user.get("last_name")] if part
            )[:128],
        }
    elif config.DEV_AUTH_ENABLED and x_debug_user_id:
        user_id = int(x_debug_user_id)
        defaults = {
            "username": f"dev{user_id}",
            "full_name": f"Dev User {user_id}",
        }
    else:
        raise HTTPException(401, "Open this page from Telegram or pass initData")

    user, created = await User.get_or_create(id=user_id, defaults=defaults)
    if not created:
        changed = False
        for key, value in defaults.items():
            if value and getattr(user, key) != value:
                setattr(user, key, value)
                changed = True
        if changed:
            await user.save()
    if user.is_banned:
        raise HTTPException(403, "User is banned")
    request.state.user = user
    return user


async def require_admin(user: User) -> User:
    if user.id not in config.BOT_ADMINS and user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user
