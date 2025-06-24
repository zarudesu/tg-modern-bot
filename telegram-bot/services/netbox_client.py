import httpx
from loguru import logger
from config import settings

class NetBoxClient:
    """Клиент для работы с NetBox API"""
    
    def __init__(self):
        self.base_url = settings.NETBOX_URL
        self.token = settings.NETBOX_TOKEN
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
    
    async def search(self, query: str) -> str:
        """Универсальный поиск в NetBox"""
        
        try:
            async with httpx.AsyncClient() as client:
                results = []
                
                # Поиск устройств
                devices = await self._search_devices(client, query)
                if devices:
                    results.extend(devices)
                
                # Поиск IP адресов
                ips = await self._search_ips(client, query)
                if ips:
                    results.extend(ips)
                
                # Поиск сайтов/площадок
                sites = await self._search_sites(client, query)
                if sites:
                    results.extend(sites)
                
                if results:
                    return "\n".join(results[:5])  # Максимум 5 результатов
                else:
                    return "Ничего не найдено"
                    
        except Exception as e:
            logger.error(f"Ошибка поиска в NetBox: {e}")
            return "Ошибка подключения к NetBox"
    
    async def _search_devices(self, client, query: str) -> list:
        """Поиск устройств"""
        
        if not self.token:
            return ["⚠️ API токен NetBox не настроен"]
        
        try:
            response = await client.get(
                f"{self.base_url}/api/dcim/devices/",
                headers=self.headers,
                params={"q": query, "limit": 3}
            )
            
            if response.status_code == 200:
                devices = response.json()["results"]
                return [f"🖥️ {device['display']} - {device.get('device_type', {}).get('display', 'Unknown')}" 
                       for device in devices]
            else:
                return ["⚠️ Ошибка API NetBox"]
                
        except Exception as e:
            logger.error(f"Ошибка поиска устройств: {e}")
            return []
    
    async def _search_ips(self, client, query: str) -> list:
        """Поиск IP адресов"""
        
        if not self.token:
            return []
        
        try:
            response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                headers=self.headers,
                params={"q": query, "limit": 3}
            )
            
            if response.status_code == 200:
                ips = response.json()["results"]
                return [f"🌐 {ip['display']} - {ip.get('description', 'Без описания')}" 
                       for ip in ips]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Ошибка поиска IP: {e}")
            return []
    
    async def _search_sites(self, client, query: str) -> list:
        """Поиск сайтов/площадок"""
        
        if not self.token:
            return []
        
        try:
            response = await client.get(
                f"{self.base_url}/api/dcim/sites/",
                headers=self.headers,
                params={"q": query, "limit": 3}
            )
            
            if response.status_code == 200:
                sites = response.json()["results"]
                return [f"🏢 {site['display']} - {site.get('description', 'Без описания')}" 
                       for site in sites]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Ошибка поиска сайтов: {e}")
            return []
    
    async def get_ip_info(self, ip: str) -> str:
        """Подробная информация об IP адресе"""
        
        if not self.token:
            return "⚠️ API токен NetBox не настроен"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/ipam/ip-addresses/",
                    headers=self.headers,
                    params={"address": ip}
                )
                
                if response.status_code == 200:
                    ips = response.json()["results"]
                    if ips:
                        ip_data = ips[0]
                        info = f"🌐 **{ip_data['display']}**\n"
                        
                        if ip_data.get('description'):
                            info += f"📝 Описание: {ip_data['description']}\n"
                        
                        if ip_data.get('assigned_object'):
                            obj = ip_data['assigned_object']
                            info += f"📎 Привязан к: {obj.get('display', 'Unknown')}\n"
                        
                        if ip_data.get('vrf'):
                            info += f"🌐 VRF: {ip_data['vrf']['display']}\n"
                        
                        if ip_data.get('tenant'):
                            info += f"🏢 Клиент: {ip_data['tenant']['display']}\n"
                        
                        return info
                    else:
                        return f"❌ IP {ip} не найден в NetBox"
                else:
                    return "⚠️ Ошибка API NetBox"
                    
        except Exception as e:
            logger.error(f"Ошибка получения информации об IP {ip}: {e}")
            return "⚠️ Ошибка подключения к NetBox"
    
    async def get_device_info(self, device_name: str) -> str:
        """Подробная информация об устройстве"""
        
        if not self.token:
            return "⚠️ API токен NetBox не настроен"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/dcim/devices/",
                    headers=self.headers,
                    params={"name": device_name}
                )
                
                if response.status_code == 200:
                    devices = response.json()["results"]
                    if devices:
                        device = devices[0]
                        info = f"🖥️ **{device['display']}**\n"
                        
                        if device.get('device_type'):
                            info += f"⚙️ Тип: {device['device_type']['display']}\n"
                        
                        if device.get('site'):
                            info += f"🏢 Площадка: {device['site']['display']}\n"
                        
                        if device.get('rack'):
                            info += f"🗄️ Стойка: {device['rack']['display']}\n"
                        
                        if device.get('primary_ip4'):
                            info += f"🌐 IP: {device['primary_ip4']['display']}\n"
                        
                        if device.get('status'):
                            info += f"📊 Статус: {device['status']['label']}\n"
                        
                        return info
                    else:
                        return f"❌ Устройство '{device_name}' не найдено"
                else:
                    return "⚠️ Ошибка API NetBox"
                    
        except Exception as e:
            logger.error(f"Ошибка получения информации об устройстве {device_name}: {e}")
            return "⚠️ Ошибка подключения к NetBox"
    
    async def get_client_info(self, client_name: str) -> str:
        """Информация о клиенте/арендаторе"""
        
        if not self.token:
            return "⚠️ API токен NetBox не настроен"
        
        try:
            async with httpx.AsyncClient() as client:
                # Поиск арендатора
                response = await client.get(
                    f"{self.base_url}/api/tenancy/tenants/",
                    headers=self.headers,
                    params={"q": client_name}
                )
                
                if response.status_code == 200:
                    tenants = response.json()["results"]
                    if tenants:
                        tenant = tenants[0]
                        info = f"🏢 **{tenant['display']}**\n"
                        
                        if tenant.get('description'):
                            info += f"📝 Описание: {tenant['description']}\n"
                        
                        # Ищем сайты клиента
                        sites_response = await client.get(
                            f"{self.base_url}/api/dcim/sites/",
                            headers=self.headers,
                            params={"tenant_id": tenant['id']}
                        )
                        
                        if sites_response.status_code == 200:
                            sites = sites_response.json()["results"]
                            if sites:
                                info += f"🏢 Площадки: {', '.join([s['display'] for s in sites[:3]])}\n"
                        
                        return info
                    else:
                        return f"❌ Клиент '{client_name}' не найден"
                else:
                    return "⚠️ Ошибка API NetBox"
                    
        except Exception as e:
            logger.error(f"Ошибка получения информации о клиенте {client_name}: {e}")
            return "⚠️ Ошибка подключения к NetBox"
