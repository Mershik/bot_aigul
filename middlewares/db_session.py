from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для передачи session_factory и сервисов в handlers.
    В aiogram 3.x данные из dp автоматически доступны в data,
    поэтому этот middleware просто пропускает событие дальше.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # В aiogram 3.x все данные из dp уже автоматически доступны в data
        # Просто вызываем handler
        return await handler(event, data)
