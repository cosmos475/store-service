import asyncio

from engine.sync import run_initial_sync

MAX_CONCURRENT_SYNCS = 5
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)
_running_tasks: dict[tuple[int, str], asyncio.Task] = {}

# Cooperative pause flags checked inside the sync loop.
_pause_flags: set[tuple[int, str]] = set()


async def _run_with_limit(user_id: int, product_id: str) -> None:
    async with _semaphore:
        await run_initial_sync(user_id, product_id)
    _running_tasks.pop((user_id, product_id), None)
    _pause_flags.discard((user_id, product_id))


def enqueue_sync(user_id: int, product_id: str) -> None:
    key = (user_id, product_id)
    _pause_flags.discard(key)
    if key in _running_tasks:
        return
    task = asyncio.create_task(_run_with_limit(user_id, product_id))
    _running_tasks[key] = task


def resume_sync(user_id: int, product_id: str) -> None:
    enqueue_sync(user_id, product_id)


def pause_sync(user_id: int, product_id: str) -> bool:
    """Request a pause. The running loop checks this flag between messages
    and exits cleanly, saving progress. Returns True if a task is currently
    running for this user/product."""
    key = (user_id, product_id)
    if key not in _running_tasks:
        return False
    _pause_flags.add(key)
    return True


def is_pause_requested(user_id: int, product_id: str) -> bool:
    return (user_id, product_id) in _pause_flags


def clear_pause_flag(user_id: int, product_id: str) -> None:
    _pause_flags.discard((user_id, product_id))


def is_running(user_id: int, product_id: str) -> bool:
    return (user_id, product_id) in _running_tasks
