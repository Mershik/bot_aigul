from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from database.crud import create_session, get_user_by_telegram_id
from database.models import User
from config.prompts import SCENARIOS


class DialogStates(StatesGroup):
    """FSM состояния для диалога с ИИ"""
    in_dialog = State()


async def handle_scenario_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    session_factory,
    llm_service
) -> None:
    """
    Обработчик выбора сценария из inline-кнопок.
    
    Args:
        callback: Callback query от кнопки сценария
        state: FSM контекст для управления состоянием
        session_factory: Фабрика для создания сессий БД
        llm_service: Сервис для генерации ответов LLM
    """
    async with session_factory() as session:
        # Парсим callback.data (например, "scenario_expensive" → "expensive")
        scenario_key = callback.data.replace("scenario_", "")
        
        # Проверяем, что сценарий существует
        if scenario_key not in SCENARIOS:
            await callback.answer("Неизвестный сценарий", show_alert=True)
            return
        
        # Получаем пользователя из БД по telegram_id
        user_obj = await get_user_by_telegram_id(session, callback.from_user.id)
        
        if not user_obj:
            await callback.answer("❌ Пользователь не найден. Используйте /start", show_alert=True)
            return
        
        # Создаем новую Session в БД с внутренним id пользователя
        db_session = await create_session(
            session=session,
            user_id=user_obj.id,  # Используем внутренний id из БД
            scenario=scenario_key
        )
        
        # Загружаем system_prompt из SCENARIOS
        system_prompt = SCENARIOS[scenario_key]["system_prompt"]
        
        # Вызываем LLMService.generate_response с пустым messages=[]
        ai_response = await llm_service.generate_response(
            system_prompt=system_prompt,
            messages=[]
        )
        
        # Отправляем ответ пользователю
        await callback.message.answer(ai_response)
        
        # Устанавливаем FSM state = "in_dialog"
        await state.set_state(DialogStates.in_dialog)
        
        # Сохраняем session_id и system_prompt в FSM state data
        await state.update_data(
            session_id=db_session.id,
            system_prompt=system_prompt
        )
        
        # Подтверждаем callback
        await callback.answer()
