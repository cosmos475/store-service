from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import users as users_db
from database import subscriptions as subs_db
from database import products as products_db
from utils.keyboards import admin_panel_kb

router = Router(name="admin_users")


@router.callback_query(F.data == "all_users")
async def all_users_cb(query: CallbackQuery) -> None:
    users = await users_db.list_users("all")
    text = _format_user_list("👥 All Users", users)
    await query.message.edit_text(text, reply_markup=admin_panel_kb())
    await query.answer()


@router.callback_query(F.data == "allowed_users")
async def allowed_users_cb(query: CallbackQuery) -> None:
    subs = await subs_db.list_subscriptions(status="approved")
    lines = ["✅ Allowed Users\n"]
    for sub in subs:
        product = await products_db.get_product(sub["product_id"])
        pname = product["name"] if product else "Unknown"
        lines.append(f"• {sub['user_id']} — {pname}")
    if len(lines) == 1:
        lines.append("None.")
    await query.message.edit_text("\n".join(lines), reply_markup=admin_panel_kb())
    await query.answer()


@router.callback_query(F.data == "pending_requests")
async def pending_requests_cb(query: CallbackQuery) -> None:
    subs = await subs_db.list_subscriptions(status="pending")
    lines = ["⏳ Pending Requests\n"]
    for sub in subs:
        product = await products_db.get_product(sub["product_id"])
        pname = product["name"] if product else "Unknown"
        lines.append(f"• {sub['user_id']} — {pname}")
    if len(lines) == 1:
        lines.append("None.")
    await query.message.edit_text("\n".join(lines), reply_markup=admin_panel_kb())
    await query.answer()


@router.callback_query(F.data == "banned_users")
async def banned_users_cb(query: CallbackQuery) -> None:
    users = await users_db.list_users("banned")
    text = _format_user_list("🚫 Banned Users", users)
    await query.message.edit_text(text, reply_markup=admin_panel_kb())
    await query.answer()


def _format_user_list(title: str, users: list) -> str:
    lines = [f"{title}\n"]
    for u in users:
        uname = u.get("username") or "no_username"
        lines.append(f"• {u['_id']} (@{uname})")
    if len(lines) == 1:
        lines.append("None.")
    return "\n".join(lines)


def register(dp) -> None:
    dp.include_router(router)
