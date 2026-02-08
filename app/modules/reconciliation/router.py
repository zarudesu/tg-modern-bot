"""
/plane_reconcile — daily chat reconciliation UI.
"""

import json
from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ...config import settings
from ...utils.logger import bot_logger
from .reconciliation_service import (
    ReconciliationService,
    serialize_item,
    deserialize_item,
)
from .states import ReconciliationStates
from .keyboards import build_summary_keyboard, build_item_keyboard, build_journal_keyboard

router = Router(name="reconciliation")

ACTION_LABELS = {
    "close_existing": "Закрыть",
    "create_done": "Создать → Done",
    "create_started": "Создать → Started",
}

ACTION_EMOJI = {
    "close_existing": "🔒",
    "create_done": "✅",
    "create_started": "⚡",
}


def _format_summary(items: list[dict]) -> str:
    """Format reconciliation summary as HTML."""
    today = date.today().isoformat()
    lines = [f"<b>📋 Сверка чатов — {today}</b>\n"]

    # Group by project
    by_project = {}
    for i, item in enumerate(items):
        pname = item["plane_project_name"]
        by_project.setdefault(pname, []).append((i, item))

    for pname, group in by_project.items():
        company = group[0][1].get("work_journal_company", pname)
        lines.append(f"\n<b>{pname}</b> ({company}):")
        for idx, item in group:
            inc = item["incident"]
            action = item["proposed_action"]
            emoji = ACTION_EMOJI.get(action, "❓")
            label = ACTION_LABELS.get(action, action)
            resolved = "✓" if inc["is_resolved"] else "⚡"
            seq = ""
            if item.get("matching_plane_task"):
                seq = f" #{item['matching_plane_task'].get('sequence_id', '?')}"
            lines.append(f" {idx+1}. {emoji}{seq} {inc['title'][:50]} → <i>{label}</i>")

    lines.append(f"\nВсего: <b>{len(items)}</b> действий")
    return "\n".join(lines)


def _format_item_detail(idx: int, item: dict, total: int) -> str:
    """Format single item for review."""
    inc = item["incident"]
    action = item["proposed_action"]
    label = ACTION_LABELS.get(action, action)

    lines = [
        f"<b>[{idx+1}/{total}] {inc['title']}</b>",
        f"Действие: <i>{label}</i>",
        f"Проект: {item['plane_project_name']}",
    ]
    if inc.get("description"):
        lines.append(f"\n{inc['description'][:200]}")
    if inc.get("resolution_summary"):
        lines.append(f"\nРешение: {inc['resolution_summary'][:150]}")
    if item.get("matching_plane_task"):
        t = item["matching_plane_task"]
        lines.append(f"\nСовпадение: #{t.get('sequence_id', '?')} {t.get('name', '')[:40]}")
    if inc.get("estimated_duration"):
        lines.append(f"Время: ~{inc['estimated_duration']}")
    return "\n".join(lines)


# ---- Command ----

@router.message(Command("plane_reconcile"))
async def cmd_reconcile(message: Message, state: FSMContext):
    """Manual trigger for daily chat reconciliation."""
    if not settings.is_admin(message.from_user.id):
        await message.answer("Только для админов.")
        return

    status_msg = await message.answer("⏳ Анализирую привязанные чаты...")

    try:
        service = ReconciliationService()
        items = await service.run()
    except Exception as e:
        bot_logger.error(f"Reconciliation run error: {e}", exc_info=True)
        await status_msg.edit_text(f"✗ Ошибка: {str(e)[:100]}")
        return

    if not items:
        await status_msg.edit_text(
            "📋 Сверка завершена — сегодня инцидентов в привязанных чатах не найдено."
        )
        return

    serialized = [serialize_item(i) for i in items]
    await state.update_data(recon_items=serialized, current_idx=0, approved=[])
    await state.set_state(ReconciliationStates.reviewing)

    summary = _format_summary(serialized)
    kb = build_summary_keyboard()

    if len(summary) > 4000:
        summary = summary[:3950] + "\n\n<i>...обрезано</i>"
    await status_msg.edit_text(summary, parse_mode="HTML", reply_markup=kb)


# ---- Approve All ----

@router.callback_query(F.data == "recon:approve_all")
async def on_approve_all(callback: CallbackQuery, state: FSMContext):
    """Execute all proposed actions."""
    data = await state.get_data()
    items = data.get("recon_items", [])

    if not items:
        await callback.message.edit_text("Нет действий для выполнения.")
        await state.clear()
        await callback.answer()
        return

    await callback.message.edit_text("⏳ Выполняю...")
    await callback.answer()

    service = ReconciliationService()
    results = []
    journal_candidates = []

    for item_data in items:
        item = deserialize_item(item_data)
        ok, msg = await service.execute_action(item)
        results.append(f"{'✓' if ok else '✗'} {msg}")
        if ok and item.incident.is_resolved:
            journal_candidates.append(item_data)

    text = "<b>Результаты:</b>\n" + "\n".join(results)

    if journal_candidates:
        await state.update_data(journal_items=journal_candidates)
        await state.set_state(ReconciliationStates.journal_prompt)
        text += "\n\n<b>Создать записи в журнал работ?</b>"
        kb = build_journal_keyboard()
    else:
        await state.clear()
        kb = None

    if len(text) > 4000:
        text = text[:3950] + "\n<i>...обрезано</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ---- Review One by One ----

