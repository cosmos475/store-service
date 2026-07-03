from datetime import datetime, timezone
from bson import ObjectId
from database.client import get_db

db = get_db()
col = db["subscriptions"]


async def create_subscription(user_id: int, product_id: str) -> str:
    doc = {
        "user_id": user_id,
        "product_id": product_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    result = await col.insert_one(doc)
    return str(result.inserted_id)


async def get_subscription(user_id: int, product_id: str) -> dict | None:
    return await col.find_one({"user_id": user_id, "product_id": product_id})


async def update_status(sub_id: str, status: str) -> bool:
    result = await col.update_one(
        {"_id": ObjectId(sub_id)}, {"$set": {"status": status}}
    )
    return result.modified_count > 0


async def list_subscriptions(status: str | None = None) -> list[dict]:
    query = {"status": status} if status else {}
    return await col.find(query).to_list(length=None)
