from googleapiclient.discovery import build
from google_auth import get_google_credentials

class SheetsHandler:
    def __init__(self, spreadsheet_id):
        """
        Инициализация handler для Google Sheets
        spreadsheet_id - ID таблицы
        """
        creds = get_google_credentials()
        self.service = build('sheets', 'v4', credentials=creds)
        self.spreadsheet_id = spreadsheet_id
    
    def add_receipt_data(self, data):
        """
        Добавление данных чека в таблицу
        data - словарь с полями:
        {
            'full_name': 'Фамилия И.О.',
            'amount': '7 021,00',
            'services': 'актерские услуги',
            'buyer_inn': '9705246070',
            'date': '13.08.2025',
            'status': 'Действителен / Аннулирован',
            'fns_link': 'https://...',
            'drive_link': 'https://...'
        }
        """
        # Формируем строку для добавления
        row = [
            data.get('date', ''),
            data.get('full_name', ''),
            data.get('buyer_inn', ''),
            data.get('services', ''),
            data.get('amount', ''),
            data.get('status', ''),
            data.get('fns_link', ''),
            data.get('drive_link', '')
        ]
        
        # Добавляем строку в конец таблицы
        body = {
            'values': [row]
        }
        result = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range='A:H',  # Колонки A-H
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
            'Ссылка Drive'
        ]
        
        body = {
            'values': [headers]
        }
        result = self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range='A1:H1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return result