from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

_client = AsyncIOMotorClient(MONGO_URI)
_db = _client["notes_bot"]


def get_db():
    return _db
