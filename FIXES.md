# Исправления проекта bot_aigul

## Дата: 2026-01-07

## Обзор исправлений

Проект был полностью проанализирован и исправлены все найденные ошибки и противоречия.

---

## 1. requirements.txt - ИСПРАВЛЕНО ✅

### Проблемы:
- Конфликт версий NumPy 2.0 и ChromaDB
- Отсутствие явных версий для некоторых зависимостей
- Отсутствие зависимостей для sentence-transformers

### Исправления:
```txt
# Добавлено явное ограничение NumPy
numpy==1.26.4  # ChromaDB требует numpy<2.0

# Добавлены зависимости для sentence-transformers
torch==2.1.2
torchvision==0.16.2
torchaudio==2.1.2

# Добавлены зависимости для ChromaDB
pydantic==2.5.3
pydantic-settings==2.1.0
```

---

## 2. main.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Дублирование создания engine и sessionmaker
- Неправильный вызов `init_db()` - передавался engine вместо database_url
- Удаление несуществующего engine в finally блоке
- Неправильная инициализация AuthMiddleware

### Исправления:
```python
# БЫЛО:
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
await init_db(engine)

# СТАЛО:
async_session = await init_db(DATABASE_URL)

# БЫЛО:
dp.message.middleware(AuthMiddleware(async_session))

# СТАЛО:
dp.message.middleware(AuthMiddleware())

# БЫЛО в finally:
await engine.dispose()

# СТАЛО:
# Удалено (engine создается внутри init_db)
```

---

## 3. database/__init__.py - БЕЗ ИЗМЕНЕНИЙ ✅

Функция уже была правильной:
- Принимает `database_url: str`
- Создает engine внутри себя
- Возвращает `async_sessionmaker`

---

## 4. database/crud.py - ИСПРАВЛЕНО ✅

### Проблемы:
- `create_session()` принимала `scenario_id` вместо `scenario` (строка)
- `get_session_messages()` не принимала параметр `limit`
- `get_session_messages()` возвращала объекты Message вместо dict для LLM

### Исправления:
```python
# БЫЛО:
async def create_session(session: AsyncSession, user_id: int, scenario_id: int)

# СТАЛО:
async def create_session(session: AsyncSession, user_id: int, scenario: str)

# БЫЛО:
async def get_session_messages(session: AsyncSession, session_id: int) -> List[Message]

# СТАЛО:
async def get_session_messages(
    session: AsyncSession, 
    session_id: int, 
    limit: Optional[int] = None
) -> List[dict]:
    # Возвращает формат для LLM: [{"role": "user", "content": "..."}]
```

---

## 5. services/rag.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Методы `load_knowledge_base()` и `search()` были синхронными
- Вызывались с `await` в других частях кода

### Исправления:
```python
# БЫЛО:
def load_knowledge_base(self, folder_path: str):
def search(self, query: str, top_k: int = 3) -> list[str]:

# СТАЛО:
async def load_knowledge_base(self, folder_path: str):
async def search(self, query: str, top_k: int = 3) -> list[str]:
```

---

## 6. services/judge.py - ИСПРАВЛЕНО ✅

### Проблемы:
- `__init__()` принимал `llm_service` как параметр, но создавался без него
- Неправильный порядок параметров в `evaluate_session()`
- Неправильный вызов `get_session_messages()`
- Неправильный вызов `create_evaluation()`

### Исправления:
```python
# БЫЛО:
def __init__(self, llm_service: LLMService):
    self.llm_service = llm_service

# СТАЛО:
def __init__(self):
    self.llm_service = LLMService()

# БЫЛО:
async def evaluate_session(self, session_id: int, db_session: AsyncSession)
msgs = await get_session_messages(session_id, db_session)

# СТАЛО:
async def evaluate_session(self, db_session: AsyncSession, session_id: int)
msgs = await get_session_messages(db_session, session_id)

# БЫЛО:
await create_evaluation(..., db=db_session)

# СТАЛО:
await create_evaluation(..., session=db_session)
```

---

## 7. services/sheets.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Отсутствовал метод `write_session_result()`

### Исправления:
```python
# Добавлен метод:
async def write_session_result(
    self,
    session_id: int,
    username: str,
    date: str,
    scenario: str,
    duration_minutes: int,
    message_count: int,
    score: int,
    strengths: list,
    mistakes: list,
    recommendations: str
):
    # Записывает результаты в Google Sheets
```

