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
                "skipped_count": 0,
                "failed_count": 0,
                "pinned_done": False,
                "sync_status": "in_progress",
                "progress_message_id": None,
                "completed_at": None,
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def set_progress_message_id(user_id: int, product_id: str, message_id: int) -> None:
    await col.update_one(
        _key(user_id, product_id),
        {"$set": {"progress_message_id": message_id, "last_updated": datetime.now(timezone.utc)}},
    )


async def update_progress(
    user_id: int, product_id: str, last_message_id: int, total_synced: int,
    skipped_count: int | None = None, failed_count: int | None = None,
    pinned_done: bool | None = None,
) -> None:
    update = {
        "last_message_id": last_message_id,
        "total_synced": total_synced,
        "last_updated": datetime.now(timezone.utc),
    }
    if skipped_count is not None:
        update["skipped_count"] = skipped_count
    if failed_count is not None:
        update["failed_count"] = failed_count
    if pinned_done is not None:
        update["pinned_done"] = pinned_done
    await col.update_one(_key(user_id, product_id), {"$set": update})


async def set_sync_status(user_id: int, product_id: str, status: str) -> None:
    update = {"sync_status": status, "last_updated": datetime.now(timezone.utc)}
    if status == "completed":
        update["completed_at"] = datetime.now(timezone.utc)
    await col.update_one(_key(user_id, product_id), {"$set": update})


async def get_progress(user_id: int, product_id: str) -> dict | None:
    return await col.find_one(_key(user_id, product_id))


async def list_active_syncs() -> list[dict]:
    return await col.find({"sync_status": "in_progress"}).to_list(length=None)


async def list_failed_syncs() -> list[dict]:
    return await col.find({"sync_status": "failed"}).to_list(length=None)


async def list_paused_syncs() -> list[dict]:
    return await col.find({"sync_status": "paused"}).to_list(length=None)
