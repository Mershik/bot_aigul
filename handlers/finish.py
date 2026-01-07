from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import update_session
from config.settings import ADMIN_IDS
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def handle_finish(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    bot
):
    """
    Обработчик завершения диалога с клиентом.
    Оценивает сессию, отправляет результаты админу и записывает в Google Sheets.
    """
    try:
        # Получаем данные из state
        state_data = await state.get_data()
        session_id = state_data.get("session_id")
        
        if not session_id:
            await message.answer("❌ У вас нет активного диалога")
            return
        
        # Обновляем статус сессии
        updated_session = await update_session(
            session,
            session_id,
            status="completed",
            finished_at=datetime.utcnow()
        )
        
        if not updated_session:
            await message.answer("❌ Ошибка при завершении диалога")
            return
        
        # Получаем сервисы из bot data
        judge_service = message.bot.get("judge_service")
        sheets_service = message.bot.get("sheets_service")
        
        # Оцениваем сессию через JudgeService
        evaluation = await judge_service.evaluate_session(session, session_id)
        
        # Отправляем сообщение сотруднику
        await message.answer("✅ Диалог завершен! Результаты отправлены руководителю.")
        
        # Формируем сообщение для админа
        username = message.from_user.username or message.from_user.full_name
        date = updated_session.finished_at.strftime("%d.%m.%Y %H:%M")
        scenario_name = updated_session.scenario.name if updated_session.scenario else "Неизвестно"
        
        # Вычисляем длительность
        duration = updated_session.finished_at - updated_session.started_at
        minutes = int(duration.total_seconds() / 60)
        
        # Подсчитываем количество сообщений
        message_count = len(updated_session.messages)
        
        # Формируем списки достижений и ошибок
        strengths_text = ""
        if evaluation.get("strengths"):
            for strength in evaluation["strengths"][:2]:  # Берем первые 2
                strengths_text += f"• {strength}\n"
        else:
            strengths_text = "• Нет данных\n"
        
        mistakes_text = ""
        if evaluation.get("mistakes"):
            for mistake in evaluation["mistakes"][:3]:  # Берем первые 3
                mistakes_text += f"• {mistake}\n"
        else:
            mistakes_text = "• Ошибок не обнаружено\n"
        
        recommendations = evaluation.get("recommendations", "Нет рекомендаций")
        score = evaluation.get("score", 0)
        
        admin_message = f"""📊 **Новый результат тренировки**

👤 Сотрудник: @{username}
📅 Дата: {date}
🎯 Сценарий: {scenario_name}
⏱ Длительность: {minutes} мин
💬 Сообщений: {message_count}

⭐ Оценка: {score}/10

✅ Что хорошо:
{strengths_text}
⚠️ Ошибки:
{mistakes_text}
💡 Рекомендации:
{recommendations}
"""
        
        # Отправляем админам
        for admin_id in ADMIN_IDS:
            try:
                # Создаем кнопку для просмотра полного диалога
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📝 Посмотреть полный диалог",
                        callback_data=f"view_session_{session_id}"
                    )]
                ])
                
                await bot.send_message(
                    admin_id,
                    admin_message,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения админу {admin_id}: {e}")
        
        # Записываем в Google Sheets
        try:
            await sheets_service.write_session_result(
                session_id=session_id,
                username=username,
                date=date,
                scenario=scenario_name,
                duration_minutes=minutes,
                message_count=message_count,
                score=score,
                strengths=evaluation.get("strengths", []),
                mistakes=evaluation.get("mistakes", []),
                recommendations=recommendations
            )
        except Exception as e:
            logger.error(f"Ошибка при записи в Google Sheets: {e}")
        
        # Очищаем state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в handle_finish: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при завершении диалога")
