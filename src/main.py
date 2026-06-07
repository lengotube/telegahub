import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from aiogram.types import BotCommand, BotCommandScopeChat
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from . import config, handlers
from .api import router as api_router
from .bot_app import bot, dp


COMMANDS = [
    BotCommand(command="start", description="открыть Telega HUB"),
]

ADMIN_COMMANDS = COMMANDS + [
    BotCommand(command="admin", description="админ-панель"),
]


async def init_database() -> None:
    await Tortoise.init(db_url=config.DATABASE_URL, modules={"models": ["src.models"]})
    await Tortoise.generate_schemas()


async def set_commands() -> None:
    await bot.set_my_commands(COMMANDS)
    for admin_id in config.BOT_ADMINS:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, BotCommandScopeChat(chat_id=admin_id))
        except Exception as exc:
            logging.warning("Could not set admin commands for %s: %s", admin_id, exc)


async def run_bot() -> None:
    dp.include_router(handlers.router)
    await set_commands()
    me = await bot.get_me()
    logging.info("@%s polling started", me.username)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await init_database()
    bot_task = asyncio.create_task(run_bot())
    try:
        yield
    finally:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        await Tortoise.close_connections()
        await bot.session.close()


app = FastAPI(title=config.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run("src.main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
