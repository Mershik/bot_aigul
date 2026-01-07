# Bot Aigul - Telegram Bot для тренировки навыков продаж

Telegram-бот на базе Aiogram 3 с использованием PostgreSQL, ChromaDB и OpenRouter API для симуляции диалогов с клиентами.

## Технологии

- **Python 3.11**
- **Aiogram 3.4** - фреймворк для Telegram ботов
- **PostgreSQL** - основная база данных
- **ChromaDB** - векторная база для RAG
- **OpenRouter API** - доступ к LLM моделям
- **Docker & Docker Compose** - контейнеризация

## Структура проекта

```
bot_aigul/
├── config/              # Конфигурация и промпты
│   ├── settings.py      # Настройки из .env
│   └── prompts.py       # Системные промпты для сценариев
├── database/            # Работа с БД
│   ├── __init__.py      # Инициализация БД
│   ├── models.py        # SQLAlchemy модели
│   └── crud.py          # CRUD операции
├── handlers/            # Обработчики команд и сообщений
│   ├── start.py         # /start команда
│   ├── scenarios.py     # Выбор сценария
│   ├── chat.py          # Обработка диалога
│   └── finish.py        # /finish команда
├── middlewares/         # Middleware для бота
│   ├── auth.py          # Проверка whitelist
│   └── rate_limit.py    # Ограничение частоты запросов
├── services/            # Бизнес-логика
│   ├── llm.py           # Работа с OpenRouter API
│   ├── rag.py           # RAG с ChromaDB
│   ├── judge.py         # Оценка диалогов
│   └── sheets.py        # Запись в Google Sheets
├── knowledge_base/      # PDF и TXT файлы для RAG
├── main.py              # Точка входа
├── requirements.txt     # Python зависимости
├── Dockerfile           # Docker образ
└── docker-compose.yml   # Docker Compose конфигурация
```

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd bot_aigul
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните необходимые значения:

```bash
cp .env.example .env
```

Обязательные переменные:
- `BOT_TOKEN` - токен Telegram бота от @BotFather
- `OPENROUTER_API_KEY` - API ключ от OpenRouter
- `DATABASE_URL` - URL подключения к PostgreSQL
- `WHITELIST_EMPLOYEES` - список разрешенных Telegram ID через запятую
- `ADMIN_IDS` - список администраторов через запятую

### 3. Запуск через Docker Compose (рекомендуется)

```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

### 4. Запуск без Docker (для разработки)

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск бота
python main.py
```

## База знаний (RAG)

Поместите PDF или TXT файлы в папку `knowledge_base/`. Бот автоматически загрузит их при старте и будет использовать для контекстных ответов.

## Google Sheets интеграция

1. Создайте Service Account в Google Cloud Console
2. Скачайте `credentials.json`
3. Поместите файл в корень проекта
4. Укажите ID таблицы в `GOOGLE_SHEETS_ID`

## Сценарии

Доступные сценарии настраиваются в `config/prompts.py`:
- **expensive** - Отработка возражения "Дорого"
- **cold_call** - Холодный звонок

## Команды бота

- `/start` - Начать работу, выбрать сценарий
- `/finish` - Завершить диалог и получить оценку
- Текстовые сообщения - Диалог с AI клиентом

## Разработка

### Структура базы данных

- `users` - Пользователи бота
- `scenarios` - Сценарии диалогов
- `sessions` - Сессии тренировок
- `messages` - Сообщения в диалогах
- `evaluations` - Оценки сессий

### Добавление нового сценария

1. Добавьте сценарий в `config/prompts.py`:
```python
SCENARIO_NEW = {
    "name": "Название сценария",
    "system_prompt": BASE_SYSTEM_PROMPT + """
    Дополнительные инструкции...
    """
}

SCENARIOS = {
    "new_scenario": SCENARIO_NEW,
    # ...
}
```

2. Сценарий автоматически появится в меню бота

## Troubleshooting

### Ошибка при установке зависимостей

Если возникают проблемы с NumPy/ChromaDB:
```bash
pip install numpy==1.26.4
pip install chromadb==0.4.22
```

### База данных не подключается

Проверьте `DATABASE_URL` в `.env`:
```
postgresql+asyncpg://user:password@host:port/database
```

### ChromaDB ошибки

Убедитесь, что используется NumPy < 2.0:
```bash
pip install "numpy<2.0"
```

## Лицензия

MIT
