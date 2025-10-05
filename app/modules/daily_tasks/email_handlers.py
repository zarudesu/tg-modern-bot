"""
Обработчики email для ежедневных задач

КРИТИЧЕСКИ ВАЖНО: Обработчики работают только с email от админов
Используют фильтр IsAdminEmailFilter для изоляции от других модулей
"""

from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from .filters import IsAdminEmailFilter
from ...database.database import get_async_session
from ...database.models import UserSession
from ...services.daily_tasks_service import daily_tasks_service
from ...utils.logger import bot_logger
from ...config import settings


router = Router()


def escape_markdown_v2(text: str) -> str:
    """Правильное экранирование для MarkdownV2"""
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!', '@']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text


@router.message(IsAdminEmailFilter())
async def handle_admin_email_input(message: Message):
    """
    ЕДИНСТВЕННЫЙ обработчик email для админов daily_tasks
    
    Работает ТОЛЬКО с email от админов (ID в settings.admin_user_id_list)
    Этот фильтр обеспечивает изоляцию от других модулей
    """
    try:
        admin_id = message.from_user.id
        email = message.text.strip().lower()
        
        bot_logger.info(f"🎯 ADMIN EMAIL HANDLER TRIGGERED: {email} from admin {admin_id}")
        
        # КРИТИЧЕСКИЙ ФИКС: Проверяем что сервис инициализирован
        # Импортируем заново чтобы получить актуальную ссылку
        from ...services.daily_tasks_service import daily_tasks_service as dts_service
        
        if dts_service is None:
            bot_logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: daily_tasks_service = None для admin {admin_id}")
            await message.reply(
                "❌ *Критическая ошибка системы*\n\n"
                "Сервис ежедневных задач не инициализирован\\. "
                "Обратитесь к разработчику\\.",
                parse_mode="MarkdownV2"
            )
            return
            
        bot_logger.info(f"✅ Daily tasks service найден: {type(dts_service)}")
        # Используем локальную переменную вместо глобальной
        daily_tasks_service_local = dts_service
        
        async for session in get_async_session():
            # Сохраняем email в настройках сервиса
            if admin_id not in daily_tasks_service_local.admin_settings:
                daily_tasks_service_local.admin_settings[admin_id] = {}
                bot_logger.info(f"📝 Создаем новые настройки для admin {admin_id}")
            
            daily_tasks_service_local.admin_settings[admin_id]['plane_email'] = email
            bot_logger.info(f"📧 Устанавливаем email {email} для admin {admin_id}")
            
            # Попробуем сохранить в БД
            save_result = await daily_tasks_service_local._save_admin_settings_to_db()
            
            bot_logger.info(f"✅ Email {email} saved for admin {admin_id}, result: {save_result}")
            
            # 🚀 Запускаем background парсинг задач
            if save_result:
                from ...services.user_tasks_cache_service import user_tasks_cache_service
                sync_started = await user_tasks_cache_service.start_user_sync(
                    user_email=email,
                    telegram_user_id=admin_id,
                    notify_user=True
                )
                if sync_started:
                    bot_logger.info(f"🔄 Background sync started for {email}")
                else:
                    bot_logger.warning(f"⚠️ Background sync not started for {email} (already in progress?)")
        
            # Обновляем пользовательскую сессию
            result = await session.execute(
                select(UserSession).where(UserSession.telegram_user_id == admin_id)
            )
            user_session = result.scalar_one_or_none()
            
            if user_session:
                # Очищаем контекст после успешного сохранения
                user_session.last_command = None
                user_session.context = {}
                await session.commit()
            
            # Экранируем текст для MarkdownV2
            email_escaped = escape_markdown_v2(email)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_to_settings")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            
            await message.reply(
                f"✅ *Email сохранен успешно*\n\n"
                f"📧 *Email:* {email_escaped}\n"
                f"👤 *Админ ID:* {admin_id}\n\n"
                f"Теперь вы будете получать ежедневные задачи на этот email\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"❌ Error saving admin email {email} for admin {admin_id}: {e}")
        await message.reply(
            "❌ *Ошибка сохранения email*\n\n"
            "Попробуйте еще раз или обратитесь к разработчику\\.",
            parse_mode="MarkdownV2"  
        )


# DEBUG обработчик удален - использует только IsAdminEmailFilter для изоляции