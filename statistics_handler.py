from googleapiclient.discovery import build
from google_auth import get_google_credentials
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

load_dotenv()


class StatisticsHandler:
    """
    Handler для сбора статистики использования бота
    """
    
    def __init__(self):
        """
        Инициализация. Использует ID таблицы из .env
        """
        creds = get_google_credentials()
        self.service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        
        # ID таблицы статистики (нужно будет добавить в .env)
        self.spreadsheet_id = os.getenv('STATISTICS_SHEET_ID')
        
        if not self.spreadsheet_id:
            raise ValueError("STATISTICS_SHEET_ID не найден в .env")
    
    def _get_moscow_time(self):
        """Получение текущего времени в МСК"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        return datetime.now(moscow_tz).strftime('%d.%m.%Y %H:%M:%S')
    
    def log_action(self, user_id, username, action, result, details=""):
        """
        Логирование действия пользователя
        
        user_id - Telegram ID пользователя
        username - username пользователя
        action - тип действия (/start, обработка чека, /full_analyze и т.д.)
        result - успех/ошибка
        details - дополнительная информация
        """
        try:
            row = [
                self._get_moscow_time(),
                str(user_id),
                username or "Без username",
                action,
                result,
                details
            ]
            
            body = {'values': [row]}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Лог действий!A:F',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
        except Exception as e:
            print(f"Ошибка логирования: {e}")
    
    def update_user_stats(self, user_id, username, action_type, success=True):
        """
        Обновление статистики пользователя
        
        user_id - Telegram ID
        username - username
        action_type - тип действия ('receipt' или 'folder_analysis')
        success - успешно ли выполнено
        """
        try:
            # Получаем текущие данные пользователя
            user_data = self._get_user_data(user_id)
            
            if user_data:
                # Пользователь уже есть - обновляем
                self._update_existing_user(user_id, user_data, action_type, success)
            else:
                # Новый пользователь - добавляем
                self._add_new_user(user_id, username, action_type, success)
        except Exception as e:
            print(f"Ошибка обновления статистики: {e}")
    
    def _get_user_data(self, user_id):
        """Получение данных пользователя из таблицы"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Статистика пользователей!A:H'
            ).execute()
            
            values = result.get('values', [])
            
            # Ищем пользователя (пропускаем заголовок)
            for idx, row in enumerate(values[1:], start=2):
                if len(row) > 0 and row[0] == str(user_id):
                    return {
                        'row_index': idx,
                        'user_id': row[0],
                        'username': row[1] if len(row) > 1 else '',
                        'first_use': row[2] if len(row) > 2 else '',
                        'last_use': row[3] if len(row) > 3 else '',
                        'total_receipts': int(row[4]) if len(row) > 4 and row[4] else 0,
                        'success_receipts': int(row[5]) if len(row) > 5 and row[5] else 0,
                        'error_receipts': int(row[6]) if len(row) > 6 and row[6] else 0,
                        'days_active': int(row[7]) if len(row) > 7 and row[7] else 0
                    }
            return None
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            return None
    
    def _calculate_days_active(self, first_use_str, last_use_str):
        """
        Вычисление количества дней между первым и последним использованием
        """
        try:
            first_use = datetime.strptime(first_use_str, '%d.%m.%Y %H:%M:%S')
            last_use = datetime.strptime(last_use_str, '%d.%m.%Y %H:%M:%S')
            delta = last_use - first_use
            return delta.days
        except:
            return 0
    
    def _update_existing_user(self, user_id, user_data, action_type, success):
        """Обновление существующего пользователя"""
        current_time = self._get_moscow_time()
        
        # Обновляем счетчики
        total = user_data['total_receipts'] + 1
        success_count = user_data['success_receipts'] + (1 if success else 0)
        error_count = user_data['error_receipts'] + (0 if success else 1)
        
        # Вычисляем количество дней
        days_active = self._calculate_days_active(user_data['first_use'], current_time)
        
        # Обновляем строку
        row = [
            str(user_id),
            user_data['username'],
            user_data['first_use'],
            current_time,
            total,
            success_count,
            error_count,
            days_active
        ]
        
        body = {'values': [row]}
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f'Статистика пользователей!A{user_data["row_index"]}:H{user_data["row_index"]}',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
    
    def _add_new_user(self, user_id, username, action_type, success):
        """Добавление нового пользователя"""
        current_time = self._get_moscow_time()
        
        row = [
            str(user_id),
            username or "Без username",
            current_time,  # Первое использование
            current_time,  # Последнее использование
            1,  # Всего чеков
            1 if success else 0,  # Успешно
            0 if success else 1,  # Ошибок
            0  # Дней активен (0 для нового пользователя)
        ]
        
        body = {'values': [row]}
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range='Статистика пользователей!A:H',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
    
    def setup_statistics_sheets(self):
        """
        Установка заголовков для таблиц статистики
        Запускать один раз при первой настройке
        """
        # Заголовки для "Статистика пользователей"
        users_headers = [
            'User ID',
            'Username',
            'Первое использование',
            'Последнее использование',
            'Всего чеков',
            'Успешно',
            'Ошибок',
            'Дней активен'
        ]
        
        # Заголовки для "Лог действий"
        log_headers = [
            'Timestamp (МСК)',
            'User ID',
            'Username',
            'Действие',
            'Результат',
            'Детали'
        ]
        
        # Создаем/обновляем листы
        try:
            # Лист "Статистика пользователей"
            body = {'values': [users_headers]}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Статистика пользователей!A1:H1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Лист "Лог действий"
            body = {'values': [log_headers]}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Лог действий!A1:F1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print("✅ Заголовки статистики установлены!")
        except Exception as e:
            print(f"❌ Ошибка установки заголовков: {e}")