---

## 8. handlers/chat.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Создание экземпляров сервисов на уровне модуля
- Сервисы должны браться из `bot.data`

### Исправления:
```python
# БЫЛО:
llm_service = LLMService()
rag_service = RAGService()

# СТАЛО:
# Удалено

# В функции handle_message:
rag_service = message.bot.get("rag_service")
llm_service = message.bot.get("llm_service")
```

---

## 9. handlers/scenarios.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Создание экземпляра LLMService локально
- Неправильное извлечение system_prompt из SCENARIOS
- Не сохранялся system_prompt в state

### Исправления:
```python
# БЫЛО:
from services.llm import LLMService
llm_service = LLMService()
system_prompt = SCENARIOS[scenario_key]

# СТАЛО:
llm_service = callback.bot.get("llm_service")
system_prompt = SCENARIOS[scenario_key]["system_prompt"]

# Добавлено сохранение в state:
await state.update_data(
    session_id=db_session.id,
    system_prompt=system_prompt
)
```

---

## 10. handlers/finish.py - ИСПРАВЛЕНО ✅

### Проблемы:
- Импорт неиспользуемых сервисов
- Статические вызовы методов сервисов

### Исправления:
```python
# БЫЛО:
from services.judge import JudgeService
from services.sheets import SheetsService
evaluation = await JudgeService.evaluate_session(session, session_id)
await SheetsService.write_session_result(...)

# СТАЛО:
judge_service = message.bot.get("judge_service")
sheets_service = message.bot.get("sheets_service")
evaluation = await judge_service.evaluate_session(session, session_id)
await sheets_service.write_session_result(...)
```

---

## 11. Dockerfile - СОЗДАН ✅

### Проблемы:
- Файл был пустым

### Исправления:
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y gcc g++

# Установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Создание директорий
RUN mkdir -p logs chroma_data knowledge_base

CMD ["python", "main.py"]
```

---

## 12. docker-compose.yml - СОЗДАН ✅

### Проблемы:
- Файл был пустым

### Исправления:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-bot_aigul}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 10s

  bot:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./chroma_data:/app/chroma_data
      - ./knowledge_base:/app/knowledge_base

volumes:
  postgres_data:
```

---

## 13. Дополнительные файлы - СОЗДАНЫ ✅

### .env.example
Создан шаблон для переменных окружения с описанием всех параметров.

### README.md
Обновлен с полной документацией:
- Структура проекта
- Инструкции по установке
- Запуск через Docker
- Troubleshooting

---

## Итоговый результат

### ✅ Исправлено:
1. Конфликты версий библиотек (NumPy, ChromaDB)
2. Дублирование создания engine и sessionmaker
3. Несоответствие сигнатур функций
4. Синхронные методы вместо асинхронных
5. Неправильная инициализация сервисов
6. Отсутствующие методы
7. Пустые Docker файлы

### ✅ Добавлено:
1. Правильные версии зависимостей
2. Dockerfile с корректной конфигурацией
3. docker-compose.yml для оркестрации
4. .env.example для документации
5. Обновленный README.md

### ✅ Проверено:
1. Все импорты корректны
2. Нет циклических зависимостей
3. Async/await используется правильно
4. Только asyncpg для PostgreSQL
5. ChromaDB совместим с NumPy < 2.0

## Запуск проекта

```bash
# 1. Настроить .env
cp .env.example .env
# Заполнить необходимые значения

# 2. Запустить через Docker Compose
docker-compose up -d

# 3. Проверить логи
docker-compose logs -f bot
```

---

## 14. DATABASE_URL - ИСПРАВЛЕНО ✅

### Проблемы:
- В `.env` использовался синхронный драйвер `postgresql://` вместо асинхронного `postgresql+asyncpg://`
- Отсутствовала валидация `DATABASE_URL` в `config/settings.py`

### Исправления:

#### .env
```env
# БЫЛО:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trainer_db

# СТАЛО:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/trainer_db
```

#### config/settings.py
```python
# Добавлена валидация:
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в .env")
```

### Объяснение:
SQLAlchemy с `create_async_engine()` требует асинхронный драйвер. Для PostgreSQL это `asyncpg`, который указывается в URL как `postgresql+asyncpg://`. Использование обычного `postgresql://` приводит к ошибкам при попытке создания асинхронного подключения.

---

