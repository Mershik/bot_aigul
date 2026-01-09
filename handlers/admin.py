import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.models import User
from database.crud import create_user, get_user_by_telegram_id

logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_employee_id = State()

async def handle_admin_employees(callback: types.CallbackQuery, session_factory):
    """Показывает список сотрудников и кнопку добавления."""
    async with session_factory() as session:
        # Получаем всех пользователей, которые не админы
        result = await session.execute(select(User).where(User.is_admin == False))
        users = result.scalars().all()
        
        text = "👥 **Список сотрудников в базе:**\n\n"
        if not users:
            text += "Список пуст."
        for u in users:
            text += f"• {u.full_name or u.username} (ID: `{u.telegram_id}`)\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="admin_add_employee")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()

async def start_add_employee(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает ID нового сотрудника."""
    await callback.message.answer("Пришлите Telegram ID сотрудника, которому нужно дать доступ:")
    await state.set_state(AdminStates.waiting_for_employee_id)
    await callback.answer()

async def process_add_employee(message: types.Message, state: FSMContext, session_factory):
    """Сохраняет нового сотрудника в базу."""
    if not message.text.isdigit():
        await message.answer("❌ Ошибка: ID должен состоять только из цифр. Попробуйте еще раз:")
        return
    
    new_id = int(message.text)
    
    async with session_factory() as session:
        # Проверяем, нет ли его уже
        existing = await get_user_by_telegram_id(session, new_id)
        if existing:
            await message.answer(f"ℹ️ Пользователь с ID `{new_id}` уже есть в базе.")
        else:
            await create_user(
                session=session,
                telegram_id=new_id,
                username=f"user_{new_id}",
                full_name="Новый сотрудник",
                is_admin=False
            )
            await message.answer(f"✅ Сотрудник с ID `{new_id}` успешно добавлен и теперь имеет доступ к боту.")
    
    await state.clear()
