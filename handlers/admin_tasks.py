from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import progress as progress_db
from database import products as products_db
from database import users as users_db
from database import subscriptions as subs_db
from database import messages as messages_db
from utils.keyboards import admin_panel_kb
from engine.queue_manager import resume_sync, pause_sync

router = Router(name="admin_tasks")

_STATUS_LABELS = {
    "in_progress": "🟢 Running",
    "paused": "⏸ Paused",
    "completed": "✅ Completed",
    "cancelled": "🚫 Cancelled",
    "failed": "❌ Failed",
}


async def _render_task_block(task: dict) -> tuple[str, InlineKeyboardButton | None]:
    user_id = task["user_id"]
    product_id = task["product_id"]

    product = await products_db.get_product(product_id)
    pname = product["name"] if product else "Unknown"

    user = await users_db.get_user(user_id)
    username = user.get("username") if user else None
    who = f"👤 {user_id} (@{username})" if username else f"👤 {user_id}"

    current = task.get("total_synced", 0)
    total = await messages_db.count_for_product(product_id)
    total = max(total, current)
    pct = int((current / total) * 100) if total else 0

    status = task.get("sync_status", "in_progress")
    status_label = _STATUS_LABELS.get(status, status)

    block = (
        f"{who}\n"
        f"📦 {pname}\n"
        f"📊 {current}/{total} ({pct}%)\n"
        f"{status_label}"
    )

    button = None
    if status == "in_progress":
        button = InlineKeyboardButton(
            text=f"⏸ Pause {user_id} / {pname}",
            callback_data=f"pausesync_{user_id}_{product_id}",
        )
    elif status == "paused":
        button = InlineKeyboardButton(
            text=f"▶️ Resume {user_id} / {pname}",
            callback_data=f"resumesync_{user_id}_{product_id}",
        )

    return block, button


@router.callback_query(F.data == "active_tasks")
async def active_tasks_cb(query: CallbackQuery) -> None:
    active = await progress_db.list_active_syncs()
    paused = await progress_db.list_paused_syncs()

    blocks = []
    rows = []

    for task in active + paused:
        block, button = await _render_task_block(task)
        blocks.append(block)
        if button:
            rows.append([button])

    if not blocks:
        text = "🔄 Active Tasks\n\nNone."
    else:
        text = "🔄 Active Tasks\n\n" + "\n\n".join(blocks)

    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await query.answer()


@router.callback_query(F.data.startswith("pausesync_"))
async def pause_task_cb(query: CallbackQuery) -> None:
    _, user_id, product_id = query.data.split("_", 2)
    ok = pause_sync(int(user_id), product_id)
    await query.answer("⏸ Pause requested." if ok else "Task not running.", show_alert=not ok)
    await active_tasks_cb(query)


@router.callback_query(F.data.startswith("resumesync_"))
async def resume_task_cb(query: CallbackQuery) -> None:
    _, user_id, product_id = query.data.split("_", 2)
    resume_sync(int(user_id), product_id)
    await query.answer("▶️ Resuming.")
    await active_tasks_cb(query)


@router.callback_query(F.data == "retry_failed")
async def retry_failed_cb(query: CallbackQuery) -> None:
    failed = await progress_db.list_failed_syncs()
    if not failed:
        await query.message.edit_text("No failed syncs.", reply_markup=admin_panel_kb())
        await query.answer()
        return

    for f in failed:
        resume_sync(f["user_id"], f["product_id"])

    await query.message.edit_text(
        f"🔁 Retrying {len(failed)} failed sync(s).", reply_markup=admin_panel_kb()
    )
    await query.answer()


@router.callback_query(F.data == "statistics")
async def statistics_cb(query: CallbackQuery) -> None:
    all_users = await users_db.list_users("all")
    all_products = await products_db.get_all_products()
    approved = await subs_db.list_subscriptions(status="approved")
    pending = await subs_db.list_subscriptions(status="pending")
    active = await progress_db.list_active_syncs()

    text = (
        "📊 Statistics\n\n"
        f"Total Users: {len(all_users)}\n"
        f"Total Products: {len(all_products)}\n"
        f"Approved Subscriptions: {len(approved)}\n"
        f"Pending Requests: {len(pending)}\n"
        f"Active Syncs: {len(active)}"
    )
    await query.message.edit_text(text, reply_markup=admin_panel_kb())
    await query.answer()


def register(dp) -> None:
    dp.include_router(router)
