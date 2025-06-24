import httpx
from loguru import logger
from config import settings

class BookStackClient:
    """Клиент для работы с BookStack API"""
    
    def __init__(self):
        self.base_url = settings.BOOKSTACK_URL
        self.token = settings.BOOKSTACK_TOKEN
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
    
    async def search(self, query: str) -> str:
        """Универсальный поиск в BookStack"""
        
        try:
            async with httpx.AsyncClient() as client:
                results = []
                
                # Поиск страниц
                pages = await self._search_pages(client, query)
                if pages:
                    results.extend(pages)
                
                # Поиск книг
                books = await self._search_books(client, query)
                if books:
                    results.extend(books)
                
                # Поиск разделов
                chapters = await self._search_chapters(client, query)
                if chapters:
                    results.extend(chapters)
                
                if results:
                    return "\n".join(results[:5])  # Максимум 5 результатов
                else:
                    return "Ничего не найдено"
                    
        except Exception as e:
            logger.error(f"Ошибка поиска в BookStack: {e}")
            return "Ошибка подключения к BookStack"
    
    async def _search_pages(self, client, query: str) -> list:
        """Поиск страниц"""
        
        if not self.token:
            return ["⚠️ API токен BookStack не настроен"]
        
        try:
            response = await client.get(
                f"{self.base_url}/api/search",
                headers=self.headers,
                params={"query": query, "filter[type]": "page"}
            )
            
            if response.status_code == 200:
                search_results = response.json()["data"]
                return [f"📄 {result['name']} - {result.get('preview_content', {}).get('content', '')[:100]}..." 
                       for result in search_results[:3]]
            else:
                return ["⚠️ Ошибка API BookStack"]
                
        except Exception as e:
            logger.error(f"Ошибка поиска страниц: {e}")
            return []
    
    async def _search_books(self, client, query: str) -> list:
        """Поиск книг"""
        
        if not self.token:
            return []
        
        try:
            response = await client.get(
                f"{self.base_url}/api/search",
                headers=self.headers,
                params={"query": query, "filter[type]": "book"}
            )
            
            if response.status_code == 200:
                search_results = response.json()["data"]
                return [f"📚 {result['name']} - {result.get('description', 'Без описания')}" 
                       for result in search_results[:2]]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Ошибка поиска книг: {e}")
            return []
    
    async def _search_chapters(self, client, query: str) -> list:
        """Поиск разделов"""
        
        if not self.token:
            return []
        
        try:
            response = await client.get(
                f"{self.base_url}/api/search",
                headers=self.headers,
                params={"query": query, "filter[type]": "chapter"}
            )
            
            if response.status_code == 200:
                search_results = response.json()["data"]
                return [f"📑 {result['name']} - {result.get('description', 'Без описания')}" 
                       for result in search_results[:2]]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Ошибка поиска разделов: {e}")
            return []
    
    async def search_client(self, client_name: str) -> str:
        """Поиск документации по клиенту"""
        
        if not self.token:
            return "⚠️ API токен BookStack не настроен"
        
        try:
            async with httpx.AsyncClient() as client:
                # Ищем документацию клиента
                response = await client.get(
                    f"{self.base_url}/api/search",
                    headers=self.headers,
                    params={"query": client_name}
                )
                
                if response.status_code == 200:
                    search_results = response.json()["data"]
                    if search_results:
                        results = []
                        for result in search_results[:3]:
                            result_type = "📄" if result['type'] == 'page' else "📚" if result['type'] == 'book' else "📑"
                            results.append(f"{result_type} {result['name']}")
                        
                        return "\n".join(results)
                    else:
                        return f"❌ Документация по клиенту '{client_name}' не найдена"
                else:
                    return "⚠️ Ошибка API BookStack"
                    
        except Exception as e:
            logger.error(f"Ошибка поиска документации клиента {client_name}: {e}")
            return "⚠️ Ошибка подключения к BookStack"
    
    async def get_page_content(self, page_id: int) -> str:
        """Получение содержимого страницы"""
        
        if not self.token:
            return "⚠️ API токен BookStack не настроен"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/pages/{page_id}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    page = response.json()
                    content = page.get('html', '')
                    
                    # Очищаем HTML и обрезаем
                    import re
                    clean_content = re.sub('<[^<]+?>', '', content)
                    return clean_content[:500] + "..." if len(clean_content) > 500 else clean_content
                else:
                    return "⚠️ Страница не найдена"
                    
        except Exception as e:
            logger.error(f"Ошибка получения страницы {page_id}: {e}")
            return "⚠️ Ошибка подключения к BookStack"
