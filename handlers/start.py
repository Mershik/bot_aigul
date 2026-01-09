from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_user_by_telegram_id, create_user
from config.prompts import SCENARIOS
from config.settings import ADMIN_IDS, GOOGLE_SHEETS_ID


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
        
        # Проверяем, является ли пользователь админом по списку из настроек
        is_admin_in_config = telegram_id in ADMIN_IDS
        
        # Если пользователя нет, создаем его
        if not user:
            username = message.from_user.username or ""
            full_name = message.from_user.full_name or ""
            user = await create_user(
                session=session,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                is_admin=is_admin_in_config
            )
        else:
            # Если пользователь есть, но его статус админа изменился в конфиге - обновляем в БД
            if user.is_admin != is_admin_in_config:
                user.is_admin = is_admin_in_config
                await session.commit()
                await session.refresh(user)
        
        # Формируем кнопки сценариев (доступны всем)
        scenario_buttons = []
        for key, scenario in SCENARIOS.items():
            button = InlineKeyboardButton(
                text=scenario["name"],
                callback_data=f"scenario_{key}"
            )
            scenario_buttons.append([button])
        
        welcome_text = (
            "👋 Добро пожаловать в Тренажер Продаж!\n"
            "Ты — менеджер школы английского языка «Global Speak RF».\n"
            "Я — твой потенциальный клиент. Я знаю цены, сравниваю вас с конкурентами и внимательно читаю договор. 🧐\n"
            "Твоя задача: выявить мои потребности, отработать возражения и закрыть сделку. В конце диалога ИИ-Судья оценит твою работу и даст советы.\n"
            "👇 Выберите сценарий для тренировки:"
        )

        # Если админ - добавляем админские кнопки сверху
        if user.is_admin:
            sheets_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}"
            admin_buttons = [
                [
                    InlineKeyboardButton(text="📊 Отчеты (Google Sheets)", url=sheets_url),
                    InlineKeyboardButton(text="👥 Сотрудники", callback_data="admin_employees")
                ]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=admin_buttons + scenario_buttons)
            # Возвращаем полное описание для админа, но в компактном виде
            admin_welcome = (
                f"👋 **Панель Администратора**\n\n"
                f"{welcome_text}"
            )
            
            if isinstance(message, types.Message):
                await message.answer(admin_welcome, reply_markup=keyboard, parse_mode="Markdown")
            elif isinstance(message, types.CallbackQuery):
                await message.message.edit_text(admin_welcome, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Обычный сотрудник
            keyboard = InlineKeyboardMarkup(inline_keyboard=scenario_buttons)
            await message.answer(
                welcome_text,
                reply_markup=keyboard
            )
