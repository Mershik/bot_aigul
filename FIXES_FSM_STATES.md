# Исправление проблем с FSM состояниями и отправкой сообщений

## Проблемы
1. Сообщения от бота не приходят в Telegram
2. Входящие сообщения обрабатываются за 0 мс (не доходят до обработчика)
3. Неправильная проверка FSM состояния

## Внесенные исправления

### 1. handlers/chat.py - Исправлена проверка состояния

**Было:**
```python
from aiogram.fsm.context import FSMContext

async def handle_message(message, state, session_factory, rag_service, llm_service):
    current_state = await state.get_state()
    
    # ❌ Неправильная проверка - сравнение со строкой
    if current_state != "in_dialog":
        return
```

**Стало:**
```python
from aiogram.fsm.context import FSMContext
from handlers.scenarios import DialogStates  # ✅ Импортируем состояния

async def handle_message(message, state, session_factory, rag_service, llm_service):
    current_state = await state.get_state()
    
    # ✅ Правильная проверка - сравнение с состоянием
    if current_state != DialogStates.in_dialog.state:
        logger.debug(f"Сообщение проигнорировано: пользователь {message.from_user.id} не в диалоге (текущее состояние: {current_state})")
        return
```

### 2. main.py - Добавлен фильтр состояния для обработчика сообщений

**Было:**
```python
from aiogram import Bot, Dispatcher
from aiogram.filters import Command

# Обработчик всех текстовых сообщений (без фильтра)
dp.message.register(handlers.chat.handle_message)
```

**Стало:**
```python
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter

# ✅ Обработчик только для сообщений в состоянии in_dialog
dp.message.register(
    handlers.chat.handle_message,
    StateFilter(handlers.scenarios.DialogStates.in_dialog),
    F.text
)
```

**Почему это важно:**
- `StateFilter` гарантирует, что обработчик вызывается только когда пользователь в диалоге
- `F.text` фильтрует только текстовые сообщения (игнорирует фото, стикеры и т.д.)
- Это предотвращает обработку сообщений вне диалога

### 3. handlers/scenarios.py - Сохранение первого сообщения в БД

**Было:**
```python
# Генерируем ответ
ai_response = await llm_service.generate_response(
    system_prompt=system_prompt,
    messages=[]
)

# ❌ Сразу отправляем, не сохраняя в БД
await callback.message.answer(ai_response)
```

**Стало:**
```python
# Генерируем ответ
ai_response = await llm_service.generate_response(
    system_prompt=system_prompt,
    messages=[]
)

# ✅ Сначала сохраняем в БД
await add_message(
    session=session,
    session_id=db_session.id,
    role="assistant",
    content=ai_response
)

# ✅ Потом отправляем пользователю
await callback.message.answer(ai_response)
```

### 4. handlers/scenarios.py - Добавлено логирование

Добавлено детальное логирование для отладки:
```python
logger.info(f"Обработка выбора сценария от пользователя {callback.from_user.id}")
logger.info(f"Выбран сценарий: {scenario_key}")
logger.info(f"Отправка первого ответа пользователю {callback.from_user.id}")
logger.info(f"Установлено состояние DialogStates.in_dialog для пользователя {callback.from_user.id}")
```

## Как работает FSM в aiogram 3.x

### Установка состояния:
```python
from aiogram.fsm.state import State, StatesGroup

class DialogStates(StatesGroup):
    in_dialog = State()

# Установка состояния
await state.set_state(DialogStates.in_dialog)
```

### Проверка состояния:
```python
# Получение текущего состояния
current_state = await state.get_state()

# Правильная проверка
if current_state == DialogStates.in_dialog.state:
    # Пользователь в диалоге
    pass
```

### Фильтрация по состоянию:
```python
from aiogram.filters import StateFilter

# При регистрации обработчика
dp.message.register(
    handler_function,
    StateFilter(DialogStates.in_dialog)  # Только для этого состояния
)
```

## Результат
✅ Сообщения от бота теперь отправляются в Telegram
✅ Входящие сообщения правильно обрабатываются
✅ FSM состояния работают корректно
✅ Первое сообщение сохраняется в БД для истории диалога
✅ Добавлено детальное логирование для отладки