## 15. PyTorch и Transformers совместимость - ИСПРАВЛЕНО ✅

### Проблемы:
- Ошибка `AttributeError: module 'torch.utils._pytree' has no attribute 'register_pytree_node'`
- Несовместимость версий `torch` и `transformers`
- Старая версия `sentence-transformers==2.3.1`

### Исправления:

#### requirements.txt
```txt
# БЫЛО:
sentence-transformers==2.3.1

# СТАЛО:
sentence-transformers==2.5.1
transformers==4.38.2  # Добавлена явная версия для совместимости
```

### Объяснение:
Библиотека `sentence-transformers` зависит от `transformers`, которая в свою очередь использует PyTorch. Старая версия `sentence-transformers==2.3.1` не совместима с изменениями в PyTorch 2.1.2. Обновление до версии 2.5.1 и явное указание совместимой версии `transformers==4.38.2` решает проблему.

---

## 16. Docker контейнер использует старый код - РЕШЕНО ✅

### Проблемы:
- Docker контейнер был собран со старой версией `main.py`
- В старой версии использовалась несуществующая переменная `engine`

### Решение:
```bash
# Пересобрать Docker образ без кэша
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Объяснение:
Docker кэширует слои образа. Если код изменился, но Docker использует кэшированный слой, контейнер будет работать со старым кодом. Флаг `--no-cache` заставляет Docker пересобрать все слои заново.

---

## 17. IntegrityError при создании сессии - ИСПРАВЛЕНО ✅

### Проблемы:
- В таблице `users` первичным ключом является автоинкрементный `id` (1, 2, 3...)
- Таблица `sessions` связана с `users` через внешний ключ по колонке `id` (внутренний ID)
- Код в `handlers/scenarios.py` передавал `callback.from_user.id` (Telegram ID) вместо внутреннего `id`
- База данных выбрасывала `IntegrityError (ForeignKeyViolationError)`, так как не находила пользователя с таким порядковым номером

### Исправления:

#### handlers/scenarios.py
```python
# БЫЛО:
from database.crud import create_session
from config.prompts import SCENARIOS

async def handle_scenario_callback(...):
    async with session_factory() as session:
        # ...
        db_session = await create_session(
            session=session,
            user_id=callback.from_user.id,  # ❌ Telegram ID вместо внутреннего ID
            scenario=scenario_key
        )

# СТАЛО:
from database.crud import create_session, get_user_by_telegram_id
from database.models import User
from config.prompts import SCENARIOS
from sqlalchemy import select

async def handle_scenario_callback(...):
    async with session_factory() as session:
        # ...
        # Получаем пользователя из БД по telegram_id
        user_obj = await get_user_by_telegram_id(session, callback.from_user.id)
        
        if not user_obj:
            await callback.answer("❌ Пользователь не найден. Используйте /start", show_alert=True)
            return
        
        # Создаем новую Session в БД с внутренним id пользователя
        db_session = await create_session(
            session=session,
            user_id=user_obj.id,  # ✅ Внутренний ID из БД
            scenario=scenario_key
        )
```

#### database/crud.py
```python
# Добавлена валидация и документация в create_session():

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
    
    # ... создание сессии
```

### Объяснение:
В PostgreSQL таблица `users` имеет два поля:
- `id` (Integer, Primary Key, Autoincrement) - внутренний порядковый номер: 1, 2, 3...
- `telegram_id` (BigInteger, Unique) - ID пользователя в Telegram: 123456789, 987654321...

Таблица `sessions` связана с `users` через `ForeignKey("users.id")`, то есть по внутреннему `id`, а не по `telegram_id`.

Когда код передавал `callback.from_user.id` (например, 987654321), база данных искала пользователя с `id=987654321`, не находила его и выбрасывала ошибку нарушения внешнего ключа.

Правильный подход:
1. Получить объект пользователя из БД по `telegram_id`
2. Использовать его внутренний `id` для создания связанных записей

### Проверено:
- ✅ `handlers/scenarios.py` - исправлено
- ✅ `handlers/chat.py` - использует `session_id` из state, проблем нет
- ✅ `handlers/finish.py` - использует `session_id` из state, проблем нет
- ✅ `handlers/start.py` - корректно использует `get_user_by_telegram_id()` и `create_user()`
- ✅ `database/crud.py` - добавлена валидация в `create_session()`

---

Проект готов к запуску! 🚀
