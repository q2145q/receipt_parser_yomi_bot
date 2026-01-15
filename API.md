# API Reference - Receipt Parser Yomi Bot

## Table of Contents
- [Bot Module (`bot.py`)](#bot-module)
- [Receipt Processor (`receipt_processor.py`)](#receipt-processor)
- [OpenAI Vision Parser (`openai_vision.py`)](#openai-vision-parser)
- [QR Parser (`qr_parser.py`)](#qr-parser)
- [OCR Handler (`ocr_handler.py`)](#ocr-handler)
- [Drive Handler (`drive_handler.py`)](#drive-handler)
- [Sheets Handler (`sheets_handler.py`)](#sheets-handler)
- [Google Auth (`google_auth.py`)](#google-auth)
- [Data Structures](#data-structures)

---

## Bot Module

### `async start(update: Update, context: ContextTypes.DEFAULT_TYPE)`
Обработчик команды `/start`.

**Параметры:**
- `update`: Telegram Update объект
- `context`: Контекст бота

**Возвращает:** None

**Описание:** Отправляет приветственное сообщение с инструкциями.

---

### `async handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE)`
Обработчик фотографий чеков.

**Параметры:**
- `update`: Telegram Update объект
- `context`: Контекст бота

**Возвращает:** None

**Описание:**
- Определяет, является ли фото частью альбома (media_group)
- Для одиночных фото вызывает `process_single_photo()`
- Для альбомов группирует фото и запускает отложенную обработку

**Workflow:**
1. Получение фото из сообщения
2. Проверка на media_group_id
3. Группировка или немедленная обработка

---

### `async process_single_photo(update: Update, photo)`
Обработка одного фото чека.

**Параметры:**
- `update`: Telegram Update объект
- `photo`: Telegram PhotoSize объект

**Возвращает:** None

**Описание:**
1. Скачивает фото во временный файл
2. Вызывает `processor.process_receipt_image()`
3. Сохраняет данные в `pending_receipts`
4. Отображает данные с кнопками подтверждения

**Обработка ошибок:**
- Удаляет временный файл при ошибке
- Отправляет сообщение об ошибке пользователю

---

### `async process_media_group_delayed(context, media_group_id, chat_id)`
Отложенная обработка альбома фотографий.

**Параметры:**
- `context`: Контекст бота
- `media_group_id`: ID группы медиа
- `chat_id`: ID чата для отправки результатов

**Возвращает:** None

**Описание:**
1. Ждет 2 секунды для сбора всех фото
2. Обрабатывает каждое фото
3. Автоматически загружает на Drive и в Sheets
4. Отправляет сводный отчет

**Формат отчета:**
```
✅ Обработано чеков: X/Y

📋 Успешно загружены:
1. ФИО - Сумма (Дата)
...

❌ Ошибки (N):
• Чек X: описание ошибки
```

---

### `async handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE)`
Обработчик PDF документов.

**Параметры:**
- `update`: Telegram Update объект
- `context`: Контекст бота

**Возвращает:** None

**Описание:**
1. Проверяет, что документ - PDF
2. Скачивает файл
3. Конвертирует первую страницу в JPG через `pdf2image`
4. Обрабатывает как изображение
5. Сохраняет оригинальный PDF (не JPG) для загрузки

---

### `async handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE)`
Обработчик текстовых сообщений.

**Параметры:**
- `update`: Telegram Update объект
- `context`: Контекст бота

**Возвращает:** None

**Описание:**
- Распознает ссылки на чеки ФНС
- Парсит URL через `parse_fns_url()`
- Информирует, что для полной обработки нужно фото

---

### `async button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE)`
Обработчик нажатий на inline-кнопки.

**Параметры:**
- `update`: Telegram Update объект
- `context`: Контекст бота

**Возвращает:** None

**Callback Data:**
- `confirm` - подтверждение и загрузка
- `edit` - отмена с предложением отправить заново
- `cancel` - полная отмена

---

### `format_receipt_data(data: dict) -> str`
Форматирование данных чека для отображения.

**Параметры:**
- `data`: Словарь с данными чека

**Возвращает:** Отформатированная строка в Markdown

**Формат вывода:**
```markdown
📋 **Распознанные данные:**

👤 ФИО: `{full_name}`
💰 Сумма: `{amount}`
📝 Услуги: `{services}`
🏢 ИНН покупателя: `{buyer_inn}`
📅 Дата: `{date}`
✅ Статус: `{status}`
🔗 [Ссылка ФНС]({fns_url})

Все верно?
```

---

## Receipt Processor

### `class ReceiptProcessor`

#### `__init__()`
Инициализация процессора чеков.

**Создает:**
- `self.drive`: DriveHandler
- `self.sheets`: SheetsHandler

---

#### `process_receipt_image(image_path: str) -> tuple[bool, dict, str]`
Полная обработка чека из изображения.

**Параметры:**
- `image_path`: Путь к файлу изображения

**Возвращает:**
- `success` (bool): True если успешно
- `data` (dict): Словарь с данными чека
- `message` (str): Сообщение об ошибке или "OK"

**Процесс:**
1. Извлечение QR-кода через `extract_qr_from_image()`
2. Парсинг URL ФНС через `parse_fns_url()`
3. Извлечение данных через OpenAI Vision
4. Добавление URL из QR в данные
5. Валидация через `validate_and_clean_data()`

**Пример использования:**
```python
processor = ReceiptProcessor()
success, data, message = processor.process_receipt_image('receipt.jpg')
if success:
    print(data)
else:
    print(f"Error: {message}")
```

---

#### `upload_and_save(image_path: str, receipt_data: dict) -> tuple[bool, str]`
Загрузка чека на Drive и сохранение в Sheets.

**Параметры:**
- `image_path`: Путь к файлу для загрузки
- `receipt_data`: Словарь с данными чека

**Возвращает:**
- `success` (bool): True если успешно
- `result_message` (str): Сообщение с результатом

**Процесс:**
1. Загрузка файла через `drive.upload_file()`
2. Добавление ссылки на Drive в `receipt_data`
3. Сохранение в Sheets через `sheets.add_receipt_data()`

**Пример результата:**
```
✅ Чек успешно обработан!

📁 Файл: Сабатаров А.Г. 13.08.2025.jpg
📂 Папка: 9705246070/08-2025
🔗 Drive: https://drive.google.com/...
📊 Добавлено в таблицу
```

---

## OpenAI Vision Parser

### `class OpenAIVisionParser`

#### `__init__()`
Инициализация OpenAI клиента.

**Требует:** `OPENAI_API_KEY` в переменных окружения

---

#### `encode_image(image_path: str) -> str`
Кодирование изображения в base64.

**Параметры:**
- `image_path`: Путь к изображению

**Возвращает:** Base64-кодированная строка

---

#### `parse_receipt(image_path: str) -> tuple[bool, dict, str]`
Парсинг чека через GPT-4o-mini Vision.

**Параметры:**
- `image_path`: Путь к изображению чека

**Возвращает:**
- `success` (bool): True если успешно
- `data` (dict): Извлеченные данные
- `message` (str): "OK" или описание ошибки

**Модель:** `gpt-4o-mini`

**Параметры запроса:**
- `max_tokens`: 500
- `temperature`: 0 (для точности)

**Извлекаемые поля:**
```json
{
  "full_name": "Фамилия И.О.",
  "amount": "7 021.00 ₽",
  "services": "актерские услуги",
  "seller_inn": "123456789012",
  "buyer_inn": "9705246070",
  "date": "13.08.2025",
  "status": "Действителен",
  "date_obj": datetime
}
```

**Обработка ошибок:**
- JSONDecodeError: если ответ не валидный JSON
- Exception: общие ошибки OpenAI API

---

## QR Parser

### `extract_qr_from_image(image_path: str) -> str | None`
Извлечение URL из QR-кода на изображении.

**Параметры:**
- `image_path`: Путь к изображению

**Возвращает:** URL строка или None

**Методы:**
1. Декодирование через PIL + pyzbar
2. Если не сработало: улучшение через OpenCV + декодирование

**OpenCV обработка:**
- Конвертация в grayscale
- Эквализация гистограммы (`cv2.equalizeHist`)

---

### `parse_fns_url(url: str) -> dict | None`
Парсинг URL ФНС для извлечения параметров.

**Параметры:**
- `url`: URL чека ФНС

**Возвращает:** Словарь с данными или None

**Формат URL:**
```
https://lknpd.nalog.ru/api/v1/receipt/{INN}/{receipt_id}/print
```

**Результат:**
```python
{
    'seller_inn': '123456789012',
    'receipt_id': 'abc123xyz',
    'fns_url': 'https://lknpd.nalog.ru/...'
}
```

**Regex паттерн:**
```python
r'https://lknpd\.nalog\.ru/api/v1/receipt/(\d+)/([a-zA-Z0-9]+)'
```

---

## OCR Handler

### `extract_text_from_image(image_path: str) -> str`
Извлечение текста через OCR (Tesseract).

**Параметры:**
- `image_path`: Путь к изображению

**Возвращает:** Извлеченный текст

**Язык:** `rus` (русский)

**Примечание:** В текущей версии используется резервно, основной метод - OpenAI Vision.

---

### `parse_receipt_data(ocr_text: str) -> dict`
Извлечение структурированных данных из OCR текста.

**Параметры:**
- `ocr_text`: Текст, извлеченный через OCR

**Возвращает:** Словарь с данными

**Regex паттерны:**
- ФИО: `([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)`
- Сумма: `Итого\s*([\d\s]+[,.]?\d*)\s*[₽Р]`
- ИНН: `\b(\d{12}|\d{10})\b`
- Дата: `(\d{2}\.\d{2}\.\d{4})`
- Услуги: `1\s+([а-яё\s]+)\s+[\d\s,]+`

---

### `validate_and_clean_data(data: dict) -> tuple[bool, str]`
Валидация и очистка данных чека.

**Параметры:**
- `data`: Словарь с данными чека

**Возвращает:**
- `is_valid` (bool): True если валидно
- `message` (str): Описание ошибки или "OK"

**Обязательные поля:**
- `full_name`
- `amount`
- `buyer_inn`
- `date`

**Валидация:**
- ИНН: 10 или 12 цифр (`^\d{10}$|^\d{12}$`)

---

## Drive Handler

### `class DriveHandler`

#### `__init__(root_folder_id: str)`
Инициализация Drive handler.

**Параметры:**
- `root_folder_id`: ID корневой папки на Google Drive

**Создает:** Google Drive v3 service

---

#### `get_or_create_folder(folder_name: str, parent_id: str) -> str`
Получение или создание папки.

**Параметры:**
- `folder_name`: Название папки
- `parent_id`: ID родительской папки

**Возвращает:** ID папки

**Логика:**
1. Поиск существующей папки по имени и родителю
2. Если не найдена - создание новой
3. Возврат ID

**Drive API запросы:**
- `files().list()` для поиска
- `files().create()` для создания

---

#### `upload_file(file_path: str, buyer_inn: str, receipt_date: datetime, full_name: str) -> dict`
Загрузка файла на Drive.

**Параметры:**
- `file_path`: Путь к локальному файлу
- `buyer_inn`: ИНН покупателя
- `receipt_date`: Дата чека (datetime объект)
- `full_name`: ФИО в формате "Фамилия И.О."

**Возвращает:**
```python
{
    'file_id': 'abc123...',
    'web_link': 'https://drive.google.com/...',
    'filename': 'Сабатаров А.Г. 13.08.2025.jpg',
    'folder_path': '9705246070/08-2025'
}
```

**Структура папок:**
```
Root Folder
└── {buyer_inn}
    └── {MM-YYYY}
        └── {full_name} {DD.MM.YYYY}.{ext}
```

**Пример:**
```
Root Folder
└── 9705246070
    └── 08-2025
        └── Сабатаров А.Г. 13.08.2025.jpg
```

---

## Sheets Handler

### `class SheetsHandler`

#### `__init__(spreadsheet_id: str)`
Инициализация Sheets handler.

**Параметры:**
- `spreadsheet_id`: ID Google Sheets таблицы

**Создает:** Google Sheets v4 service

---

#### `add_receipt_data(data: dict) -> dict`
Добавление данных чека в таблицу.

**Параметры:**
- `data`: Словарь с данными чека

**Возвращает:** Результат операции append

**Структура данных:**
```python
{
    'date': '13.08.2025',
    'full_name': 'Сабатаров А.Г.',
    'buyer_inn': '9705246070',
    'services': 'актерские услуги',
    'amount': '7 021.00 ₽',
    'status': 'Действителен',
    'fns_link': 'https://...',
    'drive_link': 'https://...'
}
```

**Диапазон:** `A:H` (колонки A-H)

**Метод:** `values().append()` с `valueInputOption='USER_ENTERED'`

---

#### `setup_headers() -> dict`
Установка заголовков таблицы.

**Возвращает:** Результат операции update

**Заголовки:**
| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| Дата | ФИО | ИНН покупателя | Наименование услуг | Сумма | Статус | Ссылка ФНС | Ссылка Drive |

**Диапазон:** `A1:H1`

**Примечание:** Запускать один раз при первой настройке

---

## Google Auth

### `get_google_credentials() -> Credentials`
Получение Google API credentials.

**Возвращает:** Google OAuth2 Credentials объект

**Процесс:**
1. Проверка наличия `token.pickle`
2. Загрузка сохраненных credentials
3. Если невалидны:
   - Обновление через refresh_token
   - Или новая авторизация через браузер
4. Сохранение в `token.pickle`

**SCOPES:**
- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/spreadsheets`

**Файлы:**
- `credentials.json` - OAuth 2.0 client secrets (из Google Cloud Console)
- `token.pickle` - сохраненные токены (генерируется автоматически)

**OAuth Flow:**
1. Первый запуск: открывается браузер
2. Пользователь авторизуется в Google
3. Токены сохраняются локально
4. Последующие запуски: автоматическое использование токенов

---

## Data Structures

### Receipt Data

Основная структура данных чека:

```python
receipt_data = {
    # Обязательные поля
    'full_name': str,      # "Фамилия И.О."
    'amount': str,         # "7 021.00 ₽"
    'buyer_inn': str,      # "9705246070" (10 или 12 цифр)
    'date': str,           # "13.08.2025" (dd.mm.yyyy)
    
    # Дополнительные поля
    'services': str,       # "актерские услуги"
    'seller_inn': str,     # "123456789012" (12 цифр)
    'status': str,         # "Действителен" | "Аннулирован"
    'fns_url': str,        # "https://lknpd.nalog.ru/..."
    'drive_link': str,     # "https://drive.google.com/..." (после загрузки)
    
    # Служебные поля
    'date_obj': datetime,  # Объект datetime для Drive
}
```

### Media Group Info

Структура для управления альбомами:

```python
media_group_info = {
    'photos': list,        # Список PhotoSize объектов
    'user_id': int,        # ID пользователя
    'chat_id': int,        # ID чата
    'notified': bool,      # Флаг уведомления
    'processing': bool,    # Флаг обработки
}
```

### Pending Receipt

Временное хранилище обрабатываемого чека:

```python
pending_receipt = {
    'data': dict,          # receipt_data
    'file_path': str,      # Путь к временному файлу
}
```

---

## Error Handling

### Типичные ошибки

#### OpenAI Vision
```python
# JSONDecodeError
return False, {}, f"Ошибка парсинга JSON: {str(e)}"

# General Exception
return False, {}, f"Ошибка OpenAI: {str(e)}"
```

#### QR Parser
```python
# Если QR не найден
return None

# Exception
print(f"Ошибка при чтении QR: {e}")
return None
```

#### Drive Upload
```python
# Exception в upload_and_save
return False, f"Ошибка при сохранении: {str(e)}"
```

#### Validation
```python
# Отсутствует поле
return False, f"Отсутствует поле: {field}"

# Некорректный ИНН
return False, "Некорректный ИНН покупателя"
```

---

## Usage Examples

### Полный цикл обработки

```python
from receipt_processor import ReceiptProcessor

# Инициализация
processor = ReceiptProcessor()

# Обработка изображения
success, data, message = processor.process_receipt_image('receipt.jpg')

if success:
    print(f"Данные извлечены: {data}")
    
    # Загрузка на Drive и в Sheets
    upload_success, result = processor.upload_and_save('receipt.jpg', data)
    
    if upload_success:
        print(result)
    else:
        print(f"Ошибка загрузки: {result}")
else:
    print(f"Ошибка обработки: {message}")
```

### Только Vision парсинг

```python
from openai_vision import OpenAIVisionParser

parser = OpenAIVisionParser()
success, data, message = parser.parse_receipt('receipt.jpg')

if success:
    print(data['full_name'])
    print(data['amount'])
```

### Только QR извлечение

```python
from qr_parser import extract_qr_from_image, parse_fns_url

# Извлечь URL
url = extract_qr_from_image('receipt.jpg')

# Парсить URL
if url:
    qr_data = parse_fns_url(url)
    print(qr_data['seller_inn'])
    print(qr_data['receipt_id'])
```

### Только Drive загрузка

```python
from drive_handler import DriveHandler
from datetime import datetime

drive = DriveHandler('your_folder_id')
result = drive.upload_file(
    file_path='receipt.jpg',
    buyer_inn='9705246070',
    receipt_date=datetime(2025, 8, 13),
    full_name='Сабатаров А.Г.'
)

print(result['web_link'])
```

### Только Sheets сохранение

```python
from sheets_handler import SheetsHandler

sheets = SheetsHandler('your_sheet_id')
sheets.add_receipt_data({
    'date': '13.08.2025',
    'full_name': 'Сабатаров А.Г.',
    'buyer_inn': '9705246070',
    'services': 'актерские услуги',
    'amount': '7 021.00 ₽',
    'status': 'Действителен',
    'fns_link': 'https://...',
    'drive_link': 'https://...'
})
```

---

## Rate Limits & Quotas

### OpenAI API
- **Модель:** gpt-4o-mini
- **Стоимость:** ~$0.0003 на запрос
- **Rate limit:** Зависит от тарифного плана

### Google Drive API
- **Queries per day:** 1,000,000,000
- **Queries per 100 seconds per user:** 1,000

### Google Sheets API
- **Read requests per minute per user:** 60
- **Write requests per minute per user:** 60

### Telegram Bot API
- **Messages per second:** 30
- **Messages per second to same chat:** 1
- **No cost**

---

## Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | ✅ | `123456:ABC-DEF...` |
| `GOOGLE_DRIVE_FOLDER_ID` | ID корневой папки Drive | ✅ | `1aB2cD3eF4...` |
| `GOOGLE_SHEET_ID` | ID Google Sheets таблицы | ✅ | `1aB2cD3eF4...` |
| `OPENAI_API_KEY` | API ключ OpenAI | ✅ | `sk-proj-...` |

---

## Logging

### Log Levels

```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
```

### Log Messages

- `INFO`: Запуск бота, успешные операции
- `ERROR`: Ошибки обработки, API ошибки

### Examples

```
2025-01-15 19:05:00 - bot - INFO - 🤖 Бот запущен!
2025-01-15 19:05:10 - bot - ERROR - Ошибка обработки фото: ...
```
