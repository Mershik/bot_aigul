"""
Обработчик сообщений в диалоге с пользователем
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import add_message, get_session_messages, update_session
from config.settings import MAX_MESSAGE_LENGTH

logger = logging.getLogger(__name__)

# Ключевые фразы для завершения диалога
FINISH_PHRASES = [
    "договорились",
    "оформляйте",
    "до свидания",
    "не интересно"
]


async def handle_message(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка сообщений пользователя в активном диалоге
    
    Args:
        message: Входящее сообщение от пользователя
        state: Контекст состояния FSM
        session: Сессия базы данных
    """
    try:
        # Получаем текущее состояние
        current_state = await state.get_state()
        
        # Проверяем, что пользователь находится в диалоге
        if current_state != "in_dialog":
            logger.debug(f"Сообщение проигнорировано: пользователь {message.from_user.id} не в диалоге")
            return
        
        # Проверяем длину сообщения
        if not message.text or len(message.text) > MAX_MESSAGE_LENGTH:
            await message.answer(
                f"⚠️ Сообщение слишком длинное. Максимальная длина: {MAX_MESSAGE_LENGTH} символов."
            )
            logger.warning(f"Сообщение от пользователя {message.from_user.id} превышает максимальную длину")
            return
        
        # Получаем session_id из состояния
        state_data = await state.get_data()
        session_id = state_data.get("session_id")
        
        if not session_id:
            await message.answer("❌ Ошибка: сессия не найдена. Начните диалог заново с /start")
            logger.error(f"Session_id не найден для пользователя {message.from_user.id}")
            await state.clear()
            return
        
        logger.info(f"Обработка сообщения от пользователя {message.from_user.id}, session_id={session_id}")
        
        # Получаем сервисы из bot data
        bot_data = message.bot
        rag_service = bot_data.get("rag_service")
        llm_service = bot_data.get("llm_service")
        
        # Сохраняем сообщение пользователя в БД
        await add_message(
            session=session,
            session_id=session_id,
            role="user",
            content=message.text
        )
        
        # Получаем последние 10 сообщений из истории
        messages = await get_session_messages(session, session_id, limit=10)
        
        # Выполняем RAG поиск по базе знаний
        rag_results = await rag_service.search(message.text, top_k=3)
        
        # Формируем контекст из результатов RAG
        context = "\n".join(rag_results) if rag_results else ""
        
        # Получаем системный промпт из данных состояния
        system_prompt = state_data.get("system_prompt", "")
        
        # Генерируем ответ от LLM
        response = await llm_service.generate_response(
            messages=messages,
            system_prompt=system_prompt,
            context=context
        )
        
        # Сохраняем ответ ассистента в БД
        await add_message(
            session=session,
            session_id=session_id,
            role="assistant",
            content=response
        )
        
        # Отправляем ответ пользователю
        await message.answer(response)
        
        logger.info(f"Ответ отправлен пользователю {message.from_user.id}")
        
        # Проверяем ключевые фразы для завершения диалога
        response_lower = response.lower()
        if any(phrase in response_lower for phrase in FINISH_PHRASES):
            logger.info(f"Обнаружена ключевая фраза завершения в ответе для session_id={session_id}")
            await finish_session(message, state, session, session_id)
    
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения от пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке вашего сообщения. Попробуйте еще раз или начните диалог заново с /start"
        )


async def finish_session(message: types.Message, state: FSMContext, session: AsyncSession, session_id: int):
    """
    Завершение сессии диалога
    
    Args:
        message: Сообщение пользователя
        state: Контекст состояния FSM
        session: Сессия базы данных
        session_id: ID сессии для завершения
    """
    try:
        # Обновляем статус сессии в БД
        await update_session(session, session_id, status="completed")
        
        # Очищаем состояние FSM
        await state.clear()
        
        logger.info(f"Сессия {session_id} завершена для пользователя {message.from_user.id}")
        
        # Отправляем прощальное сообщение
        await message.answer(
            "✅ Диалог завершен. Спасибо за обращение!\n"
            "Для начала нового диалога используйте /start"
        )
    
    except Exception as e:
        logger.error(f"Ошибка при завершении сессии {session_id}: {e}", exc_info=True)
