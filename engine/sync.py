import asyncio
import time
import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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

_BOX_TEMPLATE = """
╔════❰ {header} ❱═❍⊱❁۪۪
║╭━━━━━━━━━━━━━━━➣
║┣⪼📦 <b>Pʀᴏᴅᴜᴄᴛ:</b> <code>{product_name}</code>
║┃
║┣⪼📍 <b>Cᴜʀʀᴇɴᴛ/Tᴏᴛᴀʟ:</b> <code>{current}</code>/<code>{total}</code>
║┃
║┣⪼✅ <b>Dᴇʟɪᴠᴇʀᴇᴅ:</b> <code>{delivered}</code>
║┃
║┣⪼⏭️ <b>Sᴋɪᴘᴘᴇᴅ:</b> <code>{skipped}</code>
║┃
║┣⪼❌ <b>Fᴀɪʟᴇᴅ:</b> <code>{failed}</code>
║┃
{extra_line}║┣⪼📊 <b>Sᴛᴀᴛᴜs:</b> <code>{status}</code>
║┃
║┣⪼𖨠 <b>Pᴇʀᴄᴇɴᴛᴀɢᴇ:</b> <code>{percentage}</code> %
║┃
║┣⪼⏱ <b>ETA:</b> <code>{eta}</code>
║╰━━━━━━━━━━━━━━━➣
╚════❰ {footer} ❱══❍⊱❁۪۪
""".strip()

_COMPLETION_TEMPLATE = """
╔════❰ ᴅᴇʟɪᴠᴇʀʏ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ❱═❍⊱❁۪۪
║╭━━━━━━━━━━━━━━━➣
║┣⪼📦 <b>Pʀᴏᴅᴜᴄᴛ:</b> <code>{product_name}</code>
║┃
║┣⪼✅ <b>Dᴇʟɪᴠᴇʀᴇᴅ:</b> <code>{delivered}</code>/<code>{total}</code>
║┃
║┣⪼⏭️ <b>Sᴋɪᴘᴘᴇᴅ:</b> <code>{skipped}</code>
║┃
║┣⪼❌ <b>Fᴀɪʟᴇᴅ:</b> <code>{failed}</code>
║┃
║┣⪼⏱ <b>Tɪᴍᴇ Tᴀᴋᴇɴ:</b> <code>{time_taken}</code>
║╰━━━━━━━━━━━━━━━➣
╚════❰ ✅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ❱══❍⊱❁۪۪
""".strip()


def _format_eta(seconds: int) -> str:
    if seconds <= 0:
        return "-"
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {secs}s"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def _format_progress_text(
    product_name: str, header: str, footer: str, status: str,
    delivered: int, skipped: int, failed: int, total: int,
    start_time: float | None = None, sleeping_for: int | None = None,
) -> str:
    current = delivered + skipped + failed
    percentage = min(100, round(current * 100 / total)) if total else 0

    eta = "-"
    if status == "Forwarding" and start_time:
        elapsed = max(1, time.time() - start_time)
        speed = current / elapsed
        remaining = max(0, total - current)
        if speed > 0:
            eta = _format_eta(round(remaining / speed))

    extra_line = ""
    if sleeping_for is not None:
        extra_line = f"║┣⪼💤 <b>Sʟᴇᴇᴘɪɴɢ:</b> <code>{sleeping_for}s</code>\n║┃\n"

    return _BOX_TEMPLATE.format(
        header=header, footer=footer, product_name=product_name,
        current=current, total=total, delivered=delivered, skipped=skipped,
        failed=failed, status=status, percentage=percentage, eta=eta,
        extra_line=extra_line,
    )


def _progress_keyboard(user_id: int, product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏸ Pause", callback_data=f"userpause_{product_id}")
    ]])


