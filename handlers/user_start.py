import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from database import users as users_db
from database import products as products_db
from utils.validators import verify_channel_admin

logger = logging.getLogger(__name__)
router = Router(name="user_start")

# in-memory state: user_id -> "awaiting_destination"
_state: dict[int, str] = {}

# in-memory: user_id -> main menu message_id, so /start edits instead of resending
_menu_message_id: dict[int, int] = {}


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

    await render_main_menu(message, user_id, edit=False)
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
    await render_main_menu(message, user_id, edit=False)


def _main_menu_kb(products: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"product_{p['_id']}")]
        for p in products
    ]
    rows.append([
        InlineKeyboardButton(text="📊 Status", callback_data="user_status"),
        InlineKeyboardButton(text="🔁 Change Destination", callback_data="change_dest"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def render_main_menu(message: Message, user_id: int, edit: bool) -> None:
    """Single main menu: products + Status + Change Destination in one
    message, edited in place on repeat visits to avoid chat clutter."""
    products = await products_db.get_all_products(enabled_only=True)
    kb = _main_menu_kb(products)
    text = "📋 Main Menu\n\nSelect a product, or check your status / change destination below." if products \
        else "📋 Main Menu\n\nNo products available right now."

    message_id = _menu_message_id.get(user_id)

    if edit and message_id:
        try:
            await message.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=text, reply_markup=kb)
            return
        except Exception:
            pass  # fall through to sending a fresh menu

    sent = await message.reply(text, reply_markup=kb)
    _menu_message_id[user_id] = sent.message_id


def set_awaiting_destination(user_id: int) -> None:
    _state[user_id] = "awaiting_destination"


def register(dp) -> None:
    dp.include_router(router)
