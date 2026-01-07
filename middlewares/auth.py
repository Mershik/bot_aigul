from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config.settings import WHITELIST_EMPLOYEES, ADMIN_IDS

class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки whitelist пользователей.
    Подходит для aiogram 3.x
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # В aiogram 3.x 'event' — это сразу Message или CallbackQuery
        # У обоих этих типов есть атрибут from_user
        user = getattr(event, "from_user", None)
        
        if user is None:
            # Если не удалось получить пользователя, пропускаем дальше
            return await handler(event, data)
        
        telegram_id = user.id
        
        # Объединяем whitelist и admin списки (превращаем в числа на случай, если в .env строки)
        allowed_users = {int(uid) for uid in (WHITELIST_EMPLOYEES + ADMIN_IDS)}
        
        # Проверяем доступ
        if telegram_id not in allowed_users:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещен")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещен", show_alert=True)
            return  # Прекращаем выполнение
        
        # Если всё ок, идем к обработчику
        return await handler(event, data)