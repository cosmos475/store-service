import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID
from database import users as users_db
from database import products as products_db
from utils.keyboards import user_main_kb, product_list_kb
from utils.validators import verify_channel_admin

logger = logging.getLogger(__name__)
router = Router(name="user_start")

# in-memory state: user_id -> "awaiting_destination"
_state: dict[int, str] = {}


@router.message(Command("start"), F.chat.type == "private", F.from_user.id != OWNER_ID)
async def start_handler(message: Message) -> None:
    logger.info(f"DEBUG: /start received from user_id={message.from_user.id}")

    user_id = message.from_user.id

    await users_db.upsert_user(user_id, message.from_user.username or "")
    user = await users_db.get_user(user_id)

    if user.get("banned"):
        await message.reply("🚫 You are banned from using this bot.")
        return

    if not user.get("destination_channel_id"):
        _state[user_id] = "awaiting_destination"
        await message.reply(
            "Welcome! Please forward any message from your destination channel "
            "to set it up.\n\nMake sure the bot is added as admin with post permission."
        )
        return

    await _show_main_menu(message)
    logger.info(f"DEBUG: /start reply sent to user_id={user_id}")


@router.message(
    F.chat.type == "private",
    F.from_user.id != OWNER_ID,
    F.forward_origin,
    ~Command("start"),
)
async def forwarded_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id

    if _state.get(user_id) != "awaiting_destination":
        return

    fwd_origin = message.forward_origin
    fwd_chat = getattr(fwd_origin, "chat", None)
    if not fwd_chat or fwd_chat.type != "channel":
        await message.reply("❌ Please forward a message from a Telegram channel.")
        return

    is_admin = await verify_channel_admin(bot, fwd_chat.id)
    if not is_admin:
        await message.reply(
            "❌ The bot is not an admin in that channel, or lacks post permission.\n"
            "Please fix this and forward a message again."
        )
        return

    await users_db.set_destination(user_id, fwd_chat.id)
    _state.pop(user_id, None)
    await message.reply("✅ Destination channel saved.")
    await _show_main_menu(message)


async def _show_main_menu(message: Message) -> None:
    products = await products_db.get_all_products(enabled_only=True)
    if not products:
        await message.reply("No products available right now.", reply_markup=user_main_kb())
        return
    await message.reply("Select a product:", reply_markup=product_list_kb(products))
    await message.reply("Other options:", reply_markup=user_main_kb())


def set_awaiting_destination(user_id: int) -> None:
    _state[user_id] = "awaiting_destination"


def register(dp) -> None:
    dp.include_router(router)
