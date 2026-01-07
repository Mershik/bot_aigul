import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm import LLMService
from database.crud import get_session_messages, create_evaluation
from config.prompts import JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class JudgeService:
    """Сервис для оценки сессий психологического консультирования."""
    
    def __init__(self, llm_service: LLMService):
        """
        Инициализация сервиса оценки.
        
        Args:
            llm_service: Сервис для работы с LLM
        """
        self.llm_service = llm_service
    
    async def evaluate_session(self, session_id: int, db_session: AsyncSession) -> dict:
        """
        Оценка сессии консультирования.
        
        Args:
            session_id: ID сессии для оценки
            db_session: Асинхронная сессия БД
            
        Returns:
            dict: Результат оценки с полями score, good_points, mistakes, recommendations
        """
        try:
            # Получаем все сообщения сессии
            msgs = await get_session_messages(session_id, db_session)
            
            if not msgs:
                logger.warning(f"Сессия {session_id} не содержит сообщений")
                return self._get_default_evaluation()
            
            # Формируем историю диалога для LLM
            messages = [{"role": msg.role, "content": msg.content} for msg in msgs]
            
            # Вызываем LLM для оценки с системным промптом судьи
            response = await self.llm_service.generate_response(
                messages=messages,
                system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            # Парсим JSON ответ
            try:
                evaluation_data = json.loads(response)
                
                # Валидация структуры ответа
                score = evaluation_data.get("score", 5)
                good_points = evaluation_data.get("good_points", "Не указано")
                mistakes = evaluation_data.get("mistakes", "Не указано")
                recommendations = evaluation_data.get("recommendations", "Не указано")
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON ответа от LLM: {e}")
                logger.debug(f"Ответ LLM: {response}")
                return self._get_default_evaluation()
            
            # Сохраняем оценку в БД
            evaluation = await create_evaluation(
                session_id=session_id,
                score=score,
                good_points=good_points,
                mistakes=mistakes,
                recommendations=recommendations,
                db=db_session
            )
            
            # Возвращаем результат
            result = {
                "session_id": session_id,
                "score": score,
                "good_points": good_points,
                "mistakes": mistakes,
                "recommendations": recommendations
            }
            
            logger.info(f"Сессия {session_id} успешно оценена. Оценка: {score}/10")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при оценке сессии {session_id}: {e}", exc_info=True)
            return self._get_default_evaluation()
    
    def _get_default_evaluation(self) -> dict:
        """
        Возвращает дефолтные значения оценки при ошибке.
        
        Returns:
            dict: Дефолтная оценка
        """
        return {
            "session_id": None,
            "score": 5,
            "good_points": "Не удалось выполнить оценку",
            "mistakes": "Не удалось выполнить оценку",
            "recommendations": "Не удалось выполнить оценку"
        }
