from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, Update

from config.settings import WHITELIST_EMPLOYEES, ADMIN_IDS


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки whitelist пользователей.
    Разрешает доступ только пользователям из WHITELIST_EMPLOYEES и ADMIN_IDS.
    """

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
        
        # Объединяем whitelist и admin списки
        allowed_users = set(WHITELIST_EMPLOYEES + ADMIN_IDS)
        
        # Проверяем, есть ли пользователь в whitelist
        if telegram_id not in allowed_users:
            # Отправляем сообщение об отказе в доступе
            if event.message:
                await event.message.answer("⛔ Доступ запрещен")
            elif event.callback_query:
                await event.callback_query.answer("⛔ Доступ запрещен", show_alert=True)
            
            # Прекращаем обработку
            return
        
        # Пользователь в whitelist, продолжаем обработку
        return await handler(event, data)
