"""
Admin commands for managing Plane↔Telegram mappings

Commands:
- /list_members - List all telegram member mappings
- /add_member - Add new member mapping (interactive)
- /list_companies - List all company mappings
- /add_company - Add new company mapping (interactive)
- /sync_plane - Sync members/projects from Plane API
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..config import settings
from ..database.database import get_async_session
from ..services.plane_mappings_service import PlaneMappingsService
from ..utils.logger import bot_logger


router = Router(name="admin_mappings")


# ═══════════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════════

class AddMemberStates(StatesGroup):
    waiting_lookup_key = State()
    waiting_telegram_id = State()
    waiting_display_name = State()
    waiting_short_name = State()
    waiting_group_handle = State()


class AddCompanyStates(StatesGroup):
    waiting_plane_name = State()
    waiting_display_name_ru = State()


# ═══════════════════════════════════════════════════════════
# LIST MEMBERS
# ═══════════════════════════════════════════════════════════

@router.message(Command("list_members"))
async def cmd_list_members(message: Message):
    """List all telegram member mappings"""
    if not settings.is_admin(message.from_user.id):
        await message.reply("⛔ Только для администраторов")
        return

    try:
        async for session in get_async_session():
            service = PlaneMappingsService(session)
            mappings = await service.list_telegram_mappings()

            if not mappings:
                await message.reply("📭 Нет сохранённых маппингов участников")
                return

            # Group by telegram_id
            grouped = {}
            for m in mappings:
                if m.telegram_id not in grouped:
                    grouped[m.telegram_id] = {
                        "display_name": m.display_name,
                        "short_name": m.short_name,
                        "group_handle": m.group_handle,
                        "username": m.telegram_username,
                        "lookup_keys": []
                    }
                grouped[m.telegram_id]["lookup_keys"].append(m.lookup_key)

            # Format output
            lines = ["<b>👥 Участники команды</b>\n"]
            for tg_id, info in grouped.items():
                name = info["display_name"] or info["short_name"] or "—"
                short = info["short_name"] or "—"
                handle = info["group_handle"] or "—"
                username = f"@{info['username']}" if info["username"] else "—"
                keys = ", ".join(info["lookup_keys"][:3])
                if len(info["lookup_keys"]) > 3:
                    keys += f" +{len(info['lookup_keys']) - 3}"

                lines.append(
                    f"<b>{name}</b>\n"
                    f"  ID: <code>{tg_id}</code>\n"
                    f"  Короткое: {short} | Handle: {handle}\n"
                    f"  TG: {username}\n"
                    f"  Ключи: {keys}\n"
                )

            await message.reply("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        bot_logger.error(f"Error listing members: {e}")
        await message.reply(f"❌ Ошибка: {e}")


# ═══════════════════════════════════════════════════════════
# LIST COMPANIES
# ═══════════════════════════════════════════════════════════

@router.message(Command("list_companies"))
async def cmd_list_companies(message: Message):
    """List all company mappings"""
    if not settings.is_admin(message.from_user.id):
        await message.reply("⛔ Только для администраторов")
        return

    try:
        async for session in get_async_session():
            service = PlaneMappingsService(session)
            mappings = await service.list_company_mappings()

            if not mappings:
                await message.reply("📭 Нет сохранённых маппингов компаний")
                return

            # Format output
            lines = ["<b>🏢 Компании</b>\n"]
            for m in mappings:
                lines.append(
                    f"• <b>{m.display_name_ru}</b>\n"
                    f"  Plane: <code>{m.plane_project_name}</code>\n"
                )

            # Split into chunks if too long
            text = "\n".join(lines)
            if len(text) > 4000:
                # Send first part
                await message.reply(text[:4000] + "\n\n[продолжение...]", parse_mode="HTML")
                await message.reply(text[4000:], parse_mode="HTML")
            else:
                await message.reply(text, parse_mode="HTML")

    except Exception as e:
        bot_logger.error(f"Error listing companies: {e}")
        await message.reply(f"❌ Ошибка: {e}")


# ═══════════════════════════════════════════════════════════
# ADD MEMBER (Interactive)
# ═══════════════════════════════════════════════════════════

@router.message(Command("add_member"))
async def cmd_add_member(message: Message, state: FSMContext):
    """Start adding new member mapping"""
    if not settings.is_admin(message.from_user.id):
        await message.reply("⛔ Только для администраторов")
        return

    await state.set_state(AddMemberStates.waiting_lookup_key)
    await message.reply(
        "<b>➕ Добавление участника</b>\n\n"
        "Шаг 1/5: Введите <b>lookup_key</b>\n"
        "(имя в Plane, email или вариант написания)\n\n"
        "Пример: <code>Иван Петров</code> или <code>ivan@company.com</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddMemberStates.waiting_lookup_key, F.text)
async def process_lookup_key(message: Message, state: FSMContext):
    """Process lookup_key input"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    await state.update_data(lookup_key=message.text.strip())
    await state.set_state(AddMemberStates.waiting_telegram_id)
    await message.reply(
        "Шаг 2/5: Введите <b>Telegram ID</b>\n"
        "(числовой ID пользователя)\n\n"
        "Пример: <code>123456789</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddMemberStates.waiting_telegram_id, F.text)
async def process_telegram_id(message: Message, state: FSMContext):
    """Process telegram_id input"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите числовой ID. Попробуйте ещё раз:")
        return

    await state.update_data(telegram_id=telegram_id)
    await state.set_state(AddMemberStates.waiting_display_name)
    await message.reply(
        "Шаг 3/5: Введите <b>полное имя</b>\n"
        "(для отображения в отчётах)\n\n"
        "Пример: <code>Иван Петров</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddMemberStates.waiting_display_name, F.text)
async def process_display_name(message: Message, state: FSMContext):
    """Process display_name input"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    await state.update_data(display_name=message.text.strip())
    await state.set_state(AddMemberStates.waiting_short_name)
    await message.reply(
        "Шаг 4/5: Введите <b>короткое имя</b>\n"
        "(для UI, например в списке исполнителей)\n\n"
        "Пример: <code>Ваня</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddMemberStates.waiting_short_name, F.text)
async def process_short_name(message: Message, state: FSMContext):
    """Process short_name input"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    await state.update_data(short_name=message.text.strip())
    await state.set_state(AddMemberStates.waiting_group_handle)
    await message.reply(
        "Шаг 5/5: Введите <b>@handle для группы</b>\n"
        "(для упоминаний в групповых сообщениях)\n\n"
        "Пример: <code>@ivan_petrov</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddMemberStates.waiting_group_handle, F.text)
async def process_group_handle(message: Message, state: FSMContext):
    """Process group_handle and save member"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    data = await state.get_data()
    group_handle = message.text.strip()
    if not group_handle.startswith("@"):
        group_handle = f"@{group_handle}"

    try:
        async for session in get_async_session():
            service = PlaneMappingsService(session)
            await service.add_telegram_mapping(
                lookup_key=data["lookup_key"],
                telegram_id=data["telegram_id"],
                display_name=data["display_name"],
                short_name=data["short_name"],
                group_handle=group_handle,
                created_by=f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
            )

        await state.clear()
        await message.reply(
            f"✅ <b>Участник добавлен!</b>\n\n"
            f"Ключ: <code>{data['lookup_key']}</code>\n"
            f"Telegram ID: <code>{data['telegram_id']}</code>\n"
            f"Имя: {data['display_name']}\n"
            f"Короткое: {data['short_name']}\n"
            f"Handle: {group_handle}",
            parse_mode="HTML"
        )

    except Exception as e:
        await state.clear()
        bot_logger.error(f"Error adding member: {e}")
        await message.reply(f"❌ Ошибка при добавлении: {e}")


# ═══════════════════════════════════════════════════════════
# ADD COMPANY (Interactive)
# ═══════════════════════════════════════════════════════════

@router.message(Command("add_company"))
async def cmd_add_company(message: Message, state: FSMContext):
    """Start adding new company mapping"""
    if not settings.is_admin(message.from_user.id):
        await message.reply("⛔ Только для администраторов")
        return

    await state.set_state(AddCompanyStates.waiting_plane_name)
    await message.reply(
        "<b>➕ Добавление компании</b>\n\n"
        "Шаг 1/2: Введите <b>название проекта в Plane</b>\n\n"
        "Пример: <code>NewClient</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddCompanyStates.waiting_plane_name, F.text)
async def process_plane_name(message: Message, state: FSMContext):
    """Process plane_name input"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    await state.update_data(plane_name=message.text.strip())
    await state.set_state(AddCompanyStates.waiting_display_name_ru)
    await message.reply(
        "Шаг 2/2: Введите <b>русское название</b>\n"
        "(для отображения в отчётах)\n\n"
        "Пример: <code>Новый Клиент</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(AddCompanyStates.waiting_display_name_ru, F.text)
async def process_display_name_ru(message: Message, state: FSMContext):
    """Process display_name_ru and save company"""
    if message.text.startswith("/"):
        await state.clear()
        await message.reply("❌ Отменено")
        return

    data = await state.get_data()
    display_name_ru = message.text.strip()

    try:
        async for session in get_async_session():
            service = PlaneMappingsService(session)
            await service.add_company_mapping(
                plane_project_name=data["plane_name"],
                display_name_ru=display_name_ru
            )

        await state.clear()
        await message.reply(
            f"✅ <b>Компания добавлена!</b>\n\n"
            f"Plane: <code>{data['plane_name']}</code>\n"
            f"Название: {display_name_ru}",
            parse_mode="HTML"
        )

    except Exception as e:
        await state.clear()
        bot_logger.error(f"Error adding company: {e}")
        await message.reply(f"❌ Ошибка при добавлении: {e}")


# ═══════════════════════════════════════════════════════════
# CANCEL COMMAND
# ═══════════════════════════════════════════════════════════

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.reply("❌ Операция отменена")
    else:
        await message.reply("Нечего отменять")
