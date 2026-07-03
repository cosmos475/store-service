from config import OWNER_ID
from engine.client_holder import get_bot
from utils.formatters import summary_text, error_text


async def notify_owner(text: str) -> None:
    bot = get_bot()
    if bot:
        await bot.send_message(OWNER_ID, text)


async def notify_sync_start(user_id: int, product_name: str) -> None:
    await notify_owner(f"▶️ Sync started\n\nUser ID: {user_id}\nProduct: {product_name}")


async def notify_sync_complete(
    user_id: int, username: str, product_name: str, total: int, time_taken: str
) -> None:
    await notify_owner(
        summary_text(username, user_id, product_name, total, time_taken)
    )


async def notify_sync_error(user_id: int, product_name: str, error: str) -> None:
    await notify_owner(error_text(user_id, product_name, error))
