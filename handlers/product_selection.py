from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import OWNER_ID
from database import products as products_db
from database import subscriptions as subs_db
from database import users as users_db
from database import progress as progress_db
from utils.keyboards import approval_kb
from engine.queue_manager import enqueue_sync

router = Router(name="product_selection")


@router.callback_query(F.data.startswith("product_"))
async def product_selected_cb(query: CallbackQuery, bot: Bot) -> None:
    user_id = query.from_user.id
    product_id = query.data.split("_", 1)[1]

    user = await users_db.get_user(user_id)
    if not user or not user.get("destination_channel_id"):
        await query.answer("Please set your destination channel first.", show_alert=True)
        return

    existing = await subs_db.get_subscription(user_id, product_id)
    if existing and existing["status"] in ("pending", "approved"):
        await query.answer(f"You already have a {existing['status']} request for this product.", show_alert=True)
        return

    await subs_db.create_subscription(user_id, product_id)

    product = await products_db.get_product(product_id)
    username = query.from_user.username or query.from_user.first_name or str(user_id)

    await bot.send_message(
        OWNER_ID,
        f"📥 New Approval Request\n\n"
        f"User: {username}\n"
        f"User ID: {user_id}\n"
        f"Product: {product['name']}",
        reply_markup=approval_kb(user_id, product_id),
    )

    await query.message.reply("⏳ Waiting for approval.")
    await query.answer()


@router.callback_query(F.data.startswith("approve_"))
async def approve_cb(query: CallbackQuery, bot: Bot) -> None:
    if query.from_user.id != OWNER_ID:
        await query.answer("Not authorized.", show_alert=True)
        return

    _, user_id, product_id = query.data.split("_", 2)
    user_id = int(user_id)

    sub = await subs_db.get_subscription(user_id, product_id)
    if not sub:
        await query.answer("Subscription not found.", show_alert=True)
        return

    await subs_db.update_status(str(sub["_id"]), "approved")
    await progress_db.init_progress(user_id, product_id)

    product = await products_db.get_product(product_id)
    try:
        await bot.send_message(
            user_id, f"✅ Approved for {product['name']}. Starting delivery..."
        )
    except Exception:
        pass

    enqueue_sync(user_id, product_id)

    await query.message.edit_text(query.message.text + "\n\n✅ Approved")
    await query.answer()


@router.callback_query(F.data.startswith("reject_"))
async def reject_cb(query: CallbackQuery, bot: Bot) -> None:
    if query.from_user.id != OWNER_ID:
        await query.answer("Not authorized.", show_alert=True)
        return

    _, user_id, product_id = query.data.split("_", 2)
    user_id = int(user_id)

    sub = await subs_db.get_subscription(user_id, product_id)
    if sub:
        await subs_db.update_status(str(sub["_id"]), "rejected")

    try:
        await bot.send_message(user_id, "❌ Your request was rejected.")
    except Exception:
        pass

    await query.message.edit_text(query.message.text + "\n\n❌ Rejected")
    await query.answer()


def register(dp) -> None:
    dp.include_router(router)
