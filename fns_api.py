import requests
from datetime import datetime

def get_receipt_data_from_fns(qr_url):
    """
    Получение данных чека из API ФНС по ссылке из QR-кода
    Возвращает словарь с данными чека
    """
    try:
        from qr_parser import extract_receipt_id_from_url
        
        # Извлекаем параметры из URL
        params = extract_receipt_id_from_url(qr_url)
        if not params or not params['receipt_id']:
            return None
        
        # Формируем запрос к API ФНС
        # URL для проверки чека самозанятого
        api_url = f"https://npd.nalog.ru/api/v1/receipt/{params['inn']}/{params['receipt_id']}"
        
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Парсим данные
            receipt_info = {
                'full_name': format_full_name(data.get('sellerName', '')),
                'amount': f"{data.get('totalAmount', 0):,.2f} ₽".replace(',', ' '),
                'services': ', '.join([item.get('name', '') for item in data.get('items', [])]),
                'seller_inn': data.get('inn', ''),
                'buyer_inn': params.get('inn', ''),
                'date': parse_date(data.get('receiptDate', '')),
                'status': 'Аннулирован' if data.get('canceled', False) else 'Действителен',
                'fns_link': qr_url,
                'receipt_id': params['receipt_id']
            }
            
            return receipt_info
        else:
            print(f"Ошибка API ФНС: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Ошибка получения данных из ФНС: {e}")
        return None

def format_full_name(full_name):
    """
    Форматирование ФИО в формат "Фамилия И.О."
    Пример: "Сабатаров Андрей Георгиевич" -> "Сабатаров А.Г."
    """
    try:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            surname = parts[0]
            initials = ''.join([p[0] + '.' for p in parts[1:]])
            return f"{surname} {initials}"
        return full_name
    except:
        return full_name

def parse_date(date_str):
    """
    Парсинг даты в формат dd.mm.yyyy
    """
    try:
        # API может возвращать разные форматы
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d.%m.%Y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%d.%m.%Y')
            except:
                continue
        return date_str
    except:
        return date_str