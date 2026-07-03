from datetime import datetime, timezone
from database.client import get_db

db = get_db()
col = db["progress"]


def _key(user_id: int, product_id: str) -> dict:
    return {"user_id": user_id, "product_id": product_id}


async def init_progress(user_id: int, product_id: str) -> None:
    await col.update_one(
        _key(user_id, product_id),
        {
            "$set": {
                "last_message_id": 0,
                "total_synced": 0,
                "sync_status": "in_progress",
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def update_progress(
    user_id: int, product_id: str, last_message_id: int, total_synced: int
) -> None:
    await col.update_one(
        _key(user_id, product_id),
        {
            "$set": {
                "last_message_id": last_message_id,
                "total_synced": total_synced,
                "last_updated": datetime.now(timezone.utc),
            }
        },
    )


async def set_sync_status(user_id: int, product_id: str, status: str) -> None:
    await col.update_one(
        _key(user_id, product_id),
        {"$set": {"sync_status": status, "last_updated": datetime.now(timezone.utc)}},
    )


async def get_progress(user_id: int, product_id: str) -> dict | None:
    return await col.find_one(_key(user_id, product_id))


async def list_active_syncs() -> list[dict]:
    return await col.find({"sync_status": "in_progress"}).to_list(length=None)


async def list_failed_syncs() -> list[dict]:
    return await col.find({"sync_status": "failed"}).to_list(length=None)
