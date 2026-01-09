"""
Обработчик сообщений в диалоге с пользователем
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from database.crud import add_message, get_session_messages, update_session, get_session_with_relations
from config.settings import MAX_MESSAGE_LENGTH
from handlers.scenarios import DialogStates
from handlers.admin_script_reply import get_script_reply_keyboard
from config.settings import ADMIN_IDS, ENABLE_SCRIPT_REPLY

logger = logging.getLogger(__name__)

# Ключевые фразы для завершения диалога
FINISH_PHRASES = [
    "договорились",
    "оформляйте",
    "до свидания",
    "не интересно"
]


async def handle_message(
    message: types.Message,
    state: FSMContext,
    session_factory,
    rag_service,
    llm_service,
    judge_service,
    sheets_service
) -> None:
    """
    Обработка сообщений пользователя в активном диалоге
    
    Args:
        message: Входящее сообщение от пользователя
        state: Контекст состояния FSM
        session_factory: Фабрика для создания сессий БД
        rag_service: Сервис для поиска в базе знаний
        llm_service: Сервис для генерации ответов LLM
        judge_service: Сервис для оценки сессий
        sheets_service: Сервис для записи в Google Sheets
    """
    async with session_factory() as session:
        try:
            # Получаем текущее состояние
            current_state = await state.get_state()
            
            # Проверяем, что пользователь находится в диалоге
            if current_state != DialogStates.in_dialog.state:
                logger.debug(f"Сообщение проигнорировано: пользователь {message.from_user.id} не в диалоге (текущее состояние: {current_state})")
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
            
            # Сохраняем сообщение пользователя в БД
            await add_message(
                session=session,
                session_id=session_id,
                role="user",
                content=message.text
            )
            
            # Получаем последние 20 сообщений из истории для поддержания контекста
            messages = await get_session_messages(session, session_id, limit=20)
            
            # Выполняем RAG поиск по базе знаний (только в коллекции для клиента)
            rag_results = await rag_service.search(message.text, collection_type="client", top_k=3)
            
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
            
            # Если включен функционал ответов по скрипту, дублируем сообщение админам с кнопкой
            if ENABLE_SCRIPT_REPLY:
                reply_markup = get_script_reply_keyboard()
                for admin_id in ADMIN_IDS:
                    try:
                        await message.bot.send_message(
                            chat_id=admin_id,
                            text=f"👤 **Пользователь {message.from_user.full_name} (ID: {message.from_user.id}) пишет:**\n\n{message.text}",
                            reply_markup=reply_markup,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

            logger.info(f"Ответ отправлен пользователю {message.from_user.id}")
            
            # Проверяем ключевые фразы для завершения диалога
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in FINISH_PHRASES):
                logger.info(f"Обнаружена ключевая фраза завершения в ответе для session_id={session_id}")
                await finish_session(
                    message,
                    state,
                    session_factory,
                    session_id,
                    rag_service,
                    judge_service,
                    sheets_service
                )
        
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения от пользователя {message.from_user.id}: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке вашего сообщения. Попробуйте еще раз или начните диалог заново с /start"
            )


async def finish_session(
    message: types.Message,
    state: FSMContext,
    session_factory,
    session_id: int,
    rag_service,
    judge_service,
    sheets_service
):
    """
    Завершение сессии диалога
    
    Args:
        message: Сообщение пользователя
        state: Контекст состояния FSM
        session_factory: Фабрика для создания сессий БД
        session_id: ID сессии для завершения
        judge_service: Сервис для оценки сессий
        sheets_service: Сервис для записи в Google Sheets
    """
    async with session_factory() as session:
        try:
            from datetime import datetime
            
            # Сначала получаем сессию, чтобы проверить статус
            db_session_obj = await get_session_with_relations(session, session_id)
            
            if not db_session_obj:
                logger.error(f"Сессия {session_id} не найдена")
                return
                
            if db_session_obj.status == "completed":
                logger.warning(f"Сессия {session_id} уже завершена. Пропускаем повторное завершение.")
                await state.clear()
                return

            # Обновляем статус сессии в БД
            now = datetime.utcnow()
            await update_session(
                session,
                session_id,
                status="completed",
                finished_at=now
            )
            
            # После коммита в update_session объект может стать expired.
            # Получаем свежий объект с подгруженными связями для дальнейшей работы.
            updated_session = await get_session_with_relations(session, session_id)
            
            if not updated_session:
                logger.error(f"Не удалось получить сессию {session_id} после обновления")
                return
            
            # Принудительно обновляем объект, чтобы Python увидел записанные данные
            await session.refresh(updated_session)

            logger.info(f"Сессия {session_id} успешно обновлена в БД (status=completed)")

            # Оцениваем сессию и отправляем в Google Sheets в отдельном try-except с rollback
            try:
                # Оцениваем сессию через JudgeService (с использованием RAG для скриптов)
                logger.info(f"Запуск оценки сессии {session_id}...")
                evaluation = await judge_service.evaluate_session(session, session_id, rag_service=rag_service)
                logger.info(f"Оценка сессии {session_id} завершена: score={evaluation.get('score')}")

                # Подготовка данных для Google Sheets
                username = message.from_user.username or message.from_user.full_name
                
                # Защита от NoneType для finished_at
                finish_time = updated_session.finished_at or now
                date = finish_time.strftime("%d.%m.%Y %H:%M")
                
                scenario_name = updated_session.scenario.name if updated_session.scenario else "Неизвестно"
                duration = finish_time - updated_session.started_at
                minutes = int(duration.total_seconds() / 60)
                message_count = len(updated_session.messages)

                # Записываем в Google Sheets
                logger.info(f"Отправка результатов сессии {session_id} в Google Sheets...")
                await sheets_service.write_session_result(
                    session_id=session_id,
                    username=username,
                    date=date,
                    scenario=scenario_name,
                    duration_minutes=minutes,
                    message_count=message_count,
                    score=evaluation.get("score", 0),
                    strengths=evaluation.get("good_points", []),
                    mistakes=evaluation.get("mistakes", []),
                    recommendations=evaluation.get("recommendations", "Нет рекомендаций")
                )
                logger.info(f"Результаты сессии {session_id} успешно отправлены в Google Sheets")

                # Дополнительно записываем полный лог диалога на второй лист
                # Сортируем сообщения по времени создания для корректного порядка
                sorted_messages = sorted(updated_session.messages, key=lambda msg: msg.timestamp)
                
                dialog_full_text = ""
                for m in sorted_messages:
                    # Корректное присвоение ролей
                    role_name = "Менеджер" if m.role == "user" else "Клиент"
                    
                    # Форматирование времени
                    message_time = m.timestamp.strftime("%H:%M:%S")
                    
                    dialog_full_text += f"[{message_time}] {role_name}: {m.content}\n\n"
                
                await sheets_service.write_dialog_log(
                    session_id=session_id,
                    username=username,
                    dialog_text=dialog_full_text
                )

            except Exception as db_e:
                logger.error(f"Ошибка при оценке или записи в Sheets для сессии {session_id}: {db_e}")
                await session.rollback()
                # Продолжаем, чтобы хотя бы очистить состояние и отправить сообщение
            
            # Очищаем состояние FSM
            await state.clear()
            
            logger.info(f"Сессия {session_id} завершена для пользователя {message.from_user.id}")
            
            # Отправляем прощальное сообщение
            await message.answer(
                "✅ Диалог завершен. Результаты тренировки сохранены.\n"
                "Для начала нового диалога используйте /start"
            )
        
        except Exception as e:
            logger.error(f"Критическая ошибка при завершении сессии {session_id}: {e}", exc_info=True)
            await session.rollback()
