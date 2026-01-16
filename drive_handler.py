from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth import get_google_credentials
import os
from datetime import datetime

class DriveHandler:
    def __init__(self, root_folder_id):
        """
        Инициализация handler для Google Drive
        root_folder_id - ID корневой папки проекта (или папки пользователя)
        """
        creds = get_google_credentials()
        self.service = build('drive', 'v3', credentials=creds)
        self.root_folder_id = root_folder_id
    
    def get_or_create_folder(self, folder_name, parent_id):
        """
        Получить ID папки или создать новую
        folder_name - название папки
        parent_id - ID родительской папки
        """
        # Ищем существующую папку
        query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        
        if folders:
            return folders[0]['id']
        
        # Создаем новую папку
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = self.service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')
    
    def upload_file(self, file_path, buyer_inn, receipt_date, full_name):
        """
        Загрузка файла на Drive с правильной структурой
        ВНИМАНИЕ: root_folder_id теперь это папка пользователя!
        
        file_path - путь к локальному файлу
        buyer_inn - ИНН покупателя
        receipt_date - дата чека (объект datetime)
        full_name - ФИО в формате "Фамилия И.О."
        
        Структура внутри папки пользователя:
        Папка пользователя (@username)
        ├── 9705246070 (ИНН)
        │   └── 08-2025 (месяц-год)
        │       └── Фамилия И.О. 13.08.2025.jpg
        """
        # Создаем структуру папок: ИНН / месяц-год
        inn_folder_id = self.get_or_create_folder(buyer_inn, self.root_folder_id)
        month_folder_name = receipt_date.strftime("%m-%Y")  # например: 08-2025
        month_folder_id = self.get_or_create_folder(month_folder_name, inn_folder_id)
        
        # Формируем название файла: Фамилия И.О. дата
        date_str = receipt_date.strftime("%d.%m.%Y")
        file_extension = os.path.splitext(file_path)[1]
        new_filename = f"{full_name} {date_str}{file_extension}"
        
        # Загружаем файл
        file_metadata = {
            'name': new_filename,
            'parents': [month_folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return {
            'file_id': file.get('id'),
            'web_link': file.get('webViewLink'),
            'filename': new_filename,
            'folder_path': f"{buyer_inn}/{month_folder_name}"
        }
    
    def create_analysis_folder(self, folder_name):
        """
        Создание папки для массового анализа ВНУТРИ папки пользователя
        folder_name - название папки (например: "@username 2026-01-16 10-30")
        Возвращает: (folder_id, web_link)
        """
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [self.root_folder_id]  # root_folder_id = папка пользователя
        }
        folder = self.service.files().create(
            body=folder_metadata,
            fields='id, webViewLink'
        ).execute()
        
        return folder.get('id'), folder.get('webViewLink')

    def list_files_in_folder(self, folder_id):
        """
        Получение списка всех файлов из папки
        Возвращает список файлов: [{'id': '...', 'name': '...', 'mimeType': '...'}, ...]
        """
        import logging
        logger = logging.getLogger(__name__)
        
        query = f"'{folder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.folder'"
        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=1000
        ).execute()
        
        files = results.get('files', [])
        
        logger.info(f"Всего файлов в папке: {len(files)}")
        for f in files:
            logger.info(f"Файл: {f['name']}, тип: {f['mimeType']}")
        
        # Фильтруем только изображения и PDF (расширенный список)
        allowed_types = [
            'image/jpeg',
            'image/png', 
            'image/jpg',
            'application/pdf',
            'image/heic',  # iPhone фото
            'image/heif',  # iPhone фото
            'image/webp'   # Веб-формат
        ]
        
        filtered = [f for f in files if f['mimeType'] in allowed_types]
        
        logger.info(f"Файлов после фильтрации: {len(filtered)}")
        
        return filtered

    def download_file(self, file_id, destination_path):
        """
        Скачивание файла с Drive
        file_id - ID файла на Drive
        destination_path - путь для сохранения
        """
        request = self.service.files().get_media(fileId=file_id)
        
        with open(destination_path, 'wb') as f:
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()