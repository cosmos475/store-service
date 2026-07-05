from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from database import products as products_db
from database import subscriptions as subs_db
from database import users as users_db
from database import progress as progress_db
from database import messages as messages_db
from utils.keyboards import approval_kb
from engine.queue_manager import enqueue_sync

router = Router(name="product_selection")

_STATUS_LABELS = {
    "in_progress": "🟢 In Progress",
    "paused": "⏸ Paused",
    "completed": "✅ Completed",
    "cancelled": "🚫 Cancelled",
    "failed": "❌ Failed",
}


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]])


async def _render_product_panel(user_id: int, product_id: str, product_name: str) -> str:
    sub = await subs_db.get_subscription(user_id, product_id)

    if not sub:
        return f"📦 {product_name}\n\nNo request yet."

    if sub["status"] == "pending":
        return f"📦 {product_name}\n\n⏳ Pending approval."

    if sub["status"] == "rejected":
        return f"📦 {product_name}\n\n❌ Request rejected."

    progress = await progress_db.get_progress(user_id, product_id)
    if not progress:
        return f"📦 {product_name}\n\n✅ Approved. Starting soon..."

    current = progress.get("total_synced", 0)
    skipped = progress.get("skipped_count", 0)
    total = await messages_db.count_for_product(product_id)
    total = max(total, current)
    status = progress.get("sync_status", "in_progress")
    status_label = _STATUS_LABELS.get(status, status)

    lines = [
        f"📦 {product_name}",
        "",
        f"Forwarded: {current} / {total}",
        f"Pending: {max(total - current, 0)}",
    ]
    if skipped:
        lines.append(f"Failed: {skipped}")
    lines.append(status_label)

    if status == "completed" and progress.get("completed_at"):
        lines.append(f"Completed at: {progress['completed_at'].strftime('%Y-%m-%d %H:%M UTC')}")
    elif progress.get("last_updated"):
        lines.append(f"Last updated: {progress['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("product_"))
async def product_selected_cb(query: CallbackQuery, bot: Bot) -> None:
    user_id = query.from_user.id
    product_id = query.data.split("_", 1)[1]

    user = await users_db.get_user(user_id)
    if not user or not user.get("destination_channel_id"):
        await query.answer("Please set your destination channel first.", show_alert=True)
        return

    product = await products_db.get_product(product_id)
    if not product:
        await query.answer("Product not found.", show_alert=True)
        return

    existing = await subs_db.get_subscription(user_id, product_id)

    if not existing or existing["status"] == "rejected":
        await subs_db.create_subscription(user_id, product_id)
        username = query.from_user.username or query.from_user.first_name or str(user_id)
        await bot.send_message(
            OWNER_ID,
            f"📥 New Approval Request\n\n"
            f"User: {username}\n"
            f"User ID: {user_id}\n"
            f"Product: {product['name']}",
            reply_markup=approval_kb(user_id, product_id),
        )

    text = await _render_product_panel(user_id, product_id, product["name"])
    await query.message.edit_text(text, reply_markup=_back_kb())
    await query.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_cb(query: CallbackQuery) -> None:
    from handlers.user_start import render_main_menu
    await render_main_menu(query.message, query.from_user.id, edit=True)
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
