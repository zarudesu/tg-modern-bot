"""
Обработчик команд для синхронизации с Google Sheets
"""
import logging
from typing import Dict, Any
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..middleware.auth import admin_required
from ..integrations.google_sheets import sheets_service
from ..utils.keyboards import get_back_to_main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "sheets_sync_menu")
@admin_required
async def callback_sheets_sync_menu(callback: CallbackQuery):
    """Показать меню синхронизации Google Sheets"""
    try:
        await callback.answer()
        
        # Создаем клавиатуру с опциями
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Превью данных", callback_data="sheets_preview")],
            [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sheets_sync_start")],
            [InlineKeyboardButton(text="📋 Статус последней синхронизации", callback_data="sheets_sync_status")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(
            "🔗 <b>Синхронизация с Google Sheets</b>\n\n"
            "📝 Выберите действие для работы с Google Sheets:\n\n"
            "• <b>Превью данных</b> - просмотр последних записей\n"
            "• <b>Синхронизировать</b> - импорт новых записей в БД\n"
            "• <b>Статус</b> - информация о последней синхронизации",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in sheets sync menu: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отображении меню синхронизации",
            reply_markup=get_back_to_main_menu_keyboard()
        )


@router.message(Command("sheets_sync"))
@admin_required
async def cmd_sheets_sync(message: Message, state: FSMContext):
    """Команда синхронизации с Google Sheets"""
    try:
        await state.clear()
        
        # Создаем клавиатуру с опциями
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Превью данных", callback_data="sheets_preview")],
            [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sheets_sync_start")],
            [InlineKeyboardButton(text="📋 Статус последней синхронизации", callback_data="sheets_sync_status")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await message.answer(
            "🔗 <b>Синхронизация с Google Sheets</b>\n\n"
            "📝 Выберите действие для работы с Google Sheets:\n\n"
            "• <b>Превью данных</b> - просмотр последних записей\n"
            "• <b>Синхронизировать</b> - импорт новых записей в БД\n"
            "• <b>Статус</b> - информация о последней синхронизации",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in sheets sync command: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке команды синхронизации",
            reply_markup=get_back_to_main_menu_keyboard()
        )


@router.callback_query(F.data == "sheets_preview")
@admin_required
async def callback_sheets_preview(callback: CallbackQuery):
    """Показать превью данных из Google Sheets"""
    try:
        await callback.answer()
        
        # Показываем индикатор загрузки
        loading_msg = await callback.message.edit_text(
            "⏳ <b>Загружаем данные из Google Sheets...</b>\n\n"
            "Пожалуйста, подождите...",
            parse_mode="HTML"
        )
        
        # Получаем превью данных
        preview_data = await sheets_service.get_sheet_preview(limit=5)
        
        if not preview_data:
            await loading_msg.edit_text(
                "❌ <b>Не удалось получить данные из Google Sheets</b>\n\n"
                "Возможные причины:\n"
                "• Неверные учетные данные\n"
                "• Нет доступа к таблице\n"
                "• Таблица пуста\n"
                "• Проблемы с интернет-соединением",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="sheets_preview")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            return
        
        # Формируем текст с превью
        preview_text = "📊 <b>Превью данных из Google Sheets</b>\n\n"
        preview_text += f"📈 <b>Показано записей:</b> {len(preview_data)}\n\n"
        
        for i, entry in enumerate(preview_data, 1):
            preview_text += f"<b>{i}.</b> "
            
            # Ищем основные поля (адаптируемся к структуре таблицы)
            date_field = entry.get('work_date', entry.get('Дата работ', entry.get('Date', 'N/A')))
            company_field = entry.get('company', entry.get('Компания', entry.get('Company', 'N/A')))
            duration_field = entry.get('work_duration', entry.get('Длительность', entry.get('Duration', 'N/A')))
            
            preview_text += f"{date_field} | {company_field} | {duration_field}\n"
            
            if i >= 5:  # Ограничиваем количество показываемых записей
                break
        
        if len(preview_data) > 5:
            preview_text += f"\n... и еще записей в таблице"
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Синхронизировать эти данные", callback_data="sheets_sync_start")],
            [InlineKeyboardButton(text="🔄 Обновить превью", callback_data="sheets_preview")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await loading_msg.edit_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in sheets preview: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении превью данных",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )


@router.callback_query(F.data == "sheets_sync_start")
@admin_required
async def callback_sheets_sync_start(callback: CallbackQuery):
    """Запуск синхронизации с Google Sheets"""
    try:
        await callback.answer()
        
        # Показываем индикатор загрузки
        loading_msg = await callback.message.edit_text(
            "🔄 <b>Синхронизация с Google Sheets запущена...</b>\n\n"
            "⏳ Обрабатываем данные, пожалуйста подождите...\n"
            "Это может занять несколько минут в зависимости от объема данных.",
            parse_mode="HTML"
        )
        
        # Запускаем синхронизацию
        start_time = datetime.now()
        sync_stats = await sheets_service.sync_from_sheets()
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Формируем отчет о синхронизации
        if sync_stats['error_entries'] == sync_stats['total_processed'] and sync_stats['total_processed'] > 0:
            # Все записи с ошибками
            result_text = (
                "❌ <b>Синхронизация завершена с ошибками</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Обработано записей: {sync_stats['total_processed']}\n"
                f"• Ошибок: {sync_stats['error_entries']}\n"
                f"• Время выполнения: {duration:.1f} сек\n\n"
                "❗ <b>Возможные причины:</b>\n"
                "• Неверный формат данных в таблице\n"
                "• Отсутствуют обязательные поля\n"
                "• Проблемы с доступом к таблице"
            )
        elif sync_stats['new_entries'] == 0:
            # Нет новых записей
            result_text = (
                "✅ <b>Синхронизация завершена</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Обработано записей: {sync_stats['total_processed']}\n"
                f"• Новых записей: {sync_stats['new_entries']}\n"
                f"• Пропущено (уже существуют): {sync_stats['skipped_entries']}\n"
                f"• Ошибок: {sync_stats['error_entries']}\n"
                f"• Время выполнения: {duration:.1f} сек\n\n"
                "ℹ️ Все записи из таблицы уже существуют в базе данных"
            )
        else:
            # Успешная синхронизация с новыми записями
            result_text = (
                "✅ <b>Синхронизация успешно завершена</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Обработано записей: {sync_stats['total_processed']}\n"
                f"• Добавлено новых: {sync_stats['new_entries']}\n"
                f"• Пропущено (уже существуют): {sync_stats['skipped_entries']}\n"
                f"• Ошибок: {sync_stats['error_entries']}\n"
                f"• Время выполнения: {duration:.1f} сек\n\n"
                f"🎉 В базу данных добавлено <b>{sync_stats['new_entries']}</b> новых записей!"
            )
        
        # Создаем клавиатуру с действиями
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Посмотреть превью", callback_data="sheets_preview")],
            [InlineKeyboardButton(text="🔄 Синхронизировать снова", callback_data="sheets_sync_start")],
            [InlineKeyboardButton(text="📖 История записей", callback_data="history_menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await loading_msg.edit_text(
            result_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in sheets sync: {e}")
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка при синхронизации</b>\n\n"
            f"Техническая информация: {str(e)[:100]}...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="sheets_sync_start")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "sheets_sync_status")
@admin_required
async def callback_sheets_sync_status(callback: CallbackQuery):
    """Показать статус синхронизации с Google Sheets"""
    try:
        await callback.answer()
        
        status_text = (
            "📋 <b>Статус синхронизации Google Sheets</b>\n\n"
            "🔗 <b>Параметры подключения:</b>\n"
            f"• Сервисный аккаунт: n8n-sheets-integration@hhivp-plane.iam.gserviceaccount.com\n"
            f"• ID таблицы: {sheets_service.parser.spreadsheet_id or 'не настроен'}\n\n"
            "ℹ️ <b>Возможности:</b>\n"
            "• Автоматический импорт записей журнала работ\n"
            "• Предотвращение дублирования данных\n"
            "• Поддержка различных форматов дат\n"
            "• Парсинг множественных исполнителей"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Превью данных", callback_data="sheets_preview")],
            [InlineKeyboardButton(text="🔄 Запустить синхронизацию", callback_data="sheets_sync_start")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(
            status_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in sheets sync status: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении статуса синхронизации",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
