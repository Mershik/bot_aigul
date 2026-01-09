import gspread_asyncio
from google.oauth2.service_account import Credentials
from config.settings import GOOGLE_SHEETS_ID, GOOGLE_CREDENTIALS_PATH
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_creds():
    """
    Функция для получения credentials для gspread-asyncio.
    Вызывается каждый раз при необходимости обновления токена.
    """
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH)
    scoped = creds.with_scopes([
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets'
    ])
    return scoped


class SheetsService:
    """Сервис для работы с Google Sheets (асинхронный)"""
    
    def __init__(self):
        """
        Инициализация сервиса Google Sheets.
        Создает менеджер для асинхронной работы с Google Sheets.
        """
        try:
            # Создаем AsyncioGspreadClientManager
            self.agcm = gspread_asyncio.AsyncioGspreadClientManager(get_creds)
            logger.info("SheetsService инициализирован успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации SheetsService: {e}")
            raise
    
    async def _get_worksheet(self):
        """
        Получает worksheet для работы.
        Создает новое подключение для каждой операции.
        
        Returns:
            Worksheet объект
        """
        try:
            # Получаем авторизованного клиента
            agc = await self.agcm.authorize()
            
            # Открываем таблицу по ID
            spreadsheet = await agc.open_by_key(GOOGLE_SHEETS_ID)
            
            # Получаем первый worksheet
            worksheet = await spreadsheet.get_worksheet(0)
            
            return worksheet
            
        except Exception as e:
            logger.error(f"Ошибка при получении worksheet: {e}")
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
            # Получаем worksheet
            worksheet = await self._get_worksheet()
            
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
            
            # Добавляем строку в конец таблицы (асинхронно)
            await worksheet.append_row(row, value_input_option='USER_ENTERED')
            
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
        """
        Записывает результаты сессии в Google Sheets.
        
        Args:
            session_id: ID сессии
            username: Имя пользователя
            date: Дата сессии
            scenario: Название сценария
            duration_minutes: Длительность в минутах
            message_count: Количество сообщений
            score: Оценка
            strengths: Список сильных сторон
            mistakes: Список ошибок
            recommendations: Рекомендации
        """
        try:
            # Получаем worksheet
            worksheet = await self._get_worksheet()
            
            # Проверяем заголовки на первом листе
            headers = await worksheet.row_values(1)
            if not headers or "Ссылка" not in headers:
                new_headers = ["ID Сессии", "Сотрудник", "Дата", "Сценарий", "Мин", "Сообщ", "Балл", "Плюсы", "Ошибки", "Советы", "Ссылка"]
                await worksheet.update('A1:K1', [new_headers])

            # Получаем ID листа "Диалоги" для формирования ссылки
            agc = await self.agcm.authorize()
            spreadsheet = await agc.open_by_key(GOOGLE_SHEETS_ID)
            dialogs_worksheet = await spreadsheet.worksheet("Диалоги")
            dialogs_gid = dialogs_worksheet.id
            
            # Определяем номер следующей строки
            next_row = len(await worksheet.col_values(1)) + 1

            # Формируем строку данных
            row = [
                str(session_id),
                username,
                date,
                scenario,
                str(duration_minutes),
                str(message_count),
                str(score),
                ", ".join(strengths) if strengths else "",
                ", ".join(mistakes) if mistakes else "",
                recommendations,
                f'=HYPERLINK("#gid={dialogs_gid}&range=A" & MATCH(A{next_row}; \'Диалоги\'!A:A; 0); "👁 Посмотреть")'
            ]
            
            # Примечание: Мы используем формулу MATCH для поиска ID сессии на листе 'Диалоги'
            # Добавляем строку в конец таблицы (асинхронно)
            await worksheet.append_row(row, value_input_option='USER_ENTERED')
            
            logger.info(f"Результаты сессии {session_id} успешно записаны в Google Sheets")
            
        except Exception as e:
            logger.error(f"Ошибка при записи результатов сессии {session_id} в Google Sheets: {e}")
            # Не пробрасываем исключение, чтобы не прерывать работу бота

    async def write_dialog_log(self, session_id: int, username: str, dialog_text: str):
        """
        Записывает полный текст диалога на второй лист таблицы.
        """
        try:
            agc = await self.agcm.authorize()
            spreadsheet = await agc.open_by_key(GOOGLE_SHEETS_ID)
            
            # Пытаемся получить второй лист (индекс 1), если его нет - создаем
            try:
                worksheet = await spreadsheet.get_worksheet(1)
            except Exception:
                worksheet = await spreadsheet.add_worksheet(title="Диалоги", rows="1000", cols="5")
                # Добавляем заголовки, если лист новый
                await worksheet.append_row(["ID Сессии", "Дата", "Сотрудник", "Полный диалог", "Результат"])

            # Получаем GID первого листа для обратной ссылки
            main_worksheet = await spreadsheet.get_worksheet(0)
            main_gid = main_worksheet.id
            
            # Определяем номер следующей строки на листе Диалоги
            next_row = len(await worksheet.col_values(1)) + 1

            row = [
                str(session_id),
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                username,
                dialog_text,
                f'=HYPERLINK("#gid={main_gid}&range=A" & MATCH(A{next_row}; \'{main_worksheet.title}\'!A:A; 0); "⭐ К оценке")'
            ]
            
            await worksheet.append_row(row, value_input_option='USER_ENTERED')
            logger.info(f"Лог диалога для сессии {session_id} успешно записан")
            
        except Exception as e:
            logger.error(f"Ошибка при записи лога диалога {session_id}: {e}")
