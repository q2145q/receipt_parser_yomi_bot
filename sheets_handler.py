# Файл: sheets_handler.py

from googleapiclient.discovery import build
from google_auth import get_google_credentials
from datetime import datetime
import pytz

def extract_amount_number(amount_str):
    """
    Извлекает число из строки суммы
    Например: "7 021.00 ₽" → 7021.00
    """
    if not amount_str or amount_str == "Не распознано":
        return 0
    
    try:
        # Убираем все кроме цифр, точки и запятой
        clean_str = amount_str.replace('₽', '').replace(' ', '').replace(',', '.').strip()
        # Преобразуем в float
        return float(clean_str)
    except:
        return 0

class SheetsHandler:
    def __init__(self, spreadsheet_id):
        """
        Инициализация handler для Google Sheets
        spreadsheet_id - ID таблицы
        """
        creds = get_google_credentials()
        self.service = build('sheets', 'v4', credentials=creds)
        self.spreadsheet_id = spreadsheet_id
    
    def add_receipt_data(self, data, source_link=None, source_name=None):
        """
        Добавление данных чека в таблицу
        data - словарь с полями:
        {
            'full_name': 'Фамилия И.О.',
            'amount': '7 021,00 ₽',
            'services': 'актерские услуги',
            'buyer_inn': '9705246070',
            'date': '13.08.2025',
            'status': 'Действителен / Аннулирован',
            'fns_url': 'https://...',
            'drive_link': 'https://...',
            'error_details': ''  # для ошибок
        }
        source_link - ссылка на папку анализа (если чек из папки)
        source_name - название источника (если чек из папки)
        """
        # Получаем текущее время в московском часовом поясе
        moscow_tz = pytz.timezone('Europe/Moscow')
        timestamp = datetime.now(moscow_tz).strftime('%d.%m.%Y %H:%M:%S')
        
        # Формируем значение для колонки "Источник"
        if source_link and source_name:
            # Гиперссылка: =HYPERLINK("url", "текст")
            source_value = f'=HYPERLINK("{source_link}"; "{source_name}")'
        else:
            # Обычная загрузка чека
            source_value = 'Прямая загрузка'
        
        # Формируем строку для добавления
        row = [
            data.get('date', 'Не распознано'),
            data.get('full_name', 'Не распознано'),
            data.get('buyer_inn', 'Не распознано'),
            data.get('services', 'Не распознано'),
            extract_amount_number(data.get('amount', '0')),
            data.get('status', 'Не распознано'),
            data.get('fns_url', ''),
            data.get('drive_link', ''),
            timestamp,
            source_value  # Колонка J - "Источник"
        ]
        
        # Добавляем строку в конец таблицы
        body = {
            'values': [row]
        }
        result = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range='A:J',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return result
    
    def setup_headers(self):
        """
        Установка заголовков таблицы (запускать один раз)
        """
        headers = [
            'Дата',
            'ФИО',
            'ИНН покупателя',
            'Наименование услуг',
            'Сумма',
            'Статус',
            'Ссылка ФНС',
            'Ссылка Drive',
            'Добавлено (МСК)',
            'Источник'  # НОВАЯ КОЛОНКА J
        ]
        
        body = {
            'values': [headers]
        }
        result = self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range='A1:J1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return result