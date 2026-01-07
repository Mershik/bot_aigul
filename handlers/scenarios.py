from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import create_session
from services.llm import LLMService
from config.prompts import SCENARIOS


class DialogStates(StatesGroup):
    """FSM состояния для диалога с ИИ"""
    in_dialog = State()


async def handle_scenario_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """
    Обработчик выбора сценария из inline-кнопок.
    
    Args:
        callback: Callback query от кнопки сценария
        state: FSM контекст для управления состоянием
        session: Async сессия БД
    """
    # Парсим callback.data (например, "scenario_expensive" → "expensive")
    scenario_key = callback.data.replace("scenario_", "")
    
    # Проверяем, что сценарий существует
    if scenario_key not in SCENARIOS:
        await callback.answer("Неизвестный сценарий", show_alert=True)
        return
    
    # Создаем новую Session в БД
    db_session = await create_session(
        session=session,
        user_id=callback.from_user.id,
        scenario=scenario_key
    )
    
    # Загружаем system_prompt из SCENARIOS
    system_prompt = SCENARIOS[scenario_key]
    
    # Вызываем LLMService.generate_response с пустым messages=[]
    llm_service = LLMService()
    ai_response = await llm_service.generate_response(
        system_prompt=system_prompt,
        messages=[]
    )
    
    # Отправляем ответ пользователю
    await callback.message.answer(ai_response)
    
    # Устанавливаем FSM state = "in_dialog"
    await state.set_state(DialogStates.in_dialog)
    
    # Сохраняем session_id в FSM state data
    await state.update_data(session_id=db_session.id)
    
    # Подтверждаем callback
    await callback.answer()
