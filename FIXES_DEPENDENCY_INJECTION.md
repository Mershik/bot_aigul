# Исправление ошибки AttributeError: 'Bot' object has no attribute 'get'

## Проблема
В aiogram 3.x нельзя использовать `bot.get()` или `bot['key']` для получения сервисов. Вместо этого нужно использовать dependency injection через аргументы функций-обработчиков.

## Решение
Изменены сигнатуры всех функций-обработчиков, чтобы они принимали необходимые сервисы напрямую в качестве аргументов. Aiogram 3.x автоматически инжектирует зависимости из `dp` (диспетчера) в функции по именам аргументов.

## Внесенные изменения

### 1. handlers/scenarios.py
**Было:**
```python
async def handle_scenario_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    session_factory
) -> None:
    ...
    llm_service = callback.bot.get("llm_service")  # ❌ Ошибка!
```

**Стало:**
```python
async def handle_scenario_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    session_factory,
    llm_service  # ✅ Прямой аргумент
) -> None:
    ...
    # llm_service уже доступен как аргумент
```

### 2. handlers/chat.py
**Было:**
```python
async def handle_message(message: types.Message, state: FSMContext, session_factory) -> None:
    ...
    bot_data = message.bot
    rag_service = bot_data.get("rag_service")  # ❌ Ошибка!
    llm_service = bot_data.get("llm_service")  # ❌ Ошибка!
```

**Стало:**
```python
async def handle_message(
    message: types.Message,
    state: FSMContext,
    session_factory,
    rag_service,  # ✅ Прямой аргумент
    llm_service   # ✅ Прямой аргумент
) -> None:
    ...
    # Сервисы уже доступны как аргументы
```

### 3. handlers/finish.py
**Было:**
```python
async def handle_finish(
    message: types.Message,
    state: FSMContext,
    session_factory,
    bot  # ❌ Неправильно
) -> None:
    ...
    judge_service = message.bot.get("judge_service")  # ❌ Ошибка!
    sheets_service = message.bot.get("sheets_service")  # ❌ Ошибка!
    ...
    await bot.send_message(admin_id, ...)
```

**Стало:**
```python
async def handle_finish(
    message: types.Message,
    state: FSMContext,
    session_factory,
    judge_service,   # ✅ Прямой аргумент
    sheets_service   # ✅ Прямой аргумент
) -> None:
    ...
    # Сервисы уже доступны как аргументы
    ...
    await message.bot.send_message(admin_id, ...)  # ✅ Используем message.bot
```

### 4. middlewares/db_session.py
**Было:**
```python
class DatabaseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data) -> Any:
        session_factory = data.get("session_factory")
        if session_factory:
            data["session_factory"] = session_factory
        return await handler(event, data)
```

**Стало:**
```python
class DatabaseMiddleware(BaseMiddleware):
    """
    В aiogram 3.x данные из dp автоматически доступны в data,
    поэтому этот middleware просто пропускает событие дальше.
    """
    async def __call__(self, handler, event, data) -> Any:
        # Все данные из dp уже автоматически доступны в data
        return await handler(event, data)
```

## Как это работает

1. В `main.py` сервисы сохраняются в диспетчере:
```python
dp["session_factory"] = session_factory
dp["rag_service"] = rag_service
dp["llm_service"] = llm_service
dp["judge_service"] = judge_service
dp["sheets_service"] = sheets_service
```

2. Aiogram 3.x автоматически инжектирует эти зависимости в функции-обработчики по именам аргументов:
   - Если функция имеет аргумент `rag_service`, aiogram автоматически передаст `dp["rag_service"]`
   - Если функция имеет аргумент `llm_service`, aiogram автоматически передаст `dp["llm_service"]`
   - И так далее для всех сервисов

3. Имена аргументов должны точно совпадать с ключами в `dp`

## Результат
✅ Ошибка `AttributeError: 'Bot' object has no attribute 'get'` исправлена
✅ Все обработчики теперь получают сервисы через dependency injection
✅ Код стал более явным и типобезопасным
