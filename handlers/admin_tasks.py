from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import progress as progress_db
from database import products as products_db
from database import users as users_db
from database import subscriptions as subs_db
from utils.keyboards import admin_panel_kb
from engine.queue_manager import resume_sync

router = Router(name="admin_tasks")


@router.callback_query(F.data == "active_tasks")
async def active_tasks_cb(query: CallbackQuery) -> None:
    active = await progress_db.list_active_syncs()
    lines = ["🔄 Active Tasks\n"]
    for a in active:
        product = await products_db.get_product(a["product_id"])
        pname = product["name"] if product else "Unknown"
        lines.append(f"• {a['user_id']} — {pname} ({a.get('total_synced', 0)} synced)")
    if len(lines) == 1:
        lines.append("None.")
    await query.message.edit_text("\n".join(lines), reply_markup=admin_panel_kb())
    await query.answer()


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
