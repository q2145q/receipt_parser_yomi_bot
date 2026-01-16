from googleapiclient.discovery import build
from google_auth import get_google_credentials
import os
from dotenv import load_dotenv

load_dotenv()


class UserManager:
    """
    Управление структурой папок и таблиц для каждого пользователя
    """
    
    def __init__(self):
        """
        Инициализация сервисов Google Drive и Sheets
        """
        creds = get_google_credentials()
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.root_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    def get_chat_name(self, chat_id, username=None, chat_title=None):
        """
        Получение имени для папки/таблицы
        chat_id - ID чата
        username - username пользователя (для личных чатов)
        chat_title - название чата (для групповых чатов)
        
        Возвращает: строку типа "@username" или "Название чата"
        """
        if chat_title:
            # Групповой чат
            return chat_title
        elif username:
            # Личный чат с username
            return f"@{username}"
        else:
            # Личный чат без username
            return f"user_{chat_id}"
    
    def get_or_create_user_structure(self, chat_id, chat_name):
        """
        Получение или создание структуры папок и таблиц для пользователя
        
        Возвращает: {
            'user_folder_id': 'xxx',
            'user_folder_link': 'https://...',
            'user_sheet_id': 'xxx',
            'user_sheet_link': 'https://...'
        }
        """
        # Ищем существующую папку пользователя
        folder_name = chat_name
        user_folder_id = self._find_user_folder(folder_name)
        
        if not user_folder_id:
            # Создаем новую папку
            user_folder_id = self._create_user_folder(folder_name)
        
        # Получаем ссылку на папку
        user_folder_link = self._get_folder_link(user_folder_id)
        
        # Ищем или создаем корневую таблицу
        sheet_name = f"{chat_name} - Реестр чеков"
        user_sheet_id = self._find_user_sheet(user_folder_id, sheet_name)
        
        if not user_sheet_id:
            # Создаем новую таблицу
            user_sheet_id = self._create_user_sheet(sheet_name, user_folder_id)
        
        # Получаем ссылку на таблицу
        user_sheet_link = self._get_sheet_link(user_sheet_id)
        
        return {
            'user_folder_id': user_folder_id,
            'user_folder_link': user_folder_link,
            'user_sheet_id': user_sheet_id,
            'user_sheet_link': user_sheet_link
        }
    
    def _find_user_folder(self, folder_name):
        """
        Поиск папки пользователя по имени
        Возвращает folder_id или None
        """
        query = f"name='{folder_name}' and '{self.root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        return folders[0]['id'] if folders else None
    
    def _create_user_folder(self, folder_name):
        """
        Создание папки пользователя
        Возвращает folder_id
        """
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [self.root_folder_id]
        }
        folder = self.drive_service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id')
    
    def _get_folder_link(self, folder_id):
        """
        Получение ссылки на папку
        """
        file = self.drive_service.files().get(
            fileId=folder_id,
            fields='webViewLink'
        ).execute()
        
        return file.get('webViewLink')
    
    def _find_user_sheet(self, folder_id, sheet_name):
        """
        Поиск таблицы пользователя по имени в его папке
        Возвращает sheet_id или None
        """
        query = f"name='{sheet_name}' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        
        sheets = results.get('files', [])
        return sheets[0]['id'] if sheets else None
    
    def _create_user_sheet(self, sheet_name, folder_id):
        """
        Создание корневой таблицы для пользователя
        Возвращает sheet_id
        """
        # Создаем таблицу
        spreadsheet = {
            'properties': {
                'title': sheet_name
            },
            'sheets': [{
                'properties': {
                    'title': 'Чеки',
                    'gridProperties': {
                        'frozenRowCount': 1
                    }
                }
            }]
        }
        
        spreadsheet = self.sheets_service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId'
        ).execute()
        
        sheet_id = spreadsheet.get('spreadsheetId')
        
        # Перемещаем таблицу в папку пользователя
        file = self.drive_service.files().get(
            fileId=sheet_id,
            fields='parents'
        ).execute()
        
        previous_parents = ",".join(file.get('parents'))
        self.drive_service.files().update(
            fileId=sheet_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        
        # Устанавливаем заголовки
        self._setup_user_sheet_headers(sheet_id)
        
        return sheet_id
    
    def _setup_user_sheet_headers(self, sheet_id):
        """
        Установка заголовков в корневую таблицу пользователя
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
            'Источник'  # НОВАЯ КОЛОНКА - с гиперссылкой на папку анализа
        ]
        
        body = {
            'values': [headers]
        }
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='A1:J1',
            valueInputOption='RAW',
            body=body
        ).execute()
    
    def _get_sheet_link(self, sheet_id):
        """
        Получение ссылки на таблицу
        """
        file = self.drive_service.files().get(
            fileId=sheet_id,
            fields='webViewLink'
        ).execute()
        
        return file.get('webViewLink')
