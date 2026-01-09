import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete

from database.models import User
from database.crud import create_user, get_user_by_telegram_id

logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_employee_data = State()

async def handle_admin_employees(callback: types.CallbackQuery, session_factory):
    """Показывает список сотрудников с кнопками удаления."""
    await callback.answer()
    async with session_factory() as session:
        # Получаем всех пользователей, которые не админы
        result = await session.execute(select(User).where(User.is_admin == False))
        users = result.scalars().all()
        
        text = "👥 **Управление сотрудниками**\n\n"
        
        keyboard_buttons = []
        
        if not users:
            text += "Список пуст."
        else:
            for u in users:
                name = u.full_name or u.username or f"ID: {u.telegram_id}"
                # Ограничиваем длину имени для кнопки
                display_name = (name[:20] + '..') if len(name) > 20 else name
                keyboard_buttons.append([
                    InlineKeyboardButton(text=f"❌ {display_name}", callback_data=f"admin_del_{u.telegram_id}")
                ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="admin_add_employee")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            # Если edit_text не срабатывает (например, сообщение то же самое), пробуем заново
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()

async def delete_employee(callback: types.CallbackQuery, session_factory):
    """Удаляет сотрудника из базы."""
    await callback.answer("⏳ Удаление...", show_alert=False)
    user_id = int(callback.data.replace("admin_del_", ""))
    
    async with session_factory() as session:
        await session.execute(delete(User).where(User.telegram_id == user_id))
        await session.commit()
    
    await callback.answer("✅ Сотрудник удален", show_alert=True)
    await handle_admin_employees(callback, session_factory)

async def start_add_employee(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает данные нового сотрудника."""
    await callback.message.answer(
        "Введите данные сотрудника в формате:\n`ID Имя` (через пробел)\n\n"
        "Пример: `144842314 Иван Иванов`",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_employee_data)
    await callback.answer()

async def process_add_employee(message: types.Message, state: FSMContext, session_factory):
    """Сохраняет нового сотрудника в базу с именем."""
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("❌ Ошибка! Введите ID (цифры) и Имя через пробел.\nПример: `12345678 Иван`")
        return
    
    new_id = int(parts[0])
    new_name = parts[1]
    
    async with session_factory() as session:
        existing = await get_user_by_telegram_id(session, new_id)
        if existing:
            # Если пользователь уже есть, просто обновим ему имя
            existing.full_name = new_name
            await session.commit()
            await message.answer(f"✅ Имя сотрудника с ID `{new_id}` обновлено на `{new_name}`.")
        else:
            await create_user(
                session=session,
                telegram_id=new_id,
                username=f"user_{new_id}",
                full_name=new_name,
                is_admin=False
            )
            await message.answer(f"✅ Сотрудник `{new_name}` (ID: `{new_id}`) успешно добавлен.")
    
    await state.clear()
    # Возвращаемся в меню (имитируем callback)
    # Для простоты просто просим нажать /start
    await message.answer("Используйте /start для возврата в меню.")
