def progress_text(current: int, total: int) -> str:
    return f"Forwarding...\n\n{current} / {total}"


def summary_text(
    username: str,
    user_id: int,
    product_name: str,
    total: int,
    time_taken: str,
) -> str:
    return (
        "✅ Sync Completed\n\n"
        f"User: {username}\n"
        f"User ID: {user_id}\n"
        f"Product: {product_name}\n"
        f"Total Delivered: {total}\n"
        f"Time Taken: {time_taken}"
    )


def error_text(user_id: int, product_name: str, error: str) -> str:
    return (
        "❌ Sync Failed\n\n"
        f"User ID: {user_id}\n"
        f"Product: {product_name}\n"
        f"Error: {error}"
    )
