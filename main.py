import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config.settings import BOT_TOKEN, DATABASE_URL
from database import init_db
from services.rag import RAGService
from services.llm import LLMService
from services.judge import JudgeService
from services.sheets import SheetsService
from middlewares.auth import AuthMiddleware
from middlewares.rate_limit import RateLimitMiddleware
import handlers.start
import handlers.scenarios
import handlers.chat
import handlers.finish


# Настройка логирования
def setup_logging():
    """Настройка логирования в файл и консоль"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "bot.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


async def main():
    """Главная функция запуска бота"""
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск бота...")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Создание async engine для PostgreSQL
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db(engine)
        
        # Инициализация сервисов
        logger.info("Инициализация сервисов...")
        
        # RAG Service - загрузка базы знаний
        rag_service = RAGService()
        knowledge_base_path = Path("knowledge_base")
        if knowledge_base_path.exists():
            await rag_service.load_knowledge_base(str(knowledge_base_path))
            logger.info("База знаний загружена")
        else:
            logger.warning(f"Директория {knowledge_base_path} не найдена")
        
        # Остальные сервисы
        llm_service = LLMService()
        judge_service = JudgeService()
        sheets_service = SheetsService()
        
        # Сохранение сервисов и сессии в bot data для доступа из handlers
        dp["db_session"] = async_session
        dp["rag_service"] = rag_service
        dp["llm_service"] = llm_service
        dp["judge_service"] = judge_service
        dp["sheets_service"] = sheets_service
        dp["engine"] = engine
        
        # Подключение middlewares
        logger.info("Подключение middlewares...")
        dp.message.middleware(AuthMiddleware(async_session))
        dp.callback_query.middleware(AuthMiddleware(async_session))
        dp.message.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())
        
        # Регистрация handlers
        logger.info("Регистрация обработчиков...")
        
        # /start команда
        dp.message.register(handlers.start.handle_start, commands=["start"])
        
        # callback для сценариев
        dp.callback_query.register(
            handlers.scenarios.handle_scenario_callback,
            lambda c: c.data and c.data.startswith("scenario_")
        )
        
        # /finish команда
        dp.message.register(handlers.finish.handle_finish, commands=["finish"])
        
        # Обработчик всех текстовых сообщений (должен быть последним)
        dp.message.register(handlers.chat.handle_message)
        
        logger.info("Бот успешно запущен и готов к работе")
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        raise
    finally:
        # Graceful shutdown
        logger.info("Остановка бота...")
        await bot.session.close()
        await engine.dispose()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
