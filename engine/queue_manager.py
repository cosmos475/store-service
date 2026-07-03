import asyncio

from engine.sync import run_initial_sync

MAX_CONCURRENT_SYNCS = 5
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)
_running_tasks: dict[tuple[int, str], asyncio.Task] = {}


async def _run_with_limit(user_id: int, product_id: str) -> None:
    async with _semaphore:
        await run_initial_sync(user_id, product_id)
    _running_tasks.pop((user_id, product_id), None)


def enqueue_sync(user_id: int, product_id: str) -> None:
    key = (user_id, product_id)
    if key in _running_tasks:
        return
    task = asyncio.create_task(_run_with_limit(user_id, product_id))
    _running_tasks[key] = task


def resume_sync(user_id: int, product_id: str) -> None:
    enqueue_sync(user_id, product_id)
