from pyzbar.pyzbar import decode
from PIL import Image
import cv2
import re

def extract_qr_from_image(image_path):
    """
    Извлечение URL из QR-кода на изображении
    Возвращает URL или None
    """
    try:
        # Пробуем через PIL
        img = Image.open(image_path)
        decoded_objects = decode(img)
        
        if decoded_objects:
            qr_data = decoded_objects[0].data.decode('utf-8')
            return qr_data
        
        # Если не получилось, пробуем через OpenCV с улучшением
        img_cv = cv2.imread(image_path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        
        decoded_objects = decode(gray)
        if decoded_objects:
            qr_data = decoded_objects[0].data.decode('utf-8')
            return qr_data
        
        return None
        
    except Exception as e:
        print(f"Ошибка при чтении QR: {e}")
        return None

def parse_fns_url(url):
    """
    Парсинг URL ФНС для извлечения параметров чека
    Формат: https://lknpd.nalog.ru/api/v1/receipt/{INN}/{receipt_id}/print
    Возвращает словарь с данными или None
    """
    try:
        # Паттерн для URL из QR
        pattern = r'https://lknpd\.nalog\.ru/api/v1/receipt/(\d+)/([a-zA-Z0-9]+)'
        match = re.search(pattern, url)
        
        if match:
            return {
                'seller_inn': match.group(1),
                'receipt_id': match.group(2),
                'fns_url': url
            }
        
        return None
        
    except Exception as e:
        print(f"Ошибка парсинга URL: {e}")
        return None