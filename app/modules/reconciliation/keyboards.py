from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✓ Всё подтвердить", callback_data="recon:approve_all"),
            InlineKeyboardButton(text="По одному", callback_data="recon:review"),
        ],
        [
            InlineKeyboardButton(text="✗ Отмена", callback_data="recon:cancel"),
        ],
    ])


def build_item_keyboard(idx: int, total: int) -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="✓ OK", callback_data=f"recon:item_ok:{idx}"),
        InlineKeyboardButton(text="Пропустить", callback_data=f"recon:item_skip:{idx}"),
    ]]
    if idx < total - 1:
        buttons.append([
            InlineKeyboardButton(text="Далее →", callback_data=f"recon:item_next:{idx + 1}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_journal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Создать записи", callback_data="recon:journal"),
        InlineKeyboardButton(text="Пропустить", callback_data="recon:no_journal"),
    ]])
