from googleapiclient.discovery import build
from google_auth import get_google_credentials
from datetime import datetime
import pytz


def extract_amount_number(amount_str):
    """
    Извлекает число из строки суммы
    """
    if not amount_str or amount_str == "Не распознано":
        return 0
    
    try:
        clean_str = amount_str.replace('₽', '').replace(' ', '').replace(',', '.').strip()
        return float(clean_str)
    except:
        return 0


class AnalysisSheetHandler:
    """
    Handler для создания НОВЫХ таблиц для массового анализа
    (отличается от SheetsHandler тем, что создает новые таблицы)
    """
    
    def __init__(self):
        """
        Инициализация без spreadsheet_id - будем создавать новые таблицы
        """
        creds = get_google_credentials()
        self.service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
    
    def create_analysis_spreadsheet(self, title, folder_id):
        """
        Создание новой таблицы для анализа
        title - название таблицы
        folder_id - ID папки Drive, куда поместить таблицу
        Возвращает: (spreadsheet_id, web_link)
        """
        # Создаем таблицу
        spreadsheet = {
            'properties': {
                'title': title
            },
            'sheets': [{
                'properties': {
                    'title': 'Результаты анализа',
                    'gridProperties': {
                        'frozenRowCount': 1  # Закрепляем первую строку
                    }
                }
            }]
        }
        
        spreadsheet = self.service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()
        
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        web_link = spreadsheet.get('spreadsheetUrl')
        
        # Перемещаем таблицу в нужную папку
        file = self.drive_service.files().get(
            fileId=spreadsheet_id,
            fields='parents'
        ).execute()
        
        previous_parents = ",".join(file.get('parents'))
        self.drive_service.files().update(
            fileId=spreadsheet_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        
        # Устанавливаем заголовки
        self._setup_headers(spreadsheet_id)
        
        return spreadsheet_id, web_link
    
    def _setup_headers(self, spreadsheet_id):
        """
        Установка заголовков в новую таблицу
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
            'Ошибки обработки'
        ]
        
        body = {
            'values': [headers]
        }
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='A1:I1',
            valueInputOption='RAW',
            body=body
        ).execute()
    
    def add_receipt_to_sheet(self, spreadsheet_id, data):
        """
        Добавление данных чека в таблицу анализа
        (без timestamp - только данные чека)
        """
        row = [
            data.get('date', 'Не распознано'),
            data.get('full_name', 'Не распознано'),
            data.get('buyer_inn', 'Не распознано'),
            data.get('services', 'Не распознано'),
            extract_amount_number(data.get('amount', '0')),
            data.get('status', 'Не распознано'),
            data.get('fns_url', ''),
            data.get('drive_link', ''),
            data.get('error_details', '')
        ]
        
        body = {
            'values': [row]
        }
        result = self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A:I',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return result