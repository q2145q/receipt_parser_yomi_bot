from qr_parser import extract_qr_from_image, parse_fns_url
from ocr_handler import extract_text_from_image, parse_receipt_data, validate_and_clean_data
from drive_handler import DriveHandler
from sheets_handler import SheetsHandler
import os
from dotenv import load_dotenv

load_dotenv()

class ReceiptProcessor:
    def __init__(self, user_folder_id=None, user_sheet_id=None):
        """
        Инициализация процессора чеков
        
        user_folder_id - ID папки пользователя на Drive
        user_sheet_id - ID таблицы пользователя в Sheets
        
        Если не указаны - используются значения из .env (старое поведение)
        """
        if user_folder_id and user_sheet_id:
            # Новое поведение - используем структуру пользователя
            self.drive = DriveHandler(user_folder_id)
            self.sheets = SheetsHandler(user_sheet_id)
        else:
            # Старое поведение - для обратной совместимости
            self.drive = DriveHandler(os.getenv('GOOGLE_DRIVE_FOLDER_ID'))
            self.sheets = SheetsHandler(os.getenv('GOOGLE_SHEET_ID'))

    def process_receipt_image(self, image_path):
        """
        Обработка чека из изображения через OpenAI Vision
        """
        try:
            from openai_vision import OpenAIVisionParser
            
            # 1. Парсинг QR-кода для получения URL
            qr_url = extract_qr_from_image(image_path)
            qr_data = parse_fns_url(qr_url) if qr_url else {}
            
            # 2. Парсинг данных через OpenAI Vision
            vision_parser = OpenAIVisionParser()
            success, receipt_data, message = vision_parser.parse_receipt(image_path)
            
            if not success:
                return False, receipt_data, message
            
            # 3. Добавляем URL из QR в данные
            if qr_data:
                receipt_data['fns_url'] = qr_data.get('fns_url', '')
            
            # 4. Валидация (теперь всегда возвращает True)
            is_valid, error_details = validate_and_clean_data(receipt_data)

            # Добавляем информацию об ошибках в данные
            receipt_data['error_details'] = error_details

            return True, receipt_data, "OK"
            
        except Exception as e:
            return False, {}, f"Ошибка обработки: {str(e)}"

    def upload_and_save(self, image_path, receipt_data, source_link=None, source_name=None):
        """
        Загрузка чека на Drive и сохранение в Sheets
        
        source_link - ссылка на папку анализа (если чек из папки)
        source_name - название источника (если чек из папки)
        
        Возвращает: (success, result_message)
        """
        try:
            # 1. Загружаем файл на Drive
            drive_result = self.drive.upload_file(
                file_path=image_path,
                buyer_inn=receipt_data['buyer_inn'],
                receipt_date=receipt_data['date_obj'],
                full_name=receipt_data['full_name']
            )
            
            # 2. Добавляем ссылку на Drive в данные
            receipt_data['drive_link'] = drive_result['web_link']
            
            # 3. Сохраняем в Google Sheets (с информацией об источнике)
            self.sheets.add_receipt_data(receipt_data, source_link, source_name)
            
            result_message = f"""
✅ Чек успешно обработан!

📁 Файл: {drive_result['filename']}
📂 Папка: {drive_result['folder_path']}
🔗 Drive: {drive_result['web_link']}
📊 Добавлено в таблицу
"""
            return True, result_message
            
        except Exception as e:
            return False, f"Ошибка при сохранении: {str(e)}"
    
    def add_to_user_sheet(self, receipt_data, source_link=None, source_name=None):
        """
        Добавление записи в корневую таблицу пользователя
        (используется при анализе папки для дублирования записей)
        
        receipt_data - данные чека
        source_link - ссылка на папку анализа
        source_name - название источника
        """
        try:
            self.sheets.add_receipt_data(receipt_data, source_link, source_name)
            return True
        except Exception as e:
            return False