@router.callback_query(F.data == "recon:review")
async def on_review(callback: CallbackQuery, state: FSMContext):
    """Start reviewing items one by one."""
    data = await state.get_data()
    items = data.get("recon_items", [])
    if not items:
        await callback.message.edit_text("Нет действий.")
        await state.clear()
        await callback.answer()
        return

    await state.update_data(current_idx=0, approved=[])
    await state.set_state(ReconciliationStates.item_review)
    await _show_item(callback.message, items, 0)
    await callback.answer()


async def _show_item(msg, items: list, idx: int):
    """Show a single item for review."""
    if idx >= len(items):
        return
    text = _format_item_detail(idx, items[idx], len(items))
    kb = build_item_keyboard(idx, len(items))
    await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("recon:item_ok:"))
async def on_item_ok(callback: CallbackQuery, state: FSMContext):
    """Approve single item."""
    idx = int(callback.data.split(":")[-1])
    data = await state.get_data()
    approved = data.get("approved", [])
    approved.append(idx)
    await state.update_data(approved=approved)

    items = data.get("recon_items", [])
    next_idx = idx + 1

    if next_idx >= len(items):
        await _execute_approved(callback, state)
    else:
        await state.update_data(current_idx=next_idx)
        await _show_item(callback.message, items, next_idx)

    await callback.answer()


@router.callback_query(F.data.startswith("recon:item_skip:"))
async def on_item_skip(callback: CallbackQuery, state: FSMContext):
    """Skip single item."""
    idx = int(callback.data.split(":")[-1])
    data = await state.get_data()
    items = data.get("recon_items", [])
    next_idx = idx + 1

    if next_idx >= len(items):
        await _execute_approved(callback, state)
    else:
        await state.update_data(current_idx=next_idx)
        await _show_item(callback.message, items, next_idx)

    await callback.answer()


@router.callback_query(F.data.startswith("recon:item_next:"))
async def on_item_next(callback: CallbackQuery, state: FSMContext):
    """Navigate to next item."""
    idx = int(callback.data.split(":")[-1])
    data = await state.get_data()
    items = data.get("recon_items", [])
    await state.update_data(current_idx=idx)
    await _show_item(callback.message, items, idx)
    await callback.answer()


async def _execute_approved(callback: CallbackQuery, state: FSMContext):
    """Execute only approved items after one-by-one review."""
    data = await state.get_data()
    items = data.get("recon_items", [])
    approved_indices = set(data.get("approved", []))

    if not approved_indices:
        await callback.message.edit_text("Ничего не подтверждено.")
        await state.clear()
        return

    await callback.message.edit_text("⏳ Выполняю...")

    service = ReconciliationService()
    results = []
    journal_candidates = []

    for idx in sorted(approved_indices):
        if idx < len(items):
            item = deserialize_item(items[idx])
            ok, msg = await service.execute_action(item)
            results.append(f"{'✓' if ok else '✗'} {msg}")
            if ok and item.incident.is_resolved:
                journal_candidates.append(items[idx])

    text = "<b>Результаты:</b>\n" + "\n".join(results)

    if journal_candidates:
        await state.update_data(journal_items=journal_candidates)
        await state.set_state(ReconciliationStates.journal_prompt)
        text += "\n\n<b>Создать записи в журнал работ?</b>"
        kb = build_journal_keyboard()
    else:
        await state.clear()
        kb = None

    if len(text) > 4000:
        text = text[:3950] + "\n<i>...обрезано</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ---- Cancel ----

@router.callback_query(F.data == "recon:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel reconciliation."""
    await state.clear()
    await callback.message.edit_text("Сверка отменена.")
    await callback.answer()


# ---- Journal ----

@router.callback_query(F.data == "recon:journal")
async def on_create_journal(callback: CallbackQuery, state: FSMContext):
    """Create work journal entries for resolved incidents."""
    data = await state.get_data()
    journal_items = data.get("journal_items", [])

    if not journal_items:
        await callback.message.edit_text("Нет записей для журнала.")
        await state.clear()
        await callback.answer()
        return

    await callback.message.edit_text("⏳ Создаю записи в журнал...")
    await callback.answer()

    from ...services.work_journal_service import WorkJournalService
    from ...database.database import AsyncSessionLocal

    results = []
    today = date.today()
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        service = WorkJournalService(session)

        for item_data in journal_items:
            item = deserialize_item(item_data)
            try:
                entry = await service.create_entry_quick(
                    telegram_user_id=user_id,
                    work_date=today,
                    company=item.work_journal_company or item.plane_project_name,
                    work_description=item.incident.title,
                    work_duration=item.incident.estimated_duration or "30 мин",
                )
                results.append(f"✓ {item.incident.title[:40]}")
            except Exception as e:
                results.append(f"✗ {item.incident.title[:30]}: {str(e)[:30]}")
                bot_logger.error(f"Journal quick create error: {e}")

    text = "<b>Журнал работ:</b>\n" + "\n".join(results)
    await state.clear()
    await callback.message.edit_text(text, parse_mode="HTML")


@router.callback_query(F.data == "recon:no_journal")
async def on_skip_journal(callback: CallbackQuery, state: FSMContext):
    """Skip journal creation."""
    await state.clear()
    # Just remove the keyboard, keep the results text
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("OK")
