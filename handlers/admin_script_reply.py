import logging
from aiogram import types, Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import ENABLE_SCRIPT_REPLY
from config.prompts import SCRIPT_REPLY_SYSTEM_PROMPT
from services.llm import LLMService
from services.rag import RAGService

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith("script_reply_"))
async def handle_script_reply(callback: types.CallbackQuery, llm_service: LLMService, rag_service: RAGService):
    """Обработчик нажатия кнопки 'Ответить по скрипту'"""
    if not ENABLE_SCRIPT_REPLY:
        await callback.answer("Функционал отключен в настройках", show_alert=True)
        return

    await callback.answer("Генерирую ответ...")
    
    # Извлекаем текст сообщения бота (клиента), на которое админу нужно ответить
    bot_message_text = callback.message.text or callback.message.caption or ""
    
    if not bot_message_text:
        await callback.message.answer("Не удалось получить текст сообщения для анализа.")
        return

    try:
        # 1. Поиск в базе знаний (скрипты) на основе сообщения бота
        # Чтобы понять, как ответить на реплику бота, мы ищем подходящие скрипты
        context_list = await rag_service.search(bot_message_text, collection_type="scripts", top_k=3)
        context = "\n---\n".join(context_list) if context_list else "Скрипты не найдены."

        # 2. Генерация ответа через LLM
        # Мы просим LLM придумать ответ МЕНЕДЖЕРА на реплику КЛИЕНТА (бота)
        messages = [{"role": "user", "content": f"Клиент сказал: {bot_message_text}"}]
        ai_reply = await llm_service.generate_response(
            messages=messages,
            system_prompt=SCRIPT_REPLY_SYSTEM_PROMPT,
            context=context
        )

        # 3. Отправка результата админу
        response_text = f"📝 **Предлагаемый ответ по скрипту:**\n\n{ai_reply}"
        
        await callback.message.reply(response_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации ответа по скрипту: {e}")
        await callback.message.answer("Произошла ошибка при генерации ответа.")

def get_script_reply_keyboard():
    """Возвращает клавиатуру с кнопкой 'Ответить по скрипту'"""
    if not ENABLE_SCRIPT_REPLY:
        return None
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Ответить по скрипту", callback_data="script_reply_gen")]
    ])
