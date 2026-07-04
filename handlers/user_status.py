from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import users as users_db
from database import subscriptions as subs_db
from database import products as products_db
from database import progress as progress_db
from handlers.user_start import set_awaiting_destination
from engine.queue_manager import pause_sync, resume_sync

router = Router(name="user_status")


@router.callback_query(F.data == "user_status")
async def status_cb(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    user = await users_db.get_user(user_id)
    if not user:
        await query.answer("No data found.", show_alert=True)
        return

    subs = await subs_db.list_subscriptions()
    my_subs = [s for s in subs if s["user_id"] == user_id]

    if not my_subs:
        await query.message.reply("You have no active or pending product requests.")
        await query.answer()
        return

    lines = ["📊 Your Status:\n"]
    rows = []
    for sub in my_subs:
        product = await products_db.get_product(sub["product_id"])
        pname = product["name"] if product else "Unknown"
        line = f"• {pname}: {sub['status']}"

        if sub["status"] == "approved":
            progress = await progress_db.get_progress(user_id, sub["product_id"])
            if progress:
                status = progress.get("sync_status")
                line += f" ({status}, {progress.get('total_synced', 0)} synced)"

                if status == "in_progress":
                    rows.append([InlineKeyboardButton(
                        text=f"⏸ Pause {pname}",
                        callback_data=f"userpause_{sub['product_id']}",
                    )])
                elif status == "paused":
                    rows.append([InlineKeyboardButton(
                        text=f"▶️ Resume {pname}",
                        callback_data=f"userresume_{sub['product_id']}",
                    )])

        lines.append(line)

    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    await query.message.reply("\n".join(lines), reply_markup=kb)
    await query.answer()


@router.callback_query(F.data.startswith("userpause_"))
async def user_pause_cb(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    product_id = query.data.split("_", 1)[1]
    ok = pause_sync(user_id, product_id)
    await query.answer("⏸ Pause requested." if ok else "No active sync running.", show_alert=not ok)


@router.callback_query(F.data.startswith("userresume_"))
async def user_resume_cb(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    product_id = query.data.split("_", 1)[1]
    resume_sync(user_id, product_id)
    await query.answer("▶️ Resuming.")


@router.callback_query(F.data == "change_dest")
async def change_dest_cb(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    set_awaiting_destination(user_id)
    await query.message.reply(
        "Please forward any message from your new destination channel."
    )
    await query.answer()


def register(dp) -> None:
    dp.include_router(router)
