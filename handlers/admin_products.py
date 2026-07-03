from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from database import products as products_db
from utils.keyboards import product_manage_kb, admin_panel_kb

router = Router(name="admin_products")

# in-memory admin conversation state
# states: awaiting_product_name, awaiting_product_source, awaiting_rename_<id>, awaiting_source_update_<id>
_state: dict[int, str] = {}
_pending_name: dict[int, str] = {}


@router.callback_query(F.data == "add_product")
async def add_product_start(query: CallbackQuery) -> None:
    _state[OWNER_ID] = "awaiting_product_name"
    await query.message.reply("Send the product name.")
    await query.answer()


@router.callback_query(F.data == "manage_products")
async def manage_products_cb(query: CallbackQuery) -> None:
    all_products = await products_db.get_all_products()
    if not all_products:
        await query.message.edit_text("No products yet.", reply_markup=admin_panel_kb())
        await query.answer()
        return

    rows = [
        [InlineKeyboardButton(
            text=f"{p['name']} {'✅' if p['enabled'] else '🔕'}",
            callback_data=f"viewproduct_{p['_id']}",
        )]
        for p in all_products
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin_main")])
    await query.message.edit_text("Products:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await query.answer()


@router.callback_query(F.data.startswith("viewproduct_"))
async def view_product_cb(query: CallbackQuery) -> None:
    product_id = query.data.split("_", 1)[1]
    product = await products_db.get_product(product_id)
    if not product:
        await query.answer("Not found.", show_alert=True)
        return
    text = (
        f"Product: {product['name']}\n"
        f"Source Channel ID: {product['source_channel_id']}\n"
        f"Status: {'Enabled' if product['enabled'] else 'Disabled'}"
    )
    await query.message.edit_text(text, reply_markup=product_manage_kb(product_id))
    await query.answer()


@router.callback_query(F.data.startswith("rename_"))
async def rename_start(query: CallbackQuery) -> None:
    product_id = query.data.split("_", 1)[1]
    _state[OWNER_ID] = f"awaiting_rename_{product_id}"
    await query.message.reply("Send the new product name.")
    await query.answer()


@router.callback_query(F.data.startswith("srcupd_"))
async def source_update_start(query: CallbackQuery) -> None:
    product_id = query.data.split("_", 1)[1]
    _state[OWNER_ID] = f"awaiting_source_update_{product_id}"
    await query.message.reply("Forward any message from the new source channel.")
    await query.answer()


@router.callback_query(F.data.startswith("toggle_"))
async def toggle_cb(query: CallbackQuery) -> None:
    product_id = query.data.split("_", 1)[1]
    product = await products_db.get_product(product_id)
    if not product:
        await query.answer("Not found.", show_alert=True)
        return
    new_state = not product["enabled"]
    await products_db.toggle_product(product_id, new_state)
    await query.answer(f"{'Enabled' if new_state else 'Disabled'}.")
    product = await products_db.get_product(product_id)
    text = (
        f"Product: {product['name']}\n"
        f"Source Channel ID: {product['source_channel_id']}\n"
        f"Status: {'Enabled' if product['enabled'] else 'Disabled'}"
    )
    await query.message.edit_text(text, reply_markup=product_manage_kb(product_id))


@router.callback_query(F.data.startswith("delete_"))
async def delete_cb(query: CallbackQuery) -> None:
    product_id = query.data.split("_", 1)[1]
    await products_db.delete_product(product_id)
    await query.answer("Deleted.")
    await manage_products_cb(query)


@router.message(
    F.chat.type == "private",
    F.from_user.id == OWNER_ID,
    F.text,
    ~Command("start", "ban", "unban", "resume"),
)
async def text_state_handler(message: Message) -> None:
    state = _state.get(OWNER_ID)
    if not state:
        return

    if state == "awaiting_product_name":
        _pending_name[OWNER_ID] = message.text.strip()
        _state[OWNER_ID] = "awaiting_product_source"
        await message.reply("Now forward any message from that product's source channel.")
        return

    if state.startswith("awaiting_rename_"):
        product_id = state.split("_", 2)[2]
        await products_db.rename_product(product_id, message.text.strip())
        _state.pop(OWNER_ID, None)
        await message.reply("✅ Renamed.")
        return


@router.message(F.chat.type == "private", F.from_user.id == OWNER_ID, F.forward_origin)
async def forwarded_state_handler(message: Message) -> None:
    state = _state.get(OWNER_ID)
    if not state:
        return

    fwd_origin = message.forward_origin
    fwd_chat = getattr(fwd_origin, "chat", None)
    if not fwd_chat or fwd_chat.type != "channel":
        await message.reply("❌ Please forward a message from a channel.")
        return

    if state == "awaiting_product_source":
        name = _pending_name.pop(OWNER_ID, "Unnamed")
        await products_db.add_product(name, fwd_chat.id)
        _state.pop(OWNER_ID, None)
        await message.reply(
            f"✅ Product '{name}' saved.\nSource: {fwd_chat.title} ({fwd_chat.id})"
        )
        return

    if state.startswith("awaiting_source_update_"):
        product_id = state.split("_", 3)[3]
        await products_db.update_source(product_id, fwd_chat.id)
        _state.pop(OWNER_ID, None)
        await message.reply(f"✅ Source channel updated to {fwd_chat.title}.")
        return


def register(dp) -> None:
    dp.include_router(router)
