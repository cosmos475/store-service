import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config import OWNER_ID
from utils.keyboards import admin_main_kb, admin_panel_kb

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


@router.message(Command("start"), F.chat.type == "private", F.from_user.id == OWNER_ID)
async def owner_start(message: Message, bot: Bot) -> None:
    logger.info(f"DEBUG: owner /start received from user_id={message.from_user.id}")
    await message.reply("👑 Admin Menu", reply_markup=admin_main_kb())
    logger.info("DEBUG: owner /start reply sent")


@router.callback_query(F.data == "admin_main")
async def admin_main_cb(query: CallbackQuery) -> None:
    await query.message.edit_text("👑 Admin Menu", reply_markup=admin_main_kb())
    await query.answer()


@router.callback_query(F.data == "admin_panel")
async def admin_panel_cb(query: CallbackQuery) -> None:
    await query.message.edit_text("Admin Panel", reply_markup=admin_panel_kb())
    await query.answer()


def register(dp) -> None:
    dp.include_router(router)
