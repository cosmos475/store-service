from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import settings as settings_db
from utils.keyboards import settings_kb

router = Router(name="admin_settings")


@router.callback_query(F.data == "settings")
async def settings_cb(query: CallbackQuery) -> None:
    current = await settings_db.get_delay()
    await query.message.edit_text(
        f"⚙️ Settings\n\nForward Delay: {current}s", reply_markup=settings_kb(current)
    )
    await query.answer()


@router.callback_query(F.data.startswith("delay_"))
async def delay_set_cb(query: CallbackQuery) -> None:
    value = float(query.data.split("_", 1)[1])
    await settings_db.set_delay(value)
    await query.message.edit_text(
        f"⚙️ Settings\n\nForward Delay: {value}s", reply_markup=settings_kb(value)
    )
    await query.answer(f"Delay set to {value}s")


def register(dp) -> None:
    dp.include_router(router)
