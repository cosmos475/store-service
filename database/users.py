from datetime import datetime, timezone
from database.client import get_db

db = get_db()
col = db["users"]


async def upsert_user(user_id: int, username: str) -> None:
    await col.update_one(
        {"_id": user_id},
        {
            "$set": {"username": username},
            "$setOnInsert": {
                "banned": False,
                "destination_channel_id": None,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


async def set_destination(user_id: int, channel_id: int) -> None:
    await col.update_one(
        {"_id": user_id}, {"$set": {"destination_channel_id": channel_id}}
    )


async def get_user(user_id: int) -> dict | None:
    return await col.find_one({"_id": user_id})


async def ban_user(user_id: int) -> bool:
    result = await col.update_one({"_id": user_id}, {"$set": {"banned": True}})
    return result.modified_count > 0


async def unban_user(user_id: int) -> bool:
    result = await col.update_one({"_id": user_id}, {"$set": {"banned": False}})
    return result.modified_count > 0


async def list_users(filter: str = "all") -> list[dict]:
    query = {}
    if filter == "banned":
        query = {"banned": True}
    return await col.find(query).to_list(length=None)
