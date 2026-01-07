# Инструкция по деплою на сервер через GitHub

## 1. Подготовка локального репозитория

### Инициализация Git (если еще не сделано)
```bash
git init
git add .
git commit -m "Initial commit: bot_aigul project"
```

### Если репозиторий уже существует, обновите код
```bash
git add .
git commit -m "Fix: исправлена ошибка с engine в main.py"
git push origin main
```

## 2. Создание репозитория на GitHub

1. Перейдите на https://github.com
2. Нажмите "New repository"
3. Укажите название: `bot_aigul`
4. Выберите "Private" (для приватного проекта)
5. НЕ добавляйте README, .gitignore или LICENSE (они уже есть)
6. Нажмите "Create repository"

## 3. Связывание локального репозитория с GitHub

```bash
# Добавьте удаленный репозиторий
git remote add origin https://github.com/ваш-username/bot_aigul.git

# Или если используете SSH
git remote add origin git@github.com:ваш-username/bot_aigul.git

# Отправьте код на GitHub
git branch -M main
git push -u origin main
```

## 4. Деплой на сервер

### Вариант A: Через SSH на сервер

```bash
# Подключитесь к серверу
ssh user@your-server-ip

# Клонируйте репозиторий
cd /opt  # или другая директория
git clone https://github.com/ваш-username/bot_aigul.git
cd bot_aigul

# Создайте .env файл (НЕ храните его в Git!)
nano .env
# Скопируйте содержимое из локального .env

# Запустите через Docker
docker-compose up -d

# Проверьте логи
docker-compose logs -f bot
```

### Вариант B: Обновление кода на сервере

```bash
# Подключитесь к серверу
ssh user@your-server-ip

# Перейдите в директорию проекта
cd /opt/bot_aigul

# Остановите контейнеры
docker-compose down

# Получите последние изменения
git pull origin main

# Пересоберите и запустите
docker-compose build --no-cache
docker-compose up -d

# Проверьте логи
docker-compose logs -f bot
```

## 5. Автоматизация через GitHub Actions (опционально)

Создайте файл `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Server

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/bot_aigul
            git pull origin main
            docker-compose down
            docker-compose build --no-cache
            docker-compose up -d
```

Добавьте секреты в GitHub:
- Settings → Secrets → Actions → New repository secret
- `SERVER_HOST`: IP адрес сервера
- `SERVER_USER`: имя пользователя
- `SSH_PRIVATE_KEY`: приватный SSH ключ

## 6. Важные замечания

### Файлы, которые НЕ должны попадать в Git:
- `.env` - содержит секретные ключи
- `logs/` - логи бота
- `chroma_data/` - данные ChromaDB
- `credentials.json` - Google Sheets credentials
- `__pycache__/` - Python кэш

Эти файлы уже добавлены в `.gitignore`.

### Безопасность .env файла:
```bash
# На сервере создайте .env вручную
nano .env

# Или используйте переменные окружения в docker-compose.yml
# Или используйте секреты Docker Swarm/Kubernetes
```

## 7. Проверка деплоя

```bash
# Проверьте статус контейнеров
docker-compose ps

# Проверьте логи
docker-compose logs -f bot

# Проверьте подключение к БД
docker-compose exec postgres psql -U postgres -d trainer_db -c "\dt"

# Проверьте работу бота
# Отправьте /start в Telegram
```

## 8. Откат к предыдущей версии (если что-то пошло не так)

```bash
# Посмотрите историю коммитов
git log --oneline

# Откатитесь к предыдущему коммиту
git checkout <commit-hash>

# Пересоберите контейнеры
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 9. Мониторинг

```bash
# Просмотр логов в реальном времени
docker-compose logs -f bot

# Просмотр использования ресурсов
docker stats

# Перезапуск при необходимости
docker-compose restart bot
```
