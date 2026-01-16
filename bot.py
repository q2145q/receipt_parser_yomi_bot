import os
import logging
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv
from receipt_processor import ReceiptProcessor
from qr_parser import parse_fns_url
from drive_handler import DriveHandler
from analysis_handler import AnalysisSheetHandler

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация процессора чеков
processor = ReceiptProcessor()

# Хранилище для папок анализа (user_id -> folder_info)
analysis_folders = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start
    """
    await update.message.reply_text(
        "👋 Привет! Я бот для обработки чеков самозанятых.\n\n"
        "📤 Отправь мне:\n"
        "• 📸 Фото чека (или несколько сразу)\n"
        "• 📄 PDF файл\n"
        "• 🔗 Ссылку на чек ФНС\n\n"
        "🔍 Команды:\n"
        "• /full_analyze - массовая обработка чеков из папки\n\n"
        "Я распознаю данные и загружу чек на Google Drive + добавлю в таблицу."
    )


async def full_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /full_analyze - массовая обработка чеков
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    await update.message.reply_text("📁 Создаю папку для анализа...")
    
    try:
        # Создаем папку с именем: @username ГГГГ-ММ-ДД ЧЧ-ММ
        timestamp = datetime.now().strftime("%Y-%m-%d %H-%M")
        folder_name = f"@{username} {timestamp}" if not username.startswith('user_') else f"{username} {timestamp}"
        
        drive = DriveHandler(os.getenv('GOOGLE_DRIVE_FOLDER_ID'))
        folder_id, folder_link = drive.create_analysis_folder(folder_name)
        
        # Сохраняем информацию о папке
        analysis_folders[user_id] = {
            'folder_id': folder_id,
            'folder_name': folder_name,
            'username': f"@{username}" if not username.startswith('user_') else username
        }
        
        # Отправляем ссылку на папку с кнопкой
        keyboard = [
            [InlineKeyboardButton("🚀 Начать анализ", callback_data=f'analyze_{user_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"✅ Папка создана!\n\n"
            f"📂 Название: {folder_name}\n"
            f"🔗 Ссылка: {folder_link}\n\n"
            f"📋 Инструкция:\n"
            f"1. Перейди по ссылке выше\n"
            f"2. Загрузи чеки (фото JPG/PNG или PDF)\n"
            f"3. Нажми кнопку \"Начать анализ\" ниже\n\n"
            f"⚠️ Убедись, что загрузил все нужные чеки перед началом анализа!"
        )
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка создания папки: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатий на кнопки
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Обработка кнопки "Начать анализ"
    if callback_data.startswith('analyze_'):
        user_id = int(callback_data.split('_')[1])
        
        # Проверяем, что это тот же пользователь
        if user_id != update.effective_user.id:
            await query.edit_message_text("❌ Эта кнопка не для тебя!")
            return
        
        # Проверяем, что папка существует
        if user_id not in analysis_folders:
            await query.edit_message_text("❌ Папка не найдена. Создай новую через /full_analyze")
            return
        
        folder_info = analysis_folders[user_id]
        
        await query.edit_message_text("🔄 Начинаю обработку чеков...\nЭто может занять несколько минут.")
        
        # Запускаем обработку
        await process_analysis_folder(query, folder_info)

async def process_analysis_folder(query, folder_info):
    """
    Обработка всех файлов из папки анализа
    """
    try:
        logger.info(f"Начало обработки папки: {folder_info}")
        
        folder_id = folder_info['folder_id']
        folder_name = folder_info['folder_name']
        username = folder_info['username']
        
        # Получаем список файлов из папки
        drive = DriveHandler(os.getenv('GOOGLE_DRIVE_FOLDER_ID'))
        files = drive.list_files_in_folder(folder_id)
        
        logger.info(f"Найдено файлов: {len(files)}")
        
        if not files:
            await query.message.reply_text("❌ В папке нет файлов для обработки!")
            return
        
        await query.message.reply_text(f"📊 Найдено файлов: {len(files)}\nНачинаю обработку...")
        
        # Создаем таблицу для результатов
        sheet_title = f"{username}, {datetime.now().strftime('%Y-%m-%d %H-%M')}, анализ"
        analysis_sheet = AnalysisSheetHandler()
        spreadsheet_id, sheet_link = analysis_sheet.create_analysis_spreadsheet(sheet_title, folder_id)
        
        # Статистика
        total_files = len(files)
        processed_count = 0
        success_count = 0
        errors = []
        
        # Обрабатываем каждый файл
        for idx, file in enumerate(files, 1):
            try:
                file_id = file['id']
                file_name = file['name']
                file_type = file['mimeType']
                
                logger.info(f"Обработка файла {idx}/{total_files}: {file_name}")
                await query.message.reply_text(f"⏳ Обработка {idx}/{total_files}: {file_name}")
                
                # Скачиваем файл
                with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                    tmp_path = tmp_file.name
                
                drive.download_file(file_id, tmp_path)
                
                # Если PDF - конвертируем в JPG
                if file_type == 'application/pdf':
                    from pdf2image import convert_from_path
                    images = convert_from_path(tmp_path, first_page=1, last_page=1)
                    
                    if not images:
                        errors.append(f"{file_name}: Не удалось прочитать PDF")
                        os.unlink(tmp_path)
                        continue
                    
                    # Сохраняем как изображение
                    img_path = tmp_path.replace('.tmp', '.jpg')
                    images[0].save(img_path, 'JPEG')
                    os.unlink(tmp_path)
                    tmp_path = img_path
                
                # Обрабатываем чек
                success, data, message = processor.process_receipt_image(tmp_path)
                
                if success:
                    # Добавляем ссылку на файл в Drive
                    file_link = f"https://drive.google.com/file/d/{file_id}/view"
                    data['drive_link'] = file_link
                    
                    # Добавляем в таблицу
                    analysis_sheet.add_receipt_to_sheet(spreadsheet_id, data)
                    
                    success_count += 1
                    processed_count += 1
                else:
                    errors.append(f"{file_name}: {message}")
                    processed_count += 1
                
                # Удаляем временный файл
                os.unlink(tmp_path)
                
            except Exception as e:
                logger.error(f"Ошибка обработки файла {file_name}: {e}")
                errors.append(f"{file_name}: {str(e)}")
                processed_count += 1
        
        # Формируем итоговое сообщение
        result_message = f"✅ <b>Анализ завершен!</b>\n\n"
        result_message += f"📊 Обработано чеков: {processed_count}/{total_files}\n"
        result_message += f"✅ Успешно: {success_count}\n"
        result_message += f"❌ Ошибок: {len(errors)}\n\n"
        result_message += f"📁 Таблица с результатами:\n{sheet_link}\n\n"
        
        if errors:
            result_message += f"⚠️ <b>Список ошибок:</b>\n"
            for error in errors[:10]:  # Показываем первые 10 ошибок
                result_message += f"• {error}\n"
            
            if len(errors) > 10:
                result_message += f"\n... и еще {len(errors) - 10} ошибок"
        
        await query.message.reply_text(result_message, parse_mode='HTML')
        
        # Удаляем информацию о папке из памяти
        user_id = query.from_user.id  # ИСПРАВЛЕНО
        if user_id in analysis_folders:
            del analysis_folders[user_id]
        
    except Exception as e:
        logger.error(f"Ошибка обработки папки: {e}")
        await query.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка каждого фото отдельно (без группировки)
    """
    message = update.message
    photo = message.photo[-1]
    
    # Каждое фото обрабатываем независимо
    await message.reply_text("⏳ Обрабатываю чек...")
    
    try:
        # Скачиваем фото
        photo_file = await photo.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            await photo_file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Обрабатываем чек
        success, data, message_text = processor.process_receipt_image(tmp_path)
        
        if not success:
            await message.reply_text(
                f"❌ Ошибка обработки:\n{message_text}\n\n"
                f"Попробуй отправить более четкое фото."
            )
            os.unlink(tmp_path)
            return
        
        # Добавляем username пользователя
        username = update.effective_user.username or f"user_{update.effective_user.id}"
        data['username'] = f"@{username}" if not username.startswith('user_') else username
        
        # Сразу загружаем без подтверждения
        upload_success, upload_message = processor.upload_and_save(tmp_path, data)
        
        if upload_success:
            # Успешно загружено
            # Формируем сообщение с учетом возможных ошибок
            error_info = ""
            if data.get('error_details'):
                error_info = f"\n\n⚠️ Ошибки распознавания:\n{data['error_details']}"
            
            summary = (
                f"✅ <b>Чек обработан!</b>\n\n"
                f"👤 {data.get('full_name')}\n"
                f"💰 {data.get('amount')}\n"
                f"📅 {data.get('date')}\n"
                f"📝 {data.get('services')}\n"
                f"📁 Загружено на Drive и в таблицу"
                f"{error_info}"
            )
            await message.reply_text(summary, parse_mode='HTML')
        else:
            await message.reply_text(f"❌ Ошибка сохранения:\n{upload_message}")
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await message.reply_text(f"❌ Произошла ошибка: {str(e)}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка PDF документа
    """
    document = update.message.document
    
    # Проверяем, что это PDF
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text(
            "❌ Поддерживаются только PDF файлы.\n"
            "Отправь фото чека или PDF."
        )
        return
    
    await update.message.reply_text("⏳ Обрабатываю PDF...")
    
    try:
        # Скачиваем PDF
        file = await document.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Конвертируем PDF в изображение (первую страницу)
        from pdf2image import convert_from_path
        images = convert_from_path(tmp_path, first_page=1, last_page=1)
        
        if not images:
            await update.message.reply_text("❌ Не удалось прочитать PDF")
            os.unlink(tmp_path)
            return
        
        # Сохраняем как изображение
        img_path = tmp_path.replace('.pdf', '.jpg')
        images[0].save(img_path, 'JPEG')
        
        # Обрабатываем как изображение
        success, data, message_text = processor.process_receipt_image(img_path)
        
        if not success:
            await update.message.reply_text(
                f"❌ Ошибка обработки:\n{message_text}"
            )
            os.unlink(tmp_path)
            os.unlink(img_path)
            return
        
        # Добавляем username пользователя
        username = update.effective_user.username or f"user_{update.effective_user.id}"
        data['username'] = f"@{username}" if not username.startswith('user_') else username
        
        # Удаляем временное изображение
        os.unlink(img_path)
        
        # Загружаем оригинальный PDF
        upload_success, upload_message = processor.upload_and_save(tmp_path, data)
        
        if upload_success:
            # Формируем сообщение с учетом возможных ошибок
            error_info = ""
            if data.get('error_details'):
                error_info = f"\n\n⚠️ Ошибки распознавания:\n{data['error_details']}"
            
            summary = (
                f"✅ <b>Чек обработан!</b>\n\n"
                f"👤 {data.get('full_name')}\n"
                f"💰 {data.get('amount')}\n"
                f"📅 {data.get('date')}\n"
                f"📝 {data.get('services')}\n"
                f"📁 Загружено на Drive и в таблицу"
                f"{error_info}"
            )
            await update.message.reply_text(summary, parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ Ошибка сохранения:\n{upload_message}")
        
        # Удаляем временный PDF
        os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки PDF: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка текстовых сообщений (ссылок на чеки)
    """
    text = update.message.text
    
    # Проверяем, это ссылка на ФНС
    if 'lknpd.nalog.ru' in text or 'npd.nalog.ru' in text:
        await update.message.reply_text(
            "🔗 Получил ссылку на чек.\n\n"
            "⚠️ Для полной обработки отправь фото или PDF чека.\n"
            "По ссылке я не могу автоматически извлечь данные."
        )
        
        # Парсим URL
        url_data = parse_fns_url(text)
        if url_data:
            await update.message.reply_text(
                f"📋 Информация из ссылки:\n"
                f"ИНН продавца: {url_data.get('seller_inn', 'не найден')}\n"
                f"ID чека: {url_data.get('receipt_id', 'не найден')}\n\n"
                f"Отправь фото этого чека для полной обработки."
            )
    else:
        await update.message.reply_text(
            "❓ Не понял команду.\n\n"
            "Отправь:\n"
            "• 📸 Фото чека (можно несколько сразу)\n"
            "• 📄 PDF файл\n"
            "• 🔗 Ссылку на чек ФНС\n\n"
            "Или используй команду /full_analyze для массовой обработки"
        )


def main():
    """
    Запуск бота
    """
    # Получаем токен из .env
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в .env")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("full_analyze", full_analyze))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()