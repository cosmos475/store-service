from database.client import get_db

db = get_db()
col = db["settings"]

DEFAULT_DELAY = 3.0


async def get_delay() -> float:
    doc = await col.find_one({"_id": "global"})
    if not doc:
        return DEFAULT_DELAY
    return doc.get("forward_delay", DEFAULT_DELAY)


async def set_delay(value: float) -> None:
    await col.update_one(
        {"_id": "global"}, {"$set": {"forward_delay": value}}, upsert=True
    )
