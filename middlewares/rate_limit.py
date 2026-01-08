from typing import Callable, Dict, Any, Awaitable
from time import time
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

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
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # В aiogram 3.x event — это сам Message или CallbackQuery.
        # У обоих есть .from_user
        user = getattr(event, "from_user", None)

        if not user:
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
