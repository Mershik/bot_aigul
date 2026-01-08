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
        scenario: Ключ сценария
        
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
    
    new_session = Session(
        user_id=user_id,
        scenario_id=1,  # TODO: Получить scenario_id из базы по имени сценария
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
