from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_user_by_telegram_id, create_user
from config.prompts import SCENARIOS
from config.settings import ADMIN_IDS, GOOGLE_SHEETS_ID


async def handle_start(event: types.Union[types.Message, types.CallbackQuery], session_factory) -> None:
    """
    Обработчик команды /start и возврата в меню.
    """
    # Определяем объект сообщения и ID пользователя
    if isinstance(event, types.CallbackQuery):
        message = event.message
        telegram_id = event.from_user.id
    else:
        message = event
        telegram_id = event.from_user.id

    async with session_factory() as session:
        # Проверяем, есть ли пользователь в БД
        user = await get_user_by_telegram_id(session, telegram_id)
        
        # Проверяем, является ли пользователь админом по списку из настроек
        is_admin_in_config = telegram_id in ADMIN_IDS
        
        # Если пользователя нет, создаем его
        if not user:
            username = event.from_user.username or ""
            full_name = event.from_user.full_name or ""
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

        # Если админ - показываем только панель управления
        if user.is_admin:
            sheets_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}"
            admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📊 Отчеты (Google Sheets)", url=sheets_url),
                    InlineKeyboardButton(text="👥 Сотрудники", callback_data="admin_employees")
                ],
                [
                    InlineKeyboardButton(text="🚀 Запустить тренажер", callback_data="start_trainer")
                ]
            ])
            
            admin_text = "👋 **Панель управления Администратора**\n\nВыберите раздел:"
            
            if isinstance(event, types.Message):
                await message.answer(admin_text, reply_markup=admin_keyboard, parse_mode="Markdown")
            else:
                await message.edit_text(admin_text, reply_markup=admin_keyboard, parse_mode="Markdown")
        else:
            # Обычный сотрудник
            keyboard = InlineKeyboardMarkup(inline_keyboard=scenario_buttons)
            await message.answer(
                welcome_text,
                reply_markup=keyboard
            )

async def show_trainer_for_admin(callback: types.CallbackQuery, session_factory):
    """Показывает админу приветствие и сценарии тренажера."""
    await callback.answer()
    # Формируем кнопки сценариев
    scenario_buttons = []
    for key, scenario in SCENARIOS.items():
        button = InlineKeyboardButton(
            text=scenario["name"],
            callback_data=f"scenario_{key}"
        )
        scenario_buttons.append([button])
    
    # Добавляем кнопку Назад в админку
    scenario_buttons.append([InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=scenario_buttons)
    
    welcome_text = (
        "👋 Добро пожаловать в Тренажер Продаж!\n"
        "Ты — менеджер школы английского языка «Global Speak RF».\n"
        "Я — твой потенциальный клиент. Я знаю цены, сравниваю вас с конкурентами и внимательно читаю договор. 🧐\n"
        "Твоя задача: выявить мои потребности, отработать возражения и закрыть сделку. В конце диалога ИИ-Судья оценит твою работу и даст советы.\n"
        "👇 Выберите сценарий для тренировки:"
    )
    
    await callback.message.edit_text(welcome_text, reply_markup=keyboard)
    await callback.answer()
