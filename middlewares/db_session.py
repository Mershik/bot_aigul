from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для передачи session_factory в handlers.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем session_factory из dispatcher data
        session_factory = data.get("session_factory")
        
        if session_factory:
            # Передаем session_factory в data для handlers
            data["session_factory"] = session_factory
        
        # Вызываем handler
        return await handler(event, data)
