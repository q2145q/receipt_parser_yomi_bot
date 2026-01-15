from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth import get_google_credentials
import os
from datetime import datetime

class DriveHandler:
    def __init__(self, root_folder_id):
        """
        Инициализация handler для Google Drive
        root_folder_id - ID корневой папки проекта
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
        file_path - путь к локальному файлу
        buyer_inn - ИНН покупателя
        receipt_date - дата чека (объект datetime)
        full_name - ФИО в формате "Фамилия И.О."
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