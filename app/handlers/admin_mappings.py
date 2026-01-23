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
from ..integrations.plane import plane_api
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


# ═══════════════════════════════════════════════════════════
# SYNC FROM PLANE API
# ═══════════════════════════════════════════════════════════

@router.message(Command("sync_plane"))
async def cmd_sync_plane(message: Message):
    """
    Sync members and projects from Plane API

    Discovers new workspace members and projects,
    adds any missing mappings to database.
    """
    if not settings.is_admin(message.from_user.id):
        await message.reply("⛔ Только для администраторов")
        return

    status_msg = await message.reply("🔄 <b>Синхронизация с Plane API...</b>", parse_mode="HTML")

    try:
        import aiohttp

        new_members = 0
        new_companies = 0
        existing_members = 0
        existing_companies = 0

        async with aiohttp.ClientSession() as http_session:
            # 1. Sync workspace members
            await status_msg.edit_text("🔄 Загрузка участников из Plane...")

            try:
                members = await plane_api.users.get_workspace_members(http_session)
                bot_logger.info(f"📥 Got {len(members)} members from Plane API")

                async for db_session in get_async_session():
                    service = PlaneMappingsService(db_session)
                    existing_mappings = await service.list_telegram_mappings()
                    existing_lookup_keys = {m.lookup_key.lower() for m in existing_mappings}

                    for member in members:
                        display_name = member.display_name or f"{member.first_name} {member.last_name}".strip()

                        # Check if email already mapped
                        if member.email.lower() not in existing_lookup_keys:
                            # Check if display_name already mapped
                            if display_name.lower() not in existing_lookup_keys:
                                bot_logger.info(
                                    f"📝 New Plane member found: {display_name} ({member.email}) "
                                    f"- needs Telegram ID mapping"
                                )
                                new_members += 1
                            else:
                                existing_members += 1
                        else:
                            existing_members += 1

            except Exception as e:
                bot_logger.error(f"Error syncing members: {e}")
                await status_msg.edit_text(f"⚠️ Ошибка загрузки участников: {e}")

            # 2. Sync projects
            await status_msg.edit_text("🔄 Загрузка проектов из Plane...")

            try:
                projects = await plane_api.projects.get_projects(http_session)
                bot_logger.info(f"📥 Got {len(projects)} projects from Plane API")

                async for db_session in get_async_session():
                    service = PlaneMappingsService(db_session)
                    existing_companies = await service.list_company_mappings()
                    existing_project_names = {c.plane_project_name.lower() for c in existing_companies}

                    for project in projects:
                        project_name = project.name
                        project_identifier = project.identifier or project_name

                        # Check if project already mapped
                        if project_name.lower() not in existing_project_names:
                            if project_identifier.lower() not in existing_project_names:
                                # Add new company mapping
                                try:
                                    await service.add_company_mapping(
                                        plane_project_name=project_name,
                                        display_name_ru=project_name,  # Use original name as default
                                        display_name_en=project_name,
                                        plane_project_id=project.id
                                    )
                                    bot_logger.info(f"✅ Added company mapping: {project_name}")
                                    new_companies += 1
                                except Exception as e:
                                    bot_logger.warning(f"⚠️ Failed to add company {project_name}: {e}")
                            else:
                                existing_companies += 1
                        else:
                            existing_companies += 1

            except Exception as e:
                bot_logger.error(f"Error syncing projects: {e}")
                await status_msg.edit_text(f"⚠️ Ошибка загрузки проектов: {e}")

        # Final report
        report = (
            f"<b>✅ Синхронизация завершена</b>\n\n"
            f"<b>Участники:</b>\n"
            f"  Новых: {new_members}\n"
            f"  Уже в базе: {existing_members}\n\n"
            f"<b>Компании/Проекты:</b>\n"
            f"  Новых: {new_companies}\n"
            f"  Уже в базе: {existing_companies}\n\n"
        )

        if new_members > 0:
            report += (
                f"⚠️ <b>Внимание:</b> Найдены новые участники без Telegram ID.\n"
                f"Используйте /add_member чтобы добавить их Telegram ID.\n"
            )

        await status_msg.edit_text(report, parse_mode="HTML")

    except Exception as e:
        bot_logger.error(f"Error in sync_plane: {e}")
        await status_msg.edit_text(f"❌ Ошибка синхронизации: {e}")
