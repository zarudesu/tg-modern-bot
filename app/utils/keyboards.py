"""
Общие клавиатуры для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Google Sheets", callback_data="sheets_sync_menu")],
        [InlineKeyboardButton(text="📋 Daily Tasks", callback_data="daily_tasks_menu")],
        [InlineKeyboardButton(text="📝 Work Journal", callback_data="work_journal_menu")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
        ]
    ])
