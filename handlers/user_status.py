from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import users as users_db
from database import subscriptions as subs_db
from database import products as products_db
from database import progress as progress_db
from handlers.user_start import set_awaiting_destination

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
    for sub in my_subs:
        product = await products_db.get_product(sub["product_id"])
        pname = product["name"] if product else "Unknown"
        line = f"• {pname}: {sub['status']}"

        if sub["status"] == "approved":
            progress = await progress_db.get_progress(user_id, sub["product_id"])
            if progress:
                line += f" ({progress.get('sync_status')}, {progress.get('total_synced', 0)} synced)"

        lines.append(line)

    await query.message.reply("\n".join(lines))
    await query.answer()


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
