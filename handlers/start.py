from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_user_by_telegram_id, create_user
from config.prompts import SCENARIOS


async def handle_start(message: types.Message, session_factory) -> None:
    """
    Обработчик команды /start.
    
    Проверяет наличие пользователя в БД, создает при необходимости,
    и отправляет приветственное сообщение с соответствующими кнопками
    в зависимости от роли (админ/сотрудник).
    """
    async with session_factory() as session:
        telegram_id = message.from_user.id
        
        # Проверяем, есть ли пользователь в БД
        user = await get_user_by_telegram_id(session, telegram_id)
        
        # Если пользователя нет, создаем его
        if not user:
            username = message.from_user.username or ""
            full_name = message.from_user.full_name or ""
            user = await create_user(
                session=session,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name
            )
        
        # Проверяем роль пользователя
        if user.is_admin:
            # Админ: показываем админские кнопки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📊 Отчеты", callback_data="admin_reports"),
                    InlineKeyboardButton(text="👥 Сотрудники", callback_data="admin_employees")
                ]
            ])
            await message.answer(
                "👋 Добро пожаловать, Администратор!",
                reply_markup=keyboard
            )
        else:
            # Сотрудник: показываем кнопки сценариев
            buttons = []
            for key, scenario in SCENARIOS.items():
                button = InlineKeyboardButton(
                    text=scenario["name"],
                    callback_data=f"scenario_{key}"
                )
                buttons.append([button])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer(
                "👋 Добро пожаловать! Выберите сценарий:",
                reply_markup=keyboard
            )
