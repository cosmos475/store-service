import asyncio
import time
import logging

from aiogram.exceptions import TelegramAPIError

from engine.client_holder import get_bot
from engine.notifier import notify_sync_start, notify_sync_complete, notify_sync_error
from database import products as products_db
from database import users as users_db
from database import progress as progress_db
from database import settings as settings_db
from database import messages as messages_db
from utils.formatters import progress_text

logger = logging.getLogger(__name__)


async def run_initial_sync(user_id: int, product_id: str) -> None:
    bot = get_bot()
    product = await products_db.get_product(product_id)
    user = await users_db.get_user(user_id)

    if not product or not user or not user.get("destination_channel_id"):
        await notify_sync_error(user_id, product.get("name", "?") if product else "?", "Missing product or destination")
        return

    source_id = product["source_channel_id"]
    dest_id = user["destination_channel_id"]
    product_name = product["name"]

    progress = await progress_db.get_progress(user_id, product_id)
    if not progress or progress.get("sync_status") not in ("in_progress", "paused"):
        await progress_db.init_progress(user_id, product_id)
        progress = await progress_db.get_progress(user_id, product_id)

    last_message_id = progress.get("last_message_id", 0)
    total_synced = progress.get("total_synced", 0)

    await progress_db.set_sync_status(user_id, product_id, "in_progress")
    await notify_sync_start(user_id, product_name)

    start_time = time.monotonic()
    delay = await settings_db.get_delay()

    try:
        # Replay everything archived for this product since last_message_id,
        # oldest first. This only covers messages archived since the bot
        # started watching this source (archive-from-now-on mode) — not
        # full Telegram history, which the Bot API cannot provide.
        pending = await messages_db.list_after(product_id, last_message_id)
        total_to_send = total_synced + len(pending)

        for record in pending:
            msg_id = record["source_message_id"]

            try:
                await bot.copy_message(
                    chat_id=dest_id, from_chat_id=source_id, message_id=msg_id
                )
            except TelegramAPIError as e:
                logger.warning("Skipping message %s for user %s: %s", msg_id, user_id, e)
                last_message_id = msg_id
                continue

            last_message_id = msg_id
            total_synced += 1

            await progress_db.update_progress(user_id, product_id, last_message_id, total_synced)

            if total_synced % 20 == 0:
                try:
                    await bot.send_message(user_id, progress_text(total_synced, total_to_send))
                except TelegramAPIError:
                    pass

            await asyncio.sleep(delay)

        await progress_db.set_sync_status(user_id, product_id, "completed")

        try:
            await bot.send_message(user_id, "✅ Forwarding Completed")
        except TelegramAPIError:
            pass

        elapsed = time.monotonic() - start_time
        time_taken = _format_duration(elapsed)

        await notify_sync_complete(
            user_id, user.get("username", str(user_id)), product_name, total_synced, time_taken
        )

    except Exception as e:
        await progress_db.set_sync_status(user_id, product_id, "failed")
        await notify_sync_error(user_id, product_name, str(e))


def _format_duration(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {secs}s"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"
