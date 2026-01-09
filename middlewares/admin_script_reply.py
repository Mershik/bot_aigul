import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from config.settings import ADMIN_IDS, ENABLE_SCRIPT_REPLY
from handlers.admin_script_reply import get_script_reply_keyboard

logger = logging.getLogger(__name__)

class AdminScriptReplyMiddleware(BaseMiddleware):
    """
    Middleware для добавления кнопки 'Ответить по скрипту' к сообщениям пользователей,
    которые пересылаются или отображаются в админ-панели.
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Если функционал выключен, просто пропускаем
        if not ENABLE_SCRIPT_REPLY:
            return await handler(event, data)

        # Проверяем, является ли пользователь админом
        user_id = event.from_user.id
        if user_id not in ADMIN_IDS:
            return await handler(event, data)

        # Логика: если админ получает сообщение от пользователя (например, в режиме мониторинга)
        # или если это текстовое сообщение в админ-чате, которое не является командой.
        # В данном проекте сообщения пользователей обрабатываются в handlers/chat.py.
        # Чтобы админ мог нажать кнопку под сообщением пользователя, нам нужно, 
        # чтобы это сообщение было доступно админу.
        
        # Однако, согласно ТЗ, кнопка должна быть "под входящими сообщениями пользователей".
        # В текущей архитектуре входящие сообщения идут в `handle_message`.
        # Мы можем модифицировать `handle_message`, чтобы он дублировал сообщение админу с кнопкой,
        # ИЛИ мы можем добавить кнопку к ответу бота, чтобы админ видел, как бот ответил и мог предложить свой вариант.
        
        # Но ТЗ просит "под входящими сообщениями пользователей". 
        # Обычно это подразумевает, что админ видит эти сообщения.
        
        return await handler(event, data)
