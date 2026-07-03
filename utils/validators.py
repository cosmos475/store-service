from aiogram import Bot
from aiogram.exceptions import TelegramAPIError


async def verify_channel_admin(bot: Bot, channel_id: int) -> bool:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(channel_id, me.id)
        if member.status not in ("administrator", "creator"):
            return False
        can_post = getattr(member, "can_post_messages", True)
        # can_post_messages is only meaningful for administrator status;
        # creator always has full rights.
        if member.status == "administrator" and can_post is False:
            return False
        return True
    except TelegramAPIError:
        return False
