from openai import OpenAI
import base64
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class OpenAIVisionParser:
    def __init__(self):
        """
        Инициализация OpenAI клиента
        """
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def encode_image(self, image_path):
        """
        Кодирование изображения в base64
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def parse_receipt(self, image_path):
        """
        Парсинг чека через GPT-4o-mini Vision
        Возвращает словарь с данными чека
        """
        try:
            # Кодируем изображение
            base64_image = self.encode_image(image_path)
            
            # Промпт для извлечения данных
            prompt = """
Проанализируй этот чек самозанятого и извлеки следующие данные в формате JSON:

{
  "full_name": "Фамилия И.О. (например: Сабатаров А.Г.)",
  "amount": "Сумма с символом ₽ (например: 7 021.00 ₽)",
  "services": "Наименование услуг (например: актерские услуги)",
  "seller_inn": "ИНН продавца (12 цифр)",
  "buyer_inn": "ИНН покупателя (10 или 12 цифр)",
  "date": "Дата в формате dd.mm.yyyy",
  "status": "Действителен"
}

ВАЖНО:
- Сумму бери из строки с наименованием услуги, НЕ из строки "Итого"
- ИНН продавца идет ПЕРВЫМ (после "ЧЕК")
- ИНН покупателя идет ВТОРЫМ (после "Покупатель")
- Верни ТОЛЬКО JSON, без дополнительного текста
"""
            
            # Запрос к OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0  # Для точности
            )
            
            # Извлекаем JSON из ответа
            content = response.choices[0].message.content.strip()
            
            # Убираем возможные markdown блоки
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            # Парсим JSON
            data = json.loads(content.strip())
            
            # Добавляем объект даты для Drive
            try:
                data['date_obj'] = datetime.strptime(data['date'], '%d.%m.%Y')
            except:
                data['date_obj'] = datetime.now()
            
            return True, data, "OK"
            
        except json.JSONDecodeError as e:
            return False, {}, f"Ошибка парсинга JSON: {str(e)}"
        except Exception as e:
            return False, {}, f"Ошибка OpenAI: {str(e)}"