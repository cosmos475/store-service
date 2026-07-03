from datetime import datetime, timezone
from bson import ObjectId
from database.client import get_db
from database import messages as messages_db

db = get_db()
col = db["products"]


async def add_product(name: str, source_channel_id: int) -> str:
    doc = {
        "name": name,
        "source_channel_id": source_channel_id,
        "enabled": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await col.insert_one(doc)
    return str(result.inserted_id)


async def get_product(product_id: str) -> dict | None:
    return await col.find_one({"_id": ObjectId(product_id)})


async def get_all_products(enabled_only: bool = False) -> list[dict]:
    query = {"enabled": True} if enabled_only else {}
    return await col.find(query).to_list(length=None)


async def rename_product(product_id: str, new_name: str) -> bool:
    result = await col.update_one(
        {"_id": ObjectId(product_id)}, {"$set": {"name": new_name}}
    )
    return result.modified_count > 0


async def update_source(product_id: str, source_channel_id: int) -> bool:
    result = await col.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"source_channel_id": source_channel_id}},
    )
    # Source changed -> wipe old archive so content from two different
    # channels is never mixed under the same product.
    await messages_db.clear_for_product(product_id)
    return result.modified_count > 0


async def toggle_product(product_id: str, enabled: bool) -> bool:
    result = await col.update_one(
        {"_id": ObjectId(product_id)}, {"$set": {"enabled": enabled}}
    )
    return result.modified_count > 0


async def delete_product(product_id: str) -> bool:
    result = await col.delete_one({"_id": ObjectId(product_id)})
    return result.deleted_count > 0
