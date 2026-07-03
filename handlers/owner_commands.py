from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import OWNER_ID
from database import users as users_db
from database import subscriptions as subs_db
from database import products as products_db
from engine.queue_manager import resume_sync

router = Router(name="owner_commands")


@router.message(Command("ban"), F.chat.type == "private", F.from_user.id == OWNER_ID)
async def ban_cmd(message: Message, command: CommandObject) -> None:
    target_id = _parse_target(command)
    if target_id is None:
        await message.reply("Usage: /ban <user_id>")
        return
    ok = await users_db.ban_user(target_id)
    await message.reply("✅ Banned." if ok else "User not found.")


@router.message(Command("unban"), F.chat.type == "private", F.from_user.id == OWNER_ID)
async def unban_cmd(message: Message, command: CommandObject) -> None:
    target_id = _parse_target(command)
    if target_id is None:
        await message.reply("Usage: /unban <user_id>")
        return
    ok = await users_db.unban_user(target_id)
    await message.reply("✅ Unbanned." if ok else "User not found.")


@router.message(Command("resume"), F.chat.type == "private", F.from_user.id == OWNER_ID)
async def resume_cmd(message: Message, command: CommandObject) -> None:
    target_id = _parse_target(command)
    if target_id is None:
        await message.reply("Usage: /resume <user_id>")
        return

    subs = await subs_db.list_subscriptions(status="approved")
    my_subs = [s for s in subs if s["user_id"] == target_id]

    if not my_subs:
        await message.reply("No approved subscriptions found for this user.")
        return

    if len(my_subs) == 1:
        product_id = my_subs[0]["product_id"]
        resume_sync(target_id, product_id)
        product = await products_db.get_product(product_id)
        await message.reply(f"▶️ Resuming sync for {product['name']}.")
        return

    lines = ["This user has multiple products. Resuming all:"]
    for sub in my_subs:
        product = await products_db.get_product(sub["product_id"])
        resume_sync(target_id, sub["product_id"])
        lines.append(f"• {product['name']}")
    await message.reply("\n".join(lines))


def _parse_target(command: CommandObject) -> int | None:
    if not command.args:
        return None
    parts = command.args.split()
    if len(parts) != 1:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def register(dp) -> None:
    dp.include_router(router)
