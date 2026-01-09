from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config.settings import WHITELIST_EMPLOYEES, ADMIN_IDS
from database.crud import get_user_by_telegram_id

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
        
        # 1. Проверяем по спискам из .env
        allowed_in_config = {int(uid) for uid in (WHITELIST_EMPLOYEES + ADMIN_IDS)}
        if telegram_id in allowed_in_config:
            return await handler(event, data)
            
        # 2. Проверяем по базе данных (если пользователь был добавлен админом)
        session_factory = data.get("session_factory")
        if session_factory:
            async with session_factory() as session:
                db_user = await get_user_by_telegram_id(session, telegram_id)
                if db_user:
                    # Если пользователь есть в базе, значит он прошел регистрацию или был добавлен
                    return await handler(event, data)
        
        # Если нигде не найден
        if isinstance(event, Message):
            await event.answer("⛔ Доступ запрещен. Обратитесь к администратору.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Доступ запрещен", show_alert=True)
        return  # Прекращаем выполнение
        
        # Если всё ок, идем к обработчику
        return await handler(event, data)