import json
import logging
import re
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
                # Используем текст сообщений сотрудника (assistant) для поиска релевантных скриптов
                employee_messages = " ".join([m['content'] for m in msgs if m['role'] == 'assistant'])
                if employee_messages:
                    relevant_scripts = await rag_service.search(employee_messages, collection_type="scripts", top_k=3)
                    if relevant_scripts:
                        scripts_context = "\n\nЭТАЛОННЫЕ СКРИПТЫ ДЛЯ ПРОВЕРКИ:\n" + "\n---\n".join(relevant_scripts)
            
            # Формируем финальный системный промпт с контекстом
            final_system_prompt = JUDGE_SYSTEM_PROMPT + scripts_context
            
            # Вызываем LLM для оценки
            response = await self.llm_service.generate_response(
                messages=msgs,
                system_prompt=final_system_prompt
            )
            
            # Парсим JSON ответ
            try:
                res_text = response.strip()
                json_match = re.search(r'(\{.*\})', res_text, re.DOTALL)
                if json_match:
                    res_text = json_match.group(1)
                else:
                    if res_text.startswith("```json"):
                        res_text = res_text[7:]
                    if res_text.endswith("```"):
                        res_text = res_text[:-3]
                    res_text = res_text.strip()
                
                # Очистка от управляющих символов, которые могут ломать json.loads
                # Оставляем только стандартные пробельные символы (пробел, таб, перевод строки)
                res_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', res_text)
                
                evaluation_data = json.loads(res_text)
                
                # Валидация структуры
                score = evaluation_data.get("score", 5)
                good_points = evaluation_data.get("good_points", [])
                mistakes = evaluation_data.get("mistakes", [])
                recommendations = evaluation_data.get("recommendations", "Не указано")
                
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Ошибка парсинга JSON ответа от LLM: {e}")
                return self._get_default_evaluation()
            
            # Сохраняем оценку в БД
            await create_evaluation(
                session=db_session,
                session_id=session_id,
                score=score,
                good_points=json.dumps(good_points, ensure_ascii=False) if isinstance(good_points, list) else str(good_points),
                mistakes=json.dumps(mistakes, ensure_ascii=False) if isinstance(mistakes, list) else str(mistakes),
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
