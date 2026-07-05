import asyncio
import time
import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from engine.client_holder import get_bot
from engine.notifier import notify_sync_start, notify_sync_complete, notify_sync_error
from engine import queue_manager
from database import products as products_db
from database import users as users_db
from database import progress as progress_db
from database import settings as settings_db
from database import messages as messages_db

logger = logging.getLogger(__name__)

PROGRESS_INTERVAL = 15

# Errors where the source message itself is the problem (deleted, not
# copyable) -- expected/skippable, logged at WARNING with a short reason
# instead of a full ERROR stack.
_SKIPPABLE_ERROR_HINTS = ("message to copy not found", "message can't be copied", "message_id_invalid")


def _format_progress_text(status_line: str, synced: int, total: int, extra: str | None = None) -> str:
    text = f"{status_line}\n\n{synced} / {total}"
    if extra:
        text += f"\n\n{extra}"
    return text


async def _set_progress_message(bot, user_id: int, product_id: str, progress_message_id, text: str) -> int | None:
    """Edit the existing progress message, or send a new one if none exists
    yet or the edit fails (e.g. message deleted by user)."""
    if progress_message_id:
        try:
            await bot.edit_message_text(chat_id=user_id, message_id=progress_message_id, text=text)
            return progress_message_id
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return progress_message_id
            logger.warning(f"Progress message edit failed for user {user_id}, sending new one: {e}")
        except TelegramAPIError as e:
            logger.warning(f"Progress message edit failed for user {user_id}, sending new one: {e}")

    try:
        msg = await bot.send_message(user_id, text)
        await progress_db.set_progress_message_id(user_id, product_id, msg.message_id)
        return msg.message_id
    except TelegramAPIError:
        logger.exception(f"Failed to send progress message to user {user_id}")
        return progress_message_id


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
    is_resume = bool(progress and progress.get("sync_status") == "paused")

    if not progress or progress.get("sync_status") not in ("in_progress", "paused"):
        await progress_db.init_progress(user_id, product_id)
        progress = await progress_db.get_progress(user_id, product_id)

    last_message_id = progress.get("last_message_id", 0)
    total_synced = progress.get("total_synced", 0)
    progress_message_id = progress.get("progress_message_id")

    await progress_db.set_sync_status(user_id, product_id, "in_progress")
    queue_manager.clear_pause_flag(user_id, product_id)
    await notify_sync_start(user_id, product_name)

    start_time = time.monotonic()
    delay = await settings_db.get_delay()

    try:
        pending = await messages_db.list_after(product_id, last_message_id)
        total_to_send = total_synced + len(pending)

        if is_resume:
            text = _format_progress_text(
                "▶️ Resumed", total_synced, total_to_send, "Continuing from previous progress..."
            )
        else:
            text = _format_progress_text("▶️ Forwarding...", total_synced, total_to_send)
        progress_message_id = await _set_progress_message(bot, user_id, product_id, progress_message_id, text)

        skipped_count = progress.get("skipped_count", 0)

        for record in pending:
            # Cooperative ban check -- stop immediately instead of finishing.
            fresh_user = await users_db.get_user(user_id)
            if not fresh_user or fresh_user.get("banned"):
                await progress_db.set_sync_status(user_id, product_id, "cancelled")
                text = _format_progress_text("🚫 Cancelled (user banned)", total_synced, total_to_send)
                await _set_progress_message(bot, user_id, product_id, progress_message_id, text)
                return

            # Cooperative pause check.
            if queue_manager.is_pause_requested(user_id, product_id):
                await progress_db.set_sync_status(user_id, product_id, "paused")
                text = _format_progress_text("⏸ Paused", total_synced, total_to_send)
                await _set_progress_message(bot, user_id, product_id, progress_message_id, text)
                queue_manager.clear_pause_flag(user_id, product_id)
                return

            msg_id = record["source_message_id"]

            try:
                await bot.copy_message(chat_id=dest_id, from_chat_id=source_id, message_id=msg_id)
            except TelegramAPIError as e:
                reason = str(e).lower()
                if any(hint in reason for hint in _SKIPPABLE_ERROR_HINTS):
                    logger.warning(f"Skipped message {msg_id} for user {user_id}: {e}")
                    skipped_count += 1
                    last_message_id = msg_id
                    await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count)
                    continue

                # Possibly transient -- retry once after a short backoff.
                await asyncio.sleep(1.5)
                try:
                    await bot.copy_message(chat_id=dest_id, from_chat_id=source_id, message_id=msg_id)
                except TelegramAPIError as e2:
                    logger.warning(f"Skipped message {msg_id} for user {user_id} after retry: {e2}")
                    skipped_count += 1
                    last_message_id = msg_id
                    await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count)
                    continue

            last_message_id = msg_id
            total_synced += 1

            await progress_db.update_progress(user_id, product_id, last_message_id, total_synced)

            if total_synced % PROGRESS_INTERVAL == 0:
                text = _format_progress_text("▶️ Forwarding...", total_synced, total_to_send)
                progress_message_id = await _set_progress_message(bot, user_id, product_id, progress_message_id, text)

            await asyncio.sleep(delay)

        await progress_db.set_sync_status(user_id, product_id, "completed")

        text = _format_progress_text("✅ Forwarding Completed", total_synced, total_to_send)
        await _set_progress_message(bot, user_id, product_id, progress_message_id, text)

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
