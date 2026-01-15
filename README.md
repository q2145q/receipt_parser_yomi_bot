# Receipt Parser Yomi 🤖📄

Telegram бот для автоматической обработки чеков самозанятых с загрузкой на Google Drive и добавлением в Google Sheets.

## Возможности

- 📸 Распознавание чеков из фото (одиночных или пачкой)
- 📄 Поддержка PDF файлов
- 🔗 Обработка ссылок на чеки ФНС
- 🤖 Автоматическое извлечение данных через GPT-4o-mini Vision
- 📊 Автоматическое добавление в Google Sheets
- 📁 Структурированное хранение на Google Drive (по ИНН/месяцам)
- ✅ Подтверждение данных перед сохранением

## Технологии

- Python 3.12
- python-telegram-bot
- OpenAI GPT-4o-mini Vision API
- Google Drive API
- Google Sheets API
- pyzbar (парсинг QR-кодов)

## Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/YOUR_USERNAME/receipt_parser_yomi.git
cd receipt_parser_yomi
```

### 2. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Установка системных библиотек (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y libzbar0 zbar-tools
sudo apt-get install -y libgl1 libglib2.0-0
sudo apt-get install -y tesseract-ocr tesseract-ocr-rus
sudo apt-get install -y poppler-utils
```

### 5. Настройка Google API

1. Перейди в [Google Cloud Console](https://console.cloud.google.com/)
2. Создай новый проект
3. Включи API:
   - Google Drive API
   - Google Sheets API
4. Создай OAuth 2.0 credentials (Desktop app)
5. Скачай `credentials.json` и помести в корень проекта
6. Создай папку на Google Drive для чеков
7. Создай Google Sheets таблицу

### 6. Настройка Telegram Bot

1. Создай бота через [@BotFather](https://t.me/BotFather)
2. Получи токен бота

### 7. Настройка OpenAI API

1. Получи API ключ на [platform.openai.com](https://platform.openai.com/api-keys)

### 8. Настройка переменных окружения

Создай файл `.env`:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
GOOGLE_SHEET_ID=your_spreadsheet_id
OPENAI_API_KEY=your_openai_api_key
```

**Как получить ID:**
- **GOOGLE_DRIVE_FOLDER_ID**: из URL папки `https://drive.google.com/drive/folders/FOLDER_ID`
- **GOOGLE_SHEET_ID**: из URL таблицы `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`

## Запуск

### Первый запуск (авторизация Google)
```bash
python3 test_auth.py
```
Откроется браузер для авторизации → разреши доступ → создастся `token.pickle`

### Запуск бота
```bash
python3 bot.py
```

## Использование

1. Найди бота в Telegram
2. Отправь команду `/start`
3. Отправь:
   - 📸 Одно фото чека
   - 📸📸📸 Несколько фото сразу (альбомом)
   - 📄 PDF файл чека
4. Проверь распознанные данные
5. Нажми "✅ Все верно" для загрузки

## Структура проекта
```
receipt_parser_yomi/
├── bot.py                  # Главный файл Telegram бота
├── receipt_processor.py    # Обработчик чеков
├── openai_vision.py        # Распознавание через OpenAI
├── qr_parser.py           # Парсинг QR-кодов
├── ocr_handler.py         # OCR (резервный вариант)
├── drive_handler.py       # Работа с Google Drive
├── sheets_handler.py      # Работа с Google Sheets
├── google_auth.py         # Авторизация Google API
├── requirements.txt       # Зависимости Python
├── .env                   # Переменные окружения (не в git)
├── credentials.json       # Google OAuth (не в git)
└── README.md             # Документация
```

## Стоимость использования

- **OpenAI GPT-4o-mini Vision**: ~$0.0003 за чек (~0.03₽)
- **Google Drive/Sheets API**: бесплатно (в пределах квот)
- **Telegram Bot API**: бесплатно

## Автор

Миша Абрамян

## Лицензия

MIT
```

---

## Шаг 3: Обновляем requirements.txt

**Файл `requirements.txt`:**
```
python-telegram-bot[job-queue]==20.7
google-api-python-client==2.108.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
opencv-python==4.8.1.78
pyzbar==0.1.9
requests==2.31.0
pillow==10.1.0
python-dotenv==1.0.0
openai==1.54.0
pdf2image==1.17.0
pytesseract==0.3.10
numpy<2