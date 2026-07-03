from datetime import datetime, timezone
from database.client import get_db

db = get_db()
col = db["messages"]


async def archive_message(product_id: str, source_message_id: int) -> None:
    await col.update_one(
        {"product_id": product_id, "source_message_id": source_message_id},
        {
            "$setOnInsert": {
                "product_id": product_id,
                "source_message_id": source_message_id,
                "archived_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def list_after(product_id: str, after_message_id: int) -> list[dict]:
    """Archived messages for a product with source_message_id > after_message_id,
    oldest first."""
    cursor = col.find(
        {"product_id": product_id, "source_message_id": {"$gt": after_message_id}}
    ).sort("source_message_id", 1)
    return await cursor.to_list(length=None)


async def count_for_product(product_id: str) -> int:
    return await col.count_documents({"product_id": product_id})


async def clear_for_product(product_id: str) -> None:
    """Wipe archive when a product's source channel is changed, so old and
    new source content is never mixed."""
    await col.delete_many({"product_id": product_id})
