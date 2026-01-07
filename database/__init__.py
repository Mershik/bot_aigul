from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .models import Base, User, Scenario, Session, Message, Evaluation


async def init_db(database_url: str) -> async_sessionmaker[AsyncSession]:
    """
    Инициализация базы данных.
    
    Args:
        database_url: URL подключения к PostgreSQL (например: postgresql+asyncpg://user:password@localhost/dbname)
    
    Returns:
        async_sessionmaker для создания сессий
    """
    # Создаем асинхронный движок
    engine = create_async_engine(
        database_url,
        echo=False,  # Установите True для отладки SQL-запросов
        future=True,
        pool_pre_ping=True,  # Проверка соединения перед использованием
    )
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем фабрику сессий
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    return async_session_factory


__all__ = [
    "init_db",
    "Base",
    "User",
    "Scenario",
    "Session",
    "Message",
    "Evaluation",
]
