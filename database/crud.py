from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import User, Scenario, Session, Message, Evaluation


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    is_admin: bool = False
) -> User:
    """Создать нового пользователя."""
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        is_admin=is_admin
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """Получить пользователя по telegram_id."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_scenario(
    session: AsyncSession,
    scenario_name: str
) -> Scenario:
    """
    Получить сценарий по имени или создать новый.
    
    Args:
        session: Сессия БД
        scenario_name: Ключ сценария из SCENARIOS (например, 'expensive', 'cold_call')
        
    Returns:
        Найденный или созданный сценарий
    """
    from config.prompts import SCENARIOS
    
    # Ищем сценарий по имени
    result = await session.execute(
        select(Scenario).where(Scenario.name == scenario_name)
    )
    scenario = result.scalar_one_or_none()
    
    # Если не найден, создаем
    if not scenario:
        if scenario_name not in SCENARIOS:
            raise ValueError(f"Сценарий '{scenario_name}' не найден в конфигурации")
        
        scenario_config = SCENARIOS[scenario_name]
        scenario = Scenario(
            name=scenario_name,
            description=scenario_config.get("name", ""),
            system_prompt=scenario_config["system_prompt"]
        )
        session.add(scenario)
        await session.commit()
        await session.refresh(scenario)
    
    return scenario


async def create_session(
    session: AsyncSession,
    user_id: int,
    scenario: str
) -> Session:
    """
    Создать новую сессию.
    
    Args:
        session: Сессия БД
        user_id: Внутренний ID пользователя из таблицы users (НЕ telegram_id!)
        scenario: Ключ сценария (например, 'expensive', 'cold_call')
        
    Returns:
        Созданная сессия
        
    Raises:
        ValueError: Если пользователь с указанным user_id не найден
    """
    # Проверяем существование пользователя
    user_result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден в базе данных")
    
    # Получаем или создаем сценарий
    scenario_obj = await get_or_create_scenario(session, scenario)
    
    new_session = Session(
        user_id=user_id,
        scenario_id=scenario_obj.id,
        status="active",
        started_at=datetime.utcnow(),
        messages_count=0
    )
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return new_session


async def update_session(
    session: AsyncSession,
    session_id: int,
    status: Optional[str] = None,
    finished_at: Optional[datetime] = None,
    messages_count: Optional[int] = None,
    duration_minutes: Optional[int] = None
) -> Optional[Session]:
    """Обновить данные сессии."""


async def get_session_with_relations(
    session: AsyncSession,
    session_id: int
) -> Optional[Session]:
    """Получить сессию с подгруженными связями (scenario, messages)."""
    result = await session.execute(
        select(Session)
        .options(
            selectinload(Session.scenario),
            selectinload(Session.messages)
        )
        .where(Session.id == session_id)
    )
    return result.scalar_one_or_none()
    result = await session.execute(
        select(Session).where(Session.id == session_id)
    )
    db_session = result.scalar_one_or_none()
    
    if db_session is None:
        return None
    
    if status is not None:
        db_session.status = status
    if finished_at is not None:
        db_session.finished_at = finished_at
    if messages_count is not None:
        db_session.messages_count = messages_count
    if duration_minutes is not None:
        db_session.duration_minutes = duration_minutes
    
    await session.commit()
    await session.refresh(db_session)
    return db_session


async def add_message(
    session: AsyncSession,
    session_id: int,
    role: str,
    content: str
) -> Message:
    """Добавить сообщение в сессию."""
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        timestamp=datetime.utcnow()
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def get_session_messages(
    session: AsyncSession,
    session_id: int,
    limit: Optional[int] = None
) -> List[dict]:
    """Получить сообщения сессии в формате для LLM."""
    query = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp.desc())
    )
    
    if limit:
        query = query.limit(limit)
    
    result = await session.execute(query)
    messages = list(result.scalars().all())
    
    # Возвращаем в обратном порядке (от старых к новым) и в формате для LLM
    return [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(messages)
    ]


async def create_evaluation(
    session: AsyncSession,
    session_id: int,
    score: int,
    good_points: Optional[List[str]] = None,
    mistakes: Optional[List[str]] = None,
    recommendations: Optional[str] = None
) -> Evaluation:
    """Создать оценку для сессии."""
    evaluation = Evaluation(
        session_id=session_id,
        score=score,
        good_points=good_points or [],
        mistakes=mistakes or [],
        recommendations=recommendations,
        evaluated_at=datetime.utcnow()
    )
    session.add(evaluation)
    await session.commit()
    await session.refresh(evaluation)
    return evaluation


async def seed_scenarios(session_factory) -> None:
    """
    Инициализация таблицы scenarios дефолтными значениями.
    Вызывается при запуске бота для предотвращения ошибок внешнего ключа.
    """
    import logging
    from config.prompts import SCENARIOS
    
    async with session_factory() as session:
        # Проверяем, есть ли уже сценарии
        result = await session.execute(select(Scenario))
        existing_scenarios = result.scalars().all()
        
        if not existing_scenarios:
            # Добавляем все сценарии из конфигурации
            for scenario_key, scenario_config in SCENARIOS.items():
                scenario = Scenario(
                    name=scenario_key,
                    description=scenario_config.get("name", ""),
                    system_prompt=scenario_config["system_prompt"]
                )
                session.add(scenario)
            
            await session.commit()
            logging.info(f"✅ Добавлено {len(SCENARIOS)} дефолтных сценариев в БД")
        else:
            logging.info(f"ℹ️ В БД уже есть {len(existing_scenarios)} сценариев")
