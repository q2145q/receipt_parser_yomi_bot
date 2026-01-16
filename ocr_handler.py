import pytesseract
from PIL import Image
import re
from datetime import datetime

def extract_text_from_image(image_path):
    """
    Извлечение текста из изображения через OCR
    """
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='rus')
        return text
    except Exception as e:
        print(f"Ошибка OCR: {e}")
        return ""

def parse_receipt_data(ocr_text):
    """
    Извлечение структурированных данных из текста чека
    Возвращает словарь с данными чека
    """
    data = {}
    
    # ФИО (паттерн: Фамилия Имя Отчество)
    fio_match = re.search(r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)', ocr_text)
    if fio_match:
        surname = fio_match.group(1)
        name = fio_match.group(2)
        patronymic = fio_match.group(3)
        data['full_name'] = f"{surname} {name[0]}.{patronymic[0]}."
    
    # Сумма (ищем "Итого" с цифрами)
    # Паттерны: "Итого 7 021,00", "Итого 7021,00 Р"
    amount_patterns = [
        r'Итого\s*([\d\s]+[,.]?\d*)\s*[₽Р]',
        r'Итого\s*([\d\s]+[,.]?\d*)',
        r'Сумма[:\s]*([\d\s]+[,.]?\d*)\s*[₽Р]'
    ]
    
    for pattern in amount_patterns:
        amount_match = re.search(pattern, ocr_text)
        if amount_match:
            # Очищаем от пробелов и заменяем запятую на точку
            raw_amount = amount_match.group(1).strip()
            cleaned_amount = raw_amount.replace(' ', '').replace(',', '.')
            # Форматируем с пробелом как разделитель тысяч
            try:
                amount_float = float(cleaned_amount)
                data['amount'] = f"{amount_float:,.2f} ₽".replace(',', ' ')
            except:
                data['amount'] = raw_amount + " ₽"
            break
    
    # ИНН (12 или 10 цифр)
    inn_matches = re.findall(r'\b(\d{12}|\d{10})\b', ocr_text)
    if inn_matches:
        # Первый ИНН обычно продавца, второй - покупателя
        data['seller_inn'] = inn_matches[0]
        if len(inn_matches) > 1:
            data['buyer_inn'] = inn_matches[1]
        else:
            # Пытаемся найти ИНН покупателя после слова "Покупатель"
            buyer_pattern = r'Покупатель.*?(\d{12}|\d{10})'
            buyer_match = re.search(buyer_pattern, ocr_text, re.DOTALL)
            if buyer_match:
                data['buyer_inn'] = buyer_match.group(1)
    
    # Дата (dd.mm.yyyy)
    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', ocr_text)
    if date_match:
        data['date'] = date_match.group(1)
        # Конвертируем в объект datetime для Drive
        try:
            data['date_obj'] = datetime.strptime(data['date'], '%d.%m.%Y')
        except:
            data['date_obj'] = datetime.now()
    
    # Наименование услуг
    # Паттерн: после "Наименование услуг" или просто строка с услугой
    service_patterns = [
        r'1\s+([а-яё\s]+)\s+[\d\s,]+',  # "1 актерские услуги 7021"
        r'услуг[и]?\s+([а-яё\s]+)',      # "услуги актерские"
    ]
    
    for pattern in service_patterns:
        service_match = re.search(pattern, ocr_text, re.IGNORECASE)
        if service_match:
            data['services'] = service_match.group(1).strip()
            break
    
    # Статус (по умолчанию "Действителен", проверка аннулирования требует API)
    data['status'] = 'Действителен'
    
    return data

def validate_and_clean_data(data):
    """
    Проверка и очистка данных
    Теперь НЕ отклоняет чек, а собирает список ошибок
    Возвращает (True, список_ошибок)
    """
    errors = []
    required_fields = ['full_name', 'amount', 'buyer_inn', 'date']
    
    # Проверяем наличие обязательных полей
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Не найдено: {field}")
            # Добавляем значение по умолчанию
            data[field] = "Не распознано"
    
    # Проверка формата ИНН (только если поле заполнено)
    if data.get('buyer_inn') and data['buyer_inn'] != "Не распознано":
        if not re.match(r'^\d{10}$|^\d{12}$', data['buyer_inn']):
            errors.append("Некорректный формат ИНН покупателя")
    
    # Формируем текст ошибок
    error_text = "; ".join(errors) if errors else ""
    
    # Всегда возвращаем True - чек сохраняется в любом случае
    return True, error_text