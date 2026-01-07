import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config.settings import GOOGLE_SHEETS_ID, GOOGLE_CREDENTIALS_PATH
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SheetsService:
    """Сервис для работы с Google Sheets"""
    
    def __init__(self):
        """
        Инициализация сервиса Google Sheets.
        Авторизация через credentials.json и открытие таблицы.
        """
        try:
            # Определяем scope для доступа к Google Sheets и Drive
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Авторизация через service account
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                GOOGLE_CREDENTIALS_PATH,
                scope
            )
            
            # Создаем клиент gspread
            client = gspread.authorize(credentials)
            
            # Открываем таблицу по ID
            spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
            
            # Сохраняем первый worksheet (можно изменить на нужный)
            self.worksheet = spreadsheet.sheet1
            
            logger.info(f"Успешно подключено к Google Sheets: {GOOGLE_SHEETS_ID}")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации SheetsService: {e}")
            raise
    
    async def append_row(self, data: dict):
        """
        Добавляет строку с данными сессии в таблицу.
        
        Args:
            data (dict): Словарь с данными:
                - username: имя пользователя
                - telegram_id: ID пользователя в Telegram
                - scenario: название сценария
                - rating: оценка (опционально)
                - duration: длительность сессии в секундах
                - message_count: количество сообщений
                - status: статус завершения
        """
        try:
            # Формируем строку данных
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # дата и время
                data.get('username', ''),
                str(data.get('telegram_id', '')),
                data.get('scenario', ''),
                str(data.get('rating', '')),
                str(data.get('duration', '')),
                str(data.get('message_count', '')),
                data.get('status', '')
            ]
            
            # Добавляем строку в конец таблицы
            self.worksheet.append_row(row)
            
            logger.info(
                f"Данные успешно добавлены в Google Sheets для пользователя "
                f"{data.get('telegram_id')}"
            )
            
        except Exception as e:
            logger.error(
                f"Ошибка при добавлении данных в Google Sheets: {e}. "
                f"Данные: {data}"
            )
            # Не пробрасываем исключение, чтобы не прерывать работу бота
