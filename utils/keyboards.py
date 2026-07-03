from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def product_list_kb(products: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"product_{p['_id']}")]
        for p in products
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Add Product", callback_data="add_product")],
        [InlineKeyboardButton(text="📦 Manage Products", callback_data="manage_products")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👥 All Users", callback_data="all_users")],
        [InlineKeyboardButton(text="✅ Allowed Users", callback_data="allowed_users")],
        [InlineKeyboardButton(text="⏳ Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton(text="🚫 Banned Users", callback_data="banned_users")],
        [InlineKeyboardButton(text="🔄 Active Tasks", callback_data="active_tasks")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="statistics")],
        [InlineKeyboardButton(text="🔁 Retry Failed Syncs", callback_data="retry_failed")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(current_delay: float) -> InlineKeyboardMarkup:
    def label(v):
        return f"{v}s ✅" if v == current_delay else f"{v}s"

    rows = [
        [
            InlineKeyboardButton(text=label(1.0), callback_data="delay_1.0"),
            InlineKeyboardButton(text=label(2.0), callback_data="delay_2.0"),
            InlineKeyboardButton(text=label(3.0), callback_data="delay_3.0"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_manage_kb(product_id: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✏️ Rename", callback_data=f"rename_{product_id}"),
            InlineKeyboardButton(text="🔗 Update Source", callback_data=f"srcupd_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="🔕 Enable/Disable", callback_data=f"toggle_{product_id}"),
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"delete_{product_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="manage_products")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approval_kb(user_id: int, product_id: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Allow", callback_data=f"approve_{user_id}_{product_id}"
            ),
            InlineKeyboardButton(
                text="❌ Reject", callback_data=f"reject_{user_id}_{product_id}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔁 Change Destination Channel", callback_data="change_dest")],
        [InlineKeyboardButton(text="📊 Status", callback_data="user_status")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
