from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
import re
import ipaddress

from services.netbox_client import NetBoxClient
from services.vaultwarden_client import VaultwardenClient  
from services.bookstack_client import BookStackClient

router = Router()

@router.message(Command("search"))
async def search_command(message: Message):
    """Универсальный поиск по всем системам"""
    
    query = message.text.replace("/search", "").strip()
    if not query:
        await message.answer("❌ Укажите поисковый запрос: `/search название`", parse_mode="Markdown")
        return
    
    user_id = message.from_user.id
    logger.info(f"🔍 Пользователь {user_id} ищет: '{query}'")
    
    # Отправляем сообщение о начале поиска
    search_msg = await message.answer("🔍 Ищу во всех системах...")
    
    results = []
    
    # Поиск в NetBox
    try:
        netbox = NetBoxClient()
        netbox_results = await netbox.search(query)
        if netbox_results:
            results.append(f"🌐 **NetBox:**\n{netbox_results}")
    except Exception as e:
        logger.error(f"Ошибка поиска в NetBox: {e}")
        results.append("🌐 **NetBox:** ⚠️ Недоступен")
    
    # Поиск в Vaultwarden
    try:
        vault = VaultwardenClient()
        vault_results = await vault.search(query)
        if vault_results:
            results.append(f"🔐 **Vaultwarden:**\n{vault_results}")
    except Exception as e:
        logger.error(f"Ошибка поиска в Vaultwarden: {e}")
        results.append("🔐 **Vaultwarden:** ⚠️ Недоступен")
    
    # Поиск в BookStack
    try:
        books = BookStackClient()
        books_results = await books.search(query)
        if books_results:
            results.append(f"📚 **BookStack:**\n{books_results}")
    except Exception as e:
        logger.error(f"Ошибка поиска в BookStack: {e}")
        results.append("📚 **BookStack:** ⚠️ Недоступен")
    
    # Формируем ответ
    if results:
        result_text = f"🔍 **Результаты поиска '{query}':**\n\n" + "\n\n".join(results)
    else:
        result_text = f"❌ По запросу '{query}' ничего не найдено"
    
    # Обновляем сообщение с результатами
    await search_msg.edit_text(result_text, parse_mode="Markdown")

@router.message(Command("ip"))
async def ip_command(message: Message):
    """Поиск информации об IP адресе"""
    
    ip_text = message.text.replace("/ip", "").strip()
    if not ip_text:
        await message.answer("❌ Укажите IP адрес: `/ip 192.168.1.1`", parse_mode="Markdown")
        return
    
    # Валидация IP
    try:
        ip = ipaddress.ip_address(ip_text)
        logger.info(f"🌐 Поиск IP {ip} пользователем {message.from_user.id}")
    except ValueError:
        await message.answer("❌ Некорректный IP адрес", parse_mode="Markdown")
        return
    
    search_msg = await message.answer(f"🔍 Ищу информацию об IP {ip}...")
    
    try:
        netbox = NetBoxClient()
        ip_info = await netbox.get_ip_info(str(ip))
        
        if ip_info:
            await search_msg.edit_text(f"🌐 **Информация об IP {ip}:**\n\n{ip_info}", parse_mode="Markdown")
        else:
            await search_msg.edit_text(f"❌ IP {ip} не найден в системе", parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка поиска IP {ip}: {e}")
        await search_msg.edit_text("⚠️ Ошибка при поиске IP адреса", parse_mode="Markdown")

@router.message(Command("device"))
async def device_command(message: Message):
    """Поиск устройства"""
    
    device_name = message.text.replace("/device", "").strip()
    if not device_name:
        await message.answer("❌ Укажите название устройства: `/device router01`", parse_mode="Markdown")
        return
    
    logger.info(f"🖥️ Поиск устройства '{device_name}' пользователем {message.from_user.id}")
    
    search_msg = await message.answer(f"🔍 Ищу устройство '{device_name}'...")
    
    try:
        netbox = NetBoxClient()
        device_info = await netbox.get_device_info(device_name)
        
        if device_info:
            await search_msg.edit_text(f"🖥️ **Устройство '{device_name}':**\n\n{device_info}", parse_mode="Markdown")
        else:
            await search_msg.edit_text(f"❌ Устройство '{device_name}' не найдено", parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка поиска устройства {device_name}: {e}")
        await search_msg.edit_text("⚠️ Ошибка при поиске устройства", parse_mode="Markdown")

@router.message(Command("client"))
async def client_command(message: Message):
    """Поиск информации о клиенте"""
    
    client_name = message.text.replace("/client", "").strip()
    if not client_name:
        await message.answer("❌ Укажите название клиента: `/client ООО Ромашка`", parse_mode="Markdown")
        return
    
    logger.info(f"👥 Поиск клиента '{client_name}' пользователем {message.from_user.id}")
    
    search_msg = await message.answer(f"🔍 Ищу информацию о клиенте '{client_name}'...")
    
    results = []
    
    # Поиск в NetBox (площадки клиента)
    try:
        netbox = NetBoxClient()
        netbox_info = await netbox.get_client_info(client_name)
        if netbox_info:
            results.append(f"🌐 **NetBox (сеть):**\n{netbox_info}")
    except Exception as e:
        logger.error(f"Ошибка поиска клиента в NetBox: {e}")
    
    # Поиск в BookStack (документация)
    try:
        books = BookStackClient()
        docs_info = await books.search_client(client_name)
        if docs_info:
            results.append(f"📚 **Документация:**\n{docs_info}")
    except Exception as e:
        logger.error(f"Ошибка поиска клиента в BookStack: {e}")
    
    if results:
        result_text = f"👥 **Клиент '{client_name}':**\n\n" + "\n\n".join(results)
    else:
        result_text = f"❌ Информация о клиенте '{client_name}' не найдена"
    
    await search_msg.edit_text(result_text, parse_mode="Markdown")

@router.message(Command("password"))
async def password_command(message: Message):
    """Поиск пароля в Vaultwarden"""
    
    service_name = message.text.replace("/password", "").strip()
    if not service_name:
        await message.answer("❌ Укажите название сервиса: `/password router admin`", parse_mode="Markdown")
        return
    
    user_id = message.from_user.id
    logger.info(f"🔐 Поиск пароля '{service_name}' пользователем {user_id}")
    
    search_msg = await message.answer(f"🔍 Ищу пароль для '{service_name}'...")
    
    try:
        vault = VaultwardenClient()
        password_info = await vault.get_password(service_name)
        
        if password_info:
            # Отправляем в приватном чате для безопасности
            await search_msg.edit_text(f"🔐 **Найден пароль для '{service_name}':**\n\n{password_info}", parse_mode="Markdown")
        else:
            await search_msg.edit_text(f"❌ Пароль для '{service_name}' не найден", parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка поиска пароля {service_name}: {e}")
        await search_msg.edit_text("⚠️ Ошибка при поиске пароля", parse_mode="Markdown")

# Обработка обычных текстовых сообщений как поиска
@router.message()
async def text_search(message: Message):
    """Обработка текстовых сообщений как универсального поиска"""
    
    query = message.text.strip()
    if len(query) < 2:
        return
    
    # Если сообщение похоже на IP
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', query):
        # Перенаправляем на обработку IP
        message.text = f"/ip {query}"
        await ip_command(message)
        return
    
    # Иначе делаем универсальный поиск
    message.text = f"/search {query}"
    await search_command(message)
