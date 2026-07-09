import logging
from datetime import datetime

import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import OWNER_ID, RENDER_EXTERNAL_URL
from utils.keyboards import keep_alive_kb

logger = logging.getLogger(__name__)
router = Router(name="admin_keepalive")
router.callback_query.filter(F.from_user.id == OWNER_ID)

_last_ping_time: str | None = None
_last_ping_status: str | None = None


@router.callback_query(F.data == "keep_alive")
async def keep_alive_cb(query: CallbackQuery) -> None:
    await query.message.edit_text("🟢 Keep Alive", reply_markup=keep_alive_kb())
    await query.answer()


@router.callback_query(F.data == "ping_now")
async def ping_now_cb(query: CallbackQuery) -> None:
    global _last_ping_time, _last_ping_status

    await query.message.edit_text("🔄 Sending Ping...", reply_markup=keep_alive_kb())
    await query.answer()

    if not RENDER_EXTERNAL_URL:
        _last_ping_status = "Failed: RENDER_EXTERNAL_URL not set"
        await query.message.edit_text(
            "❌ Ping Failed\n\nReason: RENDER_EXTERNAL_URL is not configured.",
            reply_markup=keep_alive_kb(),
        )
        return

    url = RENDER_EXTERNAL_URL.rstrip("/") + "/health"
    now = datetime.now().strftime("%H:%M:%S")

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                status = resp.status
        _last_ping_time = now
        _last_ping_status = f"{status} OK" if status == 200 else f"HTTP {status}"
        await query.message.edit_text(
            f"✅ Ping Successful\n\nHTTP: {status} OK\nTime: {now}",
            reply_markup=keep_alive_kb(),
        )
    except Exception as e:
        logger.exception(f"DEBUG: keep-alive ping failed: {e}")
        _last_ping_time = now
        _last_ping_status = f"Failed: {e}"
        await query.message.edit_text(
            f"❌ Ping Failed\n\nReason: {e}\nTime: {now}",
            reply_markup=keep_alive_kb(),
        )


@router.callback_query(F.data == "ping_status")
async def ping_status_cb(query: CallbackQuery) -> None:
    text = (
        "📊 Keep Alive Status\n\n"
        f"Last Ping Time: {_last_ping_time or 'Never'}\n"
        f"Last HTTP Status: {_last_ping_status or 'N/A'}\n"
        f"Health Endpoint: {(RENDER_EXTERNAL_URL.rstrip('/') + '/health') if RENDER_EXTERNAL_URL else 'Not configured'}\n"
        "Current Mode: Manual"
    )
    await query.message.edit_text(text, reply_markup=keep_alive_kb())
    await query.answer()


def register(dp) -> None:
    dp.include_router(router)