async def _set_progress_message(
    bot, user_id: int, product_id: str, progress_message_id, text: str, show_button: bool = True
) -> int | None:
    """Edit the existing progress message, or send a new one if none exists
    yet or the edit fails (e.g. message deleted by user)."""
    markup = _progress_keyboard(user_id, product_id) if show_button else None

    if progress_message_id:
        try:
            await bot.edit_message_text(chat_id=user_id, message_id=progress_message_id, text=text, reply_markup=markup)
            return progress_message_id
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return progress_message_id
            logger.warning(f"Progress message edit failed for user {user_id}, sending new one: {e}")
        except TelegramAPIError as e:
            logger.warning(f"Progress message edit failed for user {user_id}, sending new one: {e}")

    try:
        msg = await bot.send_message(user_id, text, reply_markup=markup)
        await progress_db.set_progress_message_id(user_id, product_id, msg.message_id)
        return msg.message_id
    except TelegramAPIError:
        logger.exception(f"Failed to send progress message to user {user_id}")
        return progress_message_id


async def _pin_first_message(bot, user_id: int, dest_id: int, sent_message, pin_state: dict) -> None:
    """Pins the first successfully delivered message in the destination
    chat. Retries once on transient errors, but never blocks or aborts
    delivery -- pinning is best-effort. Notifies the user once if it
    ultimately fails (e.g. missing Pin Messages permission)."""
    if sent_message is None or pin_state.get("done"):
        return
    pin_state["done"] = True  # mark immediately so we never retry-storm this

    last_error = None
    for attempt in range(2):
        try:
            await bot.pin_chat_message(chat_id=dest_id, message_id=sent_message.message_id, disable_notification=False)
            return
        except TelegramAPIError as e:
            last_error = e
            await asyncio.sleep(1)

    logger.warning(f"Auto-pin failed for user {user_id}, chat {dest_id}: {last_error}")
    try:
        await bot.send_message(user_id, "⚠️ Auto pin failed because bot has not pin rights or permission in your destination channel.")
    except Exception:
        pass


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

    # pinned_done survives a resume within the same process (in-memory);
    # after a full restart it defaults to False, but if total_synced > 0
    # we treat the first message as already pinned rather than re-pinning
    # (avoids overriding something the user pinned manually in the meantime).
    pin_state = {"done": bool(progress.get("pinned_done")) or total_synced > 0}

    await progress_db.set_sync_status(user_id, product_id, "in_progress")
    queue_manager.clear_pause_flag(user_id, product_id)
    await notify_sync_start(user_id, product_name)

    start_time = time.monotonic()
    wall_start = time.time()
    delay = await settings_db.get_delay()

    try:
        pending = await messages_db.list_after(product_id, last_message_id)
        total_to_send = total_synced + len(pending)

        skipped_count = progress.get("skipped_count", 0)
        failed_count = progress.get("failed_count", 0)

        header = "▶️ Rᴇsᴜᴍᴇᴅ" if is_resume else "▶️ Fᴏʀᴡᴀʀᴅ Sᴛᴀᴛᴜs"
        text = _format_progress_text(
            product_name, header, "Fᴏʀᴡᴀʀᴅɪɴɢ...", "Forwarding",
            total_synced, skipped_count, failed_count, total_to_send, wall_start,
        )
        progress_message_id = await _set_progress_message(bot, user_id, product_id, progress_message_id, text)

        for record in pending:
            # Cooperative ban check -- stop immediately instead of finishing.
            fresh_user = await users_db.get_user(user_id)
            if not fresh_user or fresh_user.get("banned"):
                await progress_db.set_sync_status(user_id, product_id, "cancelled")
                text = _format_progress_text(
                    product_name, "🚫 Cᴀɴᴄᴇʟʟᴇᴅ", "ᴄᴀɴᴄᴇʟʟᴇᴅ", "Cancelled (user banned)",
                    total_synced, skipped_count, failed_count, total_to_send,
                )
                await _set_progress_message(bot, user_id, product_id, progress_message_id, text, show_button=False)
                return

            # Cooperative pause check.
            if queue_manager.is_pause_requested(user_id, product_id):
                await progress_db.set_sync_status(user_id, product_id, "paused")
                await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count, failed_count, pinned_done=pin_state["done"])
                text = _format_progress_text(
                    product_name, "⏸ Pᴀᴜsᴇᴅ", "ᴘᴀᴜsᴇᴅ", "Paused",
                    total_synced, skipped_count, failed_count, total_to_send,
                )
                await _set_progress_message(bot, user_id, product_id, progress_message_id, text, show_button=False)
                queue_manager.clear_pause_flag(user_id, product_id)
                return

            msg_id = record["source_message_id"]
            sent_message = None

            try:
                sent_message = await bot.copy_message(chat_id=dest_id, from_chat_id=source_id, message_id=msg_id)
            except TelegramRetryAfter as e:
                text = _format_progress_text(
                    product_name, "▶️ Fᴏʀᴡᴀʀᴅ Sᴛᴀᴛᴜs", "Fᴏʀᴡᴀʀᴅɪɴɢ...", "Forwarding",
                    total_synced, skipped_count, failed_count, total_to_send, wall_start,
                    sleeping_for=e.retry_after,
                )
                await _set_progress_message(bot, user_id, product_id, progress_message_id, text)
                await asyncio.sleep(e.retry_after)
                try:
                    sent_message = await bot.copy_message(chat_id=dest_id, from_chat_id=source_id, message_id=msg_id)
                except TelegramAPIError as e2:
                    logger.warning(f"Failed message {msg_id} for user {user_id} after flood-wait retry: {e2}")
                    failed_count += 1
                    last_message_id = msg_id
                    await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count, failed_count, pinned_done=pin_state["done"])
                    continue
            except TelegramAPIError as e:
                reason = str(e).lower()
                if any(hint in reason for hint in _SKIPPABLE_ERROR_HINTS):
                    logger.warning(f"Skipped message {msg_id} for user {user_id}: {e}")
                    skipped_count += 1
                    last_message_id = msg_id
                    await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count, failed_count, pinned_done=pin_state["done"])
                    continue

                # Possibly transient -- retry once after a short backoff.
                await asyncio.sleep(1.5)
                try:
                    sent_message = await bot.copy_message(chat_id=dest_id, from_chat_id=source_id, message_id=msg_id)
                except TelegramAPIError as e2:
                    logger.warning(f"Failed message {msg_id} for user {user_id} after retry: {e2}")
                    failed_count += 1
                    last_message_id = msg_id
                    await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count, failed_count, pinned_done=pin_state["done"])
                    continue

            await _pin_first_message(bot, user_id, dest_id, sent_message, pin_state)

            last_message_id = msg_id
            total_synced += 1

            await progress_db.update_progress(user_id, product_id, last_message_id, total_synced, skipped_count, failed_count, pinned_done=pin_state["done"])

            if total_synced % PROGRESS_INTERVAL == 0:
                text = _format_progress_text(
                    product_name, "▶️ Fᴏʀᴡᴀʀᴅ Sᴛᴀᴛᴜs", "Fᴏʀᴡᴀʀᴅɪɴɢ...", "Forwarding",
                    total_synced, skipped_count, failed_count, total_to_send, wall_start,
                )
                progress_message_id = await _set_progress_message(bot, user_id, product_id, progress_message_id, text)

            await asyncio.sleep(delay)

        await progress_db.set_sync_status(user_id, product_id, "completed")

        elapsed = time.monotonic() - start_time
        time_taken = _format_duration(elapsed)

        completion_text = _COMPLETION_TEMPLATE.format(
            product_name=product_name, delivered=total_synced, total=total_to_send,
            skipped=skipped_count, failed=failed_count, time_taken=time_taken,
        )
        await _set_progress_message(bot, user_id, product_id, progress_message_id, completion_text, show_button=False)

        try:
            await bot.send_message(dest_id, "That's it ❤️")
        except Exception as e:
            logger.warning(f"Could not send completion message to destination {dest_id}: {e}")

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
