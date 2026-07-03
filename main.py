import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from web.server import start_web_server
from engine.client_holder import set_bot
from engine import archiver
from engine.queue_manager import resume_sync
from database import progress as progress_db

from handlers import (
    user_start,
    user_status,
    product_selection,
    owner_commands,
    admin_panel,
    admin_products,
    admin_settings,
    admin_users,
    admin_tasks,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties())
dp = Dispatcher()


def _register_all_handlers() -> None:
    logger.info("DEBUG: registering handlers...")
    # Order matters: owner-specific routers first so they claim the
    # OWNER_ID's /start and text/forward messages before generic
    # user routers get a chance (aiogram routers are tried in order,
    # first match wins per event within a router).
    admin_panel.register(dp)
    logger.info("DEBUG: admin_panel registered")
    admin_products.register(dp)
    logger.info("DEBUG: admin_products registered")
    admin_settings.register(dp)
    logger.info("DEBUG: admin_settings registered")
    admin_users.register(dp)
    logger.info("DEBUG: admin_users registered")
    admin_tasks.register(dp)
    logger.info("DEBUG: admin_tasks registered")
    owner_commands.register(dp)
    logger.info("DEBUG: owner_commands registered")
    user_start.register(dp)
    logger.info("DEBUG: user_start registered")
    user_status.register(dp)
    logger.info("DEBUG: user_status registered")
    product_selection.register(dp)
    logger.info("DEBUG: product_selection registered")
    archiver.register(dp)
    logger.info("DEBUG: archiver registered")


async def _resume_interrupted_syncs() -> None:
    active = await progress_db.list_active_syncs()
    for task in active:
        resume_sync(task["user_id"], task["product_id"])
    if active:
        logger.info(f"Resumed {len(active)} interrupted sync(s).")


async def main() -> None:
    await start_web_server()
    logger.info("DEBUG: startup completed - web server started.")

    set_bot(bot)
    _register_all_handlers()
    logger.info("DEBUG: all handlers registered.")

    await _resume_interrupted_syncs()

    logger.info("DEBUG: starting polling.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "channel_post"])


if __name__ == "__main__":
    asyncio.run(main())
