import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import BOT_TOKEN, DATABASE_URL
from database import init_db
from services.rag import RAGService
from services.llm import LLMService
from services.judge import JudgeService
from services.sheets import SheetsService
from middlewares.auth import AuthMiddleware
from middlewares.rate_limit import RateLimitMiddleware
from middlewares.db_session import DatabaseMiddleware
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
    
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        session_factory = await init_db(DATABASE_URL)
        
        # Инициализация дефолтных сценариев
        from database.crud import seed_scenarios
        await seed_scenarios(session_factory)
        
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
        
        # Сохранение сервисов и session_factory в bot data для доступа из handlers
        dp["session_factory"] = session_factory
        dp["rag_service"] = rag_service
        dp["llm_service"] = llm_service
        dp["judge_service"] = judge_service
        dp["sheets_service"] = sheets_service
        
        # Подключение middlewares
        logger.info("Подключение middlewares...")
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        dp.message.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())
        
        # Регистрация handlers
        logger.info("Регистрация обработчиков...")
        
        # /start команда
        dp.message.register(handlers.start.handle_start, Command("start"))
        
        # callback для сценариев
        dp.callback_query.register(
            handlers.scenarios.handle_scenario_callback,
            lambda c: c.data and c.data.startswith("scenario_")
        )
        
        # /finish команда
        dp.message.register(handlers.finish.handle_finish, Command("finish"))
        
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
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
