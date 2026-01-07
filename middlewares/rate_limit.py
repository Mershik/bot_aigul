from typing import Callable, Dict, Any, Awaitable
from time import time
from aiogram import BaseMiddleware
from aiogram.types import Message, Update

from config.settings import RATE_LIMIT_SECONDS


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты сообщений.
    Не позволяет пользователям отправлять сообщения чаще, чем раз в RATE_LIMIT_SECONDS секунд.
    """

    def __init__(self):
        super().__init__()
        # Словарь для хранения времени последнего сообщения каждого пользователя
        self.user_last_message: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем telegram_id пользователя
        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user
        
        if user is None:
            # Если не удалось получить пользователя, пропускаем событие
            return await handler(event, data)
        
        telegram_id = user.id
        current_time = time()
        
        # Проверяем, когда пользователь отправлял последнее сообщение
        if telegram_id in self.user_last_message:
            last_message_time = self.user_last_message[telegram_id]
            time_passed = current_time - last_message_time
            
            # Если прошло меньше времени, чем RATE_LIMIT_SECONDS
            if time_passed < RATE_LIMIT_SECONDS:
                # Игнорируем сообщение молча (не отвечаем)
                return
        
        # Обновляем время последнего сообщения
        self.user_last_message[telegram_id] = current_time
        
        # Продолжаем обработку
        return await handler(event, data)
