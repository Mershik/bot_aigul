import json
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm import LLMService
from database.crud import get_session_messages, create_evaluation
from config.prompts import JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class JudgeService:
    """Сервис для оценки сессий психологического консультирования."""
    
    def __init__(self):
        """
        Инициализация сервиса оценки.
        """
        self.llm_service = LLMService()
    
    async def evaluate_session(self, db_session: AsyncSession, session_id: int) -> dict:
        """
        Оценка сессии консультирования.
        
        Args:
            db_session: Асинхронная сессия БД
            session_id: ID сессии для оценки
            
        Returns:
            dict: Результат оценки с полями score, good_points, mistakes, recommendations
        """
        try:
            # Получаем все сообщения сессии
            msgs = await get_session_messages(db_session, session_id)
            
            if not msgs:
                logger.warning(f"Сессия {session_id} не содержит сообщений")
                return self._get_default_evaluation()
            
            # Сообщения уже в формате для LLM
            messages = msgs
            
            # Вызываем LLM для оценки с системным промптом судьи
            response = await self.llm_service.generate_response(
                messages=messages,
                system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            # Парсим JSON ответ
            try:
                # Очистка текста от Markdown блоков и лишних пробелов
                res_text = response.strip()
                
                # Пытаемся найти JSON с помощью регулярного выражения, если он обернут в текст
                json_match = re.search(r'(\{.*\})', res_text, re.DOTALL)
                if json_match:
                    res_text = json_match.group(1)
                else:
                    # Если регулярка не сработала, пробуем старый метод очистки
                    if res_text.startswith("```json"):
                        res_text = res_text[7:]
                    if res_text.endswith("```"):
                        res_text = res_text[:-3]
                    res_text = res_text.strip()
                
                try:
                    evaluation_data = json.loads(res_text)
                except json.JSONDecodeError:
                    logger.error(f"Не удалось распарсить JSON даже после очистки. Ответ: {response}")
                    return self._get_default_evaluation()
                
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
                session=db_session,
                session_id=session_id,
                score=score,
                good_points=good_points,
                mistakes=mistakes,
                recommendations=recommendations
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
