import aiohttp
import logging
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, DAILY_COST_LIMIT


logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для работы с OpenRouter API"""
    
    def __init__(self):
        """Инициализация сервиса с параметрами из конфигурации"""
        self.api_key = OPENROUTER_API_KEY
        self.base_url = OPENROUTER_BASE_URL
        self.model = OPENROUTER_MODEL
        self.daily_cost_limit = DAILY_COST_LIMIT
        self.total_cost = 0.0
        
    async def generate_response(self, messages: list, system_prompt: str, context: str = "") -> str:
        """
        Генерирует ответ от LLM через OpenRouter API
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            system_prompt: Системный промпт для модели
            context: Дополнительный контекст (опционально)
            
        Returns:
            str: Сгенерированный ответ от модели
        """
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Формируем системное сообщение с контекстом
        system_content = system_prompt
        if context:
            system_content += f"\n\nКонтекст:\n{context}"
        
        # Формируем полный список сообщений
        full_messages = [{"role": "system", "content": system_content}] + messages
        
        body = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, headers=headers, json=body) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        raise Exception(f"OpenRouter API вернул ошибку: {response.status}")
                    
                    data = await response.json()
                    
                    if "choices" not in data or len(data["choices"]) == 0:
                        logger.error(f"Некорректный ответ от API: {data}")
                        raise Exception("Некорректный ответ от OpenRouter API")
                    
                    content = data["choices"][0]["message"]["content"]
                    
                    # Подсчитываем токены и стоимость
                    if "usage" in data:
                        total_tokens = data["usage"].get("total_tokens", 0)
                    else:
                        # Примерная оценка если нет данных об использовании
                        total_tokens = self.count_tokens(system_content + str(messages) + content)
                    
                    await self.track_cost(total_tokens)
                    
                    logger.info(f"Успешно получен ответ от LLM, токенов: {total_tokens}")
                    return content
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка соединения с OpenRouter API: {e}")
            raise Exception(f"Ошибка соединения с API: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """
        Примерная оценка количества токенов в тексте
        
        Args:
            text: Текст для подсчета
            
        Returns:
            int: Примерное количество токенов
        """
        return len(text) // 4
    
    async def track_cost(self, tokens: int):
        """
        Отслеживает стоимость использования API
        
        Args:
            tokens: Количество использованных токенов
            
        Raises:
            Exception: Если превышен дневной лимит стоимости
        """
        # Примерная цена за токен (в долларах)
        cost_per_token = 0.00001
        cost = tokens * cost_per_token
        
        self.total_cost += cost
        
        logger.info(f"Использовано токенов: {tokens}, стоимость: ${cost:.6f}, всего: ${self.total_cost:.6f}")
        
        if self.total_cost > self.daily_cost_limit:
            logger.warning(f"Превышен дневной лимит стоимости: ${self.total_cost:.6f} > ${self.daily_cost_limit}")
            raise Exception(f"Превышен дневной лимит стоимости API: ${self.daily_cost_limit}")
