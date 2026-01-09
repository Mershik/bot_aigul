import json
import logging
import re
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm import LLMService
from database.crud import get_session_messages, create_evaluation
from config.prompts import JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class JudgeService:
    """Сервис для оценки сессий продаж на основе эталонных скриптов."""
    
    def __init__(self):
        """
        Инициализация сервиса оценки.
        """
        self.llm_service = LLMService()
    
    async def evaluate_session(self, db_session: AsyncSession, session_id: int, rag_service=None) -> dict:
        """
        Оценка сессии диалога.
        
        Args:
            db_session: Асинхронная сессия БД
            session_id: ID сессии для оценки
            rag_service: Сервис RAG для поиска эталонных скриптов
            
        Returns:
            dict: Результат оценки
        """
        try:
            # Получаем все сообщения сессии
            msgs = await get_session_messages(db_session, session_id)
            
            if not msgs:
                logger.warning(f"Сессия {session_id} не содержит сообщений")
                return self._get_default_evaluation()
            
            # Поиск эталонных скриптов, если RAG доступен
            scripts_context = ""
            if rag_service:
                # Используем текст сообщений сотрудника (user) для поиска релевантных скриптов
                employee_messages = " ".join([m['content'] for m in msgs if m['role'] == 'user'])
                if employee_messages:
                    relevant_scripts = await rag_service.search(employee_messages, collection_type="scripts", top_k=3)
                    if relevant_scripts:
                        scripts_context = "\n\nЭТАЛОННЫЕ СКРИПТЫ ДЛЯ ПРОВЕРКИ:\n" + "\n---\n".join(relevant_scripts)
            
            # Формируем финальный системный промпт с контекстом
            final_system_prompt = JUDGE_SYSTEM_PROMPT + scripts_context
            
            # Попытки генерации оценки (до 3-х раз)
            max_retries = 3
            evaluation_data = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Попытка оценки #{attempt + 1} для сессии {session_id}")
                    
                    # Формируем диалог в виде текста для анализа, чтобы LLM не продолжала роль клиента
                    dialog_text = "ДИАЛОГ ДЛЯ АНАЛИЗА:\n"
                    for m in msgs:
                        role_name = "Менеджер" if m['role'] == 'user' else "Клиент"
                        dialog_text += f"{role_name}: {m['content']}\n"
                    
                    # Вызываем LLM для оценки, передавая диалог как одно сообщение
                    response = await self.llm_service.generate_response(
                        messages=[{"role": "user", "content": dialog_text}],
                        system_prompt=final_system_prompt
                    )
                    
                    # Парсим JSON ответ
                    res_text = response.strip()
                    
                    # 1. Пытаемся найти JSON через регулярку с DOTALL
                    json_match = re.search(r'(\{.*\})', res_text, re.DOTALL)
                    if json_match:
                        res_text = json_match.group(1)
                    else:
                        # 2. Если регулярка не сработала, ищем вручную по скобкам
                        start_idx = res_text.find('{')
                        end_idx = res_text.rfind('}')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            res_text = res_text[start_idx:end_idx + 1]
                        else:
                            # 3. Очистка от Markdown если ничего не помогло
                            if res_text.startswith("```json"):
                                res_text = res_text[7:]
                            if res_text.endswith("```"):
                                res_text = res_text[:-3]
                            res_text = res_text.strip()
                    
                    # Очистка от управляющих символов, которые могут ломать json.loads
                    res_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', res_text)
                    
                    evaluation_data = json.loads(res_text, strict=False)
                    
                    # Если мы здесь, значит JSON успешно распарсен
                    logger.info(f"JSON успешно распарсен на попытке {attempt + 1}")
                    break
                    
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"Все {max_retries} попыток оценки провалены.")
                        logger.error(f"ПОЛНЫЙ ОТВЕТ LLM (ПОСЛЕДНЯЯ ПОПЫТКА):\n{response}")
                        return self._get_default_evaluation()
                    # Небольшая пауза перед следующей попыткой
                    await asyncio.sleep(1)
            
            # Валидация структуры (после успешного выхода из цикла)
            score = evaluation_data.get("score", 5)
            good_points = evaluation_data.get("good_points", [])
            mistakes = evaluation_data.get("mistakes", [])
            recommendations = evaluation_data.get("recommendations", "Не указано")
            
            # Сохраняем оценку в БД
            await create_evaluation(
                session=db_session,
                session_id=session_id,
                score=score,
                good_points=good_points,
                mistakes=mistakes,
                recommendations=recommendations
            )
            
            result = {
                "session_id": session_id,
                "score": score,
                "good_points": good_points,
                "mistakes": mistakes,
                "recommendations": recommendations
            }
            
            logger.info(f"Сессия {session_id} успешно оценена по скриптам. Оценка: {score}/10")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при оценке сессии {session_id}: {e}", exc_info=True)
            return self._get_default_evaluation()
    
    def _get_default_evaluation(self) -> dict:
        return {
            "session_id": None,
            "score": 5,
            "good_points": "Не удалось выполнить оценку",
            "mistakes": "Не удалось выполнить оценку",
            "recommendations": "Не удалось выполнить оценку"
        }
