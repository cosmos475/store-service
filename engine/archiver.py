import logging

from aiogram import Bot, Router
from aiogram.types import Message

from database import products as products_db
from database import users as users_db
from database import subscriptions as subs_db
from database import progress as progress_db
from database import messages as messages_db

logger = logging.getLogger(__name__)

router = Router(name="archiver")


@router.channel_post()
async def handle_channel_post(message: Message, bot: Bot) -> None:
    source_id = message.chat.id
    all_products = await products_db.get_all_products()
    product = next(
        (p for p in all_products if p["source_channel_id"] == source_id), None
    )
    if not product or not product.get("enabled"):
        return

    product_id = str(product["_id"])

    # Archive first (archive-from-now-on): every new post is recorded
    # regardless of whether anyone is approved yet.
    await messages_db.archive_message(product_id, message.message_id)

    # Live-deliver to users who are already fully caught up.
    approved_subs = await subs_db.list_subscriptions(status="approved")
    for sub in approved_subs:
        if sub["product_id"] != product_id:
            continue

        user_id = sub["user_id"]
        user = await users_db.get_user(user_id)
        if not user or user.get("banned") or not user.get("destination_channel_id"):
            continue

        progress = await progress_db.get_progress(user_id, product_id)
        if not progress or progress.get("sync_status") != "completed":
            continue  # still catching up on backlog; sync.py will deliver this later

        try:
            await bot.copy_message(
                chat_id=user["destination_channel_id"],
                from_chat_id=source_id,
                message_id=message.message_id,
            )
            await progress_db.update_progress(
                user_id, product_id, message.message_id, progress.get("total_synced", 0) + 1
            )
        except Exception:
            logger.exception("Live delivery failed for user %s product %s", user_id, product_id)
            continue


def register(dp) -> None:
    dp.include_router(router)
